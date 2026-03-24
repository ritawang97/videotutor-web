# -*- coding: utf-8 -*-
"""
视频合并线程：将人脸视频叠加到主视频上
"""

import os
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

from app.config import WORK_PATH
from app.core.video_merger import VideoMerger


class VideoMergeThread(QThread):
    """视频合并线程"""
    
    progress = pyqtSignal(int)  # 进度信号
    status = pyqtSignal(str)  # 状态信号
    finished = pyqtSignal(str)  # 完成信号（合并后的视频路径）
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, main_video_path: str, avatar_video_path: str, parent=None):
        """
        初始化线程
        
        Args:
            main_video_path: 主视频路径（Intelligent Video生成的视频）
            avatar_video_path: 人脸视频路径（SadTalker生成的视频）
        """
        super().__init__(parent)
        self.main_video_path = main_video_path
        self.avatar_video_path = avatar_video_path
    
    def run(self):
        """运行线程"""
        try:
            self.status.emit("Initializing video merger...")
            self.progress.emit(5)
            
            # 创建合并器
            merger = VideoMerger()
            
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"Merged_Video_{timestamp}.mp4"
            output_path = os.path.join(WORK_PATH, output_filename)
            
            self.status.emit(f"Output file: {output_filename}")
            
            # 定义进度回调
            def progress_callback(progress: int, message: str):
                self.progress.emit(progress)
                self.status.emit(message)
            
            # 合并视频
            self.status.emit("Merging videos...")
            
            merged_video_path = merger.merge_videos(
                main_video_path=self.main_video_path,
                avatar_video_path=self.avatar_video_path,
                output_path=output_path,
                position="top-left",  # 左上角
                avatar_size=None,  # 自动计算（主视频宽度的1/6）
                margin=15,  # 稍微减小边距
                progress_callback=progress_callback
            )
            
            self.status.emit(f"Video merged successfully: {merged_video_path}")
            self.finished.emit(merged_video_path)
            
        except Exception as e:
            error_msg = str(e)
            self.status.emit(f"Error: {error_msg}")
            self.error.emit(error_msg)

