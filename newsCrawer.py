from fastapi import FastAPI, Query, HTTPException
from typing import List
from datetime import datetime, timedelta, timezone
import aiohttp
import asyncio
import json
import re # 新增导入
import sys # 新增导入
import random # 新增导入
from playwright.async_api import async_playwright

app = FastAPI()

# ---------- 工具函数 ----------
import re
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

async def get_eastmoney_news():
    """
    通过API获取东方财富网新闻数据（红字焦点快讯）
    """
    api_url = "http://api.guiguiya.com/api/hotlist/eastmoney?type=101&apiKey=5f1640bafa754a0c7d0e93d432b07c79"
    results = []
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, timeout=10) as response:
                response.raise_for_status()  # 检查HTTP响应状态
                data = await response.json()
                
                if data.get("success") and data.get("data"):
                    for item in data["data"]:
                        pub_time_str = item.get("time")
                        pub_time = None
                        if pub_time_str:
                            try:
                                # API返回的时间格式是 "YYYY-MM-DD HH:MM:SS"
                                pub_time = datetime.strptime(pub_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
                            except ValueError:
                                print(f"无法解析API返回的时间格式: {pub_time_str}")
                        
                        results.append({
                            "title": item.get("title", "").strip(),
                            "summary": item.get("content", "").strip(),
                            "url": item.get("url", ""),
                            "datetime": pub_time.isoformat() if pub_time else None,
                            "market": "东方财富" # 固定为东方财富
                        })
                else:
                    print(f"API返回失败或无数据: {data.get('msg', '未知错误')}")
        except aiohttp.ClientError as e:
            print(f"请求东方财富API失败: {e}")
        except asyncio.TimeoutError:
            print("请求东方财富API超时")
        except Exception as e:
            print(f"处理东方财富API响应时发生错误: {e}")
    # 随机抽取3条新闻
    return random.sample(results, min(len(results), 3))


async def get_cls_news(start_date: datetime, end_date: datetime):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto("https://www.cls.cn/", timeout=30000)
            # await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)

            # 根据实际页面结构更新选择器
            # 财联社主页新闻通常在这些区域
            news_selectors = [
                'a[href*="/detail/"]',  # 详情页链接
                '.news-item a',
                '.article-item a', 
                '.news-list a'
            ]
            
            items = []
            for selector in news_selectors:
                temp_items = await page.query_selector_all(selector)
                if temp_items:
                    items = temp_items
                    break
            
            if not items:
                print("未找到新闻条目，可能需要更新选择器")
                return results

            for item in items:
                try:
                    # 获取标题和链接
                    title_element = item  # 直接使用item作为标题元素
                    title = (await title_element.inner_text()).strip()
                    url = await item.get_attribute("href")
                    
                    if not title or not url:
                        continue
                        
                    # 构建完整URL
                    if url.startswith('/'):
                        full_url = f"https://www.cls.cn{url}"
                    elif not url.startswith('http'):
                        full_url = f"https://www.cls.cn/{url}"
                    else:
                        full_url = url

                    # 获取时间信息 - 寻找包含时间的父元素或兄弟元素
                    pub_time = None
                    time_text = ""
                    
                    # 尝试从多个可能位置获取时间
                    time_sources = [
                        await item.evaluate("el => el.closest('.news-item, .article-item')?.innerText || ''"),
                        await item.evaluate("el => el.parentElement?.innerText || ''"),
                        await item.evaluate("el => el.querySelector('.time, .date, .publish-time')?.innerText || ''")
                    ]
                    
                    for source in time_sources:
                        if source:
                            # 匹配多种时间格式
                            time_patterns = [
                                r'(\d{1,2}月\d{1,2}日\s+\d{2}:\d{2})',  # 6月3日 07:00
                                r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{2}:\d{2})',  # 2025-06-03 07:00
                                r'(\d{1,2}-\d{1,2}\s+\d{2}:\d{2})'  # 06-03 07:00
                            ]
                            
                            for pattern in time_patterns:
                                match = re.search(pattern, source)
                                if match:
                                    time_text = match.group(1)
                                    break
                            if time_text:
                                break
                    
                    # 解析时间
                    if time_text:
                        try:
                            if '月' in time_text and '日' in time_text:
                                # 处理 "6月3日 07:00" 格式
                                pub_time = datetime.strptime(time_text, "%m月%d日 %H:%M")
                                pub_time = pub_time.replace(year=start_date.year)
                            elif '-' in time_text and len(time_text.split('-')[0]) == 4:
                                # 处理 "2025-06-03 07:00" 格式
                                pub_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
                            elif '-' in time_text:
                                # 处理 "06-03 07:00" 格式
                                pub_time = datetime.strptime(time_text, "%m-%d %H:%M")
                                pub_time = pub_time.replace(year=start_date.year)
                        except ValueError as e:
                            print(f"时间解析失败: {time_text}, 错误: {e}")
                            continue

                    # 如果没有获取到时间或时间不在范围内，跳过
                    if not pub_time or not (start_date <= pub_time <= end_date):
                        continue

                    # 访问详情页获取摘要
                    summary = ""
                    try:
                        detail_page = await browser.new_page()
                        await detail_page.goto(full_url, timeout=15000)
                        await detail_page.wait_for_load_state('networkidle', timeout=10000)
                        
                        # 财联社详情页内容选择器
                        content_selectors = [
                            '.detail-content p:first-of-type',
                            '.article-content p:first-of-type', 
                            '.content p:first-of-type',
                            '.news-content p:first-of-type',
                            'article p:first-of-type',
                            '.main-content p:first-of-type'
                        ]
                        
                        for selector in content_selectors:
                            try:
                                element = await detail_page.query_selector(selector)
                                if element:
                                    text = await element.inner_text()
                                    if text and len(text.strip()) > 10:  # 确保有实质内容
                                        summary = text.strip()
                                        break
                            except:
                                continue
                                
                        await detail_page.close()
                        
                    except Exception as e:
                        print(f"获取详情页失败 {full_url}: {e}")
                        # 即使获取摘要失败，也保留新闻条目
                        summary = ""

                    results.append({
                        "title": title,
                        "summary": summary,
                        "url": full_url,
                        "datetime": pub_time.isoformat() if pub_time else "",
                        "market": "财联社"
                    })
                    
                except Exception as e:
                    print(f"处理新闻条目时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"财联社爬取出错: {e}")
        finally:
            await browser.close()
    
    return results


async def get_wsj_news(start_date: datetime, end_date: datetime):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 设置用户代理避免反爬
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        try:
            await page.goto("https://wallstreetcn.com/news/shares", wait_until='domcontentloaded')
            # await page.wait_for_load_state('networkidle', timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 尝试多种可能的选择器
            possible_selectors = [
                ".list-item",           # 你原来的选择器
                ".news-item",           # 常见的新闻项选择器  
                ".article-item",        # 文章项选择器
                "[data-testid*='news']", # 测试ID选择器
                ".content-item",        # 内容项选择器
                "article",              # HTML5语义标签
                ".feed-item"            # 信息流项选择器
            ]
            
            for attempt in range(5):  # 最多尝试5次加载更多
                # 尝试找到新闻列表
                items = []
                for selector in possible_selectors:
                    items = await page.query_selector_all(selector)
                    if items:
                        print(f"使用选择器: {selector}, 找到 {len(items)} 个项目")
                        break
                
                if not items:
                    print("未找到新闻项目，尝试等待页面加载...")
                    await page.wait_for_timeout(2000)
                    continue
                
                # 处理找到的新闻项
                for item in items:
                    try:
                        # 尝试多种标题选择器
                        title_selectors = [
                            ".article-link.title",
                            ".title a",
                            ".news-title",
                            "h3 a", "h2 a", "h1 a",
                            ".headline a",
                            "a[href*='/news/']",
                            ".link-title"
                        ]
                        
                        title_el = None
                        title = ""
                        url = ""
                        
                        for title_selector in title_selectors:
                            title_el = await item.query_selector(title_selector)
                            if title_el:
                                title = await title_el.inner_text()
                                url = await title_el.get_attribute("href")
                                break
                        
                        # 如果没有找到带链接的标题，尝试纯文本标题
                        if not title_el:
                            text_selectors = [".title", ".headline", "h3", "h2", "h1"]
                            for text_selector in text_selectors:
                                title_el = await item.query_selector(text_selector)
                                if title_el:
                                    title = await title_el.inner_text()
                                    break
                        
                        if not title:
                            continue
                            
                        # 尝试多种时间选择器
                        time_selectors = [
                            ".meta .time",
                            ".time",
                            ".publish-time", 
                            ".date",
                            "[datetime]",
                            ".timestamp",
                            ".meta-time"
                        ]
                        
                        time_el = None
                        pub_time = None
                        
                        for time_selector in time_selectors:
                            time_el = await item.query_selector(time_selector)
                            if time_el:
                                # 尝试获取datetime属性
                                raw_time_attr = await time_el.get_attribute("datetime")
                                if not raw_time_attr:
                                    # 如果没有datetime属性，尝试获取文本内容
                                    raw_time_attr = await time_el.inner_text()
                                
                                if raw_time_attr:
                                    pub_time = parse_time(raw_time_attr)
                                    if pub_time:
                                        break
                        
                        # 如果没有找到时间，跳过这个项目
                        if not pub_time or not (start_date <= pub_time <= end_date):
                            continue
                        
                        # 确保URL是完整的
                        if url and not url.startswith('http'):
                            if url.startswith('/'):
                                url = "https://wallstreetcn.com" + url
                            else:
                                url = "https://wallstreetcn.com/" + url
                        
                        # 获取摘要
                        summary = ""
                        summary_selectors = [
                            ".content",
                            ".summary", 
                            ".description",
                            ".excerpt",
                            ".abstract",
                            "p"
                        ]
                        
                        for summary_selector in summary_selectors:
                            try:
                                summary_el = await item.query_selector(summary_selector)
                                if summary_el:
                                    summary = (await summary_el.inner_text()).strip()
                                    if summary:  # 如果找到非空摘要就停止
                                        break
                            except:
                                continue
                        
                        # 检查是否已经存在相同的新闻（去重）
                        if not any(result['title'] == title.strip() for result in results):
                            results.append({
                                "title": title.strip(),
                                "summary": summary,
                                "url": url,
                                "datetime": pub_time.isoformat(),
                                "market": "华尔街见闻"
                            })
                    
                    except Exception as e:
                        print(f"处理新闻项时出错: {e}")
                        continue
                
                # 尝试点击加载更多
                try:
                    # 尝试多种"加载更多"按钮选择器
                    load_more_selectors = [
                        "text=加载更多",
                        "text=更多",
                        "text=Load More",
                        ".load-more",
                        ".more-btn",
                        "[data-testid*='load']",
                        "button:has-text('更多')",
                        "button:has-text('加载')"
                    ]
                    
                    load_more_clicked = False
                    for load_selector in load_more_selectors:
                        try:
                            load_more = await page.query_selector(load_selector)
                            if load_more and await load_more.is_visible():
                                await load_more.click()
                                await page.wait_for_timeout(3000)  # 等待新内容加载
                                load_more_clicked = True
                                print(f"点击了加载更多按钮: {load_selector}")
                                break
                        except:
                            continue
                    
                    if not load_more_clicked:
                        # 尝试滚动到页面底部触发懒加载
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(2000)
                        
                        # 检查是否有新内容加载
                        new_items = []
                        for selector in possible_selectors:
                            new_items = await page.query_selector_all(selector)
                            if new_items:
                                break
                        
                        if len(new_items) <= len(items):
                            print("没有更多内容，结束爬取")
                            break
                    
                except Exception as e:
                    print(f"加载更多内容时出错: {e}")
                    break
                    
        except Exception as e:
            print(f"访问页面时出错: {e}")
        
        finally:
            await browser.close()
    
    return results


def parse_time(time_str):
    """解析各种时间格式并返回带时区(UTC+8)的datetime对象"""
    if not time_str:
        return None
        
    time_str = time_str.strip()
    beijing_tz = timezone(timedelta(hours=8))
    
    # 尝试解析ISO格式
    try:
        # 处理带时区的ISO格式
        if 'T' in time_str:
            # 移除毫秒部分
            if '.' in time_str:
                time_str = time_str.split('.')[0] + time_str.split('.')[-1][-6:]
            
            # 处理时区
            if time_str.endswith('Z'):
                time_str = time_str.replace('Z', '+00:00')
            elif '+' in time_str[-6:] or '-' in time_str[-6:]:
                pass  # 已有时区信息
            else:
                time_str += '+08:00'  # 默认北京时间
                
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=beijing_tz)
            return dt.astimezone(beijing_tz)
    except:
        pass
    
    # 尝试解析常见的中文时间格式
    try:
        # 格式: "2025-07-01 13:37"
        if len(time_str) == 16 and '-' in time_str and ':' in time_str:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=beijing_tz)
        
        # 格式: "07-01 13:37"
        if len(time_str) == 11 and '-' in time_str and ':' in time_str:
            current_year = datetime.now().year
            return datetime.strptime(f"{current_year}-{time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=beijing_tz)
            
        # 格式: "今天 13:37"
        if time_str.startswith('今天'):
            time_part = time_str.replace('今天', '').strip()
            today = datetime.now(beijing_tz).date()
            time_obj = datetime.strptime(time_part, "%H:%M").time()
            return datetime.combine(today, time_obj).replace(tzinfo=beijing_tz)
            
        # 格式: "昨天 13:37"
        if time_str.startswith('昨天'):
            time_part = time_str.replace('昨天', '').strip()
            yesterday = datetime.now(beijing_tz).date() - timedelta(days=1)
            time_obj = datetime.strptime(time_part, "%H:%M").time()
            return datetime.combine(yesterday, time_obj).replace(tzinfo=beijing_tz)
            
    except:
        pass
    
    print(f"无法解析时间格式: {time_str}")
    return None
async def get_weibo_hot_search():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://s.weibo.com/top/summary")
        await page.wait_for_selector(".td-02")
        items = await page.query_selector_all("table tbody tr")
        for item in items:
            rank_el = await item.query_selector(".td-01")
            title_el = await item.query_selector(".td-02 a")
            if not title_el:
                continue
            title = await title_el.inner_text()
            url = await title_el.get_attribute("href")
            results.append({
                "title": title.strip(),
                "summary": "",  # 可选扩展
                "url": f"https://s.weibo.com{url}",
                "datetime": datetime.now().isoformat(),
                "market": "微博热搜"
            })
        await browser.close()
    # 随机抽取1条热搜
    return random.sample(results, min(len(results), 1))

# ---------- 主接口 ----------
@app.get("/news")
async def get_news(
    start: str = Query(..., description="起始日期，支持YYYY-MM-DD或ISO 8601格式"),
    end: str = Query(..., description="结束日期，支持YYYY-MM-DD或ISO 8601格式")
):
    beijing_tz = timezone(timedelta(hours=8))

    def _parse_date_with_timezone(date_str: str) -> datetime:
        # 尝试解析ISO 8601格式
        try:
            # 处理 'Z' 结尾的UTC时间
            if date_str.endswith('Z'):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).astimezone(beijing_tz)
            else:
                dt = datetime.fromisoformat(date_str).astimezone(beijing_tz)
            return dt
        except ValueError:
            pass # 继续尝试其他格式

        # 尝试解析 YYYY-MM-DD 格式
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=beijing_tz)
            return dt
        except ValueError:
            pass # 继续尝试其他格式
        
        raise HTTPException(
            status_code=400,
            detail=f"日期格式错误，请使用YYYY-MM-DD或ISO 8601格式: {date_str}"
        )

    start_date = _parse_date_with_timezone(start)
    end_date = _parse_date_with_timezone(end)
    
    # 如果end_date只提供了日期，将其设置为当天的最后一刻
    if len(end) == 10 and '-' in end: # 假设YYYY-MM-DD格式
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 检查日期有效性
    now = datetime.now(timezone(timedelta(hours=8)))
    if start_date > now or end_date > now:
        raise HTTPException(
            status_code=400,
            detail="日期不能超过当前日期"
        )

    all_results = []

    all_results += await get_eastmoney_news()

    # all_results += await get_cls_news(start_date, end_date)
    # all_results += await get_wsj_news(start_date, end_date)
    all_results += await get_weibo_hot_search()

    return {"data": all_results}

if __name__ == "__main__":
    # 在 Windows 上运行时，设置此策略以避免事件循环错误
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # 示例运行，可以根据需要调整日期
    asyncio.run(get_news(start="2025-06-01", end="2025-07-01"))