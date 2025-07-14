import asyncio
import json
import pandas as pd
from playwright.async_api import async_playwright
from datetime import datetime
import time

class StockSectorCrawler:
    def __init__(self):
        self.base_url = "http://push2.eastmoney.com/api/qt/clist/get"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://quote.eastmoney.com/',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
        
    async def get_sector_data(self, page):
        """获取板块资金流向数据"""
        try:
            # 构建请求参数
            params = {
                'cb': 'jQuery112404953340710317346_1640000000000',
                'pn': '1',
                'pz': '500',  # 获取更多数据
                'po': '1',
                'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2',
                'invt': '2',
                'wbp2u': '|0|0|0|web',
                'fid': 'f62',  # 按主力净流入排序
                'fs': 'm:90 t:2',  # 板块数据
                'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124'
            }
            
            # 构建完整URL
            url = f"{self.base_url}?"
            for key, value in params.items():
                url += f"{key}={value}&"
            url = url.rstrip('&')
            
            print(f"正在请求数据: {url}")
            
            # 发送请求
            response = await page.goto(url, wait_until='networkidle')
            content = await page.content()
            
            # 解析JSONP响应
            if 'jQuery' in content:
                # 提取JSON数据
                start_idx = content.find('(') + 1
                end_idx = content.rfind(')')
                json_str = content[start_idx:end_idx]
                
                data = json.loads(json_str)
                return data.get('data', {}).get('diff', [])
            else:
                print("响应格式异常")
                return []
                
        except Exception as e:
            print(f"获取数据失败: {e}")
            return []
    
    async def parse_sector_data(self, raw_data):
        """解析板块数据"""
        sectors = []
        
        for item in raw_data:
            try:
                sector_info = {
                    'code': item.get('f12', ''),  # 板块代码
                    'name': item.get('f14', ''),  # 板块名称
                    'price': item.get('f2', 0),   # 最新价
                    'change_pct': item.get('f3', 0),  # 涨跌幅
                    'main_net_inflow': item.get('f62', 0),  # 主力净流入
                    'main_net_inflow_pct': item.get('f184', 0),  # 主力净流入占比
                    'super_large_net_inflow': item.get('f66', 0),  # 超大单净流入
                    'large_net_inflow': item.get('f69', 0),  # 大单净流入
                    'medium_net_inflow': item.get('f72', 0),  # 中单净流入
                    'small_net_inflow': item.get('f75', 0),  # 小单净流入
                    'super_large_inflow': item.get('f78', 0),  # 超大单流入
                    'super_large_outflow': item.get('f79', 0),  # 超大单流出
                    'large_inflow': item.get('f81', 0),  # 大单流入
                    'large_outflow': item.get('f82', 0),  # 大单流出
                    'medium_inflow': item.get('f84', 0),  # 中单流入
                    'medium_outflow': item.get('f85', 0),  # 中单流出
                    'small_inflow': item.get('f87', 0),  # 小单流入
                    'small_outflow': item.get('f88', 0),  # 小单流出
                    'total_turnover': item.get('f124', 0),  # 成交额
                }
                
                # 转换数值（东财的数据需要除以10000转换为万元）
                money_fields = ['main_net_inflow', 'super_large_net_inflow', 'large_net_inflow', 
                               'medium_net_inflow', 'small_net_inflow', 'super_large_inflow',
                               'super_large_outflow', 'large_inflow', 'large_outflow',
                               'medium_inflow', 'medium_outflow', 'small_inflow', 'small_outflow']
                
                for field in money_fields:
                    if sector_info[field]:
                        sector_info[field] = sector_info[field] / 10000  # 转换为万元
                
                sectors.append(sector_info)
                
            except Exception as e:
                print(f"解析板块数据失败: {e}")
                continue
        
        return sectors
    
    def analyze_sectors(self, sectors):
        """分析板块数据，找出净流入最多和净流出最多的板块"""
        if not sectors:
            return None
        
        # 转换为DataFrame便于分析
        df = pd.DataFrame(sectors)
        
        # 按主力净流入排序
        df_sorted = df.sort_values('main_net_inflow', ascending=False)
        
        # 净流入最多的板块
        max_inflow_sector = df_sorted.iloc[0]
        
        # 净流出最多的板块（净流入最少/负值最大）
        max_outflow_sector = df_sorted.iloc[-1]
        
        result = {
            'max_inflow': {
                'name': max_inflow_sector['name'],
                'code': max_inflow_sector['code'],
                'net_inflow': max_inflow_sector['main_net_inflow'],
                'change_pct': max_inflow_sector['change_pct'],
                'price': max_inflow_sector['price']
            },
            'max_outflow': {
                'name': max_outflow_sector['name'],
                'code': max_outflow_sector['code'],
                'net_outflow': abs(max_outflow_sector['main_net_inflow']),  # 转为正值表示流出
                'change_pct': max_outflow_sector['change_pct'],
                'price': max_outflow_sector['price']
            },
            'total_sectors': len(sectors),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return result
    
    async def crawl_sector_money_flow(self):
        """主要爬取逻辑"""
        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(
                headless=True,  # 无头模式
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                # 创建页面
                page = await browser.new_page()
                await page.set_extra_http_headers(self.headers)
                
                # 设置视口大小
                await page.set_viewport_size({"width": 1920, "height": 1080})
                
                print("开始爬取A股板块资金流向数据...")
                
                # 获取原始数据
                raw_data = await self.get_sector_data(page)
                
                if not raw_data:
                    print("未获取到数据")
                    return None
                
                print(f"获取到 {len(raw_data)} 个板块数据")
                
                # 解析数据
                sectors = await self.parse_sector_data(raw_data)
                
                if not sectors:
                    print("数据解析失败")
                    return None
                
                # 分析数据
                analysis_result = self.analyze_sectors(sectors)
                
                return analysis_result, sectors
                
            except Exception as e:
                print(f"爬取过程中发生错误: {e}")
                return None
            finally:
                await browser.close()

# 使用示例
async def main():
    crawler = StockSectorCrawler()
    
    try:
        result = await crawler.crawl_sector_money_flow()
        
        if result:
            analysis, all_sectors = result
            
            print("\n" + "="*50)
            print("A股板块资金流向分析结果")
            print("="*50)
            
            print(f"\n📈 净流入最多的板块:")
            print(f"   板块名称: {analysis['max_inflow']['name']}")
            print(f"   板块代码: {analysis['max_inflow']['code']}")
            print(f"   净流入金额: {analysis['max_inflow']['net_inflow']:.2f} 万元")
            print(f"   涨跌幅: {analysis['max_inflow']['change_pct']:.2f}%")
            print(f"   最新价: {analysis['max_inflow']['price']:.2f}")
            
            print(f"\n📉 净流出最多的板块:")
            print(f"   板块名称: {analysis['max_outflow']['name']}")
            print(f"   板块代码: {analysis['max_outflow']['code']}")
            print(f"   净流出金额: {analysis['max_outflow']['net_outflow']:.2f} 万元")
            print(f"   涨跌幅: {analysis['max_outflow']['change_pct']:.2f}%")
            print(f"   最新价: {analysis['max_outflow']['price']:.2f}")
            
            print(f"\n📊 统计信息:")
            print(f"   总板块数: {analysis['total_sectors']}")
            print(f"   更新时间: {analysis['timestamp']}")
            
            # 可选：保存详细数据到CSV
            df = pd.DataFrame(all_sectors)
            df.to_csv('sector_money_flow.csv', index=False, encoding='utf-8-sig')
            print(f"\n💾 详细数据已保存到 sector_money_flow.csv")
            
        else:
            print("爬取失败，请检查网络连接或稍后重试")
            
    except Exception as e:
        print(f"程序执行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())