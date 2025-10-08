from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import uuid
from datetime import datetime, timezone

from models import User, Session, Conversation, SessionSummary

from connection import  use_sync_connection


class MemoryDAL:
    '''所有和数据库相关的操作-记忆模块'''

    @use_sync_connection(is_query=False)
    def create_user(self, cursor, username: str) -> None:
        '''新建用户'''
    
        unique_id = uuid.uuid4()
        current_datetime = datetime.utcnow()
        current_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        unique_token = f"{unique_id}_{current_time}"

        sql = """
        INSERT INTO users (user_id, username, create_at, update_at)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (unique_token, username, current_datetime, current_datetime))

    # # 会话相关
    @use_sync_connection(is_query=False)
    def create_session(self, cursor, user_id: str, session_name: str) -> None:
        '''新建会话'''

        unique_id = uuid.uuid4()
        current_datetime = datetime.utcnow()
        current_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        session_id = f"{unique_id}_{current_time}"
        sql = """
        INSERT INTO sessions (session_id, user_id, session_name, last_active, is_active, message_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (session_id, user_id, session_name, current_datetime, 1, 0))

    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_session_by_id(self, cursor, session_id: str) -> Optional[Session]:
        print('session_id', session_id)
        """根据ID获取会话"""
        sql = """
        SELECT session_id, user_id, session_name, last_active, is_active, message_count
        FROM sessions WHERE session_id = %s
        """
        cursor.execute(sql, (session_id,))
        row = cursor.fetchone()
        if row:
            return Session.from_dict(row)
        return None
    
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_user_sessions(self, cursor, user_id: str, active_only: bool = True) -> List[Session]:
        """获取用户的所有会话"""
        sql = """
        SELECT session_id, user_id, session_name, last_active, is_active, message_count
        FROM sessions WHERE user_id = %s
        """
        params = [user_id]
        
        if active_only:
            sql += " AND is_active = 1"
        
        sql += " ORDER BY last_active DESC"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
                
        return [Session.from_dict(row) for row in rows]
            
    @use_sync_connection(is_query=False)
    def update_session_name(self, cursor, session_id: str, session_name: str) -> bool:
        """更新会话名称"""
        sql = "UPDATE sessions SET session_name = %s WHERE session_id = %s"
        cursor.execute(sql, (session_name, session_id))
        return cursor.rowcount > 0
            
    @use_sync_connection(is_query=False)
    def deactivate_session(self, cursor, session_id: str) -> bool:
        """停用会话"""
        sql = "UPDATE sessions SET is_active = 0 WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        return cursor.rowcount > 0
    
    @use_sync_connection(is_query=False)
    def activate_session(self, cursor, session_id: str) -> bool:
        """激活会话"""
        current_time = datetime.now(timezone.utc)
        sql = "UPDATE sessions SET is_active = 1, last_active = %s WHERE session_id = %s"
        cursor.execute(sql, (current_time, session_id))
        return cursor.rowcount > 0
                
    @use_sync_connection(is_query=True)
    def get_session_count_by_user(self, cursor, user_id: str) -> int:
        """获取用户的会话总数"""
        sql = "SELECT COUNT(*) FROM sessions WHERE user_id = %s"
        cursor.execute(sql, (user_id,))
        return cursor.fetchone()[0]
                
    @use_sync_connection(is_query=True)
    def get_message_count(self, cursor, session_id: str) -> int:
        """获取会话的消息总数"""
        sql = "SELECT message_count FROM sessions WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        return cursor.fetchone()[0]
                
            

    
    @use_sync_connection(is_query=False)
    def delete_session(self, cursor, session_id: str) -> bool:
        """删除会话（级联删除相关数据）"""

        # 删除会话摘要
        cursor.execute("DELETE FROM summary WHERE session_id = %s", (session_id,))
                
        # 删除对话记录
        cursor.execute("DELETE FROM conversations WHERE session_id = %s", (session_id,))
                
        # 删除会话
        cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
                
        return cursor.rowcount > 0
                
    @use_sync_connection(is_query=False)
    def update_session_activity(self, cursor, session_id: str) -> bool:
        """更新会话活跃时间和消息计数"""
        sql = """
        UPDATE sessions 
        SET last_active = %s, message_count = message_count + 1
        WHERE session_id = %s
        """
        current_time = datetime.now(timezone.utc)
        
        cursor.execute(sql, (current_time, session_id))
        return cursor.rowcount > 0
                
            
    # # 对话相关
    @use_sync_connection(is_query=False)
    def add_conversation_turn(self, cursor, session_id: str, query: str, response: str, question_type: str, turn_number: int, token_count: int) -> None:
        """向 conversations 表插入一轮对话"""
        sql = """
            INSERT INTO conversations 
            (session_id, query, response, question_type, turn_number, token_count) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (session_id, query, response, question_type, turn_number, token_count))
    
    @use_sync_connection(is_query=True)
    def get_next_turn_number(self, cursor, session_id: str) -> int:
        """获取会话的下一个轮次号"""
        sql = "SELECT message_count + 1 FROM sessions WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        result = cursor.fetchone()
        return result[0] if result else 1
                
    @use_sync_connection(is_query=True)
    def get_conversation_by_id(self, cursor, conversation_id: int) -> Optional[Conversation]:
        """根据ID获取对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, created_time
        FROM conversations WHERE conversation_id = %s
        """
        cursor.execute(sql, (conversation_id,))
        row = cursor.fetchone()
        if row:
            return Conversation.from_dict(row)
        return None
                
    @use_sync_connection(is_query=True)
    def get_conversations_by_turn_range(self, cursor, session_id: str, start_turn: int, end_turn: int) -> List[Conversation]:
        """获取指定轮次范围的对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, created_time
        FROM conversations 
        WHERE session_id = %s AND turn_number BETWEEN %s AND %s
        ORDER BY turn_number ASC
        """
        cursor.execute(sql, (session_id, start_turn, end_turn))
        rows = cursor.fetchall()
        return [Conversation.from_dict(row) for row in rows]
                
    @use_sync_connection(is_query=True)
    def get_conversation_count(self, cursor, seesion_id: str) -> int:
        '''获取总对话数量'''
        sql = """
        SELECT message_count FROM sessions WHERE session_id = %s
        """
        cursor.execute(sql, (seesion_id))
        return cursor.fetchone()[0]
                
    @use_sync_connection
    def get_conversations_by_type(self, cursor, session_id: str, question_type: str) -> List[Conversation]:
        """获取指定类型的对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, created_time
        FROM conversations 
        WHERE session_id = %s AND question_type = %s
        ORDER BY turn_number ASC
        """
        cursor.execute(sql, (session_id, question_type))
        rows = cursor.fetchall()
        return [Conversation.from_dict(row) for row in rows]
               
        
    # 摘要相关
    @use_sync_connection(is_query=False)
    def create_or_update_summary(self, cursor, session_id: str, summary_text: str, turn_number: int, token_count: int) -> bool:
        """创建或更新会话摘要"""
        current_time = datetime.now(timezone.utc)
        sql = """
        INSERT INTO session_summaries (session_id, summary_text, turn_number, last_summary_time, token_count)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            summary_text = VALUES(summary_text),
            turn_number = VALUES(turn_number),
            last_summary_time = VALUES(last_summary_time)
        """
        cursor.execute(sql, (session_id, summary_text, turn_number, current_time, token_count))
        return cursor.rowcount > 0
                
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_session_summary(self, cursor, session_id: str) -> Optional[SessionSummary]:
        """获取会话摘要"""
        sql = """
        SELECT session_id, summary_text, turn_number, last_summary_time
        FROM session_summaries WHERE session_id = %s
        """
        cursor.execute(sql, (session_id,))
        row = cursor.fetchone()
        if row:
            return SessionSummary.from_dict(row)
        return None
                
    @use_sync_connection(is_query=False)
    def update_summary(self, cursor, session_id: str, summary_text: str, turn_number: int, token_count: int) -> bool:
        """更新会话摘要"""
        current_time = datetime.now(timezone.utc)
        sql = """
        UPDATE session_summaries 
        SET summary_text = %s, turn_number = %s, last_summary_time = %s, token_count = %s
        WHERE session_id = %s
        """
        cursor.execute(sql, (summary_text, turn_number, current_time, token_count, session_id))
        return cursor.rowcount > 0
                
    @use_sync_connection(is_query=False)
    def delete_session_summary(self, cursor, session_id: str) -> bool:
        """删除会话摘要"""
        sql = "DELETE FROM session_summaries WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        return cursor.rowcount > 0
    
from .connection import use_async_connection

class LogDAL:
    '''所有和数据库相关的操作-日志模块'''
    

    


