# macOS 部署指南

本指南详细说明如何在macOS系统上部署和运行金融数据爬虫项目。

## 系统要求

- macOS 10.14+ (推荐 macOS 11.0+)
- Python 3.8+ (推荐 Python 3.9-3.11)
- Homebrew (推荐)
- 至少 8GB RAM (音频处理功能需要)
- 10GB+ 磁盘空间 (用于模型和依赖)

## 安装步骤

### 1. 系统依赖安装

```bash
# 安装 Homebrew (如果没有)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装系统级依赖
brew install python@3.11
brew install mysql
brew install portaudio    # 音频处理必需
brew install ffmpeg       # 音频格式转换
brew install git
```

### 2. Python 环境设置

```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel
```

### 3. PyTorch 安装 (重要!)

根据你的Mac型号选择：

#### Intel Mac:
```bash
pip install torch torchvision torchaudio
```

#### Apple Silicon Mac (M1/M2/M3):
```bash
# 推荐使用Metal Performance Shaders后端
pip install torch torchvision torchaudio
```

### 4. 音频处理依赖

```bash
# 核心音频库
pip install librosa soundfile numpy

# 可能需要的系统库
brew install libsndfile
```

### 5. 安装项目依赖

```bash
# 基础依赖
pip install -r requirements.txt

# Playwright 浏览器
playwright install --with-deps chromium

# 特殊依赖 (可能需要从源安装)
pip install git+https://github.com/linto-ai/whisper-timestamped.git
pip install whisperx
pip install forcealign
```

### 6. MySQL 配置

```bash
# 启动MySQL服务
brew services start mysql

# 创建数据库
mysql -u root -p < database_setup.sql
```

### 7. 配置文件设置

```bash
# 复制环境配置
cp .env.example .env

# 编辑配置文件
nano .env
```

在 `.env` 文件中设置：
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_DATABASE=financial_scraper
```

## 特殊配置调整

### 1. User-Agent 适配

建议修改爬虫的User-Agent为macOS版本：

```python
# 将Windows UA替换为macOS UA
user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
```

### 2. 文件路径兼容性

项目中的路径处理已经使用 `os.path.join()`, 在macOS上应该正常工作。

### 3. 权限设置

```bash
# 给Python脚本执行权限
chmod +x *.py

# 确保目录写权限
mkdir -p user_data generated_videos temp_html models
chmod 755 user_data generated_videos temp_html models
```

## 测试安装

### 1. 基础功能测试

```bash
# 测试数据库连接
python -c "from database import get_database_manager; print('DB连接:', get_database_manager().test_connection())"

# 测试PyTorch
python pytorch_version_check.py

# 测试模型加载
python checkmodels.py
```

### 2. 启动服务

```bash
# 启动API服务
uvicorn app:app --host 0.0.0.0 --port 8100 --reload
```

### 3. 功能测试

```bash
# 测试爬虫功能 (不包含音频处理)
curl "http://localhost:8100/scrape?time=2025-01-01T10:00:00"

# 测试历史记录
curl "http://localhost:8100/scrape/history"
```

## 常见问题解决

### 问题 1: PyTorch 安装失败
```bash
# 清理缓存重试
pip cache purge
pip install torch --no-cache-dir
```

### 问题 2: 音频库错误
```bash
# 重新安装音频依赖
brew reinstall portaudio libsndfile
pip uninstall librosa soundfile
pip install librosa soundfile --no-cache-dir
```

### 问题 3: Playwright 浏览器问题
```bash
# 重新安装浏览器
playwright uninstall
playwright install --with-deps chromium
```

### 问题 4: MySQL 连接错误
```bash
# 检查MySQL状态
brew services list | grep mysql

# 重启MySQL
brew services restart mysql
```

### 问题 5: 权限错误
```bash
# 修复目录权限
sudo chown -R $(whoami) ./user_data ./generated_videos ./temp_html
```

## 性能优化建议

### Apple Silicon Mac 优化

```bash
# 如果使用M1/M2/M3芯片，可以启用MPS加速
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

### 内存优化

对于内存较小的Mac，可以调整音频处理参数：

```python
# 在 app.py 中调整批处理大小
result = model.transcribe(
    audio, 
    batch_size=2,  # 降低批处理大小
    chunk_size=4,  # 降低块大小
    print_progress=True
)
```

## Docker 替代方案

如果原生安装遇到问题，可以使用Docker：

```bash
# 构建镜像 (需要调整Dockerfile适配macOS)
docker build -t market-scraper-api .

# 运行容器
docker run -d -p 8100:8100 --name market-scraper market-scraper-api
```

## 自动化脚本

创建启动脚本 `start_macos.sh`:

```bash
#!/bin/bash
set -e

echo "启动 macOS 金融爬虫服务..."

# 激活虚拟环境
source venv/bin/activate

# 检查MySQL
if ! brew services list | grep mysql | grep started > /dev/null; then
    echo "启动 MySQL 服务..."
    brew services start mysql
fi

# 启动应用
echo "启动 FastAPI 服务..."
uvicorn app:app --host 0.0.0.0 --port 8100 --reload
```

```bash
chmod +x start_macos.sh
./start_macos.sh
```

## 故障排除日志

如果遇到问题，可以启用详细日志：

```bash
# 设置详细日志
export LOG_LEVEL=DEBUG
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 运行应用
python app.py
```

---

**注意**: 音频处理功能是最复杂的部分，如果只需要爬虫和数据存储功能，可以暂时跳过音频相关的依赖安装。