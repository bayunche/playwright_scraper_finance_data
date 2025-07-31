# 视频+音频录制解决方案

## 问题分析

### 🎯 **核心问题**
Playwright的原生录屏功能 **不支持音频录制**，这是一个已知的限制。

### 📋 **技术原因**
1. **Playwright限制**: `record_video_dir` 和 `record_video_size` 只录制视频，不包含音频轨道
2. **浏览器安全策略**: 浏览器对音频录制有严格的安全限制
3. **跨域问题**: 音频文件和HTML页面可能存在跨域限制

## 解决方案

### 🛠️ **解决方案1: FFmpeg视频音频合成（推荐）**

**原理**: 分别录制视频和下载音频，然后使用FFmpeg合成

**优点**:
- 音频质量最佳（原始音频文件）
- 支持各种音频格式
- 视频音频完全同步

**缺点**:
- 需要安装FFmpeg
- 处理时间较长

**实现**:
```python
# 新增API接口
POST /generate-video-with-audio

# 处理流程
1. 下载原始音频文件
2. 录制HTML页面视频（静音）
3. 使用FFmpeg合成视频+音频
4. 返回最终MP4文件
```

### 🔧 **解决方案2: 优化现有录屏（临时方案）**

**原理**: 优化浏览器参数，尝试触发音频播放

**修改**:
```python
browser = await p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox', 
        '--disable-dev-shm-usage',
        '--autoplay-policy=no-user-gesture-required',  # 允许自动播放
        '--disable-web-security',  # 禁用安全限制（仅测试）
    ]
)
```

**局限性**: 仍然无法录制到音频轨道

## 使用指南

### 📦 **环境要求**

1. **基础依赖**:
   ```bash
   pip install aiofiles
   ```

2. **FFmpeg安装** (方案1必需):
   ```bash
   # Windows (使用chocolatey)
   choco install ffmpeg
   
   # macOS (使用homebrew)
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   ```

3. **验证FFmpeg**:
   ```bash
   ffmpeg -version
   ```

### 🚀 **API使用**

#### 方案1: 带音频的视频生成
```bash
curl -X POST "http://localhost:8100/generate-video-with-audio" \
-H "Content-Type: application/json" \
-d '{
  "html_content": "<html>...</html>",
  "audio_url": "https://example.com/audio.mp3",
  "play_button_selector": "#playButton"
}'
```

#### 方案2: 仅视频录制（原有功能）
```bash
curl -X POST "http://localhost:8100/generate-video" \
-H "Content-Type: application/json" \
-d '{
  "html_content": "<html>...</html>",
  "audio_url": "https://example.com/audio.mp3"
}'
```

### 📋 **接口对比**

| 接口 | 音频支持 | 输出格式 | FFmpeg依赖 | 处理时间 |
|------|----------|----------|------------|----------|
| `/generate-video` | ❌ | .webm | ❌ | 快 |
| `/generate-video-with-audio` | ✅ | .mp4 | ✅ | 较慢 |

## 最佳实践

### 🎵 **HTML音频页面优化**

```html
<!DOCTYPE html>
<html>
<head>
    <title>音频播放页面</title>
</head>
<body>
    <audio id="audioPlayer" controls>
        <source src="audio.mp3" type="audio/mpeg">
    </audio>
    <button id="playBtn">播放</button>
    
    <script>
        // 自动播放逻辑
        window.addEventListener('DOMContentLoaded', function() {
            const audio = document.getElementById('audioPlayer');
            const playBtn = document.getElementById('playBtn');
            
            // 多种播放触发方式
            setTimeout(() => {
                audio.play().catch(console.error);
            }, 1000);
            
            playBtn.addEventListener('click', () => {
                audio.play();
            });
        });
    </script>
</body>
</html>
```

### ⚡ **性能优化建议**

1. **音频预处理**: 使用标准格式（MP3, WAV）
2. **视频参数**: 适当降低分辨率和帧率
3. **并发控制**: 限制同时录制的任务数量
4. **缓存机制**: 缓存处理过的音频文件

### 🔍 **故障排除**

#### FFmpeg相关问题
```bash
# 检查FFmpeg是否在PATH中
ffmpeg -version

# 手动测试合成
ffmpeg -i video.webm -i audio.mp3 -c:v libx264 -c:a aac -shortest output.mp4
```

#### 音频播放问题
1. 检查音频URL是否可访问
2. 确认音频格式支持
3. 验证CORS策略
4. 尝试不同的播放按钮选择器

#### 浏览器权限问题
```python
# 添加更多浏览器参数
args=[
    '--no-sandbox',
    '--disable-dev-shm-usage', 
    '--autoplay-policy=no-user-gesture-required',
    '--disable-web-security',
    '--disable-features=VizDisplayCompositor',
    '--allow-running-insecure-content'
]
```

## 未来改进

### 🔮 **技术路线**

1. **实时音频录制**: 探索WebRTC音频捕获
2. **云端处理**: 使用云服务进行视频音频合成
3. **更多格式支持**: 支持更多音频和视频格式
4. **批量处理**: 支持批量视频生成

### 📈 **性能监控**

建议监控以下指标:
- 视频录制时间
- 音频下载时间  
- FFmpeg处理时间
- 最终文件大小
- 错误率统计

---

**总结**: 虽然Playwright原生不支持音频录制，但通过FFmpeg合成的方案可以完美解决这个问题，生成高质量的视频+音频文件。