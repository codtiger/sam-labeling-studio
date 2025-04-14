import json
import zipfile

def export_annotations_to_zip(self, output_zip_path: str, dataset_type: str):
    """
    Export all saved annotations to a ZIP file in COCO format.
    The annotations are saved in a folder named 'annotations/' with the filename
    'instances_<dataset_type>.json'.
    """
    if dataset_type not in ["Train", "Test", "Validation"]:
        logger.error("Invalid dataset type. Must be one of: Train, Test, Validation.")
        return

    # Prepare COCO format data
    coco_data = {
        "images": [],
        "annotations": [],
        "categories": [],
    }

    # Create category mapping
    category_mapping = {label: idx + 1 for idx, label in enumerate(self.color_dict.keys())}
    for label, idx in category_mapping.items():
        coco_data["categories"].append({"id": idx, "name": label})

    annotation_id = 1
    for image_idx, (image_url, annotation) in enumerate(self.annotations.items()):
        # Add image metadata
        image_name = os.path.basename(image_url)
        coco_data["images"].append({
            "id": image_idx + 1,
            "file_name": image_name,
        })

        # Add annotations
        for obj in annotation["objects"]:
            coco_data["annotations"].append({
                "id": annotation_id,
                "image_id": image_idx + 1,
                "category_id": category_mapping[obj["label"]],
                "segmentation": [sum(obj["polygon"], [])],  # Flatten polygon points
                "bbox": self.__polygon_to_bbox(obj["polygon"]),
                "iscrowd": 0,
            })
            annotation_id += 1

    # Save COCO JSON to a temporary file
    json_filename = f"annotations/instances_{dataset_type}.json"
    with open(json_filename, "w") as f:
        json.dump(coco_data, f, indent=4)

    # Create a ZIP file
    with zipfile.ZipFile(output_zip_path, "w") as zipf:
        zipf.write(json_filename, arcname=json_filename)

    logger.info(f"Annotations exported to {output_zip_path}")

def import_annotations_from_zip(self, input_zip_path: str, dataset_type: str):
    """
    Import annotations from a ZIP file in COCO format.
    The annotations are expected to be in a folder named 'annotations/' with the filename
    'instances_<dataset_type>.json'.
    """
    if dataset_type not in ["Train", "Test", "Validation"]:
        logger.error("Invalid dataset type. Must be one of: Train, Test, Validation.")
        return

    # Extract the ZIP file
    with zipfile.ZipFile(input_zip_path, "r") as zipf:
        zipf.extractall()

    # Load the COCO JSON file
    json_filename = f"annotations/instances_{dataset_type}.json"
    with open(json_filename, "r") as f:
        coco_data = json.load(f)

    # Create reverse category mapping
    category_mapping = {cat["id"]: cat["name"] for cat in coco_data["categories"]}

    # Map annotations to images
    image_annotations = {img["file_name"]: [] for img in coco_data["images"]}
    for annotation in coco_data["annotations"]:
        image_name = next(
            (img["file_name"] for img in coco_data["images"] if img["id"] == annotation["image_id"]), None
        )
        if image_name:
            image_annotations[image_name].append({
                "id": annotation["id"],
                "label": category_mapping[annotation["category_id"]],
                "polygon": self.__bbox_to_polygon(annotation["bbox"]) if "bbox" in annotation else [],
            })

    # Load annotations into the application
    for image_url in self.urls:
        image_name = os.path.basename(image_url)
        if image_name in image_annotations:
            self.annotations[image_url] = {"objects": image_annotations[image_name]}
            logger.info(f"Annotations imported for {image_name}")

def __polygon_to_bbox(self, polygon):
    """Convert a polygon to a bounding box [x_min, y_min, width, height]."""
    x_coords = [point[0] for point in polygon]
    y_coords = [point[1] for point in polygon]
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    return [x_min, y_min, x_max - x_min, y_max - y_min]

def __bbox_to_polygon(self, bbox):
    """Convert a bounding box [x_min, y_min, width, height] to a polygon."""
    x_min, y_min, width, height = bbox
    return [[x_min, y_min], [x_min + width, y_min], [x_min + width, y_min + height], [x_min, y_min + height]]