from PyQt6.QtCore import QThread, pyqtSignal

from .utils import get_convex_hull, get_logger
from .models.sam2.build_sam import build_sam2
from .models.sam2.sam2_image_predictor import SAM2ImagePredictor

import numpy as np
import cv2

class ModelThread(QThread):
    """Thread to run the segmentation model."""

    result_ready = pyqtSignal(list)

    def __init__(self, image, text, points, boxes, device):
        super().__init__()
        self.image = image  # PIL Image
        self.text = text  # Text prompt
        self.points = points  # List of [x, y]
        self.boxes = boxes  # List of [x1, y1, x2, y2]
        self.logger = get_logger(__file__)

        sam2_checkpoint = "weights/sam2.1_hiera_large.pt"
        model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"

        self.model = build_sam2(model_cfg, sam2_checkpoint, device=device)

        self.predictor = SAM2ImagePredictor(self.model)
        self.predictor.set_image(np.array(image.convert("RGB")))

    def run(self):
        all_preds = []
        for points, box in zip(self.points, self.boxes):
            self.logger.debug(f"points: {points}")
            self.logger.debug(f"box: {box}")
            preds, confids, masks = self.predictor.predict(
                point_coords=np.array(points),
                point_labels=np.ones(len(points)),
                box=np.array(box),
                mask_input=None,
            )
            cv2.imwrite("preds.png", preds[confids.argmax()] * 255)
            all_preds.extend([get_convex_hull(preds[confids.argmax()])])
        # Placeholder for SAM with GroundingDINO
        # Expected input: image (PIL), text (str), points (list), boxes (list)
        # Expected output: list of polygons, each a list of [x, y] points
        # Replace with actual model call, e.g.:
        # polygons = call_sam_model(self.image, self.text, self.points, self.boxes)
        self.result_ready.emit(all_preds)
