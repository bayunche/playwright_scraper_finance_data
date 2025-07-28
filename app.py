import sys
from fastapi import FastAPI, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from dateutil import parser as date_parser
from datetime import datetime
import asyncio
from market_scraper import scrape_financial_data
from newsCrawer import get_news

from whisper_timestamped import transcribe_timestamped
import tempfile
import json
from forcealign import ForceAlign
import whisperx
import torch
from pydantic import BaseModel
from typing import List, Tuple, Dict, Optional
import aiohttp
import os
import uuid
import librosa
import soundfile as sf
import numpy as np
from pydub import AudioSegment
import io
import nltk
from nltk.data import find


import re
import jieba
from difflib import SequenceMatcher

# 在Windows上设置事件循环策略
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

# 挂载静态文件服务用于视频下载
app.mount("/videos", StaticFiles(directory="generated_videos"), name="videos")

class DialogueUnit(BaseModel):
    text: str
    model_name: str
    emotion: str
    speed_facter: float
    text_lang: str

class AlignRequest(BaseModel):
    audio_url: str
    transcript: Optional[List[DialogueUnit]] = None
    transcript_text: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    html_content: str
    audio_url: str

class VideoGenerationResponse(BaseModel):
    success: bool
    video_url: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
# 改进的对齐算法类
class ImprovedAlignment:
    def __init__(self):
        # 初始化中文分词
        jieba.initialize()
        
    def preprocess_text(self, text: str) -> str:
        """文本预处理"""
        if not text:
            return ""
        
        # 移除中文标点
        text = re.sub(r'[，。！？；：""''（）【】《》、]', '', text)
        # 移除英文标点
        text = re.sub(r'[,.!?;:"()[\]{}<>]', '', text)
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()
    
    def chinese_tokenize(self, text: str) -> List[str]:
        """中文分词"""
        processed_text = self.preprocess_text(text)
        if not processed_text:
            return []
            
        if self.is_chinese(text):
            # 中文分词
            tokens = list(jieba.cut(processed_text))
            return [token for token in tokens if token.strip()]
        else:
            # 英文分词
            return processed_text.split()
    
    def is_chinese(self, text: str) -> bool:
        """检测是否为中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    def calculate_similarity(self, word1: str, word2: str) -> float:
        """计算词语相似度"""
        if not word1 or not word2:
            return 0.0
        
        # 基本字符串相似度
        similarity = SequenceMatcher(None, word1, word2).ratio()
        
        # 如果是中文，增加字符级别匹配
        if self.is_chinese(word1) and self.is_chinese(word2):
            char_similarity = self.chinese_char_similarity(word1, word2)
            similarity = max(similarity, char_similarity)
        
        # 如果长度相差太大，降低相似度
        len_diff = abs(len(word1) - len(word2))
        max_len = max(len(word1), len(word2))
        if max_len > 0:
            len_penalty = len_diff / max_len
            similarity *= (1 - len_penalty * 0.3)
        
        return similarity
    
    def chinese_char_similarity(self, word1: str, word2: str) -> float:
        """计算中文字符相似度"""
        if len(word1) == 0 or len(word2) == 0:
            return 0.0
        
        # 字符重叠度
        chars1 = set(word1)
        chars2 = set(word2)
        intersection = chars1 & chars2
        union = chars1 | chars2
        
        if not union:
            return 0.0
        
        jaccard = len(intersection) / len(union)
        
        # 考虑字符顺序
        sequence_sim = SequenceMatcher(None, word1, word2).ratio()
        
        # 综合评分
        return (jaccard + sequence_sim) / 2
    
    def sequence_alignment(self, target_text: str, source_words: List[Tuple[str, float, float]], 
                          threshold: float = 0.3) -> List[Dict]:
        """序列对齐算法"""
        target_words = self.chinese_tokenize(target_text)
        if not target_words or not source_words:
            return []
        
        # 预处理源词语
        processed_source = []
        for word, start, end in source_words:
            processed_word = self.preprocess_text(word)
            if processed_word:
                processed_source.append((processed_word, start, end))
        
        if not processed_source:
            return []
        
        # 动态规划对齐
        n, m = len(target_words), len(processed_source)
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        parent = [[(-1, -1)] * (m + 1) for _ in range(n + 1)]
        
        # 填充DP表
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                # 匹配当前词
                similarity = self.calculate_similarity(target_words[i-1], processed_source[j-1][0])
                match_score = dp[i-1][j-1] + similarity
                
                # 跳过源词（插入）
                skip_source_score = dp[i][j-1] - 0.1
                
                # 跳过目标词（删除）
                skip_target_score = dp[i-1][j] - 0.3
                
                # 选择最佳
                if match_score >= skip_source_score and match_score >= skip_target_score:
                    dp[i][j] = match_score
                    parent[i][j] = (i-1, j-1)
                elif skip_source_score >= skip_target_score:
                    dp[i][j] = skip_source_score
                    parent[i][j] = (i, j-1)
                else:
                    dp[i][j] = skip_target_score
                    parent[i][j] = (i-1, j)
        
        # 回溯找到最佳对齐路径
        alignment = []
        i, j = n, m
        
        while i > 0 and j > 0:
            prev_i, prev_j = parent[i][j]
            
            if prev_i == i - 1 and prev_j == j - 1:
                # 匹配
                similarity = self.calculate_similarity(target_words[i-1], processed_source[j-1][0])
                if similarity >= threshold:
                    alignment.append({
                        'target_word': target_words[i-1],
                        'source_word': processed_source[j-1][0],
                        'original_word': source_words[j-1][0],
                        'start': processed_source[j-1][1],
                        'end': processed_source[j-1][2],
                        'confidence': similarity
                    })
            
            i, j = prev_i, prev_j
        
        alignment.reverse()
        return alignment
    
    def fuzzy_match_fallback(self, target_text: str, source_words: List[Tuple[str, float, float]], 
                            threshold: float = 0.4) -> List[Dict]:
        """模糊匹配作为后备方案"""
        target_words = self.chinese_tokenize(target_text)
        if not target_words:
            return []
        
        matched_words = []
        used_indices = set()
        
        for target_word in target_words:
            best_match = None
            best_score = 0
            best_index = -1
            
            for i, (source_word, start, end) in enumerate(source_words):
                if i in used_indices:
                    continue
                
                processed_source = self.preprocess_text(source_word)
                similarity = self.calculate_similarity(target_word, processed_source)
                
                if similarity > best_score and similarity >= threshold:
                    best_match = {
                        'target_word': target_word,
                        'source_word': processed_source,
                        'original_word': source_word,
                        'start': start,
                        'end': end,
                        'confidence': similarity
                    }
                    best_score = similarity
                    best_index = i
            
            if best_match:
                matched_words.append(best_match)
                used_indices.add(best_index)
        
        return matched_words
    
    def interpolate_timing(self, alignment_result: List[Dict], unit_text: str) -> Tuple[float, float]:
        """时间插值优化"""
        if not alignment_result:
            return 0.0, 0.0
        
        # 基本时间边界
        start_time = alignment_result[0]['start']
        end_time = alignment_result[-1]['end']
        
        # 计算平均每字符时间
        total_chars = sum(len(item['target_word']) for item in alignment_result)
        if total_chars > 0:
            char_duration = (end_time - start_time) / total_chars
            
            # 根据完整文本长度调整
            full_text_chars = len(self.preprocess_text(unit_text))
            if full_text_chars > total_chars:
                # 如果完整文本更长，扩展时间
                additional_time = (full_text_chars - total_chars) * char_duration
                end_time += additional_time * 0.5  # 保守扩展
        
        return start_time, end_time
    
    def smooth_timestamps(self, segments: List[Dict], smooth_factor: float = 0.1) -> List[Dict]:
        """平滑时间戳，避免重叠"""
        if len(segments) <= 1:
            return segments
        
        smoothed = []
        for i, segment in enumerate(segments):
            current_segment = segment.copy()
            
            if i == 0:
                smoothed.append(current_segment)
                continue
            
            # 检查与前一个段的重叠
            prev_end = smoothed[-1]['end']
            current_start = current_segment['start']
            
            if current_start < prev_end:
                # 存在重叠，调整边界
                gap = prev_end - current_start
                mid_point = prev_end - gap * smooth_factor
                
                smoothed[-1]['end'] = mid_point
                current_segment['start'] = mid_point
            
            smoothed.append(current_segment)
        
        return smoothed

# 改进的对齐函数
def improved_align_segments(transcript: List[DialogueUnit], align_words: List, 
                           audio_duration: float) -> List[Dict]:
    """改进的段落对齐函数"""
    
    aligner = ImprovedAlignment()
    words = [(w.word, w.time_start, w.time_end) for w in align_words]
    segments = []
    
    if not words:
        return segments
    
    # 预处理所有词语
    processed_words = []
    for word, start, end in words:
        processed_word = aligner.preprocess_text(word)
        if processed_word:
            processed_words.append((word, start, end))
    
    current_word_index = 0
    
    for unit in transcript:
        if not unit.text.strip():
            continue
        
        # 获取可用的词语
        available_words = processed_words[current_word_index:]
        if not available_words:
            print(f"警告: 没有更多词语可用于对齐 '{unit.text}'")
            break
        
        # 首先尝试序列对齐
        alignment_result = aligner.sequence_alignment(unit.text, available_words, threshold=0.3)
        
        if alignment_result:
            # 序列对齐成功
            start_time, end_time = aligner.interpolate_timing(alignment_result, unit.text)
            
            # 计算平均置信度
            avg_confidence = sum(item['confidence'] for item in alignment_result) / len(alignment_result)
            
            # 更新当前词索引
            if alignment_result:
                last_word = alignment_result[-1]['original_word']
                for i, (word, _, _) in enumerate(available_words):
                    if word == last_word:
                        current_word_index += i + 1
                        break
            
            print(f"序列对齐成功: '{unit.text}' -> {start_time:.2f}-{end_time:.2f}s (置信度: {avg_confidence:.2f})")
            
        else:
            # 序列对齐失败，使用模糊匹配
            matched_words = aligner.fuzzy_match_fallback(unit.text, available_words, threshold=0.4)
            
            if matched_words:
                start_time = matched_words[0]['start']
                end_time = matched_words[-1]['end']
                
                # 更新当前词索引
                last_word = matched_words[-1]['original_word']
                for i, (word, _, _) in enumerate(available_words):
                    if word == last_word:
                        current_word_index += i + 1
                        break
                
                avg_confidence = sum(item['confidence'] for item in matched_words) / len(matched_words)
                print(f"模糊匹配成功: '{unit.text}' -> {start_time:.2f}-{end_time:.2f}s (置信度: {avg_confidence:.2f})")
            else:
                print(f"警告: 无法对齐文本 '{unit.text}'，跳过")
                continue
        
        # 确保时间合理性
        start_time = max(0, start_time)
        end_time = min(audio_duration, max(start_time + 0.1, end_time))
        
        if start_time < end_time:
            segments.append({
                "start": start_time,
                "end": end_time,
                "text": unit.text,
                "model_name": unit.model_name,
                "emotion": unit.emotion,
                "speed_facter": unit.speed_facter,
                "text_lang": unit.text_lang
            })
    
    # 应用时间平滑
    segments = aligner.smooth_timestamps(segments, smooth_factor=0.1)
    
    return segments

def pad_audio_if_needed(audio: np.ndarray, target_sr: int = 16000, min_duration: float = 0.5) -> np.ndarray:
    """
    如果音频太短，进行填充处理
    """
    min_samples = int(target_sr * min_duration)
    
    if len(audio) < min_samples:
        # 如果音频极短，用静音填充
        if len(audio) < target_sr * 0.1:  # 少于0.1秒
            pad_length = min_samples - len(audio)
            audio = np.pad(audio, (0, pad_length), mode='constant', constant_values=0)
        else:
            # 如果音频较短但有内容，重复音频内容
            repeat_count = int(np.ceil(min_samples / len(audio)))
            audio = np.tile(audio, repeat_count)[:min_samples]
    
    return audio

def ensure_nltk_data():
    """确保NLTK数据可用"""
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        print("下载NLTK数据...")
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)

def convert_audio_to_wav(audio_data: bytes, target_sr: int = 16000) -> Tuple[np.ndarray, str]:
    """
    转换音频数据为WAV格式
    """
    import librosa
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_file.write(audio_data)
        temp_input_path = temp_file.name
    
    try:
        # 使用librosa加载音频
        audio, sr = librosa.load(temp_input_path, sr=target_sr)
        
        # 音频增强
        audio = librosa.effects.preemphasis(audio)  # 预加重
        audio = librosa.util.normalize(audio)  # 归一化
        
        # 创建输出临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as output_file:
            temp_output_path = output_file.name
        
        # 保存处理后的音频
        sf.write(temp_output_path, audio, target_sr)
        
        return audio, temp_output_path
        
    finally:
        # 清理输入临时文件
        if os.path.exists(temp_input_path):
            os.unlink(temp_input_path)

# 主要的对齐API函数
async def align_audio_text(req: AlignRequest):
    """
    完整的音频文本对齐函数
    """
    temp_files = []
    
    try:
        # 解析 transcript_text
        if req.transcript_text:
            transcript_list = json.loads(req.transcript_text)
            req.transcript = [DialogueUnit(**item) for item in transcript_list]
        elif req.transcript is None:
            req.transcript = []

        # 下载音频
        print("正在下载音频文件...")
        async with aiohttp.ClientSession() as session:
            async with session.get(req.audio_url) as response:
                if response.status != 200:
                    return {"error": f"下载失败，HTTP状态码: {response.status}"}
                
                audio_data = await response.read()
                content_type = response.headers.get('content-type', '')
                print(f"下载完成，文件大小: {len(audio_data)} bytes, Content-Type: {content_type}")

        # 检查文件大小
        if len(audio_data) < 1000:
            return {"error": "音频文件过小，可能下载不完整"}

        # 转换音频格式
        print("正在转换音频格式...")
        try:
            audio, temp_wav_path = convert_audio_to_wav(audio_data, target_sr=16000)
            temp_files.append(temp_wav_path)
        except Exception as e:
            return {"error": f"音频格式转换失败: {str(e)}"}

        # 获取音频信息
        duration = len(audio) / 16000
        print(f"音频信息: {len(audio)} samples, {duration:.2f}s, 采样率: 16000Hz")
        
        # 检查音频长度
        MIN_DURATION = 0.3
        if duration < MIN_DURATION:
            return {"error": f"音频文件过短（{duration:.2f}s），需要至少 {MIN_DURATION}s"}
        
        # 对短音频进行填充
        if duration < 1.0:
            audio = pad_audio_if_needed(audio, target_sr=16000, min_duration=1.0)
            sf.write(temp_wav_path, audio, 16000)
            duration = len(audio) / 16000
            print(f"音频已填充至 {duration:.2f}s")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"使用设备: {device}")

        # ASR 转录
        compute_type = "float16" if device == "cuda" else "float32"
        
        try:
            print("正在加载 WhisperX 模型...")
            model = whisperx.load_model("large-v3", device=device, compute_type=compute_type)
            
            print("正在进行 ASR 转录...")
            result = model.transcribe(
                audio, 
                batch_size=4,
                chunk_size=6,
                print_progress=True
            )
            
            if not result.get("segments"):
                return {"error": "ASR 转录失败，未检测到语音内容"}
            
            detected_language = result.get("language", "zh")
            print(f"检测到的语言: {detected_language}")
            
            # 加载对齐模型
            print("正在加载对齐模型...")
            if detected_language == "zh":
                model_name = "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"
            else:
                model_name = None
            
            if model_name:
                try:
                    align_model, metadata = whisperx.load_align_model(
                        language_code=detected_language,
                        device=device,
                        model_name=model_name
                    )
                except:
                    print("指定模型加载失败，使用默认模型")
                    align_model, metadata = whisperx.load_align_model(
                        language_code=detected_language,
                        device=device
                    )
            else:
                align_model, metadata = whisperx.load_align_model(
                    language_code=detected_language,
                    device=device
                )
            
            print("正在进行强制对齐...")
            aligned = whisperx.align(
                result["segments"], 
                align_model, 
                metadata, 
                audio, 
                device=device,
                return_char_alignments=True,
                
            )
            
        except Exception as e:
            return {"error": f"ASR/对齐处理失败: {str(e)}"}

        # 提取ASR文本
        asr_segments = aligned["segments"]
        if not asr_segments:
            return {"error": "对齐失败，未获得有效的语音段"}
            
        asr_text = " ".join([seg["text"] for seg in asr_segments])
        print(f"ASR 识别文本: {asr_text}")

        # 使用 ForceAlign 进行整体对齐
        ref_text = " ".join([u.text for u in req.transcript])
        if not ref_text.strip():
            return {"error": "参考文本为空"}
            
        print(f"参考文本: {ref_text}")
        
        try:
            ensure_nltk_data()
            
            print("正在进行 ForceAlign 对齐...")
            fa = ForceAlign(audio_file=temp_wav_path, transcript=ref_text)
            align_words = fa.inference()
            
            if not align_words:
                return {"error": "ForceAlign 对齐失败"}
                
        except Exception as e:
            return {"error": f"ForceAlign 处理失败: {str(e)}"}

        # 使用改进的对齐算法
        print("正在使用改进算法进行段落对齐...")
        segments = improved_align_segments(req.transcript, align_words, duration)
        
        print(f"成功处理 {len(segments)} 个语音段")
        
        # 输出详细信息
        for i, segment in enumerate(segments):
            print(f"段落 {i+1}: {segment['start']:.2f}-{segment['end']:.2f}s | {segment['text']}")
        
        return {"segments": segments}
        
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        return {"error": f"处理过程中发生错误: {str(e)}"}
        
    finally:
        # 清理临时文件
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    print(f"已清理临时文件: {temp_file}")
                except Exception as e:
                    print(f"清理临时文件失败: {e}")

@app.post("/align")
async def align(req: AlignRequest):
    return await align_audio_text(req)

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

async def download_audio_and_get_duration(audio_url: str) -> Tuple[bytes, float]:
    """下载音频并获取时长"""
    async with aiohttp.ClientSession() as session:
        async with session.get(audio_url) as response:
            if response.status != 200:
                raise Exception(f"音频下载失败，HTTP状态码: {response.status}")
            
            audio_data = await response.read()
            
    # 使用librosa获取音频时长
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_file.write(audio_data)
        temp_path = temp_file.name
    
    try:
        # 加载音频获取时长
        audio, sr = librosa.load(temp_path, sr=None)
        duration = len(audio) / sr
        return audio_data, duration
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def save_html_file(html_content: str) -> str:
    """保存HTML内容到临时文件"""
    if not html_content or not html_content.strip():
        raise ValueError("HTML内容不能为空")
    
    # 生成唯一文件名
    unique_id = str(uuid.uuid4())[:8]
    filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{unique_id}.html"
    file_path = os.path.join("temp_html", filename)
    
    # 确保目录存在
    os.makedirs("temp_html", exist_ok=True)
    
    # 保存HTML文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML文件保存成功: {file_path}")
        return file_path
    except Exception as e:
        raise Exception(f"保存HTML文件失败: {str(e)}")

async def record_html_video(html_path: str, duration: float) -> str:
    """使用Playwright录制HTML页面视频"""
    from playwright.async_api import async_playwright
    
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML文件不存在: {html_path}")
    
    if duration <= 0:
        raise ValueError("音频时长必须大于0")
    
    # 生成视频文件名  
    unique_id = str(uuid.uuid4())[:8]
    video_filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{unique_id}.webm"
    video_path = os.path.join("generated_videos", video_filename)
    
    # 确保目录存在
    os.makedirs("generated_videos", exist_ok=True)
    
    browser = None
    context = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                record_video_dir="generated_videos",
                record_video_size={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # 获取绝对路径并转换为file URL
            abs_html_path = os.path.abspath(html_path)
            file_url = f"file:///{abs_html_path.replace(os.sep, '/')}"
            print(f"正在打开HTML页面: {file_url}")
            
            # 打开HTML页面
            await page.goto(file_url, wait_until='domcontentloaded', timeout=30000)
            
            # 等待页面完全加载
            await page.wait_for_timeout(2000)
            
            # 录制指定时长（加1秒缓冲）
            record_duration = int((duration + 1) * 1000)
            print(f"开始录制视频，时长: {record_duration/1000:.1f}秒")
            await page.wait_for_timeout(record_duration)
            
            # 关闭context以保存视频
            await context.close()
            await browser.close()
            
            # 等待视频文件生成
            await asyncio.sleep(2)
            
        # 查找生成的视频文件
        video_files = []
        if os.path.exists("generated_videos"):
            video_files = [f for f in os.listdir("generated_videos") 
                          if f.endswith('.webm') and f != video_filename]
        
        if video_files:
            # 获取最新的视频文件
            latest_video = max([os.path.join("generated_videos", f) for f in video_files], 
                              key=os.path.getctime)
            
            # 重命名为目标文件名
            if os.path.exists(latest_video):
                os.rename(latest_video, video_path)
                print(f"视频录制成功: {video_path}")
                return video_path
        
        raise Exception("视频录制失败，未生成视频文件")
        
    except Exception as e:
        print(f"录屏过程中发生错误: {str(e)}")
        # 清理可能生成的临时文件
        if os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except:
                pass
        raise Exception(f"视频录制失败: {str(e)}")
    
    finally:
        # 确保浏览器资源被正确释放
        try:
            if context:
                await context.close()
            if browser:
                await browser.close()
        except:
            pass

@app.post("/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """生成HTML+音频的视频"""
    temp_files = []
    
    try:
        # 1. 下载音频并获取时长
        print("正在下载音频并获取时长...")
        audio_data, duration = await download_audio_and_get_duration(request.audio_url)
        print(f"音频时长: {duration:.2f}秒")
        
        # 2. 保存HTML文件
        print("正在保存HTML文件...")
        html_path = save_html_file(request.html_content)
        temp_files.append(html_path)
        print(f"HTML文件已保存: {html_path}")
        
        # 3. 录制视频
        print("正在录制视频...")
        video_path = await record_html_video(html_path, duration)
        temp_files.append(video_path)
        print(f"视频录制完成: {video_path}")
        
        # 4. 获取视频文件信息
        file_size = os.path.getsize(video_path)
        video_filename = os.path.basename(video_path)
        video_url = f"/videos/{video_filename}"
        
        return VideoGenerationResponse(
            success=True,
            video_url=video_url,
            duration=duration,
            file_size=file_size
        )
        
    except Exception as e:
        print(f"视频生成失败: {str(e)}")
        return VideoGenerationResponse(
            success=False,
            error=str(e)
        )
    
    finally:
        # 清理HTML临时文件（保留视频文件）
        for temp_file in temp_files:
            if temp_file.endswith('.html') and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    print(f"已清理临时文件: {temp_file}")
                except Exception as e:
                    print(f"清理临时文件失败: {e}")