import sys
from fastapi import FastAPI, Query
from dateutil import parser as date_parser
from datetime import datetime
import asyncio
from market_scraper import scrape_financial_data
from newsCrawer import get_news

# 在Windows上设置事件循环策略
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

@app.get("/news")
# 定义一个异步函数news，用于获取新闻
async def news(
    # 起始日期，格式为YYYY-MM-DD
    start: str = Query(..., description="起始日期，格式为YYYY-MM-DD"),
    # 结束日期，格式为YYYY-MM-DD
    end: str = Query(..., description="结束日期，格式为YYYY-MM-DD")
):
    # 返回获取新闻的异步函数
    return await get_news(start, end)

@app.get("/scrape")
async def scrape(time: str = Query(..., description="时间参数，例如2025-06-29T10:00:00 或任意可识别的时间字符串")):
    try:
        parsed_time = date_parser.parse(time)
    except Exception:
        parsed_time = datetime.now()

    data = await scrape_financial_data()
    return {"time": parsed_time.isoformat(), "data": data}