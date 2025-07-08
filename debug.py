
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import asyncio

async def debug():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://finviz.com/groups.ashx?g=sector&v=111", timeout=60000)
        await page.wait_for_timeout(5000)  # 等待额外加载
        await page.screenshot(path="debug_finviz.png", full_page=True)

        html = await page.content()
        with open("debug_finviz.html","w",encoding="utf-8") as f:
            f.write(html)

        print("截图和 HTML 已保存，供排查结构使用")
        await browser.close()
