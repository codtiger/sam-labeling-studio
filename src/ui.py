from typing import Optional, Union
from functools import partial
from pathlib import Path
from io import BytesIO
import os
import yaml

from PyQt6.QtWidgets import (
    QMainWindow,
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QHBoxLayout,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QListView,
    QPushButton,
    QSlider,
    QLabel,
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QPoint,
    QThread,
    pyqtSignal,
)
from PIL import Image
from PyQt6.QtGui import (
    QKeySequence,
    QPixmap,
    QIcon,
    QAction,
    QColor,
    QKeyEvent,
    QBrush,
)

from .image_viewer import ImageViewer
from .list_item_widget import CustomListItemWidget
from .threads import AsyncRemoteImageLoader, LocalImageLoader
from .sam_thread import ModelWorker
from .utils import (
    pil_to_qimage,
    read_colors,
    gray_out_icon,
    get_logger,
    svg_to_icon,
    ShapeDelegate,
    DataSource,
    ControlItem,
    MaskData,
)

logger = get_logger("Main UI")


class MainWindow(QMainWindow):

    MEMORY_LIMIT = 200
    MAX_PARALLEL_REQUESTS = 10

    trigger_embbeding = pyqtSignal(Image.Image)
    trigger_prediction = pyqtSignal(str, list, list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Annotation Platform")
        self.resize(1920, 1080)

        self.setFocus()
        config = self.__load__config("configs/app_config.yaml")
        self.color_dict = read_colors(config["label_colors_file"]) if config else {}
        # Central widget with vertical layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        self.last_directory = (
            os.environ["HOME"] + "/" + config["last_directory"] if config else ""
        )
        # Mode selection radio buttons
        mode_layout = QHBoxLayout()
        self.model_mode_radio = QRadioButton("Point/Mask Selection (Model)")
        self.manual_mode_radio = QRadioButton("Manual Annotation")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.model_mode_radio)
        self.mode_group.addButton(self.manual_mode_radio)
        mode_layout.addWidget(self.model_mode_radio)
        mode_layout.addWidget(self.manual_mode_radio)
        layout.addLayout(mode_layout)

        # Set default mode
        self.manual_mode_radio.setChecked(True)
        # Text input for model prompt
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text prompt for the model")
        layout.addWidget(self.text_input)

        # Slider for file navigation
        self.slider_layout = QHBoxLayout()
        self.back_button = QPushButton("<")
        self.back_button.setFixedWidth(30)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)  # Will update when files are loaded
        self.slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                height: 8px;
                background: #d0d0d0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #333333;
                border: 1px solid #000000;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #1E90FF;  /* Blue progress */
                border-radius: 4px;
            }
        """
        )
        self.forward_button = QPushButton(">")
        self.forward_button.setFixedWidth(30)
        self.slider_layout.addWidget(self.back_button)
        self.slider_layout.addWidget(self.slider)
        self.slider_layout.addWidget(self.forward_button)
        layout.addLayout(self.slider_layout)

        self.back_button.pressed.connect(self.go_back)
        self.forward_button.pressed.connect(self.go_forward)
        self.slider.sliderMoved.connect(self.change_img_src)

        # Filename label
        self.filename_label = QLabel("No file loaded")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.filename_label)

        # Image viewer for displaying and interacting with images
        self.image_viewer = ImageViewer(self.color_dict)
        layout.addWidget(self.image_viewer)
        self.image_viewer.setMouseTracking(True)
        self.image_viewer.setEnabled(False)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Left sidebar with QListWidget for controls
        self.control_dock = QDockWidget("", self)
        self.control_list = QListWidget()
        self.control_list.setItemDelegate(ShapeDelegate())

        # SVG for Box (square)
        mouse_svg = """
            <svg xmlns="http://www.w3.org/2000/svg" stroke="white" width="24" height="24" viewBox="0 0 24 24">
            <path stroke="white" stroke-width="1" fill="transparent" d="M4 0l16 12.279-6.951 1.17 4.325 8.817-3.596 1.734-4.35-8.879-5.428 4.702z"/>

            </svg>
        """
        mouse_icon = svg_to_icon(mouse_svg, 48)
        mouse_item = QListWidgetItem(mouse_icon, "")
        mouse_item.setToolTip("Cursor")
        mouse_item.setData(0, ControlItem.NORMAL)
        mouse_item.setData(Qt.ItemDataRole.UserRole, mouse_icon)

        self.control_list.addItem(mouse_item)
        box_svg = """

        <svg viewbox="0 0 24 24" stroke="white">
            <rect x="8" y="8" width="24" height="24" fill="none" stroke="white" stroke-width="2"/>
        </svg>
        """
        box_icon = svg_to_icon(box_svg, 48)
        box_item = QListWidgetItem(box_icon, "")
        box_item.setToolTip("Box")
        box_item.setData(0, ControlItem.BOX)
        box_item.setData(Qt.ItemDataRole.UserRole, box_icon)

        self.control_list.addItem(box_item)

        # SVG for Polygon (pentagon)
        polygon_svg = """
        <svg stroke="white" viewBox="0 0 48 48">
            <polygon points="24,4 44,18 34,40 14,40 4,18" fill="none" stroke="white" stroke-width="4"/>
        </svg>
        """
        polygon_icon = svg_to_icon(polygon_svg, 48)
        polygon_item = QListWidgetItem(polygon_icon, "")
        polygon_item.setToolTip("Polygon")
        polygon_item.setData(0, ControlItem.POLYGON)
        polygon_item.setData(Qt.ItemDataRole.UserRole, polygon_icon)

        self.control_list.addItem(polygon_item)

        zoom_in_svg = """
        <svg width="100" height="100" viewBox="0 0 24 24" fill="none"
            xmlns="http://www.w3.org/2000/svg"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
        >
                <line x1="11" y1="6" x2="11" y2="12" stroke="white" stroke-width="2"/>
                <line x1="8" y1="9" x2="14" y2="9" stroke="white" stroke-width="2"/>
            <circle cx="10" cy="10" r="7" stroke="white" stroke-width="2"/>
            <line x1="15" y1="15" x2="22" y2="22" stroke="white" stroke-width="2"/>
        </svg>
        """
        zoom_in_icon = svg_to_icon(zoom_in_svg, 48)
        zoom_in_item = QListWidgetItem(zoom_in_icon, "")
        zoom_in_item.setToolTip("Zoom In")
        zoom_in_item.setData(0, ControlItem.ZOOM_IN)
        zoom_in_item.setData(Qt.ItemDataRole.UserRole, zoom_in_icon)

        self.control_list.addItem(zoom_in_item)

        zoom_out_svg = """
        <svg width="100" height="100" viewBox="0 0 24 24" fill="none"
            xmlns="http://www.w3.org/2000/svg"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
        >
                <line x1="8" y1="9" x2="14" y2="9" stroke="white" stroke-width="2"/>
            <circle cx="10" cy="10" r="7" stroke="white" stroke-width="2"/>
            <line x1="15" y1="15" x2="22" y2="22" stroke="white" stroke-width="2"/>
        </svg>
        """
        zoom_out_icon = svg_to_icon(zoom_out_svg, 48)
        zoom_out_item = QListWidgetItem(zoom_out_icon, "")
        zoom_out_item.setToolTip("Zoom Out")
        zoom_out_item.setData(0, ControlItem.ZOOM_OUT)
        zoom_out_item.setData(Qt.ItemDataRole.UserRole, zoom_out_icon)

        self.control_list.addItem(zoom_out_item)

        roi_region_svg = """
        <svg width="100" height="100" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" >
              <rect x="12" y="5" width="11" height="7" stroke="white" stroke-width="2" fill="none"/>

              <!-- Magnifying Glass -->
                <circle cx="10" cy="10" r="7" stroke="white" stroke-width="2" fill="none"/>
                <line x1="15" y1="15" x2="22" y2="22" stroke="white" stroke-width="2"/>
            </svg>

        """
        roi_icon = svg_to_icon(roi_region_svg, 48)
        roi_item = QListWidgetItem(roi_icon, "")
        roi_item.setToolTip("Select ROI")
        roi_item.setData(0, ControlItem.ROI)
        roi_item.setData(Qt.ItemDataRole.UserRole, roi_icon)

        self.control_list.addItem(roi_item)

        star_svg = """
            <svg width="40" height="40" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <polygon points="50,5 61,39 98,39 67,60 78,95 50,75 22,95 33,60 2,39 39,39"
             fill="none" stroke="white" stroke-width="5"/>
    </svg>
        """
        star_icon = svg_to_icon(star_svg, 48)
        star_item = QListWidgetItem(star_icon, "")
        star_item.setToolTip("Point")
        star_item.setData(0, ControlItem.STAR)
        star_item.setFlags(star_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        star_item.setData(Qt.ItemDataRole.UserRole, star_icon)

        self.control_list.addItem(star_item)

        self.control_list_dict = {
            "manual": [
                mouse_item,
                box_item,
                polygon_item,
                zoom_in_item,
                zoom_out_item,
                roi_item,
            ],
            "model": [mouse_item, box_item, star_item],
        }
        self.control_list.setStyleSheet(
            """
            QListWidget::item {
                height: 56px;  /* Larger item height */
                padding: 4px;
                text-align: center;  /* Rarely affects icons, included for completeness */
            }
        """
        )
        self.control_list.itemClicked.connect(self.control_selected)
        self.control_dock.setFixedWidth(50)
        self.control_dock.setWidget(self.control_list)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.control_dock)
        # Connect mode toggle to update ImageViewer and button state
        self.model_mode_radio.toggled.connect(self.update_mode)
        self.manual_mode_radio.toggled.connect(self.update_mode)

        # Right dock widget for object list
        self.object_dock = QDockWidget("", self)
        self.anno_widget = QTabWidget()
        self.anno_widget.setStyleSheet("QTabWidget{  border:none;}")
        self.object_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.object_dock.setMinimumWidth(350)
        self.object_list = QListWidget()
        self.anno_widget.addTab(self.object_list, "Objects")

        self.issues_list = QListWidget()
        self.anno_widget.addTab(self.issues_list, "Issues")
        # self.object_list.setStyleSheet("QListWidget::item { border: 1px solid gray }")
        # self.object_list.setSizePolicy(
        #     QSizePolicy.Expanding,
        #     QSizePolicy.Expanding
        # )
        # self.object_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.object_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.object_list.currentRowChanged.connect(self.on_object_selected)
        self.object_dock.setWidget(self.anno_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.object_dock)

        # Menu bar
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.load_url_action = QAction("Load URL List", self)
        self.load_images_action = QAction("Load Images", self)
        self.load_url_action.triggered.connect(self.load_url_list)
        self.load_images_action.triggered.connect(self.show_filepicker_dialog)
        self.file_menu.addAction(self.load_url_action)
        self.file_menu.addAction(self.load_images_action)

        # Toolbar with actions
        self.toolbar = self.addToolBar("Tools")
        if self.toolbar:
            self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            self.run_model_action = QAction("Run Model", self)
            self.run_model_action.setIcon(QIcon("assets/neural_net.svg"))
            self.run_model_action.triggered.connect(self.run_model)
            self.toolbar.addAction(self.run_model_action)

            self.undo_action = QAction("Undo", self)
            self.undo_action.setIcon(QIcon("assets/undo.svg"))
            self.undo_action.setShortcut(
                QKeySequence(Qt.Key.Key_Control + Qt.Key.Key_R)
            )
            self.redo_action = QAction("Redo", self)
            self.redo_action.setIcon(QIcon("assets/redo.svg"))
            self.undo_action.setShortcut(
                QKeySequence(Qt.Key.Key_Control + Qt.Key.Key_Shift + Qt.Key.Key_R)
            )
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.toolbar.addAction(self.undo_action)
            self.toolbar.addAction(self.redo_action)

        # async loader
        self.async_remote_loader = None
        self.loader_thread: Optional[QThread] = None
        # Data storage
        self.prev_selected_obj_idx = None
        self.data_source = DataSource.LOCAL
        self.urls = []  # List of image URLs
        self.images = [None] * MainWindow.MEMORY_LIMIT  # List of PIL.Image objects
        self.start_idx, self.end_idx = 0, MainWindow.MEMORY_LIMIT

        self.current_idx = 0  # Index of the current image
        self.annotations = {}  # Dictionary to store annotations
        self.current_image = None  # Current PIL image
        # Initial update to set button state
        self.update_mode()

        # signal connectors
        self.image_viewer.object_added.connect(self.add_to_object_list)
        self.image_viewer.control_change.connect(self.set_control)

        # Initiate model
        self.model_loaded, self.is_embedded = False, False
        self.ckpt_path = "weights/sam2.1_hiera_large.pt"
        self.model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"
        self.model_thread = None
        self.__init_model_thread__()

    def __init_model_thread__(self):
        self.model_thread = QThread()
        self.model_worker = ModelWorker(
            device="mps", ckpt_path=self.ckpt_path, cfg_path=self.model_cfg
        )
        self.model_worker.moveToThread(self.model_thread)
        self.model_thread.started.connect(self.model_worker.load_model)

        self.model_worker.model_ready.connect(self.on_model_ready)
        self.model_worker.image_embedded.connect(self.on_image_embedded)
        self.model_worker.prediction_done.connect(self.on_model_result)

        self.trigger_embbeding.connect(self.model_worker.set_image)
        self.trigger_prediction.connect(self.model_worker.predict)

        self.model_thread.start()

    # def __calc_embedding__(self, image):
    #     embedding_worker = EmbeddingWorker(self.model, image)
    #     embedding_worker.signals.finished.connect(self.store_predictor)
    #     if self.thread_pool:
    #         self.thread_pool.start(embedding_worker)

    def on_model_ready(self):
        logger.warning("MODEL LOADED")
        self.model_loaded = True

    def on_image_embedded(self):
        self.run_model_action.setEnabled(True)
        self.is_embedded = True

    def __load__config(self, yaml_path):

        with open(yaml_path, "r") as stream:
            try:
                config_dict = yaml.safe_load(stream)
                return config_dict
            except yaml.YAMLError as exc:
                self.close()

    def update_mode(self):
        """Update ImageViewer mode and Run Model button state based on radio selection."""
        if self.model_mode_radio.isChecked():
            self.image_viewer.set_mode("model")
            if self.is_embedded:
                self.run_model_action.setEnabled(True)

            # Enable and disable items based on mode
            for item in self.control_list_dict["manual"]:
                # Set the grayed-out icon
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setIcon(gray_out_icon(item.data(Qt.ItemDataRole.UserRole)))

            for item in self.control_list_dict["model"]:
                # Restore the original icon
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable)
                item.setIcon(item.data(Qt.ItemDataRole.UserRole))

        else:  # manual_mode_radio is checked
            self.image_viewer.set_mode("manual")
            self.image_viewer.clear_prompts()
            self.run_model_action.setEnabled(False)

            # Enable and disable items based on mode
            for item in self.control_list_dict["model"]:
                # Set the grayed-out icon
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setIcon(gray_out_icon(item.data(Qt.ItemDataRole.UserRole)))

            for item in self.control_list_dict["manual"]:
                # Restore the original icon
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable)
                item.setIcon(item.data(Qt.ItemDataRole.UserRole))

        # Refresh the control list to apply visual changes
        self.control_list.viewport().update()

    def load_url_list(self):
        """Load a text file containing image URLs."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select URL List",
            str(self.last_directory),
            "Text files (*.txt)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_name:
            self.last_directory = Path(file_name).parent
            with open(file_name, "r") as f:
                self.urls = [line.strip() for line in f if line.strip()]
            self.current_idx = 0
            self.images = [None] * self.MEMORY_LIMIT
            # if user rushes to select new files or urls, this should be set to None
            self.current_image = None

            self.data_source = DataSource.URL_REQUEST
            if self.urls:
                self.slider.setMaximum(len(self.urls) - 1)
                self.slider.setValue(self.current_idx)
                self.update_filename_label()
                if (
                    self.loader_thread is not None
                    and self.async_remote_loader is not None
                ) and self.loader_thread.isRunning():
                    self.async_remote_loader.stop()
                    self.loader_thread.quit()
                    self.loader_thread.wait()
                    del self.async_remote_loader
                self.load_image_from_url(self.urls[self.start_idx : self.end_idx])

    def show_filepicker_dialog(self):
        self.urls, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            str(self.last_directory),
            "Images (*.png *.jpg)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        self.images = [None] * self.MEMORY_LIMIT
        # if user rushes to select new files or urls, this should be set to None
        self.current_image = None
        if len(self.urls) != 0:
            self.last_directory = Path(self.urls[0]).parent
            self.current_idx = 0
            self.data_source = DataSource.LOCAL

            # change slider data
            self.slider.setMaximum(len(self.urls) - 1)
            self.slider.setValue(self.current_idx)
            self.update_filename_label()

            self.load_images_local(self.urls[self.start_idx : self.end_idx])

    # def update_prompt_mode(self, text):
    #     self.image_viewer.switch_model_prompt(text)

    def show_label_combobox(self):
        """Show a QComboBox with labels at the mouse position."""
        combo = QComboBox(self)
        labels = list(self.color_dict.keys())
        combo.addItems(labels)
        combo.setFixedWidth(150)  # Small window size

        # Position above the mouse cursor
        mouse_pos = self.mapFromGlobal(QPoint(self.cursor().pos()))
        combo.move(mouse_pos - QPoint(0, combo.height() + 5))  # 5px above mouse
        combo.showPopup()  # Show dropdown immediately
        combo.activated.connect(
            lambda _: self.image_viewer.set_last_label(combo.currentText())
        )

    def load_image_from_url(self, urls):
        """Start a thread to load an image from a URL."""
        self.async_remote_loader = AsyncRemoteImageLoader(
            urls, self.MAX_PARALLEL_REQUESTS, self.images
        )
        self.loader_thread = QThread()
        self.async_remote_loader.moveToThread(self.loader_thread)
        self.async_remote_loader.image_loaded.connect(self.on_image_loaded)
        self.async_remote_loader.error_occurred.connect(self.on_image_load_error)
        self.loader_thread.started.connect(self.async_remote_loader.run)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)

        self.loader_thread.start()

    def stop_asyc_loader(self):
        if self.async_remote_loader:
            self.async_remote_loader.stop()

    def on_image_loaded(self, url, image):
        # self.images.append(image)
        if self.current_image is None:
            self.load_viewer(image)

    def on_image_load_error(self, url, error):
        logger.error(f"Failed to load image: {url} ; Error: {error}")

    def load_images_local(self, paths):
        self.local_thread = LocalImageLoader(paths, self.images)
        self.local_thread.image_loaded.connect(self.load_viewer)
        self.local_thread.start()

    def load_viewer(self, image: Image.Image):
        """Handle the loaded image by displaying it."""
        self.image_viewer.setEnabled(False)
        self.current_image = image
        qimage = pil_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)
        self.image_viewer.clear()
        self.object_list.clearSelection()
        self.object_list.clear()
        self.image_viewer.set_image(pixmap)
        self.update_filename_label()
        self.image_viewer.setEnabled(True)
        # Load the embedding
        if self.model_loaded:
            self.trigger_embbeding.emit(image)
        self.prev_selected_obj_idx = None

    def change_img_src(self, index):
        if 0 <= index < len(self.urls) and index != self.current_idx:
            # save annotations for current image
            self.save_annotations()
            # load anno for next
            self.current_idx = index
            # reset run_model action until embedding calculated
            self.run_model_action.setEnabled(False)

            if (self.current_idx >= self.start_idx) and (
                self.current_idx < self.end_idx
            ):
                self.load_viewer(
                    self.images[self.current_idx % MainWindow.MEMORY_LIMIT]
                )
            elif self.current_idx >= self.end_idx:
                self.start_idx, self.end_idx = (
                    self.current_idx,
                    self.current_idx + MainWindow.MEMORY_LIMIT,
                )
                if self.data_source == DataSource.LOCAL:
                    self.load_images_local(self.urls[self.start_idx : self.end_idx])
                elif self.data_source == DataSource.URL_REQUEST:
                    self.load_image_from_url(self.urls[self.start_idx : self.end_idx])
            elif self.current_idx < self.start_idx:
                # for now do above
                # TODO: change to loading from [current_idx, end_idx - (start_idx - current_idx)]
                self.start_idx, self.end_idx = (
                    self.current_idx,
                    self.current_idx + MainWindow.MEMORY_LIMIT,
                )
                if self.data_source == DataSource.LOCAL:
                    self.load_images_local(self.urls[self.start_idx : self.end_idx])
                elif self.data_source == DataSource.URL_REQUEST:
                    self.load_image_from_url(self.urls[self.start_idx : self.end_idx])
            self.load_annotations(self.current_idx)
            return 0
        return 1

    def go_back(self):
        ret = self.change_img_src(self.current_idx - 1)
        if ret == 0:
            self.slider.setValue(self.current_idx)
        # if self.current_idx > 0:
        #     self.current_idx -= 1
        #     if self.current_idx >= self.start_idx:
        #         self.load_viewer(self.images[self.current_idx])
        #     if
        #     self.slider.setValue(self.current_idx)
        #     self.load_image(self.urls[self.current_idx])

    def go_forward(self):
        ret = self.change_img_src(self.current_idx + 1)
        if ret == 0:
            self.slider.setValue(self.current_idx)

    def update_filename_label(self):
        if self.urls and 0 <= self.current_idx < len(self.urls):
            filename = os.path.basename(self.urls[self.current_idx])
            self.filename_label.setText(filename)
        else:
            self.filename_label.setText("No file loaded")

    def run_model(self):
        """Run the segmentation model with user inputs."""
        if not self.current_image:
            return
        text = self.text_input.text()
        points = self.image_viewer.prompt_star_coords
        boxes = self.image_viewer.prompt_box_coords
        self.model_worker.predict(
            text, points, boxes if boxes != [] else [None] * len(points)
        )
        # TODO: Change this to something like thread.join() or emitting a signal from thread

    def on_model_result(self, polygons):
        """Display model results and populate the object list."""
        masks: list[MaskData] = self.image_viewer.add_prediction_polys(polygons)
        for mask in masks:
            self.add_to_object_list(mask)
        self.image_viewer.clear_prompts()

    def delete_object(self, item: QListWidgetItem, mask_id: int):
        self.image_viewer.removePolygon(item.data(Qt.ItemDataRole.UserRole))
        self.object_list.takeItem(self.object_list.row(item))

    def change_object_label(self, item: QListWidgetItem, label_text):
        self.image_viewer.changePolygonLabel(
            item.data(Qt.ItemDataRole.UserRole), label_text
        )
        # item = self.object_list.item(poly_idx)
        if item:
            item.setData(Qt.ItemDataRole.UserRole + 1, label_text)
            item.setBackground(QColor(*self.color_dict[label_text] + (50,)))

    def add_to_object_list(self, shape_dict: MaskData):
        custom_widget = CustomListItemWidget(list(self.color_dict.keys()))

        custom_widget.setupFields(shape_dict.id, shape_dict.label, "Polygon")
        item = QListWidgetItem("")
        item.setData(Qt.ItemDataRole.UserRole, shape_dict.id)
        item.setData(Qt.ItemDataRole.UserRole + 1, shape_dict.label)
        item.setSizeHint(custom_widget.sizeHint())

        # item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setBackground(QColor(*self.color_dict[shape_dict.label] + (50,)))
        self.object_list.addItem(item)
        custom_widget.deleted.connect(partial(self.delete_object, item))
        self.object_list.setItemWidget(item, custom_widget)

        custom_widget.label_combo_box.currentTextChanged.connect(
            partial(self.change_object_label, item)
        )

    def on_object_selected(self, index):
        """Highlight the selected object's polygon."""
        # TODO: Stop using index to communicate with the ImageView for polys.
        # Obtain their shape.id from a constructed dict
        if index == -1:
            return
        item = self.object_list.item(index)
        if item:
            if self.prev_selected_obj_idx is not None:
                prev_item = self.object_list.item(self.prev_selected_obj_idx)
                if prev_item:
                    self.image_viewer.unhighlight_polygon(
                        prev_item.data(Qt.ItemDataRole.UserRole)
                    )
            self.image_viewer.highlight_polygon(item.data(Qt.ItemDataRole.UserRole))
            item.setForeground(QColor("Blue"))
            self.prev_selected_obj_idx = index

    def control_selected(self, item: QListWidgetItem):
        """Update the ImageViewer's control based on list selection."""
        control = item.data(0)  # "box" or "polygon"
        if control == ControlItem.BOX or control == ControlItem.POLYGON:
            if self.manual_mode_radio.isChecked():
                self.show_label_combobox()
            self.image_viewer.set_control(control)
        elif control == ControlItem.ROI:
            self.image_viewer.set_control(control)
        elif control == ControlItem.ZOOM_IN:
            self.image_viewer.zoom(control)
            self.control_list.setCurrentRow(0)
        elif control == ControlItem.ZOOM_OUT:
            self.image_viewer.zoom(control)
            self.control_list.setCurrentRow(0)
        elif control == ControlItem.NORMAL:
            self.image_viewer.set_control(control)
        elif control == ControlItem.STAR:
            self.image_viewer.set_control(control)

    def set_control(self, control: ControlItem):
        self.control_list.setCurrentRow(control.value.real)

    def save_annotations(self):
        objects = []
        image_url = self.urls[self.current_idx]
        for i in range(self.object_list.count()):
            logger.debug(
                f"Number of objects in object_list: {self.object_list.count()}"
            )
            row = self.object_list.item(i)
            if row:
                id = row.data(Qt.ItemDataRole.UserRole)
                label = row.data(Qt.ItemDataRole.UserRole + 1)
                polygon = self.image_viewer.id_to_poly[id].polygon()
                polygon_points = [[p.x(), p.y()] for p in polygon]
                objects.append({"id": id, "label": label, "polygon": polygon_points})
        self.annotations[image_url] = {"objects": objects}
        self.current_idx += 1

    def load_annotations(self, index):
        anno = self.annotations.get(self.urls[index], None)
        if anno:
            mask_data_list = [
                MaskData(
                    mask_id=obj["id"],
                    points=obj["polygon"],
                    label=obj["label"],
                )
                for obj in anno["objects"]
            ]
            self.image_viewer.display_polygons(mask_data_list)
            for mask_data in mask_data_list:
                self.add_to_object_list(mask_data)

    def keyPressEvent(self, a0: Optional[QKeyEvent]) -> None:
        if a0 is not None:
            if a0.key() == Qt.Key.Key_Right:
                self.go_forward()
            if a0.key() == Qt.Key.Key_Left:
                self.go_back()

        return super().keyPressEvent(a0)
