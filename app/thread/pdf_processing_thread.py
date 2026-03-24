# -*- coding: utf-8 -*-
import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

from PyQt5.QtCore import QThread, pyqtSignal

try:
    import PyPDF2
    import fitz  # PyMuPDF
    HAS_PDF_LIBS = True
except ImportError:
    HAS_PDF_LIBS = False

from app.common.config import cfg
from app.config import WORK_PATH
from app.core.utils.logger import setup_logger

logger = setup_logger("PDFProcessingThread")


class PDFProcessingThread(QThread):
    """PDF处理线程"""
    
    progress = pyqtSignal(int, str)  # 进度值, 状态信息
    preview_ready = pyqtSignal(str)  # 预览内容
    finished = pyqtSignal(str, str, str)  # script_path, subtitle_path, audio_path
    error = pyqtSignal(str)  # 错误信息

    def __init__(self, pdf_path: str, config: Dict):
        super().__init__()
        self.pdf_path = pdf_path
        self.config = config
        self.is_running = True

    def run(self):
        """主处理流程"""
        try:
            # 检查PDF库
            if not HAS_PDF_LIBS:
                self.error.emit("缺少PDF处理库，请安装 PyPDF2 和 PyMuPDF")
                return

            # 1. 提取PDF内容
            self.progress.emit(10, "正在提取PDF内容...")
            pdf_content = self.extract_pdf_content()
            if not pdf_content.strip():
                self.error.emit("PDF内容提取失败或文件为空")
                return

            # 2. 调用AI生成演讲稿
            self.progress.emit(30, "正在生成演讲稿...")
            script_content = self.generate_script_with_ai(pdf_content)
            if not script_content:
                self.error.emit("演讲稿生成失败")
                return

            # 发送预览
            self.preview_ready.emit(script_content)

            # 3. 保存演讲稿
            self.progress.emit(60, "正在保存演讲稿...")
            script_path = self.save_script(script_content)

            subtitle_path = ""
            audio_path = ""

            # 4. 生成TTS语音（先生成音频，以便字幕同步）
            if self.config.get('generate_audio', False):
                self.progress.emit(70, "正在生成TTS语音...")
                audio_path = self.generate_tts_audio(script_content)

            # 5. 生成字幕文件（基于音频时长）
            if self.config.get('generate_subtitle', False):
                self.progress.emit(85, "正在生成字幕文件...")
                subtitle_path = self.generate_subtitle_file(script_content, audio_path)

            self.progress.emit(100, "处理完成")
            self.finished.emit(script_path, subtitle_path, audio_path)

        except Exception as e:
            logger.error(f"PDF处理失败: {str(e)}")
            self.error.emit(f"处理失败: {str(e)}")

    def extract_pdf_content(self) -> str:
        """提取PDF内容"""
        content = ""
        
        try:
            # 首先尝试使用PyMuPDF（支持图片和复杂布局）
            doc = fitz.open(self.pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 提取文本
                text = page.get_text()
                if text.strip():
                    content += f"\n--- 第{page_num + 1}页 ---\n"
                    content += text
                
                # 检查是否有图片
                image_list = page.get_images()
                if image_list:
                    content += f"\n[该页包含 {len(image_list)} 张图片，需要AI分析]\n"
            
            doc.close()
            
        except Exception as e:
            logger.warning(f"PyMuPDF提取失败，尝试PyPDF2: {e}")
            
            # 备选方案：使用PyPDF2
            try:
                with open(self.pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num, page in enumerate(pdf_reader.pages):
                        text = page.extract_text()
                        if text.strip():
                            content += f"\n--- 第{page_num + 1}页 ---\n"
                            content += text
            except Exception as e2:
                logger.error(f"PyPDF2提取也失败: {e2}")
                raise e2

        return content.strip()

    def generate_script_with_ai(self, pdf_content: str) -> str:
        """使用AI生成演讲稿"""
        ai_service = self.config.get('ai_service', 'OpenAI GPT')
        custom_prompt = self.config.get('custom_prompt', '')
        
        # 构建提示词
        system_prompt = """你是一位资深的演讲稿撰写专家和内容策划师，拥有丰富的公众演讲和内容创作经验。请基于提供的PDF内容，创作一份高质量、引人入胜的演讲稿。

## 核心要求：

### 1. 结构设计
- **开场白**：用引人注目的开头吸引听众注意力（可以是问题、故事、数据或引言）
- **主体内容**：逻辑清晰地展开核心观点，使用"总-分-总"或"问题-分析-解决方案"结构
- **过渡衔接**：在各部分之间加入自然的过渡语句
- **结尾总结**：强化核心信息，给听众留下深刻印象

### 2. 语言风格
- 使用口语化表达，避免书面语的生硬感
- 句子长短搭配，便于朗读和理解
- 适当使用修辞手法（比喻、排比、设问等）增强表现力
- 加入互动元素（如"大家想过这个问题吗？"）

### 3. 内容处理
- 将复杂概念用通俗易懂的语言解释
- 如遇图表数据，要进行生动的描述和深入的解读
- 如有图片内容，请用生动形象的语言详细描述图片场景、要素和含义，让听众能够"看到"图片内容
- 添加具体例子和案例来支撑观点
- 突出关键信息，形成记忆点

### 4. 朗读优化
- 只输出演讲稿本身的内容，不要添加任何无关朗读的信息
- 不要使用加粗、斜体、*号或其他格式标记
- 使用自然的标点符号表示停顿（句号、逗号等）
- 输出纯文本内容，便于直接朗读

### 5. 专业性与趣味性平衡
- 保持内容的准确性和专业深度
- 用生活化的比喻让专业内容更易理解
- 适当加入幽默元素（如果内容允许）
- 确保信息传达的完整性

请直接输出完整的演讲稿内容，字数控制在800-1500字之间，确保内容丰富且适合口语表达。"""

        if custom_prompt.strip():
            system_prompt = custom_prompt

        user_content = f"PDF内容：\n{pdf_content}\n\n请基于以上内容生成演讲稿。"

        # 根据选择的AI服务调用相应的API
        try:
            if ai_service == "OpenAI GPT":
                return self.call_openai_api(system_prompt, user_content)
            elif ai_service == "Google Gemini":
                return self.call_gemini_api(system_prompt, user_content)
            elif ai_service == "Claude":
                return self.call_claude_api(system_prompt, user_content)
            else:
                # 默认使用配置的LLM服务
                return self.call_default_llm_service(system_prompt, user_content)
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            # 如果AI调用失败，返回基础的演讲稿
            return self.generate_fallback_script(pdf_content)

    def call_openai_api(self, system_prompt: str, user_content: str) -> str:
        """调用OpenAI API"""
        try:
            import openai
            
            # 使用应用配置的API密钥
            api_key = cfg.get(cfg.openai_api_key)  # 使用标准的配置读取方式
            if not api_key or api_key.strip() == "":
                raise ValueError("未配置OpenAI API密钥，请在PDF界面或设置中配置")
            
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except ImportError:
            raise ValueError("未安装openai库，请运行: pip install openai")
        except Exception as e:
            raise ValueError(f"OpenAI API调用失败: {e}")

    def call_gemini_api(self, system_prompt: str, user_content: str) -> str:
        """调用Google Gemini API"""
        import time
        
        max_retries = 3
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                import openai
                
                # 使用应用配置的Gemini API密钥和基础URL
                api_key = cfg.get(cfg.gemini_api_key)
                base_url = cfg.get(cfg.gemini_api_base)
                model = cfg.get(cfg.gemini_model)
                
                if not api_key or api_key.strip() == "":
                    raise ValueError("未配置Gemini API密钥，请在PDF界面或设置中配置")
                
                if not base_url or base_url.strip() == "":
                    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                
                if not model or model.strip() == "":
                    model = "gemini-2.0-flash-exp"
                
                logger.info(f"正在调用Gemini API (尝试 {attempt + 1}/{max_retries})...")
                
                # 使用OpenAI兼容的客户端调用Gemini
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=60  # 设置超时时间
                )
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    max_tokens=3000,  # Gemini支持更长的输出
                    temperature=0.7
                )
                
                result = response.choices[0].message.content
                if not result or result.strip() == "":
                    raise ValueError("API返回空内容")
                
                logger.info("Gemini API调用成功")
                return result.strip()
                
            except ImportError:
                raise ValueError("未安装openai库，请运行: pip install openai")
            except Exception as e:
                logger.warning(f"Gemini API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                
                if attempt == max_retries - 1:
                    # 最后一次尝试失败，抛出异常
                    raise ValueError(f"Gemini API调用失败，已重试{max_retries}次: {e}")
                
                # 等待后重试
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避

    def call_claude_api(self, system_prompt: str, user_content: str) -> str:
        """调用Claude API"""
        # 这里可以实现Claude API调用
        # 暂时返回模拟内容
        return self.generate_fallback_script(user_content)

    def call_default_llm_service(self, system_prompt: str, user_content: str) -> str:
        """调用默认的LLM服务"""
        try:
            import openai
            from app.common.config import cfg
            from app.core.entities import LLMServiceEnum
            
            # 获取当前选择的LLM服务配置
            current_service = cfg.llm_service.value
            
            if current_service == LLMServiceEnum.OPENAI:
                base_url = cfg.openai_api_base.value
                api_key = cfg.openai_api_key.value
                model = cfg.openai_model.value
            elif current_service == LLMServiceEnum.SILICON_CLOUD:
                base_url = cfg.silicon_cloud_api_base.value
                api_key = cfg.silicon_cloud_api_key.value
                model = cfg.silicon_cloud_model.value
            elif current_service == LLMServiceEnum.DEEPSEEK:
                base_url = cfg.deepseek_api_base.value
                api_key = cfg.deepseek_api_key.value
                model = cfg.deepseek_model.value
            elif current_service == LLMServiceEnum.GEMINI:
                base_url = cfg.gemini_api_base.value
                api_key = cfg.gemini_api_key.value
                model = cfg.gemini_model.value
            elif current_service == LLMServiceEnum.CHATGLM:
                base_url = cfg.chatglm_api_base.value
                api_key = cfg.chatglm_api_key.value
                model = cfg.chatglm_model.value
            else:
                # 如果没有配置或配置不完整，返回fallback
                logger.warning("未找到有效的LLM服务配置，使用fallback生成")
                return self.generate_fallback_script(user_content)
            
            if not api_key or api_key.strip() == "":
                raise ValueError(f"未配置{current_service.value} API密钥")
            
            # 使用OpenAI兼容的客户端
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=3000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except ImportError:
            logger.error("未安装openai库")
            return self.generate_fallback_script(user_content)
        except Exception as e:
            logger.error(f"LLM服务调用失败: {e}")
            return self.generate_fallback_script(user_content)

    def generate_fallback_script(self, content: str) -> str:
        """生成备用演讲稿（当AI调用失败时）"""
        import re
        
        # 简单的文本处理，生成基础演讲稿结构
        lines = content.split('\n')
        clean_lines = []
        
        # 清理和过滤内容
        for line in lines:
            line = line.strip()
            if line and not line.startswith('---') and len(line) > 3:
                # 移除页码、特殊字符等
                line = re.sub(r'^\d+\s*', '', line)  # 移除开头数字
                line = re.sub(r'[^\w\s\u4e00-\u9fff，。！？；：""''（）【】]', '', line)  # 保留中文和基本标点
                if line:
                    clean_lines.append(line)
        
        # 生成更智能的演讲稿
        script = "各位听众，大家好！\n\n"
        
        # 尝试提取标题或主题
        title_line = ""
        if clean_lines:
            # 通常第一行或最短的行可能是标题
            potential_titles = [line for line in clean_lines[:5] if len(line) < 50]
            if potential_titles:
                title_line = potential_titles[0]
                script += f"今天我要和大家分享的主题是：{title_line}\n\n"
            else:
                script += "今天我要和大家分享一些重要的内容。\n\n"
        
        # 分段处理内容
        current_section = ""
        section_count = 0
        
        for i, line in enumerate(clean_lines[:30]):  # 限制长度
            if line == title_line:  # 跳过已用作标题的行
                continue
                
            # 检查是否是新段落的开始（较短的行或包含关键词）
            is_new_section = (
                len(line) < 30 or 
                any(keyword in line for keyword in ['第一', '第二', '第三', '首先', '其次', '最后', '总结', '结论'])
            )
            
            if is_new_section and current_section:
                # 结束当前段落
                script += f"{current_section}\n\n"
                current_section = ""
                section_count += 1
                
                if section_count >= 3:  # 限制段落数量
                    break
            
            # 添加适合口语的连接词
            if not current_section:
                if section_count == 0:
                    current_section = f"首先，让我们来看看{line}"
                elif section_count == 1:
                    current_section = f"接下来，{line}"
                elif section_count == 2:
                    current_section = f"最后，{line}"
            else:
                # 添加适当的停顿和连接
                if len(current_section) > 100:
                    current_section += f"。\n\n另外，{line}"
                else:
                    current_section += f"，{line}"
        
        # 添加最后一段
        if current_section:
            script += f"{current_section}\n\n"
        
        # 添加结尾
        script += "通过今天的分享，希望能够给大家带来一些启发和思考。\n\n"
        script += "谢谢大家的聆听，如果有任何问题，欢迎交流讨论！"
        
        return script

    def save_script(self, script_content: str) -> str:
        """保存演讲稿"""
        pdf_name = Path(self.pdf_path).stem
        script_filename = f"{pdf_name}_演讲稿.txt"
        script_path = Path(WORK_PATH) / script_filename
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return str(script_path)

    def generate_subtitle_file(self, script_content: str, audio_path: str = None) -> str:
        """
        生成字幕文件
        
        改进：基于实际TTS音频时长生成字幕，确保同步
        """
        pdf_name = Path(self.pdf_path).stem
        subtitle_filename = f"{pdf_name}_字幕.srt"
        subtitle_path = Path(WORK_PATH) / subtitle_filename
        
        # 按句子分割
        sentences = []
        for line in script_content.split('\n'):
            line = line.strip()
            if line:
                # 按标点符号分句
                import re
                parts = re.split(r'[。！？.!?]', line)
                sentences.extend([part.strip() for part in parts if part.strip()])
        
        if not sentences:
            logger.warning("没有提取到句子，使用整段文本")
            sentences = [script_content]
        
        # 获取实际音频时长
        actual_audio_duration = 0
        if audio_path and Path(audio_path).exists():
            try:
                import subprocess
                cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    audio_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                actual_audio_duration = float(result.stdout.strip())
                logger.info(f"实际音频时长: {actual_audio_duration:.2f}秒")
            except Exception as e:
                logger.warning(f"无法获取音频时长: {e}")
        
        # 计算每个句子的时长权重（基于字符数）
        char_counts = [len(s) for s in sentences]
        total_chars = sum(char_counts)
        
        if total_chars == 0:
            logger.error("总字符数为0")
            return str(subtitle_path)
        
        # 如果有实际音频时长，按比例分配；否则使用估算
        if actual_audio_duration > 0:
            # 基于实际时长分配
            durations = [(count / total_chars) * actual_audio_duration for count in char_counts]
        else:
            # 估算时长（字符数 * 0.15秒，更接近实际朗读速度）
            durations = [max(2, min(8, count * 0.15)) for count in char_counts]
        
        # 生成SRT格式字幕
        srt_content = ""
        start_time = 0
        
        for i, (sentence, duration) in enumerate(zip(sentences, durations)):
            if not sentence:
                continue
            
            end_time = start_time + duration
            
            # 格式化时间
            start_str = self.seconds_to_srt_time(start_time)
            end_str = self.seconds_to_srt_time(end_time)
            
            srt_content += f"{i + 1}\n"
            srt_content += f"{start_str} --> {end_str}\n"
            srt_content += f"{sentence}\n\n"
            
            start_time = end_time + 0.3  # 间隔0.3秒
        
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        logger.info(f"字幕文件已生成: {subtitle_path}, 共{len(sentences)}条字幕")
        return str(subtitle_path)

    def seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

    def generate_tts_audio(self, script_content: str) -> str:
        """生成TTS语音"""
        pdf_name = Path(self.pdf_path).stem
        audio_filename = f"{pdf_name}_语音.wav"
        audio_path = Path(WORK_PATH) / audio_filename
        
        # 获取用户选择的语音
        selected_voice = self.config.get('tts_voice', 'System Default')
        
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            # 设置语音参数
            voices = engine.getProperty('voices')
            voice_selected = False
            
            if voices:
                # 根据用户选择设置语音
                if sys.platform == "darwin":
                    # Mac系统语音映射
                    voice_map = {
                        # Chinese voices
                        "Tingting (Chinese Female, Clear) ⭐ Recommended": "tingting",
                        "Sinji (Chinese Female, Natural)": "sinji",
                        "Meijia (Chinese Female, Taiwan)": "meijia",
                        # English voices
                        "Samantha (US Female, Natural) ⭐ Recommended": "samantha",
                        "Daniel (UK Male, Professional)": "daniel",
                        "Karen (AU Female, Clear)": "karen",
                        "Fred (US Male, Steady)": "fred",
                        "Moira (Irish Female)": "moira",
                        "Rishi (Indian English Male)": "rishi",
                        "Tessa (South African Female)": "tessa",
                    }

                    # Ignore section headers or default
                    target_voice = (
                        ""
                        if (not selected_voice or selected_voice.startswith("---") or selected_voice == "System Default")
                        else voice_map.get(selected_voice, "").lower()
                    )
                    
                    if target_voice:
                        # 查找指定语音
                        for voice in voices:
                            if target_voice in voice.id.lower():
                                engine.setProperty('voice', voice.id)
                                logger.info(f"使用用户选择的语音: {voice.id}")
                                voice_selected = True
                                break
                    
                    if not voice_selected:
                        # 降级：查找任何中文语音
                        for voice in voices:
                            if any(lang in voice.id.lower() for lang in ['zh', 'chinese', 'tingting', 'sinji', 'meijia']):
                                engine.setProperty('voice', voice.id)
                                logger.info(f"使用Mac中文语音: {voice.id}")
                                voice_selected = True
                                break
                    
                    if not voice_selected:
                        # 再降级：查找英文语音
                        for voice in voices:
                            if any(name in voice.id.lower() for name in ['samantha', 'daniel', 'karen']):
                                engine.setProperty('voice', voice.id)
                                logger.info(f"使用Mac英文语音: {voice.id}")
                                voice_selected = True
                                break
                    
                    if not voice_selected and voices:
                        # 最后降级：使用第一个可用语音
                        engine.setProperty('voice', voices[0].id)
                        logger.info(f"使用Mac默认语音: {voices[0].id}")
                
                elif sys.platform == "win32":
                    # Windows系统语音选择
                    for voice in voices:
                        if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                            engine.setProperty('voice', voice.id)
                            logger.info(f"使用Windows中文语音: {voice.id}")
                            break
            
            # 设置语速和音量（调整为更清晰）
            engine.setProperty('rate', 160)  # 提高语速，更清晰
            engine.setProperty('volume', 1.0)  # 最大音量
            
            # 保存音频
            engine.save_to_file(script_content, str(audio_path))
            engine.runAndWait()
            
            logger.info(f"TTS音频已生成: {audio_path}")
                
        except ImportError:
            logger.error("缺少pyttsx3库，请运行: pip install pyttsx3")
            return ""
        except Exception as e:
            logger.error(f"TTS生成失败: {e}")
            # 在Mac上，如果TTS失败，可以尝试使用系统say命令作为备选
            if sys.platform == "darwin":
                try:
                    import subprocess
                    # 使用Mac的say命令生成音频
                    subprocess.run([
                        'say', '-o', str(audio_path), '-f', 'aiff', script_content
                    ], check=True)
                    
                    # 转换aiff到wav
                    wav_path = audio_path.with_suffix('.wav')
                    subprocess.run([
                        'afconvert', str(audio_path), str(wav_path), '-f', 'WAVE'
                    ], check=True)
                    
                    # 删除临时aiff文件
                    if audio_path.exists():
                        audio_path.unlink()
                    
                    audio_path = wav_path
                    logger.info(f"使用Mac say命令生成音频: {audio_path}")
                    
                except Exception as say_error:
                    logger.error(f"Mac say命令也失败了: {say_error}")
                    return ""
            else:
                return ""
        
        return str(audio_path) if audio_path.exists() else ""

    def stop(self):
        """停止处理"""
        self.is_running = False
        self.terminate()
