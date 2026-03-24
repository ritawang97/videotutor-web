from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFontDatabase
from PyQt5.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ImageLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PushSettingCard,
    ScrollArea,
    SettingCardGroup,
)
from qfluentwidgets import FluentIcon as FIF

from app.common.config import cfg
from app.common.signal_bus import signalBus
from app.components.MySettingCard import (
    ColorSettingCard,
    ComboBoxSettingCard,
    DoubleSpinBoxSettingCard,
    SpinBoxSettingCard,
)
from app.config import ASSETS_PATH, SUBTITLE_STYLE_PATH
from app.core.utils.platform_utils import open_folder
from app.core.utils.subtitle_preview import generate_preview

PERVIEW_TEXTS = {
    "Long Text": (
        "This is a long text used for testing subtitle preview and style settings.",
        "这是一段用于测试字幕预览和样式设置的Long Text内容",
    ),
    "Medium Text": (
        "Welcome to apply for the prestigious South China Normal University!",
        "Welcome to apply for the prestigious South China Normal University",
    ),
    "Short Text": ("Elementary school students know this", "Elementary school students know this"),
}

DEFAULT_BG_LANDSCAPE = {
    "path": ASSETS_PATH / "default_bg_landscape.png",
    "width": 1280,
    "height": 720,
}
DEFAULT_BG_PORTRAIT = {
    "path": ASSETS_PATH / "default_bg_portrait.png",
    "width": 480,
    "height": 852,
}


class PreviewThread(QThread):
    previewReady = pyqtSignal(str)

    def __init__(
        self,
        style_str: str,
        preview_text: Tuple[str, Optional[str]],
        bg_path: str,
        width: int,
        height: int,
    ):
        """
        Args:
            style_str: ASS style string
            preview_text: Preview text tuple (main subtitle, sub subtitle), sub subtitle is optional
        """
        super().__init__()
        self.style_str = style_str
        self.preview_text = preview_text
        self.bg_path = bg_path
        self.width = width
        self.height = height

    def run(self):
        preview_path = generate_preview(
            style_str=self.style_str,
            preview_text=self.preview_text,
            bg_path=self.bg_path,
            width=self.width,
            height=self.height,
        )
        self.previewReady.emit(preview_path)


class SubtitleStyleInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SubtitleStyleInterface")
        self.setWindowTitle(self.tr("Subtitle Style Configuration"))

        # Create main layout
        self.hBoxLayout = QHBoxLayout(self)

        # Initialize interface components
        self._initSettingsArea()
        self._initPreviewArea()
        self._initSettingCards()
        self._initLayout()
        self._initStyle()

        # Add a flag to control whether to trigger onSettingChanged
        self._loading_style = False

        # Set initial values, load style
        self.__setValues()

        # Connect signals
        self.connectSignals()

    def _initSettingsArea(self):
        """Initialize left settings area"""
        self.settingsScrollArea = ScrollArea()
        self.settingsScrollArea.setFixedWidth(350)
        self.settingsWidget = QWidget()
        self.settingsLayout = QVBoxLayout(self.settingsWidget)
        self.settingsScrollArea.setWidget(self.settingsWidget)
        self.settingsScrollArea.setWidgetResizable(True)

        # Create setting groups
        self.layoutGroup = SettingCardGroup(self.tr("Subtitle Layout"), self.settingsWidget)
        self.mainGroup = SettingCardGroup(self.tr("Main subtitle style"), self.settingsWidget)
        self.subGroup = SettingCardGroup(self.tr("Sub subtitle style"), self.settingsWidget)
        self.previewGroup = SettingCardGroup(self.tr("Preview settings"), self.settingsWidget)

    def _initPreviewArea(self):
        """初始化右侧Preview area"""
        self.previewCard = CardWidget()
        self.previewLayout = QVBoxLayout(self.previewCard)
        self.previewLayout.setSpacing(16)

        # 顶部Preview area
        self.previewTopWidget = QWidget()
        self.previewTopWidget.setFixedHeight(430)
        self.previewTopLayout = QVBoxLayout(self.previewTopWidget)

        self.previewLabel = BodyLabel(self.tr("Preview Effect"))
        self.previewImage = ImageLabel()
        self.previewImage.setAlignment(Qt.AlignCenter)  # type: ignore
        self.previewTopLayout.addWidget(self.previewImage, 0, Qt.AlignCenter)  # type: ignore
        self.previewTopLayout.setAlignment(Qt.AlignVCenter)  # type: ignore

        # Bottom control area
        self.previewBottomWidget = QWidget()
        self.previewBottomLayout = QVBoxLayout(self.previewBottomWidget)

        self.styleNameComboBox = ComboBoxSettingCard(
            FIF.VIEW,  # type: ignore
            self.tr("Select Style"),
            self.tr("Select saved subtitle style"),
            texts=[],  # type: ignore
        )

        self.newStyleButton = PushSettingCard(
            self.tr("New Style"),
            FIF.ADD,
            self.tr("New Style"),
            self.tr("Create new preset based on current style"),
        )

        self.openStyleFolderButton = PushSettingCard(
            self.tr("Open Style Folder"),
            FIF.FOLDER,
            self.tr("Open Style Folder"),
            self.tr("Open style folder in file manager"),
        )

        self.previewBottomLayout.addWidget(self.styleNameComboBox)
        self.previewBottomLayout.addWidget(self.newStyleButton)
        self.previewBottomLayout.addWidget(self.openStyleFolderButton)

        self.previewLayout.addWidget(self.previewTopWidget)
        self.previewLayout.addWidget(self.previewBottomWidget)
        self.previewLayout.addStretch(1)

    def _initSettingCards(self):
        """Initialize all setting cards"""
        # Subtitle layout settings
        self.layoutCard = ComboBoxSettingCard(
            FIF.ALIGNMENT,  # type: ignore
            self.tr("Subtitle Layout"),
            self.tr("Set display method for main and sub subtitles"),
            texts=["Translation on Top", "Original on Top", "Translation Only", "Original Only"],
        )

        # Vertical spacing
        self.verticalSpacingCard = SpinBoxSettingCard(
            FIF.ALIGNMENT,  # type: ignore
            self.tr("Vertical spacing"),
            self.tr("Set subtitle vertical spacing"),
            minimum=8,
            maximum=10000,
        )

        # Main subtitle style设置
        self.mainFontCard = ComboBoxSettingCard(
            FIF.FONT,  # type: ignore
            self.tr("Main Subtitle Font"),
            self.tr("Set main subtitle font"),
            texts=["Arial"],
        )

        self.mainSizeCard = SpinBoxSettingCard(
            FIF.FONT_SIZE,  # type: ignore
            self.tr("Main Subtitle Size"),
            self.tr("Set main subtitle size"),
            minimum=8,
            maximum=1000,
        )

        self.mainSpacingCard = DoubleSpinBoxSettingCard(
            FIF.ALIGNMENT,  # type: ignore
            self.tr("Main Subtitle Spacing"),
            self.tr("Set main subtitle character spacing"),
            minimum=0.0,
            maximum=10.0,
            decimals=1,
        )

        self.mainColorCard = ColorSettingCard(
            QColor(255, 255, 255),
            FIF.PALETTE,  # type: ignore
            self.tr("Main Subtitle Color"),
            self.tr("Set main subtitle color"),
        )

        self.mainOutlineColorCard = ColorSettingCard(
            QColor(0, 0, 0),
            FIF.PALETTE,  # type: ignore
            self.tr("Main Subtitle Border Color"),
            self.tr("Set main subtitle border color"),
        )

        self.mainOutlineSizeCard = DoubleSpinBoxSettingCard(
            FIF.ZOOM,  # type: ignore
            self.tr("Main Subtitle Border Size"),
            self.tr("Set main subtitle border thickness"),
            minimum=0.0,
            maximum=10.0,
            decimals=1,
        )

        # Sub subtitle style设置
        self.subFontCard = ComboBoxSettingCard(
            FIF.FONT,  # type: ignore
            self.tr("Sub Subtitle Font"),
            self.tr("Set sub subtitle font"),
            texts=["Arial"],
        )

        self.subSizeCard = SpinBoxSettingCard(
            FIF.FONT_SIZE,  # type: ignore
            self.tr("Sub Subtitle Size"),
            self.tr("Set sub subtitle size"),
            minimum=8,
            maximum=1000,
        )

        self.subSpacingCard = DoubleSpinBoxSettingCard(
            FIF.ALIGNMENT,  # type: ignore
            self.tr("Sub Subtitle Spacing"),
            self.tr("Set sub subtitle character spacing"),
            minimum=0.0,
            maximum=50.0,
            decimals=1,
        )

        self.subColorCard = ColorSettingCard(
            QColor(255, 255, 255),
            FIF.PALETTE,  # type: ignore
            self.tr("Sub Subtitle Color"),
            self.tr("Set sub subtitle color"),
        )

        self.subOutlineColorCard = ColorSettingCard(
            QColor(0, 0, 0),
            FIF.PALETTE,  # type: ignore
            self.tr("Sub Subtitle Border Color"),
            self.tr("Set sub subtitle border color"),
        )

        self.subOutlineSizeCard = DoubleSpinBoxSettingCard(
            FIF.ZOOM,  # type: ignore
            self.tr("Sub Subtitle Border Size"),
            self.tr("Set sub subtitle border thickness"),
            minimum=0.0,
            maximum=50.0,
            decimals=1,
        )

        # Preview settings
        self.previewTextCard = ComboBoxSettingCard(
            FIF.MESSAGE,  # type: ignore
            self.tr("Preview Text"),
            self.tr("Set text content for preview display"),
            texts=list(PERVIEW_TEXTS.keys()),
            parent=self.previewGroup,
        )

        self.orientationCard = ComboBoxSettingCard(
            FIF.LAYOUT,  # type: ignore
            self.tr("Preview Orientation"),
            self.tr("Set display orientation of preview image"),
            texts=["Landscape", "Portrait"],
            parent=self.previewGroup,
        )

        self.previewImageCard = PushSettingCard(
            self.tr("Select Image"),
            FIF.PHOTO,
            self.tr("Preview Background"),
            self.tr("Select background image for preview"),
            parent=self.previewGroup,
        )

    def _initLayout(self):
        """Initialize layout"""
        # Add cards to group
        self.layoutGroup.addSettingCard(self.layoutCard)
        self.layoutGroup.addSettingCard(self.verticalSpacingCard)
        self.mainGroup.addSettingCard(self.mainFontCard)
        self.mainGroup.addSettingCard(self.mainSizeCard)
        self.mainGroup.addSettingCard(self.mainSpacingCard)
        self.mainGroup.addSettingCard(self.mainColorCard)
        self.mainGroup.addSettingCard(self.mainOutlineColorCard)
        self.mainGroup.addSettingCard(self.mainOutlineSizeCard)

        self.subGroup.addSettingCard(self.subFontCard)
        self.subGroup.addSettingCard(self.subSizeCard)
        self.subGroup.addSettingCard(self.subSpacingCard)
        self.subGroup.addSettingCard(self.subColorCard)
        self.subGroup.addSettingCard(self.subOutlineColorCard)
        self.subGroup.addSettingCard(self.subOutlineSizeCard)

        self.previewGroup.addSettingCard(self.previewTextCard)
        self.previewGroup.addSettingCard(self.orientationCard)
        self.previewGroup.addSettingCard(self.previewImageCard)

        # Add groups to layout
        self.settingsLayout.addWidget(self.layoutGroup)
        self.settingsLayout.addWidget(self.mainGroup)
        self.settingsLayout.addWidget(self.subGroup)
        self.settingsLayout.addWidget(self.previewGroup)
        self.settingsLayout.addStretch(1)

        # Add left and right sides to main layout
        self.hBoxLayout.addWidget(self.settingsScrollArea)
        self.hBoxLayout.addWidget(self.previewCard)

    def _initStyle(self):
        """Initialize style"""
        self.settingsWidget.setObjectName("settingsWidget")
        self.setStyleSheet(
            """        
            SubtitleStyleInterface, #settingsWidget {
                background-color: transparent;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """
        )

    def __setValues(self):
        """Set initial values"""
        # Set subtitle layout
        self.layoutCard.comboBox.setCurrentText(cfg.get(cfg.subtitle_layout))
        # Set subtitle style
        self.styleNameComboBox.comboBox.setCurrentText(cfg.get(cfg.subtitle_style_name))

        # Get system fonts, set comboBox options
        fontDatabase = QFontDatabase()
        fontFamilies = fontDatabase.families()
        self.mainFontCard.addItems(fontFamilies)
        self.subFontCard.addItems(fontFamilies)

        # Set maximum display count for font option box
        self.mainFontCard.comboBox.setMaxVisibleItems(12)
        self.subFontCard.comboBox.setMaxVisibleItems(12)

        # Get all txt file names in style directory
        style_files = [f.stem for f in SUBTITLE_STYLE_PATH.glob("*.txt")]
        if "default" in style_files:
            style_files.insert(0, style_files.pop(style_files.index("default")))
        else:
            style_files.insert(0, "default")
            self.saveStyle("default")
        self.styleNameComboBox.comboBox.addItems(style_files)

        # Load default style
        subtitle_style_name = cfg.get(cfg.subtitle_style_name)
        if subtitle_style_name in style_files:
            self.loadStyle(subtitle_style_name)
            self.styleNameComboBox.comboBox.setCurrentText(subtitle_style_name)
        else:
            self.loadStyle(style_files[0])
            self.styleNameComboBox.comboBox.setCurrentText(style_files[0])

    def connectSignals(self):
        """Connect all setting change signals to preview update function"""
        # Subtitle Layout
        self.layoutCard.currentTextChanged.connect(self.onSettingChanged)
        self.layoutCard.currentTextChanged.connect(
            lambda: cfg.set(cfg.subtitle_layout, self.layoutCard.comboBox.currentText())
        )
        # Vertical spacing
        self.verticalSpacingCard.spinBox.valueChanged.connect(self.onSettingChanged)

        # Main subtitle style
        self.mainFontCard.currentTextChanged.connect(self.onSettingChanged)
        self.mainSizeCard.spinBox.valueChanged.connect(self.onSettingChanged)
        self.mainSpacingCard.spinBox.valueChanged.connect(self.onSettingChanged)
        self.mainColorCard.colorChanged.connect(self.onSettingChanged)
        self.mainOutlineColorCard.colorChanged.connect(self.onSettingChanged)
        self.mainOutlineSizeCard.spinBox.valueChanged.connect(self.onSettingChanged)

        # Sub subtitle style
        self.subFontCard.currentTextChanged.connect(self.onSettingChanged)
        self.subSizeCard.spinBox.valueChanged.connect(self.onSettingChanged)
        self.subSpacingCard.spinBox.valueChanged.connect(self.onSettingChanged)
        self.subColorCard.colorChanged.connect(self.onSettingChanged)
        self.subOutlineColorCard.colorChanged.connect(self.onSettingChanged)
        self.subOutlineSizeCard.spinBox.valueChanged.connect(self.onSettingChanged)

        # Preview settings
        self.previewTextCard.currentTextChanged.connect(self.onSettingChanged)
        self.orientationCard.currentTextChanged.connect(self.onOrientationChanged)
        self.previewImageCard.clicked.connect(self.selectPreviewImage)

        # 连接样式切换信号
        self.styleNameComboBox.currentTextChanged.connect(self.loadStyle)
        self.newStyleButton.clicked.connect(self.createNewStyle)
        self.openStyleFolderButton.clicked.connect(self.on_open_style_folder_clicked)

        # 连接字幕排布信号
        self.layoutCard.comboBox.currentTextChanged.connect(
            signalBus.subtitle_layout_changed
        )
        signalBus.subtitle_layout_changed.connect(self.on_subtitle_layout_changed)

    def on_open_style_folder_clicked(self):
        """Open Style Folder"""
        open_folder(str(SUBTITLE_STYLE_PATH))

    def on_subtitle_layout_changed(self, layout: str):
        cfg.subtitle_layout.value = layout
        self.layoutCard.setCurrentText(layout)

    def onOrientationChanged(self):
        """当Preview Orientation改变时调用"""
        orientation = self.orientationCard.comboBox.currentText()
        preview_image = (
            DEFAULT_BG_LANDSCAPE if orientation == "Landscape" else DEFAULT_BG_PORTRAIT
        )
        cfg.set(cfg.subtitle_preview_image, str(Path(preview_image["path"])))
        self.updatePreview()

    def onSettingChanged(self):
        """当任何设置改变时调用"""
        # 如果正在加载样式，不触发更新
        if self._loading_style:
            return

        self.updatePreview()
        # 获取当前选择的样式名称
        current_style = self.styleNameComboBox.comboBox.currentText()
        if current_style:
            self.saveStyle(current_style)  # 自动保存为当前选择的样式
        else:
            self.saveStyle("default")  # 如果没有Select Style,保存为默认样式

    def selectPreviewImage(self):
        """选择Preview Background图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Background Image"),
            "",
            self.tr("Image File") + " (*.png *.jpg *.jpeg)",
        )
        if file_path:
            cfg.set(cfg.subtitle_preview_image, file_path)
            self.updatePreview()

    def generateAssStyles(self) -> str:
        """生成 ASS style string"""
        style_format = "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding"

        # 从控件获取当前设置
        # 获取Vertical spacing
        vertical_spacing = int(
            self.verticalSpacingCard.spinBox.value()
        )  # 转换为ASS单位

        # 提取Main subtitle style元素
        main_font = self.mainFontCard.comboBox.currentText()
        main_size = self.mainSizeCard.spinBox.value()

        # 获取颜色值并转换为 ASS 格式 (AABBGGRR)
        main_color_hex = self.mainColorCard.colorPicker.color.name()
        main_outline_hex = self.mainOutlineColorCard.colorPicker.color.name()
        main_color = (
            f"&H00{main_color_hex[5:7]}{main_color_hex[3:5]}{main_color_hex[1:3]}"
        )
        main_outline_color = (
            f"&H00{main_outline_hex[5:7]}{main_outline_hex[3:5]}{main_outline_hex[1:3]}"
        )
        main_spacing = self.mainSpacingCard.spinBox.value()
        main_outline_size = self.mainOutlineSizeCard.spinBox.value()

        # 提取Sub subtitle style元素
        sub_font = self.subFontCard.comboBox.currentText()
        sub_size = self.subSizeCard.spinBox.value()

        # 获取颜色值并转换为 ASS 格式 (AABBGGRR)
        sub_color_hex = self.subColorCard.colorPicker.color.name()
        sub_outline_hex = self.subOutlineColorCard.colorPicker.color.name()
        sub_color = f"&H00{sub_color_hex[5:7]}{sub_color_hex[3:5]}{sub_color_hex[1:3]}"
        sub_outline_color = (
            f"&H00{sub_outline_hex[5:7]}{sub_outline_hex[3:5]}{sub_outline_hex[1:3]}"
        )
        sub_spacing = self.subSpacingCard.spinBox.value()
        sub_outline_size = self.subOutlineSizeCard.spinBox.value()

        # 生成样式字符串
        main_style = f"Style: Default,{main_font},{main_size},{main_color},&H000000FF,{main_outline_color},&H00000000,-1,0,0,0,100,100,{main_spacing},0,1,{main_outline_size},0,2,10,10,{vertical_spacing},1,\\q1"
        sub_style = f"Style: Secondary,{sub_font},{sub_size},{sub_color},&H000000FF,{sub_outline_color},&H00000000,-1,0,0,0,100,100,{sub_spacing},0,1,{sub_outline_size},0,2,10,10,{vertical_spacing},1,\\q1"

        return f"[V4+ Styles]\n{style_format}\n{main_style}\n{sub_style}"

    def updatePreview(self):
        """更新预览图片"""
        # 生成 ASS style string
        style_str = self.generateAssStyles()

        # 获取预览文本
        main_text, sub_text = PERVIEW_TEXTS[self.previewTextCard.comboBox.currentText()]

        # Subtitle Layout
        layout = self.layoutCard.comboBox.currentText()
        if layout == "Translation on Top":
            main_text, sub_text = sub_text, main_text
        elif layout == "Original on Top":
            main_text, sub_text = main_text, sub_text
        elif layout == "Translation Only":
            main_text, sub_text = sub_text, None
        elif layout == "Original Only":
            main_text, sub_text = main_text, None

        # 获取Preview Orientation
        orientation = self.orientationCard.comboBox.currentText()
        default_preview = (
            DEFAULT_BG_LANDSCAPE if orientation == "Landscape" else DEFAULT_BG_PORTRAIT
        )

        # 检查是否存在用户自定义背景图片
        user_bg_path = cfg.get(cfg.subtitle_preview_image)
        if user_bg_path and Path(user_bg_path).exists():
            path = user_bg_path
            # 可以保持默认宽高或获取实际图片宽高
            width = default_preview["width"]
            height = default_preview["height"]
        else:
            path = default_preview["path"]
            width = default_preview["width"]
            height = default_preview["height"]

        # 创建预览线程
        self.preview_thread = PreviewThread(
            style_str=style_str,
            preview_text=(main_text, sub_text),
            bg_path=path,
            width=width,
            height=height,
        )
        self.preview_thread.previewReady.connect(self.onPreviewReady)
        self.preview_thread.start()

    def onPreviewReady(self, preview_path):
        """预览图片生成完成的回调"""
        self.previewImage.setImage(preview_path)
        self.updatePreviewImage()

    def updatePreviewImage(self):
        """更新预览图片"""
        height = int(self.previewTopWidget.height() * 0.98)
        width = int(self.previewTopWidget.width() * 0.98)
        self.previewImage.scaledToWidth(width)
        if self.previewImage.height() > height:
            self.previewImage.scaledToHeight(height)
        self.previewImage.setBorderRadius(8, 8, 8, 8)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updatePreviewImage()

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        self.updatePreviewImage()

    def loadStyle(self, style_name):
        """加载指定样式"""
        style_path = SUBTITLE_STYLE_PATH / f"{style_name}.txt"

        if not style_path.exists():
            return

        # 设置标志位，防止触发onSettingChanged
        self._loading_style = True

        with open(style_path, "r", encoding="utf-8") as f:
            style_content = f.read()

        # 解析样式内容
        for line in style_content.split("\n"):
            if line.startswith("Style: Default"):
                # 解析Main subtitle style
                parts = line.split(",")
                self.mainFontCard.setCurrentText(parts[1])
                self.mainSizeCard.spinBox.setValue(int(parts[2]))

                vertical_spacing = int(parts[21])
                self.verticalSpacingCard.spinBox.setValue(vertical_spacing)

                # 将 &HAARRGGBB 格式转换为 QColor
                primary_color = parts[3].strip()
                if primary_color.startswith("&H"):
                    # 移除 &H 前缀,转换为 RGB
                    color_hex = primary_color[2:]
                    alpha = int(color_hex[0:2], 16)
                    blue = int(color_hex[2:4], 16)
                    green = int(color_hex[4:6], 16)
                    red = int(color_hex[6:8], 16)
                    self.mainColorCard.setColor(QColor(red, green, blue, alpha))

                outline_color = parts[5].strip()
                if outline_color.startswith("&H"):
                    color_hex = outline_color[2:]
                    alpha = int(color_hex[0:2], 16)
                    blue = int(color_hex[2:4], 16)
                    green = int(color_hex[4:6], 16)
                    red = int(color_hex[6:8], 16)
                    self.mainOutlineColorCard.setColor(QColor(red, green, blue, alpha))

                self.mainSpacingCard.spinBox.setValue(float(parts[13]))
                self.mainOutlineSizeCard.spinBox.setValue(float(parts[16]))
            elif line.startswith("Style: Secondary"):
                # 解析Sub subtitle style
                parts = line.split(",")
                self.subFontCard.setCurrentText(parts[1])
                self.subSizeCard.spinBox.setValue(int(parts[2]))
                # 将 &HAARRGGBB 格式转换为 QColor
                primary_color = parts[3].strip()
                if primary_color.startswith("&H"):
                    color_hex = primary_color[2:]
                    alpha = int(color_hex[0:2], 16)
                    blue = int(color_hex[2:4], 16)
                    green = int(color_hex[4:6], 16)
                    red = int(color_hex[6:8], 16)
                    self.subColorCard.setColor(QColor(red, green, blue, alpha))

                outline_color = parts[5].strip()
                if outline_color.startswith("&H"):
                    color_hex = outline_color[2:]
                    alpha = int(color_hex[0:2], 16)
                    blue = int(color_hex[2:4], 16)
                    green = int(color_hex[4:6], 16)
                    red = int(color_hex[6:8], 16)
                    self.subOutlineColorCard.setColor(QColor(red, green, blue, alpha))

                self.subSpacingCard.spinBox.setValue(float(parts[13]))
                self.subOutlineSizeCard.spinBox.setValue(float(parts[16]))

        cfg.set(cfg.subtitle_style_name, style_name)

        # 重置标志位
        self._loading_style = False

        # 手动更新一次预览
        self.updatePreview()

        # 显示加载SuccessTip
        InfoBar.success(
            title=self.tr("Success"),
            content=self.tr("Loaded Style ") + style_name,
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=self,
        )

    def createNewStyle(self):
        """创建新样式"""
        dialog = StyleNameDialog(self)
        if dialog.exec():
            style_name = dialog.nameLineEdit.text().strip()
            if not style_name:
                return

            # 检查是否已存在同名样式
            if (SUBTITLE_STYLE_PATH / f"{style_name}.txt").exists():
                InfoBar.warning(
                    title=self.tr("Warning"),
                    content=self.tr("Style ") + style_name + self.tr(" Already Exists"),
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self,
                )
                return

            # 保存新样式
            self.saveStyle(style_name)

            # 更新样式列表并选中新样式
            self.styleNameComboBox.addItem(style_name)
            self.styleNameComboBox.comboBox.setCurrentText(style_name)

            # 显示创建SuccessTip
            InfoBar.success(
                title=self.tr("Success"),
                content=self.tr("Created New Style ") + style_name,
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def saveStyle(self, style_name):
        """保存样式
        Args:
            style_name (str): 样式名称
        """
        # 确保样式目录存在
        SUBTITLE_STYLE_PATH.mkdir(parents=True, exist_ok=True)

        # 生成样式内容并保存
        style_content = self.generateAssStyles()
        style_path = SUBTITLE_STYLE_PATH / f"{style_name}.txt"

        with open(style_path, "w", encoding="utf-8") as f:
            f.write(style_content)


class StyleNameDialog(MessageBoxBase):
    """样式名称输入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self.tr("New Style"), self)
        self.nameLineEdit = LineEdit(self)

        self.nameLineEdit.setPlaceholderText(self.tr("Enter Style Name"))
        self.nameLineEdit.setClearButtonEnabled(True)

        # 添加控件到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.nameLineEdit)

        # 设置按钮文本
        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))

        self.widget.setMinimumWidth(350)
        self.yesButton.setDisabled(True)
        self.nameLineEdit.textChanged.connect(self._validateInput)

    def _validateInput(self, text):
        self.yesButton.setEnabled(bool(text.strip()))
