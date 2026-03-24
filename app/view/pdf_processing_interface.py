# -*- coding: utf-8 -*-
import os
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QGroupBox,
    QProgressBar,
    QScrollArea,
)
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ToolButton,
    ComboBox,
    CheckBox,
    TextEdit,
)

from app.common.config import cfg
from app.config import ASSETS_PATH
from app.core.entities import SupportedDocumentFormats
from app.thread.pdf_processing_thread import PDFProcessingThread

LOGO_PATH = ASSETS_PATH / "logo.jpg"


class PDFProcessingInterface(QWidget):
    """
    PDF processing interface class for PDF to speech script conversion.
    """

    finished = pyqtSignal(str, str, str)  # Signal: script_path, subtitle_path, audio_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_processing_thread = None

        self.setObjectName("PDFProcessingInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)

        self.setup_ui()
        self.setup_signals()
        self.update_api_status()

    def setup_ui(self):
        """Setup UI interface"""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create scroll content widget
        scroll_content = QWidget()
        self.main_layout = QVBoxLayout(scroll_content)
        self.main_layout.setSpacing(12)  # Reduce spacing
        self.main_layout.setContentsMargins(15, 10, 15, 10)  # Reduce margins

        # Title
        self.title_label = BodyLabel("PDF Intelligent Script Generation", self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2;")  # Further reduce font size
        self.main_layout.addWidget(self.title_label)

        # PDF input area
        self.setup_pdf_input_section()
        
        # AI model configuration area
        self.setup_ai_config_section()
        
        # Generation options area
        self.setup_generation_options_section()
        
        # Preview area
        self.setup_preview_section()
        
        # Control buttons area
        self.setup_control_buttons_section()
        
        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)

        self.main_layout.addStretch()
        
        # Setup scroll area
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def setup_pdf_input_section(self):
        """设置PDF input area"""
        pdf_group = QGroupBox("PDF File Input", self)
        pdf_layout = QVBoxLayout(pdf_group)

        # File selection row
        file_layout = QHBoxLayout()
        self.pdf_path_input = LineEdit(self)
        self.pdf_path_input.setPlaceholderText("Select PDF file or drag file here")
        self.pdf_path_input.setFixedHeight(35)
        
        self.browse_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_button.setFixedSize(35, 35)
        
        file_layout.addWidget(self.pdf_path_input)
        file_layout.addWidget(self.browse_button)
        
        pdf_layout.addLayout(file_layout)
        self.main_layout.addWidget(pdf_group)

    def setup_ai_config_section(self):
        """Setup AI configuration area"""
        ai_group = QGroupBox("AI Model Configuration", self)
        ai_layout = QVBoxLayout(ai_group)

        # AI service selection
        service_layout = QHBoxLayout()
        service_layout.addWidget(BodyLabel("AI Service:", self))
        self.ai_service_combo = ComboBox(self)
        self.ai_service_combo.addItems(["OpenAI GPT", "Google Gemini", "Claude"])
        self.ai_service_combo.setCurrentText("OpenAI GPT")
        service_layout.addWidget(self.ai_service_combo)
        service_layout.addStretch()
        
        ai_layout.addLayout(service_layout)
        
        # API configuration tips and quick setup
        api_tip_layout = QHBoxLayout()
        api_tip = BodyLabel("💡 Tip: Need to configure API key to use AI generation features", self)
        api_tip.setStyleSheet("color: #888888; font-size: 12px;")
        
        # Quick API key configuration
        self.api_key_input = LineEdit(self)
        self.api_key_input.setPlaceholderText("Enter OpenAI API key here (sk-...)")
        self.api_key_input.setFixedHeight(30)
        self.api_key_input.setEchoMode(self.api_key_input.Password)  # Hide key display
        
        self.save_api_button = PushButton("Save Key", self)
        self.save_api_button.setFixedHeight(30)
        self.save_api_button.clicked.connect(self.save_api_key)
        
        api_tip_layout.addWidget(api_tip)
        api_tip_layout.addStretch()
        ai_layout.addLayout(api_tip_layout)
        
        # API key input row
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(BodyLabel("API Key:", self))
        api_key_layout.addWidget(self.api_key_input)
        api_key_layout.addWidget(self.save_api_button)
        ai_layout.addLayout(api_key_layout)

        # Prompt settings
        ai_layout.addWidget(BodyLabel("Custom Prompt (Optional):", self))
        self.prompt_input = TextEdit(self)
        self.prompt_input.setPlainText(
            "Based on the provided PDF content, create a high-quality, engaging speech script. Requirements:\n"
            "1. Clear structure: Attention-grabbing opening, logically clear main content, memorable ending\n"
            "2. Language style: Conversational expression, varied sentence length, appropriate use of rhetoric\n"
            "3. Content handling: Explain complex concepts in plain language, vividly describe chart data, add specific examples\n"
            "4. Reading optimization: Only output the speech script itself, do not add any information unrelated to reading, do not use bold, italic, asterisks or other formatting marks\n"
            "5. Image description: If there are images, use vivid language to describe the image content in detail, so that the audience can 'see' the picture\n"
            "6. Word count control: 800-1500 words, ensure rich content suitable for oral expression"
        )
        self.prompt_input.setFixedHeight(80)  # Reduce height
        ai_layout.addWidget(self.prompt_input)

        self.main_layout.addWidget(ai_group)

    def setup_generation_options_section(self):
        """设置Generation options area"""
        options_group = QGroupBox("Generation Options", self)
        options_layout = QVBoxLayout(options_group)

        # Generation content selection
        self.generate_script_cb = CheckBox("Generate Script (TXT)", self)
        self.generate_script_cb.setChecked(True)
        
        self.generate_audio_cb = CheckBox("Generate TTS Voice (WAV)", self)
        self.generate_audio_cb.setChecked(True)
        
        self.generate_subtitle_cb = CheckBox("Generate Subtitle File (SRT) - Need to generate TTS first", self)
        self.generate_subtitle_cb.setChecked(False)  # Unchecked by default
        
        # Add tip
        subtitle_tip = BodyLabel("💡 Tip: Recommend generating TXT and TTS first, can manually add subtitles or use other subtitle modules later", self)
        subtitle_tip.setStyleSheet("color: #ff9800; font-size: 11px;")
        options_layout.addWidget(subtitle_tip)

        options_layout.addWidget(self.generate_script_cb)
        options_layout.addWidget(self.generate_audio_cb)
        options_layout.addWidget(self.generate_subtitle_cb)

        # TTS options
        tts_layout = QHBoxLayout()
        tts_layout.addWidget(BodyLabel("TTS Voice:", self))
        self.tts_voice_combo = ComboBox(self)
        
        # High-quality TTS voice options
        self.tts_voice_combo.addItems([
            "--- Chinese Voices ---",
            "Tingting (Chinese Female, Clear) ⭐ Recommended",
            "Sinji (Chinese Female, Natural)",
            "Meijia (Chinese Female, Taiwan)",
            "--- English Voices ---",
            "Samantha (US Female, Natural) ⭐ Recommended",
            "Daniel (UK Male, Professional)",
            "Karen (AU Female, Clear)",
            "Fred (US Male, Steady)",
            "Moira (Irish Female)",
            "Rishi (Indian English Male)",
            "Tessa (South African Female)",
            "--- Other ---",
            "System Default"
        ])
        tts_layout.addWidget(self.tts_voice_combo)
        
        # Preview voice button
        self.preview_tts_button = PushButton("Preview Voice", self)
        self.preview_tts_button.clicked.connect(self.on_preview_tts)
        tts_layout.addWidget(self.preview_tts_button)
        tts_layout.addStretch()
        
        options_layout.addLayout(tts_layout)
        self.main_layout.addWidget(options_group)

    class TTSPreviewThread(QThread):
        finished = pyqtSignal()
        error = pyqtSignal(str)

        def __init__(self, selected_voice: str, parent=None):
            super().__init__(parent)
            self.selected_voice = selected_voice

        def run(self):
            try:
                import sys
                import pyttsx3

                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                voice_selected = False

                # Map UI labels to system voice ids (macOS)
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

                selected_voice = self.selected_voice or "System Default"
                target_voice = (
                    ""
                    if (selected_voice.startswith("---") or selected_voice == "System Default")
                    else voice_map.get(selected_voice, "").lower()
                )

                if voices:
                    if sys.platform == "darwin":
                        if target_voice:
                            for v in voices:
                                if target_voice in v.id.lower():
                                    engine.setProperty('voice', v.id)
                                    voice_selected = True
                                    break
                        if not voice_selected:
                            for v in voices:
                                if any(x in v.id.lower() for x in ['zh', 'chinese', 'tingting', 'sinji', 'meijia']):
                                    engine.setProperty('voice', v.id)
                                    voice_selected = True
                                    break
                        if not voice_selected:
                            for v in voices:
                                if any(x in v.id.lower() for x in ['samantha', 'daniel', 'karen']):
                                    engine.setProperty('voice', v.id)
                                    voice_selected = True
                                    break
                        if not voice_selected:
                            engine.setProperty('voice', voices[0].id)
                    elif sys.platform == "win32":
                        for v in voices:
                            if 'chinese' in v.name.lower() or 'zh' in v.id.lower():
                                engine.setProperty('voice', v.id)
                                break

                engine.setProperty('rate', 160)
                engine.setProperty('volume', 1.0)
                engine.say("This is a voice preview.")
                engine.runAndWait()
                self.finished.emit()
            except Exception as e:
                self.error.emit(str(e))

    def on_preview_tts(self):
        try:
            voice_label = self.tts_voice_combo.currentText()
            self.preview_tts_button.setEnabled(False)
            InfoBar.info("Preview", "Playing voice preview...", duration=1500, parent=self)
            
            self._tts_preview_thread = self.TTSPreviewThread(voice_label, self)
            self._tts_preview_thread.finished.connect(lambda: self.preview_tts_button.setEnabled(True))
            self._tts_preview_thread.error.connect(lambda msg: (self.preview_tts_button.setEnabled(True), InfoBar.error("TTS Error", msg, duration=3000, parent=self)))
            self._tts_preview_thread.start()
        except Exception as e:
            self.preview_tts_button.setEnabled(True)
            InfoBar.error("TTS Error", str(e), duration=3000, parent=self)

    def setup_preview_section(self):
        """设置Preview area"""
        preview_group = QGroupBox("Generation Preview", self)
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit(self)
        self.preview_text.setPlaceholderText("Generated script will be displayed here...")
        self.preview_text.setFixedHeight(120)  # 减小Preview area高度
        self.preview_text.setReadOnly(True)
        
        preview_layout.addWidget(self.preview_text)
        self.main_layout.addWidget(preview_group)

    def setup_control_buttons_section(self):
        """设置Control buttons area"""
        button_layout = QHBoxLayout()
        
        self.generate_button = PrimaryPushButton("Start Generation", self)
        self.generate_button.setFixedHeight(35)  # Reduce button height
        
        self.save_button = PushButton("Save Result", self)
        self.save_button.setFixedHeight(35)  # Reduce button height
        self.save_button.setEnabled(False)
        
        self.open_folder_button = PushButton("Open Folder", self)
        self.open_folder_button.setFixedHeight(35)
        self.open_folder_button.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.open_folder_button)
        button_layout.addStretch()
        
        self.main_layout.addLayout(button_layout)

    def setup_signals(self):
        """Setup signal connections"""
        self.browse_button.clicked.connect(self.on_browse_pdf)
        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.save_button.clicked.connect(self.on_save_clicked)
        self.open_folder_button.clicked.connect(self.on_open_folder_clicked)

    def save_api_key(self):
        """Save API key"""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            InfoBar.warning(
                "Warning",
                "Please enter API key",
                duration=3000,
                parent=self,
            )
            return
        
        if not api_key.startswith('sk-'):
            InfoBar.warning(
                "Warning", 
                "OpenAI API key should start with 'sk-'",
                duration=3000,
                parent=self,
            )
            return
        
        try:
            # Save to configuration
            cfg.set(cfg.openai_api_key, api_key)
            
            # Verify save successful
            saved_key = cfg.get(cfg.openai_api_key)
            if saved_key == api_key:
                InfoBar.success(
                    "Success",
                    "API key saved! You can now use AI generation features",
                    duration=3000,
                    parent=self,
                )
                
                # Clear input box
                self.api_key_input.clear()
                
                # Update API status display
                self.update_api_status()
            else:
                raise Exception("Configuration save verification failed")
            
        except Exception as e:
            InfoBar.error(
                "Error",
                f"Failed to save API key: {str(e)}",
                duration=3000,
                parent=self,
            )

    def update_api_status(self):
        """Update API key status display"""
        try:
            api_key = cfg.get(cfg.openai_api_key)
            if api_key and api_key.strip():
                # Display partial key (only show first and last few characters)
                masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "Configured"
                self.api_key_input.setPlaceholderText(f"Current key: {masked_key}")
                self.save_api_button.setText("Update Key")
            else:
                self.api_key_input.setPlaceholderText("Enter OpenAI API key here (sk-...)")
                self.save_api_button.setText("Save Key")
        except Exception as e:
            print(f"API status update error: {e}")  # For debugging
            self.api_key_input.setPlaceholderText("Enter OpenAI API key here (sk-...)")
            self.save_api_button.setText("Save Key")

    def on_browse_pdf(self):
        """Browse PDF file"""
        file_dialog = QFileDialog()
        pdf_filter = f"PDF Files (*.pdf)"
        
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select PDF File", "", pdf_filter
        )
        
        if file_path:
            self.pdf_path_input.setText(file_path)

    def on_generate_clicked(self):
        """Start Generation处理"""
        pdf_path = self.pdf_path_input.text().strip()
        
        if not pdf_path:
            InfoBar.error(
                "Error",
                "Please select PDF file first",
                duration=3000,
                parent=self,
            )
            return
            
        if not os.path.exists(pdf_path):
            InfoBar.error(
                "Error",
                "PDF file does not exist",
                duration=3000,
                parent=self,
            )
            return

        # 检查文件格式
        if not pdf_path.lower().endswith('.pdf'):
            InfoBar.error(
                "Error",
                "Please select PDF format file",
                duration=3000,
                parent=self,
            )
            return

        # Start Processing
        self.start_processing(pdf_path)

    def start_processing(self, pdf_path):
        """StartPDF处理"""
        self.generate_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)

        # 获取配置
        config = {
            'ai_service': self.ai_service_combo.currentText(),
            'custom_prompt': self.prompt_input.toPlainText(),
            'generate_script': self.generate_script_cb.isChecked(),
            'generate_subtitle': self.generate_subtitle_cb.isChecked(),
            'generate_audio': self.generate_audio_cb.isChecked(),
            'tts_voice': self.tts_voice_combo.currentText(),
        }

        # 创建处理线程
        self.pdf_processing_thread = PDFProcessingThread(pdf_path, config)
        self.pdf_processing_thread.progress.connect(self.on_progress_updated)
        self.pdf_processing_thread.preview_ready.connect(self.on_preview_ready)
        self.pdf_processing_thread.finished.connect(self.on_processing_finished)
        self.pdf_processing_thread.error.connect(self.on_processing_error)
        self.pdf_processing_thread.start()

        InfoBar.info(
            "Start Processing",
            "Processing PDF file, please wait...",
            duration=3000,
            parent=self,
        )

    def on_progress_updated(self, value, status):
        """更新Progress"""
        self.progress_bar.setValue(value)

    def on_preview_ready(self, script_content):
        """显示预览"""
        self.preview_text.setPlainText(script_content)

    def on_processing_finished(self, script_path, subtitle_path, audio_path):
        """Processing completed"""
        self.generate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.progress_bar.hide()
        
        # 保存文件路径供后续使用
        self.generated_files = {
            'script': script_path,
            'subtitle': subtitle_path,
            'audio': audio_path
        }

        # 显示更详细的完成信息
        files_info = []
        if script_path:
            files_info.append(f"Script: {os.path.basename(script_path)}")
        if subtitle_path:
            files_info.append(f"Subtitle: {os.path.basename(subtitle_path)}")
        if audio_path:
            files_info.append(f"Audio: {os.path.basename(audio_path)}")
        
        files_text = "\n".join(files_info) if files_info else "No files generated"
        
        InfoBar.success(
                "Processing completed",
            f"PDF processing completed！Generated files：\n{files_text}",
            duration=5000,
            parent=self,
        )

        # 发送完成信号
        self.finished.emit(script_path, subtitle_path, audio_path)

    def on_processing_error(self, error_msg):
        """处理Error"""
        self.generate_button.setEnabled(True)
        self.progress_bar.hide()

        InfoBar.error(
            "Processing failed",
                f"Error occurred during processing: {error_msg}",
            duration=5000,
            parent=self,
        )

    def on_save_clicked(self):
        """Save Result到指定位置"""
        if not hasattr(self, 'generated_files'):
            InfoBar.warning(
                "Tip",
                "Please generate content before saving",
                duration=3000,
                parent=self,
            )
            return
        
        folder = QFileDialog.getExistingDirectory(self, "Select save location")
        if not folder:
            return
            
        try:
            import shutil
            copied_files = []
            
            # 复制所有生成的文件到选择的文件夹
            for file_type, file_path in self.generated_files.items():
                if file_path and os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    dest_path = os.path.join(folder, filename)
                    shutil.copy2(file_path, dest_path)
                    copied_files.append(filename)
            
            if copied_files:
                files_list = "\n".join(copied_files)
                InfoBar.success(
                    "Save successful",
                    f"Following files saved to：{folder}\n\n{files_list}",
                    duration=5000,
                    parent=self,
                )
                
                # 可选：Open Folder
                import subprocess
                subprocess.run(['open', folder])
                
            else:
                InfoBar.warning(
                    "Warning",
                    "No files found to save",
                    duration=3000,
                    parent=self,
                )
                
        except Exception as e:
            InfoBar.error(
                "Error",
                f"Error saving files:{str(e)}",
                duration=3000,
                parent=self,
            )

    def on_open_folder_clicked(self):
        """打开Generated files所在的文件夹"""
        try:
            from app.config import WORK_PATH
            import subprocess
            
            if os.path.exists(WORK_PATH):
                # 在Mac上Open Folder
                subprocess.run(['open', str(WORK_PATH)])
                InfoBar.info(
                    "Folder opened",
                    f"Opened work directory:{WORK_PATH}",
                    duration=3000,
                    parent=self,
                )
            else:
                InfoBar.warning(
                    "Warning",
                    "Work directory does not exist",
                    duration=3000,
                    parent=self,
                )
        except Exception as e:
            InfoBar.error(
                "Error",
                f"Failed to open folder: {str(e)}",
                duration=3000,
                parent=self,
            )

    def dragEnterEvent(self, event):
        """Drag enter event"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Drop event"""
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if not os.path.isfile(file_path):
                continue

            if file_path.lower().endswith('.pdf'):
                self.pdf_path_input.setText(file_path)
                InfoBar.success(
                "Import Successful",
                "PDF file imported successfully",
                    duration=1500,
                    parent=self,
                )
                break
            else:
                InfoBar.error(
                    "Format Error",
                    "Please select PDF format file",
                    duration=3000,
                    parent=self,
                )


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication([])
    window = PDFProcessingInterface()
    window.show()
    app.exec_()
