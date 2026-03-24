# -*- coding: utf-8 -*-
"""
2D人物视频生成线程
"""

import os
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

from app.common.config import cfg
from app.config import WORK_PATH
from app.core.avatar_video import AvatarVideoGenerator


class AvatarVideoThread(QThread):
    """2D人物视频生成线程"""
    
    progress = pyqtSignal(int)  # 进度信号
    status = pyqtSignal(str)  # 状态信号
    finished = pyqtSignal(str)  # 完成信号（视频路径）
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, config: dict, parent=None):
        """
        初始化线程
        
        Args:
            config: 配置字典，包含以下键：
                - avatar_image: 人物照片路径
                - script_path: 演讲稿路径
                - audio_path: 音频路径
                - video_style: 视频风格
                - enable_lip_sync: 是否启用嘴形同步
                - auto_background: 是否自动生成背景
                - background_prompts: 背景提示词列表（可选）
        """
        super().__init__(parent)
        self.config = config
    
    def run(self):
        """运行线程"""
        try:
            # 获取配置
            avatar_image = self.config['avatar_image']
            script_path = self.config['script_path']
            audio_path = self.config['audio_path']
            video_style = self.config.get('video_style', 'realistic')
            background_prompts = self.config.get('background_prompts', None)
            
            # 获取API配置
            api_base = cfg.get(cfg.kling_api_base)
            access_key = cfg.get(cfg.kling_access_key)
            secret_key = cfg.get(cfg.kling_secret_key)
            upload_ep = cfg.get(cfg.kling_upload_endpoint)
            create_ep = cfg.get(cfg.kling_create_endpoint)
            task_ep = cfg.get(cfg.kling_task_endpoint)

            if not access_key or not secret_key:
                self.error.emit("Kling Access/Secret Key not configured")
                return
            
            if not api_base:
                api_base = "https://api.klingai.com"
            
            self.status.emit("Initializing avatar video generator...")
            self.progress.emit(5)
            
            # 创建生成器
            generator = AvatarVideoGenerator(
                kling_api_base=api_base or "https://api.klingai.com",
                kling_access_key=access_key,
                kling_secret_key=secret_key,
                upload_endpoint=upload_ep or "/v1/upload",
                create_endpoint=create_ep or "/v1/video/create",
                task_endpoint=task_ep or "/v1/video/task/{task_id}",
                work_dir=os.path.join(WORK_PATH, 'avatar_video_temp')
            )
            
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"Avatar_Video_{timestamp}.mp4"
            output_path = os.path.join(WORK_PATH, output_filename)
            
            self.status.emit(f"Output file: {output_filename}")
            
            # 定义进度回调
            def progress_callback(progress: int, message: str):
                self.progress.emit(progress)
                self.status.emit(message)
            
            # 生成视频
            self.status.emit("Starting video generation...")
            
            video_path = generator.generate_from_script(
                avatar_image=avatar_image,
                audio_path=audio_path,
                script_path=script_path,
                output_path=output_path,
                background_prompts=background_prompts,
                style=video_style,
                progress_callback=progress_callback
            )
            
            self.status.emit(f"Video generated successfully: {video_path}")
            self.finished.emit(video_path)
            
        except Exception as e:
            error_msg = str(e)
            self.status.emit(f"Error: {error_msg}")
            self.error.emit(error_msg)

