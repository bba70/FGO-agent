from typing import Annotated, Sequence, Any, Literal, Dict
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState

def query_classify_node(state: AgentState) -> Dict[str, Any]:
    """
    查询分类节点，根据用户输入判断查询类型。
    """

def knowledge_base_node(state: AgentState) -> Dict[str, Any]:
    """
    知识库节点，根据用户输入查询知识库。
    """

def web_search_node(state: AgentState) -> Dict[str, Any]:
        """
        网络搜索节点：处理角色相关讨论查询
        """
    
def end_node(state: AgentState) -> Dict[str, Any]:
    """
    结束节点：直接结束对话
    """
    return {
        "messages": [AIMessage(content="如有其他问题，请随时询问！")]
    }