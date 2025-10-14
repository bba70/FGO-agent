from typing import Annotated, Sequence, Any, Literal, Dict
from langchain_core.messages import HumanMessage, AIMessage
from pathlib import Path
import logging
import json
import asyncio
import sys
import os

from .state import AgentState
from src.tools.rag.rag import retrieve_documents, calculate_retrieval_quality
from src.tools.rag.entity_linking import link_entities
from llm.router import ModelRouter

# FastMCP 客户端相关导入
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# 初始化 ModelRouter（单例模式）
_router = None

def get_router() -> ModelRouter:
    """获取 ModelRouter 单例"""
    global _router
    if _router is None:
        # config.yaml 在 FGO-agent/llm/config.yaml
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "llm" / "config.yaml"
        _router = ModelRouter(str(config_path))
    return _router

# ============================================================================
# 节点定义（仅定义接口，不做具体实现）
# ============================================================================

async def query_classify_node(state: AgentState) -> Dict[str, Any]:
    """
    查询分类节点，根据用户输入判断查询类型。
    
    功能：
    1. 实体链接：将别名替换为标准全名（规则）
    2. 上下文指代消解：将代词替换为具体实体（LLM）
    3. 查询优化：根据失败原因改写查询（LLM）
    4. 查询分类：判断查询类型（knowledge_base/web_search/end）
    
    Returns:
        更新 query_classification, original_query, rewritten_query
    """
    logger.info("=== 进入查询分类节点 ===")
    
    # 1. 提取用户查询
    messages = state.get("messages", [])
    user_query = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    if not user_query:
        logger.warning("未找到用户查询，默认返回 end")
        return {
            "query_classification": "end",
            "original_query": "",
        }
    
    logger.info(f"用户原始查询: '{user_query}'")
    
    # 2. 查询改写流程
    current_query = user_query
    
    # 获取上一次评估的失败信息
    retry_count = state.get("retry_count", 0) or 0
    evaluation_reason = state.get("evaluation_reason", "")
    retrieval_score = state.get("retrieval_score", 0.0)
    
    if retry_count > 0:
        logger.info(f"🔁 检测到重试（第 {retry_count} 次）")
        logger.info(f"📊 上次检索质量分数: {retrieval_score:.3f}")
        logger.info(f"📝 失败原因: {evaluation_reason}")
    
    # ===== 步骤2.1: 实体链接（规则映射） =====
    linked_query = link_entities(current_query)
    if linked_query != current_query:
        logger.info(f"🔗 实体链接: '{current_query}' → '{linked_query}'")
        current_query = linked_query
    
    # ===== 步骤2.2: 上下文指代消解 + 查询优化（LLM） =====
    # 判断是否需要调用 LLM 改写
    need_rewrite = False
    rewrite_reason = []
    
    # 条件1: 有重试（说明上次检索失败）
    if retry_count > 0:
        need_rewrite = True
        rewrite_reason.append("检索失败重试")
    
    # 条件2: 查询中包含指代词
    pronouns = ["她", "他", "它", "这个", "那个", "这", "那", "前者", "后者"]
    if any(pronoun in current_query for pronoun in pronouns):
        need_rewrite = True
        rewrite_reason.append("包含指代词")
    
    if need_rewrite:
        logger.info(f"✍️ 需要 LLM 改写查询，原因: {', '.join(rewrite_reason)}")
        
        # 构建改写 Prompt（直接写在节点中）
        rewrite_system_prompt = """你是一个专业的查询改写专家，你的任务是优化用户的查询，使其更适合在 FGO 从者知识库中检索。

**改写规则**：
1. **指代消解**：将代词（她/他/这个/那个等）替换为具体的从者名称
2. **查询优化**：使查询更清晰、具体，便于检索
3. **保留意图**：不改变用户的原始意图
4. **保持简洁**：不添加多余信息

**重要**：
- 只返回改写后的查询，不要任何解释
- 如果无法改写或不需要改写，返回原查询
- 确保改写后的查询是完整的、可独立理解的

示例1:
历史: 用户问"玛修的宝具是什么"，AI回答"..."
当前查询: "她的技能呢"
改写: "玛修的技能是什么"

示例2:
历史: 用户问"阿尔托莉雅厉害吗"
当前查询: "她的宝具效果"
改写: "阿尔托莉雅的宝具效果"""

        # 构建历史对话上下文（最近3轮）
        history_context = []
        for msg in messages[-6:]:  # 最近3轮（3个用户 + 3个AI）
            if isinstance(msg, HumanMessage):
                history_context.append(f"用户: {msg.content}")
            elif isinstance(msg, AIMessage):
                # 截取 AI 回复的前100字（避免太长）
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                history_context.append(f"AI: {content}")
        
        history_text = "\n".join(history_context) if history_context else "无历史对话"
        
        # 构建改写请求
        rewrite_user_prompt = f"""**历史对话**:
{history_text}

**当前查询**: {current_query}"""
        
        # 如果有失败原因，添加到 prompt
        if evaluation_reason:
            rewrite_user_prompt += f"\n\n**上次检索失败原因**: {evaluation_reason}"
            rewrite_user_prompt += "\n\n请根据失败原因优化查询，使其更容易检索到正确结果。"
        
        rewrite_messages = [
            {"role": "system", "content": rewrite_system_prompt},
            {"role": "user", "content": rewrite_user_prompt}
        ]
        
        try:
            router = get_router()
            logger.info("调用 LLM 进行查询改写")
            
            result, instance_name, physical_model_name, failover_events = await router.chat(
                messages=rewrite_messages,
                model="fgo-chat-model",
                stream=False
            )
            
            rewritten = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if rewritten and rewritten != current_query:
                logger.info(f"✨ LLM 改写: '{current_query}' → '{rewritten}'")
                current_query = rewritten
            else:
                logger.info("ℹ️ LLM 未进行有效改写，保持原查询")
        
        except Exception as e:
            logger.warning(f"⚠️ LLM 改写失败: {e}，使用原查询")
    
    # 最终改写结果
    rewritten_query = current_query
    if rewritten_query != user_query:
        logger.info(f"📌 最终改写结果: '{user_query}' → '{rewritten_query}'")
    
    # 3. 查询分类
    router = get_router()
    
    # 构造分类 prompt
    system_prompt = """你是一个查询分类助手，负责判断用户查询应该使用哪种方式处理。

**知识库查询（knowledge_base）**：
- FGO 从者的基础资料（职阶、星级、属性、CV等）
- FGO 从者的技能信息（技能名称、效果、冷却时间等）
- FGO 从者的宝具信息（宝具名称、类型、效果等）
- FGO 从者的角色资料和背景故事
- FGO 从者的素材需求（灵基再临、技能强化所需素材）

**网络搜索（web_search）**：
- 实时信息查询（活动时间、卡池信息、版本更新等）
- 攻略和玩法建议（队伍配置、关卡攻略等）
- 社区讨论和玩家心得

**闲聊结束（end）**：
- 问候、闲聊
- 非 FGO 相关问题

请根据用户查询，判断应该使用哪种方式处理。只需要返回 JSON 格式：
{"classification": "knowledge_base" | "web_search" | "end", "reason": "分类理由"}"""

    user_prompt = f"用户查询：{user_query}"
    
    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        logger.info("调用 LLM 进行查询分类")
        
        # 调用 LLM（非流式）
        result, instance_name, physical_model_name, failover_events = await router.chat(
            messages=llm_messages,
            model="fgo-chat-model",
            stream=False
        )
        
        # 解析 LLM 响应
        llm_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        logger.info(f"LLM 分类响应: {llm_response}")
        
        # 尝试解析 JSON
        try:
            # 提取 JSON（可能被 markdown 包裹）
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()
            
            parsed = json.loads(json_str)
            classification = parsed.get("classification", "knowledge_base")
            reason = parsed.get("reason", "")
            
            logger.info(f"分类结果: {classification}, 理由: {reason}")
            
            # 首次分类时 retry_count = 0，重试时保持不变
            result = {
                "query_classification": classification,
                "original_query": user_query,
                "rewritten_query": rewritten_query,
            }
            if retry_count == 0:
                result["retry_count"] = 0
            
            return result
            
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败，使用默认分类 knowledge_base")
            result = {
                "query_classification": "knowledge_base",
                "original_query": user_query,
                "rewritten_query": rewritten_query,
            }
            if retry_count == 0:
                result["retry_count"] = 0
            return result
    
    except Exception as e:
        logger.error(f"查询分类失败: {str(e)}", exc_info=True)
        # 默认使用知识库
        result = {
            "query_classification": "knowledge_base",
            "original_query": user_query,
            "rewritten_query": rewritten_query,
        }
        if retry_count == 0:
            result["retry_count"] = 0
        return result


def knowledge_base_node(state: AgentState) -> Dict[str, Any]:
    """
    知识库 RAG 节点，从向量数据库检索相关文档。
    
    工作流程：
    1. 确定查询文本（优先使用改写后的查询）
    2. 调用 RAG 检索器进行向量检索和重排序
    3. 将检索结果存入 state
    
    Returns:
        更新 retrieved_docs
    """
    logger.info("=== 进入知识库检索节点 ===")
    
    # 1. 确定查询文本
    # 优先级：rewritten_query > original_query > 从 messages 提取
    query = None
    
    if state.get("rewritten_query"):
        query = state["rewritten_query"]
        logger.info(f"使用改写后的查询: {query}")
    elif state.get("original_query"):
        query = state["original_query"]
        logger.info(f"使用原始查询: {query}")
    else:
        # 从 messages 中提取最后一条用户消息
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                query = msg.content
                logger.info(f"从消息历史提取查询: {query}")
                break
    
    # 如果没有找到查询文本，返回空结果
    if not query:
        logger.warning("未找到查询文本，返回空结果")
        return {
            "retrieved_docs": [],
            "retrieval_score": 0.0
        }
    
    # 2. 执行 RAG 检索（包含向量检索 + CrossEncoder 重排序）
    try:
        logger.info(f"开始检索文档，查询: '{query}'")
        documents = retrieve_documents(
            query=query,
            top_k=5,  # 返回 top 5 文档
            rerank=True,  # 启用重排序
            rerank_method="crossencoder"  # 使用 CrossEncoder 重排序
        )
        
        logger.info(f"检索完成，共找到 {len(documents)} 个相关文档")
        
        # 记录检索结果摘要
        if documents:
            for i, doc in enumerate(documents[:3], 1):  # 只打印前3个
                logger.info(
                    f"  文档{i}: {doc['metadata'].get('servant_name', 'N/A')} - "
                    f"{doc['metadata'].get('type', 'N/A')} "
                    f"(分数: {doc.get('rerank_score', doc.get('score', 0)):.3f})"
                )
        
        return {
            "retrieved_docs": documents
        }
        
    except Exception as e:
        logger.error(f"检索失败: {str(e)}", exc_info=True)
        # 检索失败时返回空结果
        return {
            "retrieved_docs": [],
            "retrieval_score": 0.0
        }


async def rag_evaluation_node(state: AgentState) -> Dict[str, Any]:
    """
    RAG 评估节点，评估检索结果的质量。
    
    评估结果：
    - "pass": 检索结果良好，进入 LLM 生成节点
    - "rewrite": 检索结果不佳且未超过重试次数，改写查询回到分类节点
    
    注意：如果重试次数已达上限，即使质量不佳也返回 "pass"
    
    Returns:
        更新 evaluation_result, retrieval_score, retry_count
    """
    logger.info("=== 进入 RAG 评估节点 ===")
    
    # 最大重试次数（避免无限循环）
    MAX_RETRY = 2
    
    # 1. 获取检索结果和当前重试次数
    retrieved_docs = state.get("retrieved_docs", [])
    retry_count = state.get("retry_count", 0) or 0
    original_query = state.get("original_query", "")
    
    logger.info(f"检索到 {len(retrieved_docs)} 个文档，当前重试次数: {retry_count}")
    
    # 2. 如果没有检索到文档
    if not retrieved_docs:
        logger.warning("未检索到任何文档")
        
        # 判断是否可以重试
        if retry_count < MAX_RETRY:
            logger.info(f"尝试改写查询重试（{retry_count + 1}/{MAX_RETRY}）")
            return {
                "evaluation_result": "rewrite",
                "retrieval_score": 0.0,
                "retry_count": retry_count + 1,
                "evaluation_reason": "未检索到任何相关文档，建议补全从者全名或明确查询的数据类型（技能/宝具/资料/素材）"
            }
        else:
            logger.warning(f"已达最大重试次数 {MAX_RETRY}，强制通过")
            return {
                "evaluation_result": "pass",
                "retrieval_score": 0.0,
                "retry_count": retry_count
            }
    
    # 3. 计算检索质量分数
    quality_score = calculate_retrieval_quality(retrieved_docs)
    logger.info(f"检索质量分数: {quality_score:.3f}")
    
    # 4. 准备文档摘要给 LLM 评估
    doc_summaries = []
    for i, doc in enumerate(retrieved_docs[:3], 1):  # 只展示前3个文档
        servant_name = doc['metadata'].get('servant_name', 'N/A')
        doc_type = doc['metadata'].get('type', 'N/A')
        score = doc.get('rerank_score', doc.get('score', 0))
        content_preview = doc['content'][:100] + "..." if len(doc['content']) > 100 else doc['content']
        
        doc_summaries.append(
            f"文档{i}：{servant_name} - {doc_type}（分数: {score:.3f}）\n内容预览: {content_preview}"
        )
    
    doc_summary_text = "\n\n".join(doc_summaries)
    
    # 5. 调用 LLM 进行评估
    router = get_router()
    
    system_prompt = """你是一个检索质量评估助手，负责判断检索到的文档是否能够回答用户的查询。

**评估标准**：
1. 相关性：文档内容是否与查询直接相关
2. 完整性：文档是否包含足够的信息来回答查询
3. 准确性：文档来源是否正确（从者名称、数据类型等）

**评估结果**：
- "pass": 文档质量良好，可以用来生成答案
- "rewrite": 文档质量不佳，建议改写查询重新检索

请根据用户查询和检索到的文档，判断是否应该使用这些文档。只需要返回 JSON 格式：
{"result": "pass" | "rewrite", "reason": "评估理由"}"""

    user_prompt = f"""用户查询：{original_query}

检索质量分数：{quality_score:.3f}（0-1之间，越高越好）

检索到的文档（前3个）：
{doc_summary_text}

请评估这些文档是否足以回答用户的查询。"""

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        logger.info("调用 LLM 进行检索质量评估")
        
        # 调用 LLM（非流式）
        result, instance_name, physical_model_name, failover_events = await router.chat(
            messages=llm_messages,
            model="fgo-chat-model",
            stream=False
        )
        
        # 解析 LLM 响应
        llm_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        logger.info(f"LLM 评估响应: {llm_response}")
        
        # 尝试解析 JSON
        try:
            # 提取 JSON（可能被 markdown 包裹）
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()
            
            parsed = json.loads(json_str)
            llm_result = parsed.get("result", "pass")
            reason = parsed.get("reason", "")
            
            logger.info(f"LLM 评估结果: {llm_result}, 理由: {reason}")
            
            # 6. 根据 LLM 评估结果和重试次数决定
            if llm_result == "rewrite" and retry_count < MAX_RETRY:
                logger.info(f"LLM 建议改写查询，准备重试（{retry_count + 1}/{MAX_RETRY}）")
                return {
                    "evaluation_result": "rewrite",
                    "retrieval_score": quality_score,
                    "retry_count": retry_count + 1,
                    "evaluation_reason": reason  # 👈 携带 LLM 评估的失败原因
                }
            else:
                # LLM 建议 pass 或已达最大重试次数
                if llm_result == "rewrite" and retry_count >= MAX_RETRY:
                    logger.warning(f"LLM 建议改写，但已达最大重试次数 {MAX_RETRY}，强制通过")
                else:
                    logger.info("LLM 评估通过，进入生成阶段")
                
                return {
                    "evaluation_result": "pass",
                    "retrieval_score": quality_score,
                    "retry_count": retry_count
                }
            
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败，默认评估为 pass")
            return {
                "evaluation_result": "pass",
                "retrieval_score": quality_score,
                "retry_count": retry_count
            }
    
    except Exception as e:
        logger.error(f"LLM 评估失败: {str(e)}", exc_info=True)
        
        # LLM 评估失败，回退到基于质量分数的简单判断
        logger.info("回退到基于质量分数的简单判断")
        
        # 质量分数阈值：> 0.6 为合格
        if quality_score > 0.6:
            logger.info(f"质量分数 {quality_score:.3f} > 0.6，评估通过")
            return {
                "evaluation_result": "pass",
                "retrieval_score": quality_score,
                "retry_count": retry_count
            }
        elif retry_count < MAX_RETRY:
            logger.info(f"质量分数 {quality_score:.3f} <= 0.6，尝试改写（{retry_count + 1}/{MAX_RETRY}）")
            return {
                "evaluation_result": "rewrite",
                "retrieval_score": quality_score,
                "retry_count": retry_count + 1,
                "evaluation_reason": f"检索质量分数较低（{quality_score:.3f}），文档相关性不足，建议改写查询"
            }
        else:
            logger.warning(f"质量分数低但已达最大重试次数，强制通过")
            return {
                "evaluation_result": "pass",
                "retrieval_score": quality_score,
                "retry_count": retry_count
            }


async def llm_generate_node(state: AgentState) -> Dict[str, Any]:
    """
    LLM 生成节点，基于 RAG 检索的文档生成最终答案。
    
    工作流程：
    1. 获取用户查询和检索到的文档
    2. 构造 RAG prompt（文档作为上下文）
    3. 调用 LLM 生成答案
    4. 清理所有中间状态，只保留 messages
    
    Returns:
        更新 messages（添加 AI 回复），清理所有中间状态字段
    """
    logger.info("=== 进入 LLM 生成节点 ===")
    
    # 1. 获取用户查询和检索到的文档
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    retrieved_docs = state.get("retrieved_docs", [])
    
    if not user_query:
        logger.warning("未找到用户查询")
        return {
            "messages": [AIMessage(content="抱歉，我没有理解您的问题。")],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    if not retrieved_docs:
        logger.warning("未找到检索文档，生成兜底答案")
        return {
            "messages": [AIMessage(content=f"抱歉，我没有找到关于「{user_query}」的相关信息。请尝试换一种问法或提供更详细的信息。")],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    logger.info(f"用户查询: '{user_query}'")
    logger.info(f"基于 {len(retrieved_docs)} 个文档生成答案")
    
    # 2. 构造文档上下文
    doc_contexts = []
    for i, doc in enumerate(retrieved_docs, 1):
        servant_name = doc['metadata'].get('servant_name', 'N/A')
        doc_type = doc['metadata'].get('type', 'N/A')
        content = doc['content']
        
        doc_contexts.append(
            f"【参考资料 {i}】\n"
            f"来源：{servant_name} - {doc_type}\n"
            f"内容：\n{content}"
        )
    
    context_text = "\n\n".join(doc_contexts)
    
    # 3. 构造 RAG prompt
    system_prompt = """你是一位专业的 FGO（Fate/Grand Order）游戏助手，负责根据提供的参考资料回答用户的问题。

**回答要求**：
1. 基于提供的参考资料进行回答，确保信息准确
2. 如果参考资料中没有明确答案，请诚实说明
3. 组织语言清晰、有条理，便于理解
4. 可以适当补充游戏相关的背景知识
5. 使用友好、专业的语气

**回答格式**：
- 直接回答问题，不需要说"根据参考资料"之类的前缀
- 如果是列表信息（如技能、素材），用清晰的格式展示
- 可以用表情符号增强可读性（如 ⭐、🎯、💎 等）"""

    user_prompt = f"""用户问题：{user_query}

参考资料：
{context_text}

请基于以上参考资料回答用户的问题。"""

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 4. 调用 LLM 生成答案
    router = get_router()
    
    try:
        logger.info("调用 LLM 生成答案（流式）")
        
        # 调用 LLM（流式）
        stream_wrapper = await router.chat(
            messages=llm_messages,
            model="fgo-chat-model",
            stream=True  # 启用流式输出
        )
        
        # 收集流式响应
        llm_response = ""
        async for chunk in stream_wrapper:
            if chunk.get("choices"):
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    llm_response += content
        
        # 获取元数据（可选）
        if hasattr(stream_wrapper, '_metadata_dict'):
            instance_name = stream_wrapper._metadata_dict.get('instance_name')
            physical_model_name = stream_wrapper._metadata_dict.get('physical_model_name')
            logger.info(f"使用实例: {instance_name}, 物理模型: {physical_model_name}")
        
        if not llm_response:
            logger.warning("LLM 返回空响应")
            llm_response = f"抱歉，我无法生成关于「{user_query}」的答案。"
        
        logger.info(f"生成答案成功，长度: {len(llm_response)} 字符")
        
        # 5. 返回结果并清理中间状态
        return {
            "messages": [AIMessage(content=llm_response)],
            # 清理所有中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    except Exception as e:
        logger.error(f"LLM 生成答案失败: {str(e)}", exc_info=True)
        
        # 生成失败时，返回兜底答案
        fallback_answer = f"抱歉，我在生成答案时遇到了问题。不过我找到了一些相关信息：\n\n"
        
        # 提取关键信息作为兜底
        if retrieved_docs:
            first_doc = retrieved_docs[0]
            servant_name = first_doc['metadata'].get('servant_name', 'N/A')
            doc_type = first_doc['metadata'].get('type', 'N/A')
            content_preview = first_doc['content'][:200] + "..." if len(first_doc['content']) > 200 else first_doc['content']
            
            fallback_answer += f"来源：{servant_name} - {doc_type}\n{content_preview}"
        else:
            fallback_answer = f"抱歉，我无法回答关于「{user_query}」的问题。"
        
        return {
            "messages": [AIMessage(content=fallback_answer)],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }


async def web_search_node(state: AgentState) -> Dict[str, Any]:
    """
    网络搜索节点，通过 FastMCP 客户端调用 web_search MCP 服务器进行搜索并生成答案。
    
    流程：
    1. 提取用户查询
    2. 通过 FastMCP 客户端调用 search_and_extract 工具
    3. 获取网络搜索结果
    4. LLM 基于搜索结果生成最终答案
    
    关键：此节点内部完成搜索和答案生成，直接输出最终答案
    
    Returns:
        更新 messages（添加 AI 回复），清理中间状态
    """
    logger.info("=== 进入网络搜索节点 ===")
    
    # 1. 获取用户查询
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    if not user_query:
        logger.warning("未找到用户查询")
        return {
            "messages": [AIMessage(content="抱歉，我没有理解您的问题。")],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    logger.info(f"用户查询: '{user_query}'")
    
    # 2. 调用 FastMCP 服务器进行网络搜索
    async def call_fastmcp_search():
        """通过 FastMCP 客户端调用 search_and_extract 工具"""
        # 获取 web_search.py 的绝对路径
        current_dir = Path(__file__).parent.parent
        web_search_script = current_dir / "tools" / "web_search" / "web_search.py"
        
        if not web_search_script.exists():
            logger.error(f"未找到 web_search.py: {web_search_script}")
            return None
        
        logger.info(f"连接 FastMCP 服务器: {web_search_script}")
        
        try:
            # 使用 FastMCP 客户端连接到服务器
            # FastMCP 使用 stdio 传输，通过子进程启动服务器
            client = FastMCP("web-search-client")
            
            # 通过 stdio 连接到服务器
            async with client.stdio_client(
                command=sys.executable,
                args=[str(web_search_script)],
                env=None
            ) as connection:
                logger.info("FastMCP 连接建立成功")
                
                # 调用 search_and_extract 工具
                logger.info(f"调用工具: search_and_extract, query={user_query}")
                
                result = await connection.call_tool(
                    "search_and_extract",
                    query=user_query,
                    max_results=5,
                    extract_count=3
                )
                
                # 解析返回结果
                if result:
                    logger.info(f"FastMCP 搜索成功，结果长度: {len(result)} 字符")
                    return result
                else:
                    logger.warning("FastMCP 工具返回空结果")
                    return None
        
        except Exception as e:
            logger.error(f"FastMCP 调用失败: {str(e)}", exc_info=True)
            return None
    
    # 执行搜索
    try:
        search_results = await call_fastmcp_search()
    except Exception as e:
        logger.error(f"执行网络搜索失败: {str(e)}", exc_info=True)
        search_results = None
    
    # 3. 处理搜索结果
    if not search_results:
        logger.warning("网络搜索失败或未找到结果")
        return {
            "messages": [AIMessage(content=f"抱歉，我无法在网络上找到关于「{user_query}」的相关信息。")],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    logger.info(f"网络搜索成功，结果长度: {len(search_results)} 字符")
    
    # 4. 调用 LLM 生成最终答案
    system_prompt = """你是一位专业的 FGO（Fate/Grand Order）游戏助手，负责根据网络搜索结果回答用户的问题。

**回答要求**：
1. 基于提供的网络搜索结果进行回答
2. 整合多个信息源，给出全面、准确的答案
3. 如果信息不确定，请诚实说明
4. 组织语言清晰、有条理，便于理解
5. 可以引用信息来源的链接
6. 使用友好、专业的语气

**回答格式**：
- 直接回答问题，简洁明了
- 必要时可以分点列举
- 可以用表情符号增强可读性（如 ⭐、🔍、📄 等）"""

    user_prompt = f"""用户问题：{user_query}

网络搜索结果：
{search_results}

请基于以上网络搜索结果回答用户的问题。"""

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    router = get_router()
    
    try:
        logger.info("调用 LLM 生成答案")
        
        # 调用 LLM（非流式）
        result, instance_name, physical_model_name, failover_events = await router.chat(
            messages=llm_messages,
            model="fgo-chat-model",
            stream=False
        )
        
        # 解析 LLM 响应
        llm_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not llm_response:
            logger.warning("LLM 返回空响应，使用搜索结果作为兜底")
            llm_response = f"根据网络搜索，我找到了以下关于「{user_query}」的信息：\n\n{search_results[:500]}..."
        
        logger.info(f"生成答案成功，长度: {len(llm_response)} 字符")
        
        # 5. 返回结果并清理中间状态
        return {
            "messages": [AIMessage(content=llm_response)],
            # 清理所有中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }
    
    except Exception as e:
        logger.error(f"LLM 生成答案失败: {str(e)}", exc_info=True)
        
        # 生成失败时，直接返回搜索结果摘要
        fallback_answer = f"根据网络搜索，我找到了以下关于「{user_query}」的信息：\n\n"
        fallback_answer += search_results[:800] + "..." if len(search_results) > 800 else search_results
        
        return {
            "messages": [AIMessage(content=fallback_answer)],
            # 清理中间状态
            "query_classification": None,
            "retry_count": None,
            "original_query": None,
            "rewritten_query": None,
            "retrieved_docs": None,
            "retrieval_score": None,
            "evaluation_result": None,
            "evaluation_reason": None,
        }

    
def end_node(state: AgentState) -> Dict[str, Any]:
    """
    结束节点，直接结束对话（例如闲聊、问候等）。
    
    Returns:
        更新 messages，清理中间状态
    """
    return {
        "messages": [AIMessage(content="如有其他问题，请随时询问！")],
        # 清理中间状态
        "query_classification": None,
        "retry_count": None,
        "original_query": None,
    }
