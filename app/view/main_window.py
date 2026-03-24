import os

import psutil
from PyQt5.QtCore import QSize, QThread
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    FluentWindow,
    MessageBox,
    NavigationItemPosition,
    SplashScreen,
)

from app.common.config import cfg
from app.common.ui_styles import GLOBAL_STYLE
from app.components.DonateDialog import DonateDialog
from app.config import ASSETS_PATH
from app.thread.version_manager_thread import VersionManager
from app.view.batch_process_interface import BatchProcessInterface
from app.view.dashboard_interface import DashboardInterface
from app.view.home_interface import HomeInterface
from app.view.setting_interface import SettingInterface
from app.view.subtitle_style_interface import SubtitleStyleInterface
from app.view.intelligent_video_interface import IntelligentVideoInterface
from app.view.avatar_video_interface import AvatarVideoInterface
# Removed RAG Q&A interface - functionality moved to PDF Vector DB
# from app.view.rag_qa_interface import RAGQAInterface
from app.view.pdf_vector_db_interface import PDFVectorDBInterface
from app.view.student_qa_interface import StudentQAInterface
from app.view.teacher_review_interface import TeacherReviewInterface

LOGO_PATH = ASSETS_PATH / "logo.jpg"


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()

        # Create sub-interfaces
        self.dashboardInterface = DashboardInterface(self)
        self.homeInterface = HomeInterface(self)
        self.settingInterface = SettingInterface(self)
        self.subtitleStyleInterface = SubtitleStyleInterface(self)
        self.batchProcessInterface = BatchProcessInterface(self)
        self.intelligentVideoInterface = IntelligentVideoInterface(self)
        self.avatarVideoInterface = AvatarVideoInterface(self)
        # Removed RAG Q&A interface - functionality moved to PDF Vector DB
        # self.ragQAInterface = RAGQAInterface(self)
        self.pdfVectorDBInterface = PDFVectorDBInterface(self)
        self.studentQAInterface = StudentQAInterface(self)
        self.teacherReviewInterface = TeacherReviewInterface(self)

        # Connect dashboard signals
        self.dashboardInterface.switchToInterface.connect(self.onSwitchToInterface)

        # Initialize version manager
        self.versionManager = VersionManager()
        self.versionManager.newVersionAvailable.connect(self.onNewVersion)
        self.versionManager.announcementAvailable.connect(self.onAnnouncement)

        # Create version check thread
        self.versionThread = QThread()
        self.versionManager.moveToThread(self.versionThread)
        self.versionThread.started.connect(self.versionManager.performCheck)
        self.versionThread.start()

        # Initialize navigation interface
        self.initNavigation()
        self.splashScreen.finish()

        # Register exit handler, cleanup processes
        import atexit

        atexit.register(self.stop)

    def initNavigation(self):
        """Initialize navigation bar"""
        # Add navigation items
        self.addSubInterface(self.dashboardInterface, FIF.APPLICATION, self.tr("Dashboard"))
        self.addSubInterface(self.homeInterface, FIF.HOME, self.tr("Home"))
        self.addSubInterface(self.batchProcessInterface, FIF.VIDEO, self.tr("Batch Process"))
        self.addSubInterface(self.subtitleStyleInterface, FIF.FONT, self.tr("Subtitle Style"))
        self.addSubInterface(self.intelligentVideoInterface, FIF.MOVIE, self.tr("Intelligent Video"))
        self.addSubInterface(self.avatarVideoInterface, FIF.PEOPLE, self.tr("Avatar Video"))
        # Removed RAG Q&A interface - functionality moved to PDF Vector DB
        # self.addSubInterface(self.ragQAInterface, FIF.CHAT, self.tr("RAG Q&A"))
        self.addSubInterface(self.pdfVectorDBInterface, FIF.DOCUMENT, self.tr("PDF Vector DB"))
        self.addSubInterface(self.studentQAInterface, FIF.CHAT, self.tr("Student Q&A"))
        self.addSubInterface(self.teacherReviewInterface, FIF.EDIT, self.tr("Teacher Review"))

        self.navigationInterface.addSeparator()
        self.addSubInterface(
            self.settingInterface,
            FIF.SETTING,
            self.tr("Settings"),
            NavigationItemPosition.BOTTOM,
        )

        # Set default interface
        self.switchTo(self.dashboardInterface)

    def switchTo(self, interface):
        if interface.windowTitle():
            self.setWindowTitle(interface.windowTitle())
        else:
            self.setWindowTitle(self.tr("RUII Classroom Assistant VideoCaptioner"))
        self.stackedWidget.setCurrentWidget(interface, popOut=False)

    def onSwitchToInterface(self, interface_name: str):
        """处理从Dashboard跳转到指定界面"""
        interface_map = {
            "home": self.homeInterface,
            "batch_process": self.batchProcessInterface,
            "subtitle_style": self.subtitleStyleInterface,
            "intelligent_video": self.intelligentVideoInterface,
            "avatar_video": self.avatarVideoInterface,
            "pdf_vector_db": self.pdfVectorDBInterface,
            "student_qa": self.studentQAInterface,
            "teacher_review": self.teacherReviewInterface,
            "setting": self.settingInterface,
        }
        
        target_interface = interface_map.get(interface_name)
        if target_interface:
            self.switchTo(target_interface)

    def initWindow(self):
        """Initialize window"""
        self.resize(1050, 800)
        self.setMinimumWidth(700)
        self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.setWindowTitle(self.tr("RUII Classroom Assistant VideoCaptioner"))
        
        # Apply global styles
        self.setStyleSheet(GLOBAL_STYLE)

        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))

        # Create splash screen
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(106, 106))
        self.splashScreen.raise_()

        # Set window position, center
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        self.show()
        QApplication.processEvents()


    def onNewVersion(self, version, force_update, update_info, download_url):
        """New version notification"""
        title = "New Version Available" if not force_update else "Current Version Deprecated"
        content = f"New version found {version}\n\n{update_info}"
        w = MessageBox(title, content, self)
        w.yesButton.setText("Update Now")
        w.cancelButton.setText("Later" if not force_update else "Exit")
        if w.exec():
            QDesktopServices.openUrl(QUrl(download_url))
        if force_update:
            QApplication.quit()

    def onAnnouncement(self, content):
        """Show announcement"""
        w = MessageBox("Announcement", content, self)
        w.yesButton.setText("Got it")
        w.cancelButton.hide()
        w.exec()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "splashScreen"):
            self.splashScreen.resize(self.size())

    def closeEvent(self, event):
        # Close all sub-interfaces
        # self.homeInterface.close()
        # self.batchProcessInterface.close()
        # self.subtitleStyleInterface.close()
        # self.settingInterface.close()
        super().closeEvent(event)

        # Force quit application
        QApplication.quit()

        # Ensure all threads and processes are terminated
        # import os
        # os._exit(0)

    def stop(self):
        # Find and close FFmpeg processes
        process = psutil.Process(os.getpid())
        for child in process.children(recursive=True):
            child.kill()
