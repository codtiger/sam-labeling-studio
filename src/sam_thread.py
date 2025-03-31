from PyQt6.QtCore import QThread, pyqtSignal

from .models.sam2.build_sam import build_sam2
from models.sam2.sam2_image_predictor import SAM2ImagePredictor


class ModelThread(QThread):
    """Thread to run the segmentation model."""

    result_ready = pyqtSignal(list)

    def __init__(self, image, text, points, boxes, device):
        super().__init__()
        self.image = image  # PIL Image
        self.text = text  # Text prompt
        self.points = points  # List of [x, y]
        self.boxes = boxes  # List of [x1, y1, x2, y2]

        sam2_checkpoint = "weights/sam2.1_hiera_large.pt"
        model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"

        self.model = build_sam2(model_cfg, sam2_checkpoint, device=device)

        self.predictor = SAM2ImagePredictor(self.model)
        self.predictor.set_image(image)

    def run(self):
        # Placeholder for SAM with GroundingDINO
        # Expected input: image (PIL), text (str), points (list), boxes (list)
        # Expected output: list of polygons, each a list of [x, y] points
        # Replace with actual model call, e.g.:
        # polygons = call_sam_model(self.image, self.text, self.points, self.boxes)
        polygons = [[[100, 100], [200, 100], [200, 200], [100, 200]]]  # Dummy square
        self.result_ready.emit(polygons)
