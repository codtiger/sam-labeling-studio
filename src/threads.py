from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex
import requests
from PIL import Image
from io import BytesIO


class ImageLoaderThread(QThread):
    """Thread to download an image from a URL."""

    image_loaded = pyqtSignal(Image.Image)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            image = Image.open(BytesIO(response.content))
            self.image_loaded.emit(image)
        except Exception as e:
            print(f"Error loading image from {self.url}: {e}")


class ImageLocalLoaderThread(QThread):
    """Thread to open images locally in batches"""

    image_loaded = pyqtSignal(Image.Image)

    def __init__(
        self, image_paths: list, image_list: list = [], background_load_num=30
    ):
        self.condition = QWaitCondition()
        self.mutex = QMutex()
        super().__init__()
        self.paths = image_paths
        self.index = 0
        self.background_load_num = min(background_load_num, len(image_paths))
        self.image_list = image_list

    def run(self):
        full_len = len(self.paths)
        ranges = range(0, full_len, self.background_load_num)
        self.mutex.lock()
        for idx in range(1, len(ranges)):
            image = Image.open(self.paths[ranges[idx - 1]], "r")
            self.image_loaded.emit(image)
            self.image_list.extend(
                [
                    Image.open(path, "r")
                    for path in self.paths[ranges[idx - 1] + 1 : ranges[idx]]
                ]
            )
            self.condition.wait(self.mutex)
            self.mutex.unlock()
        # final batch
        image = Image.open(self.paths[ranges[-1]], "r")
        self.image_loaded.emit(image)
        self.image_list.extend(
            [Image.open(self.paths[idx], "r") for idx in range(ranges[-1], full_len)]
        )

    def wake_up(self):
        self.mutex.lock()
        self.condition.wakeOne()
        self.mutex.unlock()


class ModelThread(QThread):
    """Thread to run the segmentation model."""

    result_ready = pyqtSignal(list)

    def __init__(self, image, text, points, boxes):
        super().__init__()
        self.image = image  # PIL Image
        self.text = text  # Text prompt
        self.points = points  # List of [x, y]
        self.boxes = boxes  # List of [x1, y1, x2, y2]

    def run(self):
        # Placeholder for SAM with GroundingDINO
        # Expected input: image (PIL), text (str), points (list), boxes (list)
        # Expected output: list of polygons, each a list of [x, y] points
        # Replace with actual model call, e.g.:
        # polygons = call_sam_model(self.image, self.text, self.points, self.boxes)
        polygons = [[[100, 100], [200, 100], [200, 200], [100, 200]]]  # Dummy square
        self.result_ready.emit(polygons)
