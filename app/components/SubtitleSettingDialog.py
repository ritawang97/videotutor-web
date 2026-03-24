from qfluentwidgets import (
    BodyLabel,
    ComboBoxSettingCard,
    MessageBoxBase,
    SwitchSettingCard,
)
from qfluentwidgets import FluentIcon as FIF

from app.common.config import cfg
from app.components.SpinBoxSettingCard import SpinBoxSettingCard


class SubtitleSettingDialog(MessageBoxBase):
    """字幕设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self.tr("Subtitle Settings"), self)

        # 创建设置卡片
        self.split_card = SwitchSettingCard(
            FIF.ALIGNMENT,
            self.tr("Subtitle Segmentation"),
            self.tr("Whether to use large language model for intelligent subtitle segmentation"),
            cfg.need_split,
            self,
        )

        self.split_type_card = ComboBoxSettingCard(
            cfg.split_type,
            FIF.TILES,  # type: ignore
            self.tr("Subtitle Segmentation Type"),
            self.tr("Segment subtitles by sentence or by semantic meaning"),
            texts=[model.value for model in cfg.split_type.validator.options],  # type: ignore
            parent=self,
        )

        self.word_count_cjk_card = SpinBoxSettingCard(
            cfg.max_word_count_cjk,
            FIF.TILES,  # type: ignore
            self.tr("Max Chinese Characters"),
            self.tr("Max characters per subtitle line (for CJK languages)"),
            minimum=8,
            maximum=50,
            parent=self,
        )

        self.word_count_english_card = SpinBoxSettingCard(
            cfg.max_word_count_english,
            FIF.TILES,  # type: ignore
            self.tr("Max English Words"),
            self.tr("Max words per subtitle line (English)"),
            minimum=8,
            maximum=50,
            parent=self,
        )

        self.remove_punctuation_card = SwitchSettingCard(
            FIF.ALIGNMENT,
            self.tr("Remove Trailing Punctuation"),
            self.tr("Whether to remove trailing punctuation in Chinese subtitles"),
            cfg.needs_remove_punctuation,
            self,
        )

        # 添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.split_card)
        self.viewLayout.addWidget(self.split_type_card)
        self.viewLayout.addWidget(self.word_count_cjk_card)
        self.viewLayout.addWidget(self.word_count_english_card)
        self.viewLayout.addWidget(self.remove_punctuation_card)
        # 设置间距

        self.viewLayout.setSpacing(10)

        # 设置窗口标题
        self.setWindowTitle(self.tr("Subtitle Settings"))

        # 只显示取消按钮
        self.yesButton.hide()
        self.cancelButton.setText(self.tr("Close"))
