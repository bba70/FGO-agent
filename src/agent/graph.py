from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import Annotated, Sequence, Any, Literal, Dict

from .state import AgentState, InputState
from .nodes import (
    query_classify_node,
    knowledge_base_node,
    web_search_node,
    end_node,
)



def route_after_classify(state: AgentState) -> str:
    """
    根据查询分类结果进行路由决策
    
    Args:
        state: 当前状态，包含 query_classification 字段
        
    Returns:
        str: 下一个节点的名称
    """
    classification  = state.get("query_classification")

    if classification == "knowledge_base":
        return "knowledge_base_node"
    elif classification == "web_search":
        return "web_search_node"
    elif classification == "end":
        return "end_node"
    else:
        return "end_node"
    
def create_game_character_graph():
    """
    创建并编译游戏角色智能助手的工作流图
    
    Returns:
        CompiledGraph: 编译后的可执行图
    """
    
    # 创建状态图，指定状态类型和输入接口
    workflow = StateGraph(
        state_schema=AgentState,
        input_schema=InputState
    )
    
    # === 添加节点 ===
    workflow.add_node("query_classify", query_classify_node)
    workflow.add_node("knowledge_base", knowledge_base_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("end", end_node)
    
    # === 添加边 ===
    
    # 入口边：从 START 到查询分类节点
    workflow.add_edge(START, "query_classify")
    
    # 条件边：根据分类结果路由到不同节点
    workflow.add_conditional_edges(
        source="query_classify",
        path=route_after_classify,
        path_map={
            "knowledge_base": "knowledge_base",
            "web_search": "web_search", 
            "end": "end"
        }
    )
    
    # 终止边：所有处理节点都指向 END
    workflow.add_edge("knowledge_base", END)
    workflow.add_edge("web_search", END)
    workflow.add_edge("end", END)
    
    # 编译图并返回
    return workflow.compile()

# === 导出编译好的图 ===
game_character_graph = create_game_character_graph()

# 可选：添加图的可视化和调试功能
def visualize_graph():
    """
    可视化图结构（需要安装 graphviz）
    """
    try:
        return game_character_graph.get_graph().draw_mermaid()
    except Exception as e:
        print(f"可视化失败: {e}")
        return None

def get_graph_info():
    """
    获取图的基本信息
    """
    graph_info = {
        "nodes": ["query_classify", "knowledge_base", "web_search", "end"],
        "entry_point": "query_classify",
        "routing_logic": {
            "query_classify": "根据 query_classification 字段路由",
            "knowledge_base": "处理知识库查询后结束",
            "web_search": "处理网络搜索后结束", 
            "end": "直接结束对话"
        },
        "state_flow": [
            "START -> query_classify",
            "query_classify -> [knowledge_base|web_search|end]",
            "[knowledge_base|web_search|end] -> END"
        ]
    }
    return graph_info

