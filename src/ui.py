from typing import Optional
from enum import Enum
from queue import Queue
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
from PyQt6.QtCore import QFile, Qt, QSize, QPoint
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QAction, QColor, QKeyEvent
from PyQt6.QtSvg import QSvgRenderer

from .image_viewer import ImageViewer, MaskData
from .list_item_widget import CustomListItemWidget
from .threads import ImageLoaderThread, ModelThread, ImageLocalLoaderThread
from .utils import pil_to_qimage, ShapeDelegate, read_colors


class DataSource(Enum):
    URL_REQUEST = 0
    LOCAL = 1


class ControlItem(Enum):
    NORMAL = 0
    BOX = 1
    POLYGON = 2
    ZOOM = 3


class MainWindow(QMainWindow):

    MEMORY_LIMIT = 30

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Annotation Platform")
        self.resize(1920, 1080)

        self.setFocus()
        config = self.__load__config("config.yaml")
        self.color_dict = read_colors(config["label_colors_file"]) if config else {}
        # Central widget with vertical layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        self.last_directory = config["last_directory"] if config else ""
        # Mode selection radio buttons
        mode_layout = QHBoxLayout()
        self.model_mode_radio = QRadioButton("Point/Mask Selection (Model)")
        self.manual_mode_radio = QRadioButton("Manual Annotation")
        self.manual_prompt_combo = QComboBox()
        self.manual_prompt_combo.addItems(["Points", "Boxes"])
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.model_mode_radio)
        self.mode_group.addButton(self.manual_mode_radio)
        mode_layout.addWidget(self.model_mode_radio)
        mode_layout.addWidget(self.manual_mode_radio)
        mode_layout.addWidget(self.manual_prompt_combo)
        layout.addLayout(mode_layout)

        # Set default mode
        self.model_mode_radio.setChecked(True)
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
        mouse_icon = self.svg_to_icon(mouse_svg, 48)
        mouse_item = QListWidgetItem(mouse_icon, "")
        mouse_item.setToolTip("Mouse")

        self.control_list.addItem(mouse_item)
        box_svg = """

        <svg viewbox="0 0 24 24" stroke="white">
            <rect x="8" y="8" width="24" height="24" fill="none" stroke="white" stroke-width="2"/>
        </svg>
        """
        box_icon = self.svg_to_icon(box_svg, 48)
        box_item = QListWidgetItem(box_icon, "")
        box_item.setToolTip("Box")

        self.control_list.addItem(box_item)

        # SVG for Polygon (pentagon)
        polygon_svg = """
        <svg stroke="white" viewBox="0 0 48 48">
            <polygon points="24,4 44,18 34,40 14,40 4,18" fill="none" stroke="white" stroke-width="4"/>
        </svg>
        """
        polygon_icon = self.svg_to_icon(polygon_svg, 48)
        polygon_item = QListWidgetItem(polygon_icon, "")
        polygon_item.setToolTip("Polygon")
        self.control_list.addItem(polygon_item)

        magnifier_svg = """
        <svg width="100" height="100" viewBox="0 0 24 24" fill="none"
            xmlns="http://www.w3.org/2000/svg"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
        >
            <circle cx="10" cy="10" r="7" stroke="white" stroke-width="2"/>
            <line x1="15" y1="15" x2="22" y2="22" stroke="white" stroke-width="2"/>
        </svg>
        """
        magnifier_icon = self.svg_to_icon(magnifier_svg, 48)
        magnifier_item = QListWidgetItem(magnifier_icon, "")
        magnifier_item.setToolTip("Zoom")
        self.control_list.addItem(magnifier_item)

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
        self.manual_prompt_combo.currentTextChanged.connect(self.update_prompt_mode)
        self.model_mode_radio.toggled.connect(self.update_mode)
        self.manual_mode_radio.toggled.connect(self.update_mode)

        # Right dock widget for object list
        self.object_dock = QDockWidget("Objects", self)
        self.object_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.object_dock.setMinimumWidth(350)
        self.object_list = QListWidget()
        # self.object_list.setStyleSheet("QListWidget::item { border: 1px solid gray }")
        # self.object_list.setSizePolicy(
        #     QSizePolicy.Expanding,
        #     QSizePolicy.Expanding
        # )
        # self.object_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.object_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.object_list.currentRowChanged.connect(self.on_object_selected)
        self.object_dock.setWidget(self.object_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.object_dock)

        # Menu bar
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.load_url_action = QAction("Load URL List", self)
        self.load_images_action = QAction("Load Images", self)
        self.load_url_action.triggered.connect(self.load_url_list)
        self.load_images_action.triggered.connect(self.load_images)
        self.file_menu.addAction(self.load_url_action)
        self.file_menu.addAction(self.load_images_action)

        # Toolbar with actions
        self.toolbar = self.addToolBar("Tools")
        self.run_model_action = QAction("Run Model", self)
        self.run_model_action.triggered.connect(self.run_model)
        self.toolbar.addAction(self.run_model_action)

        # Data storage
        self.prev_selected_obj_idx = None
        self.data_source = DataSource.LOCAL
        self.urls = []  # List of image URLs
        self.images = [[]] * MainWindow.MEMORY_LIMIT  # List of PIL.Image objects
        self.start_idx, self.end_idx = 0, MainWindow.MEMORY_LIMIT

        self.current_idx = 0  # Index of the current image
        self.annotations = {}  # Dictionary to store annotations
        self.current_image = None  # Current PIL image
        # Initial update to set button state
        self.update_mode()

        # signal connectors
        self.image_viewer.object_added.connect(self.add_to_object_list)

    def __load__config(self, yaml_path):

        with open(yaml_path, "r") as stream:
            try:
                config_dict = yaml.safe_load(stream)
                return config_dict
            except yaml.YAMLError as exc:
                self.close()

    def svg_to_icon(self, svg_string, size):
        """Convert an SVG string to a QIcon."""
        renderer = QSvgRenderer(bytearray(svg_string.encode("utf-8")))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def update_mode(self):
        """Update ImageViewer mode and Run Model button state based on radio selection."""
        if self.model_mode_radio.isChecked():
            self.image_viewer.set_mode("model")
            self.manual_prompt_combo.setEnabled(True)
            self.run_model_action.setEnabled(True)
            self.control_dock.setEnabled(False)
            self.control_list.clearSelection()  # Clear selection in model mode
        else:  # manual_mode_radio is checked
            self.image_viewer.set_mode("manual")
            self.run_model_action.setEnabled(False)
            self.manual_prompt_combo.setEnabled(False)
            self.control_dock.setEnabled(True)

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
            self.data_source = DataSource.URL_REQUEST
            if self.urls:
                self.slider.setMaximum(len(self.urls) - 1)
                self.slider.setValue(self.current_idx)
                self.update_filename_label()
                self.load_image_from_url(self.urls[self.current_idx])

    def load_images(self):
        self.urls, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Images",
            str(self.last_directory),
            "Images (*.png *.jpg)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if len(self.urls) != 0:
            self.last_directory = Path(self.urls[0]).parent
            self.current_idx = 0
            self.data_source = DataSource.LOCAL

            # change slider data
            self.slider.setMaximum(len(self.urls) - 1)
            self.slider.setValue(self.current_idx)
            self.update_filename_label()

            self.load_images_local(self.urls[self.start_idx : self.end_idx])

    def update_prompt_mode(self, text):
        self.image_viewer.setMousePrompt(text)

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

    def load_image_from_url(self, url):
        """Start a thread to load an image from a URL."""
        self.loader_thread = ImageLoaderThread(url)
        self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.start()

    def load_images_local(self, paths):
        self.local_thread = ImageLocalLoaderThread(paths, self.images)
        self.local_thread.image_loaded.connect(self.on_image_loaded)
        self.local_thread.start()

    def on_image_loaded(self, image):
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

        self.prev_selected_obj_idx = None

    def change_img_src(self, index):
        if 0 <= index < len(self.urls) and index != self.current_idx:
            self.accept_annotations()
            self.current_idx = index
            if (self.current_idx >= self.start_idx) and (
                self.current_idx < self.end_idx
            ):
                self.on_image_loaded(
                    self.images[self.current_idx % MainWindow.MEMORY_LIMIT]
                )
                return 0
            elif self.current_idx >= self.end_idx:
                self.start_idx, self.end_idx = (
                    self.current_idx,
                    self.current_idx + MainWindow.MEMORY_LIMIT,
                )
                if self.data_source == DataSource.LOCAL:
                    self.load_images_local(self.urls[self.start_idx : self.end_idx])
                    return 0
                elif self.data_source == DataSource.URL_REQUEST:
                    self.load_image_from_url(self.urls[self.current_idx])
                    return 0
            elif self.current_idx < self.start_idx:
                # for now do above
                # TODO: change to loading from [current_idx, end_idx - (start_idx - current_idx)]
                self.start_idx, self.end_idx = (
                    self.current_idx,
                    self.current_idx + MainWindow.MEMORY_LIMIT,
                )
                if self.data_source == DataSource.LOCAL:
                    self.load_images_local(self.urls[self.start_idx : self.end_idx])
                    return 0
                elif self.data_source == DataSource.URL_REQUEST:
                    self.load_image_from_url(self.urls[self.current_idx])
                    return 0
        return 1

    def go_back(self):
        ret = self.change_img_src(self.current_idx - 1)
        if ret == 0:
            self.slider.setValue(self.current_idx)
        # if self.current_idx > 0:
        #     self.current_idx -= 1
        #     if self.current_idx >= self.start_idx:
        #         self.on_image_loaded(self.images[self.current_idx])
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
        points = [[p.x(), p.y()] for p in self.image_viewer.points]
        boxes = [
            [b[0].x(), b[0].y(), b[1].x(), b[1].y()] for b in self.image_viewer.boxes
        ]
        self.model_thread = ModelThread(self.current_image, text, points, boxes)
        self.model_thread.result_ready.connect(self.on_model_result)
        self.model_thread.start()
        # TODO: Change this to something like thread.join() or emitting a signal from thread

    def on_model_result(self, polygons):
        """Display model results and populate the object list."""
        self.image_viewer.display_polygons(polygons)
        for i in range(len(polygons)):
            custom_widget = CustomListItemWidget(self.color_dict.keys())
            item = QListWidgetItem()
            item.setSizeHint(custom_widget.sizeHint())

            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.object_list.addItem(item)
            self.object_list.setItemWidget(item, custom_widget)

    def change_object_label(self, poly_idx, label_text):
        self.image_viewer.changePolygonLabel(poly_idx, label_text)
        item = self.object_list.item(poly_idx)
        if item:
            item.setBackground(QColor(*self.color_dict[label_text] + (50,)))

    def add_to_object_list(self, shape_dict: MaskData):
        custom_widget = CustomListItemWidget(list(self.color_dict.keys()))

        custom_widget.setupFields(shape_dict.id, shape_dict.label, "Polygon")
        item = QListWidgetItem()
        item.setSizeHint(custom_widget.sizeHint())

        # item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setBackground(QColor(*self.color_dict[shape_dict.label] + (50,)))
        self.object_list.addItem(item)
        self.object_list.setItemWidget(item, custom_widget)

        from functools import partial

        custom_widget.label_combo_box.currentTextChanged.connect(
            partial(self.change_object_label, self.object_list.count() - 1)
        )

    def on_object_selected(self, index):
        """Highlight the selected object's polygon."""
        # TODO: Stop using index to communicate with the ImageView for polys.
        # Obtain their shape.id from a constructed dict
        if index == -1:
            return
        if self.prev_selected_obj_idx is not None:
            self.image_viewer.unhighlight_polygon(self.prev_selected_obj_idx)
        self.image_viewer.highlight_polygon(index)
        self.object_list.item(index).setForeground(QColor("Blue"))
        self.prev_selected_obj_idx = index

    def control_selected(self, item: QListWidgetItem):
        """Update the ImageViewer's control based on list selection."""
        control = item.toolTip().lower()  # "box" or "polygon"
        if control == "box" or control == "polygon":
            self.image_viewer.set_shape(control)
            self.show_label_combobox()

    def accept_annotations(self):
        objects = []
        image_url = self.urls[self.current_idx]
        for i in range(self.object_list.count()):
            label = self.object_list.item(i).text()
            polygon = self.image_viewer.polygon_items[i].polygon()
            polygon_points = [[p.x(), p.y()] for p in polygon]
            objects.append({"label": label, "polygon": polygon_points})
        self.annotations[image_url] = {"objects": objects}
        self.current_idx += 1
        print(f"Annotations stored for {image_url}")

    def keyPressEvent(self, a0: Optional[QKeyEvent]) -> None:
        if a0 is not None:
            if a0.key() == Qt.Key.Key_Right:
                self.go_forward()
            if a0.key() == Qt.Key.Key_Left:
                self.go_back()

        return super().keyPressEvent(a0)
