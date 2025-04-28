from typing import Union
from PIL import Image
from pathlib import Path
import requests
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal


import numpy as np

from PIL import Image


class RequestWorker(QObject):

    image_embedded = pyqtSignal(str)
    prediction_ready = pyqtSignal(list)

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def post_image(self, image: Union[bytes, Image.Image]):
        if isinstance(image, Image.Image):
            image_bytes = image.tobytes()
        else:
            image_bytes = image
        try:
            response = requests.post(
                self.base_url + "embed/", files={"image_file": image_bytes}
            )
            return self.image_embedded.emit(response.json()["image_id"])
        except requests.exceptions.ConnectionError as e:
            print("Cannot make a connection!")
            return ""

    def predict(self, image_id, text, point_groups: list, boxes: list):
        response = requests.post(
            self.base_url + "predict/" + image_id,
            json={"point_groups": point_groups, "boxes": boxes},
        )
        self.prediction_ready.emit(response.json()["predictions"])

