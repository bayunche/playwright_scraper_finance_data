import asyncio
import logging
import sys # 导入sys模块
import traceback
import pandas as pd # 导入pandas
from datetime import datetime
import json
import re
from playwright.async_api import async_playwright, TimeoutError
from playwright.sync_api import sync_playwright # 导入sync_playwright
from tonghuashun_stats import scrape_today
# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SimpleSectorFlowScraper:
    """简化版美股板块资金流向爬取器（多源）"""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape_yahoo_sectors(self):
        """从Yahoo Finance爬取板块数据"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            try:
                print("正在访问Yahoo Finance板块页面...")
                await page.goto('https://finance.yahoo.com/sectors/', wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(8000)
                # 适配新版Yahoo Finance板块表格结构
                await page.wait_for_selector('table.yf-k3njn8', timeout=10000)
                sector_data = await page.evaluate('''
                    () => {
                        const data = [];
                        const table = document.querySelector('table.yf-k3njn8');
                        if (table) {
                            const rows = table.querySelectorAll('tbody tr');
                            rows.forEach(row => {
                                const cells = row.querySelectorAll('td');
                                if (cells.length === 3) {
                                    const name = cells[0].textContent.trim();
                                    const weightText = cells[1].textContent.trim();
                                    const ytdReturnText = cells[2].textContent.trim();
                                    // 提取百分比数值
                                    const weightMatch = weightText.match(/([+-]?\\d+\\.?\\d*)%/);
                                    const ytdReturnMatch = ytdReturnText.match(/([+-]?\\d+\\.?\\d*)%/);
                                    if (name && ytdReturnMatch) {
                                        data.push({
                                            name: name,
                                            percentage: parseFloat(ytdReturnMatch[1]),
                                            changeText: ytdReturnText,
                                            volumeText: weightMatch ? weightMatch[1] : '0'
                                        });
                                    }
                                }
                            });
                        }
                        return data;
                    }
                ''')
                print(f"从Yahoo Finance获取到 {len(sector_data)} 条原始数据")
                processed_data = []
                for item in sector_data:
                    # 这里volume用权重百分比，实际资金流量需结合市值等，暂用权重模拟
                    volume = float(item['volumeText'])
                    net_flow = abs(item['percentage']) * volume if volume else abs(item['percentage'])
                    processed_data.append({
                        'sector_name': item['name'],
                        'percentage': item['percentage'],
                        'net_flow': net_flow,
                        'volume': volume,
                        'flow_direction': 'inflow' if item['percentage'] > 0 else 'outflow',
                        'timestamp': datetime.now().isoformat()
                    })
                await browser.close()
                return processed_data
            except Exception as e:
                print(f"Yahoo Finance爬取失败: {e}")
                try:
                    await page.screenshot(path='yahoo_finance_debug.png')
                    print("已保存调试截图: yahoo_finance_debug.png")
                except:
                    pass
                await browser.close()
                return []

    async def scrape_marketwatch_sectors(self):
        """从MarketWatch爬取板块数据 - 备选数据源"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            try:
                print("正在访问MarketWatch板块页面...")
                await page.goto('https://www.marketwatch.com/investing/sectors', wait_until='networkidle')
                await page.wait_for_timeout(3000)
                # 由于页面可能被验证码拦截或结构变化，以下选择器可能无效
                # 增加异常处理和提示
                try:
                    await page.wait_for_selector('.table--primary, .data-table, table', timeout=10000)
                except Exception:
                    print("MarketWatch页面未找到预期的表格元素，可能被验证码拦截或页面结构已变更。")
                    await browser.close()
                    return []
                sector_data = await page.evaluate('''
                    () => {
                        const data = [];
                        const tableSelectors = [
                            '.table--primary',
                            '.data-table',
                            'table.table',
                            '.sector-table',
                            'table'
                        ];
                        let targetTable = null;
                        for (const selector of tableSelectors) {
                            targetTable = document.querySelector(selector);
                            if (targetTable) break;
                        }
                        if (targetTable) {
                            const rows = targetTable.querySelectorAll('tbody tr, tr');
                            rows.forEach(row => {
                                const cells = row.querySelectorAll('td');
                                if (cells.length >= 3) {
                                    const nameElem = cells[0].querySelector('a') || cells[0];
                                    let changeElem = null;
                                    for (let i = 1; i < cells.length; i++) {
                                        const cellText = cells[i].textContent;
                                        if (cellText.includes('%')) {
                                            changeElem = cells[i];
                                            break;
                                        }
                                    }
                                    if (nameElem && changeElem) {
                                        const name = nameElem.textContent.trim();
                                        const changeText = changeElem.textContent.trim();
                                        const changeMatch = changeText.match(/([+-]?\\d+\\.?\\d*)%/);
                                        if (changeMatch && name.length > 0) {
                                            const percentage = parseFloat(changeMatch[1]);
                                            data.push({
                                                name: name,
                                                percentage: percentage,
                                                changeText: changeText,
                                                volumeText: '0'
                                            });
                                        }
                                    }
                                }
                            });
                        }
                        return data;
                    }
                ''')
                print(f"从MarketWatch获取到 {len(sector_data)} 条原始数据")
                processed_data = []
                for item in sector_data:
                    processed_data.append({
                        'sector_name': item['name'],
                        'percentage': item['percentage'],
                        'net_flow': abs(item['percentage']),
                        'volume': 0,
                        'flow_direction': 'inflow' if item['percentage'] > 0 else 'outflow',
                        'timestamp': datetime.now().isoformat()
                    })
                await browser.close()
                return processed_data
            except Exception as e:
                print(f"MarketWatch爬取失败: {e}")
                await browser.close()
                return []

    async def scrape_finviz_sectors(self):
        """从Finviz爬取板块数据"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto('https://finviz.com/groups.ashx?g=sector&v=210&o=name', wait_until='networkidle')
                await page.wait_for_timeout(3000)
                await page.wait_for_selector('.groups-table', timeout=15000)
                sector_data = await page.evaluate('''
                    () => {
                        const rows = document.querySelectorAll('.groups-table tr');
                        const data = [];
                        for (let i = 1; i < rows.length; i++) {
                            const cells = rows[i].querySelectorAll('td');
                            if (cells.length >= 7) {
                                const name = cells[0].textContent.trim();
                                const changeText = cells[2].textContent.trim();
                                const volumeText = cells[6].textContent.trim();
                                const changeMatch = changeText.match(/([+-]?\\d+\\.?\\d*)%/);
                                if (changeMatch) {
                                    const percentage = parseFloat(changeMatch[1]);
                                    data.push({
                                        name: name,
                                        percentage: percentage,
                                        changeText: changeText,
                                        volumeText: volumeText
                                    });
                                }
                            }
                        }
                        return data;
                    }
                ''')
                processed_data = []
                for item in sector_data:
                    volume = self._parse_volume(item['volumeText'])
                    net_flow = abs(item['percentage']) * volume if volume else abs(item['percentage'])
                    processed_data.append({
                        'sector_name': item['name'],
                        'percentage': item['percentage'],
                        'net_flow': net_flow,
                        'volume': volume,
                        'flow_direction': 'inflow' if item['percentage'] > 0 else 'outflow',
                        'timestamp': datetime.now().isoformat()
                    })
                await browser.close()
                return processed_data
            except Exception as e:
                print(f"Finviz爬取失败: {e}")
                await browser.close()
                return []

    def _parse_volume(self, volume_text: str) -> float:
        """解析成交量字符串"""
        try:
            volume_text = volume_text.strip().replace(',', '').replace('$', '')
            multiplier = 1
            if volume_text.endswith('K'):
                multiplier = 1000
                volume_text = volume_text[:-1]
            elif volume_text.endswith('M'):
                multiplier = 1000000
                volume_text = volume_text[:-1]
            elif volume_text.endswith('B'):
                multiplier = 1000000000
                volume_text = volume_text[:-1]
            elif volume_text.endswith('T'):
                multiplier = 1000000000000
                volume_text = volume_text[:-1]
            return float(volume_text) * multiplier
        except:
            return 0.0

    def get_top_sectors(self, sector_data: list, top_n: int = 5):
        """获取资金流入/流出最多的板块"""
        if not sector_data:
            return {'top_inflow': [], 'top_outflow': []}
        inflow_sectors = [s for s in sector_data if s['flow_direction'] == 'inflow']
        outflow_sectors = [s for s in sector_data if s['flow_direction'] == 'outflow']
        inflow_sectors.sort(key=lambda x: x['net_flow'], reverse=True)
        outflow_sectors.sort(key=lambda x: x['net_flow'], reverse=True)
        return {
            'top_inflow': inflow_sectors[:top_n],
            'top_outflow': outflow_sectors[:top_n]
        }

    def print_results(self, results: dict):
        """打印结果"""
        print("=== 美股板块资金流向分析 ===")
        print(f"数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n=== 资金流入最多的板块 ===")
        for i, sector in enumerate(results['top_inflow'], 1):
            print(f"{i}. {sector['sector_name']}: {sector['net_flow']:.2f} ({sector['percentage']:.2f}%)")
        print("\n=== 资金流出最多的板块 ===")
        for i, sector in enumerate(results['top_outflow'], 1):
            print(f"{i}. {sector['sector_name']}: {sector['net_flow']:.2f} ({sector['percentage']:.2f}%)")

    def save_to_json(self, data: dict, filename: str = None):
        """保存数据到JSON文件"""
        if filename is None:
            filename = f"sector_flows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到: {filename}")

    def to_dataframe(self, sector_data: list) -> pd.DataFrame:
        """转换为DataFrame"""
        return pd.DataFrame(sector_data)

async def scrape_dow_jones(page):
    """爬取道琼斯指数数据"""
    try:
        await page.goto("https://cn.investing.com/indices/us-30", timeout=60000)
        await page.wait_for_selector('[data-test="instrument-header-details"]', timeout=10000)
        
        price = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-last"]').inner_text()
        change = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change"]').inner_text()
        change_percent = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]').inner_text()
        logging.info(f"道琼斯指数数据: 价格={price}, 涨跌={change}, 涨跌幅={change_percent}")
        return {
            'price': price.strip(),
            'change': change.strip(),
            'change_percent': change_percent.strip()
        }
    except Exception as e:
        logging.error(f"爬取道琼斯指数时出错: {e}")
        return {'error': str(e)}

async def scrape_nasdaq(page):
    """爬取纳斯达克指数数据"""
    try:
        await page.goto("https://cn.investing.com/indices/nasdaq-composite", timeout=60000)
        await page.wait_for_selector('[data-test="instrument-header-details"]', timeout=10000)
        
        price = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-last"]').inner_text()
        change = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change"]').inner_text()
        change_percent = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]').inner_text()
        
        logging.info(f"纳斯达克指数数据: 价格={price}, 涨跌={change}, 涨跌幅={change_percent}")
        return {
            'price': price.strip(),
            'change': change.strip(),
            'change_percent': change_percent.strip()
        }
    except Exception as e:
        logging.error(f"爬取纳斯达克指数时出错: {e}")
        return {'error': str(e)}

async def scrape_sp500(page):
    """爬取标普500指数数据"""
    try:
        await page.goto("https://cn.investing.com/indices/us-spx-500", timeout=60000)
        await page.wait_for_selector('[data-test="instrument-header-details"]', timeout=10000)
        
        price = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-last"]').inner_text()
        change = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change"]').inner_text()
        change_percent = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]').inner_text()
        
        logging.info(f"标普500指数数据: 价格={price}, 涨跌={change}, 涨跌幅={change_percent}")
        return {
            'price': price.strip(),
            'change': change.strip(),
            'change_percent': change_percent.strip()
        }
    except Exception as e:
        logging.error(f"爬取标普500指数时出错: {e}")
        return {'error': str(e)}


# ========== Yahoo Finance 板块资金流向爬虫及工具函数 BEGIN ==========

async def scrape_yahoo_sectors(headless: bool = True):
    """从Yahoo Finance爬取板块资金流向数据"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto('https://finance.yahoo.com/sectors/', wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)
            await page.wait_for_selector('[data-testid="sector-table"]', timeout=15000)
            sector_data = await page.evaluate('''
                () => {
                    const rows = document.querySelectorAll('[data-testid="sector-table"] tbody tr');
                    const data = [];
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 4) {
                            const nameElem = cells[0].querySelector('a');
                            const changeElem = cells[2];
                            const volumeElem = cells[3];
                            if (nameElem && changeElem) {
                                const name = nameElem.textContent.trim();
                                const changeText = changeElem.textContent.trim();
                                const volumeText = volumeElem ? volumeElem.textContent.trim() : '0';
                                const changeMatch = changeText.match(/([+-]?\\d+\\.?\\d*)%/);
                                if (changeMatch) {
                                    const percentage = parseFloat(changeMatch[1]);
                                    data.push({
                                        name: name,
                                        percentage: percentage,
                                        changeText: changeText,
                                        volumeText: volumeText
                                    });
                                }
                            }
                        }
                    });
                    return data;
                }
            ''')
            processed_data = []
            for item in sector_data:
                volume = _parse_volume(item['volumeText'])
                net_flow = abs(item['percentage']) * volume if volume else abs(item['percentage'])
                processed_data.append({
                    'sector_name': item['name'],
                    'percentage': item['percentage'],
                    'net_flow': net_flow,
                    'volume': volume,
                    'flow_direction': 'inflow' if item['percentage'] > 0 else 'outflow',
                    'timestamp': datetime.now().isoformat()
                })
            await browser.close()
            return processed_data
        except Exception as e:
            print(f"Yahoo Finance爬取失败: {e}")
            await browser.close()
            return []

def _parse_volume(volume_text: str) -> float:
    """解析成交量字符串"""
    try:
        volume_text = volume_text.strip().replace(',', '').replace('$', '')
        multiplier = 1
        if volume_text.endswith('K'):
            multiplier = 1000
            volume_text = volume_text[:-1]
        elif volume_text.endswith('M'):
            multiplier = 1000000
            volume_text = volume_text[:-1]
        elif volume_text.endswith('B'):
            multiplier = 1000000000
            volume_text = volume_text[:-1]
        elif volume_text.endswith('T'):
            multiplier = 1000000000000
            volume_text = volume_text[:-1]
        return float(volume_text) * multiplier
    except:
        return 0.0

def get_top_sectors(sector_data: list, top_n: int = 5):
    """获取资金流入/流出最多的板块"""
    if not sector_data:
        return {'top_inflow': [], 'top_outflow': []}
    inflow_sectors = [s for s in sector_data if s['flow_direction'] == 'inflow']
    outflow_sectors = [s for s in sector_data if s['flow_direction'] == 'outflow']
    inflow_sectors.sort(key=lambda x: x['net_flow'], reverse=True)
    outflow_sectors.sort(key=lambda x: x['net_flow'], reverse=True)
    return {
        'top_inflow': inflow_sectors[:top_n],
        'top_outflow': outflow_sectors[:top_n]
    }

def print_sector_flow_results(results: dict):
    """打印板块资金流向结果"""
    print("=== 美股板块资金流向分析 ===")
    print(f"数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n=== 资金流入最多的板块 ===")
    for i, sector in enumerate(results['top_inflow'], 1):
        print(f"{i}. {sector['sector_name']}: {sector['net_flow']:.2f} ({sector['percentage']:.2f}%)")
    print("\n=== 资金流出最多的板块 ===")
    for i, sector in enumerate(results['top_outflow'], 1):
        print(f"{i}. {sector['sector_name']}: {sector['net_flow']:.2f} ({sector['percentage']:.2f}%)")

def save_sector_flow_to_json(data: dict, filename: str = None):
    """保存板块资金流向数据到JSON文件"""
    if filename is None:
        filename = f"sector_flows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filename}")

def sector_flow_to_dataframe(sector_data: list) -> pd.DataFrame:
    """转换为DataFrame"""
    return pd.DataFrame(sector_data)

# ========== Yahoo Finance 板块资金流向爬虫及工具函数 END ==========


async def get_daily_market_sectors():
    """
    使用 Playwright 爬取美股每日涨跌幅前三的板块。
    数据源为 Finviz。
    
    Scrapes the top 3 daily gaining and losing US stock market sectors using Playwright.
    Data source is Finviz.
    """
    url = "https://finviz.com/groups.ashx?g=sector&v=111"
    logging.info("--- 正在抓取美股板块数据... (Scraping US Market Sectors...) ---")
    
    sectors_data = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # 隐藏爬虫指纹
            # 移除手动设置User-Agent和viewport_size，由stealth_async处理
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # 添加用户提供的init_script
            init_script = """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
                window.chrome = {
                    runtime: {},
                    // 添加其他 Chrome 对象属性
                }
            """
            await page.add_init_script(script=init_script)
            
            await page.goto(url, timeout=150000) # 增加导航超时时间到150秒
            await page.wait_for_load_state('domcontentloaded') # 等待DOM加载完成
            await asyncio.sleep(15) # 增加额外等待时间，确保数据加载
            rows_locator = page.locator(".groups_table tr.styled-row")
            
            for i in range(await rows_locator.count()):
                row = rows_locator.nth(i)
                sector_name_element = row.locator("td:nth-child(2) a")
                daily_change_element = row.locator("td:nth-child(10) span")
                logging.info(f"板块: {await sector_name_element.inner_html()}, 涨跌幅: {await daily_change_element.inner_html()}")

                if await sector_name_element.count() > 0 and await daily_change_element.count() > 0:
                    sector_name = await sector_name_element.inner_text()
                    change_str = await daily_change_element.inner_text()
                    
                    
                    try:
                        change_pct = float(change_str.strip('%'))
                        sectors_data.append({"板块 (Sector)": sector_name, "日涨跌幅 (Daily Change)": change_pct})
                    except (ValueError, TypeError):
                        continue
            await browser.close()
    except Exception as e:
        logging.error(f"❌ 美股板块数据抓取失败 (Failed to scrape sector data): {e}")
        return

    if not sectors_data:
        logging.warning("⚠️ 未能成功获取或解析美股板块数据。(Could not retrieve or parse sector data.)")
        return

    logging.info("✅ 美股板块数据抓取完成 (Sector data scraping complete)")
    
    df = pd.DataFrame(sectors_data)
    top_gainers = df.sort_values(by="日涨跌幅 (Daily Change)", ascending=False).head(3)
    top_losers = df.sort_values(by="日涨跌幅 (Daily Change)", ascending=True).head(3)

    output = "\n" + "="*50 + "\n"
    output += f"美股市场每日板块表现 (Daily US Market Sector Performance)\n"
    output += "="*50 + "\n"
    output += "\n--- 每日涨幅前三板块 (Top 3 Daily Gainers) ---\n"
    output += top_gainers.to_string(index=False) + "\n"
    output += "\n--- 每日跌幅前三板块 (Top 3 Daily Losers) ---\n"
    output += top_losers.to_string(index=False) + "\n"
    logging.info(output)
    return {"top_gainers": top_gainers.to_dict('records'), "top_losers": top_losers.to_dict('records')}


async def get_crypto_data():
    """
    使用 Playwright 爬取主流加密货币的价格、涨跌额和涨跌幅。
    数据源为 Yahoo Finance。

    Scrapes price, change value, and change percentage for major cryptocurrencies using Playwright.
    Data source is Yahoo Finance.
    """
    crypto_map = {
        "BTC-USD/": "比特币 (Bitcoin)",
        "ETH-USD/": "以太坊 (Ethereum)",
        "USDT-USD/": "泰达币 (USDT)"
    }
    
    logging.info("\n--- 正在抓取加密货币数据... (Scraping Cryptocurrency Data...) ---")
    
    crypto_results = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False,) # 可以设置为True，如果不需要显示浏览器
            page = await browser.new_page()
            # 隐藏爬虫指纹
            # 移除手动设置User-Agent和viewport_size，由stealth_async处理
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            await page.set_viewport_size({"width": 1920, "height": 1080})
            

            # 添加用户提供的init_script
            init_script = """
             Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
             Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
             Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
             Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4] });
             window.chrome = { runtime: {} };
            """
            await page.add_init_script(script=init_script)
            
            for ticker, name in crypto_map.items():
                url = f"https://finance.yahoo.com/quote/{ticker}"
                try:
                    await page.goto(url, timeout=120000, wait_until='domcontentloaded') # 增加导航超时时间到120秒
                    await asyncio.sleep(10) # 增加额外等待时间，确保数据加载
                    
                    # await page.wait_for_selector('span[data-testid="qsp-price"', timeout=60000) # 使用更具体的选择器并增加超时时间
                    # await page.wait_for_timeout(60000) # 等待60秒以确保数据加载
                    price = await page.locator('span[data-testid="qsp-price"]').inner_text()
                    change_val = await page.locator('span[data-testid="qsp-price-change"]').inner_text()
                    change_pct_text = await page.locator('span[data-testid="qsp-price-change-percent"]').inner_text()
                    change_pct = change_pct_text.strip("()")

                    crypto_results.append({
                        "名称 (Name)": name,
                        "价格 (Price)": f"${price}",
                        "24h涨跌值 (Change)": change_val,
                        "24h涨跌幅 (%)": change_pct
                    })
                except Exception as e:
                    logging.error(f"❌ 抓取 {name} ({ticker}) 数据失败 (Failed to scrape {name}): {e}")
                    continue
            await browser.close()
    except Exception as e:
        logging.error(f"❌ 加密货币数据抓取失败 (Failed to scrape crypto data): {e}")
        return

    if not crypto_results:
        logging.warning("⚠️ 未能成功获取或解析加密货币数据。(Could not retrieve or parse crypto data.)")
        return

    logging.info("✅ 加密货币数据抓取完成 (Cryptocurrency data scraping complete)")
    
    df_crypto = pd.DataFrame(crypto_results)
    output = "\n" + "="*50 + "\n"
    output += "主流加密货币实时表现 (Major Cryptocurrency Performance)\n"
    output += "="*50 + "\n"
    output += df_crypto.to_string(index=False) + "\n"
    logging.info(output)
    return df_crypto.to_dict('records')


async def remove_eastmoney_mask(page):
    """移除东方财富网页面的遮罩层"""
    try:
        # 检查遮罩层是否存在
        mask = await page.query_selector('div[style*="position: fixed"][style*="z-index: 99998"]')
        if mask:
            # 遮罩存在时，等待并点击关闭按钮
            close_btn = await page.query_selector('img[src*="ic_close.png"]')
            if close_btn:
                await close_btn.click()
                await asyncio.sleep(1)  # 等待遮罩消失
                logging.info("已移除遮罩层")
        else:
            logging.info("页面无遮罩层，继续处理")
    except Exception as e:
        logging.info(f"处理遮罩层时出现异常: {str(e)}")

async def scrape_financial_data(debug=False):
    """
    异步爬取多个财经网站的关键金融数据。
    整合了 Investing.com, 东方财富, 同花顺, 新浪财经的数据源。
    具有独立的异常处理机制，增强了程序的鲁棒性。
    
    Args:
        debug: 是否开启调试模式，开启后会显示浏览器界面，便于调试
    """
    results = {}
    logging.info("开始执行金融数据爬取任务...")

    async with async_playwright() as p:
        # 启动浏览器并设置context
        context = await p.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=not debug,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
        )
        
        
        page = await context.new_page()
        if debug:
            logging.info("调试模式已开启，浏览器界面将会显示")

        # 1. Investing.com - 全球宏观指标
        logging.info("正在从 Investing.com 爬取全球宏观指标...")
        investing_map = {
            "DXY": "https://www.investing.com/indices/usdollar",
            "WTI": "https://www.investing.com/commodities/crude-oil",
            "XAU_USD": "https://www.investing.com/currencies/xau-usd",
            "USD_CNH": "https://www.investing.com/currencies/usd-cnh",
        }
        for name, url in investing_map.items():
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_selector('[data-test="instrument-header-details"] [data-test="instrument-price-last"]', timeout=10000)
                price = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-last"]').inner_text()
                change_pct = await page.locator('[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]').inner_text()
                results[name] = {"price": price, "涨跌幅": change_pct}
                logging.info(f"成功获取 {name}: {results[name]}")
            except TimeoutError:
                logging.error(f"访问 {url} 超时或找不到元素。")
                results[name] = {"error": "Timeout or element not found"}
            except Exception as e:
                logging.error(f"爬取 {name} ({url}) 时发生错误: {e}")
                results[name] = {"error": str(e)}
        # 2. Yahoo Finance - 美股涨幅前五 (推荐使用，结构更稳定)
        logging.info("正在从 Yahoo Finance 爬取美股涨幅前五...")
        us_gainers_url = "https://finance.yahoo.com/markets/stocks/gainers/"
        try:
            await page.goto(us_gainers_url, timeout=60000)
            await page.wait_for_selector('table tbody tr', timeout=15000)
            await asyncio.sleep(3)  # 额外等待数据加载
            
            # 获取前5行数据
            top_gainers = []
            for i in range(5):
                try:
                    row_selector = f'table tbody tr:nth-child({i+1})'
                    symbol = await page.locator(f'{row_selector} td:nth-child(1)').inner_text()
                    name = await page.locator(f'{row_selector} td:nth-child(2)').inner_text()
                    
                    # 从fin-streamer元素的data-value属性获取价格
                    price_element = page.locator(f'{row_selector} td:nth-child(4) fin-streamer[data-field="regularMarketPrice"]')
                    price = await price_element.get_attribute('data-value') or 'N/A'
                    
                    # 其他字段
                    symbol = await page.locator(f'{row_selector} td:nth-child(1)').inner_text()
                    name = await page.locator(f'{row_selector} td:nth-child(2)').inner_text()
                    change = await page.locator(f'{row_selector} td:nth-child(5)').inner_text()
                    change_pct = await page.locator(f'{row_selector} td:nth-child(6)').inner_text()
                    volume = await page.locator(f'{row_selector} td:nth-child(7)').inner_text()
                    
                    top_gainers.append({
                        "排名": i + 1,
                        "股票代码": symbol.strip(),
                        "股票名称": name.strip(),
                        "价格": price.strip(),
                        "涨幅（点）": change.strip(),
                        "涨幅百分比": change_pct.strip(),
                        "成交额": volume.strip()
                    })
                except Exception as e:
                    logging.error(f"获取第 {i+1} 个涨幅股票时出错: {e}")
                    top_gainers.append({
                        "rank": i + 1,
                        "error": str(e)
                    })
            results["美股涨幅前五"] = top_gainers
            logging.info(f"成功获取美股涨幅前五: {len([g for g in top_gainers if 'error' not in g])} 只股票")
        except TimeoutError:
            logging.error("等待Yahoo Finance表格加载超时")
            results["US_TOP_GAINERS"] = {"error": "表格加载超时"}
        except Exception as e:
            logging.error(f"爬取Yahoo Finance涨幅榜时发生错误: {e}")
            results["US_TOP_GAINERS"] = {"error": str(e)}
        
        logging.info("Yahoo Finance爬取完成")

        # 集成新版 Yahoo Finance 板块资金流向（多源）
        logging.info("正在从 Yahoo Finance/MarketWatch/Finviz 爬取板块资金流向数据（新版）...")
        try:
            sector_scraper = SimpleSectorFlowScraper(headless=True)
            all_data = []
            data_sources = [
                ("Yahoo Finance", sector_scraper.scrape_yahoo_sectors),
                ("MarketWatch", sector_scraper.scrape_marketwatch_sectors),
                ("Finviz", sector_scraper.scrape_finviz_sectors)
            ]
            for source_name, scrape_func in data_sources:
                logging.info(f"开始爬取{source_name}板块数据...")
                try:
                    data = await scrape_func()
                    if data:
                        logging.info(f"成功获取{source_name}板块数据: {len(data)}条")
                        all_data.extend(data)
                    else:
                        logging.warning(f"{source_name}未获取到数据")
                except Exception as e:
                    logging.error(f"{source_name}爬取出错: {e}")
            if all_data:
                # 去重处理（基于板块名称）
                unique_sectors = {}
                for item in all_data:
                    sector_name = item['sector_name']
                    if sector_name not in unique_sectors:
                        unique_sectors[sector_name] = item
                    else:
                        existing = unique_sectors[sector_name]
                        if item['volume'] > existing['volume']:
                            unique_sectors[sector_name] = item
                final_data = list(unique_sectors.values())
                top_sectors = sector_scraper.get_top_sectors(final_data)
                results["yahoo_sector_money_flow"] = {
                    "raw_data": final_data,
                    "analysis": top_sectors,
                    "data_sources_used": len([d for d in data_sources if d[1] in [sector_scraper.scrape_yahoo_sectors, sector_scraper.scrape_marketwatch_sectors, sector_scraper.scrape_finviz_sectors]])
                }
                logging.info(f"成功获取美股板块资金流向（多源）: {len(final_data)}条")
            else:
                results["yahoo_sector_money_flow"] = {"error": "未能获取到任何板块资金流向数据"}
        except Exception as e:
            logging.error(f"爬取美股板块资金流向失败: {e}")
            results["yahoo_sector_money_flow"] = {"error": str(e)}

        logging.info("正在爬取美股三大指数")
        results["道琼斯指数数据"] = await scrape_dow_jones(page)
        results["纳斯达克指数数据"] = await scrape_nasdaq(page)
        results["标普500指数数据"] = await scrape_sp500(page)
        logging.info("美股三大指数爬取完成")
       
        # 新增：美股每日板块数据
        logging.info("正在爬取美股每日板块数据...")
        sector_data = await get_daily_market_sectors()
        if sector_data:
            results["US_MARKET_SECTORS"] = sector_data
        else:
            results["US_MARKET_SECTORS"] = {"error": "Failed to get sector data"}
        
        # 新增：加密货币数据
        logging.info("正在爬取加密货币数据...")
        crypto_data = await get_crypto_data()
        if crypto_data:
            results["CRYPTOCURRENCY_DATA"] = crypto_data
        else:
            results["CRYPTOCURRENCY_DATA"] = {"error": "Failed to get crypto data"}


        # 2. 东方财富网 - A股核心数据
        logging.info("正在从东方财富网爬取A股市场数据...")
        # 2.1 A股三大指数
        eastmoney_indices = {
            "shanghai_index": ("上证指数", "https://quote.eastmoney.com/zs000001.html"),
            "shenzhen_index": ("深证成指", "https://quote.eastmoney.com/zs399001.html"),
            "gem_index": ("创业板指", "https://quote.eastmoney.com/zs399006.html"),
        }

        for key, (name, url) in eastmoney_indices.items():
            try:
                # 设置东方财富特定headers
                eastmoney_headers = {
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                    "cache-control": "no-cache",
                    "connection": "keep-alive",
                    "cookie": "HAList=ty-1-000001-%u4E0A%u8BC1%u6307%u6570%2Cty-0-399006-%u521B%u4E1A%u677F%u6307%2Cty-114-m2601-%u8C46%u7C952601; fullscreengg=1; fullscreengg2=1; st_si=97797926086084; st_asi=delete; qgqp_b_id=cfe11e83f6b139db1c01f4403a1feebe; st_pvi=70126782567146; st_sp=2025-06-17%2021%3A02%3A44; st_inirUrl=https%3A%2F%2Fcn.bing.com%2F; st_sn=13; st_psi=20250629235208149-113200301324-2171774889",
                    "pragma": "no-cache",
                    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "script",
                    "sec-fetch-mode": "no-cors",
                    "sec-fetch-site": "same-site",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
                }

                await page.goto(url, timeout=60000)
                await remove_eastmoney_mask(page)
                await page.set_extra_http_headers(eastmoney_headers)
                # await page.wait_for_load_state('networkidle')  # 等待页面加载完成
                await asyncio.sleep(3)  # 等待额外的时间以确保数据加载
                # 等待价格和涨跌幅数据加载
                await page.wait_for_selector('.zxj, .zd', timeout=10000)

                # 获取价格、涨跌值和涨跌幅
                price = await page.locator('.zxj span span[class^="price_"]').inner_text()
                zd_spans = await page.locator('.zd span span[class^="price_"]').all()
                change = await zd_spans[0].inner_text()
                change_pct = await zd_spans[1].inner_text()
                
                results[key] = {
                    "price": price.strip(),
                    "change": change.strip(),
                    "change_pct": change_pct.strip()
                }
                results[key] = {"price": price, "change_pct": change_pct}
                logging.info(f"成功获取 {name}: {results[key]}")
            except Exception as e:
                logging.error(f"爬取 {name} ({url}) 时发生错误: {e}")
                results[key] = {"error": str(e)}

        # 2.2 板块动态 (涨跌幅 & 资金流入)
        try:
            logging.info("正在爬取行业板块动态...")
            await page.goto("https://quote.eastmoney.com/center/gridlist.html#industry_board", timeout=60000)
            await remove_eastmoney_mask(page)
            
            # 等待页面完全加载
            await asyncio.sleep(2)  # 等待额外的时间以确保数据加载
         
            await page.wait_for_selector('th', timeout=10000)  # 等待表头加载
            
            # 等待表格数据加载
            await page.wait_for_selector('.quotetable table tbody tr', state='visible', timeout=30000)
            
            # 行业板块涨幅Top5
            gainers = []
            rows = await page.locator('.quotetable table tbody tr').all()
            for row in rows[:5]:
                name = await row.locator("td:nth-child(2)").inner_text()
                pct_change = await row.locator("td:nth-child(6)").inner_text()
                gainers.append({"name": name.strip(), "change_pct": pct_change})
            results["industry_top_gainers"] = gainers
            logging.info(f"成功获取行业涨幅Top5: {gainers}")

            # 行业板块跌幅Top5 (通过点击排序实现)
            await page.locator('th.sort[title="点击排序"]:nth-child(6)').click()
            await asyncio.sleep(2) # 等待数据加载和UI更新
            losers = []
            rows_sorted = await page.locator("table tbody tr").all()
            for row in rows_sorted[:5]:
                name = await row.locator("td:nth-child(2)").inner_text()
                pct_change = await row.locator("td:nth-child(3)").inner_text()
                losers.append({"name": name.strip(), "change_pct": pct_change})
            results["industry_top_losers"] = losers
            logging.info(f"成功获取行业跌幅Top5: {losers}")
            
            # 主力资金流入Top3板块 (直接访问资金流向页面)
            await page.goto("https://data.eastmoney.com/bkzj/hy.html", timeout=60000)
            await remove_eastmoney_mask(page)
            await asyncio.sleep(2) # 等待数据加载
            
            # 等待表格数据加载
            await page.wait_for_selector('.dataview-body table tbody tr', timeout=15000)
            inflows = []
            rows_inflow = await page.locator(".dataview-body table tbody tr").all()
            for row in rows_inflow[:3]:
                name = await row.locator('td:nth-child(2)').inner_text()  # 第2列是板块名称
                inflow_amount = await row.locator('td:nth-child(4)').inner_text()  # 第4列是主力净额
                inflows.append({"name": name.strip(), "inflow_amount": inflow_amount})
                # 使用新的选择器获取前3行数据
                


            results["industry_top_inflows"] = inflows
            logging.info(f"成功获取主力资金流入Top3: {inflows}")

        except Exception as e:
            logging.error(f"爬取行业板块动态时发生错误: {e}\n{traceback.format_exc()}")
            results["industry_dynamics"] = {"error": str(e)}

        # 2.3 北向资金
        try:
            logging.info("正在爬取北向资金数据...")
            await page.goto("https://data.eastmoney.com/hsgt/index.html", timeout=60000)
            await remove_eastmoney_mask(page)
            
            # 等待页面加载完成
            # await page.wait_for_load_state('networkidle')
            await asyncio.sleep(4)  # 额外等待以确保数据加载
            
            # 等待北向资金数据加载
            await page.wait_for_selector('#north_h_cjze, #north_s_cjze, #north_cjze', timeout=10000)
            
            # 获取沪股通、深股通和北向资金成交总额
            h_amount = (await page.locator('#north_h_cjze').inner_text()).replace('亿元', '')
            s_amount = (await page.locator('#north_s_cjze').inner_text()).replace('亿元', '')
            total_amount = (await page.locator('#north_cjze').inner_text()).replace('亿元', '')
            
            results["northbound_trade"] = {
                "沪股通成交额": f"{h_amount}亿",
                "深股通成交额": f"{s_amount}亿",
                "北向资金成交总额": f"{total_amount}亿"
            }
            logging.info(f"成功获取北向资金成交数据: {results['northbound_trade']}")
        except TimeoutError:
            logging.error("等待北向资金数据加载超时")
            results["northbound_trade"] = {"error": "数据加载超时"}
        except Exception as e:
            logging.error(f"爬取北向资金时发生错误: {e}")
            results["northbound_trade"] = {"error": str(e)}

        # 3. 同花顺 - 市场情绪指标
        logging.info("正在从同花顺爬取市场情绪指标...")
        
        try:
            # 使用新的scrape_today函数获取数据
            ths_data = await scrape_today()
            
            results["stock_updown_summary"] = {
                "上涨家数": str(ths_data["upCount"]),
                "下跌家数": str(ths_data["downCount"])
            }
            results["stock_limit_summary"] = {
                "涨停总数": str(ths_data["limitUpCount"]),
                "跌停总数": str(ths_data["limitDownCount"])
            }
            results["stock_limit_up_list"] = ths_data["limitUpList"]
            results["stock_limit_down_list"] = ths_data["limitDownList"]
            
            logging.info(f"成功获取涨跌家数: {results['stock_updown_summary']}")
            logging.info(f"涨幅前三: {len(ths_data['limitUpList'])}只")
            logging.info(f"跌幅前三: {len(ths_data['limitDownList'])}只")
        except Exception as e:
            logging.error(f"爬取上涨/下跌家数时发生错误: {e}")
            results["stock_updown_summary"] = {"error": str(e)}

        # 4. 新浪财经 - 总成交额
        logging.info("正在从新浪财经爬取总成交额...")
        try:
            await page.goto("https://finance.sina.com.cn/data/", timeout=60000)
            await asyncio.sleep(3)  # 等待页面加载完成
            await page.wait_for_selector("#stockA_index_wrap", timeout=10000)
            await asyncio.sleep(2)  # 额外等待以确保数据加载
            sh_turnover = await page.locator("#stockA_index_wrap > dl:nth-child(1) > dd > span").inner_text()
            sz_turnover = await page.locator("#stockA_index_wrap > dl:nth-child(2) > dd > span").inner_text()
            results["market_total_turnover"] = {"沪市指数、涨跌幅、总成交额": sh_turnover, "深市指数、涨跌幅、总成交额": sz_turnover}
            logging.info(f"成功获取总成交额: {results['market_total_turnover']}")
        except Exception as e:
            logging.error(f"爬取总成交额时发生错误: {e}")
            results["market_total_turnover"] = {"error": str(e)}

        await context.close()
    
    logging.info("所有爬取任务已完成。")
    return results

async def main():
    """主函数，用于执行爬虫并打印结果。"""
    # 如果需要调试，传入debug=True
    scraped_data = await scrape_financial_data(debug=True)
    
    # 使用pprint获得更美观的格式化输出
    import pprint
    print("\n--- 爬取结果 ---")
    pprint.pprint(scraped_data)
    print("--- 结果结束 ---\n")

    # 额外打印板块和加密货币数据
    if "US_MARKET_SECTORS" in scraped_data and scraped_data["US_MARKET_SECTORS"]:
        print("\n--- 美股市场每日板块表现 ---")
        print("--- 每日涨幅前三板块 (Top 3 Daily Gainers) ---")
        print(pd.DataFrame(scraped_data["US_MARKET_SECTORS"]["top_gainers"]).to_string(index=False))
        print("\n--- 每日跌幅前三板块 (Top 3 Daily Losers) ---")
        print(pd.DataFrame(scraped_data["US_MARKET_SECTORS"]["top_losers"]).to_string(index=False))
    
    if "CRYPTOCURRENCY_DATA" in scraped_data and scraped_data["CRYPTOCURRENCY_DATA"]:
        print("\n--- 主流加密货币实时表现 ---")
        print(pd.DataFrame(scraped_data["CRYPTOCURRENCY_DATA"]).to_string(index=False))

# ===== 东方财富板块资金流向API爬虫类（来自 volume.py） =====
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
        try:
            params = {
                'cb': 'jQuery112404953340710317346_1640000000000',
                'pn': '1',
                'pz': '500',
                'po': '1',
                'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2',
                'invt': '2',
                'wbp2u': '|0|0|0|web',
                'fid': 'f62',
                'fs': 'm:90 t:2',
                'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124'
            }
            url = f"{self.base_url}?"
            for key, value in params.items():
                url += f"{key}={value}&"
            url = url.rstrip('&')
            response = await page.goto(url, wait_until='networkidle')
            content = await page.content()
            if 'jQuery' in content:
                start_idx = content.find('(') + 1
                end_idx = content.rfind(')')
                json_str = content[start_idx:end_idx]
                data = json.loads(json_str)
                return data.get('data', {}).get('diff', [])
            else:
                return []
        except Exception as e:
            print(f"获取数据失败: {e}")
            return []

    async def parse_sector_data(self, raw_data):
        sectors = []
        for item in raw_data:
            try:
                sector_info = {
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'price': item.get('f2', 0),
                    'change_pct': item.get('f3', 0),
                    'main_net_inflow': item.get('f62', 0),
                    'main_net_inflow_pct': item.get('f184', 0),
                    'super_large_net_inflow': item.get('f66', 0),
                    'large_net_inflow': item.get('f69', 0),
                    'medium_net_inflow': item.get('f72', 0),
                    'small_net_inflow': item.get('f75', 0),
                    'super_large_inflow': item.get('f78', 0),
                    'super_large_outflow': item.get('f79', 0),
                    'large_inflow': item.get('f81', 0),
                    'large_outflow': item.get('f82', 0),
                    'medium_inflow': item.get('f84', 0),
                    'medium_outflow': item.get('f85', 0),
                    'small_inflow': item.get('f87', 0),
                    'small_outflow': item.get('f88', 0),
                    'total_turnover': item.get('f124', 0),
                }
                money_fields = ['main_net_inflow', 'super_large_net_inflow', 'large_net_inflow',
                                'medium_net_inflow', 'small_net_inflow', 'super_large_inflow',
                                'super_large_outflow', 'large_inflow', 'large_outflow',
                                'medium_inflow', 'medium_outflow', 'small_inflow', 'small_outflow']
                for field in money_fields:
                    if sector_info[field]:
                        sector_info[field] = sector_info[field] / 10000
                sectors.append(sector_info)
            except Exception as e:
                continue
        return sectors

    def analyze_sectors(self, sectors):
        if not sectors:
            return None
        df = pd.DataFrame(sectors)
        df_sorted = df.sort_values('main_net_inflow', ascending=False)
        max_inflow_sector = df_sorted.iloc[0]
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
                'net_outflow': abs(max_outflow_sector['main_net_inflow']),
                'change_pct': max_outflow_sector['change_pct'],
                'price': max_outflow_sector['price']
            },
            'total_sectors': len(sectors),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return result

    async def crawl_sector_money_flow(self, playwright=None):
        # playwright参数可复用外部实例
        close_browser = False
        if playwright is None:
            playwright = await async_playwright().start()
            close_browser = True
        browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            page = await browser.new_page()
            await page.set_extra_http_headers(self.headers)
            await page.set_viewport_size({"width": 1920, "height": 1080})
            raw_data = await self.get_sector_data(page)
            if not raw_data:
                return None
            sectors = await self.parse_sector_data(raw_data)
            if not sectors:
                return None
            analysis_result = self.analyze_sectors(sectors)
            return analysis_result, sectors
        except Exception as e:
            print(f"爬取过程中发生错误: {e}")
            return None
        finally:
            await browser.close()
            if close_browser:
                await playwright.stop()

# ========== 修改 scrape_financial_data，集成东方财富API板块资金流向 ==========
# 在东方财富网部分最后添加如下调用
# ...
#         # 2.4 东方财富API板块资金流向
        try:
            logging.info("正在通过API爬取东方财富板块资金流向...")
            sector_crawler = StockSectorCrawler()
            # 复用playwright实例，避免重复启动
            result = await sector_crawler.crawl_sector_money_flow(playwright=p)
            if result:
                analysis, all_sectors = result
                results["eastmoney_sector_money_flow"] = {
                    "analysis": analysis,
                    "all_sectors": all_sectors
                }
                logging.info(f"成功获取东方财富API板块资金流向: {analysis}")
            else:
                results["eastmoney_sector_money_flow"] = {"error": "API未获取到数据"}
        except Exception as e:
            logging.error(f"东方财富API板块资金流向爬取失败: {e}")

if __name__ == "__main__":
    # 在 Windows 上运行时，设置此策略以避免事件循环错误
    if sys.platform == "win32":
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

