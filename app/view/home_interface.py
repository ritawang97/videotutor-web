from PyQt5.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import SegmentedWidget

from app.core.task_factory import TaskFactory
from app.view.subtitle_interface import SubtitleInterface
from app.view.task_creation_interface import TaskCreationInterface
from app.view.transcription_interface import TranscriptionInterface
from app.view.video_synthesis_interface import VideoSynthesisInterface
from app.view.pdf_processing_interface import PDFProcessingInterface


class HomeInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set object name and style
        self.setObjectName("HomeInterface")
        self.setStyleSheet(
            """
            HomeInterface{background: white}
        """
        )

        # Create segmented control and stacked widget
        self.pivot = SegmentedWidget(self)
        self.pivot.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        # Add sub-interfaces
        self.task_creation_interface = TaskCreationInterface(self)
        self.pdf_processing_interface = PDFProcessingInterface(self)
        self.transcription_interface = TranscriptionInterface(self)
        self.subtitle_optimization_interface = SubtitleInterface(self)
        self.video_synthesis_interface = VideoSynthesisInterface(self)

        self.addSubInterface(
            self.task_creation_interface, "TaskCreationInterface", self.tr("Task Creation")
        )
        self.addSubInterface(
            self.pdf_processing_interface, "PDFProcessingInterface", self.tr("PDF Transcript")
        )
        self.addSubInterface(
            self.transcription_interface, "TranscriptionInterface", self.tr("Speech Transcription")
        )
        self.addSubInterface(
            self.subtitle_optimization_interface,
            "SubtitleInterface",
            self.tr("Subtitle Optimization & Translation"),
        )
        self.addSubInterface(
            self.video_synthesis_interface,
            "VideoSynthesisInterface",
            self.tr("Video Synthesis"),
        )

        self.vBoxLayout.addWidget(self.pivot)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(30, 10, 30, 30)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.task_creation_interface)
        self.pivot.setCurrentItem("TaskCreationInterface")

        self.task_creation_interface.finished.connect(self.switch_to_transcription)
        self.transcription_interface.finished.connect(
            self.switch_to_subtitle_optimization
        )
        self.subtitle_optimization_interface.finished.connect(
            self.switch_to_video_synthesis
        )

    def switch_to_transcription(self, file_path):
        # Switch to transcription interface
        transcribe_task = TaskFactory.create_transcribe_task(
            file_path, need_next_task=True
        )
        self.transcription_interface.set_task(transcribe_task)
        self.transcription_interface.process()
        self.stackedWidget.setCurrentWidget(self.transcription_interface)
        self.pivot.setCurrentItem("TranscriptionInterface")

    def switch_to_subtitle_optimization(self, file_path, video_path):
        # Switch to subtitle processing interface
        subtitle_task = TaskFactory.create_subtitle_task(
            file_path, video_path, need_next_task=True
        )
        self.subtitle_optimization_interface.set_task(subtitle_task)
        self.subtitle_optimization_interface.process()
        self.stackedWidget.setCurrentWidget(self.subtitle_optimization_interface)
        self.pivot.setCurrentItem("SubtitleInterface")

    def switch_to_video_synthesis(self, video_path, subtitle_path):
        # Switch to video synthesis interface
        synthesis_task = TaskFactory.create_synthesis_task(
            video_path, subtitle_path, need_next_task=True
        )
        self.video_synthesis_interface.set_task(synthesis_task)
        self.video_synthesis_interface.process()
        self.stackedWidget.setCurrentWidget(self.video_synthesis_interface)
        self.pivot.setCurrentItem("VideoSynthesisInterface")

    def addSubInterface(self, widget, objectName, text):
        # Add sub-interface to stacked widget and segmented control
        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        # When the current index of stacked widget changes, update the current item of segmented control
        widget = self.stackedWidget.widget(index)
        if widget:
            self.pivot.setCurrentItem(widget.objectName())

    def closeEvent(self, event):
        # Close event, close all sub-interfaces
        self.task_creation_interface.close()
        self.pdf_processing_interface.close()
        self.transcription_interface.close()
        self.subtitle_optimization_interface.close()
        self.video_synthesis_interface.close()
        super().closeEvent(event)
