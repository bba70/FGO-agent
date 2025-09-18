import mysql.connector.pooling
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

db_config = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
}

# 创建一个全局的连接池实例
# pool_name 和 pool_size 可以根据你的应用需求调整
connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="agent_pool",
    pool_size=5,
    **db_config
)

def get_connection():
    """从连接池中获取一个数据库连接"""
    return connection_pool.get_connection()