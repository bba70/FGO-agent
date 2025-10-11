from typing import Annotated, Sequence, Any, Literal, Dict
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState

# ============================================================================
# 节点定义（仅定义接口，不做具体实现）
# ============================================================================

def query_classify_node(state: AgentState) -> Dict[str, Any]:
    """
    查询分类节点，根据用户输入判断查询类型。
    
    Returns:
        更新 query_classification, original_query, rewritten_query（如果是重试）
    """
    pass


def knowledge_base_node(state: AgentState) -> Dict[str, Any]:
    """
    知识库 RAG 节点，从向量数据库检索相关文档。
    
    Returns:
        更新 retrieved_docs
    """
    pass


def rag_evaluation_node(state: AgentState) -> Dict[str, Any]:
    """
    RAG 评估节点，评估检索结果的质量。
    
    评估结果：
    - "pass": 检索结果良好，继续到汇总节点
    - "rewrite": 检索结果不佳且未超过重试次数，改写查询回到分类节点
    
    注意：如果重试次数已达上限，即使质量不佳也返回 "pass" 进入汇总节点
    
    Returns:
        更新 evaluation_result, retrieval_score, retry_count
    """
    pass


def web_search_node(state: AgentState) -> Dict[str, Any]:
    """
    网络搜索节点，处理需要实时信息的查询。
    
    Returns:
        更新 search_results
    """
    pass


def summarize_node(state: AgentState) -> Dict[str, Any]:
    """
    汇总节点，将 RAG 或 Web Search 的结果整合成最终答案。
    
    关键：清理所有中间状态，只保留最终的 messages
    
    Returns:
        更新 messages（添加 AI 回复），清理所有中间状态字段
    """
    pass


def end_node(state: AgentState) -> Dict[str, Any]:
    """
    结束节点，直接结束对话（例如闲聊、问候等）。
    
    Returns:
        更新 messages，清理中间状态
    """
    return {
        "messages": [AIMessage(content="如有其他问题，请随时询问！")]
    }
