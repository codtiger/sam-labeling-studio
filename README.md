# sam-labeling-studio
<div align="center">
  <img src="assets/samstudio.svg" />
</div>
An annotation software based on Segment Anything Model(SAM) by Meta for semi-automatic labeling. <br>
The GUI software supports full manual annotation while giving you the flexibility of BYOM(Bring your own model) access with apis.

> **_Why not CVAT? Label-Studio? Amazon Ground Truth? Scale AI_**?

## Features:
These, and some more🙃:
* Free, open source, and multi-platform.
* Easily extensible and compatible with other models.
* Supporting many modalities of prompts(**points, boxes, text**).
* **Issues** can be attached to annotations for clarity and discussion.
* **NO DOCKER!** Native Qt GUI application.

We will be adding more features, especially to support videos, 3d data and possibly other modalities.

## Installation:
You need `Python>=3.8` to install the requirements and run the code. Clone this repository:
```bash
git clone https://github.com/entechlab/sam-labeling-studio/
cd same-labeling-studio
```
After that, make a new virtual environment and install the dependencies through pip:

```bash
python -m venv samstudio
source ./samstudio/bin/activate
pip install -r requirements.txt
```

Then you can run the application by:
```bash 
python main.py
```

## SAM2 Server:
To run the SAM2 server, first we need the model weights. You can either download and place the checkpoints in `weights/` or run:
```sh weights/download_ckpts.sh```
which will download all the weights(tiny, small, base+, large)
After that, you can run the server with any web server(e.g. uvicorn) by specifying the device, model weight path, and model configuration path.
```bash
# DEVICE could be `cuda` for NVIDIA CUDA, `mps` for Apple's Metal, or `cpu` for CPU.
# CKPT_PATH points to model checkpoint. If not set, by default searches for "weights/sam2.1_hiera_base_plus.pt"
# CFG_PATH points to model config file. If not set, by default searches for ""configs/sam2.1/sam2.1_hiera_b+.yaml""
DEVICE=<device> CKPT_PATH=<checkpoint_path> CFG_PATH=<CFG_PATH> uvicorn api.sam_handler:app --host 0.0.0.0 --port 8000
```

After running the command, the server should spawn locally on port 8000.

### Extending Servers With Custom Models
Check the document inside `api/`.