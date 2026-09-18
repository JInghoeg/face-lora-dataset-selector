# Third-Party Notices

This project uses or redistributes third-party libraries, model files, and resources. Those components keep their original licenses; the project's GPL-3.0-only license does **not** replace the licenses listed below.

## Bundled model / resource files

### YuNet face detector

- File: `models/yunet_2023mar.onnx`
- Project: OpenCV Zoo / YuNet
- License: MIT License for the files in the YuNet model directory
- Source: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet

### eDifFIQA-T

- File: `models/ediffiqa_t.onnx`
- Project: eDifFIQA
- License: MIT License
- Source: https://github.com/LSIbabnikz/eDifFIQA

### 3DDFA-V2

- Files: `models/mb1_120x120.onnx`, `models/param_mean_std_62d_120x120.pkl`
- Project: 3DDFA_V2
- License: MIT License
- Source: https://github.com/cleardusk/3DDFA_V2

### MediaPipe Pose Landmarker

- File: `models/pose_landmarker_lite.task`
- Project: MediaPipe
- License: Apache License 2.0
- Source: https://github.com/google-ai-edge/mediapipe

### PP-OCRv5 text detection

- Files: `models/ppocrv5_mobile_det/inference.onnx`, `models/ppocrv5_mobile_det/inference.yml`
- Project: PaddleOCR / PP-OCR
- License: Apache License 2.0
- Source: https://github.com/PaddlePaddle/PaddleOCR

### BRISQUE resources

- Files: `models/brisque_model_live.yml`, `models/brisque_range_live.yml`
- Project: OpenCV Contrib / QualityBRISQUE samples
- License: Apache License 2.0 (OpenCV Contrib repository)
- Source: https://github.com/opencv/opencv_contrib/tree/4.x/modules/quality/samples

### DB text detection post-processing code

- File: `text_detector.py`
- Adapted from: RapidOCR / PaddleOCR DB text detection preprocessing and post-processing
- License: Apache License 2.0
- Sources: https://github.com/RapidAI/RapidOCR and https://github.com/PaddlePaddle/PaddleOCR

Only the detection-side preprocessing / DB post-processing needed by this application is retained locally. Model inference continues to use this project's bundled PP-OCRv5 ONNX detector through ONNX Runtime.

## Optional model not redistributed in the public release

### MI-GAN

- Expected local file: `models/migan_pipeline_v2.onnx`
- Upstream project: MI-GAN
- Upstream code repository license: MIT License
- Repository: https://github.com/Picsart-AI-Research/MI-GAN
- ONNX mirror used during development: https://huggingface.co/andraniksargsyan/migan

The public repository intentionally does **not** redistribute the MI-GAN ONNX weight. When the optional MI-GAN repair path is used and the file is missing, the application can download the model directly from the upstream Hugging Face location and verify the expected file size and SHA-256 before loading it.

Users may also place the same upstream model manually at `models/migan_pipeline_v2.onnx`.

## Python dependencies

Python packages installed through `requirements.txt` retain their own upstream licenses. In particular, this project depends on PySide6, MediaPipe, OpenCV contrib, Pillow, ONNX Runtime, and pyclipper. Their licenses are not relicensed by this repository.

## Project license

Code written specifically for this project is intended to be released under **GNU General Public License v3.0 only (GPL-3.0-only)** unless a file states otherwise.
