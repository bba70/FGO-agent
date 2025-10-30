from typing import TypedDict, Annotated, Sequence, Any, Literal, Optional, List, Dict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

# --- 第一部分：定义图的公共入口 (API) ---

class InputState(TypedDict):
    """
    定义了 Agent 的外部输入接口。
    调用者需要提供消息列表，可选提供流式回调函数。
    """
    messages: Annotated[Sequence[AnyMessage], add_messages]
    stream_callback: Optional[Any]  # 🎯 流式输出回调函数（WebSocket 发送）


# --- 第二部分：定义图的内部完整状态 ---

class AgentState(InputState):
    """
    代表 Agent 内部流转的完整状态，继承自 InputState。
    
    Attributes:
        messages: 继承自 InputState，追踪完整的对话历史（最终状态）
        stream_callback: 继承自 InputState，流式输出回调函数（WebSocket 发送）
        
        # 以下为中间状态字段，仅在图遍历过程中使用，不会保留到最终状态
        query_classification: 查询分类结果（knowledge_base/web_search/end）
        retry_count: 重试次数（防止无限循环）
        original_query: 原始查询（用于改写时参考）
        rewritten_query: 改写后的查询
        
        # RAG 相关中间状态
        retrieved_docs: RAG 检索到的文档
        retrieval_score: 检索质量分数
        evaluation_result: 评估结果（pass/rewrite）
        evaluation_reason: LLM 评估的失败原因，用于指导查询改写
    """
    # 路由和控制字段
    query_classification: Optional[Literal["knowledge_base", "web_search", "end"]]
    retry_count: Optional[int]
    
    # 查询改写字段
    original_query: Optional[str]
    rewritten_query: Optional[str]
    
    # RAG 中间状态
    retrieved_docs: Optional[List[Dict[str, Any]]]
    retrieval_score: Optional[float]
    evaluation_result: Optional[Literal["pass", "rewrite"]]
    evaluation_reason: Optional[str]  # LLM 评估的失败原因，用于指导查询改写


# --- 第三部分：定义输出状态（清理后的状态）---

class OutputState(TypedDict):
    """
    定义图的最终输出状态，只包含必要的对话历史。
    中间状态字段会被清理，不会返回给调用者。
    """
    messages: Annotated[Sequence[AnyMessage], add_messages]
