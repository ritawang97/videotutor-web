# -*- coding: utf-8 -*-
"""
PDF Viewer Component
用于显示PDF页面的组件
"""

from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QDialog, QMessageBox
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton, TitleLabel, BodyLabel,
    InfoBar, InfoBarPosition
)

from app.core.utils.logger import setup_logger

logger = setup_logger("PDFViewer")

# 尝试导入PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None


class PDFViewerWidget(QWidget):
    """PDF查看器组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_path = None
        self.pdf_doc = None
        self.current_page = 0
        self.total_pages = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 控制栏
        control_layout = QHBoxLayout()
        
        self.prev_button = PushButton("◀ Previous", self)
        self.prev_button.clicked.connect(self.previous_page)
        control_layout.addWidget(self.prev_button)
        
        self.page_label = BodyLabel("Page 0 / 0", self)
        self.page_label.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.page_label)
        
        self.next_button = PushButton("Next ▶", self)
        self.next_button.clicked.connect(self.next_page)
        control_layout.addWidget(self.next_button)
        
        control_layout.addStretch()
        
        self.jump_button = PushButton("Jump to Page", self)
        self.jump_button.clicked.connect(self.jump_to_page)
        control_layout.addWidget(self.jump_button)
        
        layout.addLayout(control_layout)
        
        # PDF页面显示区域
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 800)
        self.image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        
        scroll_area.setWidget(self.image_label)
        layout.addWidget(scroll_area)
        
        self.update_buttons()
    
    def load_pdf(self, pdf_path: Path, page_num: int = 1):
        """加载PDF文件并显示指定页面"""
        try:
            if not PYMUPDF_AVAILABLE:
                raise ImportError("PyMuPDF is not installed. Please install it with: pip install pymupdf")
            
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            self.pdf_path = pdf_path
            
            # 打开PDF
            if self.pdf_doc:
                self.pdf_doc.close()
            
            self.pdf_doc = fitz.open(str(pdf_path))
            self.total_pages = len(self.pdf_doc)
            self.current_page = max(0, min(page_num - 1, self.total_pages - 1))  # 转换为0-based索引
            
            self.display_page(self.current_page)
            self.update_buttons()
            
            logger.info(f"Loaded PDF: {pdf_path.name}, Total pages: {self.total_pages}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load PDF: {e}", exc_info=True)
            self.image_label.setText(f"Error loading PDF: {str(e)}")
            return False
    
    def display_page(self, page_index: int):
        """显示指定页面"""
        if not self.pdf_doc or page_index < 0 or page_index >= self.total_pages:
            return
        
        try:
            page = self.pdf_doc[page_index]
            
            # 渲染页面为图片（放大2倍以提高清晰度）
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为QImage
            img_data = pix.tobytes("ppm")
            qimage = QImage.fromData(img_data)
            
            # 转换为QPixmap并显示
            pixmap = QPixmap.fromImage(qimage)
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            
            self.current_page = page_index
            self.page_label.setText(f"Page {page_index + 1} / {self.total_pages}")
            self.update_buttons()
            
        except Exception as e:
            logger.error(f"Failed to display page {page_index}: {e}", exc_info=True)
            self.image_label.setText(f"Error displaying page: {str(e)}")
    
    def previous_page(self):
        """上一页"""
        if self.current_page > 0:
            self.display_page(self.current_page - 1)
    
    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self.display_page(self.current_page + 1)
    
    def jump_to_page(self):
        """跳转到指定页面"""
        from PyQt5.QtWidgets import QInputDialog
        
        page_num, ok = QInputDialog.getInt(
            self, "Jump to Page", 
            f"Enter page number (1-{self.total_pages}):",
            self.current_page + 1, 1, self.total_pages, 1
        )
        
        if ok:
            self.display_page(page_num - 1)
    
    def update_buttons(self):
        """更新按钮状态"""
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < self.total_pages - 1)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.pdf_doc:
            self.pdf_doc.close()
        super().closeEvent(event)


class PDFViewerDialog(QDialog):
    """PDF查看器对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Viewer")
        self.setMinimumSize(800, 900)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title_label = TitleLabel("PDF Viewer", self)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        close_button = PushButton("Close", self)
        close_button.clicked.connect(self.close)
        title_layout.addWidget(close_button)
        
        layout.addLayout(title_layout)
        
        # PDF查看器
        self.viewer = PDFViewerWidget(self)
        layout.addWidget(self.viewer)
    
    def show_pdf_page(self, pdf_path: Path, page_num: int = 1):
        """显示PDF的指定页面"""
        if self.viewer.load_pdf(pdf_path, page_num):
            self.exec_()
        else:
            QMessageBox.warning(
                self, "Error", 
                f"Failed to load PDF: {pdf_path}\n\nPlease make sure the PDF file exists."
            )
