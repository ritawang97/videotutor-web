# -*- coding: utf-8 -*-
"""
视频分割器 - 将长音频分割成适合Kling处理的10秒片段
"""

import os
import math
from pathlib import Path
from typing import List, Tuple, Optional
from pydub import AudioSegment
from pydub.silence import detect_silence


class VideoSplitter:
    """音频分割器，用于将长音频分割成10秒以内的片段"""
    
    def __init__(self, max_duration: float = 10.0):
        """
        初始化分割器
        
        Args:
            max_duration: 最大片段时长（秒）
        """
        self.max_duration = max_duration
    
    def split_audio_by_silence(
        self,
        audio_path: str,
        output_dir: str,
        min_silence_len: int = 500,
        silence_thresh: int = -40
    ) -> List[Tuple[str, float, str]]:
        """
        根据静音点智能分割音频
        
        Args:
            audio_path: 输入音频文件路径
            output_dir: 输出目录
            min_silence_len: 最小静音长度（毫秒）
            silence_thresh: 静音阈值（dB）
            
        Returns:
            List of (segment_path, duration, text_segment) tuples
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载音频
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0  # 转换为秒
        
        segments = []
        
        # 如果音频短于最大时长，直接返回
        if total_duration <= self.max_duration:
            output_path = os.path.join(output_dir, "segment_001.wav")
            audio.export(output_path, format="wav")
            return [(output_path, total_duration, "")]
        
        # 检测静音点
        silence_ranges = detect_silence(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh
        )
        
        # 转换为秒
        silence_points = [(start / 1000.0, end / 1000.0) for start, end in silence_ranges]
        
        # 根据静音点和最大时长分割
        current_start = 0
        segment_index = 1
        
        while current_start < total_duration:
            # 计算理想的结束点
            ideal_end = current_start + self.max_duration
            
            if ideal_end >= total_duration:
                # 最后一个片段
                segment_audio = audio[int(current_start * 1000):]
                output_path = os.path.join(output_dir, f"segment_{segment_index:03d}.wav")
                segment_audio.export(output_path, format="wav")
                
                duration = len(segment_audio) / 1000.0
                segments.append((output_path, duration, ""))
                break
            
            # 寻找最接近ideal_end的静音点
            best_split_point = ideal_end
            for silence_start, silence_end in silence_points:
                silence_mid = (silence_start + silence_end) / 2
                
                # 如果静音点在合理范围内（ideal_end前后1秒）
                if abs(silence_mid - ideal_end) < 1.0 and silence_mid > current_start:
                    best_split_point = silence_mid
                    break
            
            # 提取片段
            segment_audio = audio[int(current_start * 1000):int(best_split_point * 1000)]
            output_path = os.path.join(output_dir, f"segment_{segment_index:03d}.wav")
            segment_audio.export(output_path, format="wav")
            
            duration = len(segment_audio) / 1000.0
            segments.append((output_path, duration, ""))
            
            current_start = best_split_point
            segment_index += 1
        
        return segments
    
    def split_audio_uniform(
        self,
        audio_path: str,
        output_dir: str
    ) -> List[Tuple[str, float]]:
        """
        均匀分割音频（用于无明显静音点的情况）
        
        Args:
            audio_path: 输入音频文件路径
            output_dir: 输出目录
            
        Returns:
            List of (segment_path, duration) tuples
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载音频
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        # 计算需要的片段数
        num_segments = math.ceil(total_duration / self.max_duration)
        segment_duration = total_duration / num_segments
        
        segments = []
        
        for i in range(num_segments):
            start_time = i * segment_duration * 1000  # 转换为毫秒
            end_time = min((i + 1) * segment_duration * 1000, len(audio))
            
            segment_audio = audio[int(start_time):int(end_time)]
            output_path = os.path.join(output_dir, f"segment_{i+1:03d}.wav")
            segment_audio.export(output_path, format="wav")
            
            duration = len(segment_audio) / 1000.0
            segments.append((output_path, duration))
        
        return segments
    
    def split_with_script(
        self,
        audio_path: str,
        script_path: str,
        output_dir: str
    ) -> List[Tuple[str, float, str]]:
        """
        根据演讲稿内容智能分割音频
        
        Args:
            audio_path: 音频文件路径
            script_path: 演讲稿文件路径
            output_dir: 输出目录
            
        Returns:
            List of (segment_audio_path, duration, segment_text) tuples
        """
        # 读取演讲稿
        with open(script_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        # 加载音频
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0
        
        # 按段落分割文本（假设段落用双换行分隔）
        paragraphs = [p.strip() for p in script_text.split('\n\n') if p.strip()]
        
        # 如果没有段落，按句子分割
        if len(paragraphs) <= 1:
            import re
            sentences = re.split(r'[。！？.!?]\s*', script_text)
            paragraphs = [s.strip() + '。' for s in sentences if s.strip()]
        
        # 估算每个段落的时长（假设平均语速）
        total_chars = sum(len(p) for p in paragraphs)
        
        segments = []
        current_time = 0
        segment_index = 1
        
        os.makedirs(output_dir, exist_ok=True)
        
        for paragraph in paragraphs:
            # 估算该段落的时长
            paragraph_ratio = len(paragraph) / total_chars
            estimated_duration = total_duration * paragraph_ratio
            
            # 如果单个段落超过最大时长，需要进一步分割
            if estimated_duration > self.max_duration:
                # 按句子进一步分割
                import re
                sentences = re.split(r'([。！？.!?]\s*)', paragraph)
                sentences = [''.join(sentences[i:i+2]) for i in range(0, len(sentences), 2)]
                
                for sentence in sentences:
                    if not sentence.strip():
                        continue
                    
                    sentence_ratio = len(sentence) / total_chars
                    sentence_duration = min(total_duration * sentence_ratio, self.max_duration)
                    
                    # 提取音频片段
                    end_time = min(current_time + sentence_duration, total_duration)
                    segment_audio = audio[int(current_time * 1000):int(end_time * 1000)]
                    
                    output_path = os.path.join(output_dir, f"segment_{segment_index:03d}.wav")
                    segment_audio.export(output_path, format="wav")
                    
                    actual_duration = len(segment_audio) / 1000.0
                    segments.append((output_path, actual_duration, sentence.strip()))
                    
                    current_time = end_time
                    segment_index += 1
            else:
                # 提取音频片段
                end_time = min(current_time + estimated_duration, total_duration)
                segment_audio = audio[int(current_time * 1000):int(end_time * 1000)]
                
                output_path = os.path.join(output_dir, f"segment_{segment_index:03d}.wav")
                segment_audio.export(output_path, format="wav")
                
                actual_duration = len(segment_audio) / 1000.0
                segments.append((output_path, actual_duration, paragraph))
                
                current_time = end_time
                segment_index += 1
        
        return segments





