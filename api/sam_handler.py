import logging
import io
import uuid
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Tuple
import os

import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, Path
from pydantic import BaseModel, Field

# CKPT_PATH = "weights/sam2.1_hiera_base_plus.pt"
# CFG_PATH = "configs/sam2.1/sam2.1_hiera_b+.yaml"
DEVICE = os.environ["DEVICE"]  # "mps "Or "cuda" or  "cpu"


from src.models.sam2.build_sam import build_sam2
from src.models.sam2.sam2_image_predictor import SAM2ImagePredictor

from src.utils import get_convex_hull

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Controlling app's global state across requests
app_state: Dict[str, Any] = {}

CKPT_PATH = os.environ.get("CKPT_PATH", "weights/sam2.1_hiera_base_plus.pt")
CFG_PATH = os.environ.get("CFG_PATH", "configs/sam2.1/sam2.1_hiera_b+.yaml")


class PredictRequestData(BaseModel):
    point_groups: List[List[Tuple[float, float]]] = Field(
        default_factory=list,
        description="List of point groups. Each group corresponds to one box.",
    )
    boxes: List[Optional[List[float]]] = Field(
        default_factory=list,
        description="List of boxes. Use null/None if no box for a corresponding point group.",
    )
    # text_prompt: Optional[str] = None # Add if your model uses text


class EmbedResponse(BaseModel):
    image_id: str = Field(..., description="Unique identifier for the embedded image.")
    message: str = "Image embedded successfully."


class PredictResponse(BaseModel):
    predictions: List[List[List[List[int]]]] = Field(
        ..., description="List of predicted polygons/masks for each query."
    )


# --- Lifespan Manager (Loads model on startup) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load the base SAM model
    logger.info(f"Loading base SAM2 model onto device: {DEVICE}...")
    try:
        base_model = build_sam2(CFG_PATH, CKPT_PATH, device=DEVICE)
        app_state["base_model"] = base_model
        # This cache will store predictor instances keyed by image_id
        app_state["image_predictor"] = None
        app_state["active_image"] = None
        logger.info("Base SAM2 model loaded successfully.")
    except Exception as e:
        logger.error(f"Fatal error loading base model: {e}", exc_info=True)

        app_state["base_model"] = None  # Indicate loading failure
        app_state["image_predictor"] = None
        app_state["active_image"] = None

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down...")
    app_state.clear()


app = FastAPI(
    title="SAM2 Prediction Service",
    description="API for embedding images and performing predictions with SAM2.",
    lifespan=lifespan,
)




# ---------- End points #
@app.post("/embed", response_model=EmbedResponse, tags=["SAM2"])
async def embed_image(image_file: UploadFile = File(..., description="Image file to embed.")):
    """
    Uploads an image, creates image embeddings using the SAM2 model,
    and returns a unique ID to reference these embeddings later.
    """
    if app_state.get("base_model") is None:
        raise HTTPException(status_code=503, detail="Model not loaded or failed to load.")

    try:
        # Read image data
        contents = await image_file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        image_np = np.array(image)
        image_np = np.ascontiguousarray(image_np)  # Ensure contiguous memory

        predictor = SAM2ImagePredictor(app_state["base_model"])
        
        logger.info("Creating image embeddings...")
        predictor.set_image(image_np)
        logger.info("Embeddings created.")

        image_id = str(uuid.uuid4())

        # Store the predictor instance (which now holds the embeddings)
        app_state["active_image"] = image_id
        app_state["image_predictor"] = predictor

        return EmbedResponse(image_id=image_id)

    except Exception as e:
        logger.error(f"Error during image embedding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to embed image: {str(e)}")
    finally:
        await image_file.close()


@app.post("/predict/{image_id}", response_model=PredictResponse, tags=["SAM2"])
async def predict_on_image(
    image_id: str = Path(..., description="The unique ID of the previously embedded image."),
    k: int = 6,
    request_data: PredictRequestData = ...,
):
    """
    Performs prediction on a previously embedded image using provided
    points and/or bounding boxes. Requires the `image_id` obtained
    from the /embed endpoint.
    """
    if app_state.get("base_model") is None:
        raise HTTPException(status_code=503, detail="Model not loaded or failed to load.")

    predictor = app_state["image_predictor"]
    if predictor is None or app_state["active_image"] != image_id:
        raise HTTPException(
            status_code=404,
            detail=f"Image ID '{image_id}' not found or embeddings not created.",
        )

    if not getattr(predictor, "image_set", True):  # Check if 'image_set' attribute exists and is True
        raise HTTPException(
            status_code=400,
            detail=f"Embeddings for image ID '{image_id}' are not ready.",
        )

    try:
        logger.info(f"Performing prediction for image_id: {image_id}")
        all_results = []

        np_point_groups = [
            np.array(group, dtype=np.float32) if group else None
            for group in request_data.point_groups
        ]
        np_boxes = [(np.array(b, dtype=np.float32) if b else None) for b in request_data.boxes]

        # Ensure lengths match or handle appropriately based on predictor needs
        num_prompts = max(len(np_point_groups), len(np_boxes))

        # if number of points and boxes don't match
        if len(np_point_groups) < num_prompts:
            np_point_groups.extend([None] * (num_prompts - len(np_point_groups)))
        if len(np_boxes) < num_prompts:
            np_boxes.extend([None] * (num_prompts - len(np_boxes)))

        for points, box in zip(np_point_groups, np_boxes):
            if points is None and box is None:
                logger.warning("Skipping empty prompt (no points and no box).")
                continue

            logger.debug(f"Predicting with points: {points is not None}, box: {box is not None}")
            preds, confids, masks = predictor.predict(
                point_coords=points,
                point_labels=np.ones(len(points)) if points is not None else None,
                box=box,
                mask_input=None,
            )

            if preds is not None and len(preds) > 0 and confids is not None and len(confids) > 0:
                # Process the best prediction (highest confidence)
                # best_mask = preds[confids.argmax()]
                preds_filtered = preds[confids >= 0.1]
                polygons = [
                    get_convex_hull(mask, k=k).astype(np.int32).tolist() for mask in preds_filtered
                ]
                # polygon = get_convex_hull(
                #   best_mask
                # )  # Assumes returns List[List[float/int]]
                all_results.append(polygons)
            else:
                logger.warning("Prediction returned no valid results for a prompt.")

        return PredictResponse(predictions=all_results)

    except Exception as e:
        logger.error(f"Error during prediction for image_id {image_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# --- Optional: Add a root endpoint for basic check ---
@app.get("/", tags=["Status"])
async def read_root():
    model_status = "Loaded" if app_state.get("base_model") else "Not Loaded/Error"
    return {"message": "SAM2 Service is running", "model_status": model_status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
