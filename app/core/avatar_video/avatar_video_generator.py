# -*- coding: utf-8 -*-
"""
2D人物视频生成器 - 整合Kling API和视频拼接
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List, Tuple, Callable
import subprocess

from .kling_client import KlingClient
from .video_splitter import VideoSplitter


class AvatarVideoGenerator:
    """2D人物讲解视频生成器"""
    
    def __init__(
        self,
        kling_api_base: str,
        kling_access_key: str,
        kling_secret_key: str,
        upload_endpoint: str = "/v1/upload",
        create_endpoint: str = "/v1/video/create",
        task_endpoint: str = "/v1/video/task/{task_id}",
        work_dir: Optional[str] = None
    ):
        """
        初始化生成器
        
        Args:
            kling_api_base: Kling API基础URL
            kling_access_key: Access Key
            kling_secret_key: Secret Key
            upload_endpoint: 上传端点
            create_endpoint: 创建任务端点
            task_endpoint: 查询任务端点
            work_dir: 工作目录
        """
        self.kling_client = KlingClient(
            api_base=kling_api_base,
            access_key=kling_access_key,
            secret_key=kling_secret_key,
            upload_endpoint=upload_endpoint,
            create_endpoint=create_endpoint,
            task_endpoint=task_endpoint,
        )
        self.video_splitter = VideoSplitter(max_duration=10.0)
        self.work_dir = work_dir or os.path.join(os.getcwd(), 'avatar_video_temp')
        os.makedirs(self.work_dir, exist_ok=True)
    
    def generate_from_script(
        self,
        avatar_image: str,
        audio_path: str,
        script_path: str,
        output_path: str,
        background_prompts: Optional[List[str]] = None,
        style: str = "realistic",
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        根据演讲稿和语音生成完整的2D人物讲解视频
        
        Args:
            avatar_image: 人物照片路径
            audio_path: 完整语音文件路径
            script_path: 演讲稿文本文件路径
            output_path: 输出视频路径
            background_prompts: 背景描述列表（可选，如果提供会根据片段依次使用）
            style: 视频风格
            progress_callback: 进度回调函数 (progress: int, message: str) -> None
            
        Returns:
            生成的视频文件路径
        """
        try:
            # 1. 创建临时工作目录
            temp_dir = os.path.join(self.work_dir, f"temp_{os.path.basename(output_path).split('.')[0]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            audio_segments_dir = os.path.join(temp_dir, "audio_segments")
            video_segments_dir = os.path.join(temp_dir, "video_segments")
            os.makedirs(audio_segments_dir, exist_ok=True)
            os.makedirs(video_segments_dir, exist_ok=True)
            
            if progress_callback:
                progress_callback(5, "Splitting audio into segments...")
            
            # 2. 分割音频（根据演讲稿智能分割）
            audio_segments = self.video_splitter.split_with_script(
                audio_path=audio_path,
                script_path=script_path,
                output_dir=audio_segments_dir
            )
            
            total_segments = len(audio_segments)
            
            if progress_callback:
                progress_callback(10, f"Audio split into {total_segments} segments")
            
            # 3. 为每个片段生成视频
            video_segments = []
            
            for idx, (segment_audio, duration, segment_text) in enumerate(audio_segments):
                segment_num = idx + 1
                
                if progress_callback:
                    segment_progress = 10 + int((idx / total_segments) * 70)
                    progress_callback(
                        segment_progress,
                        f"Generating video segment {segment_num}/{total_segments}..."
                    )
                
                # 获取该片段的背景提示词
                background_prompt = None
                if background_prompts and idx < len(background_prompts):
                    background_prompt = background_prompts[idx]
                elif segment_text:
                    # 如果没有提供背景提示词，根据文本内容生成简单的提示
                    background_prompt = self._generate_background_prompt(segment_text)
                
                # 生成视频片段
                segment_video_path = os.path.join(
                    video_segments_dir,
                    f"video_{segment_num:03d}.mp4"
                )
                
                try:
                    self.kling_client.generate_video(
                        image_path=avatar_image,
                        audio_path=segment_audio,
                        output_path=segment_video_path,
                        duration=duration,
                        background_prompt=background_prompt,
                        style=style,
                        progress_callback=lambda p, m: None  # 内部进度不传递
                    )
                    
                    video_segments.append(segment_video_path)
                    
                except Exception as e:
                    print(f"Warning: Failed to generate segment {segment_num}: {str(e)}")
                    # 继续处理下一个片段
                    continue
            
            if not video_segments:
                raise Exception("No video segments were generated successfully")
            
            if progress_callback:
                progress_callback(80, "Merging video segments...")
            
            # 4. 拼接视频片段
            final_video = self._merge_videos(video_segments, output_path)
            
            if progress_callback:
                progress_callback(90, "Adding audio to final video...")
            
            # 5. 确保音频同步
            final_video = self._sync_audio(final_video, audio_path, output_path)
            
            if progress_callback:
                progress_callback(95, "Cleaning up temporary files...")
            
            # 6. 清理临时文件
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up temp directory: {e}")
            
            if progress_callback:
                progress_callback(100, "Video generation completed!")
            
            return final_video
            
        except Exception as e:
            # 清理临时文件
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            raise e
    
    def _generate_background_prompt(self, text: str) -> str:
        """
        根据文本内容生成背景提示词
        
        Args:
            text: 演讲稿文本片段
            
        Returns:
            背景描述提示词
        """
        # 这里可以使用简单的关键词匹配或LLM来生成背景提示
        # 目前使用简单的关键词匹配
        
        keywords = {
            'office': ['work', 'business', 'professional', 'meeting', '工作', '商务', '办公'],
            'classroom': ['education', 'learn', 'study', 'teach', '教育', '学习', '教学'],
            'tech': ['technology', 'computer', 'digital', 'AI', '技术', '科技', '计算机'],
            'nature': ['nature', 'outdoor', 'environment', '自然', '户外', '环境'],
            'home': ['home', 'room', 'living', '家', '房间', '居住'],
        }
        
        text_lower = text.lower()
        
        for background, words in keywords.items():
            if any(word in text_lower for word in words):
                prompts = {
                    'office': 'Modern professional office with clean desk and natural lighting',
                    'classroom': 'Bright classroom with whiteboard and educational atmosphere',
                    'tech': 'Futuristic tech environment with digital screens and modern design',
                    'nature': 'Beautiful natural outdoor scenery with green plants',
                    'home': 'Cozy home interior with warm lighting'
                }
                return prompts[background]
        
        # 默认背景
        return 'Clean professional background with soft lighting'
    
    def _merge_videos(self, video_paths: List[str], output_path: str) -> str:
        """
        使用FFmpeg拼接视频片段
        
        Args:
            video_paths: 视频文件路径列表
            output_path: 输出文件路径
            
        Returns:
            合并后的视频路径
        """
        if len(video_paths) == 1:
            # 如果只有一个片段，直接复制
            shutil.copy(video_paths[0], output_path)
            return output_path
        
        # 创建FFmpeg concat文件
        concat_file = os.path.join(os.path.dirname(video_paths[0]), "concat_list.txt")
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for video_path in video_paths:
                # FFmpeg concat需要相对路径或转义的绝对路径
                f.write(f"file '{os.path.abspath(video_path)}'\n")
        
        # 使用FFmpeg拼接
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            '-y',  # 覆盖输出文件
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg merge failed: {result.stderr}")
        
        return output_path
    
    def _sync_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """
        确保视频和原始音频同步
        
        Args:
            video_path: 视频文件路径
            audio_path: 原始音频文件路径
            output_path: 输出文件路径
            
        Returns:
            同步后的视频路径
        """
        # 如果视频和输出路径相同，使用临时文件
        if video_path == output_path:
            temp_output = output_path + '.temp.mp4'
        else:
            temp_output = output_path
        
        # 使用FFmpeg替换音频
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',  # 使用最短的流
            '-y',
            temp_output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg audio sync failed: {result.stderr}")
        
        # 如果使用了临时文件，替换原文件
        if temp_output != output_path:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_output, output_path)
        
        return output_path
    
    def cleanup(self):
        """清理工作目录"""
        if os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir)
            except Exception as e:
                print(f"Warning: Failed to cleanup work directory: {e}")

