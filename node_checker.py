import asyncio
import logging
from playwright.async_api import async_playwright, TimeoutError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 指定目标网址及需要检测的CSS选择器字典
URLS_TO_CHECK = {
    "Investing_DXY": {
        "url": "https://www.investing.com/indices/usdollar",
        "selectors": [
            '[data-test="instrument-header-details"] [data-test="instrument-price-last"]',
            '[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]',
        ],
    },
    "Investing_WTI": {
        "url": "https://www.investing.com/commodities/crude-oil",
        "selectors": [
            '[data-test="instrument-header-details"] [data-test="instrument-price-last"]',
            '[data-test="instrument-header-details"] [data-test="instrument-price-change-percent"]',
        ],
    },
    "EastMoney_Shanghai_Index": {
        "url": "https://quote.eastmoney.com/zs000001.html",
        "selectors": [
            '.quote-header-index-price',
            '[data-id="idx-price"]',
            '[data-id="idx-changeRate"]',
        ],
    },
    "EastMoney_Industry_Board": {
        "url": "https://quote.eastmoney.com/center/boardlist.html#industry_board",
        "selectors": [
            '#datatable > tbody > tr',
            'th[aria-label*="涨跌幅"]',
            'li[data-type="zjlx"]',
            '#datatable > tbody > tr > td:nth-child(2)',
            '#datatable > tbody > tr > td:nth-child(3)',
            '#datatable > tbody > tr > td:nth-child(7)',
        ],
    },
    "EastMoney_Northbound": {
        "url": "https://data.eastmoney.com/hsgt/index.html",
        "selectors": [
            '#hsgt_b_board .hsgt-data-item',
            '#hsgt_b_board .hsgt-data-item.active .val',
        ],
    },
    "THS_MainPage": {
        "url": "https://q.10jqka.com.cn/",
        "selectors": [
            '.hcharts-left',
            '.hcharts-left .item:nth-child(2) .c-rise',
            '.hcharts-left .item:nth-child(2) .c-fall',
            '.hcharts-left .item.cur .c-rise',
            '.hcharts-left .item.cur .c-fall',
        ],
    },
    "Sina_Finance": {
        "url": "https://finance.sina.com.cn/data/",
        "selectors": [
            '#stockA_index_wrap',
            '#stockA_index_wrap > dl:nth-child(1) > dd > span',
            '#stockA_index_wrap > dl:nth-child(2) > dd > span',
        ],
    },
}


async def check_nodes():
    logging.info("开始节点验证任务")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for name, site in URLS_TO_CHECK.items():
            url = site["url"]
            selectors = site["selectors"]
            logging.info(f">>> 正在访问 {name} 页面：{url}")
            try:
                await page.goto(url, timeout=60000)
                
                # 获取页面完整HTML
                html = await page.content()
                with open(f"{name}_full.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logging.info(f"{name} 页面完整HTML已保存")

                for selector in selectors:
                    try:
                        # 等待节点(短时间)，判断节点是否存在
                        await page.wait_for_selector(selector, timeout=5000)
                        count = await page.locator(selector).count()
                        logging.info(f"[{name}] 选择器 '{selector}' 存在，节点数量: {count}")
                    except TimeoutError:
                        logging.warning(f"[{name}] 选择器 '{selector}' 不存在或超时")
                    except Exception as e:
                        logging.error(f"[{name}] 检查选择器 '{selector}' 时发生异常: {e}")

            except TimeoutError:
                logging.error(f"{name} 页面访问超时：{url}")
            except Exception as e:
                logging.error(f"{name} 访问失败: {e}")

        await browser.close()
    logging.info("节点验证任务完成")


if __name__ == "__main__":
    asyncio.run(check_nodes())