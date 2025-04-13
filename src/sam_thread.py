import io

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread

from .utils import get_convex_hull, get_logger

from .models.sam2.build_sam import build_sam2
from .models.sam2.sam2_image_predictor import SAM2ImagePredictor

import numpy as np

# import cv2
from PIL import Image


class ModelWorker(QObject):
    model_ready = pyqtSignal()
    image_embedded = pyqtSignal()
    prediction_done = pyqtSignal(list)

    def __init__(self, device, ckpt_path, cfg_path):
        super().__init__()
        self.logger = get_logger(__file__)
        self.device = device
        self.ckpt_path = ckpt_path
        self.cfg_path = cfg_path
        self.predictor = None

    @pyqtSlot()
    def load_model(self):
        model = build_sam2(self.cfg_path, self.ckpt_path, device=self.device)
        self.predictor: SAM2ImagePredictor = SAM2ImagePredictor(model)
        self.model_ready.emit()

    @pyqtSlot(Image.Image)
    def set_image(self, pil_image):
        # image = Image.open(io.BytesIO(image_bytes))
        self.predictor.set_image(np.array(pil_image.convert("RGB")))
        self.image_embedded.emit()

    @pyqtSlot(str, list, list)
    def predict(self, text, point_groups, boxes):
        all_preds = []
        for points, box in zip(point_groups, boxes):
            self.logger.debug(f"points: {points}")
            self.logger.debug(f"box: {box}")
            # TODO: move this out
            if points == []:
                point_coords, point_labels = None, None
            else:
                point_coords, point_labels = np.array(points), np.ones(len(points))
            preds, confids, masks = self.predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=np.array(box) if box else None,
                mask_input=None,
            )
            all_preds.extend(
                [get_convex_hull(preds[confids.argmax()]).astype(np.int32)]
            )
        # Placeholder for SAM with GroundingDINO
        # Expected input: image (PIL), text (str), points (list), boxes (list)
        # Expected output: list of polygons, each a list of [x, y] points
        # Replace with actual model call, e.g.:
        # polygons = call_sam_model(self.image, self.text, self.points, self.boxes)
        self.prediction_done.emit(all_preds)


# class WorkerSignals(QObject):
#     finished = pyqtSignal(object)


# class ModelInitiateWorker(QRunnable):

#     def __init__(self, device, ckpt_path, cfg_path):
#         super().__init__()
#         self.device = device
#         self.sam2_checkpoint = ckpt_path
#         self.model_cfg = cfg_path
#         self.signals = WorkerSignals()

#     @pyqtSlot()
#     def run(self):
#         from .models.sam2.build_sam import build_sam2
#         from .models.sam2.sam2_image_predictor import SAM2ImagePredictor

#         self.model = build_sam2(
#             self.model_cfg, self.sam2_checkpoint, device=self.device
#         )
#         self.predictor = SAM2ImagePredictor(self.model)
#         self.signals.finished.emit(self.predictor)


# class EmbeddingWorker(QRunnable):
#     """Thread to run the segmentation model."""

#     def __init__(self, predictor, image):
#         super().__init__()
#         self.predictor = predictor
#         self.signals = WorkerSignals()

#         self.img = image

#     @pyqtSlot()
#     def run(self):

#         # self.predictor.set_image(np.array(self.img.convert("RGB")))
#         self.predictor.set_image(np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8))
#         self.signals.finished.emit(self.predictor)


# class PredictionWorker(QRunnable):

#     def __init__(self, predictor, text, points, boxes):
#         super().__init__()
#         self.signals = WorkerSignals()
#         self.text = text  # Text prompt
#         self.points = points  # List of [x, y]
#         self.boxes = boxes  # List of [x1, y1, x2, y2]
#         self.logger = get_logger(__file__)

#         self.predictor = predictor

#     @pyqtSlot()
#     def run(self):
#         all_preds = []
#         for points, box in zip(self.points, self.boxes):
#             self.logger.debug(f"points: {points}")
#             self.logger.debug(f"box: {box}")
#             preds, confids, masks = self.predictor.predict(
#                 point_coords=np.array(points),
#                 point_labels=np.ones(len(points)),
#                 box=np.array(box),
#                 mask_input=None,
#             )
#             all_preds.extend([get_convex_hull(preds[confids.argmax()])])
#         # Placeholder for SAM with GroundingDINO
#         # Expected input: image (PIL), text (str), points (list), boxes (list)
#         # Expected output: list of polygons, each a list of [x, y] points
#         # Replace with actual model call, e.g.:
#         # polygons = call_sam_model(self.image, self.text, self.points, self.boxes)
#         self.signals.finished.emit(all_preds)
