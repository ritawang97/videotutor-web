# -*- coding: utf-8 -*-
"""
素材搜索器：多平台搜索图片和视频素材
"""

import requests
from dataclasses import dataclass
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.core.utils.logger import setup_logger

logger = setup_logger("MaterialSearcher")


@dataclass
class Material:
    """素材信息"""
    url: str
    thumbnail_url: str
    type: str  # 'image' | 'video'
    width: int
    height: int
    duration: Optional[float] = None  # 视频才有
    source: str = ""
    title: str = ""
    photographer: str = ""
    relevance_score: float = 0.0


class PexelsSearcher:
    """Pexels素材搜索"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pexels.com/v1/"
    
    def search(self, query: str, material_type: str, count: int = 5) -> List[Material]:
        """搜索Pexels素材"""
        if not self.api_key or self.api_key == "":
            logger.warning("Pexels API Key未配置")
            return []
        
        try:
            if material_type == 'image':
                endpoint = f"{self.base_url}search"
            else:
                endpoint = f"{self.base_url}videos/search"
            
            headers = {"Authorization": self.api_key}
            params = {
                "query": query,
                "per_page": count,
                "orientation": "landscape"
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            materials = []
            if material_type == 'image':
                for item in data.get('photos', []):
                    materials.append(Material(
                        url=item['src']['original'],
                        thumbnail_url=item['src']['medium'],
                        type='image',
                        width=item['width'],
                        height=item['height'],
                        source='pexels',
                        title=item.get('alt', ''),
                        photographer=item.get('photographer', '')
                    ))
            else:
                for item in data.get('videos', []):
                    # 选择最高质量的视频文件
                    video_files = item.get('video_files', [])
                    if video_files:
                        video_file = max(video_files, key=lambda x: x.get('width', 0))
                        materials.append(Material(
                            url=video_file['link'],
                            thumbnail_url=item.get('image', ''),
                            type='video',
                            width=video_file['width'],
                            height=video_file['height'],
                            duration=item.get('duration'),
                            source='pexels'
                        ))
            
            logger.info(f"Pexels搜索到{len(materials)}个{material_type}")
            return materials
            
        except Exception as e:
            logger.error(f"Pexels搜索失败: {e}")
            return []


class UnsplashSearcher:
    """Unsplash图片搜索"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com/"
    
    def search(self, query: str, material_type: str, count: int = 5) -> List[Material]:
        """搜索Unsplash图片"""
        if material_type != 'image':
            return []
        
        if not self.api_key or self.api_key == "":
            logger.warning("Unsplash API Key未配置")
            return []
        
        try:
            endpoint = f"{self.base_url}search/photos"
            headers = {"Authorization": f"Client-ID {self.api_key}"}
            params = {
                "query": query,
                "per_page": count,
                "orientation": "landscape"
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            materials = []
            for item in data.get('results', []):
                materials.append(Material(
                    url=item['urls']['raw'],
                    thumbnail_url=item['urls']['small'],
                    type='image',
                    width=item['width'],
                    height=item['height'],
                    source='unsplash',
                    title=item.get('description', ''),
                    photographer=item['user']['name']
                ))
            
            logger.info(f"Unsplash搜索到{len(materials)}个图片")
            return materials
            
        except Exception as e:
            logger.error(f"Unsplash搜索失败: {e}")
            return []


class MaterialSearcher:
    """素材搜索器（多平台聚合）"""
    
    def __init__(self, pexels_key: str = "", unsplash_key: str = ""):
        self.searchers = {}
        
        if pexels_key:
            self.searchers['pexels'] = PexelsSearcher(pexels_key)
        if unsplash_key:
            self.searchers['unsplash'] = UnsplashSearcher(unsplash_key)
    
    def search_materials(self, query: str, material_type: str, count: int = 5) -> List[Material]:
        """
        搜索素材
        
        参数:
        - query: 搜索词（英文）
        - material_type: 'image' | 'video'
        - count: 需要的素材数量
        """
        if not self.searchers:
            logger.error("没有配置任何搜索平台API")
            return self._get_placeholder_materials(material_type, count)
        
        logger.info(f"搜索素材: {query}, 类型: {material_type}")
        
        all_results = []
        
        # 多平台并发搜索
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for platform, searcher in self.searchers.items():
                future = executor.submit(searcher.search, query, material_type, count)
                futures.append((platform, future))
            
            for platform, future in futures:
                try:
                    results = future.result(timeout=15)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"{platform}搜索超时或失败: {e}")
        
        # 相关性评分
        scored_results = self._score_relevance(query, all_results)
        
        # 去重和排序
        unique_results = self._deduplicate(scored_results)
        sorted_results = sorted(unique_results, 
                              key=lambda x: x.relevance_score, 
                              reverse=True)
        
        # 返回top N
        final_results = sorted_results[:count]
        
        # 如果没有搜索到，返回占位符
        if not final_results:
            final_results = self._get_placeholder_materials(material_type, count)
        
        logger.info(f"最终返回{len(final_results)}个素材")
        return final_results
    
    def _score_relevance(self, query: str, materials: List[Material]) -> List[Material]:
        """评估素材相关性"""
        for material in materials:
            score = 0.0
            
            # 标题匹配（50%）
            if query.lower() in material.title.lower():
                score += 0.5
            
            # 分辨率评分（20%）
            if material.width >= 1920 and material.height >= 1080:
                score += 0.2
            elif material.width >= 1280:
                score += 0.1
            
            # 来源加分（Pexels质量较高）
            if material.source == 'pexels':
                score += 0.1
            
            # 基础分
            score += 0.2
            
            material.relevance_score = min(score, 1.0)
        
        return materials
    
    def _deduplicate(self, materials: List[Material]) -> List[Material]:
        """去重"""
        seen_urls = set()
        unique_materials = []
        
        for material in materials:
            if material.url not in seen_urls:
                seen_urls.add(material.url)
                unique_materials.append(material)
        
        return unique_materials
    
    def _get_placeholder_materials(self, material_type: str, count: int) -> List[Material]:
        """获取占位符素材（当搜索失败时）"""
        logger.warning("返回占位符素材")
        
        placeholders = []
        for i in range(count):
            placeholders.append(Material(
                url="",  # 空URL表示需要生成纯色或文字背景
                thumbnail_url="",
                type=material_type,
                width=1920,
                height=1080,
                source='placeholder'
            ))
        
        return placeholders

