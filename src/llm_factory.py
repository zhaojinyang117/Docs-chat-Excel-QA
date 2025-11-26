"""
LLM 和 Embedding 模型工厂
支持 OpenAI 兼容格式的 API
"""
from typing import Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import sys
sys.path.insert(0, ".")
from config import get_config, LLMConfig, EmbeddingConfig


class LLMFactory:
    """LLM 和 Embedding 模型工厂"""
    
    _llm_instance: Optional[ChatOpenAI] = None
    _embedding_instance: Optional[OpenAIEmbeddings] = None
    
    @classmethod
    def create_llm(
        cls,
        config: Optional[LLMConfig] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> ChatOpenAI:
        """
        创建 LLM 实例
        
        Args:
            config: LLM 配置，为 None 时使用全局配置
            temperature: 温度参数，覆盖配置中的值
            **kwargs: 其他传递给 ChatOpenAI 的参数
            
        Returns:
            ChatOpenAI 实例
        """
        if config is None:
            config = get_config().llm
        
        if not config.api_key:
            raise ValueError("未配置 API Key，请在 .streamlit/secrets.toml 或环境变量中设置")
        
        final_temperature = temperature if temperature is not None else config.temperature
        
        return ChatOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=final_temperature,
            max_tokens=config.max_tokens,
            **kwargs
        )
    
    @classmethod
    def create_embedding(
        cls,
        config: Optional[EmbeddingConfig] = None,
        **kwargs
    ) -> OpenAIEmbeddings:
        """
        创建 Embedding 模型实例
        
        Args:
            config: Embedding 配置，为 None 时使用全局配置
            **kwargs: 其他传递给 OpenAIEmbeddings 的参数
            
        Returns:
            OpenAIEmbeddings 实例
        """
        if config is None:
            config = get_config().embedding
        
        if not config.api_key:
            raise ValueError("未配置 Embedding API Key，请在 .streamlit/secrets.toml 或环境变量中设置")
        
        return OpenAIEmbeddings(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            **kwargs
        )
    
    @classmethod
    def get_llm(cls, **kwargs) -> ChatOpenAI:
        """
        获取 LLM 单例实例（用于缓存）
        
        Returns:
            ChatOpenAI 实例
        """
        if cls._llm_instance is None:
            cls._llm_instance = cls.create_llm(**kwargs)
        return cls._llm_instance
    
    @classmethod
    def get_embedding(cls, **kwargs) -> OpenAIEmbeddings:
        """
        获取 Embedding 单例实例（用于缓存）
        
        Returns:
            OpenAIEmbeddings 实例
        """
        if cls._embedding_instance is None:
            cls._embedding_instance = cls.create_embedding(**kwargs)
        return cls._embedding_instance
    
    @classmethod
    def reset(cls) -> None:
        """重置单例实例（用于配置变更后重新创建）"""
        cls._llm_instance = None
        cls._embedding_instance = None


def get_llm(**kwargs) -> ChatOpenAI:
    """便捷函数：获取 LLM 实例"""
    return LLMFactory.get_llm(**kwargs)


def get_embedding(**kwargs) -> OpenAIEmbeddings:
    """便捷函数：获取 Embedding 实例"""
    return LLMFactory.get_embedding(**kwargs)


def create_llm_for_excel() -> ChatOpenAI:
    """
    创建用于 Excel QA 的 LLM 实例
    温度设置为 0 以确保确定性输出
    """
    return LLMFactory.create_llm(temperature=0)


def create_llm_for_chat() -> ChatOpenAI:
    """
    创建用于文档聊天的 LLM 实例
    使用配置中的默认温度
    """
    return LLMFactory.create_llm()

