import os

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    ProgressBar,
    PushButton,
    RoundMenu,
    TableWidget,
)
from qfluentwidgets import (
    FluentIcon as FIF,
)

from app.core.entities import (
    BatchTaskStatus,
    BatchTaskType,
    SupportedAudioFormats,
    SupportedSubtitleFormats,
    SupportedVideoFormats,
)
from app.thread.batch_process_thread import (
    BatchProcessThread,
    BatchTask,
)


class BatchProcessInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("batchProcessInterface")
        self.setWindowTitle(self.tr("Batch Process"))
        self.setAcceptDrops(True)
        self.batch_thread = BatchProcessThread()

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # Top control area
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        # Task type selection
        self.task_type_combo = ComboBox()
        self.task_type_combo.addItems([str(task_type) for task_type in BatchTaskType])
        self.task_type_combo.setCurrentText(str(BatchTaskType.FULL_PROCESS))

        # Control buttons
        self.add_file_btn = PushButton("Add Files", icon=FIF.ADD)
        self.start_all_btn = PushButton("Start Processing", icon=FIF.PLAY)
        self.clear_btn = PushButton("Clear List", icon=FIF.DELETE)

        # Add to top layout
        top_layout.addWidget(self.task_type_combo)
        top_layout.addWidget(self.add_file_btn)
        top_layout.addWidget(self.clear_btn)

        top_layout.addStretch()
        top_layout.addWidget(self.start_all_btn)

        # Create task table
        self.task_table = TableWidget()
        self.task_table.setColumnCount(3)
        self.task_table.setHorizontalHeaderLabels(["File Name", "Progress", "Status"])

        # Set table style
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.task_table.setColumnWidth(1, 250)  # Progress bar列宽
        self.task_table.setColumnWidth(2, 160)  # Status列宽

        # Set row height
        self.task_table.verticalHeader().setDefaultSectionSize(40)  # Set default row height

        # Set table border
        self.task_table.setBorderVisible(True)
        self.task_table.setBorderRadius(12)

        # Set table non-editable
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Set table size policy
        self.task_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.task_table.setMinimumHeight(300)  # Set minimum height

        # Connect double-click signal
        self.task_table.doubleClicked.connect(self.on_table_double_clicked)

        # Add to main layout
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.task_table)

        # Connect signals
        self.add_file_btn.clicked.connect(self.on_add_file_clicked)
        self.start_all_btn.clicked.connect(self.start_all_tasks)
        self.clear_btn.clicked.connect(self.clear_tasks)
        self.task_type_combo.currentTextChanged.connect(self.on_task_type_changed)

    def setup_connections(self):
        # Batch processing thread signal connections
        self.batch_thread.task_progress.connect(self.update_task_progress)
        self.batch_thread.task_error.connect(self.on_task_error)
        self.batch_thread.task_completed.connect(self.on_task_completed)

        # Table right-click menu
        self.task_table.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.task_table.customContextMenuRequested.connect(self.show_context_menu)

    def on_add_file_clicked(self):
        task_type = self.task_type_combo.currentText()
        file_filter = ""
        if task_type in [
            BatchTaskType.TRANSCRIBE,
            BatchTaskType.TRANS_SUB,
            BatchTaskType.FULL_PROCESS,
        ]:
            # Get all supported audio/video formats
            audio_formats = [f"*.{fmt.value}" for fmt in SupportedAudioFormats]
            video_formats = [f"*.{fmt.value}" for fmt in SupportedVideoFormats]
            formats = audio_formats + video_formats
            file_filter = f"Audio/Video Files ({' '.join(formats)})"
        elif task_type == BatchTaskType.SUBTITLE:
            # Get all supported subtitle formats
            subtitle_formats = [f"*.{fmt.value}" for fmt in SupportedSubtitleFormats]
            file_filter = f"Subtitle Files ({' '.join(subtitle_formats)})"

        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", file_filter)
        if files:
            self.add_files(files)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files(files)

    def add_files(self, file_paths):
        task_type = BatchTaskType(self.task_type_combo.currentText())

        # Check if files exist and collect non-existent files
        non_existent_files = []
        valid_files = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                non_existent_files.append(os.path.basename(file_path))
            else:
                valid_files.append(file_path)

        # 如果有不存在的文件，显示Warning
        if non_existent_files:
            InfoBar.warning(
                title="File does not exist",
                content=f"以下File does not exist：\n{', '.join(non_existent_files)}",
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self,
            )

        # If no valid files, return directly
        if not valid_files:
            return

        # 对有效文件按File Name排序
        valid_files.sort(key=lambda x: os.path.basename(x).lower())

        # If table is empty, auto-detect file type and set task type
        if self.task_table.rowCount() == 0 and self.task_type_combo.currentIndex() == 0:
            first_file = valid_files[0].lower()
            is_subtitle = any(
                first_file.endswith(f".{fmt.value}") for fmt in SupportedSubtitleFormats
            )
            if is_subtitle:
                self.task_type_combo.setCurrentText(str(BatchTaskType.SUBTITLE))
                task_type = BatchTaskType.SUBTITLE
            # elif is_media:
            #     self.task_type_combo.setCurrentText(str(BatchTaskType.FULL_PROCESS))
            #     task_type = BatchTaskType.FULL_PROCESS

        # Filter file types
        valid_files = self.filter_files(valid_files, task_type)

        if not valid_files:
            InfoBar.warning(
                title="Invalid Files",
                content="Please select correct file type",
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        for file_path in valid_files:
            # Check if same task already exists
            exists = False
            for row in range(self.task_table.rowCount()):
                if self.task_table.item(row, 0).toolTip() == file_path:
                    exists = True
                    InfoBar.warning(
                        title="Task already exists",
                        content="Task already exists",
                        duration=2000,
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self,
                    )
                    break

            if not exists:
                self.add_task_to_table(file_path)

    def filter_files(self, file_paths, task_type: BatchTaskType):
        valid_extensions = {}

        # Set valid extensions based on task type
        if task_type in [
            BatchTaskType.TRANSCRIBE,
            BatchTaskType.TRANS_SUB,
            BatchTaskType.FULL_PROCESS,
        ]:
            valid_extensions = {f".{fmt.value}" for fmt in SupportedAudioFormats} | {
                f".{fmt.value}" for fmt in SupportedVideoFormats
            }
        elif task_type == BatchTaskType.SUBTITLE:
            valid_extensions = {f".{fmt.value}" for fmt in SupportedSubtitleFormats}

        return [
            f
            for f in file_paths
            if any(f.lower().endswith(ext) for ext in valid_extensions)
        ]

    def add_task_to_table(self, file_path):
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)

        # File Name
        file_name = QTableWidgetItem(os.path.basename(file_path))
        file_name.setToolTip(file_path)
        self.task_table.setItem(row, 0, file_name)

        # Progress bar
        progress_bar = ProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setFixedHeight(18)
        self.task_table.setCellWidget(row, 1, progress_bar)

        # Status
        status = QTableWidgetItem(str(BatchTaskStatus.WAITING))
        status.setTextAlignment(Qt.AlignCenter)  # type: ignore
        status.setForeground(Qt.gray)  # type: ignore  # Set font color to gray
        font = QFont()
        font.setBold(True)
        status.setFont(font)
        self.task_table.setItem(row, 2, status)

    def show_context_menu(self, pos):
        row = self.task_table.rowAt(pos.y())
        if row < 0:
            return

        menu = RoundMenu(parent=self)
        file_path = self.task_table.item(row, 0).toolTip()
        status = self.task_table.item(row, 2).text()

        start_action = Action(FIF.PLAY, "Start")
        start_action.triggered.connect(lambda: self.start_task(file_path))
        menu.addAction(start_action)

        cancel_action = Action(FIF.CLOSE, "Cancel")
        cancel_action.triggered.connect(lambda: self.cancel_task(file_path))
        menu.addAction(cancel_action)

        menu.addSeparator()
        open_folder_action = Action(FIF.FOLDER, "Open Output Folder")
        open_folder_action.triggered.connect(lambda: self.open_output_folder(file_path))
        menu.addAction(open_folder_action)

        if status != str(BatchTaskStatus.WAITING):
            start_action.setEnabled(False)

        menu.exec_(self.task_table.viewport().mapToGlobal(pos))

    def open_output_folder(self, file_path: str):
        # Determine output folder based on task type and file path
        task_type = BatchTaskType(self.task_type_combo.currentText())
        file_dir = os.path.dirname(file_path)

        if task_type == BatchTaskType.FULL_PROCESS:
            # For full process tasks, output in same directory as video
            output_dir = file_dir
        else:
            # Other tasks output in same directory as file
            output_dir = file_dir

        # Open Folder
        QDesktopServices.openUrl(QUrl.fromLocalFile(output_dir))

    def update_task_progress(self, file_path: str, progress: int, status: str):
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).toolTip() == file_path:
                # 更新Progress bar
                progress_bar = self.task_table.cellWidget(row, 1)
                progress_bar.setValue(progress)
                # 更新Status
                self.task_table.item(row, 2).setText(status)
                break

    def on_task_error(self, file_path: str, error: str):
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).toolTip() == file_path:
                status_item = self.task_table.item(row, 2)
                status_item.setText(str(BatchTaskStatus.FAILED))
                status_item.setToolTip(error)
                break

    def on_task_completed(self, file_path: str):
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).toolTip() == file_path:
                self.task_table.item(row, 2).setText(str(BatchTaskStatus.COMPLETED))
                self.task_table.item(row, 2).setForeground(QColor("#4a90e2"))
                break

    def start_all_tasks(self):
        # Check if there are tasks
        if self.task_table.rowCount() == 0:
            InfoBar.warning(
                title="No Tasks",
                content="Please add files to process first",
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        # Check if there are pending tasks
        waiting_tasks = 0
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 2).text() == str(BatchTaskStatus.WAITING):
                waiting_tasks += 1

        if waiting_tasks == 0:
            InfoBar.warning(
                title="No Pending Tasks",
                content="All tasks are processing or completed",
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        # 显示Start Processing的Tip
        InfoBar.success(
            title="Start Processing",
            content=f"Start Processing {waiting_tasks} tasks",
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self,
        )
        # Start Processing任务
        for row in range(self.task_table.rowCount()):
            file_path = self.task_table.item(row, 0).toolTip()
            status = self.task_table.item(row, 2).text()
            if status == str(BatchTaskStatus.WAITING):
                task_type = BatchTaskType(self.task_type_combo.currentText())
                batch_task = BatchTask(file_path, task_type)
                self.batch_thread.add_task(batch_task)

    def start_task(self, file_path: str):
        # 显示Start Processing的Tip
        file_name = os.path.basename(file_path)
        InfoBar.success(
            title="Start Processing",
            content=f"Start Processing文件：{file_name}",
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self,
        )

        # Create and add single task
        task_type = BatchTaskType(self.task_type_combo.currentText())
        batch_task = BatchTask(file_path, task_type)
        self.batch_thread.add_task(batch_task)

    def cancel_task(self, file_path: str):
        self.batch_thread.stop_task(file_path)
        # Remove task from table
        for row in range(self.task_table.rowCount()):
            if self.task_table.item(row, 0).toolTip() == file_path:
                self.task_table.removeRow(row)
                break

    def clear_tasks(self):
        self.batch_thread.stop_all()
        self.task_table.setRowCount(0)

    def on_task_type_changed(self, task_type):
        # Clear current task list
        self.clear_tasks()

    def closeEvent(self, event):
        self.batch_thread.stop_all()
        super().closeEvent(event)

    def on_table_double_clicked(self, index):
        """Handle table double-click event"""
        row = index.row()
        file_path = self.task_table.item(row, 0).toolTip()
        self.open_output_folder(file_path)
