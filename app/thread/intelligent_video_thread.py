# -*- coding: utf-8 -*-
"""
智能视频生成线程
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from PyQt5.QtCore import QThread, pyqtSignal
from openai import OpenAI

from app.common.config import cfg
from app.config import WORK_PATH
from app.core.entities import LLMServiceEnum
from app.core.intelligent_video import (
    SceneAnalyzer,
    MaterialSearcher,
    IntelligentVideoComposer,
    Material
)
from app.core.utils.logger import setup_logger

logger = setup_logger("IntelligentVideoThread")


class IntelligentVideoThread(QThread):
    """智能视频生成线程"""
    
    progress = pyqtSignal(int, str)  # 进度值, 状态信息
    stage_finished = pyqtSignal(str, object)  # 阶段名, 结果
    finished = pyqtSignal(str)  # 最终视频路径
    error = pyqtSignal(str)  # 错误信息
    
    def __init__(self,
                 script_path: Path,
                 tts_audio_path: Path,
                 subtitle_path: Optional[Path],
                 config: dict):
        super().__init__()
        self.script_path = script_path
        self.tts_audio_path = tts_audio_path
        self.subtitle_path = subtitle_path  # 可以为None
        self.config = config
        self.is_running = True
    
    def run(self):
        """主处理流程"""
        try:
            # 阶段1：场景分析
            self.progress.emit(5, "正在分析演讲稿场景...")
            scenes = self._analyze_scenes()
            if not self.is_running:
                return
            self.stage_finished.emit("场景分析", scenes)
            
            # 阶段2：搜索素材
            self.progress.emit(20, "正在搜索相关素材...")
            materials_dict = self._search_materials(scenes)
            if not self.is_running:
                return
            self.stage_finished.emit("素材搜索", materials_dict)
            
            # 阶段3：下载素材
            self.progress.emit(40, "正在下载素材...")
            downloaded_materials = self._download_materials(materials_dict)
            if not self.is_running:
                return
            self.stage_finished.emit("素材下载", downloaded_materials)
            
            # 阶段4：视频合成
            self.progress.emit(60, "正在合成视频（这可能需要几分钟）...")
            final_video = self._compose_video(scenes, downloaded_materials)
            if not self.is_running:
                return
            
            self.progress.emit(100, "完成！")
            self.finished.emit(str(final_video))
            
        except Exception as e:
            logger.error(f"智能视频生成失败: {e}", exc_info=True)
            # 提取更详细的错误信息
            error_msg = str(e)
            # 如果是subprocess错误，提取stderr信息
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = f"{error_msg}\n详细信息: {e.stderr}"
            elif hasattr(e, 'cmd') and e.cmd:
                error_msg = f"{error_msg}\n命令: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}"
            self.error.emit(f"处理失败: {error_msg}")
    
    def _analyze_scenes(self):
        """场景分析"""
        # 读取演讲稿
        with open(self.script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # 获取音频时长
        audio_duration = self._get_audio_duration(self.tts_audio_path)
        
        # 获取LLM客户端
        client, model = self._get_llm_client()
        
        # 调用场景分析器
        analyzer = SceneAnalyzer(
            client=client,
            model=model,
            script_content=script_content,
            audio_duration=audio_duration
        )
        
        scenes = analyzer.analyze_scenes()
        logger.info(f"分析出 {len(scenes)} 个场景")
        
        return scenes
    
    def _search_materials(self, scenes) -> Dict[int, List[Material]]:
        """搜索素材"""
        # 获取API配置
        pexels_key = cfg.get(cfg.pexels_api_key) if hasattr(cfg, 'pexels_api_key') else ""
        unsplash_key = cfg.get(cfg.unsplash_api_key) if hasattr(cfg, 'unsplash_api_key') else ""
        
        searcher = MaterialSearcher(
            pexels_key=pexels_key,
            unsplash_key=unsplash_key
        )
        
        materials_dict = {}
        
        per_scene = int(self.config.get('materials_per_scene', 1))
        per_scene = max(1, min(per_scene, 8))

        for i, scene in enumerate(scenes):
            if not self.is_running:
                break
            
            self.progress.emit(
                20 + int((i / len(scenes)) * 15),
                f"搜索场景{i+1}/{len(scenes)}的素材..."
            )
            
            # 搜索素材
            materials = searcher.search_materials(
                query=scene.search_query,
                material_type=scene.visual_type,
                count=per_scene  # 每个场景搜索更多素材，稍后挑选
            )
            
            materials_dict[scene.index] = materials
            logger.info(f"场景{scene.index}搜索到{len(materials)}个素材")
        
        return materials_dict
    
    def _download_materials(self, materials_dict: Dict[int, List[Material]]) -> Dict[int, List[Path]]:
        """下载素材"""
        from app.core.intelligent_video.material_searcher import Material
        import requests
        import hashlib
        
        cache_dir = WORK_PATH / 'material_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_dict = {}
        total_materials = sum(len(mats) for mats in materials_dict.values())
        current = 0
        
        for scene_index, materials in materials_dict.items():
            if not self.is_running:
                break
            
            downloaded_paths = []
            
            for material in materials:
                current += 1
                self.progress.emit(
                    40 + int((current / total_materials) * 15),
                    f"下载素材 {current}/{total_materials}..."
                )
                
                if not material.url:
                    # 占位符，不需要下载
                    downloaded_paths.append(None)
                    continue
                
                try:
                    # 生成缓存文件名
                    url_hash = hashlib.md5(material.url.encode()).hexdigest()
                    ext = 'jpg' if material.type == 'image' else 'mp4'
                    cache_file = cache_dir / f"{url_hash}.{ext}"
                    
                    # 检查缓存
                    if cache_file.exists():
                        logger.info(f"使用缓存: {cache_file}")
                        downloaded_paths.append(cache_file)
                        continue
                    
                    # 下载
                    logger.info(f"下载素材: {material.url}")
                    response = requests.get(material.url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    with open(cache_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    downloaded_paths.append(cache_file)
                    logger.info(f"下载完成: {cache_file}")
                    
                except Exception as e:
                    logger.error(f"下载失败: {e}")
                    downloaded_paths.append(None)
            
            downloaded_dict[scene_index] = downloaded_paths
        
        return downloaded_dict
    
    def _compose_video(self, scenes, materials):
        """合成视频"""
        from datetime import datetime
        
        composer = IntelligentVideoComposer(work_dir=WORK_PATH)
        
        output_name = f"AI_Video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = WORK_PATH / output_name
        
        final_video = composer.compose_video(
            scenes=scenes,
            materials=materials,
            audio_path=self.tts_audio_path,
            subtitle_path=self.subtitle_path,
            output_path=output_path,
            add_transitions=self.config.get('add_transitions', True),
            auto_supplement_materials=self.config.get('auto_supplement_materials', True)
        )
        
        return final_video
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """获取音频时长"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            logger.info(f"音频时长: {duration}秒")
            return duration
            
        except Exception as e:
            logger.error(f"获取音频时长失败: {e}")
            return 60.0  # 默认60秒
    
    def _get_llm_client(self):
        """获取LLM客户端"""
        current_service = cfg.get(cfg.llm_service)
        
        if current_service == LLMServiceEnum.OPENAI:
            base_url = cfg.get(cfg.openai_api_base)
            api_key = cfg.get(cfg.openai_api_key)
            model = cfg.get(cfg.openai_model)
        elif current_service == LLMServiceEnum.DEEPSEEK:
            base_url = cfg.get(cfg.deepseek_api_base)
            api_key = cfg.get(cfg.deepseek_api_key)
            model = cfg.get(cfg.deepseek_model)
        elif current_service == LLMServiceEnum.GEMINI:
            base_url = cfg.get(cfg.gemini_api_base)
            api_key = cfg.get(cfg.gemini_api_key)
            model = cfg.get(cfg.gemini_model)
        else:
            # 默认使用OpenAI配置
            base_url = cfg.get(cfg.openai_api_base)
            api_key = cfg.get(cfg.openai_api_key)
            model = cfg.get(cfg.openai_model)
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        return client, model
    
    def stop(self):
        """停止处理"""
        self.is_running = False
        self.terminate()

