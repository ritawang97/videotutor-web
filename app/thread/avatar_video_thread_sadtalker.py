# -*- coding: utf-8 -*-
"""
2D人物视频生成线程 - SadTalker版本
"""

import os
import subprocess
import tempfile
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

from app.config import WORK_PATH
from app.core.avatar_video.avatar_video_generator_sadtalker import AvatarVideoGeneratorSadTalker


class AvatarVideoThreadSadTalker(QThread):
    """2D人物视频生成线程 - SadTalker版本"""
    
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
                - audio_path: 音频路径
                - preprocess: 预处理方式
                - still: 是否静态
                - enhancer: 增强器
        """
        super().__init__(parent)
        self.config = config
    
    def extract_audio_from_video(self, video_path: str) -> str:
        """
        从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            提取的音频文件路径
        """
        # 创建临时音频文件
        temp_audio = tempfile.mktemp(suffix='.wav')
        
        # 使用ffmpeg提取音频
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # 不处理视频
            '-acodec', 'pcm_s16le',  # 音频编码
            '-ar', '16000',  # 采样率
            '-ac', '1',  # 单声道
            '-y',  # 覆盖输出文件
            temp_audio
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to extract audio from video: {result.stderr}")
        
        return temp_audio
    
    def run(self):
        """运行线程"""
        temp_audio_file = None
        try:
            # 获取配置
            avatar_image = self.config['avatar_image']
            audio_path = self.config['audio_path']
            preprocess = self.config.get('preprocess', 'crop')
            still = self.config.get('still', False)
            enhancer = self.config.get('enhancer', None)
            
            self.status.emit("Initializing SadTalker...")
            self.progress.emit(5)
            
            # 如果是MP4视频文件，先提取音频
            if audio_path.lower().endswith('.mp4'):
                self.status.emit("Extracting audio from MP4 video...")
                self.progress.emit(3)
                temp_audio_file = self.extract_audio_from_video(audio_path)
                audio_path = temp_audio_file
                self.status.emit("Audio extracted successfully!")
                self.progress.emit(5)
            
            # 创建生成器
            generator = AvatarVideoGeneratorSadTalker()
            
            # 检查安装
            if not generator.check_installation():
                install_path = generator.get_installation_path()
                self.error.emit(
                    f"SadTalker not installed at {install_path}. "
                    f"Please run: bash install_sadtalker.sh"
                )
                return
            
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
            self.status.emit("Starting video generation with SadTalker...")
            
            video_path = generator.generate_from_script(
                avatar_image=avatar_image,
                audio_path=audio_path,
                output_path=output_path,
                preprocess=preprocess,
                still=still,
                enhancer=enhancer,
                progress_callback=progress_callback
            )
            
            self.status.emit(f"Video generated successfully: {video_path}")
            self.finished.emit(video_path)
            
        except Exception as e:
            error_msg = str(e)
            self.status.emit(f"Error: {error_msg}")
            self.error.emit(error_msg)
        
        finally:
            # 清理临时音频文件
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                    self.status.emit("Cleaned up temporary audio file")
                except:
                    pass

