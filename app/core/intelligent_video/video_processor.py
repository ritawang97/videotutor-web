# -*- coding: utf-8 -*-
"""
视频处理器：图片转视频、视频剪辑
"""

import subprocess
import random
from pathlib import Path
from typing import Optional

from app.core.utils.logger import setup_logger

logger = setup_logger("VideoProcessor")


class ImageToVideoConverter:
    """图片转视频转换器"""
    
    def convert_image_to_video(self,
                              image_path: Path,
                              output_path: Path,
                              duration: float,
                              resolution: tuple = (1920, 1080),
                              effect: str = 'ken_burns',
                              fps: int = 30):
        """
        将图片转换为视频片段
        
        参数：
        - image_path: 图片路径
        - output_path: 输出视频路径
        - duration: 视频时长（秒）
        - resolution: 分辨率
        - effect: 特效类型 ('static' | 'ken_burns' | 'fade')
        - fps: 帧率
        """
        logger.info(f"图片转视频: {image_path} -> {output_path}, 时长{duration}秒, 效果{effect}")
        
        try:
            if effect == 'ken_burns':
                self._apply_ken_burns(image_path, output_path, duration, resolution, fps)
            elif effect == 'fade':
                self._apply_fade(image_path, output_path, duration, resolution, fps)
            else:
                self._static_image(image_path, output_path, duration, resolution, fps)
            
            logger.info(f"图片转视频完成: {output_path}")
            
        except Exception as e:
            logger.error(f"图片转视频失败: {e}")
            # 降级为静态图片
            try:
                self._static_image(image_path, output_path, duration, resolution, fps)
            except:
                raise
    
    def _apply_ken_burns(self, image_path, output_path, duration, resolution, fps):
        """应用Ken Burns效果（缓慢缩放）"""
        w, h = resolution
        
        # 随机选择缩放方向
        zoom_in = random.choice([True, False])
        
        if zoom_in:
            scale_start, scale_end = 1.0, 1.2
        else:
            scale_start, scale_end = 1.2, 1.0
        
        cmd = [
            'ffmpeg',
            '-loop', '1',
            '-i', str(image_path),
            '-vf', (
                f"scale={int(w*1.3)}:{int(h*1.3)}:force_original_aspect_ratio=increase,"
                f"crop={int(w*1.3)}:{int(h*1.3)},"
                f"zoompan=z='if(lte(zoom,1.0),{scale_start},"
                f"{scale_start}+({scale_end}-{scale_start})*(time/{duration}))':"
                f"d={int(duration*fps)}:"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"s={w}x{h},"
                f"fade=t=in:st=0:d=0.5,"
                f"fade=t=out:st={duration-0.5}:d=0.5"
            ),
            '-c:v', 'libx264',
            '-t', str(duration),
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-y',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _apply_fade(self, image_path, output_path, duration, resolution, fps):
        """应用淡入淡出效果"""
        w, h = resolution
        
        cmd = [
            'ffmpeg',
            '-loop', '1',
            '-i', str(image_path),
            '-vf', (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                f"fade=t=in:st=0:d=1,"
                f"fade=t=out:st={duration-1}:d=1"
            ),
            '-c:v', 'libx264',
            '-t', str(duration),
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-y',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _static_image(self, image_path, output_path, duration, resolution, fps):
        """静态图片（无特效）"""
        w, h = resolution
        
        cmd = [
            'ffmpeg',
            '-loop', '1',
            '-i', str(image_path),
            '-vf', f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
            '-c:v', 'libx264',
            '-t', str(duration),
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-y',
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)


class VideoClipper:
    """视频剪辑器"""
    
    def clip_video(self,
                   input_path: Path,
                   output_path: Path,
                   start_time: float,
                   duration: float,
                   resolution: tuple = (1920, 1080)):
        """
        剪辑视频片段
        
        参数：
        - input_path: 输入视频
        - output_path: 输出视频
        - start_time: 起始时间（秒）
        - duration: 持续时间（秒）
        - resolution: 输出分辨率
        """
        logger.info(f"剪辑视频: {input_path}, 从{start_time}s开始, 持续{duration}s")
        
        w, h = resolution
        
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-i', str(input_path),
            '-t', str(duration),
            '-vf', (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}"
            ),
            '-an',  # 移除音频
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-y',
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"视频剪辑完成: {output_path}")
        except Exception as e:
            logger.error(f"视频剪辑失败: {e}")
            raise
    
    def auto_select_best_segment(self, video_path: Path, target_duration: float) -> float:
        """
        自动选择视频中最佳片段的起始时间
        
        策略：从视频中间偏后位置选择
        """
        try:
            total_duration = self._get_video_duration(video_path)
            
            if total_duration <= target_duration:
                return 0.0
            else:
                # 从30%到60%之间随机选择
                min_start = total_duration * 0.3
                max_start = total_duration * 0.6
                
                if max_start + target_duration > total_duration:
                    max_start = total_duration - target_duration
                
                start_time = random.uniform(min_start, max_start)
                return start_time
                
        except:
            return 0.0
    
    def _get_video_duration(self, video_path: Path) -> float:
        """获取视频时长"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

