import hashlib
import os
from pathlib import Path
from typing import List, Optional, Callable, Any

from ..utils.logger import setup_logger
from .asr_data import ASRData, ASRDataSeg
from .base import BaseASR

logger = setup_logger("faster_whisper")


class FasterWhisperASR(BaseASR):
    """
    Faster Whisper ASR - macOS/Python 库版本
    
    使用 Python 的 faster_whisper 库而不是 Windows 可执行文件
    """
    
    def __init__(
        self,
        audio_path: str,
        faster_whisper_program: str,  # 保留参数兼容性，但不使用
        whisper_model: str,
        model_dir: str,
        language: str = "zh",
        device: str = "cpu",
        output_dir: Optional[str] = None,
        output_format: str = "srt",
        use_cache: bool = False,
        need_word_time_stamp: bool = False,
        # VAD 相关参数
        vad_filter: bool = True,
        vad_threshold: float = 0.4,
        vad_method: str = "",
        # 音频处理
        ff_mdx_kim2: bool = False,
        # 文本处理参数
        one_word: int = 0,
        sentence: bool = False,
        max_line_width: int = 100,
        max_line_count: int = 1,
        max_comma: int = 20,
        max_comma_cent: int = 50,
        prompt: Optional[str] = None,
    ):
        super().__init__(audio_path, use_cache)

        # 基本参数
        self.model_path = whisper_model
        self.model_dir = model_dir
        self.need_word_time_stamp = need_word_time_stamp
        self.language = language
        self.device = device
        self.output_dir = output_dir
        self.output_format = output_format

        # VAD 参数
        self.vad_filter = vad_filter
        self.vad_threshold = vad_threshold
        self.vad_method = vad_method

        # 音频处理参数
        self.ff_mdx_kim2 = ff_mdx_kim2

        # 文本处理参数
        self.one_word = one_word
        self.sentence = sentence
        self.max_line_width = max_line_width
        self.max_line_count = max_line_count
        self.max_comma = max_comma
        self.max_comma_cent = max_comma_cent
        self.prompt = prompt

        # 断句宽度
        if self.language in ["zh", "ja", "ko"]:
            self.max_line_width = 30
        else:
            self.max_line_width = 90

        # 断句选项
        if self.need_word_time_stamp:
            self.one_word = 1
        else:
            self.one_word = 0
            self.sentence = True

        # 检查 Python 库是否安装
        try:
            import faster_whisper
            logger.info(f"✅ 使用 Python 版本的 faster-whisper: {faster_whisper.__version__}")
        except ImportError:
            raise EnvironmentError(
                "faster-whisper Python 库未安装。\n"
                "请运行: python -m pip install faster-whisper"
            )

        # 检查模型是否存在
        # 模型路径可能是 "large-v2" 或 "faster-whisper-large-v2"
        # 先尝试完整路径，如果不存在则添加前缀
        model_full_path = Path(model_dir) / whisper_model
        if not model_full_path.exists():
            # 如果不存在，尝试添加 "faster-whisper-" 前缀
            if not whisper_model.startswith("faster-whisper-"):
                model_full_path = Path(model_dir) / f"faster-whisper-{whisper_model}"
        
        if not model_full_path.exists():
            raise EnvironmentError(
                f"模型未找到: {model_full_path}\n"
                f"请在程序设置中下载模型，或手动下载到指定目录。\n"
                f"已尝试的路径:\n"
                f"  - {Path(model_dir) / whisper_model}\n"
                f"  - {model_full_path}"
            )
        
        self.model_full_path = model_full_path
        logger.info(f"使用模型: {model_full_path}")
        logger.info(f"设备: {device}")
        logger.info(f"语言: {language}")

    def _make_segments(self, resp_data: str) -> List[ASRDataSeg]:
        """将 SRT 格式数据转换为 ASRDataSeg 列表"""
        asr_data = ASRData.from_srt(resp_data)
        # 过滤掉纯音乐标记
        filtered_segments = []
        for seg in asr_data.segments:
            text = seg.text.strip()
            if not (
                text.startswith("【")
                or text.startswith("[")
                or text.startswith("(")
                or text.startswith("（")
            ):
                filtered_segments.append(seg)
        return filtered_segments

    def _run(
        self, callback: Optional[Callable[[int, str], None]] = None, **kwargs: Any
    ) -> str:
        """
        使用 Python 的 faster_whisper 库进行转录
        """
        def _default_callback(x, y):
            pass

        if callback is None:
            callback = _default_callback

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise EnvironmentError(
                "faster-whisper 库未安装。请运行: python -m pip install faster-whisper"
            )

        callback(5, "正在加载模型...")
        
        # 使用在 __init__ 中确定的完整模型路径
        model_full_path = self.model_full_path
        
        # 确定计算类型
        # macOS 上通常使用 int8 来减少内存占用
        compute_type = "int8" if self.device == "cpu" else "float16"
        
        logger.info(f"加载模型: {model_full_path}")
        logger.info(f"计算类型: {compute_type}")
        
        try:
            # 加载模型
            model = WhisperModel(
                str(model_full_path),
                device=self.device,
                compute_type=compute_type,
                num_workers=1  # macOS 上使用单线程更稳定
            )
            logger.info("✅ 模型加载成功")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise EnvironmentError(f"无法加载模型: {e}")

        callback(10, "开始转录...")

        # 准备转录参数
        transcribe_params = {
            "language": self.language,
            "task": "transcribe",
            "vad_filter": self.vad_filter,
        }
        
        if self.vad_filter:
            transcribe_params["vad_parameters"] = {
                "threshold": self.vad_threshold,
            }
        
        if self.prompt:
            transcribe_params["initial_prompt"] = self.prompt
        
        if self.need_word_time_stamp:
            transcribe_params["word_timestamps"] = True
        
        logger.info(f"转录参数: {transcribe_params}")
        
        try:
            # 执行转录
            segments, info = model.transcribe(
                self.audio_path,
                **transcribe_params
            )
            
            logger.info(f"检测到的语言: {info.language} (概率: {info.language_probability:.2f})")
            logger.info(f"音频时长: {info.duration:.2f}秒")
            
            callback(15, "正在处理转录结果...")
            
            # 收集所有片段
            all_segments = []
            segment_count = 0
            
            for segment in segments:
                segment_count += 1
                
                # 每10个片段更新一次进度
                if segment_count % 10 == 0:
                    progress = min(15 + int(segment_count * 0.7), 85)
                    callback(progress, f"处理中: {segment_count} 个片段...")
                
                all_segments.append(segment)
            
            logger.info(f"共转录 {segment_count} 个片段")
            
            callback(90, "生成字幕文件...")
            
            # 转换为 SRT 格式
            srt_content = self._segments_to_srt(all_segments)
            
            callback(100, "转录完成")
            logger.info("✅ 转录完成")
            
            return srt_content
            
        except Exception as e:
            logger.error(f"转录失败: {e}")
            raise RuntimeError(f"转录过程出错: {e}")

    def _segments_to_srt(self, segments) -> str:
        """将 faster_whisper 的 segments 转换为 SRT 格式"""
        srt_lines = []
        
        for i, segment in enumerate(segments, start=1):
            # 格式化时间戳
            start_time = self._format_timestamp(segment.start)
            end_time = self._format_timestamp(segment.end)
            
            # SRT 格式
            srt_lines.append(str(i))
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(segment.text.strip())
            srt_lines.append("")  # 空行
        
        return "\n".join(srt_lines)
    
    def _format_timestamp(self, seconds: float) -> str:
        """将秒数转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

    def _get_key(self):
        """获取缓存key"""
        # 使用模型路径和参数生成唯一key
        key_str = f"{self.model_path}-{self.language}-{self.device}-{self.vad_filter}"
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{self.crc32_hex}-{key_hash}"
