# -*- coding: utf-8 -*-
"""
统一UI样式定义
提供现代化的界面样式
"""

# 颜色方案 - 现代蓝色主题
COLORS = {
    # 主色调
    "primary": "#0078d4",  # 微软蓝
    "primary_hover": "#106ebe",
    "primary_light": "#deecf9",
    
    # 背景色
    "bg_primary": "#ffffff",
    "bg_secondary": "#faf9f8",
    "bg_tertiary": "#f3f2f1",
    
    # 文本色
    "text_primary": "#323130",
    "text_secondary": "#605e5c",
    "text_tertiary": "#8a8886",
    "text_disabled": "#c8c6c4",
    
    # 边框色
    "border_light": "#edebe9",
    "border_medium": "#c8c6c4",
    "border_dark": "#8a8886",
    
    # 状态色
    "success": "#107c10",
    "warning": "#ffaa44",
    "error": "#d13438",
    "info": "#0078d4",
    
    # 阴影
    "shadow_light": "rgba(0, 0, 0, 0.05)",
    "shadow_medium": "rgba(0, 0, 0, 0.1)",
    "shadow_dark": "rgba(0, 0, 0, 0.15)",
}

# 全局样式表
GLOBAL_STYLE = f"""
    /* 全局字体 */
    QWidget {{
        font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
        font-size: 13px;
    }}
    
    /* 主窗口背景 */
    QMainWindow, QWidget {{
        background-color: {COLORS['bg_secondary']};
    }}
    
    /* GroupBox样式 */
    QGroupBox {{
        font-weight: 600;
        font-size: 14px;
        color: {COLORS['text_primary']};
        border: 2px solid {COLORS['border_light']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
        background-color: {COLORS['bg_primary']};
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px;
        padding: 0 8px;
        background-color: {COLORS['bg_primary']};
        color: {COLORS['text_primary']};
    }}
    
    /* 卡片样式 */
    CardWidget {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 8px;
        padding: 16px;
    }}
    
    /* 输入框样式 */
    LineEdit, TextEdit, QTextEdit {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 13px;
        color: {COLORS['text_primary']};
    }}
    
    LineEdit:focus, TextEdit:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['primary']};
        background-color: {COLORS['bg_primary']};
    }}
    
    LineEdit:hover, TextEdit:hover, QTextEdit:hover {{
        border: 1px solid {COLORS['border_medium']};
    }}
    
    /* 按钮样式 */
    PushButton {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_medium']};
        border-radius: 4px;
        padding: 8px 16px;
        color: {COLORS['text_primary']};
        font-weight: 500;
        min-height: 32px;
    }}
    
    PushButton:hover {{
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['primary']};
        color: {COLORS['primary']};
    }}
    
    PushButton:pressed {{
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['primary_hover']};
    }}
    
    PrimaryPushButton {{
        background-color: {COLORS['primary']};
        border: none;
        border-radius: 4px;
        padding: 8px 20px;
        color: white;
        font-weight: 600;
        min-height: 36px;
    }}
    
    PrimaryPushButton:hover {{
        background-color: {COLORS['primary_hover']};
    }}
    
    PrimaryPushButton:pressed {{
        background-color: #005a9e;
    }}
    
    /* 标签样式 */
    TitleLabel {{
        font-size: 24px;
        font-weight: 700;
        color: {COLORS['text_primary']};
        letter-spacing: -0.5px;
    }}
    
    BodyLabel {{
        font-size: 13px;
        color: {COLORS['text_secondary']};
        line-height: 1.5;
    }}
    
    /* 分割线 */
    QSplitter::handle {{
        background-color: {COLORS['border_light']};
        width: 1px;
    }}
    
    QSplitter::handle:hover {{
        background-color: {COLORS['primary']};
        width: 2px;
    }}
    
    /* 滚动条 */
    QScrollBar:vertical {{
        background-color: {COLORS['bg_secondary']};
        width: 12px;
        border: none;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {COLORS['border_medium']};
        border-radius: 6px;
        min-height: 30px;
        margin: 2px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS['border_dark']};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    /* 树形控件 */
    QTreeWidget {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 4px;
        selection-background-color: {COLORS['primary_light']};
        selection-color: {COLORS['primary']};
    }}
    
    QTreeWidget::item {{
        padding: 4px;
        border-radius: 4px;
    }}
    
    QTreeWidget::item:hover {{
        background-color: {COLORS['bg_tertiary']};
    }}
    
    QTreeWidget::item:selected {{
        background-color: {COLORS['primary_light']};
        color: {COLORS['primary']};
    }}
"""

# 学生问答界面专用样式
STUDENT_QA_STYLE = f"""
    StudentQAInterface {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLORS['bg_secondary']}, stop:1 {COLORS['bg_primary']});
    }}
    
    StudentQAInterface QGroupBox {{
        background-color: {COLORS['bg_primary']};
        border: 2px solid {COLORS['border_light']};
        border-radius: 12px;
        padding: 20px;
        margin-top: 16px;
    }}
    
    StudentQAInterface QGroupBox::title {{
        font-size: 15px;
        font-weight: 600;
        color: {COLORS['primary']};
        padding: 0 10px;
    }}
    
    StudentQAInterface TextEdit, StudentQAInterface QTextEdit {{
        background-color: {COLORS['bg_primary']};
        border: 2px solid {COLORS['border_light']};
        border-radius: 6px;
        padding: 12px;
        font-size: 13px;
        line-height: 1.6;
    }}
    
    StudentQAInterface TextEdit:focus, StudentQAInterface QTextEdit:focus {{
        border: 2px solid {COLORS['primary']};
        background-color: {COLORS['bg_primary']};
    }}
    
    StudentQAInterface PrimaryPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_hover']});
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 14px;
        font-weight: 600;
        min-height: 40px;
    }}
    
    StudentQAInterface PrimaryPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLORS['primary_hover']}, stop:1 #005a9e);
        transform: translateY(-1px);
    }}
"""

# Dashboard界面专用样式
DASHBOARD_STYLE = f"""
    DashboardInterface {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #f5f7fa, stop:1 #c3cfe2);
    }}
    
    DashboardInterface TitleLabel {{
        background: transparent;
        color: {COLORS['text_primary']};
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -1px;
        margin-bottom: 10px;
    }}
"""

# 功能卡片样式
FUNCTION_CARD_STYLE = f"""
    FunctionCard {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 12px;
        padding: 20px;
    }}
    
    FunctionCard:hover {{
        background-color: {COLORS['bg_primary']};
        border: 2px solid {COLORS['primary']};
        transform: translateY(-2px);
    }}
    
    FunctionCard QLabel {{
        background: transparent;
    }}
"""

# 教师批阅界面样式
TEACHER_REVIEW_STYLE = f"""
    TeacherReviewInterface {{
        background-color: {COLORS['bg_secondary']};
    }}
    
    TeacherReviewInterface QGroupBox {{
        background-color: {COLORS['bg_primary']};
        border: 2px solid {COLORS['border_light']};
        border-radius: 10px;
        padding: 16px;
    }}
    
    TeacherReviewInterface QTableWidget {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
        gridline-color: {COLORS['border_light']};
        selection-background-color: {COLORS['primary_light']};
        selection-color: {COLORS['primary']};
    }}
    
    TeacherReviewInterface QTableWidget::item {{
        padding: 8px;
        border: none;
    }}
    
    TeacherReviewInterface QTableWidget::item:selected {{
        background-color: {COLORS['primary_light']};
        color: {COLORS['primary']};
    }}
    
    TeacherReviewInterface QHeaderView::section {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_primary']};
        font-weight: 600;
        padding: 10px;
        border: none;
        border-bottom: 2px solid {COLORS['border_light']};
    }}
"""

# PDF向量数据库界面样式
PDF_VECTOR_DB_STYLE = f"""
    PDFVectorDBInterface {{
        background-color: {COLORS['bg_secondary']};
    }}
    
    PDFVectorDBInterface QGroupBox {{
        background-color: {COLORS['bg_primary']};
        border: 2px solid {COLORS['border_light']};
        border-radius: 10px;
        padding: 16px;
    }}
    
    PDFVectorDBInterface QTreeWidget {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
    }}
"""
