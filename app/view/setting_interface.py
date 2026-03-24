import webbrowser

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog, QLabel, QWidget
from qfluentwidgets import (
    ComboBoxSettingCard,
    CustomColorSettingCard,
    ExpandLayout,
    HyperlinkCard,
    InfoBar,
    OptionsSettingCard,
    PrimaryPushSettingCard,
    PushSettingCard,
    RangeSettingCard,
    ScrollArea,
    SettingCardGroup,
    SwitchSettingCard,
    setTheme,
    setThemeColor,
)
from qfluentwidgets import FluentIcon as FIF

from app.common.config import cfg
from app.common.signal_bus import signalBus
from app.components.EditComboBoxSettingCard import EditComboBoxSettingCard
from app.components.LineEditSettingCard import LineEditSettingCard
from app.config import AUTHOR, FEEDBACK_URL, HELP_URL, RELEASE_URL, VERSION, YEAR
from app.core.entities import LLMServiceEnum, TranslatorServiceEnum
from app.core.utils.test_opanai import get_openai_models, test_openai


class SettingInterface(ScrollArea):
    """设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr("Settings"))
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self.settingLabel = QLabel(self.tr("Settings"), self)

        # 初始化所有设置组
        self.__initGroups()
        # 初始化所有配置卡片
        self.__initCards()
        # 初始化界面
        self.__initWidget()
        # 初始化布局
        self.__initLayout()
        # 连接信号和槽
        self.__connectSignalToSlot()

    def __initGroups(self):
        """初始化所有设置组"""
        # 转录配置组
        self.transcribeGroup = SettingCardGroup(self.tr("Transcription Configuration"), self.scrollWidget)
        # LLM配置组
        self.llmGroup = SettingCardGroup(self.tr("LLM Configuration"), self.scrollWidget)
        # 翻译服务组
        self.translate_serviceGroup = SettingCardGroup(
            self.tr("Translation Service"), self.scrollWidget
        )
        # 翻译与优化组
        self.translateGroup = SettingCardGroup(self.tr("Translation & Optimization"), self.scrollWidget)
        # 字幕合成配置组
        self.subtitleGroup = SettingCardGroup(
            self.tr("Subtitle Synthesis Configuration"), self.scrollWidget
        )
        # 素材搜索API配置组（新增）
        self.materialSearchGroup = SettingCardGroup(
            self.tr("Material Search API Configuration"), self.scrollWidget
        )
        # 保存配置组
        self.saveGroup = SettingCardGroup(self.tr("Save Configuration"), self.scrollWidget)
        # 个性化组
        self.personalGroup = SettingCardGroup(self.tr("Personalization"), self.scrollWidget)
        # 关于组
        self.aboutGroup = SettingCardGroup(self.tr("About"), self.scrollWidget)

    def __initCards(self):
        """初始化所有配置卡片"""
        # 转录配置卡片
        self.transcribeModelCard = ComboBoxSettingCard(
            cfg.transcribe_model,
            FIF.MICROPHONE,
            self.tr("Transcription Model"),
            self.tr("Speech recognition model to use for speech-to-text conversion"),
            texts=[model.value for model in cfg.transcribe_model.validator.options],  # type: ignore
            parent=self.transcribeGroup,
        )

        # LLM配置卡片
        self.__createLLMServiceCards()

        # 翻译配置卡片
        self.__createTranslateServiceCards()

        # 翻译与优化配置卡片
        self.subtitleCorrectCard = SwitchSettingCard(
            FIF.EDIT,
            self.tr("Subtitle Correction"),
            self.tr("Whether to correct generated subtitles during subtitle processing"),
            cfg.need_optimize,
            self.translateGroup,
        )
        self.subtitleTranslateCard = SwitchSettingCard(
            FIF.LANGUAGE,
            self.tr("Subtitle Translation"),
            self.tr("Whether to translate generated subtitles during subtitle processing"),
            cfg.need_translate,
            self.translateGroup,
        )
        self.targetLanguageCard = ComboBoxSettingCard(
            cfg.target_language,
            FIF.LANGUAGE,
            self.tr("Target Language"),
            self.tr("Select target language for subtitle translation"),
            texts=[lang.value for lang in cfg.target_language.validator.options],  # type: ignore
            parent=self.translateGroup,
        )

        # 字幕合成配置卡片
        self.subtitleStyleCard = HyperlinkCard(
            "",
            self.tr("Modify"),
            FIF.FONT,
            self.tr("Subtitle Style"),
            self.tr("Select subtitle style (color, size, font, etc.)"),
            self.subtitleGroup,
        )
        self.subtitleLayoutCard = HyperlinkCard(
            "",
            self.tr("Modify"),
            FIF.FONT,
            self.tr("Subtitle Layout"),
            self.tr("Select subtitle layout (monolingual, bilingual)"),
            self.subtitleGroup,
        )
        self.needVideoCard = SwitchSettingCard(
            FIF.VIDEO,
            self.tr("Synthesize Video"),
            self.tr("Trigger video synthesis when enabled, skip when disabled"),
            cfg.need_video,
            self.subtitleGroup,
        )
        self.softSubtitleCard = SwitchSettingCard(
            FIF.FONT,
            self.tr("Soft Subtitle"),
            self.tr("When enabled, subtitles can be turned off or adjusted in player; when disabled, subtitles are burned into video"),
            cfg.soft_subtitle,
            self.subtitleGroup,
        )

        # 保存配置卡片
        # 素材搜索API配置卡片（新增）
        self.pexelsApiKeyCard = LineEditSettingCard(
            cfg.pexels_api_key,
            FIF.PHOTO,
            self.tr("Pexels API Key"),
            self.tr("For searching high-quality image and video materials (free)"),
            placeholder="Get from: https://www.pexels.com/api/",
            parent=self.materialSearchGroup,
        )
        
        self.unsplashApiKeyCard = LineEditSettingCard(
            cfg.unsplash_api_key,
            FIF.PHOTO,
            self.tr("Unsplash API Key"),
            self.tr("For searching high-quality image materials (free)"),
            placeholder="Get from: https://unsplash.com/developers",
            parent=self.materialSearchGroup,
        )
        
        self.pixabayApiKeyCard = LineEditSettingCard(
            cfg.pixabay_api_key,
            FIF.PHOTO,
            self.tr("Pixabay API Key"),
            self.tr("For searching image and video materials (free)"),
            placeholder="Get from: https://pixabay.com/api/docs/",
            parent=self.materialSearchGroup,
        )

        self.savePathCard = PushSettingCard(
            self.tr("Work Folder"),
            FIF.SAVE,
            self.tr("Work Directory Path"),
            cfg.get(cfg.work_dir),
            self.saveGroup,
        )

        # 个性化配置卡片
        self.themeCard = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr("Application Theme"),
            self.tr("Change application appearance"),
            texts=[self.tr("Light"), self.tr("Dark"), self.tr("Use System Settings")],
            parent=self.personalGroup,
        )
        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            self.tr("Theme Color"),
            self.tr("Change application theme color"),
            self.personalGroup,
        )
        self.zoomCard = OptionsSettingCard(
            cfg.dpiScale,
            FIF.ZOOM,
            self.tr("Interface Scaling"),
            self.tr("Change size of widgets and fonts"),
            texts=["100%", "125%", "150%", "175%", "200%", self.tr("Use System Settings")],
            parent=self.personalGroup,
        )
        self.languageCard = ComboBoxSettingCard(
            cfg.language,
            FIF.LANGUAGE,
            self.tr("Language"),
            self.tr("Set your preferred interface language"),
            texts=["Simplified Chinese", "Traditional Chinese", "English", self.tr("Use System Settings")],
            parent=self.personalGroup,
        )

        # 关于卡片
        self.helpCard = HyperlinkCard(
            HELP_URL,
            self.tr("Open Help Page"),
            FIF.HELP,
            self.tr("Help"),
            self.tr("Discover new features and learn about VideoCaptioner usage tips"),
            self.aboutGroup,
        )
        self.feedbackCard = PrimaryPushSettingCard(
            self.tr("Provide Feedback"),
            FIF.FEEDBACK,
            self.tr("Provide Feedback"),
            self.tr("Provide feedback to help us improve VideoCaptioner"),
            self.aboutGroup,
        )
        self.aboutCard = PrimaryPushSettingCard(
            self.tr("Check for Updates"),
            FIF.INFO,
            self.tr("About"),
            "© "
            + self.tr("Copyright")
            + f" {YEAR}, {AUTHOR}. "
            + self.tr("Version")
            + " "
            + VERSION,
            self.aboutGroup,
        )

        # 添加卡片到对应的组
        self.translateGroup.addSettingCard(self.subtitleCorrectCard)
        self.translateGroup.addSettingCard(self.subtitleTranslateCard)
        self.translateGroup.addSettingCard(self.targetLanguageCard)

        self.subtitleGroup.addSettingCard(self.subtitleStyleCard)
        self.subtitleGroup.addSettingCard(self.subtitleLayoutCard)
        self.subtitleGroup.addSettingCard(self.needVideoCard)
        self.subtitleGroup.addSettingCard(self.softSubtitleCard)

        # 添加素材搜索API配置卡片（新增）
        self.materialSearchGroup.addSettingCard(self.pexelsApiKeyCard)
        self.materialSearchGroup.addSettingCard(self.unsplashApiKeyCard)
        self.materialSearchGroup.addSettingCard(self.pixabayApiKeyCard)

        self.saveGroup.addSettingCard(self.savePathCard)

        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        self.personalGroup.addSettingCard(self.zoomCard)
        self.personalGroup.addSettingCard(self.languageCard)

        self.aboutGroup.addSettingCard(self.helpCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

    def __createLLMServiceCards(self):
        """创建LLM服务相关的配置卡片"""
        # 服务选择卡片
        self.llmServiceCard = ComboBoxSettingCard(
            cfg.llm_service,
            FIF.ROBOT,
            self.tr("LLM Service"),
            self.tr("Select large language model service for subtitle segmentation, optimization, and translation"),
            texts=[service.value for service in cfg.llm_service.validator.options],  # type: ignore
            parent=self.llmGroup,
        )

        # 创建OPENAI官方API链接卡片
        self.openaiOfficialApiCard = HyperlinkCard(
            "https://api.videocaptioner.cn/register?aff=UrLB",
            self.tr("Visit"),
            FIF.DEVELOPER_TOOLS,
            self.tr("VideoCaptioner Official API"),
            self.tr("Integrates multiple large language models, supports high-concurrency subtitle optimization and translation"),
            self.llmGroup,
        )
        # 默认隐藏
        self.openaiOfficialApiCard.setVisible(False)

        # 定义每个服务的配置
        service_configs = {
            LLMServiceEnum.OPENAI: {
                "prefix": "openai",
                "api_key_cfg": cfg.openai_api_key,
                "api_base_cfg": cfg.openai_api_base,
                "model_cfg": cfg.openai_model,
                "default_base": "https://api.openai.com/v1",
                "default_models": [
                    "gpt-4o-mini",
                    "gpt-4o",
                    "claude-3-5-sonnet-20241022",
                ],
            },
            LLMServiceEnum.SILICON_CLOUD: {
                "prefix": "silicon_cloud",
                "api_key_cfg": cfg.silicon_cloud_api_key,
                "api_base_cfg": cfg.silicon_cloud_api_base,
                "model_cfg": cfg.silicon_cloud_model,
                "default_base": "https://api.siliconflow.cn/v1",
                "default_models": ["deepseek-ai/DeepSeek-V3"],
            },
            LLMServiceEnum.DEEPSEEK: {
                "prefix": "deepseek",
                "api_key_cfg": cfg.deepseek_api_key,
                "api_base_cfg": cfg.deepseek_api_base,
                "model_cfg": cfg.deepseek_model,
                "default_base": "https://api.deepseek.com/v1",
                "default_models": ["deepseek-chat"],
            },
            LLMServiceEnum.OLLAMA: {
                "prefix": "ollama",
                "api_key_cfg": cfg.ollama_api_key,
                "api_base_cfg": cfg.ollama_api_base,
                "model_cfg": cfg.ollama_model,
                "default_base": "http://localhost:11434/v1",
                "default_models": ["qwen2.5:7b"],
            },
            LLMServiceEnum.LM_STUDIO: {
                "prefix": "LM Studio",
                "api_key_cfg": cfg.lm_studio_api_key,
                "api_base_cfg": cfg.lm_studio_api_base,
                "model_cfg": cfg.lm_studio_model,
                "default_base": "http://localhost:1234/v1",
                "default_models": ["qwen2.5:7b"],
            },
            LLMServiceEnum.GEMINI: {
                "prefix": "gemini",
                "api_key_cfg": cfg.gemini_api_key,
                "api_base_cfg": cfg.gemini_api_base,
                "model_cfg": cfg.gemini_model,
                "default_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "default_models": ["gemini-2.0-flash-exp"],
            },
            LLMServiceEnum.CHATGLM: {
                "prefix": "chatglm",
                "api_key_cfg": cfg.chatglm_api_key,
                "api_base_cfg": cfg.chatglm_api_base,
                "model_cfg": cfg.chatglm_model,
                "default_base": "https://open.bigmodel.cn/api/paas/v4",
                "default_models": ["glm-4-flash"],
            },
            LLMServiceEnum.PUBLIC: {
                "prefix": "public",
                "api_key_cfg": cfg.public_api_key,
                "api_base_cfg": cfg.public_api_base,
                "model_cfg": cfg.public_model,
                "default_base": "https://api.public-model.com/v1",
                "default_models": ["public-model"],
            },
        }

        # 创建服务配置映射
        self.llm_service_configs = {}

        # 为每个服务创建配置卡片
        for service, config in service_configs.items():
            prefix = config["prefix"]

            # 如果是公益模型，只添加配置不创建卡片
            if service == LLMServiceEnum.PUBLIC:
                self.llm_service_configs[service] = {
                    "cards": [],
                    "api_base": None,
                    "api_key": None,
                    "model": None,
                }
                continue

            # 创建API Key卡片
            api_key_card = LineEditSettingCard(
                config["api_key_cfg"],
                FIF.FINGERPRINT,
                self.tr("API Key"),
                self.tr(f"Enter your {service.value} API Key"),
                "sk-" if service != LLMServiceEnum.OLLAMA else "",
                self.llmGroup,
            )
            setattr(self, f"{prefix}_api_key_card", api_key_card)

            # 创建Base URL卡片
            api_base_card = LineEditSettingCard(
                config["api_base_cfg"],
                FIF.LINK,
                self.tr("Base URL"),
                self.tr(f"Enter {service.value} Base URL, must include /v1"),
                config["default_base"],
                self.llmGroup,
            )
            setattr(self, f"{prefix}_api_base_card", api_base_card)

            # 创建模型选择卡片
            model_card = EditComboBoxSettingCard(
                config["model_cfg"],
                FIF.ROBOT,  # type: ignore
                self.tr("Model"),
                self.tr(f"Select {service.value} model"),
                config["default_models"],
                self.llmGroup,
            )
            setattr(self, f"{prefix}_model_card", model_card)

            # 存储服务配置
            cards = [api_key_card, api_base_card, model_card]

            self.llm_service_configs[service] = {
                "cards": cards,
                "api_base": api_base_card,
                "api_key": api_key_card,
                "model": model_card,
            }

        # 创建检查连接卡片
        self.checkLLMConnectionCard = PushSettingCard(
            self.tr("Check Connection"),
            FIF.LINK,
            self.tr("Check LLM Connection"),
            self.tr("Click to check if API connection is normal and get model list"),
            self.llmGroup,
        )

        # 初始化显示状态
        # 确保默认显示当前配置的服务（如果配置是 Gemini，会自动显示 Gemini）
        current_text = self.llmServiceCard.comboBox.currentText()
        self.__onLLMServiceChanged(current_text)

    def __createTranslateServiceCards(self):
        """创建翻译服务相关的配置卡片"""
        # 翻译服务选择卡片
        self.translatorServiceCard = ComboBoxSettingCard(
            cfg.translator_service,
            FIF.ROBOT,
            self.tr("Translation Service"),
            self.tr("Select translation service"),
            texts=[
                service.value
                for service in cfg.translator_service.validator.options  # type: ignore
            ],
            parent=self.translate_serviceGroup,
        )

        # 反思翻译开关
        self.needReflectTranslateCard = SwitchSettingCard(
            FIF.EDIT,
            self.tr("Need Reflection Translation"),
            self.tr("Enabling reflection translation can improve quality but consumes more time and tokens"),
            cfg.need_reflect_translate,
            self.translate_serviceGroup,
        )

        # DeepLx端点配置
        self.deeplxEndpointCard = LineEditSettingCard(
            cfg.deeplx_endpoint,
            FIF.LINK,
            self.tr("DeepLx Backend"),
            self.tr("Enter DeepLx backend address (required when enabling deeplx translation)"),
            "https://api.deeplx.org/translate",
            self.translate_serviceGroup,
        )

        # 批处理大小配置
        self.batchSizeCard = RangeSettingCard(
            cfg.batch_size,
            FIF.ALIGNMENT,
            self.tr("Batch Size"),
            self.tr("Number of subtitles to process per batch, recommend multiples of 10"),
            parent=self.translate_serviceGroup,
        )

        # 线程数配置
        self.threadNumCard = RangeSettingCard(
            cfg.thread_num,
            FIF.SPEED_HIGH,
            self.tr("Thread Count"),
            self.tr(
                "Number of parallel processing requests, recommend as large as allowed by model provider, larger value means faster speed"
            ),
            parent=self.translate_serviceGroup,
        )

        # 添加卡片到翻译服务组
        self.translate_serviceGroup.addSettingCard(self.translatorServiceCard)
        self.translate_serviceGroup.addSettingCard(self.needReflectTranslateCard)
        self.translate_serviceGroup.addSettingCard(self.deeplxEndpointCard)
        self.translate_serviceGroup.addSettingCard(self.batchSizeCard)
        self.translate_serviceGroup.addSettingCard(self.threadNumCard)

        # 初始化显示状态
        self.__onTranslatorServiceChanged(
            self.translatorServiceCard.comboBox.currentText()
        )

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # type: ignore
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("settingInterface")

        # 初始化样式表
        self.scrollWidget.setObjectName("scrollWidget")
        self.settingLabel.setObjectName("settingLabel")

        # 初始化翻译服务配置卡片的显示状态
        self.__onTranslatorServiceChanged(
            self.translatorServiceCard.comboBox.currentText()
        )

        self.setStyleSheet(
            """        
            SettingInterface, #scrollWidget {
                background-color: transparent;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLabel#settingLabel {
                font: 33px 'Microsoft YaHei';
                background-color: transparent;
                color: white;
            }
        """
        )

    def __initLayout(self):
        """初始化布局"""
        self.settingLabel.move(36, 30)

        # 添加转录配置卡片
        self.transcribeGroup.addSettingCard(self.transcribeModelCard)

        # 添加LLM配置卡片
        self.llmGroup.addSettingCard(self.llmServiceCard)
        # 添加OPENAI官方API链接卡片
        self.llmGroup.addSettingCard(self.openaiOfficialApiCard)
        for config in self.llm_service_configs.values():
            for card in config["cards"]:
                self.llmGroup.addSettingCard(card)
        self.llmGroup.addSettingCard(self.checkLLMConnectionCard)

        # 将所有组添加到布局
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.transcribeGroup)
        self.expandLayout.addWidget(self.llmGroup)
        self.expandLayout.addWidget(self.translate_serviceGroup)
        self.expandLayout.addWidget(self.translateGroup)
        self.expandLayout.addWidget(self.subtitleGroup)
        self.expandLayout.addWidget(self.materialSearchGroup)
        self.expandLayout.addWidget(self.saveGroup)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __connectSignalToSlot(self):
        """连接信号与槽"""
        cfg.appRestartSig.connect(self.__showRestartTooltip)

        # LLM服务切换
        self.llmServiceCard.comboBox.currentTextChanged.connect(
            self.__onLLMServiceChanged
        )

        # 翻译服务切换
        self.translatorServiceCard.comboBox.currentTextChanged.connect(
            self.__onTranslatorServiceChanged
        )

        # Check LLM Connection
        self.checkLLMConnectionCard.clicked.connect(self.checkLLMConnection)

        # 保存路径
        self.savePathCard.clicked.connect(self.__onsavePathCardClicked)

        # 字幕样式修改跳转
        self.subtitleStyleCard.linkButton.clicked.connect(
            lambda: self.window().switchTo(self.window().subtitleStyleInterface)  # type: ignore
        )
        self.subtitleLayoutCard.linkButton.clicked.connect(
            lambda: self.window().switchTo(self.window().subtitleStyleInterface)  # type: ignore
        )

        # Personalization
        self.themeCard.optionChanged.connect(lambda ci: setTheme(cfg.get(ci)))
        self.themeColorCard.colorChanged.connect(setThemeColor)

        # 反馈
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL))  # type: ignore
        )

        # About
        self.aboutCard.clicked.connect(self.checkUpdate)

        # 全局 signalBus
        self.transcribeModelCard.comboBox.currentTextChanged.connect(
            signalBus.transcription_model_changed
        )
        self.subtitleCorrectCard.checkedChanged.connect(
            signalBus.subtitle_optimization_changed
        )
        self.subtitleTranslateCard.checkedChanged.connect(
            signalBus.subtitle_translation_changed
        )
        self.targetLanguageCard.comboBox.currentTextChanged.connect(
            signalBus.target_language_changed
        )
        self.softSubtitleCard.checkedChanged.connect(signalBus.soft_subtitle_changed)
        self.needVideoCard.checkedChanged.connect(signalBus.need_video_changed)

    def __showRestartTooltip(self):
        """显示重启提示"""
        InfoBar.success(
            self.tr("Update Successful"),
            self.tr("Configuration will take effect after restart"),
            duration=1500,
            parent=self,
        )

    def __onsavePathCardClicked(self):
        """处理保存路径卡片点击事件"""
        folder = QFileDialog.getExistingDirectory(self, self.tr("Select Folder"), "./")
        if not folder or cfg.get(cfg.work_dir) == folder:
            return
        cfg.set(cfg.work_dir, folder)
        self.savePathCard.setContent(folder)

    def checkLLMConnection(self):
        """Check LLM Connection"""
        # 获取当前选中的服务
        current_service = LLMServiceEnum(self.llmServiceCard.comboBox.currentText())

        # 获取服务配置
        service_config = self.llm_service_configs.get(current_service)
        if not service_config:
            return

        # 如果是公益模型，使用配置文件中的值
        if current_service == LLMServiceEnum.PUBLIC:
            api_base = cfg.public_api_base.value
            api_key = cfg.public_api_key.value
            model = cfg.public_model.value
        else:
            # 先从界面读取值
            api_base = (
                service_config["api_base"].lineEdit.text().strip()
                if service_config["api_base"]
                else ""
            )
            api_key = (
                service_config["api_key"].lineEdit.text().strip()
                if service_config["api_key"]
                else ""
            )
            model = (
                service_config["model"].comboBox.currentText().strip()
                if service_config["model"]
                else ""
            )
            
            # 先保存配置到配置文件（确保配置已保存）
            # LineEditSettingCard 会自动保存，但为了确保，我们显式保存一次
            if service_config["api_base"]:
                cfg.set(service_config["api_base"].configItem, api_base)
            if service_config["api_key"]:
                cfg.set(service_config["api_key"].configItem, api_key)
            if service_config["model"]:
                cfg.set(service_config["model"].configItem, model)

        # 验证必填字段
        if not api_key:
            InfoBar.error(
                self.tr("Error"),
                self.tr("Please enter API Key"),
                duration=3000,
                parent=self,
            )
            return
        
        if not api_base:
            InfoBar.error(
                self.tr("Error"),
                self.tr("Please enter API Base URL"),
                duration=3000,
                parent=self,
            )
            return

        # 检查 API Base 是否属于网址
        if not api_base.startswith("http"):
            InfoBar.error(
                self.tr("Error"),
                self.tr("Please enter correct API Base URL, must start with http:// or https://"),
                duration=3000,
                parent=self,
            )
            return
        
        # 验证API Base URL格式（应该包含/v1）
        if "/v1" not in api_base and not api_base.endswith("/v1"):
            InfoBar.warning(
                self.tr("Warning"),
                self.tr("API Base URL should include /v1 (e.g., https://api.openai.com/v1)"),
                duration=3000,
                parent=self,
            )
        
        # 验证API Key格式（OpenAI格式应该以sk-开头）
        if current_service == LLMServiceEnum.OPENAI and not api_key.startswith("sk-"):
            InfoBar.warning(
                self.tr("Warning"),
                self.tr("OpenAI API Key should start with 'sk-'"),
                duration=3000,
                parent=self,
            )

        # 禁用检查按钮，显示加载状态
        self.checkLLMConnectionCard.button.setEnabled(False)
        self.checkLLMConnectionCard.button.setText(self.tr("Checking..."))

        # 创建并启动线程
        self.connection_thread = LLMConnectionThread(api_base, api_key, model)
        self.connection_thread.finished.connect(self.onConnectionCheckFinished)
        self.connection_thread.error.connect(self.onConnectionCheckError)
        self.connection_thread.start()

    def onConnectionCheckError(self, message):
        """处理连接检查错误事件"""
        self.checkLLMConnectionCard.button.setEnabled(True)
        self.checkLLMConnectionCard.button.setText(self.tr("Check Connection"))
        InfoBar.error(self.tr("LLM Connection Test Error"), message, duration=3000, parent=self)

    def onConnectionCheckFinished(self, is_success, message, models):
        """处理连接检查完成事件"""
        self.checkLLMConnectionCard.button.setEnabled(True)
        self.checkLLMConnectionCard.button.setText(self.tr("Check Connection"))

        # 获取当前服务
        current_service = LLMServiceEnum(self.llmServiceCard.comboBox.currentText())

        if is_success:
            # 配置已成功保存并验证
            InfoBar.success(
                self.tr("Configuration Saved & Verified"),
                self.tr("API connection successful! Configuration has been saved."),
                duration=3000,
                parent=self,
            )
            
            if models:
                # 更新当前服务的模型列表
                service_config = self.llm_service_configs.get(current_service)
                if service_config and service_config["model"]:
                    temp = service_config["model"].comboBox.currentText()
                    service_config["model"].setItems(models)
                    if temp in models:
                        service_config["model"].comboBox.setCurrentText(temp)

                InfoBar.success(
                    self.tr("Model list retrieved successfully"),
                    self.tr("Total: ") + str(len(models)) + self.tr(" models"),
                    duration=3000,
                    parent=self,
                )
        else:
            # 连接失败，但配置已保存
            InfoBar.warning(
                self.tr("Configuration Saved, But Connection Failed"),
                f"{self.tr('Configuration has been saved.')} {message}",
                duration=5000,
                parent=self,
            )
        if not is_success:
            InfoBar.error(
                self.tr("LLM Connection Test Error"), message, duration=3000, parent=self
            )
        else:
            InfoBar.success(
                self.tr("LLM Connection Test Successful"), message, duration=3000, parent=self
            )

    def checkUpdate(self):
        webbrowser.open(RELEASE_URL)

    def __onLLMServiceChanged(self, service):
        """处理LLM服务切换事件"""
        current_service = LLMServiceEnum(service)

        # 隐藏所有卡片
        for config in self.llm_service_configs.values():
            for card in config["cards"]:
                card.setVisible(False)

        # 隐藏OPENAI官方API链接卡片
        self.openaiOfficialApiCard.setVisible(False)

        # 显示选中服务的卡片
        if current_service in self.llm_service_configs:
            for card in self.llm_service_configs[current_service]["cards"]:
                card.setVisible(True)

            # 为OLLAMA和LM_STUDIO设置默认API Key
            service_config = self.llm_service_configs[current_service]
            if current_service == LLMServiceEnum.OLLAMA and service_config["api_key"]:
                # 如果API Key为空，设置默认值"ollama"
                if not service_config["api_key"].lineEdit.text():
                    service_config["api_key"].lineEdit.setText("ollama")
            if (
                current_service == LLMServiceEnum.LM_STUDIO
                and service_config["api_key"]
            ):
                # 如果API Key为空，设置默认值 "lm-studio"
                if not service_config["api_key"].lineEdit.text():
                    service_config["api_key"].lineEdit.setText("lm-studio")

            # 如果是OPENAI服务，显示官方API链接卡片
            if current_service == LLMServiceEnum.OPENAI:
                self.openaiOfficialApiCard.setVisible(True)

        # 更新布局
        self.llmGroup.adjustSize()
        self.expandLayout.update()

    def __onTranslatorServiceChanged(self, service):
        openai_cards = [
            self.needReflectTranslateCard,
            self.batchSizeCard,
        ]
        deeplx_cards = [self.deeplxEndpointCard]

        all_cards = openai_cards + deeplx_cards
        for card in all_cards:
            card.setVisible(False)

        # 根据选择的服务显示相应的配置卡片
        if service in [TranslatorServiceEnum.DEEPLX.value]:
            for card in deeplx_cards:
                card.setVisible(True)
        elif service in [TranslatorServiceEnum.OPENAI.value]:
            for card in openai_cards:
                card.setVisible(True)

        # 更新布局
        self.translate_serviceGroup.adjustSize()
        self.expandLayout.update()


class LLMConnectionThread(QThread):
    finished = pyqtSignal(bool, str, list)
    error = pyqtSignal(str)

    def __init__(self, api_base, api_key, model):
        super().__init__()
        self.api_base = api_base
        self.api_key = api_key
        self.model = model

    def run(self):
        """检查 LLM 连接并获取模型列表"""
        try:
            is_success, message = test_openai(self.api_base, self.api_key, self.model)
            models = get_openai_models(self.api_base, self.api_key)
            self.finished.emit(is_success, message, models)
        except Exception as e:
            self.error.emit(str(e))
