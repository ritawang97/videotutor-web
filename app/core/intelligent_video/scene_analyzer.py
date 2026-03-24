# -*- coding: utf-8 -*-
"""
场景分析器：使用LLM分析演讲稿，提取关键词和场景
"""

import json
import json_repair
from dataclasses import dataclass
from typing import List, Optional
from openai import OpenAI

from app.core.utils.logger import setup_logger

logger = setup_logger("SceneAnalyzer")


@dataclass
class SceneSegment:
    """场景段落"""
    index: int
    text: str
    duration: float  # 秒
    keywords: List[str]
    visual_type: str  # 'image' | 'video'
    search_query: str
    scene_description: str


SCENE_ANALYSIS_PROMPT = """你是专业的视频制作顾问。请分析以下演讲稿，为视频制作提供素材搜索建议。

演讲稿内容：
{script_content}

音频总时长：{audio_duration}秒

请完成以下任务：
1. 将演讲稿划分为5-10个逻辑段落
2. 为每个段落提取3-5个关键词（用于搜索图片/视频）
3. 描述每个段落需要的视觉素材类型（图片/视频）
4. 评估每个段落的展示时长建议（总和应接近音频时长）

输出JSON格式：
{{
  "segments": [
    {{
      "index": 1,
      "text": "段落文本摘要",
      "duration": 15.5,
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "visual_type": "video",
      "search_query": "优化后的英文搜索词组",
      "scene_description": "场景描述"
    }}
  ]
}}

注意：
1. search_query必须是英文（方便搜索国际素材库）
2. visual_type只能是"image"或"video"
3. 所有duration之和应该接近{audio_duration}秒
4. keywords要精准且有代表性
"""


class SceneAnalyzer:
    """场景分析器"""
    
    def __init__(self, 
                 client: OpenAI,
                 model: str,
                 script_content: str,
                 audio_duration: float):
        self.client = client
        self.model = model
        self.script = script_content
        self.total_duration = audio_duration
    
    def analyze_scenes(self) -> List[SceneSegment]:
        """
        分析演讲稿，生成场景段落
        
        返回：SceneSegment列表
        """
        logger.info(f"开始分析场景，音频时长: {self.total_duration}秒")
        
        try:
            # 1. 调用LLM分析
            response = self._call_llm_analysis()
            
            # 2. 解析JSON结果
            segments = self._parse_response(response)
            
            # 3. 调整时长，确保总和=音频时长
            segments = self._adjust_durations(segments)
            
            logger.info(f"分析完成，共{len(segments)}个场景")
            return segments
            
        except Exception as e:
            logger.error(f"场景分析失败: {e}")
            # 返回降级方案
            return self._fallback_segmentation()
    
    def _call_llm_analysis(self) -> str:
        """调用LLM进行场景分析"""
        prompt = SCENE_ANALYSIS_PROMPT.format(
            script_content=self.script[:3000],  # 限制长度
            audio_duration=self.total_duration
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是专业的视频制作顾问。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    
    def _parse_response(self, response: str) -> List[SceneSegment]:
        """解析LLM返回的JSON"""
        try:
            # 尝试修复可能的JSON格式问题
            data = json_repair.loads(response)
            
            segments = []
            for item in data.get('segments', []):
                segment = SceneSegment(
                    index=item.get('index', 0),
                    text=item.get('text', ''),
                    duration=float(item.get('duration', 5.0)),
                    keywords=item.get('keywords', []),
                    visual_type=item.get('visual_type', 'image'),
                    search_query=item.get('search_query', ''),
                    scene_description=item.get('scene_description', '')
                )
                segments.append(segment)
            
            return segments
            
        except Exception as e:
            logger.error(f"JSON解析失败: {e}")
            raise
    
    def _adjust_durations(self, segments: List[SceneSegment]) -> List[SceneSegment]:
        """
        调整各段落时长，确保总和等于音频时长
        """
        if not segments:
            return segments
        
        # 计算当前总时长
        total_suggested = sum(seg.duration for seg in segments)
        
        if total_suggested == 0:
            # 平均分配
            avg_duration = self.total_duration / len(segments)
            for seg in segments:
                seg.duration = avg_duration
        else:
            # 按比例缩放
            scale_factor = self.total_duration / total_suggested
            for seg in segments:
                seg.duration *= scale_factor
        
        # 精确调整（处理浮点误差）
        actual_total = sum(seg.duration for seg in segments)
        diff = self.total_duration - actual_total
        
        if abs(diff) > 0.01:  # 如果差异大于0.01秒
            segments[-1].duration += diff
        
        logger.info(f"时长调整完成，总时长: {sum(seg.duration for seg in segments):.2f}秒")
        return segments
    
    def _fallback_segmentation(self) -> List[SceneSegment]:
        """
        降级方案：简单分段
        """
        logger.warning("使用降级方案进行分段")
        
        # 按句子简单分段
        sentences = self.script.split('。')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 限制段落数量
        max_segments = min(len(sentences), 10)
        segments = []
        
        avg_duration = self.total_duration / max_segments
        
        for i in range(max_segments):
            if i < len(sentences):
                text = sentences[i]
            else:
                text = ""
            
            segment = SceneSegment(
                index=i + 1,
                text=text[:100],  # 截取前100字
                duration=avg_duration,
                keywords=[],
                visual_type='image',
                search_query='education learning',
                scene_description=text[:50]
            )
            segments.append(segment)
        
        return segments

