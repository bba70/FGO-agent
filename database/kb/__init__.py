"""
向量数据库模块

简化的接口，统一管理配置、连接、Embedding
"""

from .vectordb import (
    VectorDB,
    VectorDBConfig,
    LLMRouterEmbeddingFunction,
    get_vectordb,
    reset_vectordb
)

__all__ = [
    'VectorDB',
    'VectorDBConfig',
    'LLMRouterEmbeddingFunction',
    'get_vectordb',
    'reset_vectordb'
]

