from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import uuid
from datetime import datetime, timezone, timedelta

from database.db.models import User, Session, Conversation, SessionSummary

from database.db.connection import  use_sync_connection


class MemoryDAL:
    '''所有和数据库相关的操作-记忆模块'''

    # 用户相关
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_user_by_id(self, cursor, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        sql = """
        SELECT user_id, username, create_at, update_at
        FROM users WHERE user_id = %s
        """
        cursor.execute(sql, (user_id,))
        row = cursor.fetchone()
        if row:
            return User.from_dict(row)
        return None

    @use_sync_connection(is_query=False)
    def create_user(self, cursor, username: str) -> str:
        '''新建用户，返回user_id'''
    
        unique_id = uuid.uuid4()
        current_datetime = datetime.utcnow()
        current_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        unique_token = f"{unique_id}_{current_time}"

        sql = """
        INSERT INTO users (user_id, username, create_at, update_at)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (unique_token, username, current_datetime, current_datetime))
        return unique_token

    @use_sync_connection(is_query=False)
    def update_user(self, cursor, user_id: str, username: str) -> bool:
        """更新用户信息"""
        current_time = datetime.now(timezone.utc)
        sql = "UPDATE users SET username = %s, update_at = %s WHERE user_id = %s"
        cursor.execute(sql, (username, current_time, user_id))
        return cursor.rowcount > 0

    # # 会话相关
    @use_sync_connection(is_query=False)
    def create_session(self, cursor, user_id: str, session_name: str) -> str:
        '''新建会话，返回session_id'''

        unique_id = uuid.uuid4()
        current_datetime = datetime.utcnow()
        current_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        session_id = f"{unique_id}_{current_time}"
        sql = """
        INSERT INTO sessions (session_id, user_id, session_name, last_active, is_active, message_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (session_id, user_id, session_name, current_datetime, 1, 0))
        return session_id

    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_session_by_id(self, cursor, session_id: str) -> Optional[Session]:
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
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (session_id, query, response, question_type, turn_number, token_count))
    
    @use_sync_connection(is_query=True)
    def get_next_turn_number(self, cursor, session_id: str) -> int:
        """获取会话的下一个轮次号"""
        sql = "SELECT message_count + 1 FROM sessions WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        result = cursor.fetchone()
        return result[0] if result else 1
                
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_conversation_by_id(self, cursor, conversation_id: int) -> Optional[Conversation]:
        """根据ID获取对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations WHERE conversation_id = %s
        """
        cursor.execute(sql, (conversation_id,))
        row = cursor.fetchone()
        if row:
            return Conversation.from_dict(row)
        return None
                
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_conversations_by_turn_range(self, cursor, session_id: str, start_turn: int, end_turn: int) -> List[Conversation]:
        """获取指定轮次范围的对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations 
        WHERE session_id = %s AND turn_number BETWEEN %s AND %s
        ORDER BY turn_number ASC
        """
        cursor.execute(sql, (session_id, start_turn, end_turn))
        rows = cursor.fetchall()
        if rows:
            return [Conversation.from_dict(row) for row in rows]
        return []
                
    @use_sync_connection(is_query=True)
    def get_conversation_count(self, cursor, seesion_id: str) -> int:
        '''获取总对话数量'''
        sql = """
        SELECT message_count FROM sessions WHERE session_id = %s
        """
        cursor.execute(sql, (seesion_id))
        return cursor.fetchone()[0]
                
    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_conversations_by_type(self, cursor, session_id: str, question_type: str) -> List[Conversation]:
        """获取指定类型的对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations 
        WHERE session_id = %s AND question_type = %s
        ORDER BY turn_number ASC
        """
        cursor.execute(sql, (session_id, question_type))
        rows = cursor.fetchall()
        if rows:
            return [Conversation.from_dict(row) for row in rows]
        return []

    @use_sync_connection(is_query=True)
    def get_max_turn_number(self, cursor, session_id: str) -> int:
        """获取会话的最大轮次号"""
        sql = "SELECT COALESCE(MAX(turn_number), 0) FROM conversations WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_session_conversations(self, cursor, session_id: str, limit: int = None, offset: int = 0) -> List[Conversation]:
        """获取会话的所有对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations 
        WHERE session_id = %s
        ORDER BY turn_number ASC
        """
        params = [session_id]
        
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        if rows:
            return [Conversation.from_dict(row) for row in rows]
        return []

    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def get_recent_conversations(self, cursor, session_id: str, limit: int = 10) -> List[Conversation]:
        """获取最近的对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations 
        WHERE session_id = %s
        ORDER BY turn_number DESC
        LIMIT %s
        """
        cursor.execute(sql, (session_id, limit))
        rows = cursor.fetchall()
        if rows:
            # 反转顺序，使其从旧到新
            return [Conversation.from_dict(row) for row in reversed(rows)]
        return []

    @use_sync_connection(is_query=True, dictionary_cursor=True)
    def search_conversations(self, cursor, session_id: str, keyword: str, limit: int = 50) -> List[Conversation]:
        """搜索对话"""
        sql = """
        SELECT conversation_id, session_id, query, response, question_type, turn_number, token_count,
               create_at
        FROM conversations 
        WHERE session_id = %s AND (query LIKE %s OR response LIKE %s)
        ORDER BY turn_number DESC
        LIMIT %s
        """
        search_pattern = f"%{keyword}%"
        cursor.execute(sql, (session_id, search_pattern, search_pattern, limit))
        rows = cursor.fetchall()
        if rows:
            return [Conversation.from_dict(row) for row in rows]
        return []

    @use_sync_connection(is_query=False)
    def delete_conversation(self, cursor, conversation_id: int) -> bool:
        """删除单个对话"""
        sql = "DELETE FROM conversations WHERE conversation_id = %s"
        cursor.execute(sql, (conversation_id,))
        return cursor.rowcount > 0

    @use_sync_connection(is_query=False)
    def delete_conversations_after_turn(self, cursor, session_id: str, turn_number: int) -> bool:
        """删除某轮次之后的所有对话"""
        sql = "DELETE FROM conversations WHERE session_id = %s AND turn_number > %s"
        cursor.execute(sql, (session_id, turn_number))
        
        # 更新会话的消息计数
        update_sql = "UPDATE sessions SET message_count = %s WHERE session_id = %s"
        cursor.execute(update_sql, (turn_number, session_id))
        
        return cursor.rowcount > 0
               
        
    # 摘要相关
    @use_sync_connection(is_query=False)
    def create_or_update_summary(self, cursor, session_id: str, summary_text: str, turn_number: int, token_count: int) -> bool:
        """创建或更新会话摘要"""
        current_time = datetime.now(timezone.utc)
        sql = """
        INSERT INTO summary (session_id, summary_text, turn_number, last_summary_time, token_count)
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
        SELECT session_id, summary_text, turn_number, last_summary_time, token_count
        FROM summary WHERE session_id = %s
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
        UPDATE summary
        SET summary_text = %s, turn_number = %s, last_summary_time = %s, token_count = %s
        WHERE session_id = %s
        """
        cursor.execute(sql, (summary_text, turn_number, current_time, token_count, session_id))
        return cursor.rowcount > 0
                
    @use_sync_connection(is_query=False)
    def delete_session_summary(self, cursor, session_id: str) -> bool:
        """删除会话摘要"""
        sql = "DELETE FROM summary WHERE session_id = %s"
        cursor.execute(sql, (session_id,))
        return cursor.rowcount > 0
    
from .connection import use_async_connection
from database.db.models import Models, Logs

class LogDAL:
    '''所有和数据库相关的操作-日志模块'''
    @use_async_connection(dictionary_cursor=True)
    async def get_or_create_model(self,cursor, model_data: Models):
        """根据 Models 对象查找或创建模型记录，并返回其ID。"""


        print("开始插入model")
        # 1. 查找
        await cursor.execute("SELECT id FROM models WHERE instance_name = %s", (model_data.instance_name,))
        result = await cursor.fetchone()
        if result:
            return result['id']
        
        # 2. 创建
        print(f"  - 在数据库中未找到模型 '{model_data.instance_name}'，正在创建...")


        create_at = datetime.now(timezone.utc)
        sql = "INSERT INTO models (id, instance_name, type, physical_model_name, base_url, create_at) VALUES (%s, %s, %s, %s, %s, %s)"
        await cursor.execute(sql, (
            model_data.id,
            model_data.instance_name, 
            model_data.type, 
            model_data.physical_model_name, 
            model_data.base_url,
            create_at
        ))

    @use_async_connection()
    async def save_log(self, cursor, log: Logs):
        """
        insert log
        """
        
        # 1. 获取适合数据库的字典
        #    to_db_dict 依然很有用，因为它处理了 bool, datetime, json 等类型的转换
        log_dict = log.to_dict()


        # 打印出来用于调试，确认内容
        print('DEBUG - log_dict to be inserted:', log_dict)
        
        # 2. 构建简单的 INSERT SQL 语句
        columns = ', '.join(f'`{key}`' for key in log_dict.keys())
        placeholders = ', '.join(['%s'] * len(log_dict))
        
        sql = f"INSERT INTO logs ({columns}) VALUES ({placeholders})"
        
        # 3. 执行
        try:
            await cursor.execute(sql, tuple(log_dict.values()))
            print(f"✅ 日志记录 {log.id} 已成功插入数据库。")
        except Exception as e:
            print(f"❌ 插入日志记录 {log.id} 时发生数据库错误: {e}")
            raise

    @use_async_connection(dictionary_cursor=True)
    async def get_total_requests(self,cursor, time_delta: timedelta = timedelta(days=1)) -> int:
        """获取指定时间范围内的总请求数。"""
        start_time = datetime.utcnow() - time_delta
        await cursor.execute("SELECT COUNT(id) as total FROM logs WHERE timestamp_start >= %s", (start_time,))
        result = await cursor.fetchone()
        return result['total'] if result else 0

    @use_async_connection(dictionary_cursor=True)
    async def get_token_usage_summary(self,cursor, time_delta: timedelta = timedelta(days=1)) -> List[Dict[str, Any]]:
        """获取指定时间范围内，按模型分组的 Token 消耗统计。"""
        start_time = datetime.utcnow() - time_delta
        sql = """
            SELECT 
                m.physical_model_name, m.type as adapter_type,
                SUM(l.prompt_token) as total_prompt_tokens,
                SUM(l.completion_token) as total_completion_tokens,
                COUNT(l.id) as request_count
            FROM logs l JOIN models m ON l.model_id = m.id
            WHERE l.timestamp_start >= %s AND l.status = 'success'
            GROUP BY m.physical_model_name, m.type
            ORDER BY total_prompt_tokens + total_completion_tokens DESC;
        """
        await cursor.execute(sql, (start_time,))
        return await cursor.fetchall()

    @use_async_connection(dictionary_cursor=True)
    async def get_error_rate(self,cursor, time_delta: timedelta = timedelta(days=1)) -> float:
        """计算指定时间范围内的错误率。"""
        start_time = datetime.utcnow() - time_delta
        sql = """
            SELECT
                COUNT(id) as total_count,
                SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) as error_count
            FROM logs WHERE timestamp_start >= %s;
        """
        await cursor.execute(sql, (start_time,))
        result = await cursor.fetchone()
        if not result or result['total_count'] == 0:
            return 0.0
        return (result['error_count'] / result['total_count']) * 100

    @use_async_connection(dictionary_cursor=True)
    async def get_recent_logs(self, cursor, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的日志记录。"""
        sql = """
            SELECT l.*, m.instance_name
            FROM logs l LEFT JOIN models m ON l.model_id = m.id
            ORDER BY l.timestamp_start DESC LIMIT %s;
        """
        await cursor.execute(sql, (limit,))
        return await cursor.fetchall()

    


