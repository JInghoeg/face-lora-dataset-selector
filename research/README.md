# Auto Crop Research Harness v0

Research-only benchmark for conservative, content-preserving crop suggestions.

This harness is intentionally separate from the production selector UI. It never modifies source images.

## Baseline A

Reuses existing project dependencies:

- MediaPipe Pose Landmarker with segmentation masks
- OpenCV Fine-Grained Saliency
- selector cache metadata when available

No new model is bundled in this phase.

## Run

From the repository root:

```powershell
python research/auto_crop_harness.py "G:\ComfyUI-aki\数据集\渥尔比"
```

By default, if the selector cache contains recommended images, only the current final `推荐` set is analyzed. Otherwise all images are used.

Force all images:

```powershell
python research/auto_crop_harness.py "G:\ComfyUI-aki\数据集\渥尔比" --all
```

Open an existing benchmark run again:

```powershell
python research/auto_crop_harness.py --review "<run directory>"
```

## Review UI

The UI shows:

1. original image
2. original image with suggested crop box
3. cropped preview

Crop proposals use one-click labels:

- SAFE
- TOO_TIGHT
- UNNECESSARY
- TOO_LOOSE
- MANUAL

KEEP ORIGINAL cases use:

- CORRECT_KEEP
- MISSED_CROP

A click saves immediately and advances to the next sample. Numeric shortcuts and Left/Right navigation are supported.

## Output

Runs are written under:

```
%LOCALAPPDATA%\Face LoRA Dataset Selector\research\auto_crop\
```

Each run contains:

- `proposals.json`
- `proposals.csv`
- `review_pack.json`
- `review_labels.json`
- `summary.json`
- `contact_sheets\`

The highest-cost failure is `TOO_TIGHT`: meaningful subject content was cut or placed dangerously close to the crop boundary.

## Self-test

```powershell
python research/auto_crop_harness.py --self-test
```
