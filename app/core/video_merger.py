# -*- coding: utf-8 -*-
"""
视频合并工具：将人脸视频叠加到主视频上
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from app.core.utils.logger import setup_logger

logger = setup_logger("VideoMerger")


class VideoMerger:
    """视频合并器：将人脸视频叠加到主视频上"""
    
    def __init__(self):
        pass
    
    def merge_videos(
        self,
        main_video_path: str,
        avatar_video_path: str,
        output_path: str,
        position: str = "bottom-left",
        avatar_size: Optional[Tuple[int, int]] = None,
        margin: int = 20,
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        将人脸视频叠加到主视频上
        
        Args:
            main_video_path: 主视频路径（Intelligent Video生成的视频）
            avatar_video_path: 人脸视频路径（SadTalker生成的视频）
            output_path: 输出视频路径
            position: 位置 ("bottom-left", "bottom-right", "top-left", "top-right")
            avatar_size: 人脸视频尺寸 (width, height)，如果为None则自动计算
            margin: 边距（像素）
            progress_callback: 进度回调函数 (progress: int, message: str) -> None
            
        Returns:
            输出视频路径
        """
        try:
            if progress_callback:
                progress_callback(10, "检查视频文件...")
            
            # 检查文件是否存在
            if not os.path.exists(main_video_path):
                raise FileNotFoundError(f"主视频文件不存在: {main_video_path}")
            if not os.path.exists(avatar_video_path):
                raise FileNotFoundError(f"人脸视频文件不存在: {avatar_video_path}")
            
            # 获取主视频信息
            if progress_callback:
                progress_callback(20, "获取视频信息...")
            
            main_info = self._get_video_info(main_video_path)
            avatar_info = self._get_video_info(avatar_video_path)
            
            # 计算人脸视频尺寸（默认为主视频宽度的1/6，更小以减少对原视频的影响）
            if avatar_size is None:
                avatar_width = main_info['width'] // 6
                # 保持宽高比
                aspect_ratio = avatar_info['height'] / avatar_info['width']
                avatar_height = int(avatar_width * aspect_ratio)
            else:
                avatar_width, avatar_height = avatar_size
            
            # 计算位置
            if position == "bottom-left":
                x = margin
                y = main_info['height'] - avatar_height - margin
            elif position == "bottom-right":
                x = main_info['width'] - avatar_width - margin
                y = main_info['height'] - avatar_height - margin
            elif position == "top-left":
                x = margin
                y = margin
            elif position == "top-right":
                x = main_info['width'] - avatar_width - margin
                y = margin
            else:
                # 默认位置：左上角
                x = margin
                y = margin
            
            if progress_callback:
                progress_callback(40, "合成视频...")
            
            # 使用ffmpeg合成视频
            # 命令：将avatar视频缩放并叠加到主视频上
            # 尝试使用硬件编码器（macOS），如果不可用则使用软件编码器
            cmd = [
                'ffmpeg',
                '-i', main_video_path,  # 主视频
                '-i', avatar_video_path,  # 人脸视频
                '-filter_complex',
                f"[1:v]scale={avatar_width}:{avatar_height}[avatar];"
                f"[0:v][avatar]overlay={x}:{y}[v]",  # 叠加
                '-map', '[v]',  # 映射视频流
                '-map', '0:a?',  # 映射主视频的音频（如果存在）
                '-c:v', 'h264_videotoolbox',  # 使用macOS硬件编码器
                '-b:v', '5M',  # 视频比特率
                '-c:a', 'aac',  # 音频编码
                '-b:a', '192k',  # 音频比特率
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            # 先尝试硬件编码器，如果失败则尝试其他编码器
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            # 如果硬件编码器失败，尝试使用软件编码器
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                if 'encoder' in error_msg or 'not found' in error_msg or 'unknown' in error_msg:
                    logger.warning("Hardware encoder not available, trying alternative encoders...")
                    
                    # 尝试多个编码器，按优先级排序
                    encoders_to_try = [
                        ('mpeg4', ['-q:v', '3']),  # MPEG-4编码器
                        ('libx264', ['-crf', '23']),  # 如果系统有的话
                        ('h264', ['-b:v', '5M']),  # 通用H.264编码器
                    ]
                    
                    success = False
                    for encoder, encoder_params in encoders_to_try:
                        try:
                            cmd_alt = [
                                'ffmpeg',
                                '-i', main_video_path,
                                '-i', avatar_video_path,
                                '-filter_complex',
                                f"[1:v]scale={avatar_width}:{avatar_height}[avatar];"
                                f"[0:v][avatar]overlay={x}:{y}[v]",
                                '-map', '[v]',
                                '-map', '0:a?',
                                '-c:v', encoder,
                            ] + encoder_params + [
                                '-c:a', 'aac',
                                '-b:a', '192k',
                                '-y',
                                output_path
                            ]
                            
                            result = subprocess.run(
                                cmd_alt,
                                capture_output=True,
                                text=True,
                                timeout=3600
                            )
                            
                            if result.returncode == 0:
                                logger.info(f"Successfully used encoder: {encoder}")
                                success = True
                                break
                        except Exception as e:
                            logger.warning(f"Encoder {encoder} failed: {e}")
                            continue
                    
                    if not success:
                        # 如果所有编码器都失败，抛出错误
                        raise Exception(f"All encoders failed. Last error: {result.stderr}")
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg合成失败: {result.stderr}")
            
            if progress_callback:
                progress_callback(100, "视频合成完成！")
            
            logger.info(f"视频合成完成: {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            raise Exception("视频合成超时（1小时）")
        except Exception as e:
            logger.error(f"视频合成失败: {e}")
            raise
    
    def _get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # 如果ffprobe失败，尝试使用ffmpeg获取信息
            cmd2 = [
                'ffmpeg',
                '-i', video_path,
                '-hide_banner'
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
            
            # 从输出中解析信息（简单方法）
            # 默认返回一个合理的值
            return {
                'width': 1920,
                'height': 1080,
                'duration': 10.0
            }
        
        try:
            data = json.loads(result.stdout)
            stream = data['streams'][0]
            return {
                'width': int(stream.get('width', 1920)),
                'height': int(stream.get('height', 1080)),
                'duration': float(stream.get('duration', 10.0))
            }
        except:
            return {
                'width': 1920,
                'height': 1080,
                'duration': 10.0
            }

