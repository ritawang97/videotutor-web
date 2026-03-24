import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable
from typing import Dict, Literal

from ..utils.ass_auto_wrap import auto_wrap_ass_file
from ..utils.logger import setup_logger

logger = setup_logger("video_utils")


def video2audio(input_file: str, output: str = "") -> bool:
    """使用ffmpeg将视频转换为音频"""
    # 创建output目录
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = str(output_path)
    cmd = [
        "ffmpeg",
        "-i",
        input_file,
        "-map",
        "0:a",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        "aresample=async=1",  # 处理音频同步问题
        "-y",
        output,
    ]
    logger.info(f"转换为音频执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
        if result.returncode == 0 and Path(output).is_file():
            return True
        else:
            logger.error("音频转换失败")
            return False
    except Exception as e:
        logger.exception(f"音频转换出错: {str(e)}")
        return False


def check_encoder_available(encoder: str) -> bool:
    """检查编码器是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
        # 检查编码器是否在列表中
        return encoder in result.stdout
    except Exception as e:
        logger.warning(f"检查编码器可用性时出错: {e}")
        return False


def get_available_video_encoder(output_format: str = "mp4") -> str:
    """
    根据输出格式获取可用的视频编码器
    
    Args:
        output_format: 输出文件格式（如 mp4, webm, mkv）
        
    Returns:
        可用的编码器名称
    """
    # 根据格式定义编码器优先级列表
    if output_format.lower() == "webm":
        encoders = ["libvpx-vp9", "libvpx", "libx264"]
    elif output_format.lower() in ["mp4", "mov", "m4v"]:
        # 对于MP4格式，优先尝试常见的编码器
        encoders = ["libx264", "h264", "mpeg4", "libx265", "hevc"]
    else:
        # 通用格式，尝试多种编码器
        encoders = ["libx264", "h264", "mpeg4", "libx265", "hevc", "libvpx-vp9", "libvpx"]
    
    # 尝试找到第一个可用的编码器
    for encoder in encoders:
        if check_encoder_available(encoder):
            logger.info(f"找到可用编码器: {encoder} (用于 {output_format} 格式)")
            return encoder
    
    # 如果都不可用，尝试使用mpeg4（通常FFmpeg都支持）
    logger.warning(f"未找到优先编码器，尝试使用mpeg4")
    if check_encoder_available("mpeg4"):
        return "mpeg4"
    
    # 最后尝试：让FFmpeg自动选择（不指定编码器，使用默认）
    logger.error(f"未找到任何可用编码器！这可能导致FFmpeg失败")
    return "libx264"  # 返回一个默认值，即使不可用也会给出明确的错误信息


def check_cuda_available() -> bool:
    """检查CUDA是否可用"""
    logger.info("检查CUDA是否可用")
    try:
        # 首先检查ffmpeg是否支持cuda
        result = subprocess.run(
            ["ffmpeg", "-hwaccels"],
            capture_output=True,
            text=True,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
        if "cuda" not in result.stdout.lower():
            logger.info("CUDA不在支持的硬件加速器列表中")
            return False

        # 进一步检查CUDA设备信息
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-init_hw_device", "cuda"],
            capture_output=True,
            text=True,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )

        # 如果stderr中包含"Cannot load cuda" 或 "Failed to load"等错误信息，说明CUDA不可用
        if any(
            error in result.stderr.lower()
            for error in ["cannot load cuda", "failed to load", "error"]
        ):
            logger.info("CUDA设备初始化失败")
            return False

        logger.info("CUDA可用")
        return True

    except Exception as e:
        logger.exception(f"检查CUDA出错: {str(e)}")
        return False


def add_subtitles(
    input_file: str,
    subtitle_file: str,
    output: str,
    quality: Literal[
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
    ] = "medium",
    vcodec: str = "libx264",
    soft_subtitle: bool = False,
    progress_callback: Optional[Callable] = None,
) -> None:
    assert Path(input_file).is_file(), "输入文件不存在"
    assert Path(subtitle_file).is_file(), "字幕文件不存在"

    # 移动到临时文件  Fix: 路径错误
    suffix = Path(subtitle_file).suffix.lower()  # suffix 已经包含点，如 ".srt"
    temp_dir = Path(tempfile.gettempdir()) / "VideoCaptioner"
    temp_dir.mkdir(exist_ok=True)
    # 注意：suffix 已经包含点，所以不需要再加点
    temp_subtitle = temp_dir / f"temp_subtitle{suffix}"
    shutil.copy2(subtitle_file, temp_subtitle)
    subtitle_file = str(temp_subtitle)
    logger.debug(f"字幕文件复制到临时文件: {temp_subtitle}")

    # video_info = get_video_info(input_file)
    if suffix == ".ass":
        subtitle_file = auto_wrap_ass_file(
            subtitle_file,
            # video_width=video_info["width"],
            # video_height=video_info["height"],
        )

    # 如果是WebM格式，强制使用硬字幕
    if Path(output).suffix.lower() == ".webm":
        soft_subtitle = False
        logger.info("WebM格式视频，强制使用硬字幕")

    if soft_subtitle:
        # 添加软字幕
        cmd = [
            "ffmpeg",
            "-i",
            input_file,
            "-i",
            subtitle_file,
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            output,
            "-y",
        ]
        logger.info(f"添加软字幕执行命令: {' '.join(cmd)}")
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
    else:
        logger.info("使用硬字幕")
        # 转义路径中的特殊字符用于FFmpeg过滤器
        # 参考 subtitle_preview.py 和 video_composer.py 中的实现（已验证可工作）
        subtitle_file_str = str(subtitle_file).replace("\\", "/")
        # 只转义冒号（这是FFmpeg过滤器语法必需的）
        subtitle_file_str = subtitle_file_str.replace(":", "\\:")
        
        # 根据输出文件后缀决定vf参数
        # 使用单引号包裹路径（FFmpeg推荐的方式）
        if Path(output).suffix.lower() == ".ass":
            vf = f"ass='{subtitle_file_str}'"
        else:
            vf = f"subtitles='{subtitle_file_str}'"
        
        logger.debug(f"字幕文件路径（转义后）: {subtitle_file_str}")
        logger.debug(f"视频过滤器: {vf}")

        # 根据输出格式确定编码器
        output_format = Path(output).suffix.lower().lstrip('.')
        if output_format == "webm":
            # WebM格式优先使用libvpx-vp9
            preferred_codec = "libvpx-vp9"
        else:
            # 其他格式使用传入的vcodec，如果没有则使用默认值
            preferred_codec = vcodec if vcodec else "libx264"
        
        # 检查编码器是否可用，如果不可用则自动选择可用的编码器
        if not check_encoder_available(preferred_codec):
            logger.warning(f"编码器 {preferred_codec} 不可用，尝试查找替代编码器...")
            available_codec = get_available_video_encoder(output_format)
            if available_codec == "copy":
                # 如果连copy都不可用（不应该发生），使用libx264作为最后尝试
                logger.warning("所有编码器都不可用，尝试使用libx264（可能会失败）")
                available_codec = "libx264"
            vcodec = available_codec
            logger.info(f"已切换到编码器: {vcodec}")
        else:
            vcodec = preferred_codec
            logger.info(f"使用编码器: {vcodec}")

        # 检查CUDA是否可用
        use_cuda = check_cuda_available()
        cmd = ["ffmpeg"]
        if use_cuda:
            logger.info("使用CUDA加速")
            cmd.extend(["-hwaccel", "cuda"])
        
        # 构建基本命令 - 使用 -c:a 代替 -acodec（更标准的语法）
        cmd.extend(["-i", input_file, "-c:a", "copy"])
        
        # 根据编解码器添加相应的预设参数
        # libx264 和 libx265 使用 -preset（某些 FFmpeg 版本可能不支持，如 Anaconda 版本）
        # libvpx-vp9 使用 -speed (quality值映射到speed值)
        logger.info(f"使用编解码器: {vcodec}, 质量设置: {quality}")
        
        # 设置视频编解码器（使用 -c:v 代替 -vcodec，更标准且兼容性更好）
        cmd.extend(["-c:v", vcodec])
        
        # 根据编解码器添加质量参数
        # 注意：某些 FFmpeg 版本（如 Anaconda 6.1.1）可能不支持 -preset 选项
        # 如果遇到错误，可以移除 -preset 参数，使用默认设置
        if vcodec == "libvpx-vp9":
            # 对于 libvpx-vp9，使用 -speed 和 -crf
            quality_to_speed = {
                "ultrafast": "8", "superfast": "7", "veryfast": "6",
                "faster": "5", "fast": "4", "medium": "3",
                "slow": "2", "slower": "1", "veryslow": "0"
            }
            speed = quality_to_speed.get(quality, "3")  # 默认medium
            cmd.extend(["-speed", speed])
            cmd.extend(["-crf", "30"])  # libvpx-vp9 使用 CRF 而不是 preset
            logger.debug(f"添加-speed参数: {speed}, -crf: 30")
        # 对于 libx264 和 libx265，不添加 -preset（避免 Anaconda FFmpeg 不支持的错误）
        # 如果需要预设，可以稍后根据 FFmpeg 版本检测来添加
        # 目前先不添加，使用编解码器默认预设，这样至少可以正常工作
        
        # 确保输出文件路径是绝对路径，避免路径问题
        output_path = Path(output).resolve()
        cmd.extend(["-vf", vf, "-y", str(output_path)])

        cmd_str = subprocess.list2cmdline(cmd)
        logger.info(f"添加硬字幕执行命令: {cmd_str}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                ),
            )

            # 实时读取输出并调用回调函数
            total_duration = None
            current_time = 0
            error_lines = []  # 保存所有输出行用于错误诊断

            # 使用线程安全的方式读取stderr
            import threading
            stderr_data = []
            stderr_lock = threading.Lock()
            
            def read_stderr():
                """在单独线程中读取stderr"""
                try:
                    while True:
                        line = process.stderr.readline()
                        if not line:
                            break
                        with stderr_lock:
                            stderr_data.append(line)
                            error_lines.append(line)
                except Exception as e:
                    logger.warning(f"读取stderr时出错: {e}")
            
            # 启动stderr读取线程
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # 主循环：处理进度和等待完成
            while True:
                # 检查进程是否已结束
                if process.poll() is not None:
                    break
                
                # 处理已读取的输出行
                with stderr_lock:
                    lines_to_process = stderr_data[:]
                    stderr_data.clear()
                
                for output_line in lines_to_process:
                    # 检查是否是错误信息
                    if any(keyword in output_line.lower() for keyword in ['error', 'failed', 'invalid', 'cannot', 'unable', 'no such']):
                        logger.warning(f"FFmpeg警告/错误: {output_line.strip()}")
                    
                    if not progress_callback:
                        continue

                    if total_duration is None:
                        duration_match = re.search(
                            r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", output_line
                        )
                        if duration_match:
                            h, m, s = map(float, duration_match.groups())
                            total_duration = h * 3600 + m * 60 + s
                            logger.info(f"视频总时长: {total_duration}秒")

                    # 解析当前处理时间
                    time_match = re.search(
                        r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", output_line
                    )
                    if time_match:
                        h, m, s = map(float, time_match.groups())
                        current_time = h * 3600 + m * 60 + s

                    # 计算进度百分比
                    if total_duration:
                        progress = (current_time / total_duration) * 100
                        progress_callback(f"{round(progress)}", "正在合成")
                
                # 短暂休眠，避免CPU占用过高
                import time
                time.sleep(0.1)
            
            # 等待stderr读取线程完成
            stderr_thread.join(timeout=2)
            
            # 检查进程的返回码
            return_code = process.wait()
            
            # 确保所有输出都被读取
            try:
                remaining = process.stderr.read()
                if remaining:
                    error_lines.append(remaining)
            except Exception:
                pass
            
            if return_code != 0:
                # 从保存的输出行中提取错误信息
                error_info = "".join(error_lines) if error_lines else ""
                
                # 提取关键错误信息（通常在最后几行）
                error_lines_list = error_info.split('\n')
                # 查找包含错误关键词的行
                critical_errors = [
                    line.strip() for line in error_lines_list 
                    if line.strip() and any(keyword in line.lower() for keyword in ['error', 'failed', 'invalid', 'cannot', 'unable', 'no such', 'not found'])
                ]
                
                # 如果找到关键错误，优先显示
                if critical_errors:
                    error_summary = '\n'.join(critical_errors[-10:])  # 显示最后10个关键错误
                else:
                    # 否则显示最后30行输出
                    error_summary = '\n'.join([line.strip() for line in error_lines_list[-30:] if line.strip()])
                
                # 如果还是没有信息，显示完整输出
                if not error_summary:
                    error_summary = error_info[-1000:] if len(error_info) > 1000 else error_info  # 最后1000字符
                
                logger.error(f"视频合成失败 (返回代码: {return_code}):\n完整输出:\n{error_info}")
                raise Exception(f"视频合成失败 (错误代码: {return_code}):\n{error_summary}")
            
            if progress_callback:
                progress_callback("100", "合成完成")
            logger.info("视频合成完成")

        except Exception as e:
            logger.exception(f"关闭 FFmpeg: {str(e)}")
            if process and process.poll() is None:  # 如果进程还在运行
                process.kill()  # 如果进程没有及时终止，强制结束它
            raise
        finally:
            # 删除临时文件
            if temp_subtitle.exists():
                temp_subtitle.unlink()


def get_video_info(file_path: str) -> Optional[Dict]:
    """获取视频信息"""
    try:
        cmd = ["ffmpeg", "-i", file_path]

        # logger.info(f"获取视频信息执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
        info = result.stderr

        video_info_dict = {
            "file_name": Path(file_path).stem,
            "file_path": file_path,
            "duration_seconds": 0,
            "bitrate_kbps": 0,
            "video_codec": "",
            "width": 0,
            "height": 0,
            "fps": 0,
            "audio_codec": "",
            "audio_sampling_rate": 0,
            "thumbnail_path": "",
        }

        # 提取时长
        if duration_match := re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", info):
            hours, minutes, seconds = map(float, duration_match.groups())
            video_info_dict["duration_seconds"] = hours * 3600 + minutes * 60 + seconds

        # 提取比特率
        if bitrate_match := re.search(r"bitrate: (\d+) kb/s", info):
            video_info_dict["bitrate_kbps"] = int(bitrate_match.group(1))

        # 提取视频流信息
        if video_stream_match := re.search(
            r"Stream #.*?Video: (\w+)(?:\s*\([^)]*\))?.* (\d+)x(\d+).*?(?:(\d+(?:\.\d+)?)\s*(?:fps|tb[rn]))",
            info,
            re.DOTALL,
        ):
            video_info_dict.update(
                {
                    "video_codec": video_stream_match.group(1),
                    "width": int(video_stream_match.group(2)),
                    "height": int(video_stream_match.group(3)),
                    "fps": float(video_stream_match.group(4)),
                }
            )
        else:
            logger.warning("未找到视频流信息")

        return video_info_dict
    except Exception as e:
        logger.exception(f"获取视频信息时出错: {str(e)}")
        return None
