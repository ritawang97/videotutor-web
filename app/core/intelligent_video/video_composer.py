# -*- coding: utf-8 -*-
"""
视频合成器：将所有片段合成为最终视频
"""

import subprocess
import shutil
import random
from pathlib import Path
from typing import List, Dict, Optional
from .scene_analyzer import SceneSegment
from .video_processor import ImageToVideoConverter, VideoClipper
from .material_searcher import MaterialSearcher

from app.core.utils.logger import setup_logger

logger = setup_logger("VideoComposer")


class IntelligentVideoComposer:
    """智能视频合成器"""
    
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.temp_dir = work_dir / 'temp_video_compose'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def compose_video(self,
                     scenes: List[SceneSegment],
                     materials: Dict[int, List[Path]],
                     audio_path: Path,
                     subtitle_path: Optional[Path],
                     output_path: Path,
                     add_transitions: bool = True,
                     auto_supplement_materials: bool = True) -> Path:
        """
        合成最终视频
        
        参数：
        - scenes: 场景列表
        - materials: {scene_index: [material_paths]}
        - audio_path: 音频文件
        - subtitle_path: 字幕文件
        - output_path: 输出路径
        - add_transitions: 是否添加转场
        - auto_supplement_materials: 是否自动补充素材
        """
        logger.info("开始智能视频合成...")
        
        try:
            # 步骤1：预处理所有素材
            logger.info("步骤1/5: 预处理素材...")
            processed_clips = self._preprocess_materials(scenes, materials)
            
            # 步骤1.5：检查素材时长是否足够，不够则自动补充
            if auto_supplement_materials:
                logger.info("步骤2/5: 检查素材时长并自动补充...")
                processed_clips = self._auto_supplement_materials(processed_clips, audio_path, scenes)
            
            # 步骤3：拼接视频
            logger.info("步骤3/5: 拼接视频片段...")
            concatenated_video = self._concatenate_clips(processed_clips, add_transitions)
            
            # 步骤4：合成音频
            logger.info("步骤4/5: 合成音频...")
            video_with_audio = self._merge_audio_video(concatenated_video, audio_path)
            
            # 步骤5：嵌入字幕（如果提供了字幕文件）
            if subtitle_path and subtitle_path.exists():
                logger.info("步骤5/5: 嵌入字幕...")
                self._embed_subtitle(video_with_audio, subtitle_path, output_path)
            else:
                logger.info("步骤5/5: 跳过字幕（未提供字幕文件）...")
                # 直接复制或移动文件
                shutil.copy(video_with_audio, output_path)
            
            logger.info(f"视频合成完成: {output_path}")
            
            # 清理临时文件
            self._cleanup_temp_files()
            
            return output_path
            
        except Exception as e:
            logger.error(f"视频合成失败: {e}")
            raise
    
    def _preprocess_materials(self,
                             scenes: List[SceneSegment],
                             materials: Dict[int, List[Path]]) -> List[Path]:
        """预处理所有素材
        改进：每个场景尽量使用多个素材切分时长，避免长时间同一画面
        """
        processed_clips = []
        image_converter = ImageToVideoConverter()
        video_clipper = VideoClipper()

        for scene in scenes:
            scene_materials = [p for p in materials.get(scene.index, []) if p]

            # 若没有素材，创建带提示的黑屏
            if not scene_materials:
                scene_clip = self._create_black_clip(scene)
                normalized_clip = self._normalize_clip(scene_clip, scene.index)
                processed_clips.append(normalized_clip)
                continue

            # 根据素材数量分配每段时长（限制单段3-15秒）
            num_segments = max(1, len(scene_materials))
            per_duration = max(3.0, min(15.0, scene.duration / num_segments))
            remaining = float(scene.duration)

            # 为该场景生成多个子片段
            subclips: List[Path] = []
            for idx, material_path in enumerate(scene_materials):
                if remaining <= 0:
                    break

                current_duration = per_duration if idx < len(scene_materials) - 1 else remaining
                current_duration = max(1.0, float(current_duration))

                raw_clip = self.temp_dir / f"clip_{scene.index}_{idx}.mp4"

                ext = material_path.suffix.lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # 图片转视频
                    image_converter.convert_image_to_video(
                        material_path,
                        raw_clip,
                        current_duration,
                        effect='ken_burns'
                    )
                else:
                    # 视频剪辑
                    start_time = video_clipper.auto_select_best_segment(
                        material_path,
                        current_duration
                    )
                    video_clipper.clip_video(
                        material_path,
                        raw_clip,
                        start_time,
                        current_duration
                    )

                # 标准化每个子片段
                normalized = self._normalize_clip(raw_clip, scene.index * 100 + idx)
                subclips.append(normalized)
                remaining -= current_duration

                if remaining <= 0:
                    break

            # 将多个子片段合成为该场景的最终片段
            scene_clip = self.temp_dir / f"clip_{scene.index}.mp4"
            if len(subclips) == 1:
                shutil.copy(subclips[0], scene_clip)
            else:
                list_file = self.temp_dir / f"scene_{scene.index}_list.txt"
                with open(list_file, 'w', encoding='utf-8') as f:
                    for c in subclips:
                        f.write(f"file '{c.absolute()}'\n")

                cmd = [
                    'ffmpeg', '-f', 'concat', '-safe', '0',
                    '-i', str(list_file), '-c:v', 'copy', '-y', str(scene_clip)
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError:
                    # 回退到重新编码
                    cmd = [
                        'ffmpeg', '-f', 'concat', '-safe', '0',
                        '-i', str(list_file),
                        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                        '-pix_fmt', 'yuv420p', '-r', '30', '-y', str(scene_clip)
                    ]
                    subprocess.run(cmd, check=True, capture_output=True, text=True)

            # 场景最终片段再做一次标准化（保持一致参数）
            normalized_clip = self._normalize_clip(scene_clip, scene.index)
            processed_clips.append(normalized_clip)

        return processed_clips
    
    def _auto_supplement_materials(self, processed_clips: List[Path], audio_path: Path, scenes: List[SceneSegment]) -> List[Path]:
        """
        自动补充素材：检查视频总时长是否足够，不够则搜索更多素材
        """
        # 计算当前视频总时长
        current_duration = sum(self._get_duration(clip) for clip in processed_clips)
        audio_duration = self._get_duration(audio_path)
        
        logger.info(f"当前视频总时长: {current_duration:.2f}秒")
        logger.info(f"TTS音频时长: {audio_duration:.2f}秒")
        
        # 如果视频时长足够（留2秒容差），直接返回
        if current_duration >= audio_duration - 2:
            logger.info("视频时长充足，无需补充素材")
            return processed_clips
        
        # 计算需要补充的时长
        shortage = audio_duration - current_duration + 2  # 多补充2秒缓冲
        logger.info(f"需要补充 {shortage:.2f} 秒的素材")
        
        # 搜索补充素材
        try:
            from .material_searcher import MaterialSearcher
            searcher = MaterialSearcher()
            
            # 使用通用关键词搜索补充素材
            supplement_keywords = [
                "business meeting", "office work", "team collaboration", "presentation",
                "technology", "innovation", "success", "growth", "future", "strategy",
                "data analysis", "digital transformation", "leadership", "communication"
            ]
            
            # 随机选择几个关键词
            import random
            selected_keywords = random.sample(supplement_keywords, min(3, len(supplement_keywords)))
            
            supplement_clips = []
            remaining_shortage = shortage
            
            for keyword in selected_keywords:
                if remaining_shortage <= 0:
                    break
                
                logger.info(f"搜索补充素材: {keyword}")
                
                # 搜索素材（优先视频）
                materials = searcher.search_materials(
                    query=keyword,
                    material_type="video",  # 优先视频
                    count=2
                )
                
                if not materials:
                    # 如果没找到视频，尝试图片
                    materials = searcher.search_materials(
                        query=keyword,
                        material_type="image",
                        count=2
                    )
                
                # 下载并处理素材
                for material in materials[:2]:  # 最多取2个
                    if remaining_shortage <= 0:
                        break
                    
                    try:
                        # 下载素材到缓存目录
                        cache_dir = self.work_dir / "material_cache"
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        
                        # 根据素材类型确定文件扩展名
                        if material.type == "video":
                            file_ext = ".mp4"
                        else:
                            file_ext = ".jpg"
                        
                        material_path = cache_dir / f"supplement_{len(supplement_clips)}{file_ext}"
                        
                        # 下载素材
                        import requests
                        response = requests.get(material.url, timeout=30)
                        response.raise_for_status()
                        
                        with open(material_path, 'wb') as f:
                            f.write(response.content)
                        
                        # 计算使用时长（8-15秒之间）
                        clip_duration = min(15.0, max(8.0, remaining_shortage * 0.7))
                        
                        # 处理素材
                        processed_clip = self._process_supplement_material(material_path, clip_duration, len(supplement_clips))
                        supplement_clips.append(processed_clip)
                        
                        remaining_shortage -= clip_duration
                        logger.info(f"添加补充素材: {clip_duration:.2f}秒")
                        
                    except Exception as e:
                        logger.error(f"处理补充素材失败: {e}")
                        continue
            
            # 将补充素材添加到原素材列表
            if supplement_clips:
                logger.info(f"成功添加 {len(supplement_clips)} 个补充素材")
                processed_clips.extend(supplement_clips)
            else:
                logger.warning("未找到合适的补充素材")
                
        except Exception as e:
            logger.error(f"自动补充素材失败: {e}")
        
        return processed_clips
    
    def _process_supplement_material(self, material_path: Path, duration: float, index: int) -> Path:
        """处理补充素材"""
        output_clip = self.temp_dir / f"supplement_{index}.mp4"
        
        ext = material_path.suffix.lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # 图片转视频
            from .video_processor import ImageToVideoConverter
            converter = ImageToVideoConverter()
            converter.convert_image_to_video(
                material_path,
                output_clip,
                duration,
                effect='ken_burns'
            )
        else:
            # 视频剪辑
            from .video_processor import VideoClipper
            clipper = VideoClipper()
            start_time = clipper.auto_select_best_segment(material_path, duration)
            clipper.clip_video(material_path, output_clip, start_time, duration)
        
        # 标准化
        normalized_clip = self._normalize_clip(output_clip, 1000 + index)
        return normalized_clip
    
    def _create_black_clip(self, scene: SceneSegment) -> Path:
        """创建黑屏片段（占位符）- 带提示文字"""
        clip_path = self.temp_dir / f"black_{scene.index}.mp4"
        
        # 验证时长，确保是有效的正数
        duration = float(scene.duration)
        if duration <= 0:
            duration = 5.0  # 默认5秒
            logger.warning(f"场景{scene.index}时长无效，使用默认值5秒")
        
        # 创建带文字的黑屏（提示用户配置API）
        # 简化文字，避免中文编码问题和特殊字符转义问题
        # 使用简单的文本，避免冒号等特殊字符
        text = f"Scene {scene.index} - Please configure API"
        # 转义文本中的冒号（drawtext滤镜中冒号是分隔符）
        text_escaped = text.replace(':', '\\:')
        
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f"color=c=black:s=1920x1080:d={duration}",
            '-vf', (
                f"drawtext=text='{text_escaped}':"
                f"fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-y',
            str(clip_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"创建占位符片段: {clip_path}, 时长: {duration}秒")
        except subprocess.CalledProcessError as e:
            logger.error(f"创建占位符失败（带文字），使用纯黑屏: {e.stderr}")
            # 降级：纯黑屏（不带文字）
            cmd_simple = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', f"color=c=black:s=1920x1080:d={duration}",
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-y',
                str(clip_path)
            ]
            try:
                result = subprocess.run(cmd_simple, check=True, capture_output=True, text=True)
                logger.info(f"创建纯黑屏片段: {clip_path}, 时长: {duration}秒")
            except subprocess.CalledProcessError as e2:
                logger.error(f"创建纯黑屏也失败: {e2.stderr}")
                # 最后的降级方案：使用更简单的方法
                # 创建一个1秒的黑屏，然后循环
                if duration > 1:
                    duration = 1.0
                cmd_final = [
                    'ffmpeg',
                    '-f', 'lavfi',
                    '-i', f"color=c=black:s=1920x1080:d={duration}",
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-r', '30',
                    '-y',
                    str(clip_path)
                ]
                subprocess.run(cmd_final, check=True, capture_output=True, text=True)
                logger.warning(f"使用最小化方案创建黑屏: {clip_path}")
        
        return clip_path
    
    def _normalize_clip(self, clip_path: Path, index: int) -> Path:
        """
        统一化视频片段参数，确保所有片段具有相同的编码参数
        - 固定帧率：30fps
        - 固定分辨率：1920x1080
        - 固定编码：H.264
        - 固定像素格式：yuv420p
        """
        normalized_path = self.temp_dir / f"normalized_{index}.mp4"
        
        cmd = [
            'ffmpeg',
            '-i', str(clip_path),
            '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-vsync', 'cfr',  # 恒定帧率
            '-an',  # 暂时移除音频（后面会添加TTS音频）
            '-y',
            str(normalized_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"片段{index}已标准化")
            return normalized_path
        except subprocess.CalledProcessError as e:
            logger.error(f"标准化片段{index}失败: {e.stderr}")
            # 如果失败，返回原片段
            return clip_path
    
    def _concatenate_clips(self, clips: List[Path], add_transitions: bool) -> Path:
        """拼接视频片段（优化版：减少卡顿）"""
        output = self.temp_dir / "concatenated.mp4"
        
        if len(clips) == 1:
            shutil.copy(clips[0], output)
            return output
        
        # 创建文件列表
        list_file = self.temp_dir / "filelist.txt"
        with open(list_file, 'w', encoding='utf-8') as f:
            for clip in clips:
                f.write(f"file '{clip.absolute()}'\n")
        
        # 使用concat demuxer，所有片段已经标准化，可以安全使用-c copy
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(list_file),
            '-c:v', 'copy',
            '-movflags', '+faststart',  # 优化流媒体播放
            '-y',
            str(output)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("视频片段拼接完成（无重新编码）")
        except subprocess.CalledProcessError as e:
            # 如果copy失败，使用重新编码（保持相同参数）
            logger.warning(f"直接拼接失败，尝试重新编码: {e.stderr}")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(list_file),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-movflags', '+faststart',
                '-y',
                str(output)
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("视频片段拼接完成（重新编码）")
        
        return output
    
    def _merge_audio_video(self, video_path: Path, audio_path: Path) -> Path:
        """
        合成音视频 - 优化版：确保音频完整播放
        
        改进：
        1. 移除 -shortest 参数，避免视频提前结束
        2. 如果视频比音频短，搜索额外素材填充
        3. 确保音频完整播放且画面丰富
        """
        output = self.temp_dir / "video_with_audio.mp4"
        
        # 先获取音频和视频的时长
        audio_duration = self._get_duration(audio_path)
        video_duration = self._get_duration(video_path)
        
        logger.info(f"音频时长: {audio_duration:.2f}秒")
        logger.info(f"视频时长: {video_duration:.2f}秒")
        
        # 如果视频比音频短，需要特殊处理
        if video_duration < audio_duration - 2:  # 留2秒容差
            gap = audio_duration - video_duration
            logger.warning(f"视频({video_duration:.2f}s)比音频({audio_duration:.2f}s)短 {gap:.2f}秒")
            logger.info("将搜索并添加额外素材来填充...")
            
            # 搜索并添加额外素材
            extended_video = self.temp_dir / "extended_video.mp4"
            self._extend_video_with_materials(video_path, extended_video, audio_duration)
            video_path = extended_video
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-i', str(audio_path),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            # 移除 -shortest，让音频完整播放
            '-y',
            str(output)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("音视频合成完成")
        except subprocess.CalledProcessError as e:
            # 如果失败，重新编码视频
            logger.warning(f"直接合成失败，尝试重新编码: {e.stderr}")
            cmd[6] = 'libx264'
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("音视频合成完成（重新编码）")
        
        return output
    
    def _get_duration(self, file_path: Path) -> float:
        """获取视频或音频的时长"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            logger.error(f"获取时长失败: {e}")
            return 0.0
    
    def _extend_video_with_materials(self, input_video: Path, output_video: Path, target_duration: float):
        """
        使用额外素材延长视频 - 优化版：自动搜索多个素材
        
        改进：
        1. 搜索多个相关素材（视频优先）
        2. 随机选择并处理素材
        3. 拼接成完整视频
        4. 比冻结单帧更生动
        """
        logger.info(f"延长视频到 {target_duration:.2f} 秒，使用额外素材")
        
        # 获取原始视频时长
        original_duration = self._get_duration(input_video)
        extend_duration = target_duration - original_duration
        
        if extend_duration <= 0:
            shutil.copy(input_video, output_video)
            return
        
        logger.info(f"需要填充 {extend_duration:.2f} 秒的内容")
        
        # 搜索额外素材
        try:
            extra_clips = self._search_and_prepare_extra_materials(extend_duration)
            
            if not extra_clips:
                logger.warning("未找到额外素材，使用冻结最后一帧作为备选方案")
                self._extend_video_freeze(input_video, output_video, target_duration)
                return
            
            # 拼接原视频和额外素材
            concat_list = self.temp_dir / "extend_list.txt"
            with open(concat_list, 'w') as f:
                f.write(f"file '{input_video.absolute()}'\n")
                for clip in extra_clips:
                    f.write(f"file '{clip.absolute()}'\n")
            
            cmd_concat = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',
                '-y',
                str(output_video)
            ]
            
            subprocess.run(cmd_concat, check=True, capture_output=True, text=True)
            logger.info(f"✅ 视频已延长 {extend_duration:.2f} 秒（使用 {len(extra_clips)} 个额外素材）")
            
        except Exception as e:
            logger.error(f"搜索额外素材失败: {e}，使用冻结最后一帧作为备选")
            self._extend_video_freeze(input_video, output_video, target_duration)
    
    def _search_and_prepare_extra_materials(self, needed_duration: float) -> List[Path]:
        """
        搜索并准备额外素材
        
        策略：
        1. 搜索通用主题的素材（如：总结、结尾、展望等）
        2. 视频优先，图片作为补充
        3. 处理成标准格式
        """
        logger.info("开始搜索额外素材...")
        
        # 通用的补充素材关键词（适合视频结尾）
        search_keywords = [
            "conclusion, summary, ending",
            "future vision, looking forward",
            "success, achievement, positive outcome",
            "team work, collaboration",
            "technology, innovation, modern",
        ]
        
        extra_clips = []
        total_duration = 0
        
        # 初始化素材搜索器
        try:
            searcher = MaterialSearcher()
        except Exception as e:
            logger.error(f"初始化素材搜索器失败: {e}")
            return []
        
        # 尝试搜索素材，直到满足时长
        for keywords in search_keywords:
            if total_duration >= needed_duration:
                break
            
            try:
                logger.info(f"搜索关键词: {keywords}")
                
                # 搜索视频素材（优先）
                materials = searcher.search(keywords, material_type='video', limit=2)
                
                # 如果视频不够，补充图片
                if len(materials) < 2:
                    materials.extend(searcher.search(keywords, material_type='image', limit=1))
                
                if not materials:
                    continue
                
                # 随机选择一个素材
                material = random.choice(materials)
                
                # 下载素材
                material_path = searcher.download(material)
                if not material_path:
                    continue
                
                # 确定这个片段的时长（最多30秒一个片段，避免太单调）
                clip_duration = min(30, needed_duration - total_duration + 2)
                
                # 处理素材
                clip_path = self.temp_dir / f"extra_clip_{len(extra_clips)}.mp4"
                
                if material_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # 图片转视频
                    converter = ImageToVideoConverter()
                    converter.convert_image_to_video(
                        material_path,
                        clip_path,
                        clip_duration,
                        effect='ken_burns'
                    )
                else:
                    # 视频剪辑
                    clipper = VideoClipper()
                    start_time = clipper.auto_select_best_segment(material_path, clip_duration)
                    clipper.clip_video(material_path, clip_path, start_time, clip_duration)
                
                # 标准化
                normalized_clip = self._normalize_clip(clip_path, len(extra_clips) + 1000)
                
                extra_clips.append(normalized_clip)
                total_duration += clip_duration
                
                logger.info(f"添加素材 {len(extra_clips)}: {clip_duration:.1f}秒 (总计: {total_duration:.1f}秒)")
                
                # 如果已经足够，停止搜索
                if total_duration >= needed_duration:
                    break
                    
            except Exception as e:
                logger.warning(f"处理素材失败: {e}，继续下一个")
                continue
        
        logger.info(f"共准备 {len(extra_clips)} 个额外素材，总时长 {total_duration:.1f}秒")
        return extra_clips
    
    def _extend_video_freeze(self, input_video: Path, output_video: Path, target_duration: float):
        """
        备选方案：通过冻结最后一帧来延长视频
        """
        logger.info(f"使用冻结最后一帧方案")
        
        original_duration = self._get_duration(input_video)
        extend_duration = target_duration - original_duration
        
        if extend_duration <= 0:
            shutil.copy(input_video, output_video)
            return
        
        # 提取最后一帧
        last_frame = self.temp_dir / "last_frame.png"
        cmd_extract = [
            'ffmpeg',
            '-sseof', '-1',
            '-i', str(input_video),
            '-update', '1',
            '-q:v', '1',
            '-y',
            str(last_frame)
        ]
        subprocess.run(cmd_extract, check=True, capture_output=True)
        
        # 将最后一帧转换为视频
        frozen_video = self.temp_dir / "frozen.mp4"
        cmd_freeze = [
            'ffmpeg',
            '-loop', '1',
            '-i', str(last_frame),
            '-c:v', 'libx264',
            '-t', str(extend_duration + 0.5),
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-vf', 'scale=1920:1080',
            '-y',
            str(frozen_video)
        ]
        subprocess.run(cmd_freeze, check=True, capture_output=True)
        
        # 拼接
        concat_list = self.temp_dir / "extend_list.txt"
        with open(concat_list, 'w') as f:
            f.write(f"file '{input_video.absolute()}'\n")
            f.write(f"file '{frozen_video.absolute()}'\n")
        
        cmd_concat = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list),
            '-c', 'copy',
            '-y',
            str(output_video)
        ]
        
        subprocess.run(cmd_concat, check=True, capture_output=True)
        logger.info(f"视频已延长 {extend_duration:.2f} 秒（冻结帧）")
    
    def _embed_subtitle(self, video_path: Path, subtitle_path: Path, output_path: Path):
        """
        嵌入字幕（硬字幕）- 优化版：防止字幕跳动
        
        改进：
        1. 明确指定帧率，确保时间戳对齐
        2. 使用force_style优化字幕渲染
        3. 添加vsync参数确保帧同步
        """
        # Windows路径需要转义
        subtitle_path_str = str(subtitle_path).replace('\\', '/')
        subtitle_path_str = subtitle_path_str.replace(':', '\\:')
        
        # 构建字幕滤镜
        # force_style参数可以优化字幕渲染，减少跳动
        vf_filter = f"subtitles='{subtitle_path_str}':force_style='Alignment=2,MarginV=20'"
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', vf_filter,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-r', '30',  # 固定帧率30fps
            '-vsync', 'cfr',  # 恒定帧率模式，确保字幕时间戳准确
            '-c:a', 'copy',
            '-movflags', '+faststart',
            '-y',
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("字幕嵌入完成（优化模式）")
        except subprocess.CalledProcessError as e:
            logger.error(f"字幕嵌入失败: {e.stderr}")
            raise
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("临时文件已清理")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

