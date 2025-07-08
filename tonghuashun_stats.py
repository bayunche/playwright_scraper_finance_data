# filename: tonghuashun_stats.py
import asyncio
from playwright.async_api import async_playwright
import re # 导入re模块
from bs4 import BeautifulSoup # 导入BeautifulSoup
# from playwright_stealth import stealth_async # 移除此行

URL = "https://q.10jqka.com.cn/"

async def get_top3_rows(page):
    """提取当前排序下的前三行股票数据"""
    rows = await page.query_selector_all("table.m-table tbody tr")
    top3 = []
    for row in rows[:3]:
        tds = await row.query_selector_all("td")
        name = await tds[2].inner_text()
        code = await tds[1].inner_text()
        price = await tds[3].inner_text()
        change_percent = await tds[4].inner_text()
        top3.append({
            "code": code,
            "name": name,
            "price": price,
            "change_percent": change_percent
        })
    return top3

async def scrape_today():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)  # 关闭无头模式以便调试
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

        # 更快抓取：阻止图片、字体等资源加载
        # 增加页面加载检查
        await page.goto(URL, wait_until="domcontentloaded")
        
        result = {}

        try:
            all_stocks = [] # 在try块开始时初始化all_stocks
            # 等待hcharts-list元素可见
            await page.wait_for_timeout(5000) # 增加等待时间
            # 获取hcharts-list的HTML内容
            hcharts_list_html = await page.locator('.hcharts-list').inner_html(timeout=120000) # 增加超时时间
            soup = BeautifulSoup(hcharts_list_html, 'lxml')

            # 等待表格的tbody中至少有一行数据加载完成
            # await page.wait_for_selector('table.m-table.m-pager-table tbody tr', timeout=60000) # 增加等待表格行的超时时间
            await page.wait_for_timeout(5000) # 增加等待时间


            # 涨跌分布 (上涨/下跌家数)
            rise_span_dist = soup.select_one('div.item:has(h3:contains("涨跌分布")) p.detail span.c-rise')
            if rise_span_dist:
                match = re.search(r'上涨：(\d+)只', rise_span_dist.get_text())
                result['riseCount'] = int(match.group(1)) if match else 0
            else:
                result['riseCount'] = 0

            fall_span_dist = soup.select_one('div.item:has(h3:contains("涨跌分布")) p.detail span.c-fall')
            if fall_span_dist:
                match = re.search(r'下跌：(\d+)只', fall_span_dist.get_text())
                result['fallCount'] = int(match.group(1)) if match else 0
                result['downCount'] = result['fallCount']  # 添加与fallCount相同的字段
                result['upCount'] = result['riseCount']  # 添加与riseCount相同的字段
            else:
                result['fallCount'] = 0
                result['downCount'] = 0  # 异常情况下也初始化
                result['upCount'] = 0  # 异常情况下也初始化

            # 涨跌停 (涨停/跌停家数)
            limit_up_span = soup.select_one('div.item:has(h3:contains("涨跌停")) p.detail span.c-rise')
            if limit_up_span:
                match = re.search(r'涨停：(\d+)只', limit_up_span.get_text())
                result['limitUpCount'] = int(match.group(1)) if match else 0
            else:
                result['limitUpCount'] = 0

            limit_down_span = soup.select_one('div.item:has(h3:contains("涨跌停")) p.detail span.c-fall')
            if limit_down_span:
                match = re.search(r'跌停：(\d+)只', limit_down_span.get_text())
                result['limitDownCount'] = int(match.group(1)) if match else 0
            else:
                result['limitDownCount'] = 0

            # 昨日涨停今日收益
            yesterday_limit_up_profit_span = soup.select_one('div.item:has(h3:contains("昨日涨停今日收益")) p.detail span.c-rise')
            if yesterday_limit_up_profit_span:
                match = re.search(r'今收益：([\d.]+)%', yesterday_limit_up_profit_span.get_text())
                result['yesterdayLimitUpProfit'] = float(match.group(1)) if match else 0.0
            else:
                result['yesterdayLimitUpProfit'] = 0.0

            # 涨停前三股票和跌停前三股票
            # 获取涨幅前三股票
            result['limitUpTop3'] = await get_top3_rows(page)
            result['limitUpList'] = result['limitUpTop3'] # 添加别名

            # 点击“涨跌幅”列头，切换为升序排序
            await page.evaluate('document.querySelector("a[field=\'zdf\']").click()')
            
            await page.wait_for_timeout(1000) # 等待排序完成

            # 再获取跌幅前三股票
            result['limitDownTop3'] = await get_top3_rows(page)
            result['limitDownList'] = result['limitDownTop3'] # 添加别名

        except Exception as e:
            print(f"爬取数据时发生错误: {e}")
            # 初始化所有结果为默认值，以防任何部分爬取失败
            result['limitUpCount'] = 0
            result['limitDownCount'] = 0
            result['riseCount'] = 0
            result['fallCount'] = 0
            result['downCount'] = 0  # 添加与fallCount相同的字段
            result['upCount'] = 0  # 添加与riseCount相同的字段
            result['yesterdayLimitUpProfit'] = 0.0 # 新增字段初始化
            result['limitUpTop3'] = [] # 确保在异常情况下也被初始化
            result['limitUpList'] = [] # 添加与limitUpTop3相同的字段
            result['limitDownTop3'] = [] # 确保在异常情况下也被初始化
            result['limitDownList'] = [] # 添加与limitDownTop3相同的字段

        await browser.close()
        return result

async def main():
    result = await scrape_today()
    print("📈 金融界 今日统计：")
    print(f" 涨停家数：{result['limitUpCount']}")
    print(f" 跌停家数：{result['limitDownCount']}")
    print(f" 今日下跌：{result['fallCount']} 家")
    print(f" 今日上涨：{result['riseCount']} 家")
    
    print("\n📈 涨幅前三：")
    for stock in result['limitUpTop3']:
        print(f'{stock["name"]}（{stock["code"]}）: {stock["change_percent"]}%')

    print("\n📉 跌幅前三：")
    for stock in result['limitDownTop3']:
        print(f'{stock["name"]}（{stock["code"]}）: {stock["change_percent"]}%')
    
    print(f"\n昨日涨停今日收益：{result['yesterdayLimitUpProfit']}%")

if __name__ == "__main__":
    asyncio.run(main())
