"""
ChromaDB 向量数据库管理模块

统一管理配置、连接、Embedding 适配器
"""

import os
import asyncio
from typing import List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

from chromadb import PersistentClient
from chromadb.config import Settings
from chromadb.api.models.Collection import Collection

from llm.router import ModelRouter


# 配置

@dataclass
class VectorDBConfig:
    """向量数据库配置"""
    
    # ChromaDB 配置
    persist_directory: str = "data/vectorstore/chromaDB"
    collection_name: str = "fgo_servants"
    
    # Embedding 模型配置（使用 LLM 模型中台）
    llm_config_path: str = "llm/config.yaml"
    embedding_model_name: str = "fgo-emded-model"
    
    # 检索配置
    default_k: int = 5
    default_score_threshold: float = 0.0
    batch_size: int = 32
    
    @property
    def persist_path(self) -> Path:
        """返回 Path 对象"""
        return Path(self.persist_directory)


# Embedding

class LLMRouterEmbeddingFunction:
    """
    将 ModelRouter 的 embed 方法适配为 ChromaDB 的 EmbeddingFunction
    
    实现 ChromaDB 的 EmbeddingFunction 接口：
    - name() - 返回唯一标识
    - __call__() - 批量嵌入文档
    - embed_query() - 嵌入查询文本
    """
    
    def __init__(self, model_router: ModelRouter, model_name: str):
        self.model_router = model_router
        self.model_name = model_name
    
    def name(self) -> str:
        """返回 Embedding 函数的名称（ChromaDB 必需）"""
        return f"llm_router_{self.model_name}"
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """内部方法：获取文本的嵌入向量（处理异步调用）"""
        texts = [str(text) for text in texts]
        
        # 在同步上下文中运行异步方法
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 调用 ModelRouter.embed
        try:
            result = loop.run_until_complete(
                self.model_router.embed(texts=texts, model=self.model_name)
            )
            
            if result is None:
                raise RuntimeError("Embedding API 返回 None")
            
            embeddings = [item["embedding"] for item in result.get("data", [])]
            
            if not embeddings:
                raise RuntimeError(f"Embedding API 未返回有效数据: {result}")
            
            return embeddings
            
        except Exception as e:
            print(f"❌ Embedding 生成失败: {e}")
            raise RuntimeError(f"无法生成 embedding: {e}") from e
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """批量嵌入文档（插入数据时调用）"""
        return self._get_embeddings(input)
    
    def embed_query(self, input: Any) -> List[List[float]]:
        """嵌入查询文本（查询时调用）"""
        if isinstance(input, list):
            texts = [str(item) for item in input]
        else:
            texts = [str(input)]
        return self._get_embeddings(texts)


# 向量数据库管理类

class VectorDB:
    """
    ChromaDB 向量数据库管理类
    
    统一管理配置、连接、Embedding 函数
    使用单例模式，全局只有一个实例
    """
    
    def __init__(
        self,
        persist_directory: str = "data/vectorstore/chromaDB",
        collection_name: str = "fgo_servants",
        llm_config_path: str = "llm/config.yaml",
        embedding_model_name: str = "fgo-emded-model"
    ):
        """
        初始化向量数据库
        
        Args:
            persist_directory: 数据存储路径
            collection_name: 默认集合名称
            llm_config_path: LLM 配置文件路径
            embedding_model_name: Embedding 逻辑模型名
        """
        self.config = VectorDBConfig(
            persist_directory=persist_directory,
            collection_name=collection_name,
            llm_config_path=llm_config_path,
            embedding_model_name=embedding_model_name
        )
        
        # 确保目录存在
        self.config.persist_path.mkdir(parents=True, exist_ok=True)
        
        # 延迟初始化
        self._client: Optional[PersistentClient] = None
        self._embedding_function: Optional[LLMRouterEmbeddingFunction] = None
        self._model_router: Optional[ModelRouter] = None
    
    @property
    def client(self) -> PersistentClient:
        """获取 ChromaDB 客户端（延迟初始化）"""
        if self._client is None:
            print(f"📦 初始化 ChromaDB")
            print(f"   路径: {self.config.persist_directory}")
            
            self._client = PersistentClient(
                path=str(self.config.persist_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            print(f"✅ ChromaDB 初始化完成")
        
        return self._client
    
    @property
    def embedding_function(self) -> LLMRouterEmbeddingFunction:
        """获取 Embedding 函数（延迟初始化）"""
        if self._embedding_function is None:
            print(f"📦 初始化 Embedding 函数")
            print(f"   模型: {self.config.embedding_model_name}")
            
            # 初始化 ModelRouter
            if self._model_router is None:
                self._model_router = ModelRouter(
                    config_path=self.config.llm_config_path
                )
            
            # 创建 Embedding 适配器
            self._embedding_function = LLMRouterEmbeddingFunction(
                model_router=self._model_router,
                model_name=self.config.embedding_model_name
            )
            
            print(f"✅ Embedding 函数初始化完成")
        
        return self._embedding_function
    
    def get_or_create_collection(
        self,
        name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Collection:
        """
        获取或创建集合
        
        Args:
            name: 集合名称（默认使用配置中的名称）
            metadata: 集合元数据
        
        Returns:
            Collection 对象
        """
        name = name or self.config.collection_name
        
        print(f"📂 获取或创建集合: {name}")
        
        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_function,
            metadata=metadata or {"description": "FGO 从者知识库"}
        )
        
        print(f"✅ 集合就绪（文档数: {collection.count()}）")
        
        return collection
    
    def get_collection(self, name: Optional[str] = None) -> Collection:
        """获取已存在的集合"""
        name = name or self.config.collection_name
        
        try:
            return self.client.get_collection(
                name=name,
                embedding_function=self.embedding_function
            )
        except Exception as e:
            raise ValueError(f"集合 '{name}' 不存在: {e}")
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        collections = self.client.list_collections()
        return [c.name for c in collections]
    
    def delete_collection(self, name: str):
        """删除集合"""
        self.client.delete_collection(name=name)
        print(f"🗑️  已删除集合: {name}")
    
    def reset(self):
        """重置数据库（删除所有数据）"""
        if self._client:
            self._client.reset()
            print("🔄 ChromaDB 已重置")
    
    def close(self):
        """关闭连接"""
        self._client = None
        self._embedding_function = None
        self._model_router = None
        print("🔒 ChromaDB 连接已关闭")


# 全局实例（单例模式）
_vectordb_instance: Optional[VectorDB] = None

def get_vectordb(
    persist_directory: str = None,
    collection_name: str = None,
    llm_config_path: str = None,
    embedding_model_name: str = None
) -> VectorDB:
    """
    获取全局向量数据库实例（单例模式）
    
    支持环境变量配置：
    - VECTORDB_PATH
    - VECTORDB_COLLECTION
    - LLM_CONFIG_PATH
    - EMBEDDING_MODEL
    
    Args:
        persist_directory: 数据存储路径
        collection_name: 默认集合名称
        llm_config_path: LLM 配置路径
        embedding_model_name: Embedding 模型名
    
    Returns:
        VectorDB 实例
    """
    global _vectordb_instance
    
    if _vectordb_instance is None:
        _vectordb_instance = VectorDB(
            persist_directory=persist_directory or os.getenv("VECTORDB_PATH", "data/vectorstore"),
            collection_name=collection_name or os.getenv("VECTORDB_COLLECTION", "fgo_servants"),
            llm_config_path=llm_config_path or os.getenv("LLM_CONFIG_PATH", "llm/config.yaml"),
            embedding_model_name=embedding_model_name or os.getenv("EMBEDDING_MODEL", "fgo-emded-model")
        )
    
    return _vectordb_instance


def reset_vectordb():
    """重置全局实例"""
    global _vectordb_instance
    if _vectordb_instance:
        _vectordb_instance.close()
    _vectordb_instance = None

