"""
文档处理器
支持 PDF、DOCX、TXT 文件的解析和切分
"""
import os
import tempfile
from typing import List, BinaryIO, Union
from io import BytesIO

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

import sys
sys.path.insert(0, ".")
from config import get_config


class DocumentProcessor:
    """文档处理器 - 加载和切分文档"""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        初始化文档处理器
        
        Args:
            chunk_size: 切分块大小，默认使用配置值
            chunk_overlap: 切分重叠大小，默认使用配置值
        """
        config = get_config().rag
        self.chunk_size = chunk_size or config.chunk_size
        self.chunk_overlap = chunk_overlap or config.chunk_overlap
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )
    
    def load_pdf(self, file: Union[str, BinaryIO], filename: str = None) -> List[Document]:
        """
        加载 PDF 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名（用于元数据）
            
        Returns:
            Document 列表
        """
        # 如果是文件对象，先保存到临时文件
        if hasattr(file, 'read'):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name
            try:
                loader = PyPDFLoader(tmp_path)
                documents = loader.load()
            finally:
                os.unlink(tmp_path)
        else:
            loader = PyPDFLoader(file)
            documents = loader.load()
            filename = filename or os.path.basename(file)
        
        # 更新元数据
        for doc in documents:
            if filename:
                doc.metadata['source'] = filename
            doc.metadata['file_type'] = 'pdf'
        
        return documents
    
    def load_docx(self, file: Union[str, BinaryIO], filename: str = None) -> List[Document]:
        """
        加载 DOCX 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名（用于元数据）
            
        Returns:
            Document 列表
        """
        # 如果是文件对象，先保存到临时文件
        if hasattr(file, 'read'):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name
            try:
                loader = Docx2txtLoader(tmp_path)
                documents = loader.load()
            finally:
                os.unlink(tmp_path)
        else:
            loader = Docx2txtLoader(file)
            documents = loader.load()
            filename = filename or os.path.basename(file)
        
        # 更新元数据
        for doc in documents:
            if filename:
                doc.metadata['source'] = filename
            doc.metadata['file_type'] = 'docx'
            # DOCX 没有页码，用段落号代替
            doc.metadata['page'] = 1
        
        return documents
    
    def load_txt(self, file: Union[str, BinaryIO], filename: str = None) -> List[Document]:
        """
        加载 TXT 文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名（用于元数据）
            
        Returns:
            Document 列表
        """
        # 如果是文件对象，先保存到临时文件
        if hasattr(file, 'read'):
            content = file.read()
            if isinstance(content, bytes):
                # 尝试多种编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        content = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
            
            documents = [Document(
                page_content=content,
                metadata={'source': filename or 'unknown.txt', 'file_type': 'txt', 'page': 1}
            )]
        else:
            loader = TextLoader(file, encoding='utf-8')
            try:
                documents = loader.load()
            except UnicodeDecodeError:
                # 尝试 GBK 编码
                loader = TextLoader(file, encoding='gbk')
                documents = loader.load()
            
            filename = filename or os.path.basename(file)
            for doc in documents:
                doc.metadata['source'] = filename
                doc.metadata['file_type'] = 'txt'
                doc.metadata['page'] = 1
        
        return documents
    
    def load_file(self, file: Union[str, BinaryIO], filename: str = None) -> List[Document]:
        """
        根据文件类型自动加载文件
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名（用于元数据和类型检测）
            
        Returns:
            Document 列表
        """
        # 获取文件名
        if filename is None:
            if hasattr(file, 'name'):
                filename = file.name
            elif isinstance(file, str):
                filename = os.path.basename(file)
            else:
                raise ValueError("无法确定文件类型，请提供 filename 参数")
        
        # 根据扩展名选择加载器
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            return self.load_pdf(file, filename)
        elif ext in ['docx', 'doc']:
            return self.load_docx(file, filename)
        elif ext == 'txt':
            return self.load_txt(file, filename)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        切分文档
        
        Args:
            documents: 原始文档列表
            
        Returns:
            切分后的文档列表
        """
        split_docs = self.text_splitter.split_documents(documents)
        
        # 为每个切片添加 chunk_index
        for i, doc in enumerate(split_docs):
            doc.metadata['chunk_index'] = i
        
        return split_docs
    
    def process(self, file: Union[str, BinaryIO], filename: str = None) -> List[Document]:
        """
        完整处理流程：加载 + 切分
        
        Args:
            file: 文件路径或文件对象
            filename: 文件名
            
        Returns:
            切分后的文档列表
        """
        documents = self.load_file(file, filename)
        return self.split_documents(documents)
    
    def process_multiple(
        self, 
        files: List[Union[str, BinaryIO]], 
        filenames: List[str] = None
    ) -> List[Document]:
        """
        处理多个文件
        
        Args:
            files: 文件列表
            filenames: 文件名列表
            
        Returns:
            所有文档的切分结果
        """
        all_docs = []
        filenames = filenames or [None] * len(files)
        
        for file, filename in zip(files, filenames):
            docs = self.process(file, filename)
            all_docs.extend(docs)
        
        return all_docs

