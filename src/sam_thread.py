from typing import Union
from PIL import Image
import requests
from PyQt6.QtCore import QObject, pyqtSignal


class RequestWorker(QObject):
    image_embedded = pyqtSignal(str)
    prediction_ready = pyqtSignal(list)
    connection_failed = pyqtSignal(str)
    connection_ok = pyqtSignal(str)

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def check_connection(self):
        try:
            response = requests.get(self.base_url)
            if response.ok:
                self.connection_ok.emit("Ready")
            else:
                self.connection_failed.emit("Connection Error")
        except requests.exceptions.ConnectionError as e:
            self.connection_failed.emit(str(e))

    def post_image(self, image: Union[bytes, Image.Image]):
        if isinstance(image, Image.Image):
            image_bytes = image.tobytes()
        else:
            image_bytes = image
        try:
            response = requests.post(self.base_url + "embed/", files={"image_file": image_bytes})
            return self.image_embedded.emit(response.json()["image_id"])
        except requests.exceptions.ConnectionError:
            self.connection_failed.emit("Connection Error")

    def predict(self, image_id, text, point_groups: list, boxes: list):
        response = requests.post(
            self.base_url + "predict/" + image_id + "/?k=6",
            json={"point_groups": point_groups, "boxes": boxes},
        )
        self.prediction_ready.emit(response.json()["predictions"])
