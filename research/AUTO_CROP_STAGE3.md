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

## Stage 3.1 correction

The first Stage 3 benchmark exposed two implementation mistakes.

1. ISNetIS produces a soft alpha mask. Treating every non-zero 8-bit pixel as
   protected foreground caused faint background responses to expand the bbox
   toward the full image.
2. The previous 32/1024 normalized padding was our own adaptation. It inflated
   to 108/120 px on some high-resolution samples and was visibly too loose.

Stage 3.1 therefore evaluates:

1. **Raw soft-mask bbox** — diagnostic only.
2. **Primary candidate** — alpha >= 0.10 support bbox + fixed 32 px padding.
3. **Diagnostic candidate** — alpha >= 0.20 support bbox + fixed 32 px padding.

The 0.10 / 0.20 alpha floors come from mature ISNetIS downstream practice
(CharacterGen-style background removal), while fixed 32 px returns to the
ADetailer-style mature padding convention.

These remain research candidates, not production thresholds.

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

Six-column contact sheets:

1. original;
2. Stage 1 person bbox reference;
3. raw soft ISNetIS mask bbox;
4. alpha >= 0.10 bbox + fixed 32 px padding;
5. alpha >= 0.20 bbox + fixed 32 px padding;
6. primary alpha >= 0.10 crop preview.

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
