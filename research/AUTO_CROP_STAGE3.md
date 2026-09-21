# General Auto Crop — Stage 3 / Mask to Conservative Trim

Status: ACTIVE RESEARCH

## Product scope

Production input is already post-Composite single-subject active 推荐 images.

Auto Crop does **not** choose among multiple people.

## Stage 2 result

Stage 2 ISNetIS mask validation: HUMAN PASS.

DeepGHS person bbox remains useful as a localization/sanity prior, but it is not
allowed to clip the subject-protection mask.

## Mature implementation audit

### Forge

Forge's mask crop helper follows:

```
mask -> bounding region -> optional pad
```

It does not require a fixed aspect ratio.

Reference:
https://github.com/lllyasviel/stable-diffusion-webui-forge/blob/main/modules/masking.py

### ADetailer

ADetailer uses the same general production pattern around masks:

```
mask -> optional dilation -> bbox -> padding -> crop
```

Its UI exposes mask padding; 32 px is a common/default value in ADetailer-style
workflows.

Reference:
https://github.com/Bing-su/adetailer

### Albumentations

`CropNonEmptyMaskIfExists` is mature, but it requires a requested crop height
and width and is intended for randomized augmentation. This conflicts with our
requirements:
- no fixed output aspect ratio;
- preserve full subject;
- unnecessary background is cheaper than a subject cut.

It is therefore not selected.

### waifuc

`PersonSplitAction` / `ThreeStageSplitAction` are highly relevant LoRA
dataset precedents, but their person crop is detector-bbox based. Our Stage 1
real-data result already proved that raw person boxes can miss hands/silhouette,
so that crop boundary cannot be reused for General Auto Crop.

## License/reuse decision

Forge and ADetailer are AGPL-family projects.

Their code is **not vendored or copied** into this project.

Stage 3 independently implements the general, well-established geometry using
Pillow:
- foreground-support bbox from the already-generated ISNetIS mask;
- optional conservative padding;
- clip to source image bounds.

## Stage 3 candidate

Two views are evaluated:

1. **Raw soft-mask support bbox**
   - every non-zero pixel in the saved 8-bit ISNetIS mask counts as protected;
   - intentionally conservative around soft/uncertain edges.

2. **Reference padded bbox**
   - bbox above + ADetailer-inspired 32 px reference padding;
   - because sources have very different resolution, 32 px is normalized against
     the same 1024 long-side canonical scale used by ISNetIS;
   - this normalization is a research adaptation, NOT a frozen production rule.

No fixed aspect ratio.

## Important: no rerun/download

Stage 3 reads:
- Stage 2 `results.json`;
- Stage 2 saved masks;
- the original 20 frozen source images.

It does not:
- run ISNetIS;
- run DeepGHS;
- install packages;
- download a model;
- create a new venv.

## Output

Five-column contact sheets:

1. original;
2. Stage 1 person bbox reference;
3. raw ISNetIS mask bbox;
4. padded mask bbox candidate;
5. padded crop preview.

Each row also records:
- raw removed-area ratio;
- padded removed-area ratio;
- actual source-pixel padding;
- whether the raw mask support touches a source edge;
- per-side trim distances.

## Current gate

This is still a geometry benchmark.

Review questions:
- Does the mask-derived candidate preserve the hands/props/silhouette that person
  bbox missed?
- Is it consistently too loose because faint mask noise extends far into background?
- Is the 32/1024 reference padding unnecessarily large/small?
- Which images should simply KEEP ORIGINAL?

Do not implement automatic accept/keep thresholds until these geometry results are
reviewed.
