# -*- coding: utf-8 -*-
"""
2D人物视频生成器 - 使用SadTalker
"""

import os
import shutil
from typing import Optional, Callable

from .sadtalker_client import SadTalkerClient


class AvatarVideoGeneratorSadTalker:
    """2D人物讲解视频生成器 (SadTalker版本)"""
    
    def __init__(self, sadtalker_path: Optional[str] = None):
        """
        初始化生成器
        
        Args:
            sadtalker_path: SadTalker安装路径（可选）
        """
        self.sadtalker_client = SadTalkerClient(sadtalker_path)
    
    def check_installation(self) -> bool:
        """检查SadTalker是否已安装"""
        return self.sadtalker_client.check_installation()
    
    def generate_from_script(
        self,
        avatar_image: str,
        audio_path: str,
        output_path: str,
        preprocess: str = 'crop',
        still: bool = False,
        enhancer: Optional[str] = None,
        fast_mode: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        根据照片和语音生成2D人物讲解视频
        
        Args:
            avatar_image: 人物照片路径
            audio_path: 完整语音文件路径
            output_path: 输出视频路径
            preprocess: 预处理方式 ('crop', 'resize', 'full')
            still: 是否生成静态视频（头部不动，只有嘴动）
            enhancer: 面部增强器 (None, 'gfpgan', 'RestoreFormer')
            progress_callback: 进度回调函数 (progress: int, message: str) -> None
            
        Returns:
            生成的视频文件路径
        """
        try:
            if progress_callback:
                progress_callback(5, "Checking SadTalker installation...")
            
            if not self.check_installation():
                raise Exception(
                    "SadTalker not installed. Please run: bash install_sadtalker.sh"
                )
            
            if progress_callback:
                progress_callback(10, "Starting video generation...")
            
            # 使用SadTalker生成视频
            # fast_mode 时使用 256 分辨率显著提速
            size = 256 if fast_mode else None
            video_path = self.sadtalker_client.generate_video(
                image_path=avatar_image,
                audio_path=audio_path,
                output_path=output_path,
                preprocess=preprocess,
                still=still,
                enhancer=enhancer,
                size=size,
                progress_callback=progress_callback
            )
            
            return video_path
            
        except Exception as e:
            raise Exception(f"Video generation failed: {str(e)}")
    
    def get_installation_path(self) -> str:
        """获取SadTalker安装路径"""
        return self.sadtalker_client.sadtalker_path

