"""
配置管理模块
支持从 Streamlit secrets 或环境变量读取配置
"""
import os
from dataclasses import dataclass, field
from typing import Optional

# 尝试导入 streamlit，如果不在 Streamlit 环境中则跳过
try:
    import streamlit as st
    IN_STREAMLIT = True
except ImportError:
    IN_STREAMLIT = False


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "text-embedding-ada-002"


@dataclass
class RAGConfig:
    """RAG 配置"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 4


@dataclass
class AppConfig:
    """应用配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    
    # 路径配置
    data_dir: str = "data"
    logs_dir: str = "logs"


def get_secret(key: str, default: str = "") -> str:
    """
    从 Streamlit secrets 或环境变量获取配置
    优先级：Streamlit secrets > 环境变量 > 默认值
    """
    # 尝试从 Streamlit secrets 获取
    if IN_STREAMLIT:
        try:
            # 支持嵌套键，如 "llm.api_key"
            parts = key.split(".")
            value = st.secrets
            for part in parts:
                value = value[part]
            return str(value)
        except (KeyError, TypeError, AttributeError):
            pass
    
    # 尝试从环境变量获取（将点替换为下划线，转大写）
    env_key = key.replace(".", "_").upper()
    env_value = os.getenv(env_key)
    if env_value:
        return env_value
    
    return default


def load_config() -> AppConfig:
    """加载应用配置"""
    config = AppConfig()
    
    # LLM 配置
    config.llm.api_key = get_secret("llm.api_key", get_secret("OPENAI_API_KEY", ""))
    config.llm.base_url = get_secret("llm.base_url", "https://api.openai.com/v1")
    config.llm.model = get_secret("llm.model", "gpt-3.5-turbo")
    config.llm.temperature = float(get_secret("llm.temperature", "0.7"))
    config.llm.max_tokens = int(get_secret("llm.max_tokens", "2000"))
    
    # 嵌入模型配置（默认使用与 LLM 相同的 API Key 和 Base URL）
    config.embedding.api_key = get_secret("embedding.api_key", config.llm.api_key)
    config.embedding.base_url = get_secret("embedding.base_url", config.llm.base_url)
    config.embedding.model = get_secret("embedding.model", "text-embedding-ada-002")
    
    # RAG 配置
    config.rag.chunk_size = int(get_secret("rag.chunk_size", "1000"))
    config.rag.chunk_overlap = int(get_secret("rag.chunk_overlap", "200"))
    config.rag.top_k = int(get_secret("rag.top_k", "4"))
    
    return config


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例（单例模式）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """重置配置（用于测试或重新加载）"""
    global _config
    _config = None

