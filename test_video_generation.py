#!/usr/bin/env python3
"""
测试视频生成功能的脚本
"""
import asyncio
import aiohttp
import json
import sys
import os

async def test_video_generation():
    """测试视频生成API"""
    
    # 读取测试HTML文件
    html_file_path = "test_html.html"
    if not os.path.exists(html_file_path):
        print(f"测试HTML文件不存在: {html_file_path}")
        return False
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 测试音频URL（使用一个短音频文件）
    # 你可以替换为任何可访问的音频文件URL
    audio_url = "https://www.soundjay.com/misc/sounds/fail-buzzer-02.wav"
    
    # 准备请求数据
    request_data = {
        "html_content": html_content,
        "audio_url": audio_url
    }
    
    print("开始测试视频生成功能...")
    print(f"HTML内容长度: {len(html_content)} 字符")
    print(f"音频URL: {audio_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 发送POST请求到API
            async with session.post(
                "http://localhost:8100/generate-video",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    print("\n✅ 请求成功!")
                    print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
                    if result.get("success"):
                        print(f"\n🎉 视频生成成功!")
                        print(f"视频URL: {result.get('video_url')}")
                        print(f"视频时长: {result.get('duration'):.2f}秒")
                        print(f"文件大小: {result.get('file_size')} 字节")
                        return True
                    else:
                        print(f"\n❌ 视频生成失败: {result.get('error')}")
                        return False
                        
                else:
                    error_text = await response.text()
                    print(f"\n❌ API请求失败 (状态码: {response.status})")
                    print(f"错误信息: {error_text}")
                    return False
                    
    except aiohttp.ClientError as e:
        print(f"\n❌ 网络请求失败: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        return False

async def check_server_health():
    """检查服务器是否正在运行"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8100/docs") as response:
                if response.status == 200:
                    print("✅ 服务器正在运行")
                    return True
                else:
                    print(f"❌ 服务器响应异常 (状态码: {response.status})")
                    return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {str(e)}")
        print("请确保运行以下命令启动服务器:")
        print("uvicorn app:app --host 0.0.0.0 --port 8100 --reload")
        return False

async def main():
    """主测试函数"""
    print("=" * 50)
    print("HTML+音频录屏功能测试")
    print("=" * 50)
    
    # 检查服务器健康状态
    print("\n1. 检查服务器状态...")
    if not await check_server_health():
        return
    
    # 测试视频生成功能
    print("\n2. 测试视频生成功能...")
    success = await test_video_generation()
    
    if success:
        print("\n🎉 所有测试通过!")
    else:
        print("\n❌ 测试失败")
        sys.exit(1)

if __name__ == "__main__":
    # 在Windows上设置事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())