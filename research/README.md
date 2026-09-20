# Auto Crop Research Harness v0

Research-only benchmark for conservative, content-preserving crop suggestions.

This harness is intentionally separate from the production selector UI. It never modifies source images.

## Baseline A — FAILED / RETIRED

Baseline A reused existing project dependencies:

- MediaPipe Pose Landmarker with segmentation masks
- OpenCV Fine-Grained Saliency
- selector cache metadata when available

Real Valby review showed the baseline was too conservative to be useful and its rare crop suggestion was not reliable enough for production. Do not tune or promote this heuristic path further.

The next benchmark must use existing mature crop/detection implementations directly. Priority order:

1. DeepGHS **waifuc** `PersonSplitAction` / `ThreeStageSplitAction`, backed by `dghs-imgutils` person / half-body / head detectors. This is already used in automated anime/LoRA dataset pipelines.
2. DeepGHS `imgutils` character segmentation (`ISNetIS`) as an existing segmentation baseline when person boxes are insufficient.
3. GroundingDINO + SAM only as a heavier second-stage candidate for props / out-of-body content if the lighter mature stack fails.

The research UI may remain as an evaluator, but crop generation itself must not return to custom MediaPipe+saliency heuristics.

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
