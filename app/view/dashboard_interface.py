from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon as FIF,
    IconWidget,
    ScrollArea,
    TitleLabel,
)

from app.common.ui_styles import DASHBOARD_STYLE, FUNCTION_CARD_STYLE, COLORS

# Interface imports are not needed here, only for reference


class FunctionCard(CardWidget):
    """功能卡片组件"""
    clicked = pyqtSignal()

    def __init__(self, icon, title, description, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 180)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 图标
        icon_widget = IconWidget(icon, self)
        icon_widget.setFixedSize(56, 56)
        icon_widget.setStyleSheet(
            f"""
            IconWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['primary_light']}, stop:1 {COLORS['primary']});
                border-radius: 28px;
                padding: 8px;
            }}
            """
        )

        # 标题
        title_label = QLabel(title, self)
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLORS['text_primary']}; margin-top: 4px;")
        
        # 描述
        desc_label = QLabel(description, self)
        desc_font = QFont()
        desc_font.setPointSize(12)
        desc_label.setFont(desc_font)
        desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; line-height: 1.5;")
        desc_label.setWordWrap(True)

        layout.addWidget(icon_widget, 0, Qt.AlignHCenter)
        layout.addWidget(title_label, 0, Qt.AlignHCenter)
        layout.addWidget(desc_label)
        layout.addStretch()

        # 鼠标悬停效果
        self.setStyleSheet(
            f"""
            FunctionCard {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
            FunctionCard:hover {{
                background-color: {COLORS['bg_primary']};
                border: 2px solid {COLORS['primary']};
                box-shadow: 0 4px 12px {COLORS['shadow_medium']};
            }}
            """
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DashboardInterface(ScrollArea):
    """主界面 - 功能集合区"""

    # 信号：请求切换到某个界面
    switchToInterface = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardInterface")
        self.setStyleSheet(DASHBOARD_STYLE)
        self.setupUI()

    def setupUI(self):
        """设置UI"""
        # 创建滚动内容
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(30)

        # 标题
        title_label = TitleLabel("✨ 功能中心", self)
        title_label.setStyleSheet(f"""
            font-size: 36px; 
            font-weight: 700; 
            color: {COLORS['text_primary']};
            margin-bottom: 8px;
            background: transparent;
            letter-spacing: -1px;
        """)
        scroll_layout.addWidget(title_label)
        
        # 副标题
        subtitle = BodyLabel("选择下方功能模块开始使用", self)
        subtitle.setStyleSheet(f"""
            font-size: 14px; 
            color: {COLORS['text_secondary']};
            margin-bottom: 30px;
            background: transparent;
        """)
        scroll_layout.addWidget(subtitle)

        # 功能卡片网格
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)
        cards_layout.setContentsMargins(0, 0, 0, 0)

        # 定义所有功能模块
        functions = [
            {
                "icon": FIF.HOME,
                "title": "主页",
                "description": "任务创建、PDF转录、语音转录、字幕优化、视频合成",
                "interface": "home",
            },
            {
                "icon": FIF.VIDEO,
                "title": "批量处理",
                "description": "批量处理视频文件，提高工作效率",
                "interface": "batch_process",
            },
            {
                "icon": FIF.FONT,
                "title": "字幕样式",
                "description": "自定义字幕样式和显示效果",
                "interface": "subtitle_style",
            },
            {
                "icon": FIF.MOVIE,
                "title": "智能视频",
                "description": "智能视频处理和编辑功能",
                "interface": "intelligent_video",
            },
            {
                "icon": FIF.PEOPLE,
                "title": "虚拟人视频",
                "description": "创建虚拟人视频内容",
                "interface": "avatar_video",
            },
            {
                "icon": FIF.DOCUMENT,
                "title": "PDF向量数据库",
                "description": "PDF文档向量化、图片提取、知识库管理",
                "interface": "pdf_vector_db",
            },
            {
                "icon": FIF.CHAT,
                "title": "学生问答",
                "description": "学生提问，AI智能回答",
                "interface": "student_qa",
            },
            {
                "icon": FIF.EDIT,
                "title": "教师批阅",
                "description": "教师查看和批阅学生问答记录",
                "interface": "teacher_review",
            },
            {
                "icon": FIF.SETTING,
                "title": "系统设置",
                "description": "系统配置和参数设置",
                "interface": "setting",
            },
        ]

        # 创建功能卡片
        row = 0
        col = 0
        max_cols = 3

        for func in functions:
            card = FunctionCard(
                func["icon"], func["title"], func["description"], self
            )
            # 连接点击信号 - 使用functools.partial避免闭包问题
            interface_name = func["interface"]
            card.clicked.connect(
                lambda checked=False, name=interface_name: self.onCardClicked(name)
            )
            cards_layout.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        scroll_layout.addLayout(cards_layout)
        scroll_layout.addStretch()

        # 设置滚动区域
        self.setWidget(scroll_widget)
        self.setWidgetResizable(True)

    def onCardClicked(self, interface_name: str):
        """卡片点击事件处理"""
        self.switchToInterface.emit(interface_name)
