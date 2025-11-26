"""
文档聊天引擎
基于 RAG 的文档问答，支持会话历史和来源追溯
"""
from typing import List, Dict, Any, Optional, BinaryIO, Union
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, AIMessage

import sys
sys.path.insert(0, ".")
from src.llm_factory import get_llm, get_embedding
from src.processors.document_processor import DocumentProcessor
from src.stores.vector_store import VectorStore


@dataclass
class ChatResponse:
    """聊天响应"""
    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources
        }


class DocChatEngine:
    """文档聊天引擎"""
    
    # 系统提示词模板
    SYSTEM_TEMPLATE = """你是一个专业的文档问答助手。请根据提供的上下文信息回答用户的问题。

要求：
1. 只根据提供的上下文信息回答，不要编造内容
2. 如果上下文中没有相关信息，请明确告知用户
3. 回答要准确、简洁、有条理
4. 如果可能，请指出信息来源（如页码）

上下文信息：
{context}"""
    
    def __init__(
        self,
        index_name: str = "doc_chat",
        llm=None,
        embedding=None
    ):
        """
        初始化文档聊天引擎
        
        Args:
            index_name: 向量索引名称
            llm: LLM 实例
            embedding: Embedding 实例
        """
        self.index_name = index_name
        self.llm = llm or get_llm()
        self.embedding = embedding or get_embedding()
        
        self.processor = DocumentProcessor()
        self.vector_store = VectorStore(
            embedding=self.embedding,
            index_name=index_name
        )
        
        # 会话历史
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []
        
        # 文档元数据
        self.loaded_files: List[str] = []
    
    def load_file(
        self,
        file: Union[str, BinaryIO],
        filename: str = None
    ) -> int:
        """
        加载单个文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            
        Returns:
            加载的文档块数量
        """
        documents = self.processor.process(file, filename)
        
        if self.vector_store.store is None:
            self.vector_store.create_from_documents(documents)
        else:
            self.vector_store.add_documents(documents)
        
        # 记录加载的文件
        actual_filename = filename or (file if isinstance(file, str) else getattr(file, 'name', 'unknown'))
        if actual_filename not in self.loaded_files:
            self.loaded_files.append(actual_filename)
        
        return len(documents)
    
    def load_files(
        self,
        files: List[Union[str, BinaryIO]],
        filenames: List[str] = None
    ) -> int:
        """
        加载多个文件
        
        Args:
            files: 文件列表
            filenames: 文件名列表
            
        Returns:
            加载的文档块总数
        """
        total = 0
        filenames = filenames or [None] * len(files)
        
        for file, filename in zip(files, filenames):
            total += self.load_file(file, filename)
        
        return total
    
    def _format_docs(self, docs: List[Document]) -> str:
        """格式化文档为字符串"""
        return "\n\n".join(doc.page_content for doc in docs)
    
    def _format_chat_history(self) -> str:
        """格式化聊天历史"""
        if not self.chat_history:
            return ""
        
        history_str = "\n聊天历史：\n"
        for msg in self.chat_history[-6:]:  # 只保留最近3轮对话
            if isinstance(msg, HumanMessage):
                history_str += f"用户: {msg.content}\n"
            else:
                history_str += f"助手: {msg.content}\n"
        return history_str
    
    def chat(self, question: str) -> ChatResponse:
        """
        进行对话
        
        Args:
            question: 用户问题
            
        Returns:
            ChatResponse 对象
        """
        if self.vector_store.store is None:
            raise ValueError("请先加载文档")
        
        # 检索相关文档
        results = self.vector_store.search(question)
        docs = [doc for doc, _ in results]
        
        # 构建上下文
        context = self._format_docs(docs)
        history = self._format_chat_history()
        
        # 构建提示词
        full_prompt = f"""{self.SYSTEM_TEMPLATE.format(context=context)}
{history}
用户问题：{question}

请回答："""
        
        # 调用 LLM
        response = self.llm.invoke(full_prompt)
        answer = response.content if hasattr(response, 'content') else str(response)
        
        # 更新聊天历史
        self.chat_history.append(HumanMessage(content=question))
        self.chat_history.append(AIMessage(content=answer))
        
        # 提取来源信息
        sources = []
        for doc, score in results:
            source_info = {
                "content": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "file_type": doc.metadata.get("file_type", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", 0),
                "score": float(score)
            }
            sources.append(source_info)
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )
    
    def ask(self, question: str) -> str:
        """
        简单问答（仅返回答案）
        
        Args:
            question: 用户问题
            
        Returns:
            答案文本
        """
        response = self.chat(question)
        return response.answer
    
    def get_relevant_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        获取相关文档（不调用 LLM）
        
        Args:
            query: 查询文本
            k: 返回数量
            
        Returns:
            相关文档列表
        """
        results = self.vector_store.search(query, k=k)
        
        return [
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "未知"),
                "page": doc.metadata.get("page", "N/A"),
                "score": float(score),
                "metadata": doc.metadata
            }
            for doc, score in results
        ]
    
    def clear_memory(self) -> None:
        """清空会话记忆"""
        self.chat_history = []
    
    def get_chat_history(self) -> List[Dict[str, str]]:
        """获取聊天历史"""
        history = []
        
        for msg in self.chat_history:
            history.append({
                "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                "content": msg.content
            })
        
        return history
    
    def save_index(self) -> None:
        """保存向量索引"""
        self.vector_store.save()
    
    def load_index(self) -> bool:
        """
        加载已保存的向量索引
        
        Returns:
            是否成功加载
        """
        if self.vector_store.exists():
            self.vector_store.load()
            return True
        return False
    
    def reset(self) -> None:
        """重置引擎（清空所有数据）"""
        self.vector_store.delete()
        self.chat_history = []
        self.loaded_files = []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "loaded_files": self.loaded_files,
            "document_count": self.vector_store.get_document_count(),
            "chat_history_length": len(self.chat_history)
        }
