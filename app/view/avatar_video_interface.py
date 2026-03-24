# -*- coding: utf-8 -*-
"""
2D人物讲解视频生成界面 - SadTalker版本
"""

import os
import subprocess
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
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
    LineEdit,
    PrimaryPushButton,
    PushButton,
    ToolButton,
    ComboBox,
    CheckBox,
)

from app.thread.avatar_video_thread_sadtalker import AvatarVideoThreadSadTalker
from app.core.avatar_video.avatar_video_generator_sadtalker import AvatarVideoGeneratorSadTalker
from app.thread.video_merge_thread import VideoMergeThread


class AvatarVideoInterface(QWidget):
    """2D人物讲解视频生成界面 - SadTalker版本"""
    
    finished = pyqtSignal(str)  # Signal: video_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.avatar_video_thread = None
        self.merge_thread = None
        self.generator = AvatarVideoGeneratorSadTalker()
        self.generated_video_path = None
        
        self.setObjectName("AvatarVideoInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        
        self.setup_ui()
        self.setup_signals()
        self.check_sadtalker_installation()
    
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容组件
        scroll_content = QWidget()
        self.main_layout = QVBoxLayout(scroll_content)
        self.main_layout.setSpacing(12)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        
        # 标题
        self.title_label = BodyLabel("2D Avatar Video Generator (SadTalker)", self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2;")
        self.main_layout.addWidget(self.title_label)
        
        # 输入文件区域
        self.setup_input_section()
        
        # SadTalker配置区域
        self.setup_sadtalker_config_section()
        
        # 视频设置区域
        self.setup_video_settings_section()
        
        # 视频合并区域
        self.setup_video_merge_section()
        
        # 预览区域
        self.setup_preview_section()
        
        # 控制按钮区域
        self.setup_control_buttons_section()
        
        # 进度条
        self.progress_bar = QProgressBar(self)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)
        
        self.main_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
    
    def setup_input_section(self):
        """设置输入文件区域"""
        input_group = QGroupBox("Input Files", self)
        input_layout = QVBoxLayout(input_group)
        
        # 人物照片选择
        avatar_layout = QHBoxLayout()
        avatar_layout.addWidget(BodyLabel("Avatar Image:", self))
        self.avatar_image_input = LineEdit(self)
        self.avatar_image_input.setPlaceholderText("Select avatar photo (JPG/PNG)")
        self.avatar_image_input.setFixedHeight(35)
        self.browse_avatar_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_avatar_button.setFixedSize(35, 35)
        avatar_layout.addWidget(self.avatar_image_input)
        avatar_layout.addWidget(self.browse_avatar_button)
        input_layout.addLayout(avatar_layout)
        
        # 语音文件选择
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(BodyLabel("Audio (WAV/MP3/MP4):", self))
        self.audio_input = LineEdit(self)
        self.audio_input.setPlaceholderText("Select audio file or video file (audio will be extracted)")
        self.audio_input.setFixedHeight(35)
        self.browse_audio_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_audio_button.setFixedSize(35, 35)
        audio_layout.addWidget(self.audio_input)
        audio_layout.addWidget(self.browse_audio_button)
        input_layout.addLayout(audio_layout)
        
        self.main_layout.addWidget(input_group)
    
    def setup_sadtalker_config_section(self):
        """设置SadTalker配置区域"""
        sadtalker_group = QGroupBox("SadTalker Configuration", self)
        sadtalker_layout = QVBoxLayout(sadtalker_group)
        
        # 提示
        tip = BodyLabel(
            "💡 SadTalker is an open-source tool that runs locally. "
            "First-time use requires installation (about 2GB models).",
            self
        )
        tip.setStyleSheet("color: #888888; font-size: 12px;")
        tip.setWordWrap(True)
        sadtalker_layout.addWidget(tip)
        
        # 安装状态显示
        self.installation_status_label = BodyLabel("Checking installation...", self)
        self.installation_status_label.setStyleSheet("font-size: 12px;")
        sadtalker_layout.addWidget(self.installation_status_label)
        
        # 安装按钮
        install_layout = QHBoxLayout()
        self.install_sadtalker_button = PushButton("Install SadTalker", self)
        self.install_sadtalker_button.setFixedHeight(35)
        self.check_installation_button = PushButton("Check Installation", self)
        self.check_installation_button.setFixedHeight(35)
        install_layout.addWidget(self.install_sadtalker_button)
        install_layout.addWidget(self.check_installation_button)
        install_layout.addStretch()
        sadtalker_layout.addLayout(install_layout)
        
        self.main_layout.addWidget(sadtalker_group)
    
    def setup_video_settings_section(self):
        """设置视频设置区域"""
        settings_group = QGroupBox("Video Settings", self)
        settings_layout = QVBoxLayout(settings_group)
        
        # 预处理方式
        preprocess_layout = QHBoxLayout()
        preprocess_layout.addWidget(BodyLabel("Preprocess:", self))
        self.preprocess_combo = ComboBox(self)
        self.preprocess_combo.addItems([
            "crop (推荐 - 裁剪人脸)",
            "resize (调整大小)",
            "full (完整画面)"
        ])
        preprocess_layout.addWidget(self.preprocess_combo)
        preprocess_layout.addStretch()
        settings_layout.addLayout(preprocess_layout)
        
        # 功能选项
        self.still_mode_cb = CheckBox("Still Mode (静态模式 - 只有嘴动，头不动)", self)
        self.still_mode_cb.setChecked(False)
        settings_layout.addWidget(self.still_mode_cb)
        
        # 增强器选择
        enhancer_layout = QHBoxLayout()
        enhancer_layout.addWidget(BodyLabel("Enhancer:", self))
        self.enhancer_combo = ComboBox(self)
        self.enhancer_combo.addItems([
            "None (无增强)",
            "gfpgan (面部增强)",
            "RestoreFormer (面部修复)"
        ])
        enhancer_layout.addWidget(self.enhancer_combo)
        enhancer_layout.addStretch()
        settings_layout.addLayout(enhancer_layout)
        
        # 提示信息
        info_label = BodyLabel(
            "ℹ️ Note: SadTalker runs locally. First generation will download models (~2GB). "
            "Supports audio of any length.",
            self
        )
        info_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        info_label.setWordWrap(True)
        settings_layout.addWidget(info_label)
        
        self.main_layout.addWidget(settings_group)
    
    def setup_video_merge_section(self):
        """设置视频合并区域"""
        merge_group = QGroupBox("Video Merge (Optional)", self)
        merge_layout = QVBoxLayout(merge_group)
        
        # 提示信息
        tip = BodyLabel(
            "💡 Merge avatar video with an Intelligent Video to add a teacher in the top-left corner (small size to minimize impact).",
            self
        )
        tip.setStyleSheet("color: #888888; font-size: 11px;")
        tip.setWordWrap(True)
        merge_layout.addWidget(tip)
        
        # 人脸视频选择（可以选择生成的或上传的）
        avatar_video_layout = QHBoxLayout()
        avatar_video_layout.addWidget(BodyLabel("Avatar Video:", self))
        self.avatar_video_input = LineEdit(self)
        self.avatar_video_input.setPlaceholderText("Use generated video or upload existing avatar video")
        self.avatar_video_input.setFixedHeight(35)
        self.browse_avatar_video_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_avatar_video_button.setFixedSize(35, 35)
        avatar_video_layout.addWidget(self.avatar_video_input)
        avatar_video_layout.addWidget(self.browse_avatar_video_button)
        merge_layout.addLayout(avatar_video_layout)
        
        # 主视频选择
        main_video_layout = QHBoxLayout()
        main_video_layout.addWidget(BodyLabel("Main Video (Intelligent Video):", self))
        self.main_video_input = LineEdit(self)
        self.main_video_input.setPlaceholderText("Select Intelligent Video to merge with")
        self.main_video_input.setFixedHeight(35)
        self.browse_main_video_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_main_video_button.setFixedSize(35, 35)
        main_video_layout.addWidget(self.main_video_input)
        main_video_layout.addWidget(self.browse_main_video_button)
        merge_layout.addLayout(main_video_layout)
        
        # 合并按钮
        self.merge_button = PushButton("Merge Videos", self)
        self.merge_button.setFixedHeight(35)
        self.merge_button.setEnabled(False)
        merge_layout.addWidget(self.merge_button)
        
        self.main_layout.addWidget(merge_group)
    
    def setup_preview_section(self):
        """设置预览区域"""
        preview_group = QGroupBox("Status Preview", self)
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit(self)
        self.preview_text.setPlaceholderText("Generation status will be displayed here...")
        self.preview_text.setFixedHeight(120)
        self.preview_text.setReadOnly(True)
        
        preview_layout.addWidget(self.preview_text)
        self.main_layout.addWidget(preview_group)
    
    def setup_control_buttons_section(self):
        """设置控制按钮区域"""
        button_layout = QHBoxLayout()
        
        self.generate_button = PrimaryPushButton("Generate Avatar Video", self)
        self.generate_button.setFixedHeight(35)
        
        self.open_folder_button = PushButton("Open Output Folder", self)
        self.open_folder_button.setFixedHeight(35)
        self.open_folder_button.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.open_folder_button)
        button_layout.addStretch()
        
        self.main_layout.addLayout(button_layout)
    
    def setup_signals(self):
        """设置信号连接"""
        self.browse_avatar_button.clicked.connect(self.on_browse_avatar)
        self.browse_audio_button.clicked.connect(self.on_browse_audio)
        self.browse_avatar_video_button.clicked.connect(self.on_browse_avatar_video)
        self.browse_main_video_button.clicked.connect(self.on_browse_main_video)
        self.install_sadtalker_button.clicked.connect(self.on_install_sadtalker)
        self.check_installation_button.clicked.connect(self.check_sadtalker_installation)
        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.open_folder_button.clicked.connect(self.on_open_folder_clicked)
        self.merge_button.clicked.connect(self.on_merge_clicked)
        # 监听输入变化，启用/禁用合并按钮
        self.avatar_video_input.textChanged.connect(self.on_merge_inputs_changed)
        self.main_video_input.textChanged.connect(self.on_merge_inputs_changed)
    
    def check_sadtalker_installation(self):
        """检查SadTalker安装状态"""
        if self.generator.check_installation():
            self.installation_status_label.setText("✅ SadTalker installed")
            self.installation_status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
            self.generate_button.setEnabled(True)
        else:
            path = self.generator.get_installation_path()
            self.installation_status_label.setText(f"❌ SadTalker not found at: {path}")
            self.installation_status_label.setStyleSheet("color: #f44336; font-size: 12px;")
            self.generate_button.setEnabled(False)
    
    def on_install_sadtalker(self):
        """安装SadTalker"""
        try:
            install_script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'install_sadtalker.sh'
            )
            
            if not os.path.exists(install_script):
                InfoBar.error(
                    "Error",
                    f"Installation script not found at: {install_script}",
                    duration=5000,
                    parent=self
                )
                return
            
            InfoBar.info(
                "Installing",
                "Opening terminal to install SadTalker. This will take 10-30 minutes...",
                duration=5000,
                parent=self
            )
            
            # 在新终端窗口中运行安装脚本
            subprocess.Popen([
                'open', '-a', 'Terminal.app',
                install_script
            ])
            
        except Exception as e:
            InfoBar.error(
                "Error",
                f"Failed to start installation: {str(e)}",
                duration=5000,
                parent=self
            )
    
    def on_browse_avatar(self):
        """浏览人物照片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Avatar Image", "", "Image Files (*.jpg *.jpeg *.png)"
        )
        if file_path:
            self.avatar_image_input.setText(file_path)
    
    def on_browse_audio(self):
        """浏览音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "", "Audio/Video Files (*.wav *.mp3 *.mp4)"
        )
        if file_path:
            self.audio_input.setText(file_path)
    
    def on_browse_avatar_video(self):
        """浏览人脸视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Avatar Video", "", "Video Files (*.mp4 *.avi *.mov)"
        )
        if file_path:
            self.avatar_video_input.setText(file_path)
    
    def on_browse_main_video(self):
        """浏览主视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Main Video (Intelligent Video)", "", "Video Files (*.mp4 *.avi *.mov)"
        )
        if file_path:
            self.main_video_input.setText(file_path)
    
    def on_merge_inputs_changed(self):
        """合并输入变化时更新合并按钮状态"""
        # 检查人脸视频：优先使用上传的，如果没有则使用生成的
        avatar_video = self.avatar_video_input.text().strip()
        if not avatar_video or not os.path.exists(avatar_video):
            avatar_video = self.generated_video_path if self.generated_video_path and os.path.exists(self.generated_video_path) else None
        
        # 检查主视频
        main_video = self.main_video_input.text().strip()
        
        # 两个视频都存在才能合并
        self.merge_button.setEnabled(
            bool(avatar_video and os.path.exists(avatar_video) and 
                 main_video and os.path.exists(main_video))
        )
    
    def on_generate_clicked(self):
        """开始生成处理"""
        # 验证输入
        avatar_image = self.avatar_image_input.text().strip()
        audio_path = self.audio_input.text().strip()
        
        if not avatar_image or not os.path.exists(avatar_image):
            InfoBar.error("Error", "Please select a valid avatar image", duration=3000, parent=self)
            return
        
        if not audio_path or not os.path.exists(audio_path):
            InfoBar.error("Error", "Please select a valid audio file", duration=3000, parent=self)
            return
        
        # 检查SadTalker安装
        if not self.generator.check_installation():
            InfoBar.error(
                "Error",
                "SadTalker not installed. Please click 'Install SadTalker' button first.",
                duration=5000,
                parent=self
            )
            return
        
        # 开始处理
        self.start_processing(avatar_image, audio_path)
    
    def start_processing(self, avatar_image: str, audio_path: str):
        """开始视频生成处理"""
        self.generate_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.preview_text.clear()
        
        # 获取配置
        preprocess_text = self.preprocess_combo.currentText()
        preprocess = preprocess_text.split('(')[0].strip()  # 提取 'crop', 'resize', 'full'
        
        enhancer_text = self.enhancer_combo.currentText()
        enhancer = None if enhancer_text.startswith("None") else enhancer_text.split('(')[0].strip()
        
        config = {
            'avatar_image': avatar_image,
            'audio_path': audio_path,
            'preprocess': preprocess,
            'still': self.still_mode_cb.isChecked(),
            'enhancer': enhancer,
        }
        
        # 创建处理线程
        self.avatar_video_thread = AvatarVideoThreadSadTalker(config)
        self.avatar_video_thread.progress.connect(self.on_progress_updated)
        self.avatar_video_thread.status.connect(self.on_status_updated)
        self.avatar_video_thread.finished.connect(self.on_processing_finished)
        self.avatar_video_thread.error.connect(self.on_processing_error)
        self.avatar_video_thread.start()
        
        InfoBar.info("Start Processing", "Generating avatar video with SadTalker...", duration=3000, parent=self)
    
    def on_progress_updated(self, value: int):
        """更新进度"""
        self.progress_bar.setValue(value)
    
    def on_status_updated(self, message: str):
        """更新状态"""
        self.preview_text.append(message)
    
    def on_processing_finished(self, video_path: str):
        """处理完成"""
        self.generate_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.progress_bar.hide()
        
        self.generated_video_path = video_path
        
        # 如果用户没有手动上传人脸视频，自动填充生成的视频路径
        if not self.avatar_video_input.text().strip():
            self.avatar_video_input.setText(video_path)
        
        # 检查是否可以合并
        self.on_merge_inputs_changed()
        
        InfoBar.success(
            "Processing Completed",
            f"Avatar video generated successfully!\nSaved to: {os.path.basename(video_path)}",
            duration=5000,
            parent=self
        )
        
        self.finished.emit(video_path)
    
    def on_processing_error(self, error_msg: str):
        """处理错误"""
        self.generate_button.setEnabled(True)
        self.progress_bar.hide()
        
        InfoBar.error(
            "Processing Failed",
            f"Error occurred: {error_msg}",
            duration=5000,
            parent=self
        )
    
    def on_open_folder_clicked(self):
        """打开输出文件夹"""
        try:
            from app.config import WORK_PATH
            import subprocess
            
            if os.path.exists(WORK_PATH):
                subprocess.run(['open', str(WORK_PATH)])
                InfoBar.info("Folder Opened", f"Opened: {WORK_PATH}", duration=3000, parent=self)
            else:
                InfoBar.warning("Warning", "Output directory does not exist", duration=3000, parent=self)
        except Exception as e:
            InfoBar.error("Error", f"Failed to open folder: {str(e)}", duration=3000, parent=self)
    
    def on_merge_clicked(self):
        """合并视频"""
        main_video = self.main_video_input.text().strip()
        
        # 优先使用上传的人脸视频，如果没有则使用生成的
        avatar_video = self.avatar_video_input.text().strip()
        if not avatar_video or not os.path.exists(avatar_video):
            avatar_video = self.generated_video_path
        
        if not main_video or not os.path.exists(main_video):
            InfoBar.error("Error", "Please select a valid main video", duration=3000, parent=self)
            return
        
        if not avatar_video or not os.path.exists(avatar_video):
            InfoBar.error("Error", "Avatar video not found. Please generate or upload one first.", duration=3000, parent=self)
            return
        
        # 开始合并
        self.merge_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.preview_text.clear()
        self.preview_text.append("Starting video merge...")
        
        # 创建合并线程
        self.merge_thread = VideoMergeThread(main_video, avatar_video)
        self.merge_thread.progress.connect(self.on_progress_updated)
        self.merge_thread.status.connect(self.on_status_updated)
        self.merge_thread.finished.connect(self.on_merge_finished)
        self.merge_thread.error.connect(self.on_merge_error)
        self.merge_thread.start()
        
        InfoBar.info("Merging", "Merging videos... This may take a few minutes.", duration=3000, parent=self)
    
    def on_merge_finished(self, merged_video_path: str):
        """合并完成"""
        self.merge_button.setEnabled(True)
        self.progress_bar.hide()
        
        InfoBar.success(
            "Merge Completed",
            f"Videos merged successfully!\nSaved to: {os.path.basename(merged_video_path)}",
            duration=5000,
            parent=self
        )
    
    def on_merge_error(self, error_msg: str):
        """合并错误"""
        self.merge_button.setEnabled(True)
        self.progress_bar.hide()
        
        InfoBar.error(
            "Merge Failed",
            f"Error occurred: {error_msg}",
            duration=5000,
            parent=self
        )
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """拖放事件"""
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if not os.path.isfile(file_path):
                continue
            
            ext = file_path.lower()
            if ext.endswith(('.jpg', '.jpeg', '.png')):
                self.avatar_image_input.setText(file_path)
                InfoBar.success("Import Success", "Avatar image imported", duration=1500, parent=self)
            elif ext.endswith(('.wav', '.mp3')):
                self.audio_input.setText(file_path)
                InfoBar.success("Import Success", "Audio imported", duration=1500, parent=self)
            elif ext.endswith('.mp4'):
                # MP4文件：优先检查是否已有主视频，如果没有则作为主视频
                # 如果主视频已设置，则作为人脸视频
                if self.main_video_input.text().strip():
                    # 主视频已设置，作为人脸视频
                    self.avatar_video_input.setText(file_path)
                    InfoBar.success("Import Success", "Avatar video imported", duration=1500, parent=self)
                else:
                    # 主视频未设置，作为音频（提取音频）
                    self.audio_input.setText(file_path)
                    InfoBar.success("Import Success", "Video imported (audio will be extracted)", duration=1500, parent=self)
