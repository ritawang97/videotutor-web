# -*- coding: utf-8 -*-
"""
RAG问答系统界面
基于RAG的学生问答系统，支持题库导入和智能问答
"""

import os
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QFileDialog, QProgressBar, QScrollArea,
    QTextEdit, QSplitter
)
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, PrimaryPushButton,
    ComboBox, CheckBox, InfoBar, InfoBarPosition, TextEdit,
    ToolButton, FluentIcon
)

from app.config import WORK_PATH, APPDATA_PATH
from app.thread.rag_qa_thread import QuestionBankImportThread, RAGQueryThread
from app.core.utils.logger import setup_logger

# 可选导入VectorStore
try:
    from app.core.rag.vector_store import VectorStore
    VECTOR_STORE_AVAILABLE = True
except ImportError as e:
    VECTOR_STORE_AVAILABLE = False
    VectorStore = None

logger = setup_logger("RAGQAInterface")


class RAGQAInterface(QWidget):
    """RAG问答系统界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_thread = None
        self.query_thread = None
        
        self.setObjectName("RAGQAInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setup_ui()
        self.update_vector_db_info()
    
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title = BodyLabel("📚 RAG Student Q&A System", self)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4a90e2;")
        main_layout.addWidget(title)
        
        # 描述
        desc = BodyLabel(
            "基于RAG（检索增强生成）的学生问答系统：导入题库 → 向量化存储 → 智能问答",
            self
        )
        desc.setStyleSheet("font-size: 12px; color: #888;")
        main_layout.addWidget(desc)
        
        # 创建分割器，左右布局
        splitter = QSplitter(Qt.Horizontal, self)
        
        # 左侧：题库导入区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 题库导入区域
        import_group = QGroupBox("Question Bank Import", self)
        import_layout = QVBoxLayout(import_group)
        
        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(BodyLabel("Question Bank File:"))
        self.file_input = LineEdit(self)
        self.file_input.setPlaceholderText("Select JSON/CSV/TXT file")
        file_layout.addWidget(self.file_input)
        
        self.browse_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_button.setFixedSize(35, 35)
        self.browse_button.clicked.connect(self.on_browse_file)
        file_layout.addWidget(self.browse_button)
        
        import_layout.addLayout(file_layout)
        
        # 向量数据库信息
        self.db_info_label = BodyLabel("", self)
        self.db_info_label.setStyleSheet("color: #888; font-size: 11px;")
        import_layout.addWidget(self.db_info_label)
        
        # 导入按钮
        import_button_layout = QHBoxLayout()
        import_button_layout.addStretch()
        self.import_button = PrimaryPushButton("📥 Import Question Bank", self)
        self.import_button.clicked.connect(self.on_import_clicked)
        import_button_layout.addWidget(self.import_button)
        
        self.reset_button = PushButton("🔄 Reset Database", self)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        import_button_layout.addWidget(self.reset_button)
        import_button_layout.addStretch()
        
        import_layout.addLayout(import_button_layout)
        
        # 导入进度
        self.import_progress = QProgressBar(self)
        self.import_progress.setTextVisible(True)
        self.import_progress.hide()
        import_layout.addWidget(self.import_progress)
        
        # 导入状态
        self.import_status = BodyLabel("", self)
        self.import_status.setStyleSheet("color: #888; font-size: 11px;")
        import_layout.addWidget(self.import_status)
        
        left_layout.addWidget(import_group)
        left_layout.addStretch()
        
        splitter.addWidget(left_widget)
        
        # 右侧：问答区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 问答区域
        qa_group = QGroupBox("Student Q&A", self)
        qa_layout = QVBoxLayout(qa_group)
        
        # 问题输入
        qa_layout.addWidget(BodyLabel("Student Question:"))
        self.question_input = TextEdit(self)
        self.question_input.setPlaceholderText("Enter student's question here...")
        self.question_input.setMaximumHeight(100)
        qa_layout.addWidget(self.question_input)
        
        # 选项
        options_layout = QHBoxLayout()
        self.use_llm_checkbox = CheckBox("Use LLM to Generate Answer", self)
        self.use_llm_checkbox.setChecked(True)
        options_layout.addWidget(self.use_llm_checkbox)
        options_layout.addStretch()
        qa_layout.addLayout(options_layout)
        
        # 查询按钮
        query_button_layout = QHBoxLayout()
        query_button_layout.addStretch()
        self.query_button = PrimaryPushButton("🔍 Query", self)
        self.query_button.clicked.connect(self.on_query_clicked)
        query_button_layout.addWidget(self.query_button)
        query_button_layout.addStretch()
        qa_layout.addLayout(query_button_layout)
        
        # 查询进度
        self.query_progress = QProgressBar(self)
        self.query_progress.setTextVisible(True)
        self.query_progress.hide()
        qa_layout.addWidget(self.query_progress)
        
        # 查询状态
        self.query_status = BodyLabel("", self)
        self.query_status.setStyleSheet("color: #888; font-size: 11px;")
        qa_layout.addWidget(self.query_status)
        
        right_layout.addWidget(qa_group)
        
        # 答案显示区域
        answer_group = QGroupBox("Answer & Sources", self)
        answer_layout = QVBoxLayout(answer_group)
        
        # 答案
        answer_layout.addWidget(BodyLabel("Answer:"))
        self.answer_output = TextEdit(self)
        self.answer_output.setReadOnly(True)
        self.answer_output.setPlaceholderText("Answer will be displayed here...")
        answer_layout.addWidget(self.answer_output)
        
        # 来源信息
        answer_layout.addWidget(BodyLabel("Reference Sources:"))
        self.sources_output = TextEdit(self)
        self.sources_output.setReadOnly(True)
        self.sources_output.setMaximumHeight(150)
        self.sources_output.setPlaceholderText("Reference sources will be displayed here...")
        answer_layout.addWidget(self.sources_output)
        
        right_layout.addWidget(answer_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
    
    def on_browse_file(self):
        """浏览题库文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Question Bank File",
            str(WORK_PATH),
            "Question Bank Files (*.json *.csv *.txt);;All Files (*.*)"
        )
        if file_path:
            self.file_input.setText(file_path)
    
    def on_import_clicked(self):
        """导入题库"""
        file_path = self.file_input.text().strip()
        if not file_path:
            InfoBar.warning(
                title="Warning",
                content="Please select a question bank file",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        if not os.path.exists(file_path):
            InfoBar.error(
                title="Error",
                content="File not found",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 禁用按钮
        self.import_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.import_progress.show()
        self.import_status.setText("Starting import...")
        
        # 创建导入线程
        vector_store_path = str(APPDATA_PATH / "rag_vector_db")
        self.import_thread = QuestionBankImportThread(file_path, vector_store_path)
        self.import_thread.progress.connect(self.on_import_progress)
        self.import_thread.finished.connect(self.on_import_finished)
        self.import_thread.error.connect(self.on_import_error)
        self.import_thread.start()
    
    def on_import_progress(self, message: str):
        """导入进度更新"""
        self.import_status.setText(message)
    
    def on_import_finished(self, success: bool, message: str):
        """导入完成"""
        self.import_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.import_progress.hide()
        
        if success:
            InfoBar.success(
                title="Success",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            self.update_vector_db_info()
        else:
            InfoBar.error(
                title="Error",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_import_error(self, error_message: str):
        """导入错误"""
        self.import_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.import_progress.hide()
        self.import_status.setText("")
        
        InfoBar.error(
            title="Import Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def on_reset_clicked(self):
        """重置向量数据库"""
        if not VECTOR_STORE_AVAILABLE:
            InfoBar.error(
                title="Error",
                content="chromadb is not installed. Please install: pip install chromadb",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return
        
        from qfluentwidgets import MessageBox
        
        reply = MessageBox.warning(
            self,
            "Reset Database",
            "Are you sure you want to reset the vector database? All imported questions will be deleted.",
            MessageBox.Yes | MessageBox.No
        )
        
        if reply == MessageBox.Yes:
            try:
                vector_store_path = str(APPDATA_PATH / "rag_vector_db")
                vector_store = VectorStore(
                    persist_directory=vector_store_path,
                    collection_name="question_bank"
                )
                vector_store.reset()
                
                InfoBar.success(
                    title="Success",
                    content="Vector database reset successfully",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                self.update_vector_db_info()
            except Exception as e:
                InfoBar.error(
                    title="Error",
                    content=f"Failed to reset database: {str(e)}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
    
    def on_query_clicked(self):
        """执行查询"""
        question = self.question_input.toPlainText().strip()
        if not question:
            InfoBar.warning(
                title="Warning",
                content="Please enter a question",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 禁用按钮
        self.query_button.setEnabled(False)
        self.query_progress.show()
        self.query_status.setText("Querying...")
        self.answer_output.clear()
        self.sources_output.clear()
        
        # 创建查询线程
        vector_store_path = str(APPDATA_PATH / "rag_vector_db")
        use_llm = self.use_llm_checkbox.isChecked()
        self.query_thread = RAGQueryThread(question, vector_store_path, use_llm)
        self.query_thread.progress.connect(self.on_query_progress)
        self.query_thread.result.connect(self.on_query_result)
        self.query_thread.error.connect(self.on_query_error)
        self.query_thread.start()
    
    def on_query_progress(self, message: str):
        """查询进度更新"""
        self.query_status.setText(message)
    
    def on_query_result(self, result: dict):
        """查询结果"""
        self.query_button.setEnabled(True)
        self.query_progress.hide()
        self.query_status.setText("")
        
        # 显示答案
        answer = result.get("answer", "")
        confidence = result.get("confidence", 0.0)
        self.answer_output.setPlainText(answer)
        
        # 显示来源
        sources = result.get("sources", [])
        if sources:
            sources_text = f"Found {len(sources)} relevant sources:\n\n"
            for i, source in enumerate(sources, 1):
                metadata = source.get("metadata", {})
                question = metadata.get("question", "")
                answer_text = metadata.get("answer", "")
                distance = source.get("distance", 0.0)
                similarity = f"{(1 - distance / 2) * 100:.1f}%" if distance else "N/A"
                
                sources_text += f"Source {i} (Similarity: {similarity}):\n"
                if question:
                    sources_text += f"Q: {question}\n"
                if answer_text:
                    sources_text += f"A: {answer_text[:200]}...\n" if len(answer_text) > 200 else f"A: {answer_text}\n"
                sources_text += "\n"
            
            self.sources_output.setPlainText(sources_text)
        else:
            self.sources_output.setPlainText("No relevant sources found.")
        
        # 显示置信度
        if confidence > 0:
            confidence_text = f"Confidence: {confidence * 100:.1f}%"
            self.query_status.setText(confidence_text)
    
    def on_query_error(self, error_message: str):
        """查询错误"""
        self.query_button.setEnabled(True)
        self.query_progress.hide()
        self.query_status.setText("")
        
        InfoBar.error(
            title="Query Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def update_vector_db_info(self):
        """更新向量数据库信息"""
        if not VECTOR_STORE_AVAILABLE:
            self.db_info_label.setText("Vector Database: chromadb not installed. Please install: pip install chromadb")
            return
        
        try:
            vector_store_path = str(APPDATA_PATH / "rag_vector_db")
            vector_store = VectorStore(
                persist_directory=vector_store_path,
                collection_name="question_bank"
            )
            info = vector_store.get_collection_info()
            count = info.get("count", 0)
            self.db_info_label.setText(f"Vector Database: {count} documents stored")
        except Exception as e:
            logger.error(f"Failed to update vector db info: {e}")
            self.db_info_label.setText("Vector Database: Not initialized")

