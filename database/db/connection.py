import aiomysql
import mysql.connector.pooling
import os

from database.db.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "db": DB_NAME
}

class DatabaseManager:
    """
    一个统一的数据库管理器，同时提供同步和异步的连接池。
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
            
        self.sync_pool = None
        self.async_pool = None
        self._initialized = True
        print("🔧 DatabaseManager 初始化...")

    def init_sync_pool(self):
        """初始化同步连接池 (为了兼容现有的 MemoryDAL)"""
        if self.sync_pool:
            return
        try:
            print("正在初始化 MySQL 同步连接池...")
            self.sync_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="agent_sync_pool",
                pool_size=5,  # 你可以根据需要调整
                **DB_CONFIG
            )
            print("MySQL 同步连接池初始化成功！")
        except Exception as e:
            print(f"初始化 MySQL 同步连接池失败: {e}")

    async def init_async_pool(self):
        if self.async_pool:
            return
        try:
            print("🔧 正在初始化 MySQL 异步连接池...")
            self.async_pool = await aiomysql.create_pool(
                autocommit=True,
                pool_recycle=3600,
                **DB_CONFIG
            )
            print("MySQL 异步连接池初始化成功！")
        except Exception as e:
            print(f"初始化 MySQL 异步连接池失败: {e}")
            self.async_pool = None
            
    def get_sync_connection(self):
        """从同步连接池获取一个连接"""
        if not self.sync_pool:
            self.init_sync_pool()
        if not self.sync_pool:
            raise Exception("同步连接池未能初始化，无法获取连接。")
        return self.sync_pool.get_connection()

    async def get_async_connection(self):
        """从异步连接池获取一个连接"""
        if not self.async_pool:
            await self.init_async_pool()
        if not self.async_pool:
            raise Exception("异步连接池未能初始化，无法获取连接。")
        return await self.async_pool.acquire()

    async def close_all_pools(self):
        """关闭所有连接池"""
        if self.sync_pool:
            # mysql-connector-python 的连接池没有显式的 close 方法
            # 它会在程序退出时自动处理
            print("🔌 同步连接池将在程序退出时关闭。")
        if self.async_pool:
            self.async_pool.close()
            await self.async_pool.wait_closed()
            print("🔌 MySQL 异步连接池已关闭。")

# 创建一个全局的单例实例，供整个应用使用
db_manager = DatabaseManager()

from functools import wraps

def use_sync_connection(is_query: bool = False, dictionary_cursor: bool = False):
    """
    一个装饰器工厂，用于为 MemoryDAL 的同步方法自动管理数据库连接。

    Args:
        is_query (bool): 如果为 True，则不执行 commit()。
        dictionary_cursor (bool): 如果为 True，使用字典游标。
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            connection = None
            try:
                # 1. 自动获取连接
                connection = db_manager.get_sync_connection()
                
                # 2. 自动创建游标
                cursor = connection.cursor(dictionary=dictionary_cursor)
                
                # 3. 将游标作为第一个参数注入到被装饰的函数中
                result = func(self, cursor, *args, **kwargs)
                
                # 4. 自动处理事务
                if not is_query:
                    connection.commit()
                
                return result
                
            except Exception as e:
                print(f"在执行 {func.__name__} 时发生数据库错误: {e}")
                if connection:
                    connection.rollback()
                return None 
            finally:
                # 5. 自动归还连接
                if connection:
                    connection.close()
        return wrapper
    return decorator

from typing import Callable, Coroutine, Any

def use_async_connection(is_query: bool = False, dictionary_cursor: bool = False):
    """
    一个【异步】装饰器工厂，用于为 LogDAL 的异步方法自动管理数据库连接。
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            conn = None
            try:
                # 1. 异步获取连接
                conn = await db_manager.get_async_connection()
                
                # 2. 异步创建游标
                cursor_class = aiomysql.DictCursor if dictionary_cursor else aiomysql.Cursor
                async with conn.cursor(cursor_class) as cursor:
                    
                    # 3. 异步调用原始方法，并注入游标
                    result = await func(self, cursor, *args, **kwargs)
                    
                    # 4. aiomysql 连接池通常配置为 autocommit，无需手动提交
                    #    如果需要手动事务，这里的逻辑会更复杂
                    
                    return result
            
            except Exception as e:
                print(f"在执行异步方法 {func.__name__} 时发生数据库错误: {e}")
                # 异步方法中不应该回滚，因为 autocommit=True
                raise # 重新抛出异常，让上层知道出错了
            finally:
                # 5. 异步归还连接
                if conn:
                    await db_manager.async_pool.release(conn)
        return wrapper
    return decorator
