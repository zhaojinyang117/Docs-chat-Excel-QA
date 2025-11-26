"""
日志审计模块
记录用户查询、检索来源和回答
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
import uuid

import sys
sys.path.insert(0, ".")
from config import get_config


@dataclass
class AuditRecord:
    """审计记录"""
    id: str
    timestamp: str
    username: str
    query_type: str  # doc_chat, excel_qa
    question: str
    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AuditRecord":
        return cls(**data)


class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, log_file: str = None):
        """
        初始化日志记录器
        
        Args:
            log_file: 日志文件路径
        """
        config = get_config()
        self.logs_dir = config.logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.log_file = log_file or os.path.join(self.logs_dir, "audit.json")
        self._ensure_file()
    
    def _ensure_file(self) -> None:
        """确保日志文件存在"""
        if not os.path.exists(self.log_file):
            self._save_logs([])
    
    def _load_logs(self) -> List[Dict]:
        """加载日志"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_logs(self, logs: List[Dict]) -> None:
        """保存日志"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    
    def log(
        self,
        username: str,
        query_type: str,
        question: str,
        answer: str,
        sources: List[Dict[str, Any]] = None,
        metadata: Dict[str, Any] = None
    ) -> AuditRecord:
        """
        记录一条审计日志
        
        Args:
            username: 用户名
            query_type: 查询类型（doc_chat/excel_qa）
            question: 用户问题
            answer: 系统回答
            sources: 来源信息
            metadata: 其他元数据
            
        Returns:
            创建的审计记录
        """
        record = AuditRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            username=username,
            query_type=query_type,
            question=question,
            answer=answer[:2000] if len(answer) > 2000 else answer,  # 限制长度
            sources=sources or [],
            metadata=metadata or {}
        )
        
        logs = self._load_logs()
        logs.append(record.to_dict())
        self._save_logs(logs)
        
        return record
    
    def log_doc_chat(
        self,
        username: str,
        question: str,
        answer: str,
        sources: List[Dict[str, Any]] = None,
        file_name: str = None
    ) -> AuditRecord:
        """
        记录文档聊天日志
        
        Args:
            username: 用户名
            question: 用户问题
            answer: 系统回答
            sources: 来源信息
            file_name: 文件名
            
        Returns:
            审计记录
        """
        return self.log(
            username=username,
            query_type="doc_chat",
            question=question,
            answer=answer,
            sources=sources,
            metadata={"file_name": file_name} if file_name else {}
        )
    
    def log_excel_qa(
        self,
        username: str,
        question: str,
        answer: str,
        sheet_name: str = None,
        file_name: str = None,
        generated_code: str = None
    ) -> AuditRecord:
        """
        记录 Excel QA 日志
        
        Args:
            username: 用户名
            question: 用户问题
            answer: 系统回答
            sheet_name: Sheet 名称
            file_name: 文件名
            generated_code: 生成的代码
            
        Returns:
            审计记录
        """
        metadata = {}
        if file_name:
            metadata["file_name"] = file_name
        if sheet_name:
            metadata["sheet_name"] = sheet_name
        if generated_code:
            metadata["generated_code"] = generated_code
        
        return self.log(
            username=username,
            query_type="excel_qa",
            question=question,
            answer=answer,
            metadata=metadata
        )
    
    def get_logs(
        self,
        username: str = None,
        query_type: str = None,
        start_time: str = None,
        end_time: str = None,
        limit: int = None
    ) -> List[AuditRecord]:
        """
        获取日志记录
        
        Args:
            username: 按用户名过滤
            query_type: 按查询类型过滤
            start_time: 开始时间（ISO 格式）
            end_time: 结束时间（ISO 格式）
            limit: 返回数量限制
            
        Returns:
            审计记录列表
        """
        logs = self._load_logs()
        
        # 过滤
        if username:
            logs = [l for l in logs if l.get("username") == username]
        if query_type:
            logs = [l for l in logs if l.get("query_type") == query_type]
        if start_time:
            logs = [l for l in logs if l.get("timestamp", "") >= start_time]
        if end_time:
            logs = [l for l in logs if l.get("timestamp", "") <= end_time]
        
        # 按时间倒序
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # 限制数量
        if limit:
            logs = logs[:limit]
        
        return [AuditRecord.from_dict(l) for l in logs]
    
    def get_user_stats(self, username: str) -> Dict[str, Any]:
        """
        获取用户统计信息
        
        Args:
            username: 用户名
            
        Returns:
            统计信息
        """
        logs = self._load_logs()
        user_logs = [l for l in logs if l.get("username") == username]
        
        doc_chat_count = sum(1 for l in user_logs if l.get("query_type") == "doc_chat")
        excel_qa_count = sum(1 for l in user_logs if l.get("query_type") == "excel_qa")
        
        return {
            "username": username,
            "total_queries": len(user_logs),
            "doc_chat_count": doc_chat_count,
            "excel_qa_count": excel_qa_count,
            "first_query": min((l.get("timestamp") for l in user_logs), default=None),
            "last_query": max((l.get("timestamp") for l in user_logs), default=None)
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        获取全局统计信息
        
        Returns:
            统计信息
        """
        logs = self._load_logs()
        
        users = set(l.get("username") for l in logs)
        doc_chat_count = sum(1 for l in logs if l.get("query_type") == "doc_chat")
        excel_qa_count = sum(1 for l in logs if l.get("query_type") == "excel_qa")
        
        return {
            "total_queries": len(logs),
            "unique_users": len(users),
            "doc_chat_count": doc_chat_count,
            "excel_qa_count": excel_qa_count
        }
    
    def clear_logs(self, username: str = None) -> int:
        """
        清除日志
        
        Args:
            username: 指定用户，为 None 时清除所有
            
        Returns:
            清除的记录数
        """
        logs = self._load_logs()
        original_count = len(logs)
        
        if username:
            logs = [l for l in logs if l.get("username") != username]
        else:
            logs = []
        
        self._save_logs(logs)
        return original_count - len(logs)
    
    def export_logs(
        self,
        output_file: str,
        username: str = None,
        query_type: str = None
    ) -> int:
        """
        导出日志到文件
        
        Args:
            output_file: 输出文件路径
            username: 按用户名过滤
            query_type: 按查询类型过滤
            
        Returns:
            导出的记录数
        """
        records = self.get_logs(username=username, query_type=query_type)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                [r.to_dict() for r in records],
                f,
                ensure_ascii=False,
                indent=2
            )
        
        return len(records)


# 全局日志实例
_logger: Optional[AuditLogger] = None


def get_logger() -> AuditLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger


def log_query(
    username: str,
    query_type: str,
    question: str,
    answer: str,
    **kwargs
) -> AuditRecord:
    """便捷函数：记录查询"""
    return get_logger().log(
        username=username,
        query_type=query_type,
        question=question,
        answer=answer,
        **kwargs
    )

