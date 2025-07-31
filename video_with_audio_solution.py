#!/usr/bin/env python3
"""
视频+音频录制解决方案
解决Playwright不支持音频录制的问题
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional, Tuple
import subprocess
import aiofiles
import aiohttp
from playwright.async_api import async_playwright

class VideoAudioRecorder:
    """视频+音频录制器"""
    
    def __init__(self):
        self.temp_files = []
    
    async def record_html_with_audio(
        self, 
        html_path: str, 
        audio_url: str, 
        duration: float,
        play_button_selector: Optional[str] = None
    ) -> str:
        """录制HTML页面视频并合成音频"""
        
        try:
            # 1. 下载音频文件
            audio_path = await self._download_audio(audio_url)
            
            # 2. 录制视频（无音频）
            video_path = await self._record_video_only(html_path, duration, play_button_selector)
            
            # 3. 合成视频和音频
            final_video_path = await self._merge_video_audio(video_path, audio_path, duration)
            
            return final_video_path
            
        finally:
            # 清理临时文件
            await self._cleanup_temp_files()
    
    async def _download_audio(self, audio_url: str) -> str:
        """下载音频文件"""
        print(f"正在下载音频: {audio_url}")
        
        # 生成临时音频文件名
        audio_filename = f"temp_audio_{uuid.uuid4().hex[:8]}.wav"
        audio_path = os.path.join(tempfile.gettempdir(), audio_filename)
        self.temp_files.append(audio_path)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(audio_url) as response:
                if response.status != 200:
                    raise Exception(f"音频下载失败: HTTP {response.status}")
                
                async with aiofiles.open(audio_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
        
        print(f"音频下载完成: {audio_path}")
        return audio_path
    
    async def _record_video_only(
        self, 
        html_path: str, 
        duration: float,
        play_button_selector: Optional[str] = None
    ) -> str:
        """录制视频（无音频）"""
        print("正在录制视频（静音）...")
        
        # 生成临时视频文件名
        video_filename = f"temp_video_{uuid.uuid4().hex[:8]}.webm"
        video_dir = tempfile.gettempdir()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--autoplay-policy=no-user-gesture-required',  # 允许自动播放
                    '--disable-web-security',  # 禁用web安全（测试用）
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                record_video_dir=video_dir,
                record_video_size={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # 打开HTML页面
            abs_html_path = os.path.abspath(html_path)
            file_url = f"file:///{abs_html_path.replace(os.sep, '/')}"
            await page.goto(file_url, wait_until='domcontentloaded', timeout=30000)
            
            # 等待页面加载
            await page.wait_for_timeout(2000)
            
            # 尝试触发音频播放
            await self._trigger_audio_play(page, play_button_selector)
            
            # 录制指定时长
            record_duration = int((duration + 1) * 1000)
            print(f"开始录制，时长: {record_duration/1000:.1f}秒")
            await page.wait_for_timeout(record_duration)
            
            # 关闭浏览器以保存视频
            await context.close()
            await browser.close()
            
            # 等待视频文件生成
            await asyncio.sleep(2)
            
            # 查找生成的视频文件
            video_files = [
                f for f in os.listdir(video_dir) 
                if f.endswith('.webm') and 'temp_video_' in f
            ]
            
            if video_files:
                # 找到最新的视频文件
                latest_video = max(
                    [os.path.join(video_dir, f) for f in video_files], 
                    key=os.path.getctime
                )
                self.temp_files.append(latest_video)
                print(f"视频录制完成: {latest_video}")
                return latest_video
            else:
                # 查找Playwright自动生成的视频文件
                all_videos = [
                    f for f in os.listdir(video_dir) 
                    if f.endswith('.webm')
                ]
                if all_videos:
                    latest_video = max(
                        [os.path.join(video_dir, f) for f in all_videos], 
                        key=os.path.getctime
                    )
                    self.temp_files.append(latest_video)
                    print(f"找到生成的视频: {latest_video}")
                    return latest_video
                
            raise Exception("视频录制失败，未找到生成的视频文件")
    
    async def _trigger_audio_play(self, page, play_button_selector: Optional[str] = None):
        """触发音频播放"""
        try:
            if play_button_selector:
                # 使用用户指定的选择器
                await page.click(play_button_selector, timeout=5000)
                print(f"点击了播放按钮: {play_button_selector}")
            else:
                # 尝试多种播放触发方式
                play_methods = [
                    # 点击audio元素
                    lambda: page.click('audio', timeout=2000),
                    # 调用audio.play()
                    lambda: page.evaluate('document.querySelector("audio")?.play()'),
                    # 点击播放按钮
                    lambda: page.click('[aria-label*="play"], [aria-label*="播放"]', timeout=2000),
                    lambda: page.click('button:has-text("播放"), button:has-text("Play")', timeout=2000),
                    # 按空格键
                    lambda: page.keyboard.press('Space'),
                    # 点击页面中心
                    lambda: page.click('body'),
                ]
                
                for i, method in enumerate(play_methods):
                    try:
                        await method()
                        print(f"音频播放触发方式 {i+1} 执行成功")
                        await page.wait_for_timeout(500)
                        break
                    except:
                        continue
                        
        except Exception as e:
            print(f"音频播放触发失败: {e}")
    
    async def _merge_video_audio(self, video_path: str, audio_path: str, duration: float) -> str:
        """使用FFmpeg合成视频和音频"""
        print("正在合成视频和音频...")
        
        # 生成最终视频文件名
        final_filename = f"video_with_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp4"
        final_path = os.path.join("generated_videos", final_filename)
        
        # 确保输出目录存在
        os.makedirs("generated_videos", exist_ok=True)
        
        # FFmpeg命令
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', video_path,  # 输入视频
            '-i', audio_path,  # 输入音频
            '-c:v', 'libx264',  # 视频编码器
            '-c:a', 'aac',      # 音频编码器
            '-shortest',        # 以最短的流为准
            '-y',               # 覆盖输出文件
            final_path
        ]
        
        try:
            # 执行FFmpeg命令
            result = subprocess.run(
                ffmpeg_cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print(f"视频合成成功: {final_path}")
                return final_path
            else:
                raise Exception(f"FFmpeg执行失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            raise Exception("FFmpeg执行超时")
        except FileNotFoundError:
            raise Exception("FFmpeg未安装或不在PATH中")
    
    async def _cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"已清理临时文件: {temp_file}")
            except Exception as e:
                print(f"清理临时文件失败 {temp_file}: {e}")

# 测试函数
async def test_video_audio_recording():
    """测试视频音频录制"""
    recorder = VideoAudioRecorder()
    
    # 创建测试HTML文件
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>测试音频播放</title>
    </head>
    <body>
        <h1>音频播放测试</h1>
        <audio id="testAudio" controls autoplay>
            <source src="https://example.com/test.mp3" type="audio/mpeg">
            您的浏览器不支持音频播放。
        </audio>
        <button id="playBtn" onclick="document.getElementById('testAudio').play()">播放</button>
        <script>
            // 自动播放
            window.addEventListener('load', function() {
                setTimeout(() => {
                    const audio = document.getElementById('testAudio');
                    audio.play().catch(e => console.log('自动播放失败:', e));
                }, 1000);
            });
        </script>
    </body>
    </html>
    """
    
    # 保存测试HTML
    test_html_path = "test_audio.html"
    with open(test_html_path, 'w', encoding='utf-8') as f:
        f.write(test_html)
    
    try:
        final_video = await recorder.record_html_with_audio(
            html_path=test_html_path,
            audio_url="https://example.com/test-audio.mp3",  # 替换为实际音频URL
            duration=10.0,
            play_button_selector="#playBtn"
        )
        
        print(f"最终视频文件: {final_video}")
        return final_video
        
    finally:
        # 清理测试文件
        if os.path.exists(test_html_path):
            os.unlink(test_html_path)

if __name__ == "__main__":
    asyncio.run(test_video_audio_recording())