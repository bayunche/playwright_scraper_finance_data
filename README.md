# 金融市场数据爬虫和API

本项目是一个功能强大的金融数据爬虫和API，旨在从多个主流财经网站抓取实时和历史数据。它利用 Playwright 实现可靠的异步网页抓取，并通过 FastAPI 提供简洁的 RESTful API。项目已容器化，可使用 Docker 轻松部署。

## 功能特性

- **全面的数据覆盖**:
  - **美股市场**:
    - 三大指数 (道琼斯, 纳斯达克, 标普500)
    - 每日涨跌幅前三的板块 (来自 Finviz)
    - 涨幅前五的股票 (来自 Yahoo Finance)
  - **A股市场**:
    - 三大指数 (上证, 深证, 创业板)
    - 行业板块动态 (涨跌幅Top5, 主力资金流入Top3)
    - 北向资金成交额
    - 市场情绪指标 (涨跌停家数)
    - 总成交额 (沪市、深市)
  - **加密货币**:
    - 主流币种 (比特币, 以太坊, USDT) 的实时价格和涨跌幅
  - **宏观指标**:
    - 美元指数 (DXY)
    - WTI原油
    - 黄金 (XAU/USD)
    - 离岸人民币 (USD/CNH)
- **新闻抓取**:
  - 东方财富网、财联社、华尔街见闻和微博热搜的实时新闻
- **异步架构**:
  - 基于 `asyncio` 和 `Playwright` 的异步核心，实现高效的并发数据抓取。
- **健壮的错误处理**:
  - 为每个爬取任务提供独立的异常处理，确保单个网站的失败不影响整体运行。
- **反爬虫对策**:
  - 模拟真实用户行为，设置 User-Agent 和其他浏览器指纹，并使用持久化用户数据 (`user_data`) 来维持登录状态和 cookies。
- **API接口**:
  - 使用 `FastAPI` 提供两个主要的API端点：
    - `/scrape`: 获取所有金融市场的聚合数据。
    - `/news`: 根据日期范围获取财经新闻。
- **容器化部署**:
  - 提供 `Dockerfile`，可一键构建和部署，简化了环境配置。

## 技术栈

- **后端**: Python 3
- **Web框架**: FastAPI
- **Web抓取**: Playwright
- **数据处理**: Pandas
- **异步网络**: aiohttp, asyncio
- **容器化**: Docker

## 项目结构

```
.
├── app.py                  # FastAPI 应用入口
├── market_scraper.py       # 核心金融数据爬虫
├── newsCrawer.py           # 新闻爬虫模块
├── tonghuashun_stats.py    # 同花顺数据抓取模块
├── requirements.txt        # Python 依赖项
├── Dockerfile              # Docker 配置文件
└── user_data/              # 浏览器用户数据目录 (用于维持会话)
```

## 安装和运行

### 1. 本地运行

**前置条件**:
- Python 3.8+
- 安装 Poetry (推荐) 或 pip

**步骤**:

1.  **克隆项目**:
    ```bash
    git clone https://github.com/your-username/playwright_scraper_project.git
    cd playwright_scraper_project
    ```

2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **安装 Playwright 浏览器驱动**:
    ```bash
    playwright install --with-deps
    ```

4.  **运行应用**:
    ```bash
    uvicorn app:app --host 0.0.0.0 --port 8100 --reload
    ```
    `--reload` 参数可以在代码变更时自动重启服务，便于开发。

### 2. Docker 运行

**前置条件**:
- Docker 已安装并正在运行

**步骤**:

1.  **构建 Docker 镜像**:
    ```bash
    docker build -t market-scraper-api .
    ```

2.  **运行 Docker 容器**:
    ```bash
    docker run -d -p 8100:8100 --name market-scraper market-scraper-api
    ```
    这将在后台启动一个名为 `market-scraper` 的容器，并将容器的8100端口映射到主机的8100端口。

## API 使用说明

应用启动后，API将在 `http://localhost:8100` 上可用。

### 1. 获取金融数据

- **端点**: `GET /scrape`
- **描述**: 获取所有配置的金融市场数据。
- **查询参数**:
  - `time` (string, required): 时间参数，可以是任何可被 `dateutil` 解析的格式 (例如, `2025-07-08T12:00:00`)。
- **示例请求**:
  ```bash
  curl "http://localhost:8100/scrape?time=2025-07-08T12:00:00"
  ```

### 2. 获取新闻

- **端点**: `GET /news`
- **描述**: 根据指定的日期范围获取新闻。
- **查询参数**:
  - `start` (string, required): 起始日期，格式为 `YYYY-MM-DD`。
  - `end` (string, required): 结束日期，格式为 `YYYY-MM-DD`。
- **示例请求**:
  ```bash
  curl "http://localhost:8100/news?start=2025-07-01&end=2025-07-08"
  ```

## 注意事项

- **用户数据**: 项目使用 `user_data` 目录来存储浏览器会话信息。这有助于绕过某些网站的登录墙和反爬虫机制。首次运行时，此目录会自动创建。
- **反爬虫**: 尽管项目采取了一些反爬虫措施，但网站的结构和反爬虫策略可能会随时改变。如果爬虫失效，可能需要更新 `market_scraper.py` 和 `newsCrawer.py` 中的选择器。
- **调试**: 在 `market_scraper.py` 的 `scrape_financial_data` 函数中，可以将 `debug` 参数设置为 `True` (`headless=not debug`)，这样在运行时会显示浏览器界面，便于调试。
