"""
FAISS 向量存储封装
支持创建、保存、加载和检索
"""
import os
import pickle
from typing import List, Tuple, Optional, Dict, Any

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

import sys
sys.path.insert(0, ".")
from config import get_config
from src.llm_factory import get_embedding


class VectorStore:
    """FAISS 向量存储封装"""
    
    def __init__(
        self,
        embedding: Optional[OpenAIEmbeddings] = None,
        index_name: str = "default"
    ):
        """
        初始化向量存储
        
        Args:
            embedding: Embedding 模型实例
            index_name: 索引名称（用于持久化）
        """
        self.embedding = embedding or get_embedding()
        self.index_name = index_name
        self.store: Optional[FAISS] = None
        
        # 存储路径
        config = get_config()
        self.data_dir = config.data_dir
        os.makedirs(self.data_dir, exist_ok=True)
    
    @property
    def index_path(self) -> str:
        """获取索引文件路径"""
        return os.path.join(self.data_dir, f"{self.index_name}.faiss")
    
    @property
    def docstore_path(self) -> str:
        """获取文档存储路径"""
        return os.path.join(self.data_dir, f"{self.index_name}.pkl")
    
    def create_from_documents(self, documents: List[Document]) -> "VectorStore":
        """
        从文档列表创建向量存储
        
        Args:
            documents: 文档列表
            
        Returns:
            self（支持链式调用）
        """
        if not documents:
            raise ValueError("文档列表不能为空")
        
        self.store = FAISS.from_documents(documents, self.embedding)
        return self
    
    def add_documents(self, documents: List[Document]) -> "VectorStore":
        """
        添加文档到现有存储
        
        Args:
            documents: 要添加的文档列表
            
        Returns:
            self（支持链式调用）
        """
        if self.store is None:
            return self.create_from_documents(documents)
        
        self.store.add_documents(documents)
        return self
    
    def save(self) -> "VectorStore":
        """
        保存向量存储到磁盘
        
        Returns:
            self（支持链式调用）
        """
        if self.store is None:
            raise ValueError("向量存储为空，无法保存")
        
        self.store.save_local(self.data_dir, self.index_name)
        return self
    
    def load(self) -> "VectorStore":
        """
        从磁盘加载向量存储
        
        Returns:
            self（支持链式调用）
        """
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"索引文件不存在: {self.index_path}")
        
        self.store = FAISS.load_local(
            self.data_dir,
            self.embedding,
            self.index_name,
            allow_dangerous_deserialization=True
        )
        return self
    
    def exists(self) -> bool:
        """检查索引是否存在于磁盘"""
        return os.path.exists(self.index_path)
    
    def search(
        self,
        query: str,
        k: int = None,
        score_threshold: float = None
    ) -> List[Tuple[Document, float]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            k: 返回的文档数量，默认使用配置值
            score_threshold: 相似度阈值（可选）
            
        Returns:
            (文档, 相似度分数) 元组列表
        """
        if self.store is None:
            raise ValueError("向量存储未初始化")
        
        k = k or get_config().rag.top_k
        
        # 使用带分数的搜索
        results = self.store.similarity_search_with_score(query, k=k)
        
        # 过滤低于阈值的结果
        if score_threshold is not None:
            results = [(doc, score) for doc, score in results if score <= score_threshold]
        
        return results
    
    def search_documents(self, query: str, k: int = None) -> List[Document]:
        """
        搜索相似文档（仅返回文档）
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            文档列表
        """
        results = self.search(query, k)
        return [doc for doc, _ in results]
    
    def as_retriever(self, search_kwargs: Dict[str, Any] = None):
        """
        获取 LangChain Retriever 接口
        
        Args:
            search_kwargs: 搜索参数
            
        Returns:
            LangChain Retriever
        """
        if self.store is None:
            raise ValueError("向量存储未初始化")
        
        search_kwargs = search_kwargs or {"k": get_config().rag.top_k}
        return self.store.as_retriever(search_kwargs=search_kwargs)
    
    def delete(self) -> None:
        """删除持久化的索引文件"""
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        
        pkl_path = os.path.join(self.data_dir, f"{self.index_name}.pkl")
        if os.path.exists(pkl_path):
            os.remove(pkl_path)
        
        self.store = None
    
    def get_document_count(self) -> int:
        """获取存储的文档数量"""
        if self.store is None:
            return 0
        return len(self.store.docstore._dict)


def create_vector_store(
    documents: List[Document],
    index_name: str = "default",
    save: bool = True
) -> VectorStore:
    """
    便捷函数：创建向量存储
    
    Args:
        documents: 文档列表
        index_name: 索引名称
        save: 是否保存到磁盘
        
    Returns:
        VectorStore 实例
    """
    store = VectorStore(index_name=index_name)
    store.create_from_documents(documents)
    
    if save:
        store.save()
    
    return store


def load_vector_store(index_name: str = "default") -> VectorStore:
    """
    便捷函数：加载向量存储
    
    Args:
        index_name: 索引名称
        
    Returns:
        VectorStore 实例
    """
    store = VectorStore(index_name=index_name)
    store.load()
    return store

