from typing import Optional, List, Dict, Tuple
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain.chat_models import init_chat_model
import tiktoken

from database.db.repositories import MemoryDAL
from database.db.models import User, Session, Conversation, SessionSummary

class MemoryManager:
    def __init__(self, max_length: int):
        self.dal = MemoryDAL()
        self.max_length = max_length

    def ensure_user_exists(self, user_id: str, username: str = None) -> User:
        """
        确保用户存在，如果不存在则创建
        
        Args:
            user_id: 用户ID
            username: 用户名（可选）
            
        Returns:
            User: 用户对象
        """
        user = self.dal.get_user_by_id(user_id)
        if not user:
            if not username:
                username = f"用户_{user_id[:8]}"
            actual_user_id = self.dal.create_user(username)
            user = self.dal.get_user_by_id(actual_user_id)
        return user
    
    def get_user_info(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        return self.dal.get_user_by_id(user_id)
    
    def update_user_info(self, user_id: str, username: str) -> bool:
        """更新用户信息"""
        return self.dal.update_user(user_id, username)
    
    def create_session(self, user_id: str, username: str = None, session_name: str = None) -> str:
        """
        为用户创建新会话
        
        Args:
            user_id: 用户ID
            username: 用户名（新用户时需要）
            session_name: 会话名称（可选）
            
        Returns:
            str: 会话ID
        """
        # 确保用户存在
        self.ensure_user_exists(user_id, username)
        
        # 生成会话名称
        if not session_name:
            user_session_count = self.dal.get_session_count_by_user(user_id)
            session_name = f"会话_{user_session_count + 1}"
        
        # 创建会话
        session_id = self.dal.create_session(user_id, session_name)
        return session_id
    
    def get_session_info(self, session_id: str) -> Optional[Session]:
        """获取会话信息"""
        return self.dal.get_session_by_id(session_id)
    
    def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取用户的会话列表（包含摘要信息）
        
        Args:
            user_id: 用户ID
            active_only: 是否只返回活跃会话
            
        Returns:
            List[Dict]: 会话摘要列表
        """
        sessions = self.dal.get_user_sessions(user_id, active_only)
        
        result = []
        for session in sessions:
            # 获取最后一轮对话
            recent_conversations = self.dal.get_recent_conversations(session.session_id, 1)
            last_message = ""
            if recent_conversations:
                last_message = recent_conversations[0].query[:50]
                if len(recent_conversations[0].query) > 50:
                    last_message += "..."
            
            result.append({
                'session_id': session.session_id,
                'session_name': session.session_name,
                'last_active': session.last_active,
                'message_count': session.message_count,
                'last_message': last_message,
                'is_active': session.is_active
            })
        
        return result
    
    def update_session_name(self, session_id: str, session_name: str) -> bool:
        """更新会话名称"""
        return self.dal.update_session_name(session_id, session_name)
    
    def activate_session(self, session_id: str) -> bool:
        """激活会话"""
        return self.dal.activate_session(session_id)
    
    def deactivate_session(self, session_id: str) -> bool:
        """停用会话"""
        return self.dal.deactivate_session(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有数据"""
        return self.dal.delete_session(session_id)
    
    def save_conversation_turn(
        self, 
        session_id: str, 
        query: str, 
        response: str,
        question_type: str = "general",
        token_count: int = 0
    ) -> bool:
        """
        保存一轮对话
        
        Args:
            session_id: 会话ID
            user_query: 用户问题
            ai_response: AI回答
            question_type: 问题类型(knowledge_base, web_search, general)
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 保存对话
            conversation_id = self.dal.add_conversation_turn(
                session_id, query, response, question_type, token_count
            )
            
            # 更新会话活跃状态
            self.dal.update_session_activity(session_id)
            
            # 检查是否需要生成摘要
            current_turn = self.dal.get_max_turn_number(session_id)
            if current_turn >= self.summary_threshold and current_turn % self.summary_threshold == 0:
                self._generate_session_summary(session_id, current_turn)
            
            return conversation_id is not None
            
        except Exception as e:
            print(f"保存对话失败: {e}")
            return False
        
    def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = None, 
        offset: int = 0
    ) -> List[Conversation]:
        """
        获取对话历史记录
        
        Args:
            session_id: 会话ID
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            List[Conversation]: 对话记录列表
        """
        return self.dal.get_session_conversations(session_id, limit, offset)
    
    def search_conversations(self, session_id: str, keyword: str, limit: int = 20) -> List[Conversation]:
        """在会话中搜索对话"""
        return self.dal.search_conversations(session_id, keyword, limit)
    
    def get_conversations_by_type(self, session_id: str, question_type: str) -> List[Conversation]:
        """获取指定类型的对话"""
        return self.dal.get_conversations_by_type(session_id, question_type)
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """删除指定对话"""
        return self.dal.delete_conversation(conversation_id)
    
    def delete_conversations_after_turn(self, session_id: str, turn_number: int) -> int:
        """删除指定轮次之后的所有对话"""
        return self.dal.delete_conversations_after_turn(session_id, turn_number)
    
    def content_compression(self, summary_text: str, recent_conversations: List[Conversation]) -> str:
        '''上下文压缩'''
        model = init_chat_model(
            "deepseek-chat",
            temperature=0.5,
        )
        user_content = f'''
        你是一个专业的对话摘要助手。你的任务是将以下用户与AI助手的对话记录，压缩成一段简洁、连贯的摘要。

        **摘要目标**：
        为AI助手提供上下文。这份摘要将在未来的对话中被AI助手阅读，以帮助它记起之前的对话内容，更好地继续为用户服务。

        **摘要要求**：
        1. **保留核心信息**：确保所有关键实体（如角色名、技能名）、重要结论、用户的核心意图和AI的关键回答都被包含在内。
        2. **注重连贯性**：将零散的问答整合成一段流畅的、第三人称叙述的文本。
        3. **忽略闲聊**：省略无关紧要的问候语、确认性回复（如“好的”、“明白了”）和不影响核心事实的闲聊。
        4. **简洁明了**：使用尽可能少的文字来概括尽可能多的信息。

        **待摘要的对话记录**：
        {summary_text}\n
        {recent_conversations}
        **请生成摘要**：
        '''
        response = model.invoke(
            [{"role": "user", "content": user_content}]
        )
        return response.choices[0].message.content
    
    def token_calculate(self, text: str) -> int:
        '''计算token数量'''
        model_name = "deepseek-chat"
        try:
            encoding = tiktoken.encoding_for_model(model_name=model_name)
        except KeyError:
            print(f"未找到名为{model_name}的模型，将使用默认设置")
            encoding = tiktoken.get_encoding("cl100k_base")

        token_ids = encoding.encode(text=text)
        return len(token_ids)
    
    def build_langchain_message(self, session_id: str) -> List[BaseMessage]:
        '''构建langgraph State所需要的message信息'''
        
        summary = self.dal.get_session_summary(session_id)
        start_turn = 0
        messages = List[BaseMessage] = []
        token_count = 0

        if summary:
            summary_text = (
                f"这是你与用户之前对话的摘要，请利用这些信息更好地继续当前对话:\n"
                f"{summary.summary_text}"
            )
            messages.append(SystemMessage(content=summary_text))
            start_turn = summary.turn_number
            token_count += summary.token_count

        message_count = self.dal.get_message_count(session_id)
        recent_conversations = self.dal.get_conversations_by_turn_range(session_id, start_turn + 1, message_count)

        for conversation in recent_conversations:
            messages.append(HumanMessage(content=conversation.query))
            messages.append(AIMessage(content=conversation.response))
            token_count += conversation.token_count

        # 如果大于最大长度，做一次上下文压缩
        if token_count > self.max_length:
            new_summary_text = self.content_compression(summary_text, recent_conversations)
            token_count = self.token_calculate(new_summary_text)
            self.dal.update_summary(session_id, new_summary_text, message_count, token_count)
            return [SystemMessage(content=new_summary_text)]
        return messages
    
    
