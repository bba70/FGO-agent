from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import Annotated, Sequence, Any, Literal, Dict

from .state import AgentState, InputState
from .nodes import (
    query_classify_node,
    knowledge_base_node,
    rag_evaluation_node,
    web_search_node,
    summarize_node,
    end_node,
)


# ============================================================================
# 路由函数
# ============================================================================

def route_after_classify(state: AgentState) -> str:
    """
    根据查询分类结果进行路由决策
    
    Args:
        state: 当前状态，包含 query_classification 字段
        
    Returns:
        str: 下一个节点的名称
    """
    classification = state.get("query_classification")

    if classification == "knowledge_base":
        return "knowledge_base"
    elif classification == "web_search":
        return "web_search"
    elif classification == "end":
        return "end"
    else:
        return "end"


def route_after_evaluation(state: AgentState) -> str:
    """
    根据 RAG 评估结果进行路由决策
    
    Args:
        state: 当前状态，包含 evaluation_result 字段
        
    Returns:
        str: 下一个节点的名称
        - "summarize": 评估通过或重试次数已达上限，进入汇总节点
        - "query_classify": 需要改写查询，回到分类节点重新处理
    """
    evaluation_result = state.get("evaluation_result")
    
    if evaluation_result == "rewrite":
        return "query_classify"
    else:
        # 默认或 "pass" 都进入汇总节点
        return "summarize"


# 创建图

def create_game_character_graph():
    """
    创建并编译游戏角色智能助手的工作流图
    
    工作流程：
    1. 查询分类 -> 知识库/网络搜索/结束
    2. 知识库 -> RAG评估
    3. RAG评估 -> 汇总（通过）/ 查询分类（改写）/ 网络搜索（降级）
    4. 网络搜索 -> 汇总
    5. 汇总 -> 结束
    6. 结束 -> 结束
    
    Returns:
        CompiledGraph: 编译后的可执行图
    """
    
    # 创建状态图，指定状态类型和输入接口
    workflow = StateGraph(
        state_schema=AgentState,
        input_schema=InputState
    )
    
    workflow.add_node("query_classify", query_classify_node)
    workflow.add_node("knowledge_base", knowledge_base_node)
    workflow.add_node("rag_evaluation", rag_evaluation_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("end", end_node)
    
    
    # 1. 入口边：从 START 到查询分类节点
    workflow.add_edge(START, "query_classify")
    
    # 2. 条件边：根据分类结果路由
    workflow.add_conditional_edges(
        source="query_classify",
        path=route_after_classify,
        path_map={
            "knowledge_base": "knowledge_base",
            "web_search": "web_search", 
            "end": "end"
        }
    )
    
    # 3. 知识库节点 -> RAG评估节点（固定边）
    workflow.add_edge("knowledge_base", "rag_evaluation")
    
    # 4. 条件边：根据评估结果路由
    workflow.add_conditional_edges(
        source="rag_evaluation",
        path=route_after_evaluation,
        path_map={
            "summarize": "summarize",      # 评估通过，进入汇总
            "query_classify": "query_classify",  # 需要改写，回到分类
            "web_search": "web_search"     # 降级到网络搜索
        }
    )
    
    
    # 6. 汇总节点 -> END（固定边）
    workflow.add_edge("summarize", END)
    
    # 7. 结束节点 -> END（固定边）
    workflow.add_edge("end", END)
    
    # 编译图并返回
    return workflow.compile()


game_character_graph = create_game_character_graph()



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
        "nodes": [
            "query_classify",      # 查询分类节点
            "knowledge_base",      # RAG 检索节点
            "rag_evaluation",      # RAG 评估节点（新增）
            "web_search",          # 网络搜索节点
            "summarize",           # 汇总节点（新增）
            "end"                  # 结束节点
        ],
        "entry_point": "query_classify",
        "routing_logic": {
            "query_classify": "根据 query_classification 路由 -> knowledge_base/web_search/end",
            "knowledge_base": "固定路由 -> rag_evaluation",
            "rag_evaluation": "根据 evaluation_result 路由 -> summarize/query_classify/web_search",
            "web_search": "固定路由 -> summarize",
            "summarize": "固定路由 -> END（清理中间状态）",
            "end": "固定路由 -> END"
        },
        "state_flow": [
            "START -> query_classify",
            "query_classify -> [knowledge_base|web_search|end]",
            "knowledge_base -> rag_evaluation",
            "rag_evaluation -> [summarize|query_classify(重试)|web_search(降级)]",
            "web_search -> summarize",
            "summarize -> END",
            "end -> END"
        ],
        "key_features": [
            "支持 RAG 质量评估",
            "支持查询改写重试（最多2次）",
            "支持降级到网络搜索",
            "自动清理中间状态，只保留 query 和 answer"
        ]
    }
    return graph_info
