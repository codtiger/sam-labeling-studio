from typing import Union
import json
import zipfile
import os
from pathlib import Path
import shutil

from ..utils import get_logger

logger = get_logger(__file__)

PathLike = Union[str, Path]


def export_annotations_to_zip(
    annotations: dict, color_dict: dict, output_zip_path: PathLike, dataset_type: str
):
    """
    Export all saved annotations to a ZIP file in COCO format.
    The annotations are saved in a folder named 'annotations/' with the filename
    'instances_<dataset_type>.json'.
    """
    if dataset_type not in ["Train", "Test", "Validation"]:
        logger.error("Invalid dataset type. Must be one of: Train, Test, Validation.")
        return

    coco_data = {
        "images": [],
        "annotations": [],
        "categories": [],
    }

    category_mapping = {label: idx + 1 for idx, label in enumerate(color_dict.keys())}
    for label, idx in category_mapping.items():
        coco_data["categories"].append({"id": idx, "name": label})

    annotation_id = 1
    for image_idx, (image_url, annotation) in enumerate(annotations.items()):
        image_name = os.path.basename(image_url)
        coco_data["images"].append(
            {
                "id": image_idx + 1,
                "file_name": image_name,
            }
        )

        for obj in annotation["objects"]:
            coco_data["annotations"].append(
                {
                    "id": annotation_id,
                    "image_id": image_idx + 1,
                    "category_id": category_mapping[obj["label"]],
                    "segmentation": [sum(obj["polygon"], [])],  # Flatten polygon points
                    "bbox": __polygon_to_bbox(obj["polygon"]),
                    "iscrowd": 0,
                }
            )
            annotation_id += 1

    # Save COCO JSON to a temporary file
    os.makedirs("annotations", exist_ok=True)
    json_filename = f"annotations/instances_{dataset_type}.json"

    with open(json_filename, "w") as f:
        json.dump(coco_data, f, indent=0)

    output_zip_path = Path(output_zip_path)
    with zipfile.ZipFile(str(output_zip_path.with_suffix(".zip")), "w") as zipf:
        zipf.write(json_filename, arcname=json_filename)

    shutil.rmtree("annotations/")
    logger.info(f"Annotations exported to {output_zip_path}")


def import_annotations_from_zip(input_zip_path: PathLike, urls: list, dataset_type: str):
    """
    Import annotations from a ZIP file in COCO format.
    The annotations are expected to be in a folder named 'annotations/' with the filename
    'instances_<dataset_type>.json'.
    """
    annotations = {}
    if dataset_type not in ["Train", "Test", "Validation"]:
        logger.error("Invalid dataset type. Must be one of: Train, Test, Validation.")
        return

    with zipfile.ZipFile(str(input_zip_path), "r") as zipf:
        if "annotations/instances_Train.json" in zipf.namelist():
            with zipf.open(f"annotations/instances_{dataset_type}.json") as f:
                coco_data = json.load(f)
        else:
            logger.error(f"ZIP file does not contain 'annotations/instances_{dataset_type}.json'.")
            return

    category_mapping = {cat["id"]: cat["name"] for cat in coco_data["categories"]}

    image_annotations = {img["file_name"]: [] for img in coco_data["images"]}
    for annotation in coco_data["annotations"]:
        image_name = next(
            (img["file_name"] for img in coco_data["images"] if img["id"] == annotation["image_id"]),
            None,
        )
        if image_name:
            if "segmentation" in annotation and annotation["segmentation"]:
                polygon = [
                    [annotation["segmentation"][0][i], annotation["segmentation"][0][i + 1]]
                    for i in range(0, len(annotation["segmentation"][0]), 2)
                ]
            elif "bbox" in annotation:
                polygon = __bbox_to_polygon(annotation["bbox"])
            else:
                polygon = []
            image_annotations[image_name].append(
                {
                    "id": annotation["id"],
                    "label": category_mapping[annotation["category_id"]],
                    "polygon": polygon,
                }
            )

    # Load annotations into the application
    for image_url in urls:
        image_name = os.path.basename(image_url)
        if image_name in image_annotations:
            annotations[image_url] = {"objects": image_annotations[image_name]}
            logger.info(f"Annotations imported for {image_name}")
    return annotations


def __polygon_to_bbox(polygon):
    """Convert a polygon to a bounding box [x_min, y_min, width, height]."""
    x_coords = [point[0] for point in polygon]
    y_coords = [point[1] for point in polygon]
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    return [x_min, y_min, x_max - x_min, y_max - y_min]


def __bbox_to_polygon(bbox):
    """Convert a bounding box [x_min, y_min, width, height] to a polygon."""
    x_min, y_min, width, height = bbox
    return [
        [x_min, y_min],
        [x_min + width, y_min],
        [x_min + width, y_min + height],
        [x_min, y_min + height],
    ]
