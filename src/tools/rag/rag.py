"""
RAG检索和重排序模块

提供向量检索和文档重排序功能，供 LangGraph 知识库节点调用
使用 CrossEncoder 进行专业的文档重排序
"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
from pathlib import Path

from sentence_transformers import CrossEncoder
from database.kb.vectordb import get_vectordb

logger = logging.getLogger(__name__)

# 设置模型缓存目录（在当前模块所在目录下）
MODEL_CACHE_DIR = Path(__file__).parent / "models"
MODEL_CACHE_DIR.mkdir(exist_ok=True)


class RAGRetriever:
    """RAG检索器，负责从向量数据库检索相关文档并进行重排序"""
    
    def __init__(
        self, 
        collection_name: str = "fgo_servants", 
        top_k: int = 5,
        rerank_model_name: str = "BAAI/bge-reranker-base"
    ):
        """
        初始化RAG检索器
        
        Args:
            collection_name: ChromaDB集合名称
            top_k: 返回的文档数量
            rerank_model_name: CrossEncoder 模型名称
                推荐模型：
                - "BAAI/bge-reranker-base" (中文，推荐)
                - "BAAI/bge-reranker-large" (中文，效果更好但速度慢)
                - "cross-encoder/ms-marco-MiniLM-L-6-v2" (英文)
        """
        self.collection_name = collection_name
        self.top_k = top_k
        self.vectordb = get_vectordb()
        
        # 加载 CrossEncoder 模型
        logger.info(f"正在加载 CrossEncoder 模型: {rerank_model_name}")
        logger.info(f"模型缓存目录: {MODEL_CACHE_DIR}")
        try:
            self.cross_encoder = CrossEncoder(
                rerank_model_name,
                cache_folder=str(MODEL_CACHE_DIR)
            )
            logger.info("CrossEncoder 模型加载成功")
        except Exception as e:
            logger.error(f"CrossEncoder 模型加载失败: {str(e)}")
            self.cross_encoder = None
        
    def retrieve(
        self, 
        query: str, 
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        从向量数据库检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的文档数量（可选，默认使用实例化时的值）
            filter_metadata: 元数据过滤条件（可选）
                例如: {"servant_name": "玛修·基列莱特"}
        
        Returns:
            检索到的文档列表，每个文档包含:
            - content: 文档内容
            - metadata: 元数据（servant_name, chunk_type等）
            - id: 文档ID
            - score: 相似度分数（0-1，越高越相关）
        """
        if not query or not query.strip():
            logger.warning("查询文本为空")
            return []
        
        k = top_k if top_k is not None else self.top_k
        
        try:
            # 获取集合
            collection = self.vectordb.get_collection(self.collection_name)
            
            # 执行检索
            results = collection.query(
                query_texts=[query],
                n_results=k,
                where=filter_metadata if filter_metadata else None
            )
            
            # 格式化结果
            documents = []
            if results and results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    # ChromaDB 返回的 distance 是 L2 距离，需要转换为相似度分数
                    # 距离越小，相似度越高
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    score = 1.0 / (1.0 + distance)  # 转换为 0-1 之间的相似度分数
                    
                    doc = {
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'id': results['ids'][0][i] if results['ids'] else None,
                        'score': score
                    }
                    documents.append(doc)
            
            logger.info(f"检索到 {len(documents)} 个相关文档")
            return documents
            
        except Exception as e:
            logger.error(f"检索失败: {str(e)}", exc_info=True)
            return []
    
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]],
        method: str = "crossencoder"
    ) -> List[Dict[str, Any]]:
        """
        对检索到的文档进行重排序
        
        Args:
            query: 原始查询文本
            documents: 待重排序的文档列表
            method: 重排序方法
                - "crossencoder": 使用 CrossEncoder 模型（推荐）
                - "keyword": 基于关键词匹配的重排序（fallback）
                - "score": 仅使用原始相似度分数（不重排）
        
        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []
        
        if method == "crossencoder":
            return self._rerank_by_crossencoder(query, documents)
        elif method == "keyword":
            return self._rerank_by_keyword(query, documents)
        elif method == "score":
            # 已经按照相似度分数排序，直接返回
            return documents
        else:
            logger.warning(f"未知的重排序方法: {method}，使用默认排序")
            return documents
    
    def _rerank_by_crossencoder(
        self, 
        query: str, 
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        使用 CrossEncoder 模型进行重排序
        
        CrossEncoder 是专门为重排序任务设计的模型，它会：
        1. 将查询和文档作为一对输入
        2. 直接输出相关性分数
        3. 比 LLM 更快、更准确
        
        综合分数 = 原始相似度 * 0.3 + CrossEncoder分数 * 0.7
        """
        if not self.cross_encoder:
            logger.warning("CrossEncoder 模型未加载，fallback 到关键词重排序")
            return self._rerank_by_keyword(query, documents)
        
        try:
            # 构建 query-document pairs
            pairs = [[query, doc['content']] for doc in documents]
            
            # 使用 CrossEncoder 预测相关性分数
            logger.info("正在使用 CrossEncoder 进行重排序...")
            ce_scores = self.cross_encoder.predict(pairs)
            
            # 将 CrossEncoder 分数归一化到 0-1
            # CrossEncoder 通常输出 logits，需要归一化
            import numpy as np
            ce_scores_normalized = 1 / (1 + np.exp(-np.array(ce_scores)))  # Sigmoid
            
            # 综合分数并重排序
            for i, doc in enumerate(documents):
                original_score = doc['score']
                ce_score = float(ce_scores_normalized[i])
                
                # 综合分数 = 原始相似度 * 0.3 + CrossEncoder分数 * 0.7
                doc['ce_score'] = ce_score
                doc['rerank_score'] = original_score * 0.3 + ce_score * 0.7
                
                logger.debug(
                    f"文档 {doc['id']}: 原始分数={original_score:.3f}, "
                    f"CE分数={ce_score:.3f}, "
                    f"重排分数={doc['rerank_score']:.3f}"
                )
            
            # 按照重排序分数降序排序
            reranked_docs = sorted(
                documents, 
                key=lambda x: x.get('rerank_score', x.get('score', 0)), 
                reverse=True
            )
            
            logger.info(f"CrossEncoder 重排序完成，共 {len(reranked_docs)} 个文档")
            return reranked_docs
            
        except Exception as e:
            logger.error(f"CrossEncoder 重排序失败，fallback 到关键词重排: {str(e)}", exc_info=True)
            # 如果 CrossEncoder 重排序失败，fallback 到关键词重排
            return self._rerank_by_keyword(query, documents)
    
    def _rerank_by_keyword(
        self, 
        query: str, 
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        基于关键词匹配的重排序（fallback 方法）
        
        算法：
        1. 提取查询关键词（简单分词）
        2. 计算每个文档的关键词命中率
        3. 综合原始向量相似度和关键词匹配度
        4. 重新排序
        
        综合分数 = 原始相似度 * 0.7 + 关键词匹配度 * 0.3
        """
        # 提取查询关键词（简单分词，FGO相关的中文可以直接按字符分）
        # 过滤掉单字和常见虚词
        query_lower = query.lower()
        query_terms = set([
            term for term in query_lower.split() 
            if len(term) > 1  # 过滤单字
        ])
        
        # 如果分词结果为空，使用原始查询
        if not query_terms:
            query_terms = set([query_lower])
        
        # 计算每个文档的关键词匹配分数
        for doc in documents:
            content = doc['content'].lower()
            
            # 计算关键词命中数
            keyword_hits = sum(1 for term in query_terms if term in content)
            
            # 关键词匹配度：命中数 / 总关键词数
            keyword_score = keyword_hits / len(query_terms) if query_terms else 0.0
            
            # 综合分数 = 原始相似度 * 0.7 + 关键词匹配度 * 0.3
            original_score = doc['score']
            doc['rerank_score'] = original_score * 0.7 + keyword_score * 0.3
            
            logger.debug(
                f"文档 {doc['id']}: 原始分数={original_score:.3f}, "
                f"关键词分数={keyword_score:.3f}, "
                f"重排分数={doc['rerank_score']:.3f}"
            )
        
        # 按照重排序分数降序排序
        reranked_docs = sorted(
            documents, 
            key=lambda x: x.get('rerank_score', x.get('score', 0)), 
            reverse=True
        )
        
        logger.info(f"关键词重排序完成，共 {len(reranked_docs)} 个文档")
        return reranked_docs
    
    def retrieve_and_rerank(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank_method: str = "crossencoder",
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        检索并重排序（一步到位的便捷方法）
        
        流程：
        1. 从向量数据库检索文档（检索数量为 top_k * 2）
        2. 使用指定方法重排序
        3. 返回排序后的前 top_k 个文档
        
        Args:
            query: 查询文本
            top_k: 最终返回的文档数量
            rerank_method: 重排序方法（"crossencoder", "keyword", "score"）
            filter_metadata: 元数据过滤条件
        
        Returns:
            重排序后的文档列表
        """
        # 第一步：检索
        # 检索时获取更多文档（2倍），然后重排序后取 top_k
        k = top_k if top_k is not None else self.top_k
        retrieve_k = min(k * 2, 20)  # 最多检索20个文档
        
        logger.info(f"开始检索，查询: '{query}', 检索数量: {retrieve_k}")
        
        documents = self.retrieve(
            query=query,
            top_k=retrieve_k,
            filter_metadata=filter_metadata
        )
        
        if not documents:
            logger.warning("未检索到任何文档")
            return []
        
        # 第二步：重排序
        logger.info(f"开始重排序，方法: {rerank_method}")
        reranked_docs = self.rerank(
            query=query,
            documents=documents,
            method=rerank_method
        )
        
        # 第三步：返回 top_k
        final_docs = reranked_docs[:k]
        logger.info(f"最终返回 {len(final_docs)} 个文档")
        
        return final_docs


# --- 便捷函数（供 LangGraph 节点调用）---

def retrieve_documents(
    query: str,
    top_k: int = 5,
    rerank: bool = True,
    rerank_method: str = "crossencoder",
    filter_metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：检索文档（供 nodes.py 的知识库节点调用）
    
    Args:
        query: 查询文本
        top_k: 返回的文档数量
        rerank: 是否进行重排序
        rerank_method: 重排序方法（"crossencoder", "keyword", "score"）
        filter_metadata: 元数据过滤条件
            例如: {"servant_name": "玛修·基列莱特"}
    
    Returns:
        检索到的文档列表，每个文档包含:
        - content: 文档内容
        - metadata: 元数据
        - id: 文档ID
        - score: 原始相似度分数
        - ce_score: CrossEncoder 评分（如果使用 CrossEncoder）
        - rerank_score: 重排序后的分数（如果启用了重排序）
    
    Example:
        >>> docs = retrieve_documents(
        ...     query="玛修的宝具是什么",
        ...     top_k=3,
        ...     rerank=True,
        ...     rerank_method="crossencoder"
        ... )
        >>> for doc in docs:
        ...     print(f"分数: {doc['rerank_score']:.3f}")
        ...     print(f"内容: {doc['content'][:100]}...")
    """
    retriever = RAGRetriever(top_k=top_k)
    
    if rerank:
        return retriever.retrieve_and_rerank(
            query=query,
            top_k=top_k,
            rerank_method=rerank_method,
            filter_metadata=filter_metadata
        )
    else:
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )


def calculate_retrieval_quality(documents: List[Dict[str, Any]]) -> float:
    """
    计算检索质量分数（供 RAG 评估节点使用）
    
    评估指标：
    1. 平均相似度分数
    2. 文档数量（越多说明知识库覆盖越好）
    3. 分数分布（top文档和其他文档的分数差异）
    
    Args:
        documents: 检索到的文档列表
    
    Returns:
        质量分数（0-1之间），越高越好
        - > 0.7: 高质量，直接使用
        - 0.5-0.7: 中等质量，可能需要改写查询
        - < 0.5: 低质量，建议改写或切换到Web搜索
    """
    if not documents:
        return 0.0
    
    # 提取分数（优先使用 rerank_score，否则使用 score）
    scores = [
        doc.get('rerank_score', doc.get('score', 0.0)) 
        for doc in documents
    ]
    
    # 计算平均分数
    avg_score = sum(scores) / len(scores)
    
    # 计算文档数量因子（有文档比没文档好）
    count_factor = min(len(documents) / 5.0, 1.0)  # 5个文档为满分
    
    # 计算分数分布因子（top文档分数应该明显高于其他）
    if len(scores) > 1:
        top_score = scores[0]
        others_avg = sum(scores[1:]) / len(scores[1:])
        distribution_factor = min((top_score - others_avg) * 2, 1.0)
    else:
        distribution_factor = 1.0
    
    # 综合质量分数
    quality_score = (
        avg_score * 0.6 +           # 平均分数权重 60%
        count_factor * 0.2 +         # 文档数量权重 20%
        distribution_factor * 0.2    # 分数分布权重 20%
    )
    
    logger.info(
        f"检索质量评估: 平均分数={avg_score:.3f}, "
        f"文档数量={len(documents)}, "
        f"质量分数={quality_score:.3f}"
    )
    
    return quality_score
