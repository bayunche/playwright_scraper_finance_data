#!/usr/bin/env python3
import os
from dotenv import load_dotenv

print("测试环境变量加载...")

# 加载.env文件
load_dotenv()

# 检查.env文件
if os.path.exists('.env'):
    print("找到 .env 文件")
    with open('.env', 'r', encoding='utf-8') as f:
        print("文件内容:")
        print(f.read())
else:
    print("未找到 .env 文件")

# 检查环境变量
print("\n环境变量读取结果:")
print(f"DB_HOST: {os.getenv('DB_HOST', '未设置')}")
print(f"DB_PORT: {os.getenv('DB_PORT', '未设置')}")
print(f"DB_USER: {os.getenv('DB_USER', '未设置')}")
print(f"DB_PASSWORD: {'已设置' if os.getenv('DB_PASSWORD') else '未设置'}")
print(f"DB_DATABASE: {os.getenv('DB_DATABASE', '未设置')}")

# 测试数据库连接
try:
    from database import get_database_manager
    db_manager = get_database_manager()
    print(f"\n数据库配置:")
    print(f"Host: {db_manager.host}")
    print(f"Port: {db_manager.port}")
    print(f"User: {db_manager.user}")
    print(f"Database: {db_manager.database}")
    
    if db_manager.test_connection():
        print("数据库连接成功!")
    else:
        print("数据库连接失败!")
        
except Exception as e:
    print(f"数据库测试异常: {e}")