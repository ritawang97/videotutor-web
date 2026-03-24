# -*- coding: utf-8 -*-
"""
Kling API客户端 - 用于调用Kling视频生成API
"""

import os
import time
import hmac
import hashlib
import requests
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class KlingClient:
    """Kling API客户端"""
    
    def __init__(
        self,
        api_base: str,
        access_key: str,
        secret_key: str,
        upload_endpoint: str = "/v1/upload",
        create_endpoint: str = "/v1/video/create",
        task_endpoint: str = "/v1/video/task/{task_id}",
    ):
        """
        初始化Kling客户端
        
        Args:
            api_base: API基础URL
            access_key: 访问密钥（Access Key）
            secret_key: 私钥（Secret Key）
            upload_endpoint: 上传端点
            create_endpoint: 创建任务端点
            task_endpoint: 查询任务端点（包含{task_id}占位符）
        """
        self.api_base = api_base.rstrip('/')
        self.access_key = access_key
        self.secret_key = secret_key
        self.upload_endpoint = upload_endpoint
        self.create_endpoint = create_endpoint
        self.task_endpoint = task_endpoint

    def _sign(self, method: str, path: str, timestamp: str) -> str:
        message = f"{method.upper()}\n{path}\n{timestamp}".encode("utf-8")
        secret = self.secret_key.encode("utf-8")
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return signature

    def _auth_headers(self, method: str, path: str) -> Dict[str, str]:
        ts = str(int(time.time()))
        return {
            "X-Access-Key": self.access_key,
            "X-Timestamp": ts,
            "X-Signature": self._sign(method, path, ts),
        }
    
    def create_video_task(
        self,
        image_path: str,
        audio_path: str,
        duration: float = 10.0,
        background_prompt: Optional[str] = None,
        style: str = "realistic"
    ) -> Dict[str, Any]:
        """
        创建视频生成任务
        
        Args:
            image_path: 人物照片路径
            audio_path: 语音文件路径
            duration: 视频时长（秒），最大10秒
            background_prompt: 背景描述提示词
            style: 视频风格（realistic/cartoon/anime）
            
        Returns:
            包含task_id的响应字典
        """
        # 限制时长最大为10秒
        duration = min(duration, 10.0)
        
        # 上传图片
        image_url = self._upload_file(image_path, 'image')
        # 上传音频
        audio_url = self._upload_file(audio_path, 'audio')
        
        # 创建任务
        payload = {
            'image_url': image_url,
            'audio_url': audio_url,
            'duration': duration,
            'style': style,
            'enable_lip_sync': True,  # 启用嘴形同步
        }
        
        if background_prompt:
            payload['background_prompt'] = background_prompt
        
        path = self.create_endpoint
        url = urljoin(self.api_base + '/', path.lstrip('/'))
        headers = {"Content-Type": "application/json"}
        headers.update(self._auth_headers("POST", path))
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        response.raise_for_status()
        return response.json()
    
    def _upload_file(self, file_path: str, file_type: str) -> str:
        """
        上传文件到Kling服务器
        
        Args:
            file_path: 文件路径
            file_type: 文件类型（image/audio）
            
        Returns:
            上传后的文件URL
        """
        path = self.upload_endpoint
        url = urljoin(self.api_base + '/', path.lstrip('/'))
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            headers = self._auth_headers("POST", path)
            response = requests.post(url, headers=headers, files=files, data={'type': file_type}, timeout=120)
            
            response.raise_for_status()
            result = response.json()
            return result.get('url', '')
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        path = self.task_endpoint.format(task_id=task_id)
        url = urljoin(self.api_base + '/', path.lstrip('/'))
        headers = self._auth_headers("GET", path)
        response = requests.get(url, headers=headers, timeout=60)
        
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 600,
        check_interval: int = 5,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            progress_callback: 进度回调函数
            
        Returns:
            完成后的任务信息
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status_data = self.get_task_status(task_id)
            status = status_data.get('status', '')
            
            if progress_callback:
                progress = status_data.get('progress', 0)
                progress_callback(progress, status)
            
            if status == 'completed':
                return status_data
            elif status == 'failed':
                error_msg = status_data.get('error', 'Unknown error')
                raise Exception(f"Video generation failed: {error_msg}")
            
            time.sleep(check_interval)
        
        raise TimeoutError(f"Task {task_id} timeout after {timeout} seconds")
    
    def download_video(self, video_url: str, output_path: str) -> str:
        """
        下载生成的视频
        
        Args:
            video_url: 视频URL
            output_path: 输出路径
            
        Returns:
            下载的文件路径
        """
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return output_path
    
    def generate_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        duration: float = 10.0,
        background_prompt: Optional[str] = None,
        style: str = "realistic",
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        生成视频（完整流程）
        
        Args:
            image_path: 人物照片路径
            audio_path: 语音文件路径
            output_path: 输出视频路径
            duration: 视频时长
            background_prompt: 背景描述
            style: 视频风格
            progress_callback: 进度回调
            
        Returns:
            生成的视频文件路径
        """
        # 创建任务
        if progress_callback:
            progress_callback(10, "Creating video generation task...")
        
        task_result = self.create_video_task(
            image_path=image_path,
            audio_path=audio_path,
            duration=duration,
            background_prompt=background_prompt,
            style=style
        )
        
        task_id = task_result.get('task_id')
        if not task_id:
            raise Exception("Failed to create video task")
        
        if progress_callback:
            progress_callback(20, f"Task created: {task_id}")
        
        # 等待完成
        def progress_wrapper(progress, status):
            if progress_callback:
                # 将20-90的进度映射到任务进度
                mapped_progress = 20 + int(progress * 0.7)
                progress_callback(mapped_progress, f"Generating video: {status}")
        
        result = self.wait_for_completion(
            task_id=task_id,
            progress_callback=progress_wrapper
        )
        
        # 下载视频
        if progress_callback:
            progress_callback(90, "Downloading video...")
        
        video_url = result.get('video_url')
        if not video_url:
            raise Exception("No video URL in result")
        
        downloaded_path = self.download_video(video_url, output_path)
        
        if progress_callback:
            progress_callback(100, "Video generation completed")
        
        return downloaded_path

