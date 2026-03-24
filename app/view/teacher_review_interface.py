# -*- coding: utf-8 -*-
"""
Teacher Review Interface
Teachers can view, review, and edit student Q&A records
"""

from datetime import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QSplitter
)
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, PrimaryPushButton,
    InfoBar, InfoBarPosition, TextEdit, TitleLabel,
    ComboBox, CardWidget
)

from app.config import CACHE_PATH
from app.core.storage.database import DatabaseManager
from app.core.storage.qa_record_manager import QARecordManager
from app.core.storage.models import QARecord
from app.core.utils.logger import setup_logger
from app.common.ui_styles import TEACHER_REVIEW_STYLE, COLORS

logger = setup_logger("TeacherReviewInterface")


class TeacherReviewInterface(QWidget):
    """老师审核界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize database manager
        self.db_manager = DatabaseManager(str(CACHE_PATH))
        self.qa_manager = QARecordManager(self.db_manager)
        
        self.current_record = None
        self.current_record_id = None
        
        self.setObjectName("TeacherReviewInterface")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(TEACHER_REVIEW_STYLE)
        
        self.setup_ui()
        self.load_records()
        
        # Auto-refresh every 30 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_records)
        self.refresh_timer.start(30000)  # 30 seconds
    
    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = TitleLabel("👨‍🏫 Teacher Review System", self)
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
            "Review and edit student Q&A records. You can modify answers and mark records as reviewed.",
            self
        )
        desc.setStyleSheet(f"""
            font-size: 13px; 
            color: {COLORS['text_secondary']};
            margin-bottom: 20px;
            background: transparent;
        """)
        main_layout.addWidget(desc)
        
        # Statistics card
        stats_card = CardWidget(self)
        stats_layout = QHBoxLayout(stats_card)
        self.total_label = BodyLabel("Total: 0", self)
        self.reviewed_label = BodyLabel("Reviewed: 0", self)
        self.unreviewed_label = BodyLabel("Unreviewed: 0", self)
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.reviewed_label)
        stats_layout.addWidget(self.unreviewed_label)
        stats_layout.addStretch()
        
        refresh_button = PushButton("🔄 Refresh", self)
        refresh_button.clicked.connect(self.load_records)
        stats_layout.addWidget(refresh_button)
        
        main_layout.addWidget(stats_card)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal, self)
        
        # Left: Records table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Filter group
        filter_group = QGroupBox("Filter", self)
        filter_layout = QHBoxLayout(filter_group)
        
        filter_layout.addWidget(BodyLabel("Status:", self))
        self.filter_combo = ComboBox(self)
        self.filter_combo.addItems(["All", "Unreviewed", "Reviewed"])
        self.filter_combo.currentTextChanged.connect(self.load_records)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        left_layout.addWidget(filter_group)
        
        # Records table
        table_group = QGroupBox("Q&A Records", self)
        table_layout = QVBoxLayout(table_group)
        
        self.records_table = QTableWidget(self)
        self.records_table.setColumnCount(7)
        self.records_table.setHorizontalHeaderLabels([
            "ID", "Student", "Question", "Confidence", "Created", "Status", "Reviewed By"
        ])
        self.records_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.records_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.records_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.records_table.itemSelectionChanged.connect(self.on_record_selected)
        self.records_table.setColumnWidth(0, 50)
        self.records_table.setColumnWidth(1, 100)
        self.records_table.setColumnWidth(2, 250)
        self.records_table.setColumnWidth(3, 80)
        self.records_table.setColumnWidth(4, 150)
        self.records_table.setColumnWidth(5, 80)
        self.records_table.setColumnWidth(6, 120)
        
        header = self.records_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        table_layout.addWidget(self.records_table)
        left_layout.addWidget(table_group)
        
        splitter.addWidget(left_widget)
        
        # Right: Record details and edit
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Record details
        details_group = QGroupBox("Record Details", self)
        details_layout = QVBoxLayout(details_group)
        
        # Student name
        student_layout = QHBoxLayout()
        student_layout.addWidget(BodyLabel("Student:", self))
        self.student_name_label = BodyLabel("", self)
        self.student_name_label.setStyleSheet("font-weight: bold;")
        student_layout.addWidget(self.student_name_label)
        student_layout.addStretch()
        details_layout.addLayout(student_layout)
        
        # Confidence score label
        self.confidence_display_label = BodyLabel("", self)
        self.confidence_display_label.setStyleSheet("color: #4a90e2; font-size: 12px; font-weight: bold; padding: 5px;")
        self.confidence_display_label.hide()
        details_layout.addWidget(self.confidence_display_label)
        
        # Question
        details_layout.addWidget(BodyLabel("Question:", self))
        self.question_display = TextEdit(self)
        self.question_display.setReadOnly(True)
        self.question_display.setMaximumHeight(100)
        details_layout.addWidget(self.question_display)
        
        # Related pages
        details_layout.addWidget(BodyLabel("Related Pages:", self))
        self.pages_display = TextEdit(self)
        self.pages_display.setReadOnly(True)
        self.pages_display.setMaximumHeight(100)
        details_layout.addWidget(self.pages_display)
        
        # Original answer
        details_layout.addWidget(BodyLabel("Original AI Answer:", self))
        self.original_answer_display = TextEdit(self)
        self.original_answer_display.setReadOnly(True)
        self.original_answer_display.setMaximumHeight(150)
        details_layout.addWidget(self.original_answer_display)
        
        right_layout.addWidget(details_group)
        
        # Edit answer
        edit_group = QGroupBox("Edit Answer", self)
        edit_layout = QVBoxLayout(edit_group)
        
        # Teacher name input
        teacher_layout = QHBoxLayout()
        teacher_layout.addWidget(BodyLabel("Your Name:", self))
        self.teacher_name_input = LineEdit(self)
        self.teacher_name_input.setPlaceholderText("Enter your name...")
        teacher_layout.addWidget(self.teacher_name_input)
        edit_layout.addLayout(teacher_layout)
        
        # Teacher answer
        edit_layout.addWidget(BodyLabel("Your Answer (Edit if needed):", self))
        self.teacher_answer_input = TextEdit(self)
        self.teacher_answer_input.setPlaceholderText("Enter or edit the answer...")
        edit_layout.addWidget(self.teacher_answer_input)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_button = PrimaryPushButton("💾 Save Answer", self)
        self.save_button.clicked.connect(self.on_save_answer)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
        
        self.delete_button = PushButton("🗑️ Delete Record", self)
        self.delete_button.clicked.connect(self.on_delete_record)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        button_layout.addStretch()
        edit_layout.addLayout(button_layout)
        
        right_layout.addWidget(edit_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def load_records(self):
        """加载问答记录"""
        try:
            filter_text = self.filter_combo.currentText()
            reviewed_only = None
            if filter_text == "Reviewed":
                reviewed_only = True
            elif filter_text == "Unreviewed":
                reviewed_only = False
            
            records = self.qa_manager.get_all_records(reviewed_only=reviewed_only)
            
            # Update statistics
            stats = self.qa_manager.get_statistics()
            self.total_label.setText(f"Total: {stats['total']}")
            self.reviewed_label.setText(f"Reviewed: {stats['reviewed']}")
            self.unreviewed_label.setText(f"Unreviewed: {stats['unreviewed']}")
            
            # Populate table
            self.records_table.setRowCount(len(records))
            for row, record in enumerate(records):
                # ID
                record_id = record.get('id')
                id_item = QTableWidgetItem(str(record_id))
                id_item.setData(Qt.UserRole, record_id)
                self.records_table.setItem(row, 0, id_item)
                
                # Student name
                student_name = record.get('student_name') or "Unknown"
                self.records_table.setItem(row, 1, QTableWidgetItem(student_name))
                
                # Question (truncated)
                question = record.get('question', '')
                question_text = question[:50] + "..." if len(question) > 50 else question
                self.records_table.setItem(row, 2, QTableWidgetItem(question_text))
                
                # Confidence score
                confidence_score = record.get('confidence_score')
                if confidence_score is not None:
                    confidence_text = f"{confidence_score}/5"
                    confidence_item = QTableWidgetItem(confidence_text)
                    # Color coding based on confidence
                    if confidence_score >= 4:
                        confidence_item.setForeground(Qt.darkGreen)
                    elif confidence_score >= 3:
                        confidence_item.setForeground(Qt.darkYellow)
                    else:
                        confidence_item.setForeground(Qt.darkRed)
                    self.records_table.setItem(row, 3, confidence_item)
                else:
                    self.records_table.setItem(row, 3, QTableWidgetItem("-"))
                
                # Created date
                created_at = record.get('created_at')
                created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
                self.records_table.setItem(row, 4, QTableWidgetItem(created_str))
                
                # Status
                is_reviewed = record.get('is_reviewed', 0)
                status = "✓ Reviewed" if is_reviewed else "○ Unreviewed"
                status_item = QTableWidgetItem(status)
                if is_reviewed:
                    status_item.setForeground(Qt.darkGreen)
                else:
                    status_item.setForeground(Qt.darkRed)
                self.records_table.setItem(row, 5, status_item)
                
                # Reviewed by
                reviewed_by = record.get('reviewed_by') or "-"
                self.records_table.setItem(row, 6, QTableWidgetItem(reviewed_by))
            
            logger.info(f"Loaded {len(records)} Q&A records")
            
        except Exception as e:
            logger.error(f"Failed to load records: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to load records: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_record_selected(self):
        """处理记录选择"""
        selected_items = self.records_table.selectedItems()
        if not selected_items:
            return
        
        # Get record ID from first column
        row = selected_items[0].row()
        id_item = self.records_table.item(row, 0)
        if not id_item:
            return
        
        record_id = id_item.data(Qt.UserRole)
        if not record_id:
            return
        
        try:
            # 使用字典方法获取记录，避免会话绑定问题
            record = self.qa_manager.get_record_dict_by_id(record_id)
            if not record:
                InfoBar.warning(
                    title="Warning",
                    content="Record not found",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            self.current_record = record
            self.current_record_id = record_id
            
            # Display record details
            self.student_name_label.setText(record.get('student_name') or "Unknown")
            self.question_display.setPlainText(record.get('question', ''))
            
            # Display confidence score
            confidence_score = record.get('confidence_score')
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
                self.confidence_display_label.setText(confidence_text)
                self.confidence_display_label.show()
            else:
                self.confidence_display_label.hide()
            
            # Display related pages
            related_pages = record.get('related_pages')
            if related_pages:
                pages_text = ""
                for page in related_pages:
                    pdf_name = page.get("pdf_name", "Unknown")
                    page_num = page.get("page", 0)
                    pages_text += f"{pdf_name} - Page {page_num}\n"
                self.pages_display.setPlainText(pages_text)
            else:
                self.pages_display.setPlainText("No related pages")
            
            # Display original answer
            answer = record.get('answer', '')
            self.original_answer_display.setPlainText(answer)
            
            # Display teacher answer if exists, otherwise use original answer
            teacher_answer = record.get('teacher_answer')
            if teacher_answer:
                self.teacher_answer_input.setPlainText(teacher_answer)
            else:
                self.teacher_answer_input.setPlainText(answer)
            
            # Enable buttons
            self.save_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Failed to load record details: {e}", exc_info=True)
            InfoBar.error(
                title="Error",
                content=f"Failed to load record details: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_save_answer(self):
        """保存老师修改的答案"""
        if not self.current_record_id:
            return
        
        teacher_name = self.teacher_name_input.text().strip()
        if not teacher_name:
            InfoBar.warning(
                title="Warning",
                content="Please enter your name",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        teacher_answer = self.teacher_answer_input.toPlainText().strip()
        if not teacher_answer:
            InfoBar.warning(
                title="Warning",
                content="Please enter an answer",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        try:
            # 验证记录ID
            if not self.current_record_id:
                InfoBar.warning(
                    title="Warning",
                    content="No record selected",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return
            
            logger.info(f"Attempting to save answer for record {self.current_record_id} by {teacher_name}")
            
            success = self.qa_manager.update_teacher_answer(
                record_id=self.current_record_id,
                teacher_answer=teacher_answer,
                reviewed_by=teacher_name
            )
            
            if success:
                logger.info(f"Successfully saved answer for record {self.current_record_id}")
                InfoBar.success(
                    title="Success",
                    content="Answer saved successfully",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                # 刷新记录列表
                self.load_records()
                # Clear selection and reset UI
                self.records_table.clearSelection()
                self.question_display.clear()
                self.pages_display.clear()
                self.original_answer_display.clear()
                self.teacher_answer_input.clear()
                self.student_name_label.setText("")
                self.teacher_name_input.clear()
                self.save_button.setEnabled(False)
                self.delete_button.setEnabled(False)
                self.current_record = None
                self.current_record_id = None
            else:
                logger.warning(f"Failed to save answer for record {self.current_record_id} - record not found")
                InfoBar.error(
                    title="Error",
                    content="Failed to save answer: Record not found",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                
        except Exception as e:
            logger.error(f"Failed to save answer: {e}", exc_info=True)
            error_msg = str(e)
            # 提供更友好的错误信息
            if "no such table" in error_msg.lower():
                error_msg = "Database table not found. Please restart the application."
            elif "database is locked" in error_msg.lower():
                error_msg = "Database is locked. Please try again."
            
            InfoBar.error(
                title="Error",
                content=f"Failed to save answer: {error_msg}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
    
    def on_delete_record(self):
        """删除记录"""
        if not self.current_record_id:
            return
        
        reply = QMessageBox.warning(
            self,
            "Delete Record",
            f"Are you sure you want to delete record #{self.current_record_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success = self.qa_manager.delete_record(self.current_record_id)
                
                if success:
                    InfoBar.success(
                        title="Success",
                        content="Record deleted successfully",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
                    self.load_records()
                    # Clear selection and details
                    self.records_table.clearSelection()
                    self.question_display.clear()
                    self.pages_display.clear()
                    self.original_answer_display.clear()
                    self.teacher_answer_input.clear()
                    self.student_name_label.setText("")
                    self.save_button.setEnabled(False)
                    self.delete_button.setEnabled(False)
                    self.current_record = None
                    self.current_record_id = None
                else:
                    InfoBar.error(
                        title="Error",
                        content="Failed to delete record",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )
                    
            except Exception as e:
                logger.error(f"Failed to delete record: {e}", exc_info=True)
                InfoBar.error(
                    title="Error",
                    content=f"Failed to delete record: {str(e)}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
