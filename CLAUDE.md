# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于Playwright的金融数据爬虫和API项目，主要用于抓取美股、A股和加密货币市场数据，同时提供新闻爬取和语音处理功能。

## 核心架构

### Web爬虫模块
- `market_scraper.py`: 核心金融数据爬虫，使用Playwright异步抓取美股、A股、加密货币数据
- `newsCrawer.py`: 新闻爬虫模块，抓取东方财富、财联社等财经新闻
- `tonghuashun_stats.py`: 同花顺数据抓取专用模块，获取A股统计数据

### API服务
- `app.py`: FastAPI应用入口，提供RESTful API接口
  - `/scrape`: 获取金融市场数据
  - `/news`: 获取财经新闻  
  - `/align`: 音频文本对齐服务

### 语音处理模块
- 集成WhisperX和ForceAlign进行音频转录和对齐
- 支持中英文语音识别和时间戳对齐
- 使用wav2vec2模型进行强制对齐

## 常用开发命令

### 本地运行
```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install --with-deps

# 启动开发服务器
uvicorn app:app --host 0.0.0.0 --port 8100 --reload
```

### Docker部署
```bash
# 构建镜像
docker build -t market-scraper-api .

# 运行容器
docker run -d -p 8100:8100 --name market-scraper market-scraper-api
```

### 测试
```bash
# 测试加密货币爬虫
python test_crypto_scraper.py

# 检查CUDA环境
python cuda_test.py

# 验证模型
python checkmodels.py
```

## 开发注意事项

### 反爬虫处理
- 所有爬虫都使用持久化用户数据(`user_data/`目录)
- 设置真实的User-Agent和浏览器指纹
- 使用适当的延时和错误重试机制
- 调试时可在爬虫函数中设置`headless=False`显示浏览器界面

### 异步架构
- 所有网络请求都基于`asyncio`和`aiohttp`
- 使用Playwright的异步API(`async_playwright`)
- 爬虫任务之间相互独立，单个失败不影响整体

### 数据源配置
- Yahoo Finance: 美股板块和个股数据
- MarketWatch: 备用美股数据源
- 同花顺: A股市场数据
- 东方财富API: 财经新闻数据
- CoinGecko: 加密货币价格数据

### 环境依赖
- Python 3.8+
- Playwright (需要浏览器驱动)
- PyTorch (用于语音处理)
- CUDA支持(可选，提升语音处理性能)

### 目录结构
- `user_data/`: Playwright浏览器用户数据目录
- `models/`: 语音模型存储目录  
- `wxauto_logs/`: 应用日志目录
- `.venv/`: Python虚拟环境
- `__pycache__/`: Python字节码缓存

### 调试工具
- `debug.py`: 通用调试工具
- `node_checker.py`: Node.js环境检查
- `volume.py`: 音频处理工具
- 爬虫失败时会自动保存调试截图

## API接口说明

### GET /scrape
获取实时金融市场数据，包括：
- 美股三大指数
- A股市场数据
- 加密货币价格
- 宏观经济指标

### GET /news  
根据日期范围获取财经新闻

### POST /align
音频文本对齐服务，支持中英文语音处理

## 部署考虑

项目已完全容器化，支持一键Docker部署。容器内包含完整的Playwright浏览器环境和Python运行时。在生产环境中注意：
- 设置合适的资源限制
- 配置日志收集
- 监控爬虫成功率
- 定期清理用户数据缓存