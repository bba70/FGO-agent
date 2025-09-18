from typing import TypedDict, Annotated, Sequence, Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing import Optional

# --- 第一部分：定义图的公共入口 (API) ---

class InputState(TypedDict):
    """
    定义了 Agent 的外部输入接口。
    调用者只需要提供一个消息列表即可启动流程。
    """
    messages: Annotated[Sequence[AnyMessage], add_messages]


# --- 第二部分：定义图的内部完整状态 ---

class AgentState(InputState):
    """
    代表 Agent 内部流转的完整状态，继承自 InputState。
    
    Attributes:
        messages: 继承自 InputState，追踪完整的对话历史。
        query_classification: 存储查询分类节点的结果，用于条件路由。
        tool_output: 存储工具执行节点返回的原始数据，作为答案合成节点的上下文。
    """
    # 路由指令：存放分类节点的决策结果
    query_classification: Literal["knowledge_base", "web_search", "end"]
    # 工具参数
    tool_input: Optional[dict]
    # 工具调用结果
    tool_result = Optional[dict]
