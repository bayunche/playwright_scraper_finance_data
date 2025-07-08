import logging
import pandas as pd
from playwright.sync_api import sync_playwright # 使用同步API

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_crypto_data_sync():
    """
    使用 Playwright 同步爬取主流加密货币的价格、涨跌额和涨跌幅。
    数据源为 Yahoo Finance。
    不使用 playwright_stealth 和 asyncio。
    """
    crypto_map = {
        "BTC-USD": "比特币 (Bitcoin)",
        "ETH-USD": "以太坊 (Ethereum)",
        "USDT-USD": "泰达币 (USDT)"
    }

    logging.info("\n--- 正在抓取加密货币数据... (Scraping Cryptocurrency Data...) ---")

    crypto_results = []

    try:
        with sync_playwright() as p: # 使用同步playwright
            browser = p.chromium.launch(headless=False) # 可以设置为True，如果不需要显示浏览器
            page = browser.new_page()

            for ticker, name in crypto_map.items():
                url = f"https://finance.yahoo.com/quote/{ticker}"
                try:
                    page.goto(url, timeout=60000)
                    # 等待页面加载完成
                    page.wait_for_load_state('networkidle', timeout=60000) # 增加超时时间
                    # 等待包含价格信息的特定区域出现
                    page.wait_for_selector('#quote-header-info', timeout=30000) # 增加超时时间

                    # 尝试更精确地定位价格元素，例如通过其父元素
                    price_locator = page.locator('#quote-header-info fin-streamer[data-field="regularMarketPrice"]')
                    change_val_locator = page.locator('#quote-header-info fin-streamer[data-field="regularMarketChange"]')
                    change_pct_locator = page.locator('#quote-header-info fin-streamer[data-field="regularMarketChangePercent"]')

                    # 确保元素可见并获取文本
                    # 增加对元素可见性的等待
                    price = price_locator.wait_for(state='visible', timeout=10000).inner_text()
                    change_val = change_val_locator.wait_for(state='visible', timeout=10000).inner_text()
                    change_pct = change_pct_locator.wait_for(state='visible', timeout=10000).inner_text().strip("()")

                    crypto_results.append({
                        "名称 (Name)": name,
                        "价格 (Price)": f"${price}",
                        "24h涨跌值 (Change)": change_val,
                        "24h涨跌幅 (%)": change_pct
                    })
                except Exception as e:
                    logging.error(f"❌ 抓取 {name} ({ticker}) 数据失败 (Failed to scrape {name}): {e}")
                    continue
            browser.close()
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

if __name__ == "__main__":
    print("开始测试 get_crypto_data_sync 函数...")
    result = get_crypto_data_sync()
    if result:
        print("\n--- 测试结果 ---")
        print(pd.DataFrame(result).to_string(index=False))
        print("--- 测试结束 ---\n")
    else:
        print("\n--- 测试失败，未获取到数据 ---")