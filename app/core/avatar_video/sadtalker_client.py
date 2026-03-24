# -*- coding: utf-8 -*-
"""
SadTalker客户端 - 本地生成2D数字人视频
"""

import os
import subprocess
from typing import Optional


class SadTalkerClient:
    """SadTalker本地客户端"""
    
    def __init__(self, sadtalker_path: str = None):
        """
        初始化SadTalker客户端
        
        Args:
            sadtalker_path: SadTalker安装路径
        """
        if sadtalker_path is None:
            # 默认在项目根目录下的SadTalker文件夹
            self.sadtalker_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'SadTalker'
            )
        else:
            self.sadtalker_path = sadtalker_path
        
        self.inference_script = os.path.join(self.sadtalker_path, 'inference.py')
    
    def check_installation(self) -> bool:
        """检查SadTalker是否已安装"""
        return os.path.exists(self.inference_script)
    
    def generate_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        preprocess: str = 'crop',
        still: bool = False,
        enhancer: Optional[str] = None,
        size: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        生成视频
        
        Args:
            image_path: 人物照片路径
            audio_path: 音频文件路径
            output_path: 输出视频路径
            preprocess: 预处理方式 ('crop', 'resize', 'full')
            still: 是否生成静态视频（头部不动）
            enhancer: 增强器 (None, 'gfpgan', 'RestoreFormer')
            progress_callback: 进度回调
            
        Returns:
            生成的视频路径
        """
        if not self.check_installation():
            raise Exception(f"SadTalker not found at {self.sadtalker_path}. Please run install_sadtalker.sh first.")
        
        if progress_callback:
            progress_callback(10, "Initializing SadTalker...")
        
        # 创建输出目录
        result_dir = os.path.dirname(output_path)
        os.makedirs(result_dir, exist_ok=True)
        
        # 获取虚拟环境的Python路径
        venv_python = os.path.join(
            os.path.dirname(self.sadtalker_path),
            'sadtalker_env',
            'bin',
            'python'
        )
        
        # 如果虚拟环境存在，使用它；否则使用系统Python
        python_cmd = venv_python if os.path.exists(venv_python) else 'python'
        
        # 检查是否需要使用arm64模式（Apple Silicon Mac）
        import platform
        use_arm64 = platform.machine() == 'arm64' or 'arm' in platform.machine().lower()
        
        # 构建命令
        if use_arm64 and os.path.exists(venv_python):
            # 使用arch -arm64确保在arm64模式下运行
            cmd = [
                'arch', '-arm64',
                python_cmd,
                self.inference_script,
                '--driven_audio', audio_path,
                '--source_image', image_path,
                '--result_dir', result_dir,
                '--preprocess', preprocess,
            ]
        else:
            cmd = [
                python_cmd,
                self.inference_script,
                '--driven_audio', audio_path,
                '--source_image', image_path,
                '--result_dir', result_dir,
                '--preprocess', preprocess,
            ]
        
        if still:
            cmd.append('--still')
        
        if enhancer:
            cmd.extend(['--enhancer', enhancer])
        
        # 分辨率设置（256可显著提速）
        if size in (256, 512):
            cmd.extend(['--size', str(size)])
        
        if progress_callback:
            progress_callback(30, "Generating video with SadTalker...")
        
        # 运行SadTalker
        try:
            result = subprocess.run(
                cmd,
                cwd=self.sadtalker_path,
                capture_output=True,
                text=True,
                timeout=7200  # 2小时超时（适合长音频）
            )
            
            if result.returncode != 0:
                raise Exception(f"SadTalker failed: {result.stderr}")
            
            if progress_callback:
                progress_callback(90, "Video generated successfully")
            
            # SadTalker会在result_dir中生成视频，需要找到生成的文件
            # 通常是以时间戳命名的
            generated_files = [f for f in os.listdir(result_dir) if f.endswith('.mp4')]
            if generated_files:
                # 找到最新的文件
                latest_file = max(
                    [os.path.join(result_dir, f) for f in generated_files],
                    key=os.path.getmtime
                )
                
                # 重命名为目标文件名
                if latest_file != output_path:
                    os.rename(latest_file, output_path)
                
                if progress_callback:
                    progress_callback(100, "Video generation completed")
                
                return output_path
            else:
                raise Exception("No video file generated")
                
        except subprocess.TimeoutExpired:
            raise Exception("SadTalker generation timeout (2 hours). For very long audio, consider splitting it into segments.")
        except Exception as e:
            raise Exception(f"SadTalker error: {str(e)}")

