"""
FGO 游戏助手 - FastAPI 后端服务

提供 RESTful API 和 WebSocket 接口
"""
import os
import sys
from pathlib import Path

# 确保工作目录为项目根目录
project_root = Path(__file__).parent.parent
os.chdir(str(project_root))
sys.path.insert(0, str(project_root))

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.graph import create_game_character_graph
from src.memory.memory import MemoryManager

# ==================== 配置日志 ====================

# 确保日志目录存在
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/web_service.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ==================== 创建 FastAPI 应用 ====================

app = FastAPI(
    title="FGO Game Assistant",
    description="FGO 游戏助手 - 提供从者查询、战略建议等功能",
    version="1.0.0"
)

# 挂载静态文件
web_dir = project_root / "web"
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")

# ==================== 全局变量 ====================

# LangGraph 实例（懒加载）
_graph_instance = None
_memory_manager = None

def get_graph():
    """获取或创建 LangGraph 实例"""
    global _graph_instance
    if _graph_instance is None:
        logger.info("🔧 初始化 LangGraph...")
        _graph_instance = create_game_character_graph()
        logger.info("✅ LangGraph 初始化完成")
    return _graph_instance

def get_memory_manager():
    """获取或创建 MemoryManager 实例"""
    global _memory_manager
    if _memory_manager is None:
        logger.info("🔧 初始化 MemoryManager...")
        MAX_TOKEN_LENGTH = 4000 
        _memory_manager = MemoryManager(max_length=MAX_TOKEN_LENGTH)
        logger.info("✅ MemoryManager 初始化完成")
    return _memory_manager

# ==================== Pydantic 模型 ====================

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    user_id: str
    session_name: str

class ChatMessageRequest(BaseModel):
    """聊天消息请求"""
    session_id: str
    message: str

class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    session_name: str
    created_at: str
    last_active: str

class ConversationResponse(BaseModel):
    """对话响应"""
    conversation_id: int
    role: str
    content: str
    created_at: str
    question_type: Optional[str] = None

# ==================== 根路由 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页"""
    index_file = web_dir / "index.html"
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()

# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

# ==================== 用户管理 ====================

@app.post("/api/users/register")
async def register_user(username: str):
    """
    注册新用户
    
    Args:
        username: 用户名
        
    Returns:
        用户信息（包括 user_id）
    """
    try:
        memory = get_memory_manager()
        user_id = memory.create_user(username)
        
        if user_id:
            logger.info(f"✅ 用户注册成功: {username} (ID: {user_id})")
            return {
                "success": True,
                "user_id": user_id,
                "username": username
            }
        else:
            raise HTTPException(status_code=400, detail="用户注册失败")
    
    except Exception as e:
        logger.error(f"❌ 用户注册失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 会话管理 ====================

@app.post("/api/sessions/create", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    创建新会话
    
    Args:
        request: 创建会话请求
        
    Returns:
        会话信息
    """
    try:
        memory = get_memory_manager()
        session_id = memory.create_session(
            user_id=request.user_id,
            session_name=request.session_name
        )
        
        if session_id:
            logger.info(f"✅ 会话创建成功: {request.session_name} (ID: {session_id[:20]}...)")
            return SessionResponse(
                session_id=session_id,
                session_name=request.session_name,
                created_at=datetime.now().isoformat(),
                last_active=datetime.now().isoformat()
            )
        else:
            raise HTTPException(status_code=400, detail="会话创建失败")
    
    except Exception as e:
        logger.error(f"❌ 会话创建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{user_id}", response_model=List[SessionResponse])
async def get_user_sessions(user_id: str):
    """
    获取用户的所有会话
    
    Args:
        user_id: 用户ID
        
    Returns:
        会话列表
    """
    try:
        memory = get_memory_manager()
        sessions = memory.get_user_sessions(user_id)
        
        # 转换为响应模型，确保日期格式正确
        session_list = []
        for session in sessions:
            # 确保 last_active 是 ISO 格式字符串
            last_active = session.get('last_active')
            
            if isinstance(last_active, datetime):
                last_active = last_active.isoformat()
            elif last_active is None:
                last_active = datetime.now().isoformat()
            
            # created_at 使用 last_active（MemoryManager 没有返回 created_at）
            session_list.append(SessionResponse(
                session_id=session['session_id'],
                session_name=session['session_name'],
                created_at=last_active,  # 使用 last_active 作为 created_at
                last_active=last_active
            ))
        
        logger.info(f"📚 获取用户会话: {user_id} - {len(session_list)} 个会话")
        return session_list
    
    except Exception as e:
        logger.error(f"❌ 获取会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _get_session_history_impl(session_id: str, limit: int = 50):
    """
    获取会话的对话历史（内部实现）
    
    Args:
        session_id: 会话ID
        limit: 返回的最大消息数
        
    Returns:
        对话历史列表
    """
    try:
        memory = get_memory_manager()
        # 使用正确的方法名：get_conversation_history
        conversations = memory.get_conversation_history(session_id, limit=limit)
        
        # 转换为响应模型（Conversation 对象转为两条消息：query 和 response）
        conversation_list = []
        for conv in conversations:
            # conv 是 Conversation 对象，有 query 和 response 两个字段
            # 数据库中没有 created_at 字段，使用当前时间作为默认值
            created_at = conv.created_at
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            elif created_at is None:
                # 如果没有时间戳，使用当前时间
                created_at = datetime.now().isoformat()
            
            # 添加用户消息（query）
            if conv.query:
                conversation_list.append(ConversationResponse(
                    conversation_id=conv.conversation_id,
                    role="user",
                    content=conv.query,
                    created_at=created_at,
                    question_type=conv.question_type
                ))
            
            # 添加助手消息（response）
            if conv.response:
                conversation_list.append(ConversationResponse(
                    conversation_id=conv.conversation_id,
                    role="assistant",
                    content=conv.response,
                    created_at=created_at,
                    question_type=conv.question_type
                ))
        
        logger.info(f"📚 获取会话历史: {session_id[:20]}... - {len(conversation_list)} 条")
        return conversation_list
    
    except Exception as e:
        logger.error(f"❌ 获取会话历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/history", response_model=List[ConversationResponse])
async def get_session_history(session_id: str, limit: int = 50):
    """获取会话的对话历史"""
    return await _get_session_history_impl(session_id, limit)

@app.get("/api/history/{session_id}", response_model=List[ConversationResponse])
async def get_history_legacy(session_id: str, limit: int = 50):
    """获取会话的对话历史（兼容旧版前端路由）"""
    return await _get_session_history_impl(session_id, limit)

# ==================== WebSocket 聊天 ====================

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket 聊天接口
    
    Args:
        websocket: WebSocket 连接
        session_id: 会话ID
        
    工作流程：
    1. 接受连接
    2. 接收用户消息
    3. 调用 LangGraph 处理
    4. 流式返回结果
    5. 保存到数据库
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket 连接建立: {session_id[:20]}...")
    
    try:
        # 发送连接成功消息
        await websocket.send_json({
            "type": "system",
            "content": "连接成功！开始对话吧~"
        })
        
        # 持续接收消息
        while True:
            # 接收消息
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "message":
                user_message = data.get("content", "").strip()
                
                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "content": "消息不能为空"
                    })
                    continue
                
                logger.info(f"📨 收到消息 [{session_id[:20]}...]: {user_message[:50]}...")
                
                # 处理消息
                await process_chat_message(
                    websocket=websocket,
                    session_id=session_id,
                    user_message=user_message
                )
            
            elif message_type == "ping":
                # 心跳响应
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                logger.debug(f"💓 心跳响应: {session_id[:20]}...")
    
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 连接断开: {session_id[:20]}...")
    
    except Exception as e:
        logger.error(f"❌ WebSocket 错误: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"服务器错误: {str(e)}"
            })
        except:
            pass

async def process_chat_message(
    websocket: WebSocket,
    session_id: str,
    user_message: str
):
    """
    处理聊天消息（核心逻辑）
    
    Args:
        websocket: WebSocket 连接
        session_id: 会话ID
        user_message: 用户消息
        
    流程：
    1. 从数据库加载历史对话
    2. 添加当前用户消息
    3. 调用 LangGraph 执行推理（流式输出）
    4. 将流式内容发送给客户端
    5. 保存对话到数据库
    """
    ai_response = ""
    question_type = "general"
    
    try:
        # 1. 加载历史对话
        memory = get_memory_manager()
        historical_messages = await memory.build_langchain_message(session_id)
        logger.info(f"📚 加载历史消息: {len(historical_messages)} 条")
        
        # 2. 添加当前用户消息
        historical_messages.append(HumanMessage(content=user_message))
        
        # 3. 🎯 发送开始标记（告诉前端创建消息容器）
        try:
            await websocket.send_json({
                "type": "start",
                "timestamp": datetime.now().isoformat()
            })
        except WebSocketDisconnect:
            logger.info(f"🔌 客户端在开始前断开连接: {session_id[:20]}...")
            return
        
        # 4. 🎯 定义流式回调函数
        stream_aborted = False  # 标记流是否被中断
        
        async def stream_token_callback(token: str):
            """实时发送 token 到 WebSocket"""
            nonlocal stream_aborted
            
            if stream_aborted:
                return  # 如果已中断，直接返回
            
            try:
                await websocket.send_json({
                    "type": "token",
                    "content": token
                })
            except WebSocketDisconnect:
                logger.warning(f"⚠️ 客户端断开连接，停止发送 token")
                stream_aborted = True
            except Exception as e:
                logger.error(f"❌ 流式发送失败: {e}")
                stream_aborted = True
        
        # 5. 调用 LangGraph 执行推理（传入流式回调）
        graph_instance = get_graph()
        
        # 🎯 在 state 中传递流式回调
        result = await graph_instance.ainvoke({
            "messages": historical_messages,
            "stream_callback": stream_token_callback  # 传递回调函数
        })
        
        # 如果流被中断，不再继续处理
        if stream_aborted:
            logger.info(f"⚠️ 流式传输被中断: {session_id[:20]}...")
            return
        
        # 从最终结果中提取 AI 回复
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break
        
        # 从结果中提取问题类型
        # 注意：由于我们使用 ainvoke，中间状态会被清理
        # 所以这里可能拿不到 classification，使用默认值
        question_type = "general"
        
        # 6. 如果没有获取到 AI 回复，生成默认消息
        if not ai_response:
            ai_response = "抱歉，我现在无法回答您的问题。"
            try:
                await websocket.send_json({
                    "type": "token",
                    "content": ai_response
                })
            except WebSocketDisconnect:
                logger.info(f"🔌 客户端断开连接，跳过发送默认消息")
                return
        
        # 7. 发送结束标记
        try:
            await websocket.send_json({
                "type": "end",
                "question_type": question_type,
                "timestamp": datetime.now().isoformat()
            })
        except WebSocketDisconnect:
            logger.info(f"🔌 客户端断开连接，跳过发送结束标记")
            # 连接已断开，但仍然保存对话到数据库
            pass
        
        # 8. 保存对话到数据库
        token_count = memory.token_calculate(user_message + ai_response)
        save_success = memory.save_conversation_turn(
            session_id=session_id,
            query=user_message,
            response=ai_response,
            question_type=question_type,
            token_count=token_count
        )
        
        if save_success:
            logger.info(f"💾 对话已保存 - Session: {session_id[:20]}...")
        else:
            logger.warning(f"⚠️ 对话保存失败 - Session: {session_id[:20]}...")
    
    except WebSocketDisconnect:
        # 客户端断开连接，这是正常情况，不需要记录错误
        logger.info(f"🔌 客户端主动断开连接: {session_id[:20]}...")
        # 不要 raise，让主循环继续（虽然这里会退出函数，但不影响主循环）
    
    except Exception as e:
        logger.error(f"❌ 处理对话失败: {e}", exc_info=True)
        
        # 尝试发送错误消息（如果连接还在）
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"处理失败: {str(e)}"
            })
        except WebSocketDisconnect:
            # 如果连接已断开，忽略发送错误
            logger.info(f"🔌 客户端断开连接，无法发送错误消息")
        except Exception:
            pass
        
        # 不要让异常传播，让主循环继续运行


# ==================== 启动函数 ====================

if __name__ == "__main__":
    import uvicorn
    
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    logger.info("🚀 启动 FGO 游戏助手 Web 服务...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 生产环境关闭自动重载
        log_level="info"
    )
