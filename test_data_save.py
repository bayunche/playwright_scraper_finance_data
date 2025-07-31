#!/usr/bin/env python3
"""
测试数据保存修复效果
"""
from database import get_database_manager
from sqlalchemy import text
import json
from datetime import datetime

def test_existing_data_reprocess():
    """重新处理现有数据测试修复效果"""
    print("=== 测试数据保存修复 ===")
    
    db = get_database_manager()
    session = db.SessionLocal()
    
    try:
        # 获取最新的原始数据
        result = session.execute(text('SELECT record_id, raw_json FROM raw_data_backup ORDER BY id DESC LIMIT 1'))
        backup_record = result.fetchone()
        
        if not backup_record:
            print("未找到原始数据备份")
            return
            
        record_id = backup_record[0]
        raw_data = json.loads(backup_record[1])
        
        print(f"重新处理记录ID: {record_id}")
        print(f"原始数据包含 {len(raw_data)} 个数据源")
        
        # 清理现有的子表数据（保留主记录）
        tables_to_clean = [
            'us_stock_gainers',
            'a_stock_statistics', 
            'global_macro_indicators',
            'market_turnover'
        ]
        
        for table in tables_to_clean:
            result = session.execute(text(f'DELETE FROM {table} WHERE record_id = :record_id'), {'record_id': record_id})
            deleted_count = result.rowcount
            print(f"清理 {table}: {deleted_count} 条记录")
        
        # 使用修复后的逻辑重新保存数据
        db_manager = get_database_manager()
        
        # 重新保存各类数据
        db_manager._save_global_macro_data(session, record_id, raw_data)
        db_manager._save_us_gainers_data(session, record_id, raw_data)  
        db_manager._save_a_stock_stats_data(session, record_id, raw_data)
        db_manager._save_market_turnover_data(session, record_id, raw_data)
        
        # 提交更改
        session.commit()
        print("数据重新保存完成")
        
        # 验证结果
        print("\n=== 验证保存结果 ===")
        for table in tables_to_clean:
            result = session.execute(text(f'SELECT COUNT(*) FROM {table} WHERE record_id = :record_id'), {'record_id': record_id})
            count = result.fetchone()[0]
            print(f"{table}: {count} 条记录")
            
        # 显示美股数据详情
        result = session.execute(text("""
            SELECT stock_symbol, stock_name, current_price, change_percent, ranking_position 
            FROM us_stock_gainers 
            WHERE record_id = :record_id 
            ORDER BY ranking_position
        """), {'record_id': record_id})
        
        us_stocks = result.fetchall()
        if us_stocks:
            print(f"\n美股涨幅前五详情:")
            for stock in us_stocks:
                print(f"  {stock[4]}. {stock[0]} ({stock[1]}) - 价格:{stock[2]}, 涨幅:{stock[3]}%")
        
        # 显示A股统计详情
        result = session.execute(text("""
            SELECT metric_name, metric_value, metric_type
            FROM a_stock_statistics 
            WHERE record_id = :record_id 
            LIMIT 10
        """), {'record_id': record_id})
        
        a_stats = result.fetchall()
        if a_stats:
            print(f"\nA股统计数据详情:")
            for stat in a_stats:
                print(f"  {stat[2]}.{stat[0]}: {stat[1]}")
                
    except Exception as e:
        session.rollback()
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

def main():
    print("数据保存修复测试工具")
    print("=" * 50)
    test_existing_data_reprocess()

if __name__ == "__main__":
    main()