# -*- coding: utf-8 -*-
"""
Student Q&A Interface
Students can ask questions and get answers, which are automatically saved to the database
"""

import os
from pathlib import Path
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QSplitter, QMessageBox, QFileDialog
)
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, PrimaryPushButton,
    InfoBar, InfoBarPosition, TextEdit, TitleLabel,
    CardWidget
)

from app.config import APPDATA_PATH, CACHE_PATH
from app.thread.pdf_chat_thread import PDFQueryThread, PDFChatThread
from app.core.pdf_vector_db import PDFVectorStore
from app.core.rag.embedding import EmbeddingGenerator
from app.core.storage.database import DatabaseManager
from app.core.storage.qa_record_manager import QARecordManager
from app.common.config import cfg
from app.core.utils.logger import setup_logger
from app.components.pdf_viewer import PDFViewerDialog
from app.common.ui_styles import STUDENT_QA_STYLE, COLORS

logger = setup_logger("StudentQAInterface")


class StudentQAInterface(QWidget):
    """学生问答界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query_thread = None
        self.chat_thread = None
        self.vector_store_path = str(APPDATA_PATH / "pdf_vector_db")
        self.current_query_pages = []
        self.current_answer = ""
        self.current_confidence_score = None
        self.pdf_file_cache = {}  # 缓存PDF文件路径: {pdf_name: pdf_path}
        
        # Initialize database manager
        self.db_manager = DatabaseManager(str(CACHE_PATH))
        self.qa_manager = QARecordManager(self.db_manager)
        
        self.setObjectName("StudentQAInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(STUDENT_QA_STYLE)
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = TitleLabel("🎓 Student Q&A System", self)
        title.setStyleSheet(f"""
            font-size: 28px; 
            font-weight: 700; 
            color: {COLORS['primary']};
            margin-bottom: 8px;
            background: transparent;
        """)
        main_layout.addWidget(title)
        
        # Description
        desc = BodyLabel(
            "Ask questions about PDF documents. Your questions and answers will be automatically saved for teacher review.",
            self
        )
        desc.setStyleSheet(f"""
            font-size: 13px; 
            color: {COLORS['text_secondary']};
            margin-bottom: 20px;
            background: transparent;
        """)
        main_layout.addWidget(desc)
        
        # Create splitter for layout
        splitter = QSplitter(Qt.Horizontal, self)
        
        # Left: Question input and answer display
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Student name input (optional)
        name_group = QGroupBox("👤 Student Information", self)
        name_layout = QHBoxLayout(name_group)
        name_layout.setSpacing(12)
        name_label = BodyLabel("Your Name (Optional):", self)
        name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 500;")
        name_layout.addWidget(name_label)
        self.student_name_input = LineEdit(self)
        self.student_name_input.setPlaceholderText("Enter your name...")
        name_layout.addWidget(self.student_name_input, 1)
        left_layout.addWidget(name_group)
        
        # Question input
        question_group = QGroupBox("💬 Ask Your Question", self)
        question_layout = QVBoxLayout(question_group)
        
        question_layout.addWidget(BodyLabel("Your Question:", self))
        self.question_input = TextEdit(self)
        self.question_input.setPlaceholderText("Enter your question about the PDF documents...")
        self.question_input.setMaximumHeight(100)
        question_layout.addWidget(self.question_input)
        
        # Query button
        query_button_layout = QHBoxLayout()
        query_button_layout.addStretch()
        self.query_button = PrimaryPushButton("🔍 Ask Question", self)
        self.query_button.clicked.connect(self.on_query_clicked)
        query_button_layout.addWidget(self.query_button)
        query_button_layout.addStretch()
        question_layout.addLayout(query_button_layout)
        
        # Status label
        self.status_label = BodyLabel("", self)
        self.status_label.setStyleSheet(f"""
            color: {COLORS['text_tertiary']}; 
            font-size: 12px;
            font-style: italic;
            padding: 4px;
            background: transparent;
        """)
        question_layout.addWidget(self.status_label)
        
        left_layout.addWidget(question_group)
        
        # Answer display
        answer_group = QGroupBox("📝 Answer", self)
        answer_layout = QVBoxLayout(answer_group)
        
        # Related pages info
        self.related_pages_label = BodyLabel("", self)
        self.related_pages_label.setStyleSheet(f"""
            color: {COLORS['primary']}; 
            font-size: 12px; 
            padding: 8px;
            background-color: {COLORS['primary_light']};
            border-radius: 4px;
            border-left: 3px solid {COLORS['primary']};
        """)
        self.related_pages_label.setWordWrap(True)
        self.related_pages_label.hide()
        answer_layout.addWidget(self.related_pages_label)
        
        # Answer text
        answer_label = BodyLabel("AI Answer:", self)
        answer_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 600; margin-top: 8px;")
        answer_layout.addWidget(answer_label)
        self.answer_output = TextEdit(self)
        self.answer_output.setReadOnly(True)
        self.answer_output.setPlaceholderText("Answer will be displayed here...")
        answer_layout.addWidget(self.answer_output)
        
        # Confidence score display
        self.confidence_label = BodyLabel("", self)
        self.confidence_label.setStyleSheet(f"""
            color: {COLORS['primary']}; 
            font-size: 13px; 
            font-weight: 600; 
            padding: 8px;
            background-color: {COLORS['primary_light']};
            border-radius: 6px;
            margin-top: 8px;
        """)
        self.confidence_label.hide()
        answer_layout.addWidget(self.confidence_label)
        
        left_layout.addWidget(answer_group)
        left_layout.addStretch()
        
        splitter.addWidget(left_widget)
        
        # Right: Related pages display
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Related pages
        pages_group = QGroupBox("📄 Related PDF Pages", self)
        pages_layout = QVBoxLayout(pages_group)
        
        pages_layout.addWidget(BodyLabel("Pages used to generate the answer (Click to view):", self))
        self.pages_output = TextEdit(self)
        self.pages_output.setReadOnly(True)
        self.pages_output.setPlaceholderText("Related pages will be displayed here...")
        # 启用HTML格式以支持链接
        self.pages_output.setAcceptRichText(True)
        pages_layout.addWidget(self.pages_output)
        
        # 添加查看PDF按钮
        view_pdf_layout = QHBoxLayout()
        view_pdf_layout.addStretch()
        self.view_pdf_button = PushButton("📖 View PDF Page", self)
        self.view_pdf_button.clicked.connect(self.on_view_pdf_clicked)
        self.view_pdf_button.hide()
        view_pdf_layout.addWidget(self.view_pdf_button)
        pages_layout.addLayout(view_pdf_layout)
        
        right_layout.addWidget(pages_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def on_query_clicked(self):
        """处理查询按钮点击"""
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
        
        # Clear previous results
        self.answer_output.clear()
        self.pages_output.clear()
        self.related_pages_label.hide()
        self.confidence_label.hide()
        self.current_confidence_score = None
        self.status_label.setText("Searching PDF database...")
        self.query_button.setEnabled(False)
        
        # Start query thread
        self.query_thread = PDFQueryThread(
            question=question,
            vector_store_path=self.vector_store_path,
            top_k=5
        )
        self.query_thread.progress.connect(self.on_query_progress)
        self.query_thread.result.connect(self.on_query_result)
        self.query_thread.error.connect(self.on_query_error)
        self.query_thread.start()
    
    def on_query_progress(self, message: str):
        """查询进度更新"""
        self.status_label.setText(message)
    
    def on_query_result(self, pages: list):
        """查询结果处理"""
        self.current_query_pages = pages
        
        if not pages:
            self.status_label.setText("No relevant pages found")
            self.query_button.setEnabled(True)
            InfoBar.warning(
                title="No Results",
                content="No relevant pages found in the PDF database",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # Display related pages with clickable links
        pages_html = "<html><body style='font-family: Arial; font-size: 11px;'>"
        page_info = []
        for i, page in enumerate(pages, 1):
            pdf_name = page.get("pdf_name", "Unknown")
            page_num = page.get("page", 0)
            content = page.get("content", "")[:200] + "..." if len(page.get("content", "")) > 200 else page.get("content", "")
            
            # 创建可点击的链接
            link_text = f"{pdf_name} - Page {page_num}"
            pages_html += f"<p><b>Page {i}:</b> <a href='view:{pdf_name}:{page_num}' style='color: #0078d4; text-decoration: underline;'>{link_text}</a></p>"
            pages_html += f"<p style='color: #666; margin-left: 20px;'>{content}</p>"
            pages_html += "<br>"
            
            page_info.append({
                "pdf_name": pdf_name,
                "page": page_num,
                "content": page.get("content", "")
            })
        
        pages_html += "</body></html>"
        self.pages_output.setHtml(pages_html)
        
        # 连接锚点点击事件
        self.pages_output.anchorClicked.connect(self.on_page_link_clicked)
        
        # 显示查看PDF按钮
        self.view_pdf_button.show()
        
        # Show related pages label
        page_nums = [f"{p.get('pdf_name', 'Unknown')} (Page {p.get('page', 0)})" for p in pages]
        self.related_pages_label.setText(f"📄 Related Pages: {', '.join(page_nums)}")
        self.related_pages_label.show()
        
        # Start chat thread to generate answer
        self.status_label.setText("Generating answer...")
        question = self.question_input.toPlainText().strip()
        llm_service = cfg.get(cfg.llmService).value if hasattr(cfg, 'llmService') else "gemini"
        
        self.chat_thread = PDFChatThread(
            question=question,
            context_pages=page_info,
            llm_service=llm_service
        )
        self.chat_thread.progress.connect(self.on_chat_progress)
        self.chat_thread.result.connect(self.on_chat_result)
        self.chat_thread.error.connect(self.on_chat_error)
        self.chat_thread.start()
    
    def on_query_error(self, error_message: str):
        """查询错误处理"""
        self.status_label.setText("Query failed")
        self.query_button.setEnabled(True)
        InfoBar.error(
            title="Query Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def on_chat_progress(self, message: str):
        """聊天进度更新"""
        self.status_label.setText(message)
    
    def on_chat_result(self, result: dict):
        """聊天结果处理"""
        self.current_answer = result.get("answer", "")
        confidence_score = result.get("confidence_score", None)
        self.current_confidence_score = confidence_score
        
        self.answer_output.setPlainText(self.current_answer)
        
        # Display confidence score
        if confidence_score is not None:
            confidence_text = f"🤔 AI Confidence Score: {confidence_score}/5"
            if confidence_score == 5:
                confidence_text += " (Very High)"
            elif confidence_score == 4:
                confidence_text += " (High)"
            elif confidence_score == 3:
                confidence_text += " (Medium)"
            elif confidence_score == 2:
                confidence_text += " (Low)"
            else:
                confidence_text += " (Very Low)"
            self.confidence_label.setText(confidence_text)
            self.confidence_label.show()
        else:
            self.confidence_label.hide()
        
        self.status_label.setText("Answer generated successfully")
        self.query_button.setEnabled(True)
        
        # Automatically save to database
        self.save_qa_record()
    
    def on_chat_error(self, error_message: str):
        """聊天错误处理"""
        self.status_label.setText("Answer generation failed")
        self.query_button.setEnabled(True)
        InfoBar.error(
            title="Answer Generation Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def save_qa_record(self):
        """保存问答记录到数据库"""
        try:
            question = self.question_input.toPlainText().strip()
            answer = self.current_answer
            student_name = self.student_name_input.text().strip() or None
            
            # Prepare related pages data
            related_pages = []
            for page in self.current_query_pages:
                related_pages.append({
                    "pdf_name": page.get("pdf_name", "Unknown"),
                    "page": page.get("page", 0),
                    "content_preview": page.get("content", "")[:500]  # Store preview only
                })
            
            llm_service = cfg.get(cfg.llmService).value if hasattr(cfg, 'llmService') else "gemini"
            
            record_id = self.qa_manager.save_qa_record(
                question=question,
                answer=answer,
                related_pages=related_pages,
                llm_service=llm_service,
                student_name=student_name,
                confidence_score=self.current_confidence_score
            )
            
            InfoBar.success(
                title="Saved",
                content=f"Your question and answer have been saved (Record ID: {record_id})",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            logger.info(f"Saved Q&A record {record_id} for student {student_name}")
            
        except Exception as e:
            logger.error(f"Failed to save Q&A record: {e}", exc_info=True)
            InfoBar.error(
                title="Save Error",
                content=f"Failed to save Q&A record: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_page_link_clicked(self, url):
        """处理页面链接点击"""
        url_str = url.toString()
        if url_str.startswith("view:"):
            # 解析链接: view:pdf_name:page_num
            parts = url_str.split(":")
            if len(parts) >= 3:
                pdf_name = parts[1]
                try:
                    page_num = int(parts[2])
                    self.view_pdf_page(pdf_name, page_num)
                except ValueError:
                    logger.error(f"Invalid page number: {parts[2]}")
    
    def on_view_pdf_clicked(self):
        """查看PDF按钮点击事件"""
        if not self.current_query_pages:
            InfoBar.warning(
                title="Warning",
                content="No pages to view. Please ask a question first.",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 显示第一个相关页面
        first_page = self.current_query_pages[0]
        pdf_name = first_page.get("pdf_name", "Unknown")
        page_num = first_page.get("page", 1)
        self.view_pdf_page(pdf_name, page_num)
    
    def find_pdf_file(self, pdf_name: str) -> Path:
        """查找PDF文件路径"""
        # 首先检查缓存
        if pdf_name in self.pdf_file_cache:
            cached_path = Path(self.pdf_file_cache[pdf_name])
            if cached_path.exists():
                return cached_path
        
        # 尝试在常见位置查找
        search_paths = [
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            APPDATA_PATH / "pdfs",
            APPDATA_PATH.parent / "pdfs",
        ]
        
        # 尝试不同的文件名变体
        name_variants = [
            f"{pdf_name}.pdf",
            f"{pdf_name}.PDF",
        ]
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            for variant in name_variants:
                pdf_path = search_path / variant
                if pdf_path.exists():
                    self.pdf_file_cache[pdf_name] = str(pdf_path)
                    return pdf_path
        
        return None
    
    def view_pdf_page(self, pdf_name: str, page_num: int):
        """查看PDF的指定页面"""
        # 查找PDF文件
        pdf_path = self.find_pdf_file(pdf_name)
        
        if not pdf_path:
            # 如果找不到，让用户选择文件
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                f"Select PDF file: {pdf_name}",
                str(Path.home()),
                "PDF Files (*.pdf);;All Files (*.*)"
            )
            
            if file_path:
                pdf_path = Path(file_path)
                self.pdf_file_cache[pdf_name] = str(pdf_path)
            else:
                InfoBar.warning(
                    title="File Not Found",
                    content=f"Please select the PDF file: {pdf_name}.pdf",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
        
        # 打开PDF查看器
        try:
            viewer = PDFViewerDialog(self)
            viewer.show_pdf_page(pdf_path, page_num)
        except Exception as e:
            logger.error(f"Failed to open PDF viewer: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to open PDF viewer: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )