# Face LoRA Dataset Selector

[简体中文](../README.md) | **English**

[![Release](https://img.shields.io/github/v/release/JInghoeg/face-lora-dataset-selector?label=Release)](https://github.com/JInghoeg/face-lora-dataset-selector/releases)
[![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D6?logo=windows&logoColor=white)](#download--installation)
[![License](https://img.shields.io/github/license/JInghoeg/face-lora-dataset-selector)](../LICENSE)

**[Download stable release](https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0)** · [All Releases](https://github.com/JInghoeg/face-lora-dataset-selector/releases) · [User Guide](https://github.com/JInghoeg/face-lora-dataset-selector/wiki)

A local tool for organizing and filtering people / portrait datasets used in AI training.

It is designed for LoRA, model training, and other workflows built around person-centered image datasets, providing analysis, filtering, review, cleanup, cropping, and export tools in one workflow.

Automated analysis, scoring, sorting, and recommendations can remove a large amount of repetitive manual work. If you need a more carefully curated or highly personalized dataset, the automatic results can also be used as a fast starting point for manual review.

**Windows · Local-first · Portable · Lightweight**

<!-- README hero screenshot: assets/readme/hero.png -->

## Table of Contents

- [What can it do?](#what-can-it-do)
- [Who is it for?](#who-is-it-for)
- [Recommended dataset workflow](#recommended-dataset-workflow)
- Review and cleanup
  - [Text / watermark cleanup](#text--watermark-cleanup)
  - [AI-assisted review](#ai-assisted-review)
  - [Composite split](#composite-split)
  - [Auto crop](#auto-crop)
  - [Dataset organization](#dataset-organization)
- Analysis and recommendation
  - [How does automatic recommendation work?](#how-does-automatic-recommendation-work)
  - [Current analysis methods](#current-analysis-methods)
  - [Analysis speed and quality](#analysis-speed-and-quality)
  - [Manual selection and automatic results](#manual-selection-and-automatic-results)
- [Non-destructive file operations](#non-destructive-file-operations)
- [Stable and development versions](#stable-and-development-versions)
- [Download & installation](#download--installation)
- [Models and cache](#models-and-cache)
- [User guide](#user-guide)
- [License](#license)

---

## What can it do?

**Lightweight, local, portable**

Runs locally on Windows. Download, extract, and use.

**Automatic recommendation**

Choose a folder and a target dataset size, then let the scoring and recommendation system propose images in bulk.

**Fast batch analysis**

Uses lightweight, mature analysis methods suitable for processing large image collections locally.

**Research-backed filtering**

Scoring, sorting, and recommendation combine practical AI-training needs with well-documented public research, papers, and validated models. The system will continue to evolve with later versions.

**Efficient manual selection**

Quickly adjust recommendations and decide exactly which images should remain in the final dataset.

**Composite image splitting**

Detects multi-person, multi-view, and stitched images and proposes split results for fast confirmation.

**Automatic cropping**

Detects the main subject and removes unnecessary surrounding image area. Crop results can be reviewed and adjusted manually.

**Batch text / watermark cleanup**

Detects text and watermark regions in batches, with preview, manual adjustment, and batch processing.

**Non-destructive file handling**

Processed output is kept separate from source images instead of silently overwriting originals.

---

## Who is it for?

Face LoRA Dataset Selector is primarily designed for **people / portrait image datasets**, with the current version best suited to **real people and realistic or semi-realistic CG characters**.

Typical use cases include:

- identity / person LoRAs;
- face-feature training;
- body shape, proportions, and physique training;
- clothing, styling, and character appearance LoRAs;
- realistic or semi-realistic CG character datasets;
- person-centered photography or visual-style datasets;
- other datasets that need portrait filtering, duplicate review, cropping, and organization.

It works both for first-time dataset preparation and for experienced users who already have their own curation rules but want to reduce repetitive work.

Some current metrics are explicitly person-oriented. For pure scenery, product, or non-person datasets, face quality, head pose, and body framing metrics become much less meaningful.

---

## Recommended dataset workflow

A person-centered training dataset usually goes through several rounds of cleanup and review.

Recommended order:

```text
Analyze
 ↓
Initial filter
 ↓
Duplicate review
 ↓
Composite split
 ↓
Manual selection
 ↓
AI-assisted review (optional)
 ↓
Crop
 ↓
Organize
 ↓
Export
```

Text / watermark cleanup is a separate optional workflow and can be used whenever the source material requires it.

### 1. Analyze

Select an image folder and run batch analysis.

The current analysis records information such as:

- image quality;
- face quality;
- face size;
- head Yaw / Pitch / Roll;
- framing;
- visible body range;
- near-duplicate relationships;
- other data used by ranking and recommendation.

Results are cached. When the same dataset is opened again, unchanged images can reuse previous analysis instead of being processed from scratch.

### 2. Initial filter

Use the target count and automatic recommendations to reduce a large source pool to a smaller set worth reviewing.

The goal here is speed: remove obviously weak, highly repetitive, or low-value images before spending time on detailed manual decisions.

### 3. Duplicate review

Review near-duplicate groups from burst photos, video frames, photo books, and similar sources.

Images in the same group can be compared together instead of searching across the entire folder manually.

### 4. Composite split

For multi-person, multi-view, or stitched images, use the Composite Split workflow.

The application generates candidate outputs for confirmation. Accepted outputs then re-enter the normal dataset analysis and selection flow.

### 5. Manual selection

After duplicate and composite review, refine the dataset according to the actual training goal.

Useful factors may include:

- image quality;
- face quality;
- angle;
- framing;
- visible body range;
- expression;
- clothing;
- pose;
- body shape;
- scene;
- overall dataset distribution.

### 6. AI-assisted review (optional, v0.3)

Export an **AI Review Bundle** and give it to GPT or another multimodal model for an additional review pass.

The model can use both images and existing analysis results to suggest checks around identity consistency, anomalies, repetitive content, composition, and training value.

Returned results can be imported as a separate suggestion layer. They do not overwrite existing selections and do not decide the final dataset for you.

### 7. Crop

Use Auto Crop for images with excessive empty area, weak subject scale, or framing that is not ideal for direct training.

The application proposes a crop around the subject. You can accept it, keep the original, or adjust the crop manually.

### 8. Organize

After selection, the dataset can optionally be organized according to its current states.

Organization is an explicit file operation. The plan is shown before execution and checked for path conflicts.

### 9. Export

Export the confirmed images into a new training-set directory.

Source material and final output remain separate.

---

## Text / watermark cleanup

Text and watermark cleanup is an independent workflow and does not need to sit at a fixed point in the main dataset pipeline.

After choosing an image directory, the application detects text regions in batch and proposes repair boxes. Automatic detection is designed to reduce manual work, but false positives and missed regions can still occur, so reviewing the results before batch repair is recommended.

You can:

- view all images or only images that need repair / contain text / were manually edited;
- enable or disable individual repair regions;
- manually draw regions missed by detection;
- delete false-positive regions;
- preview the repaired result;
- use AI repair, TELEA, or Navier-Stokes;
- batch output repaired images to a new directory.

### Current-version interaction notes

**Pagination**

The current result list shows up to **80 images per page**. For larger folders, pagination controls and the current page / total-image count are located at the bottom of the list.

“All images” intentionally keeps images with no detected text, so cards with `Detected 0 · Suggested 0` can appear. This allows missed regions to still be corrected manually. If you only want images with results, switch to the filtered review modes.

The displayed detection count is affected by the **minimum height, minimum area, and minimum confidence** filters.

**Add a missing repair box manually**

1. Select an image from the list on the left.
2. Click **Add Region: Off** at the top to switch it to **Add Region: On**.
3. Drag a rectangle on the large preview.
4. Release the mouse. The new region is added to the repair list and enabled by default.

Existing detection boxes cannot currently be dragged or resized directly. If an automatic box is inaccurate, remove it from the region list and redraw it with Add Region.

Traditional image inpainting and AI-based repair are both available. Repaired images are written to a new output location and do not overwrite the source image.

If text covers eyes, facial features, clothing details, or other important training information, consider whether the image should remain in the dataset at all. No repair method can guarantee recovery of visual information that is no longer present in the source.

---

## How does automatic recommendation work?

The project does not let one single metric determine the value of an image.

Different analysis components answer different questions, such as:

- is there a sufficiently clear and sufficiently large face?
- what is the quality of the face itself?
- what is the visual quality of the entire image?
- which direction is the head facing?
- how much of the body is visible?
- how similar is this image to others in the dataset?

These signals are combined for scoring, sorting, and recommendation.

For example, a very clear frontal portrait may be excellent on its own, but if a dataset already contains many similar frontal portraits, its training value may be lower than a slightly weaker image that adds a side view or full-body sample.

Recommendation logic will continue to evolve based on practical training experience, public research, and further validation.

---

## Current analysis methods

The project favors methods that are well documented, research-backed or engineering-validated, and practical for local batch processing.

| Analysis | Current method | Main purpose |
| --- | --- | --- |
| Face detection | **YuNet** | Detect faces and estimate face location / size |
| Face quality | **eDifFIQA-T** | Evaluate face-image quality |
| Full-image quality | **BRISQUE** | No-reference image quality assessment |
| Head pose | **3DDFA-V2** | Estimate Yaw / Pitch / Roll |
| Body keypoints | **MediaPipe Pose** | Help estimate visible body range and framing |
| Near duplicates | **pHash + quality information** | Find highly similar images |
| Text detection | **PP-OCRv5** | Detect subtitles, watermarks, and other text regions |

No single model decides the final dataset.

References:

- [eDifFIQA](https://github.com/LSIbabnikz/eDifFIQA)
- [YuNet / OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [BRISQUE / OpenCV Quality](https://docs.opencv.org/4.x/d8/d99/classcv_1_1quality_1_1QualityBRISQUE.html)
- [3DDFA-V2](https://github.com/cleardusk/3DDFA_V2)
- [MediaPipe Pose Landmarker](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)

For full model provenance, third-party components, and licensing information, see:

[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)

---

## Analysis speed and quality

The project balances **speed, resource usage, and result quality** when choosing analysis methods.

Current models are lightweight and mature enough for local batch processing, keeping hundreds or more images within a practical processing range while retaining useful analysis quality.

Results are cached. When an existing dataset is reopened, unchanged images do not need a complete re-analysis.

If performance can be improved further **without sacrificing analysis quality or practical speed**, GPU acceleration is expected to be explored in later versions.

---

## Manual selection and automatic results

Recommended, backup, and rejected states can all be changed manually.

Experienced users can use quality, angle, framing, duplicate relationships, and other analysis information while applying their own curation rules.

Different training goals naturally require different trade-offs. For example:

- identity LoRAs may prioritize facial consistency and angle coverage;
- body-focused training may prioritize full-body visibility and body completeness;
- clothing LoRAs need clear visibility of the target outfit;
- style training may care more about overall visual characteristics.

The final dataset is always confirmed by the user.

---

## AI-assisted review

v0.3 provides AI Review Bundle export for stable IDs, existing analysis information, and review material that can be checked by GPT or another multimodal model.

It is useful as a second review pass for tasks such as:

- finding potentially missed outliers;
- checking identity consistency;
- spotting visually repetitive material;
- re-checking composition and content from the training goal;
- producing a second set of suggestions for the current selection.

Returned model results are imported as a **suggestion layer**. They do not directly modify automatic recommendations or overwrite manual choices.

The feature is optional.

---

## Composite split

Person datasets frequently contain:

- multi-panel photo layouts;
- multi-view composites;
- group photos;
- several usable subjects in one image.

Composite Split analyzes these images and generates candidate outputs for user confirmation.

Accepted outputs become active dataset assets, avoiding the need to open an external image editor and crop every image manually.

Complex magazine layouts, webpage screenshots, and dense UI thumbnail grids are not the primary target of the current implementation and may still require manual preprocessing.

---

## Auto crop

Auto Crop is mainly intended for images where the subject occupies too little of the frame, the surrounding area adds little training value, or the original composition is poorly suited to training.

The application detects the subject and proposes a crop.

During review, you can:

- accept the automatic crop;
- keep the original;
- drag or resize the crop box manually;
- reset the crop.

Auto Crop itself does not rewrite the source image.

Confirmed crop results are materialized when the final training dataset is exported.

---

## Dataset organization

After selection, you can optionally organize the source dataset directory.

Source Organizer builds a file-move plan based on the current selection states.

Before any actual move, it performs:

- operation preview;
- path-collision checks;
- explicit user confirmation.

If execution fails, rollback protections are applied where appropriate.

This step is optional. You can export the training dataset without reorganizing the source directory.

---

## Non-destructive file operations

Analysis state and processing results are kept separate from source images by default.

Operations that do **not** directly overwrite source image pixels include:

- dataset analysis;
- automatic recommendation;
- manual selection state;
- Auto Crop;
- AI-assisted review;
- text / watermark cleanup;
- final training-set export.

A small number of features do intentionally move files, but only through explicit user actions.

Current examples include:

- isolating the original composite after an accepted Composite Split;
- Source Organizer restructuring the active dataset.

These operations do not happen silently in the background.

---

## Stable and development versions

### v0.3.0

Current stable release:

**[Face LoRA Dataset Selector v0.3.0](https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0)**

Compared with the previous analysis, recommendation, duplicate, and text-cleanup workflows, v0.3.0 adds:

- dedicated duplicate-group review;
- AI-assisted review;
- Composite Split;
- Auto Crop with manual adjustment;
- Source Organizer;
- a more complete dataset workflow;
- live Chinese / English UI switching;
- progress, cancellation, and stability improvements for long-running operations.

v0.3.0 has passed both automated validation and real human QA.

### v0.2.0

v0.2.0 remains available in Releases as the previous stable version.

Future version changes will be documented together with each GitHub Release.

---

## Download & installation

### Windows stable release

Download:

**[v0.3.0 Release](https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0)**

Choose:

```text
Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip
```

Extract the complete directory, then run:

```text
Face LoRA Dataset Selector.exe
```

No separate Python installation is required.

### Run from source

Source mode is intended for development, testing, or trying unpublished changes.

Supported:

- Windows 10 / 11 x64
- Python 3.9–3.12
- Python 3.12 x64 recommended

After downloading the repository, run:

```text
安装.bat
```

Then:

```text
启动.bat
```

The installer creates a local `.venv` inside the project directory.

Manual setup is also possible:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\runtime.txt
.\.venv\Scripts\python.exe app.py
```

---

## Models and cache

Several base models are included with the application.

Some larger or optional models are downloaded on first use and verified after download.

Downloaded models are stored in a local cache and can be reused after continuing work or upgrading the application.

Image-analysis results are cached as well, so reopening an existing dataset does not require a complete re-analysis.

---

## User guide

README provides a project overview, capability summary, and basic setup instructions.

More detailed usage documentation will be organized in the GitHub Wiki, including:

- complete dataset workflow;
- interpretation of analysis metrics;
- automatic recommendation and manual review;
- AI-assisted review;
- duplicate-group review;
- Composite Split;
- Auto Crop;
- text / watermark cleanup;
- dataset organization and export;
- common problems and troubleshooting.

---

## License

This project is licensed under **GNU General Public License v3.0 only (GPL-3.0-only)**.

You may use, modify, and redistribute the project under the terms of GPLv3. Distributed derivative versions must continue to comply with GPLv3 requirements.

Third-party models, libraries, and other resources remain subject to their own licenses.
