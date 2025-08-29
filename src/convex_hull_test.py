from models.sam2.build_sam import build_sam2
from models.sam2.sam2_image_predictor import SAM2ImagePredictor
import cv2

from utils import get_convex_hull, get_convex_hull_v2

from PIL import Image
import numpy as np
from timeit import default_timer as timer


CKPT_PATH = "weights/sam2.1_hiera_large.pt"
CFG_PATH = "configs/sam2.1/sam2.1_hiera_l.yaml"
DEVICE = "mps"  # Or "cuda", "cpu"


image_np = None
image_path = ""
image = Image.open(image_path).convert("RGB")
image_np = np.array(image)
image_np = np.ascontiguousarray(image_np)  # Ensure contiguous memory

base_model = build_sam2(CFG_PATH, CKPT_PATH, device=DEVICE)
predictor = SAM2ImagePredictor(base_model)

predictor.set_image(image_np)


# points = [
#     (100, 100),
#     (125,125),
#     (150,125),
#     (130,132)
# ]
# preds, confids, masks = predictor.predict(
#     point_coords=points,
#     point_labels=np.ones(len(points)) if points is not None else None,
#     box=None,
#     mask_input=None,
# )
def run_benchmark(preds):
    for pred in preds:
        hull1 = get_convex_hull(pred, bg_value=0, k=6)
        hull2 = get_convex_hull_v2(pred, bg_value=0, k=6)
        assert np.allclose(hull1, hull2), "Convex hulls do not match!"
        # Measure runtime for get_convex_hull
    times_hull1 = []
    for _ in range(10):
        start = timer()
        hull1 = get_convex_hull(preds[0], bg_value=0, k=6)
        end = timer()
        times_hull1.append(end - start)

    # Measure runtime for get_convex_hull_v2
    times_hull2 = []
    for _ in range(10):
        start = timer()
        hull2 = get_convex_hull_v2(preds[0], bg_value=0, k=6)
        end = timer()
        times_hull2.append(end - start)

    # Calculate mean and standard deviation of runtimes
    mean_hull1 = np.mean(times_hull1)
    std_hull1 = np.std(times_hull1)

    mean_hull2 = np.mean(times_hull2)
    std_hull2 = np.std(times_hull2)

    print(f"get_convex_hull: mean={mean_hull1:.6f}s, std={std_hull1:.6f}s")
    print(f"get_convex_hull_v2: mean={mean_hull2:.6f}s, std={std_hull2:.6f}s")


if __name__ == "__main__":
    points = []

    def click_event(event, x, y, flags, param):
        global points
        if event == cv2.EVENT_LBUTTONDOWN:  # Left click to add a point
            points.append([x, y])
            cv2.circle(image_display, (x, y), 5, (0, 0, 255), -1)  # Draw point on image
            cv2.imshow("Image", image_display)
        elif event == cv2.EVENT_RBUTTONDOWN:  # Right click to process points
            if len(points) > 0:
                print(f"Points selected: {points}")
                preds, confids, masks = predictor.predict(
                    point_coords=points,
                    point_labels=np.ones(len(points)),
                    box=None,
                    #                    mask_input=None,
                )
                for pred in preds:
                    hull = get_convex_hull(pred, bg_value=0, k=6)
                    # Draw the convex hull on the image
                    for i in range(len(hull)):
                        cv2.line(
                            image_display,
                            tuple(reversed(hull[i].astype(np.int32).tolist())),
                            tuple(reversed(hull[(i + 1) % len(hull)].astype(np.int32).tolist())),
                            (0, 255, 0),
                            2,
                        )
                cv2.imshow("Image", image_display)
                points = []  # Reset points after processing

    # Load the image using OpenCV for display
    image_display = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    cv2.imshow("Image", image_display)
    cv2.setMouseCallback("Image", click_event)

    print("Left click to select points, right click to process.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
