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



### DeepGHS imgutils

- Package: `dghs-imgutils`
- Purpose here: mature anime-style person/head detection used by Composite Split
- License: MIT License
- Source: https://github.com/deepghs/imgutils

The Windows Portable build redistributes the fixed `person_detect_v1.3_s` and `head_detect_v2.0_s` ONNX weights under the upstream MIT license. Build-time downloads are SHA-256 pinned and verified.

### ISNetIS / skytnt anime-seg

- Portable file: `models/auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx`
- Purpose: General Auto Crop subject segmentation
- License: Apache License 2.0
- Source: https://huggingface.co/skytnt/anime-seg
- SHA-256: `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99`

The model owner explicitly confirmed that the `isnetis.onnx` weights are licensed under Apache-2.0. The Windows Portable build redistributes this exact SHA-256-pinned file.

### MI-GAN

- Portable file: `models/text_cleanup/migan/migan_pipeline_v2.onnx`
- Upstream project: MI-GAN
- Upstream code repository license: MIT License
- Repository: https://github.com/Picsart-AI-Research/MI-GAN
- ONNX mirror used during development: https://huggingface.co/andraniksargsyan/migan
- SHA-256: `6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b`

The Windows Portable build redistributes the pinned `migan_pipeline_v2.onnx` weight under the upstream MIT license so AI repair does not depend on a first-use network download.

The full MIT and Apache-2.0 license texts accompanying redistributed weights are included in `THIRD_PARTY_MODEL_LICENSES.md`.

## Python dependencies

Python packages installed through `requirements/runtime.txt` retain their own upstream licenses. In particular, this project depends on PySide6, MediaPipe, OpenCV contrib, Pillow, ONNX Runtime, and pyclipper. Their licenses are not relicensed by this repository.

### PySide6-Fluent-Widgets

- Package: `PySide6-Fluent-Widgets` 1.11.3
- Purpose here: Fluent visual components for the Auto Crop review surface
- License: GPL-3.0 / commercial dual-license upstream; this GPL-3.0-only project uses the GPL-compatible path
- Source: https://github.com/zhiyiYo/PyQt-Fluent-Widgets

The installer intentionally uses the existing `PySide6-Essentials` runtime and installs the Fluent package without its `PySide6` meta-package dependency so `PySide6-Addons` is not pulled into the Portable build.

### PySideSix-Frameless-Window

- Package: `PySideSix-Frameless-Window` 0.8.2
- Purpose here: runtime dependency used by PySide6-Fluent-Widgets
- Source: https://pypi.org/project/PySideSix-Frameless-Window/

### darkdetect / pywin32

These lightweight runtime dependencies are installed for the selected Fluent UI package on Windows and retain their upstream licenses.

## Project license

Code written specifically for this project is intended to be released under **GNU General Public License v3.0 only (GPL-3.0-only)** unless a file states otherwise.
