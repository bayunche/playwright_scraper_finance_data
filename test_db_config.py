#!/usr/bin/env python3
"""
测试数据库配置和连接
"""
import os
from dotenv import load_dotenv

def test_env_loading():
    """测试环境变量加载"""
    print("=== 测试环境变量加载 ===")
    
    # 加载.env文件
    load_dotenv()
    
    # 检查.env文件是否存在
    env_file = ".env"
    if os.path.exists(env_file):
        print(f"找到 {env_file} 文件")
        
        # 读取文件内容
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"📄 .env 文件内容:\n{content}")
    else:
        print(f"❌ 未找到 {env_file} 文件")
        return False
    
    # 检查环境变量
    db_vars = {
        'DB_HOST': os.getenv('DB_HOST'),
        'DB_PORT': os.getenv('DB_PORT'),
        'DB_USER': os.getenv('DB_USER'),
        'DB_PASSWORD': os.getenv('DB_PASSWORD'),
        'DB_DATABASE': os.getenv('DB_DATABASE')
    }
    
    print("\n=== 环境变量读取结果 ===")
    for key, value in db_vars.items():
        if value:
            if key == 'DB_PASSWORD':
                print(f"{key}: {'*' * len(value)}")  # 隐藏密码
            else:
                print(f"{key}: {value}")
        else:
            print(f"{key}: ❌ 未设置")
    
    return all(db_vars.values())

def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试数据库连接 ===")
    
    try:
        from database import get_database_manager
        
        db_manager = get_database_manager()
        print(f"数据库URL: {db_manager.database_url.replace(db_manager.password, '*'*len(db_manager.password))}")
        
        if db_manager.test_connection():
            print("✅ 数据库连接成功!")
            return True
        else:
            print("❌ 数据库连接失败!")
            return False
            
    except Exception as e:
        print(f"❌ 数据库连接异常: {e}")
        return False

def main():
    """主函数"""
    print("数据库配置诊断工具")
    print("=" * 50)
    
    # 测试环境变量加载
    env_ok = test_env_loading()
    
    if not env_ok:
        print("\n⚠️  环境变量配置有问题，请检查.env文件")
        return
    
    # 测试数据库连接
    db_ok = test_database_connection()
    
    if db_ok:
        print("\n🎉 所有测试通过!")
    else:
        print("\n💡 解决建议:")
        print("1. 确保MySQL服务正在运行")
        print("2. 检查.env文件中的数据库配置")
        print("3. 确认数据库用户权限")
        print("4. 运行: mysql -u root -p 测试手动连接")

if __name__ == "__main__":
    main()