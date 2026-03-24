# -*- coding: utf-8 -*-
"""
PDF向量数据库可视化界面
用于PDF上传、向量化、浏览和搜索
"""

import os
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QFileDialog, QProgressBar, QScrollArea,
    QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMessageBox
)
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, PrimaryPushButton,
    InfoBar, InfoBarPosition, TextEdit,
    ToolButton, FluentIcon, CardWidget, TitleLabel,
    ComboBox
)

from app.config import APPDATA_PATH, CACHE_PATH
from app.thread.pdf_vector_db_thread import PDFVectorizationThread
from app.thread.pdf_chat_thread import PDFQueryThread, PDFChatThread
from app.thread.email_thread import EmailSendThread
from app.thread.email_bot_thread import EmailBotThread
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.core.storage.database import DatabaseManager
from app.core.storage.asset_manager import AssetManager
from app.common.config import cfg
from app.core.utils.logger import setup_logger
from PyQt5.QtGui import QPixmap

logger = setup_logger("PDFVectorDBInterface")

# 可选导入VectorStore
try:
    from app.core.pdf_vector_db import PDFVectorStore
    VECTOR_STORE_AVAILABLE = True
except ImportError as e:
    VECTOR_STORE_AVAILABLE = False
    PDFVectorStore = None


class PDFVectorDBInterface(QWidget):
    """PDF向量数据库可视化界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vectorization_thread = None
        self.query_thread = None
        self.chat_thread = None
        self.email_thread = None
        self.email_bot_thread = None
        self.vector_store_path = str(APPDATA_PATH / "pdf_vector_db")
        self.current_query_pages = []  # Store current query results (relevant pages)
        self.current_answer = ""  # Store current chatbot answer
        
        # Initialize asset manager
        self.db_manager = DatabaseManager(str(CACHE_PATH))
        self.asset_manager = AssetManager(self.db_manager)
        
        self.setObjectName("PDFVectorDBInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        from app.common.ui_styles import PDF_VECTOR_DB_STYLE, COLORS
        self.setStyleSheet(PDF_VECTOR_DB_STYLE)
        
        self.setup_ui()
        self.update_db_info()
        self.update_embedding_tip()
        self.refresh_asset_doc_list()
    
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局（无边距，与其他模块一致）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域（与其他模块一致）
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容组件
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(12)  # 减少间距
        content_layout.setContentsMargins(15, 10, 15, 10)  # 减少边距
        
        # 标题（与其他模块一致）
        title = TitleLabel("📄 PDF Vector Database", self)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a90e2;")
        content_layout.addWidget(title)
        
        # 创建分割器，左右布局
        splitter = QSplitter(Qt.Horizontal, self)
        
        # 左侧：PDF上传和向量化区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # PDF上传区域
        upload_group = QGroupBox("PDF Upload & Vectorization", self)
        upload_layout = QVBoxLayout(upload_group)
        
        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(BodyLabel("PDF File:", self))
        self.file_input = LineEdit(self)
        self.file_input.setPlaceholderText("Select PDF file")
        file_layout.addWidget(self.file_input)
        
        self.browse_button = ToolButton(FluentIcon.FOLDER, self)
        self.browse_button.setFixedSize(35, 35)
        self.browse_button.clicked.connect(self.on_browse_file)
        file_layout.addWidget(self.browse_button)
        
        upload_layout.addLayout(file_layout)
        
        # 向量数据库信息
        self.db_info_label = BodyLabel("", self)
        self.db_info_label.setStyleSheet("color: #888; font-size: 11px;")
        upload_layout.addWidget(self.db_info_label)
        
        # Embedding配置提示和快速切换（更明显的布局）
        embedding_config_group = QGroupBox("🔧 Embedding Configuration", self)
        embedding_config_layout = QVBoxLayout(embedding_config_group)
        
        # 当前状态提示
        self.embedding_tip = BodyLabel("", self)
        self.embedding_tip.setStyleSheet("color: #ff9800; font-size: 12px; font-weight: bold; padding: 5px;")
        self.embedding_tip.setWordWrap(True)
        embedding_config_layout.addWidget(self.embedding_tip)
        
        # 快速切换按钮区域
        switch_buttons_layout = QHBoxLayout()
        switch_buttons_layout.addStretch()
        
        # 切换到本地embedding按钮（更明显）
        self.switch_to_local_button = PrimaryPushButton("🆓 Use Local Embedding (Free, No API Key)", self)
        self.switch_to_local_button.setFixedHeight(40)
        self.switch_to_local_button.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.switch_to_local_button.clicked.connect(self.on_switch_to_local)
        switch_buttons_layout.addWidget(self.switch_to_local_button)
        
        # 切换到Gemini按钮（如果需要）
        self.switch_to_gemini_button = PushButton("Switch to Gemini", self)
        self.switch_to_gemini_button.setFixedHeight(40)
        self.switch_to_gemini_button.clicked.connect(self.on_switch_to_gemini)
        switch_buttons_layout.addWidget(self.switch_to_gemini_button)
        
        switch_buttons_layout.addStretch()
        embedding_config_layout.addLayout(switch_buttons_layout)
        
        upload_layout.addWidget(embedding_config_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.vectorize_button = PrimaryPushButton("📥 Vectorize PDF", self)
        self.vectorize_button.clicked.connect(self.on_vectorize_clicked)
        button_layout.addWidget(self.vectorize_button)
        
        self.reset_button = PushButton("🔄 Reset Database", self)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        
        upload_layout.addLayout(button_layout)
        
        # 进度
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        upload_layout.addWidget(self.progress_bar)
        
        # 状态
        self.status_label = BodyLabel("", self)
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        upload_layout.addWidget(self.status_label)
        
        left_layout.addWidget(upload_group)
        left_layout.addStretch()
        
        splitter.addWidget(left_widget)
        
        # 右侧：向量内容浏览区域（不再需要单独的滚动区域，因为整个内容已在滚动区域内）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 浏览区域
        browse_group = QGroupBox("Vector Content Browser", self)
        browse_layout = QVBoxLayout(browse_group)
        
        # PDF列表
        browse_layout.addWidget(BodyLabel("PDF Files:", self))
        self.pdf_tree = QTreeWidget(self)
        self.pdf_tree.setHeaderLabels(["PDF Name / Page", "Info"])
        self.pdf_tree.setColumnWidth(0, 300)
        self.pdf_tree.setColumnWidth(1, 150)
        self.pdf_tree.itemDoubleClicked.connect(self.on_pdf_selected)
        browse_layout.addWidget(self.pdf_tree)
        
        # 页面内容显示
        browse_layout.addWidget(BodyLabel("Page Content:", self))
        self.content_text = QTextEdit(self)
        self.content_text.setReadOnly(True)
        self.content_text.setPlaceholderText("Select a PDF to view page content...")
        self.content_text.setMaximumHeight(200)
        browse_layout.addWidget(self.content_text)
        
        # PDF问答聊天区域
        chat_group = QGroupBox("💬 PDF Q&A Chat", self)
        chat_layout = QVBoxLayout(chat_group)
        
        # 问题输入
        question_layout = QHBoxLayout()
        question_layout.addWidget(BodyLabel("Your Question:", self))
        self.question_input = LineEdit(self)
        self.question_input.setPlaceholderText("Enter your question about the PDF...")
        self.question_input.returnPressed.connect(self.on_query_clicked)
        question_layout.addWidget(self.question_input)
        
        self.query_button = PrimaryPushButton("🔍 Query", self)
        self.query_button.clicked.connect(self.on_query_clicked)
        question_layout.addWidget(self.query_button)
        
        chat_layout.addLayout(question_layout)
        
        # Related page numbers display
        self.related_pages_label = BodyLabel("", self)
        self.related_pages_label.setStyleSheet("color: #4a90e2; font-size: 11px; padding: 5px;")
        self.related_pages_label.setWordWrap(True)
        self.related_pages_label.hide()
        chat_layout.addWidget(self.related_pages_label)
        
        # 操作按钮区域
        action_layout = QHBoxLayout()
        action_layout.addWidget(BodyLabel("LLM Service:", self))
        self.llm_service_combo = ComboBox(self)
        self.llm_service_combo.addItems(["gemini", "openai"])
        self.llm_service_combo.setCurrentText("gemini")
        action_layout.addWidget(self.llm_service_combo)
        
        action_layout.addStretch()
        
        self.view_pdf_button = PushButton("📄 View PDF Pages", self)
        self.view_pdf_button.clicked.connect(self.on_view_pdf_clicked)
        self.view_pdf_button.hide()
        action_layout.addWidget(self.view_pdf_button)
        
        self.ask_chatbot_button = PrimaryPushButton("🤖 Ask Chatbot", self)
        self.ask_chatbot_button.clicked.connect(self.on_ask_chatbot_clicked)
        self.ask_chatbot_button.hide()
        action_layout.addWidget(self.ask_chatbot_button)
        
        self.send_email_button = PushButton("📧 Send Email", self)
        self.send_email_button.clicked.connect(self.on_send_email_clicked)
        self.send_email_button.hide()
        action_layout.addWidget(self.send_email_button)
        
        chat_layout.addLayout(action_layout)
        
        # 聊天历史/回答显示
        self.chat_output = QTextEdit(self)
        self.chat_output.setReadOnly(True)
        self.chat_output.setPlaceholderText("Chat history and answers will be displayed here...")
        self.chat_output.setMaximumHeight(200)
        chat_layout.addWidget(self.chat_output)
        
        browse_layout.addWidget(chat_group)
        
        # Email Bot Control Group
        email_bot_group = QGroupBox("📧 Email Bot (Auto Reply)", self)
        email_bot_layout = QVBoxLayout(email_bot_group)
        
        # Status label
        self.email_bot_status_label = BodyLabel("Status: Stopped", self)
        self.email_bot_status_label.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        email_bot_layout.addWidget(self.email_bot_status_label)
        
        # Progress/Log display
        self.email_bot_log = QTextEdit(self)
        self.email_bot_log.setReadOnly(True)
        self.email_bot_log.setPlaceholderText("Email bot logs will be displayed here...")
        self.email_bot_log.setMaximumHeight(100)
        email_bot_layout.addWidget(self.email_bot_log)
        
        # Control buttons
        email_bot_control_layout = QHBoxLayout()
        email_bot_control_layout.addStretch()
        
        self.oauth_login_button = PushButton("🔐 Login with Browser (OAuth)", self)
        self.oauth_login_button.clicked.connect(self.on_oauth_login)
        email_bot_control_layout.addWidget(self.oauth_login_button)
        
        self.start_email_bot_button = PrimaryPushButton("▶️ Start Email Bot", self)
        self.start_email_bot_button.clicked.connect(self.on_start_email_bot)
        email_bot_control_layout.addWidget(self.start_email_bot_button)
        
        self.stop_email_bot_button = PushButton("⏹️ Stop Email Bot", self)
        self.stop_email_bot_button.clicked.connect(self.on_stop_email_bot)
        self.stop_email_bot_button.setEnabled(False)
        email_bot_control_layout.addWidget(self.stop_email_bot_button)
        
        email_bot_control_layout.addStretch()
        email_bot_layout.addLayout(email_bot_control_layout)
        
        browse_layout.addWidget(email_bot_group)
        
        right_layout.addWidget(browse_group)
        
        # 图片资产管理区域
        assets_group = QGroupBox("🖼️ PDF Figure Assets", self)
        assets_layout = QVBoxLayout(assets_group)
        
        # 文档选择
        doc_layout = QHBoxLayout()
        doc_layout.addWidget(BodyLabel("Document:", self))
        self.asset_doc_combo = ComboBox(self)
        self.asset_doc_combo.setPlaceholderText("Select a PDF document...")
        self.asset_doc_combo.currentTextChanged.connect(self.on_asset_doc_changed)
        doc_layout.addWidget(self.asset_doc_combo)
        
        refresh_assets_button = PushButton("🔄 Refresh List", self)
        refresh_assets_button.clicked.connect(self.refresh_asset_doc_list)
        doc_layout.addWidget(refresh_assets_button)
        
        # 添加调试和同步按钮
        debug_button = PushButton("🔍 Debug", self)
        debug_button.clicked.connect(self.debug_assets)
        doc_layout.addWidget(debug_button)
        
        sync_button = PushButton("🔄 Sync Assets", self)
        sync_button.clicked.connect(self.sync_assets_to_db)
        sync_button.setToolTip("Sync existing extracted images to database")
        doc_layout.addWidget(sync_button)
        assets_layout.addLayout(doc_layout)
        
        # 图片列表
        list_header_layout = QHBoxLayout()
        list_header_layout.addWidget(BodyLabel("Extracted Images:", self))
        list_header_layout.addStretch()
        delete_button = PushButton("🗑️ Delete Selected", self)
        delete_button.clicked.connect(self.on_delete_selected_asset)
        delete_button.setToolTip("Delete selected image from database and file system")
        list_header_layout.addWidget(delete_button)
        assets_layout.addLayout(list_header_layout)
        
        self.assets_list = QTreeWidget(self)
        self.assets_list.setHeaderLabels(["Page", "Image", "Note Status"])
        self.assets_list.setColumnWidth(0, 80)
        self.assets_list.setColumnWidth(1, 200)
        self.assets_list.setColumnWidth(2, 100)
        self.assets_list.setSelectionMode(QTreeWidget.ExtendedSelection)  # 允许多选
        self.assets_list.itemDoubleClicked.connect(self.on_asset_selected)
        assets_layout.addWidget(self.assets_list)
        
        # 图片预览和备注编辑
        asset_detail_group = QGroupBox("Image Details & Teacher Note", self)
        asset_detail_layout = QVBoxLayout(asset_detail_group)
        
        # 图片预览
        self.asset_image_label = QLabel(self)
        self.asset_image_label.setMinimumHeight(200)
        self.asset_image_label.setMaximumHeight(300)
        self.asset_image_label.setAlignment(Qt.AlignCenter)
        self.asset_image_label.setStyleSheet("border: 1px solid #ddd; background-color: #f5f5f5;")
        self.asset_image_label.setText("Select an image to preview")
        asset_detail_layout.addWidget(self.asset_image_label)
        
        # 图片信息
        self.asset_info_label = BodyLabel("", self)
        self.asset_info_label.setStyleSheet("color: #888; font-size: 11px;")
        asset_detail_layout.addWidget(self.asset_info_label)
        
        # 备注输入
        asset_detail_layout.addWidget(BodyLabel("Teacher Note:", self))
        self.asset_note_input = TextEdit(self)
        self.asset_note_input.setPlaceholderText("Enter a note describing this image...")
        self.asset_note_input.setMaximumHeight(100)
        asset_detail_layout.addWidget(self.asset_note_input)
        
        # 保存按钮
        save_note_button_layout = QHBoxLayout()
        save_note_button_layout.addStretch()
        self.save_note_button = PrimaryPushButton("💾 Save Note", self)
        self.save_note_button.clicked.connect(self.on_save_asset_note)
        self.save_note_button.setEnabled(False)
        save_note_button_layout.addWidget(self.save_note_button)
        asset_detail_layout.addLayout(save_note_button_layout)
        
        assets_layout.addWidget(asset_detail_group)
        
        right_layout.addWidget(assets_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        # 将splitter添加到内容布局
        content_layout.addWidget(splitter)
        content_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
    
    def on_browse_file(self):
        """浏览PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*.*)"
        )
        if file_path:
            self.file_input.setText(file_path)
    
    def on_vectorize_clicked(self):
        """向量化PDF"""
        file_path = self.file_input.text().strip()
        if not file_path:
            InfoBar.warning(
                title="Warning",
                content="Please select a PDF file",
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
        
        # 禁用按钮
        self.vectorize_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting vectorization...")
        
        # 创建向量化线程
        self.vectorization_thread = PDFVectorizationThread(file_path, self.vector_store_path)
        self.vectorization_thread.progress.connect(self.on_vectorization_progress)
        self.vectorization_thread.finished.connect(self.on_vectorization_finished)
        self.vectorization_thread.error.connect(self.on_vectorization_error)
        self.vectorization_thread.start()
    
    def on_vectorization_progress(self, message: str):
        """向量化进度更新"""
        self.status_label.setText(message)
    
    def on_vectorization_finished(self, success: bool, message: str):
        """向量化完成"""
        self.vectorize_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("")
        
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
            self.update_db_info()
            self.refresh_pdf_list()
            # 刷新资产文档列表（PDF导入后可能有新图片）
            self.refresh_asset_doc_list()
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
    
    def on_vectorization_error(self, error_message: str):
        """向量化错误"""
        self.vectorize_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("")
        
        # 检查是否是API错误，提供解决方案
        error_lower = error_message.lower()
        if "api" in error_lower or "key" in error_lower or "unauthorized" in error_lower:
            # 显示更详细的错误信息和解决方案
            detailed_message = (
                f"{error_message}\n\n"
                f"💡 Solutions:\n"
                f"1. Check OpenAI API Key in Settings\n"
                f"2. Verify API Key has sufficient quota\n"
                f"3. Check network connection\n"
                f"4. Switch to local embedding (Settings → RAG → Embedding Type → local)"
            )
            InfoBar.error(
                title="API Error",
                content=detailed_message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=8000,
                parent=self
            )
        else:
            InfoBar.error(
                title="Vectorization Error",
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
        
        reply = QMessageBox.warning(
            self,
            "Reset Database",
            "Are you sure you want to reset the vector database? All PDF vectors will be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                vector_store = PDFVectorStore(self.vector_store_path)
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
                self.update_db_info()
                self.refresh_pdf_list()
                self.content_text.clear()
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
    
    def on_pdf_selected(self, item: QTreeWidgetItem, column: int):
        """PDF选择事件（双击）"""
        if item.parent() is None:
            # 选择了PDF根节点
            pdf_name = item.text(0)
            self.load_pdf_pages(pdf_name)
        else:
            # 选择了页面节点
            pdf_name = item.parent().text(0)
            page_text = item.text(0)
            if page_text.startswith("Page "):
                page_num = int(page_text.replace("Page ", ""))
                self.load_page_content(pdf_name, page_num)
    
    def load_pdf_pages(self, pdf_name: str):
        """加载PDF的所有页面"""
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            pages = vector_store.get_all_pages(pdf_name=pdf_name)
            
            # 找到对应的PDF节点并展开
            for i in range(self.pdf_tree.topLevelItemCount()):
                item = self.pdf_tree.topLevelItem(i)
                if item.text(0) == pdf_name:
                    item.setExpanded(True)
                    # 如果还没有子节点，添加页面节点
                    if item.childCount() == 0:
                        for page in pages:
                            page_num = page["metadata"].get("page", 0)
                            page_item = QTreeWidgetItem(item)
                            page_item.setText(0, f"Page {page_num}")
                            page_item.setText(1, f"{len(page['document'])} chars")
                    break
            
            self.content_text.clear()
            self.content_text.setPlainText(f"PDF: {pdf_name}\nTotal Pages: {len(pages)}\n\nDouble-click a page to view content.")
            
        except Exception as e:
            logger.error(f"Failed to load PDF pages: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to load PDF pages: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def load_page_content(self, pdf_name: str, page_num: int):
        """加载页面内容"""
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            pages = vector_store.get_all_pages(pdf_name=pdf_name)
            
            # 找到对应页面
            target_page = None
            for page in pages:
                if page["metadata"].get("page") == page_num:
                    target_page = page
                    break
            
            if target_page:
                content = f"PDF: {pdf_name}\nPage: {page_num}\n\n{target_page['document']}"
                self.content_text.setPlainText(content)
            else:
                self.content_text.setPlainText(f"Page {page_num} not found in {pdf_name}")
                
        except Exception as e:
            logger.error(f"Failed to load page content: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to load page content: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def on_search_clicked(self):
        """执行相似度搜索"""
        query_text = self.search_input.text().strip()
        if not query_text:
            InfoBar.warning(
                title="Warning",
                content="Please enter search text",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        if not VECTOR_STORE_AVAILABLE:
            InfoBar.error(
                title="Error",
                content="chromadb is not installed",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        try:
            # 生成查询embedding
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "gemini"
            embedding_model = cfg.get(cfg.rag_embedding_model) if hasattr(cfg, 'rag_embedding_model') else "gemini-embedding-001"
            
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                api_base = cfg.get(cfg.openai_api_base)
                if not api_key:
                    InfoBar.error(
                        title="Error",
                        content="OpenAI API key not configured",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    return
                embedding_generator = EmbeddingGenerator(
                    model_type="openai",
                    api_key=api_key,
                    api_base=api_base,
                    model_name=embedding_model
                )
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
                if not api_key or not api_key.strip():
                    InfoBar.error(
                        title="Error",
                        content="Gemini API key not configured. Please configure it in Settings → LLM Configuration → Gemini API Key",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )
                    return
                # 确保API key没有多余空格
                api_key = api_key.strip()
                embedding_generator = EmbeddingGenerator(
                    model_type="gemini",
                    api_key=api_key,
                    api_base=None,
                    model_name=embedding_model
                )
            else:
                embedding_generator = EmbeddingGenerator(
                    model_type="local",
                    model_name=embedding_model
                )
            
            query_embedding = embedding_generator.generate_embedding(query_text)
            
            # 搜索
            vector_store = PDFVectorStore(self.vector_store_path)
            results = vector_store.search(query_embedding, n_results=5)
            
            # 显示结果
            if results:
                results_text = f"Found {len(results)} similar pages:\n\n"
                for i, result in enumerate(results, 1):
                    metadata = result.get("metadata", {})
                    pdf_name = metadata.get("pdf_name", "Unknown")
                    page_num = metadata.get("page", 0)
                    distance = result.get("distance", 0.0)
                    similarity = f"{(1 - distance / 2) * 100:.1f}%" if distance else "N/A"
                    content = result.get("document", "")[:200] + "..." if len(result.get("document", "")) > 200 else result.get("document", "")
                    
                    results_text += f"Result {i} (Similarity: {similarity}):\n"
                    results_text += f"  PDF: {pdf_name}, Page: {page_num}\n"
                    results_text += f"  Content: {content}\n\n"
                
                self.search_results.setPlainText(results_text)
            else:
                self.search_results.setPlainText("No similar pages found.")
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            InfoBar.error(
                title="Search Error",
                content=f"Search failed: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def update_db_info(self):
        """更新向量数据库信息"""
        if not VECTOR_STORE_AVAILABLE:
            self.db_info_label.setText("Vector Database: chromadb not installed. Please install: pip install chromadb")
            return
        
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            info = vector_store.get_collection_info()
            count = info.get("count", 0)
            pdf_count = info.get("pdf_count", 0)
            self.db_info_label.setText(f"Vector Database: {count} pages from {pdf_count} PDFs")
        except Exception as e:
            logger.error(f"Failed to update vector db info: {e}")
            self.db_info_label.setText("Vector Database: Not initialized")
    
    def update_embedding_tip(self):
        """更新Embedding配置提示"""
        try:
            embedding_type = cfg.get(cfg.rag_embedding_type) if hasattr(cfg, 'rag_embedding_type') else "gemini"
            if embedding_type == "openai":
                api_key = cfg.get(cfg.openai_api_key)
                gemini_key = cfg.get(cfg.gemini_api_key)
                if not api_key:
                    self.embedding_tip.setText(
                        "⚠️ Using OpenAI Embedding but API key not configured.\n"
                        "💡 Click the button below to switch to Local Embedding (Free, No API Key required)!"
                    )
                    # 显示本地按钮，隐藏Gemini按钮
                    self.switch_to_local_button.setVisible(True)
                    self.switch_to_gemini_button.setVisible(bool(gemini_key))
                else:
                    self.embedding_tip.setText(
                        "✓ Using OpenAI Embedding (API key configured)\n"
                        "💡 Want to use free local embedding? Click the button below!"
                    )
                    # 显示本地按钮，如果Gemini key已配置也显示Gemini按钮
                    self.switch_to_local_button.setVisible(True)
                    self.switch_to_gemini_button.setVisible(bool(gemini_key))
            elif embedding_type == "gemini":
                api_key = cfg.get(cfg.gemini_api_key)
                if not api_key:
                    self.embedding_tip.setText(
                        "⚠️ Using Gemini Embedding but API key not configured.\n"
                        "💡 Click the button below to switch to Local Embedding (Free, No API Key required)!"
                    )
                    # 显示本地按钮，隐藏Gemini按钮
                    self.switch_to_local_button.setVisible(True)
                    self.switch_to_gemini_button.setVisible(False)
                else:
                    self.embedding_tip.setText(
                        "✓ Using Gemini Embedding (API key configured)\n"
                        "💡 Want to use free local embedding? Click the button below!"
                    )
                    # 显示本地按钮，隐藏Gemini按钮（因为已经是Gemini了）
                    self.switch_to_local_button.setVisible(True)
                    self.switch_to_gemini_button.setVisible(False)
            else:
                self.embedding_tip.setText(
                    "✅ Using Local Embedding (Free, No API Key required)\n"
                    "🎉 You're all set! No configuration needed."
                )
                # 隐藏本地按钮（因为已经是本地了），如果Gemini key已配置显示Gemini按钮
                self.switch_to_local_button.setVisible(False)
                gemini_key = cfg.get(cfg.gemini_api_key)
                self.switch_to_gemini_button.setVisible(bool(gemini_key))
        except Exception as e:
            logger.error(f"Failed to update embedding tip: {e}")
            self.embedding_tip.setText("")
            self.switch_to_local_button.setVisible(True)
            self.switch_to_gemini_button.setVisible(False)
    
    def on_switch_to_local(self):
        """切换到本地Embedding"""
        try:
            # 切换到本地embedding
            cfg.set(cfg.rag_embedding_type, "local")
            cfg.set(cfg.rag_embedding_model, "paraphrase-multilingual-MiniLM-L12-v2")
            
            # 更新提示
            self.update_embedding_tip()
            
            InfoBar.success(
                title="Success",
                content="Switched to Local Embedding (Free, No API Key required). First use will download the model automatically.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        except Exception as e:
            logger.error(f"Failed to switch to local embedding: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to switch: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def on_switch_to_gemini(self):
        """切换到Gemini Embedding"""
        try:
            # 检查Gemini API Key是否已配置
            gemini_key = cfg.get(cfg.gemini_api_key)
            if not gemini_key:
                InfoBar.warning(
                    title="Warning",
                    content="Please configure Gemini API key in Settings first",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            # 切换到Gemini
            cfg.set(cfg.rag_embedding_type, "gemini")
            cfg.set(cfg.rag_embedding_model, "gemini-embedding-001")
            
            # 更新提示
            self.update_embedding_tip()
            
            InfoBar.success(
                title="Success",
                content="Switched to Gemini Embedding",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        except Exception as e:
            logger.error(f"Failed to switch to Gemini: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to switch: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    
    def refresh_pdf_list(self):
        """刷新PDF列表"""
        if not VECTOR_STORE_AVAILABLE:
            return
        
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            info = vector_store.get_collection_info()
            pdf_list = info.get("pdf_list", [])
            pdf_stats = info.get("pdf_stats", {})
            
            # 清空树
            self.pdf_tree.clear()
            
            # 添加PDF节点
            for pdf_name in pdf_list:
                page_count = pdf_stats.get(pdf_name, 0)
                pdf_item = QTreeWidgetItem(self.pdf_tree)
                pdf_item.setText(0, pdf_name)
                pdf_item.setText(1, f"{page_count} pages")
                
        except Exception as e:
            logger.error(f"Failed to refresh PDF list: {e}")
    
    def on_query_clicked(self):
        """Execute query - search for relevant PDF pages"""
        question = self.question_input.text().strip()
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
        
        if not VECTOR_STORE_AVAILABLE:
            InfoBar.error(
                title="Error",
                content="chromadb is not installed",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 禁用按钮
        self.query_button.setEnabled(False)
        self.chat_output.clear()
        self.related_pages_label.hide()
        self.view_pdf_button.hide()
        self.ask_chatbot_button.hide()
        self.send_email_button.hide()
        self.current_answer = ""  # Clear previous answer
        
        # 在聊天输出中显示问题
        self.chat_output.append(f"❓ <b>You:</b> {question}")
        self.chat_output.append("🔍 Searching relevant PDF pages...\n")
        
        # 创建查询线程
        self.query_thread = PDFQueryThread(question, self.vector_store_path, top_k=5)
        self.query_thread.progress.connect(self.on_query_progress)
        self.query_thread.result.connect(self.on_query_result)
        self.query_thread.error.connect(self.on_query_error)
        self.query_thread.start()
    
    def on_query_progress(self, message: str):
        """Query progress update"""
        self.chat_output.append(f"⏳ {message}")
    
    def on_query_result(self, pages: list):
        """Query result - display relevant page numbers"""
        self.query_button.setEnabled(True)
        self.current_query_pages = pages
        
        if not pages:
            self.chat_output.append("❌ No relevant pages found.\n")
            return
        
        # Extract page number information
        page_info = {}
        for page in pages:
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            if pdf_name not in page_info:
                page_info[pdf_name] = []
            page_info[pdf_name].append(page_num)
        
        # Display relevant page numbers
        pages_text = "📄 <b>Related PDF Pages:</b><br>"
        for pdf_name, page_nums in page_info.items():
            page_nums_str = ", ".join([f"Page {p}" for p in sorted(page_nums)])
            pages_text += f"  • {pdf_name}: {page_nums_str}<br>"
        
        self.related_pages_label.setText(pages_text)
        self.related_pages_label.show()
        self.view_pdf_button.show()
        self.ask_chatbot_button.show()
        
        # Display results in chat
        self.chat_output.append(f"✅ Found {len(pages)} relevant page(s)\n")
        self.chat_output.append(pages_text.replace("<br>", "\n").replace("<b>", "").replace("</b>", "") + "\n")
    
    def on_query_error(self, error_message: str):
        """Query error"""
        self.query_button.setEnabled(True)
        self.chat_output.append(f"❌ Error: {error_message}\n")
        InfoBar.error(
            title="Query Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def on_view_pdf_clicked(self):
        """View relevant PDF pages"""
        if not self.current_query_pages:
            InfoBar.warning(
                title="Warning",
                content="No pages to view. Please query first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # Extract unique PDF names and page numbers
        pdf_pages = {}
        for page in self.current_query_pages:
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            if pdf_name not in pdf_pages:
                pdf_pages[pdf_name] = []
            pdf_pages[pdf_name].append(page_num)
        
        # Locate and expand in PDF tree
        self.pdf_tree.clear()
        try:
            vector_store = PDFVectorStore(self.vector_store_path)
            info = vector_store.get_collection_info()
            pdf_list = info.get("pdf_list", [])
            pdf_stats = info.get("pdf_stats", {})
            
            for pdf_name in pdf_list:
                page_count = pdf_stats.get(pdf_name, 0)
                pdf_item = QTreeWidgetItem(self.pdf_tree)
                pdf_item.setText(0, pdf_name)
                pdf_item.setText(1, f"{page_count} pages")
                
                # If it's a relevant PDF, expand and mark relevant pages
                if pdf_name in pdf_pages:
                    pdf_item.setExpanded(True)
                    for page_num in sorted(pdf_pages[pdf_name]):
                        page_item = QTreeWidgetItem(pdf_item)
                        page_item.setText(0, f"Page {page_num} ⭐")
                        page_item.setText(1, "Relevant")
                    
                    # Load the first relevant page content
                    if pdf_pages[pdf_name]:
                        first_page = pdf_pages[pdf_name][0]
                        self.load_page_content(pdf_name, first_page)
        except Exception as e:
            logger.error(f"Failed to view PDF pages: {e}")
    
    def on_ask_chatbot_clicked(self):
        """Ask chatbot a question"""
        question = self.question_input.text().strip()
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
        
        if not self.current_query_pages:
            InfoBar.warning(
                title="Warning",
                content="No relevant pages found. Please query first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # Get selected LLM service
        llm_service = self.llm_service_combo.currentText()
        
        # Disable button
        self.ask_chatbot_button.setEnabled(False)
        self.chat_output.append(f"🤖 Asking {llm_service.upper()} chatbot...\n")
        
        # Create chat thread
        self.chat_thread = PDFChatThread(question, self.current_query_pages, llm_service=llm_service)
        self.chat_thread.progress.connect(self.on_chat_progress)
        self.chat_thread.result.connect(self.on_chat_result)
        self.chat_thread.error.connect(self.on_chat_error)
        self.chat_thread.start()
    
    def on_chat_progress(self, message: str):
        """Chat progress update"""
        self.chat_output.append(f"⏳ {message}")
    
    def on_chat_result(self, answer: str):
        """Chat result - display answer"""
        self.ask_chatbot_button.setEnabled(True)
        self.current_answer = answer  # Store answer for email sending
        self.chat_output.append(f"🤖 <b>Chatbot ({self.llm_service_combo.currentText().upper()}):</b><br>{answer}<br><br>")
        # Show send email button after getting answer
        if answer:
            self.send_email_button.show()
    
    def on_chat_error(self, error_message: str):
        """Chat error"""
        self.ask_chatbot_button.setEnabled(True)
        self.chat_output.append(f"❌ Error: {error_message}<br><br>")
        InfoBar.error(
            title="Chat Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def on_send_email_clicked(self):
        """Send email with Q&A results"""
        # Check if we have required data
        question = self.question_input.text().strip()
        if not question:
            InfoBar.warning(
                title="Warning",
                content="No question to send. Please query first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        if not self.current_query_pages:
            InfoBar.warning(
                title="Warning",
                content="No relevant pages found. Please query first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        if not self.current_answer:
            InfoBar.warning(
                title="Warning",
                content="No answer to send. Please ask chatbot first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # Get email configuration
        try:
            smtp_server = cfg.get(cfg.email_smtp_server)
            smtp_port = cfg.get(cfg.email_smtp_port)
            email_address = cfg.get(cfg.email_address)
            email_password = cfg.get(cfg.email_password)
            use_tls = cfg.get(cfg.email_use_tls)
            recipient = cfg.get(cfg.email_recipient)
            
            # Validate email configuration
            if not email_address or not email_address.strip():
                InfoBar.error(
                    title="Email Configuration Error",
                    content="Email address not configured. Please configure it in Settings.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            if not email_password or not email_password.strip():
                InfoBar.error(
                    title="Email Configuration Error",
                    content="Email password not configured. Please configure it in Settings.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            if not recipient or not recipient.strip():
                InfoBar.error(
                    title="Email Configuration Error",
                    content="Recipient email address not configured. Please configure it in Settings.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            # Disable button and show progress
            self.send_email_button.setEnabled(False)
            self.chat_output.append("📧 Sending email...\n")
            
            # Get LLM service name
            llm_service = self.llm_service_combo.currentText()
            
            # Create email send thread
            self.email_thread = EmailSendThread(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                email=email_address,
                password=email_password,
                use_tls=use_tls,
                recipient=recipient,
                question=question,
                pages=self.current_query_pages,
                answer=self.current_answer,
                llm_service=llm_service
            )
            self.email_thread.progress.connect(self.on_email_progress)
            self.email_thread.success.connect(self.on_email_success)
            self.email_thread.error.connect(self.on_email_error)
            self.email_thread.start()
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            InfoBar.error(
                title="Email Error",
                content=f"Failed to send email: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            self.send_email_button.setEnabled(True)
    
    def on_email_progress(self, message: str):
        """Email sending progress update"""
        self.chat_output.append(f"⏳ {message}\n")
    
    def on_email_success(self, recipient: str):
        """Email sent successfully"""
        self.send_email_button.setEnabled(True)
        self.chat_output.append(f"✅ Email sent successfully to {recipient}\n\n")
        InfoBar.success(
            title="Email Sent",
            content=f"Email sent successfully to {recipient}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def on_email_error(self, error_message: str):
        """Email send error"""
        self.send_email_button.setEnabled(True)
        self.chat_output.append(f"❌ Failed to send email: {error_message}\n\n")
        InfoBar.error(
            title="Email Send Error",
            content=f"Failed to send email: {error_message}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=8000,
            parent=self
        )
    
    def on_start_email_bot(self):
        """Start email bot"""
        try:
            # Get configuration
            bot_email = cfg.get(cfg.email_bot_address)
            bot_password = cfg.get(cfg.email_bot_password)
            imap_server = cfg.get(cfg.email_imap_server)
            imap_port = cfg.get(cfg.email_imap_port)
            
            # Auto-detect SMTP server based on email domain, or use configured value
            configured_smtp = cfg.get(cfg.email_bot_smtp_server) if hasattr(cfg, 'email_bot_smtp_server') else ""
            if configured_smtp and configured_smtp.strip():
                smtp_server = configured_smtp
                smtp_port = cfg.get(cfg.email_bot_smtp_port) if hasattr(cfg, 'email_bot_smtp_port') else 587
            else:
                # Auto-detect based on email domain
                email_domain = bot_email.split('@')[1].lower() if '@' in bot_email else ''
                if 'outlook.com' in email_domain or 'hotmail.com' in email_domain or 'live.com' in email_domain:
                    smtp_server = "smtp-mail.outlook.com"
                    smtp_port = 587
                elif 'gmail.com' in email_domain:
                    smtp_server = "smtp.gmail.com"
                    smtp_port = 587
                elif 'yahoo.com' in email_domain:
                    smtp_server = "smtp.mail.yahoo.com"
                    smtp_port = 587
                elif 'qq.com' in email_domain:
                    smtp_server = "smtp.qq.com"
                    smtp_port = 587
                else:
                    # Default to Outlook
                    smtp_server = "smtp-mail.outlook.com"
                    smtp_port = 587
            
            check_interval = cfg.get(cfg.email_check_interval)
            llm_service = "gemini"  # Default to Gemini
            
            # Validate configuration
            if not bot_email or not bot_email.strip():
                InfoBar.error(
                    title="Email Bot Configuration Error",
                    content="Bot email address not configured. Please configure it in Settings.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            if not bot_password or not bot_password.strip():
                InfoBar.error(
                    title="Email Bot Configuration Error",
                    content="Bot email password not configured. Please configure it in Settings.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            # Check if vector database has data
            try:
                vector_store = PDFVectorStore(self.vector_store_path)
                info = vector_store.get_collection_info()
                if info["count"] == 0:
                    InfoBar.warning(
                        title="Warning",
                        content="No data in vector database. Please upload PDF files first.",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )
                    return
            except Exception as e:
                InfoBar.error(
                    title="Vector Database Error",
                    content=f"Failed to access vector database: {str(e)}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            
            # Create and start email bot thread
            self.email_bot_thread = EmailBotThread(
                vector_store_path=self.vector_store_path,
                imap_server=imap_server,
                imap_port=imap_port,
                bot_email=bot_email,
                bot_password=bot_password,
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                check_interval=check_interval,
                llm_service=llm_service
            )
            
            # Connect signals
            self.email_bot_thread.progress.connect(self.on_email_bot_progress)
            self.email_bot_thread.new_email.connect(self.on_email_bot_new_email)
            self.email_bot_thread.reply_sent.connect(self.on_email_bot_reply_sent)
            self.email_bot_thread.error.connect(self.on_email_bot_error)
            
            # Start thread
            self.email_bot_thread.start()
            
            # Update UI
            self.start_email_bot_button.setEnabled(False)
            self.stop_email_bot_button.setEnabled(True)
            self.email_bot_status_label.setText("Status: Running")
            self.email_bot_status_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 5px; font-weight: bold;")
            self.email_bot_log.append("✅ Email bot started successfully\n")
            
            InfoBar.success(
                title="Email Bot Started",
                content="Email bot is now monitoring for incoming emails.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        
        except Exception as e:
            logger.error(f"Failed to start email bot: {e}", exc_info=True)
            InfoBar.error(
                title="Email Bot Error",
                content=f"Failed to start email bot: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_stop_email_bot(self):
        """Stop email bot"""
        try:
            if self.email_bot_thread and self.email_bot_thread.isRunning():
                self.email_bot_thread.stop()
                self.email_bot_thread.wait(5000)  # Wait up to 5 seconds
                
                # Update UI
                self.start_email_bot_button.setEnabled(True)
                self.stop_email_bot_button.setEnabled(False)
                self.email_bot_status_label.setText("Status: Stopped")
                self.email_bot_status_label.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
                self.email_bot_log.append("⏹️ Email bot stopped\n")
                
                InfoBar.success(
                    title="Email Bot Stopped",
                    content="Email bot has been stopped.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        except Exception as e:
            logger.error(f"Failed to stop email bot: {e}", exc_info=True)
            InfoBar.error(
                title="Email Bot Error",
                content=f"Failed to stop email bot: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_email_bot_progress(self, message: str):
        """Email bot progress update"""
        self.email_bot_log.append(f"⏳ {message}\n")
        # Auto-scroll to bottom
        scrollbar = self.email_bot_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_email_bot_new_email(self, email_data: dict):
        """New email received"""
        from_addr = email_data.get("from", "Unknown")
        subject = email_data.get("subject", "No Subject")
        self.email_bot_log.append(f"📧 New email from: {from_addr}\n")
        self.email_bot_log.append(f"   Subject: {subject}\n")
    
    def on_email_bot_reply_sent(self, recipient: str):
        """Reply sent successfully"""
        self.email_bot_log.append(f"✅ Reply sent to: {recipient}\n")
        InfoBar.success(
            title="Reply Sent",
            content=f"Reply sent successfully to {recipient}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def on_email_bot_error(self, error_message: str):
        """Email bot error"""
        # Append to log with proper formatting for multi-line messages
        error_lines = error_message.split('\n')
        self.email_bot_log.append("❌ Error:\n")
        for line in error_lines:
            self.email_bot_log.append(f"   {line}\n")
        
        # Show first line in InfoBar, full message in log
        first_line = error_lines[0] if error_lines else error_message
        if len(error_lines) > 1:
            first_line += " (See log for details)"
        
        InfoBar.error(
            title="Email Bot Error",
            content=first_line,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=8000,
            parent=self
        )
    
    def on_oauth_login(self):
        """OAuth browser login"""
        try:
            self.email_bot_log.append("🔐 Starting OAuth authentication...\n")
            
            # Get OAuth credentials from config
            client_id = cfg.get(cfg.email_oauth_client_id)
            client_secret = cfg.get(cfg.email_oauth_client_secret)
            
            if not client_id or not client_secret or client_id.strip() == "" or client_secret.strip() == "":
                # Show instructions for setting up OAuth
                from PyQt5.QtWidgets import QMessageBox
                msg = QMessageBox(self)
                msg.setWindowTitle("OAuth Setup Required")
                msg.setText("OAuth credentials not configured.")
                msg.setInformativeText(
                    "To use browser login, you need to:\n\n"
                    "1. Create OAuth credentials in Google Cloud Console:\n"
                    "   https://console.cloud.google.com/apis/credentials\n\n"
                    "2. Create OAuth 2.0 Client ID (Web application)\n"
                    "3. Add redirect URI: http://localhost:8080/callback\n"
                    "4. Copy Client ID and Client Secret\n"
                    "5. Configure them in Settings\n\n"
                    "For now, you can use App Password method instead."
                )
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()
                return
            
            # Disable button during authentication
            self.oauth_login_button.setEnabled(False)
            
            # Import here to avoid circular imports
            from app.core.gmail_oauth import GmailOAuth
            
            # Create OAuth handler
            oauth = GmailOAuth(client_id, client_secret)
            
            # Authenticate in browser
            self.email_bot_log.append("🌐 Opening browser for authentication...\n")
            self.email_bot_log.append("   Please complete the login in your browser.\n")
            
            success = oauth.authenticate_in_browser()
            
            if success:
                self.email_bot_log.append("✅ OAuth authentication successful!\n")
                self.email_bot_log.append("   You can now start Email Bot without password.\n")
                # Enable OAuth mode
                cfg.set(cfg.email_use_oauth, True)
                InfoBar.success(
                    title="OAuth Login Successful",
                    content="You can now start Email Bot. No password needed!",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
            else:
                self.email_bot_log.append("❌ OAuth authentication failed.\n")
                InfoBar.error(
                    title="OAuth Login Failed",
                    content="Please try again or use App Password method.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
            
            self.oauth_login_button.setEnabled(True)
            
        except Exception as e:
            logger.error(f"OAuth login failed: {e}", exc_info=True)
            self.email_bot_log.append(f"❌ Error: {str(e)}\n")
            self.oauth_login_button.setEnabled(True)
            InfoBar.error(
                title="OAuth Error",
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=8000,
                parent=self
            )
    
    def refresh_asset_doc_list(self):
        """刷新资产文档列表"""
        try:
            # 确保使用正确的数据库路径（与PDF导入时一致）
            db_path = str(CACHE_PATH)  # 使用CACHE_PATH，与PDF导入时一致
            logger.info(f"Refreshing asset doc list from database: {db_path}")
            
            # 重新初始化数据库管理器以确保路径一致
            temp_db_manager = DatabaseManager(db_path)
            
            # 获取所有有资产的文档ID
            with temp_db_manager.get_session() as session:
                from app.core.storage.models import Asset
                from sqlalchemy import distinct
                # 先检查表是否存在
                from sqlalchemy import inspect as sql_inspect
                inspector = sql_inspect(temp_db_manager._engine)
                if not inspector.has_table("assets"):
                    logger.warning("Assets table does not exist yet")
                    self.asset_doc_combo.clear()
                    self.asset_doc_combo.addItem("No documents with assets (table not created)")
                    self.assets_list.clear()
                    return
                
                doc_ids = session.query(distinct(Asset.doc_id)).all()
                doc_id_list = [doc_id[0] for doc_id in doc_ids if doc_id[0]]
            
            logger.info(f"Found {len(doc_id_list)} documents with assets: {doc_id_list}")
            
            current_selection = self.asset_doc_combo.currentText()
            self.asset_doc_combo.clear()
            
            if doc_id_list:
                self.asset_doc_combo.addItems(sorted(doc_id_list))
                # 如果之前有选择，尝试恢复
                if current_selection and current_selection in doc_id_list:
                    self.asset_doc_combo.setCurrentText(current_selection)
                elif doc_id_list:
                    # 默认选择第一个并自动加载
                    self.asset_doc_combo.setCurrentIndex(0)
                    self.refresh_asset_list(doc_id_list[0])
            else:
                self.asset_doc_combo.addItem("No documents with assets")
                self.assets_list.clear()
                logger.info("No assets found. Make sure PDFs have been imported with figure extraction enabled.")
        except Exception as e:
            logger.error(f"Failed to refresh asset doc list: {e}", exc_info=True)
            import traceback
            logger.error(traceback.format_exc())
            self.asset_doc_combo.clear()
            self.asset_doc_combo.addItem(f"Error: {str(e)[:50]}")
    
    def on_asset_doc_changed(self, doc_id: str):
        """当选择的文档改变时"""
        if doc_id and doc_id != "No documents with assets":
            self.refresh_asset_list(doc_id)
    
    def refresh_asset_list(self, doc_id: str = None):
        """刷新资产列表"""
        try:
            if not doc_id:
                doc_id = self.asset_doc_combo.currentText()
            
            if not doc_id or doc_id == "No documents with assets":
                self.assets_list.clear()
                return
            
            # 确保使用正确的数据库路径
            db_path = str(CACHE_PATH)
            temp_db_manager = DatabaseManager(db_path)
            temp_asset_manager = AssetManager(temp_db_manager)
            
            assets = temp_asset_manager.get_assets_by_doc_id(doc_id)
            
            logger.info(f"Found {len(assets)} assets for document: {doc_id}")
            
            self.assets_list.clear()
            if not assets:
                # 如果没有资产，显示提示
                item = QTreeWidgetItem(self.assets_list)
                item.setText(0, "No images")
                item.setText(1, "No images extracted")
                item.setText(2, "-")
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)  # 禁用选择
                return
            
            for asset in assets:
                page_no = asset["page_no"]
                image_path = asset["image_path"]
                asset_id = asset["asset_id"]
                has_note = "✓" if asset.get("teacher_note") else "✗"
                
                # 获取文件名
                image_name = Path(image_path).name
                
                item = QTreeWidgetItem(self.assets_list)
                item.setText(0, f"Page {page_no}")
                item.setText(1, image_name)
                item.setText(2, has_note)
                item.setData(0, Qt.UserRole, asset_id)
                item.setData(0, Qt.UserRole + 1, image_path)
                item.setData(0, Qt.UserRole + 2, asset.get("teacher_note", ""))
            
            logger.info(f"Loaded {len(assets)} assets for document {doc_id}")
        except Exception as e:
            logger.error(f"Failed to refresh asset list: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to load assets: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_asset_selected(self, item: QTreeWidgetItem, column: int):
        """当选择资产时"""
        try:
            asset_id = item.data(0, Qt.UserRole)
            image_path = item.data(0, Qt.UserRole + 1)
            teacher_note = item.data(0, Qt.UserRole + 2) or ""
            
            self.current_asset_id = asset_id
            
            # 显示图片
            if image_path and Path(image_path).exists():
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    # 缩放图片以适应标签
                    scaled_pixmap = pixmap.scaled(
                        self.asset_image_label.width(),
                        self.asset_image_label.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.asset_image_label.setPixmap(scaled_pixmap)
                else:
                    self.asset_image_label.setText("Failed to load image")
            else:
                self.asset_image_label.setText("Image file not found")
            
            # 显示图片信息
            page_no = item.text(0).replace("Page ", "")
            info_text = f"Asset ID: {asset_id}\nPage: {page_no}\nPath: {image_path}"
            self.asset_info_label.setText(info_text)
            
            # 显示现有备注
            self.asset_note_input.setPlainText(teacher_note)
            
            # 启用保存按钮
            self.save_note_button.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Failed to load asset details: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to load asset: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_save_asset_note(self):
        """保存资产备注"""
        try:
            if not self.current_asset_id:
                InfoBar.warning(
                    title="Warning",
                    content="Please select an image first",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            teacher_note = self.asset_note_input.toPlainText().strip()
            
            # 更新数据库
            success = self.asset_manager.update_teacher_note(self.current_asset_id, teacher_note)
            
            if success:
                # 更新向量数据库
                try:
                    from app.core.pdf_vector_db import PDFVectorStore
                    from app.core.rag.embedding import EmbeddingGenerator
                    from app.api.assets_api import upsert_asset_note_embedding
                    
                    asset = self.asset_manager.get_asset_by_id(self.current_asset_id)
                    if asset:
                        asset_dict = {
                            "asset_id": asset.asset_id,
                            "doc_id": asset.doc_id,
                            "page_no": asset.page_no,
                            "teacher_note": asset.teacher_note
                        }
                        upsert_asset_note_embedding(asset_dict, self.vector_store_path)
                    
                    InfoBar.success(
                        title="Success",
                        content="Teacher note saved and embedded successfully!",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    
                    # 刷新列表
                    self.refresh_asset_list()
                    
                except Exception as e:
                    logger.warning(f"Failed to update embedding: {e}", exc_info=True)
                    InfoBar.warning(
                        title="Partial Success",
                        content=f"Note saved but embedding update failed: {str(e)}",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )
            else:
                InfoBar.error(
                    title="Error",
                    content="Failed to save teacher note",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
        except Exception as e:
            logger.error(f"Failed to save asset note: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to save note: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def debug_assets(self):
        """调试：检查资产数据库状态"""
        try:
            db_path = str(CACHE_PATH)
            temp_db_manager = DatabaseManager(db_path)
            
            with temp_db_manager.get_session() as session:
                from app.core.storage.models import Asset
                from sqlalchemy import inspect as sql_inspect
                
                inspector = sql_inspect(temp_db_manager._engine)
                has_table = inspector.has_table("assets")
                
                if has_table:
                    total_assets = session.query(Asset).count()
                    doc_ids = session.query(Asset.doc_id).distinct().all()
                    doc_id_list = [doc_id[0] for doc_id in doc_ids if doc_id[0]]
                    
                    debug_info = (
                        f"Database: {db_path}\n"
                        f"Assets table exists: {has_table}\n"
                        f"Total assets: {total_assets}\n"
                        f"Documents with assets: {len(doc_id_list)}\n"
                        f"Document IDs: {doc_id_list}\n\n"
                    )
                    
                    if doc_id_list:
                        for doc_id in doc_id_list[:5]:  # 只显示前5个
                            assets = session.query(Asset).filter(Asset.doc_id == doc_id).all()
                            debug_info += f"  {doc_id}: {len(assets)} assets\n"
                else:
                    debug_info = f"Assets table does not exist in {db_path}\n\nPlease import a PDF first."
            
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("Asset Database Debug Info")
            msg.setText(debug_info)
            msg.exec_()
            
            # 刷新列表
            self.refresh_asset_doc_list()
        except Exception as e:
            logger.error(f"Debug failed: {e}", exc_info=True)
            import traceback
            InfoBar.error(
                title="Debug Error",
                content=f"{str(e)}\n\n{traceback.format_exc()[:200]}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=10000,
                parent=self
            )
    
    def sync_assets_to_db(self):
        """同步已提取的图片到数据库"""
        try:
            from app.core.pdf_vector_db.sync_assets_to_db import sync_existing_assets_to_db
            
            InfoBar.info(
                title="Syncing",
                content="Scanning assets directory and syncing to database...",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            synced_count = sync_existing_assets_to_db()
            
            if synced_count > 0:
                InfoBar.success(
                    title="Success",
                    content=f"Synced {synced_count} assets to database!",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                # 刷新列表
                self.refresh_asset_doc_list()
            else:
                InfoBar.warning(
                    title="No New Assets",
                    content="No new assets found to sync. All assets may already be in database.",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
        except Exception as e:
            logger.error(f"Failed to sync assets: {e}", exc_info=True)
            InfoBar.error(
                title="Sync Error",
                content=f"Failed to sync assets: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=8000,
                parent=self
            )
    
    def on_delete_selected_asset(self):
        """删除选中的资产"""
        selected_items = self.assets_list.selectedItems()
        if not selected_items:
            InfoBar.warning(
                title="No Selection",
                content="Please select one or more images to delete",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_items)} image(s)?\n\n"
            "This will remove them from the database and delete the image files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        deleted_count = 0
        failed_count = 0
        
        for item in selected_items:
            try:
                asset_id = item.data(0, Qt.UserRole)
                image_path = item.data(0, Qt.UserRole + 1)
                
                if not asset_id:
                    continue
                
                # 从数据库删除
                success = self.asset_manager.delete_asset(asset_id)
                
                if success:
                    # 删除文件
                    if image_path and Path(image_path).exists():
                        try:
                            Path(image_path).unlink()
                            logger.info(f"Deleted image file: {image_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete image file {image_path}: {e}")
                    
                    deleted_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to delete asset: {e}", exc_info=True)
                failed_count += 1
        
        # 刷新列表
        self.refresh_asset_list()
        
        # 清除选择
        selected_asset_ids = [item.data(0, Qt.UserRole) for item in selected_items]
        if self.current_asset_id in selected_asset_ids:
            self.current_asset_id = None
            self.asset_image_label.clear()
            self.asset_image_label.setText("Select an image to preview")
            self.asset_info_label.clear()
            self.asset_note_input.clear()
            self.save_note_button.setEnabled(False)
        
        # 显示结果
        if failed_count == 0:
            InfoBar.success(
                title="Success",
                content=f"Deleted {deleted_count} image(s) successfully!",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.warning(
                title="Partial Success",
                content=f"Deleted {deleted_count} image(s), {failed_count} failed",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )