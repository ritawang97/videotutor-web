# -*- coding: utf-8 -*-
"""
Intelligent Video Generation Interface
"""

import os
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QProgressBar
)
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, PrimaryPushButton,
    ComboBox, CheckBox, InfoBar, InfoBarPosition, TextEdit, TitleLabel
)

from app.config import WORK_PATH
from app.thread.intelligent_video_thread import IntelligentVideoThread
from app.core.utils.logger import setup_logger

logger = setup_logger("IntelligentVideoInterface")


class IntelligentVideoInterface(QWidget):
    """Intelligent Video Generation Interface"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_thread = None
        self.scenes = []
        self.materials = {}
        
        self.setObjectName("IntelligentVideoInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        from app.common.ui_styles import COLORS
        title = TitleLabel("AI Intelligent Teaching Video Generation", self)
        title.setStyleSheet(f"""
            font-size: 28px; 
            font-weight: 700; 
            color: {COLORS['primary']};
            margin-bottom: 8px;
            background: transparent;
        """)
        layout.addWidget(title)
        
        # Description
        desc = BodyLabel(
            "Automatically generate complete teaching video from script: AI material search → Smart composition → Voiceover and subtitles",
            self
        )
        desc.setStyleSheet(f"""
            font-size: 13px; 
            color: {COLORS['text_secondary']};
            margin-bottom: 20px;
            background: transparent;
        """)
        layout.addWidget(desc)
        
        # Input area
        input_group = QGroupBox("Input Files (generate from PDF processing module first)", self)
        input_layout = QVBoxLayout(input_group)
        
        # Script (required)
        self.script_input = self._create_file_input("* Script File:", "Select .txt file")
        input_layout.addLayout(self.script_input[0])
        
        # TTS audio (required)
        self.tts_input = self._create_file_input("* TTS Audio:", "Select .wav file")
        input_layout.addLayout(self.tts_input[0])
        
        # Subtitle (optional)
        input_layout.addWidget(BodyLabel(""))  # Empty line
        optional_label = BodyLabel("Optional Input (video will have no subtitles if not provided):", self)
        optional_label.setStyleSheet("color: #888; font-size: 12px; font-style: italic;")
        input_layout.addWidget(optional_label)
        
        self.subtitle_input = self._create_file_input("  Subtitle File (optional):", "Select .srt file (optional)")
        input_layout.addLayout(self.subtitle_input[0])
        
        layout.addWidget(input_group)
        
        # Material search configuration
        search_group = QGroupBox("Material Search Configuration", self)
        search_layout = QVBoxLayout(search_group)
        
        search_tip = BodyLabel(
            "💡 Need to configure Pexels or Unsplash API key (configure in settings)",
            self
        )
        search_tip.setStyleSheet("color: #ff9800; font-size: 11px;")
        search_layout.addWidget(search_tip)
        
        material_layout = QHBoxLayout()
        material_layout.addWidget(BodyLabel("Material Type:"))
        self.material_type = ComboBox(self)
        self.material_type.addItems(["Prefer Video", "Prefer Images", "Mixed Use"])
        self.material_type.setCurrentIndex(0)
        material_layout.addWidget(self.material_type)

        # Results per scene
        material_layout.addWidget(BodyLabel("Results per scene:"))
        from qfluentwidgets import SpinBox
        self.results_per_scene = SpinBox(self)
        self.results_per_scene.setRange(1, 8)
        self.results_per_scene.setValue(3)
        material_layout.addWidget(self.results_per_scene)
        material_layout.addStretch()
        search_layout.addLayout(material_layout)
        
        layout.addWidget(search_group)
        
        # Video effects configuration
        effect_group = QGroupBox("Video Effects Configuration", self)
        effect_layout = QVBoxLayout(effect_group)
        
        self.add_transitions = CheckBox("Add Transitions (Fade in/out)", self)
        self.add_transitions.setChecked(True)
        effect_layout.addWidget(self.add_transitions)
        
        self.ken_burns = CheckBox("Ken Burns Effect for Images (Slow zoom)", self)
        self.ken_burns.setChecked(True)
        effect_layout.addWidget(self.ken_burns)
        
        self.auto_supplement = CheckBox("Auto Supplement Materials (Search more if video too short)", self)
        self.auto_supplement.setChecked(True)
        effect_layout.addWidget(self.auto_supplement)
        
        layout.addWidget(effect_group)
        
        # Scene preview area (shown after generation)
        preview_group = QGroupBox("Scene Preview (shown after generation)", self)
        preview_layout = QVBoxLayout(preview_group)
        
        self.scene_table = QTableWidget(self)
        self.scene_table.setColumnCount(4)
        self.scene_table.setHorizontalHeaderLabels([
            "Scene", "Keywords", "Duration(s)", "Status"
        ])
        self.scene_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.scene_table.setMaximumHeight(150)
        preview_layout.addWidget(self.scene_table)
        
        layout.addWidget(preview_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.generate_button = PrimaryPushButton("🚀 Start Generating Video", self)
        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.generate_button.setFixedHeight(40)
        button_layout.addWidget(self.generate_button)
        
        self.stop_button = PushButton("⏹ Stop", self)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedHeight(40)
        button_layout.addWidget(self.stop_button)
        
        self.open_folder_button = PushButton("📁 Open Output Folder", self)
        self.open_folder_button.clicked.connect(self.on_open_folder_clicked)
        self.open_folder_button.setFixedHeight(40)
        button_layout.addWidget(self.open_folder_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = BodyLabel("", self)
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def _create_file_input(self, label_text, placeholder):
        """Create file input component"""
        layout = QHBoxLayout()
        layout.addWidget(BodyLabel(label_text))
        
        line_edit = LineEdit(self)
        line_edit.setPlaceholderText(placeholder)
        layout.addWidget(line_edit)
        
        browse_btn = PushButton("Browse", self)
        browse_btn.clicked.connect(lambda: self._browse_file(line_edit))
        browse_btn.setFixedWidth(80)
        layout.addWidget(browse_btn)
        
        return (layout, line_edit, browse_btn)
    
    def _browse_file(self, line_edit):
        """Browse file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            str(WORK_PATH),
            "All Files (*.*)"
        )
        
        if file_path:
            line_edit.setText(file_path)
    
    def on_generate_clicked(self):
        """Start generation"""
        # Validate required inputs
        script_path = self.script_input[1].text().strip()
        tts_path = self.tts_input[1].text().strip()
        subtitle_path = self.subtitle_input[1].text().strip()
        
        # Only check TXT and TTS (required)
        if not all([script_path, tts_path]):
            InfoBar.error(
                "Error",
                "Please enter script and TTS audio file!",
                duration=3000,
                parent=self
            )
            return
        
        if not all([os.path.exists(script_path), os.path.exists(tts_path)]):
            InfoBar.error(
                "Error",
                "Script or TTS audio file does not exist, please check the path!",
                duration=3000,
                parent=self
            )
            return
        
        # Subtitle is optional
        if subtitle_path and not os.path.exists(subtitle_path):
            InfoBar.warning(
                "Warning",
                "Subtitle file does not exist, will generate video without subtitles",
                duration=3000,
                parent=self
            )
            subtitle_path = ""  # Clear invalid path
        
        # Create configuration
        config = {
            'add_transitions': self.add_transitions.isChecked(),
            'ken_burns': self.ken_burns.isChecked(),
            'auto_supplement_materials': self.auto_supplement.isChecked(),
            'material_type': self.material_type.currentText(),
            'materials_per_scene': int(self.results_per_scene.value()),
        }
        
        # Start generation thread
        self.video_thread = IntelligentVideoThread(
            script_path=Path(script_path),
            tts_audio_path=Path(tts_path),
            subtitle_path=Path(subtitle_path) if subtitle_path else None,
            config=config
        )
        
        self.video_thread.progress.connect(self.on_progress)
        self.video_thread.stage_finished.connect(self.on_stage_finished)
        self.video_thread.finished.connect(self.on_finished)
        self.video_thread.error.connect(self.on_error)
        
        self.video_thread.start()
        
        # Update UI status
        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting processing...")
        
        InfoBar.info(
            "Processing",
            "Generating intelligent video, please wait...",
            duration=2000,
            parent=self
        )
    
    def on_progress(self, value, message):
        """Update progress"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def on_stage_finished(self, stage_name, result):
        """Stage completed"""
        logger.info(f"Stage completed: {stage_name}")
        
        if stage_name == "Scene Analysis":
            self.scenes = result
            self._update_scene_table(result)
        elif stage_name == "Material Search":
            self.materials = result
    
    def _update_scene_table(self, scenes):
        """Update scene table"""
        self.scene_table.setRowCount(len(scenes))
        
        for i, scene in enumerate(scenes):
            self.scene_table.setItem(i, 0, QTableWidgetItem(f"Scene {scene.index}"))
            self.scene_table.setItem(i, 1, QTableWidgetItem(", ".join(scene.keywords[:3])))
            self.scene_table.setItem(i, 2, QTableWidgetItem(f"{scene.duration:.1f}"))
            self.scene_table.setItem(i, 3, QTableWidgetItem("✓"))
    
    def on_finished(self, video_path):
        """Generation completed"""
        self.progress_bar.hide()
        self.status_label.setText(f"Completed! Video saved to: {video_path}")
        
        # Reset UI
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        InfoBar.success(
            "Success",
            f"Intelligent video generation completed!\nSaved to: {video_path}",
            duration=5000,
            parent=self
        )
    
    def on_error(self, error_msg):
        """Handle error"""
        self.progress_bar.hide()
        self.status_label.setText(f"Error: {error_msg}")
        
        # Reset UI
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        InfoBar.error(
            "Error",
            f"Generation failed: {error_msg}",
            duration=5000,
            parent=self
        )
    
    def on_stop_clicked(self):
        """Stop generation"""
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread.wait()
            
            self.progress_bar.hide()
            self.status_label.setText("Stopped")
            self.generate_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            InfoBar.warning(
                "Stopped",
                "Video generation stopped",
                duration=2000,
                parent=self
            )
    
    def on_open_folder_clicked(self):
        """Open output folder"""
        import subprocess
        import platform
        
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', str(WORK_PATH)])
            elif platform.system() == 'Windows':
                os.startfile(WORK_PATH)
            else:  # Linux
                subprocess.run(['xdg-open', str(WORK_PATH)])
        except Exception as e:
            InfoBar.error(
                "Error",
                f"Failed to open folder: {e}",
                duration=3000,
                parent=self
            )

