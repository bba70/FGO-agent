import os
import json
import mysql.connector



DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "your_user"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
    "db": os.getenv("DB_NAME", "llm_monitoring"),
    "autocommit": True # 自动提交，简化操作
}