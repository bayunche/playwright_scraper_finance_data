"""
数据库连接和数据保存模块
用于/scrape接口的数据持久化
"""
import json
import re
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, host='localhost', port=3306, user='root', password='', database='financial_scraper'):
        """
        初始化数据库连接
        
        Args:
            host: 数据库主机
            port: 数据库端口  
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        
        # 构建数据库URL
        self.database_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        
        # 创建数据库引擎
        self.engine = None
        self.SessionLocal = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库连接"""
        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False  # 设为True可以看到SQL语句
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info("数据库连接初始化成功")
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            raise
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def save_scrape_data(self, scrape_time: datetime, request_time: str, data: Dict[str, Any]) -> Optional[int]:
        """
        保存爬取数据到数据库
        
        Args:
            scrape_time: 实际爬取时间
            request_time: 请求参数中的时间
            data: 爬取到的数据
            
        Returns:
            record_id: 主记录ID，失败返回None
        """
        start_time = datetime.now()
        session = self.SessionLocal()
        record_id = None
        
        try:
            # 分析数据统计信息
            total_sources = len(data)
            successful_sources = sum(1 for v in data.values() if not self._is_error_data(v))
            failed_sources = total_sources - successful_sources
            
            # 1. 插入主记录
            insert_main_sql = text("""
                INSERT INTO scrape_records 
                (scrape_time, request_time, total_data_sources, successful_sources, failed_sources, processing_duration_ms)
                VALUES (:scrape_time, :request_time, :total_sources, :successful_sources, :failed_sources, :duration)
            """)
            
            processing_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            
            result = session.execute(insert_main_sql, {
                'scrape_time': scrape_time,
                'request_time': request_time,
                'total_sources': total_sources,
                'successful_sources': successful_sources,
                'failed_sources': failed_sources,
                'duration': processing_duration
            })
            
            record_id = result.lastrowid
            logger.info(f"主记录插入成功，ID: {record_id}")
            
            # 2. 保存全球宏观指标数据
            self._save_global_macro_data(session, record_id, data)
            
            # 3. 保存美股涨幅榜数据  
            self._save_us_gainers_data(session, record_id, data)
            
            # 4. 保存A股统计数据
            self._save_a_stock_stats_data(session, record_id, data)
            
            # 5. 保存市场成交额数据
            self._save_market_turnover_data(session, record_id, data)
            
            # 6. 保存原始数据备份
            self._save_raw_data_backup(session, record_id, data)
            
            # 提交事务
            session.commit()
            logger.info(f"数据保存成功，记录ID: {record_id}")
            
            return record_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"数据保存失败: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
        finally:
            session.close()
    
    def _is_error_data(self, data: Any) -> bool:
        """判断数据是否为错误数据"""
        if isinstance(data, dict):
            return 'error' in data
        return False
    
    def _safe_decimal(self, value: str, default: Optional[Decimal] = None) -> Optional[Decimal]:
        """安全转换为Decimal类型"""
        if not value:
            return default
        try:
            # 移除非数字字符（保留小数点和负号）
            clean_value = re.sub(r'[^\d.-]', '', str(value))
            if clean_value:
                return Decimal(clean_value)
        except:
            pass
        return default
    
    def _safe_int(self, value: str, default: Optional[int] = None) -> Optional[int]:
        """安全转换为int类型"""
        if not value:
            return default
        try:
            clean_value = re.sub(r'[^\d-]', '', str(value))
            if clean_value:
                return int(clean_value)
        except:
            pass
        return default
    
    def _save_global_macro_data(self, session, record_id: int, data: Dict[str, Any]):
        """保存全球宏观指标数据"""
        # 全球宏观指标的key列表
        macro_keys = ['DXY', 'WTI', 'XAU_USD', 'USD_CNH']
        
        for key in macro_keys:
            if key in data:
                item_data = data[key]
                is_error = self._is_error_data(item_data)
                
                # 解析价格和涨跌幅
                price = None
                change_percent = None
                price_text = ""
                change_text = ""
                error_msg = None
                
                if not is_error:
                    price_text = item_data.get('price', '')
                    change_text = item_data.get('涨跌幅', '')
                    price = self._safe_decimal(price_text)
                    
                    # 解析涨跌幅百分比
                    if change_text:
                        percent_match = re.search(r'([+-]?\d+\.?\d*)%', change_text)
                        if percent_match:
                            change_percent = self._safe_decimal(percent_match.group(1))
                else:
                    error_msg = item_data.get('error', '')
                
                # 插入数据
                insert_sql = text("""
                    INSERT INTO global_macro_indicators 
                    (record_id, indicator_code, indicator_name, price, price_text, 
                     change_percent, change_percent_text, is_error, error_message)
                    VALUES (:record_id, :code, :name, :price, :price_text, 
                            :change_percent, :change_text, :is_error, :error_msg)
                """)
                
                session.execute(insert_sql, {
                    'record_id': record_id,
                    'code': key,
                    'name': self._get_indicator_name(key),
                    'price': price,
                    'price_text': price_text,
                    'change_percent': change_percent,
                    'change_text': change_text,
                    'is_error': is_error,
                    'error_msg': error_msg
                })
    
    def _save_us_gainers_data(self, session, record_id: int, data: Dict[str, Any]):
        """保存美股涨幅榜数据"""
        if 'US_stock_gainers' in data:
            gainers_data = data['US_stock_gainers']
            
            if self._is_error_data(gainers_data):
                # 保存错误信息
                insert_sql = text("""
                    INSERT INTO us_stock_gainers 
                    (record_id, stock_symbol, is_error, error_message, ranking_position)
                    VALUES (:record_id, 'ERROR', TRUE, :error_msg, 1)
                """)
                session.execute(insert_sql, {
                    'record_id': record_id,
                    'error_msg': gainers_data.get('error', '')
                })
            else:
                # 保存股票数据
                for i, (symbol, stock_data) in enumerate(gainers_data.items(), 1):
                    if isinstance(stock_data, dict):
                        insert_sql = text("""
                            INSERT INTO us_stock_gainers 
                            (record_id, stock_symbol, stock_name, current_price, 
                             price_change, change_percent, volume, ranking_position, is_error)
                            VALUES (:record_id, :symbol, :name, :price, 
                                    :price_change, :change_percent, :volume, :ranking, FALSE)
                        """)
                        
                        session.execute(insert_sql, {
                            'record_id': record_id,
                            'symbol': symbol,
                            'name': stock_data.get('name', ''),
                            'price': self._safe_decimal(stock_data.get('price')),
                            'price_change': self._safe_decimal(stock_data.get('change')),
                            'change_percent': self._safe_decimal(stock_data.get('change_percent')),
                            'volume': self._safe_int(stock_data.get('volume')),
                            'ranking': i
                        })
    
    def _save_a_stock_stats_data(self, session, record_id: int, data: Dict[str, Any]):
        """保存A股统计数据"""
        # A股相关的数据keys
        a_stock_keys = ['Astock_stats', 'stock_updown_summary']
        
        for key in a_stock_keys:
            if key in data:
                stats_data = data[key]
                is_error = self._is_error_data(stats_data)
                
                if is_error:
                    # 保存错误信息
                    insert_sql = text("""
                        INSERT INTO a_stock_statistics 
                        (record_id, metric_name, metric_type, is_error, error_message)
                        VALUES (:record_id, :metric_name, :metric_type, TRUE, :error_msg)
                    """)
                    session.execute(insert_sql, {
                        'record_id': record_id,
                        'metric_name': key,
                        'metric_type': 'error',
                        'error_msg': stats_data.get('error', '')
                    })
                else:
                    # 保存统计数据
                    if isinstance(stats_data, dict):
                        for metric_name, metric_value in stats_data.items():
                            insert_sql = text("""
                                INSERT INTO a_stock_statistics 
                                (record_id, metric_name, metric_value, metric_type, 
                                 additional_info, is_error)
                                VALUES (:record_id, :metric_name, :metric_value, :metric_type, 
                                        :additional_info, FALSE)
                            """)
                            
                            # 处理复杂数据结构
                            additional_info = None
                            if isinstance(metric_value, (dict, list)):
                                additional_info = json.dumps(metric_value, ensure_ascii=False)
                                metric_value = str(metric_value)
                            
                            session.execute(insert_sql, {
                                'record_id': record_id,
                                'metric_name': metric_name,
                                'metric_value': str(metric_value),
                                'metric_type': key,
                                'additional_info': additional_info
                            })
    
    def _save_market_turnover_data(self, session, record_id: int, data: Dict[str, Any]):
        """保存市场成交额数据"""
        if 'market_total_turnover' in data:
            turnover_data = data['market_total_turnover']
            
            if self._is_error_data(turnover_data):
                # 保存错误信息
                insert_sql = text("""
                    INSERT INTO market_turnover 
                    (record_id, market_type, is_error, error_message)
                    VALUES (:record_id, 'ERROR', TRUE, :error_msg)
                """)
                session.execute(insert_sql, {
                    'record_id': record_id,
                    'error_msg': turnover_data.get('error', '')
                })
            else:
                # 保存沪深市场数据
                for market_key, market_info in turnover_data.items():
                    market_type = 'SH' if '沪市' in market_key else 'SZ' if '深市' in market_key else 'OTHER'
                    
                    insert_sql = text("""
                        INSERT INTO market_turnover 
                        (record_id, market_type, market_name, turnover_text, is_error)
                        VALUES (:record_id, :market_type, :market_name, :turnover_text, FALSE)
                    """)
                    
                    session.execute(insert_sql, {
                        'record_id': record_id,
                        'market_type': market_type,
                        'market_name': market_key,
                        'turnover_text': str(market_info)
                    })
    
    def _save_raw_data_backup(self, session, record_id: int, data: Dict[str, Any]):
        """保存原始数据备份"""
        try:
            raw_json = json.dumps(data, ensure_ascii=False, indent=2)
            data_size = len(raw_json.encode('utf-8'))
            
            insert_sql = text("""
                INSERT INTO raw_data_backup 
                (record_id, data_source, raw_json, data_size)
                VALUES (:record_id, :data_source, :raw_json, :data_size)
            """)
            
            session.execute(insert_sql, {
                'record_id': record_id,
                'data_source': 'scrape_api_full',
                'raw_json': raw_json,
                'data_size': data_size
            })
            
        except Exception as e:
            logger.warning(f"原始数据备份保存失败: {e}")
    
    def _get_indicator_name(self, code: str) -> str:
        """获取指标中文名称"""
        name_map = {
            'DXY': '美元指数',
            'WTI': 'WTI原油',
            'XAU_USD': '黄金',
            'USD_CNH': '美元离岸人民币'
        }
        return name_map.get(code, code)
    
    def get_recent_records(self, limit: int = 10) -> List[Dict]:
        """获取最近的爬取记录"""
        session = self.SessionLocal()
        try:
            query_sql = text("""
                SELECT id, scrape_time, total_data_sources, successful_sources, 
                       failed_sources, processing_duration_ms, created_at
                FROM scrape_records 
                ORDER BY scrape_time DESC 
                LIMIT :limit
            """)
            
            result = session.execute(query_sql, {'limit': limit})
            records = []
            for row in result:
                records.append({
                    'id': row[0],
                    'scrape_time': row[1].isoformat() if row[1] else None,
                    'total_data_sources': row[2],
                    'successful_sources': row[3],
                    'failed_sources': row[4],
                    'processing_duration_ms': row[5],
                    'created_at': row[6].isoformat() if row[6] else None
                })
            return records
        except Exception as e:
            logger.error(f"查询最近记录失败: {e}")
            return []
        finally:
            session.close()

# 全局数据库管理器实例（使用环境变量配置）
import os

def get_database_manager():
    """获取数据库管理器实例"""
    return DatabaseManager(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_DATABASE', 'financial_scraper')
    )