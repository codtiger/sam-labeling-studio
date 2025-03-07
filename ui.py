from pathlib import Path
from io import BytesIO
import os

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
    QSizePolicy,
    QListView,
    QPushButton,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QAction
from PyQt6.QtSvg import QSvgRenderer

from image_viewer import ImageViewer
from list_item_widget import CustomListItemWidget
from threads import ImageLoaderThread, ModelThread, ImageLocalLoaderThread
from utils import pil_to_qimage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Annotation Platform")
        self.resize(1920, 1080)

        # Central widget with vertical layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        self.last_directory = ""
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

        # Image viewer for displaying and interacting with images
        self.image_viewer = ImageViewer()
        layout.addWidget(self.image_viewer)
        self.image_viewer.setMouseTracking(True)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Left sidebar with QListWidget for shapes
        self.shape_dock = QDockWidget("Shapes", self)
        self.shape_list = QListWidget()

        # SVG for Box (square)
        box_svg = """
        <svg width="24" height="24" viewBox="0 0 24 24">
            <rect x="4" y="4" width="16" height="16" fill="none" stroke="white" stroke-width="2"/>
        </svg>
        """
        box_icon = self.svg_to_icon(box_svg)
        box_item = QListWidgetItem("Box")
        box_item.setIcon(box_icon)
        self.shape_list.addItem(box_item)

        # SVG for Polygon (pentagon)
        polygon_svg = """
        <svg width="24" height="24" viewBox="0 0 24 24">
            <polygon points="12,2 22,9 17,20 7,20 2,9" fill="none" stroke="white" stroke-width="2"/>
        </svg>
        """
        polygon_icon = self.svg_to_icon(polygon_svg)
        polygon_item = QListWidgetItem("Polygon")
        polygon_item.setIcon(polygon_icon)
        self.shape_list.addItem(polygon_item)

        # Set icon size and connect signal
        self.shape_list.setIconSize(QSize(24, 24))
        self.shape_list.itemClicked.connect(self.shape_selected)

        self.shape_dock.setWidget(self.shape_list)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.shape_dock)
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
        self.object_list.setStyleSheet("QListWidget::item { border: 1px solid gray }")
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

        self.accept_action = QAction("Accept", self)
        self.accept_action.triggered.connect(self.accept_annotations)
        self.toolbar.addAction(self.accept_action)

        # Data storage
        self.urls = []  # List of image URLs
        self.images = []  # List of PIL.Image objects
        self.current_index = 0  # Index of the current image
        self.annotations = {}  # Dictionary to store annotations
        self.current_image = None  # Current PIL image
        # Initial update to set button state
        self.update_mode()

    def svg_to_icon(self, svg_string):
        """Convert an SVG string to a QIcon."""
        renderer = QSvgRenderer(bytearray(svg_string.encode("utf-8")))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def update_mode(self):
        """Update ImageViewer mode and Run Model button state based on radio selection."""
        if self.model_mode_radio.isChecked():
            self.image_viewer.set_mode("model")
            self.manual_prompt_combo.setEnabled(True)
            self.run_model_action.setEnabled(True)
            self.shape_dock.setEnabled(False)
            self.shape_list.clearSelection()  # Clear selection in model mode
        else:  # manual_mode_radio is checked
            self.image_viewer.set_mode("manual")
            self.run_model_action.setEnabled(False)
            self.manual_prompt_combo.setEnabled(False)
            self.shape_dock.setEnabled(True)

    def load_url_list(self):
        """Load a text file containing image URLs."""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select URL List", str(self.last_directory), "Text files (*.txt)"
        )
        if file_name:
            self.last_directory = Path(file_name).parent
            with open(file_name, "r") as f:
                self.urls = [line.strip() for line in f if line.strip()]
            self.current_index = 0
            if self.urls:
                self.load_image_from_url(self.urls[self.current_index])

    def load_images(self):
        self.urls, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", str(self.last_directory), "Images (*.png *.jpg)"
        )
        if len(self.urls) != 0:
            self.last_directory = Path(self.urls[0]).parent
            self.current_index = 0
            self.load_images_local(self.urls)

    def update_prompt_mode(self, text):
        self.image_viewer.setMousePrompt(text)

    def load_image_from_url(self, url):
        """Start a thread to load an image from a URL."""
        self.image_viewer.clear()  # Clear previous annotations
        self.object_list.clear()  # Clear object list
        self.loader_thread = ImageLoaderThread(url)
        self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.start()

    def load_images_local(self, paths):
        self.local_thread = ImageLocalLoaderThread(paths, self.images, 30)
        self.local_thread.image_loaded.connect(self.on_image_loaded)
        self.local_thread.start()

    def on_image_loaded(self, image):
        """Handle the loaded image by displaying it."""
        self.current_image = image
        qimage = pil_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)
        self.image_viewer.set_image(pixmap)

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

    def on_model_result(self, polygons):
        """Display model results and populate the object list."""
        self.image_viewer.display_polygons(polygons)
        # self.object_list.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        # self.object_list.clear()
        for i in range(len(polygons)):
            custom_widget = CustomListItemWidget()
            item = QListWidgetItem()
            item.setSizeHint(custom_widget.sizeHint())

            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.object_list.addItem(item)
            self.object_list.setItemWidget(item, custom_widget)

    def on_object_selected(self, index):
        """Highlight the selected object's polygon."""
        self.image_viewer.highlight_polygon(index)

    def shape_selected(self, item):
        """Update the ImageViewer's shape based on list selection."""
        shape = item.text().lower()  # "box" or "polygon"
        self.image_viewer.set_shape(shape)

    def accept_annotations(self):
        """Save annotations for the current image and move to the next."""
        # If images are already loaded
        if len(self.images) != 0:
            objects = []
            image_url = self.urls[self.current_index]
            for i in range(self.object_list.count()):
                label = self.object_list.item(i).text()
                polygon = self.image_viewer.polygon_items[i].polygon()
                polygon_points = [[p.x(), p.y()] for p in polygon]
                objects.append({"label": label, "polygon": polygon_points})
            self.annotations[image_url] = {"objects": objects}
            self.current_index += 1
            img = self.images.pop()
            self.image_viewer.clear()  # Clear previous annotations
            self.object_list.clear()  # Clear object list
            self.on_image_loaded(img)
            print("All images annotated. Annotations stored in self.annotations.")
            return
        # if used the incomplete urlThread
        # TODO : CHANGE THIS
        if self.current_index >= len(self.urls) or not self.image_viewer.polygon_items:
            return
        image_url = self.urls[self.current_index]
        objects = []
        for i in range(self.object_list.count()):
            label = self.object_list.item(i).text()
            polygon = self.image_viewer.polygon_items[i].polygon()
            polygon_points = [[p.x(), p.y()] for p in polygon]
            objects.append({"label": label, "polygon": polygon_points})
        self.annotations[image_url] = {"objects": objects}
        self.current_index += 1
        if self.current_index < len(self.urls):
            self.load_image_from_url(self.urls[self.current_index])
        else:
            print("All images annotated. Annotations stored in self.annotations.")
