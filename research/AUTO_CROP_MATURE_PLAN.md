# Auto Crop — Mature Baseline Plan

Status: Stage 1 active.

## Requirement

For already-selected single-character LoRA images:

- decide whether cropping is worthwhile;
- when cropping, remove obvious useless outer area;
- prefer extra background over cutting important character content;
- protect hair, hands, feet, clothing silhouette, accessories, weapons and props;
- do not force a target aspect ratio;
- keep source images untouched;
- human review remains authoritative.

## Failed baseline

The custom MediaPipe Pose + segmentation + saliency heuristic is retired.

Observed Valby result:
- 161 analyzed images;
- 1 crop suggestion;
- 0 SAFE suggestions;
- that 1 suggestion required manual adjustment;
- KEEP missed-crop rate in the 72-image review pack: 36.6%.

Do not tune or revive that algorithm.

## Stage 1 — DeepGHS anime person detector

Use the existing DeepGHS implementation and weights, not a reimplementation.

Upstream:
- library: `dghs-imgutils`
- API: `imgutils.detect.detect_person`
- model repo: `deepghs/anime_person_detection`
- first model: `person_detect_v1.3_s`
- model ONNX size: 44.6 MB
- model card F1: 0.86
- model license: MIT
- library license: MIT

Why first:
- directly targets anime-style full-person detection;
- existing automated character-dataset tooling already uses this detector family;
- much smaller than segmentation;
- gives the exact person bbox that waifuc's `PersonSplitAction` would crop;
- therefore it tests the most direct mature solution before downloading heavier models.

Benchmark set:
- reuse the user's completed old Auto Crop review;
- take failure/challenge cases labeled `MISSED_CROP`, `MANUAL`, or `TOO_TIGHT`;
- maximum 20 images;
- no full-dataset run yet.

Outputs:
- original;
- raw upstream detection boxes;
- raw top-confidence bbox crop preview;
- JSON with upstream detections.

No custom crop decision, margin, saliency, pose fusion, or thresholds beyond the upstream API defaults in this stage.

### Stage-1 gate

Do not integrate or build production UI yet.

After human inspection, continue only if the detector reliably encloses the character on the challenge set. Record:
- no-detection count;
- multi-detection count;
- critical character-content cuts;
- obvious unnecessary looseness;
- weapon/prop misses.

## Stage 2 — only if Stage 1 cannot cover character silhouette

Use the existing `imgutils.segment.get_isnetis_mask` / `skytnt/anime-seg` ONNX implementation.

This stage is deferred because the ONNX weight is 176 MB. Do not download it unless Stage 1 proves that box detection is insufficient.

Model/code license: Apache-2.0.

## Stage 3 — only if Stage 1/2 show repeated prop failures

Evaluate an existing GroundingDINO + SAM implementation for explicit prop protection.

This is intentionally last because it adds a much heavier runtime/model stack.

## UI reuse gate

Do not build a new crop canvas.

Candidate donors:
1. existing project/Dataset Scout crop editor, if its source is available and portable;
2. Labelme v7 canvas/shape/rendering code, GPL-3.0, PySide6/Qt6;
3. X-AnyLabeling only as a secondary donor because its production UI is PyQt6.

Current Labelme v7 is Python >=3.12 and explicitly exposes no stable internal Python API; if chosen, vendor the required GPL-3.0 canvas/shape modules rather than importing private internals. Runtime migration/backport cost must be evaluated before adoption.

UI implementation starts only after the crop backend passes the small real-data gate.


## Stage-1 visual review result

The 20-image contact sheets showed that the mature DeepGHS person detector is useful but the raw detection box is not yet safe enough to use directly as a crop.

Observed:
- person recall on the challenge set: 20/20;
- several boxes omit extended hands/arms or other silhouette extremities;
- one multi-person sample selected a background NPC when the review script used highest detector confidence;
- the intended foreground subject in that sample had the largest area box;
- at least one composition contains two comparably large character boxes, where automatic single-subject cropping should be considered ambiguous rather than forced.

Action:
- keep DeepGHS person detection;
- review/display primary subject by largest detected person area rather than confidence;
- if the second-largest person box is >=60% of the largest area, mark the case ambiguous for review instead of treating it as a confident single-subject crop;
- do not solve missing hands by inventing custom geometry yet;
- Stage 2 is now justified: test the existing ISNetIS anime-character segmentation on the same 20 challenge images to see whether it preserves full character silhouette better.

The 60% ambiguity ratio is a temporary review flag only, not a production crop rule. It must be validated before production use.
