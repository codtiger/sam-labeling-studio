from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex
import requests
from queue import Queue
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

    def __init__(self, image_paths: list, image_list: list):
        # self.condition = QWaitCondition()
        self.mutex = QMutex()
        super().__init__()
        self.paths = image_paths
        self.index = 0
        # self.background_load_num = min(background_load_num, len(image_paths))
        self.image_list = image_list

    def run(self):
        self.image_list[0] = Image.open(self.paths[0], "r")
        self.image_loaded.emit(self.image_list[0])
        self.mutex.lock()
        for idx in range(1, len(self.paths)):
            self.image_list[idx] = Image.open(self.paths[idx], "r")
        # self.condition.wait(self.mutex)
        self.mutex.unlock()

    def wake_up(self):
        self.mutex.lock()
        # self.condition.wakeOne()
        self.mutex.unlock()
