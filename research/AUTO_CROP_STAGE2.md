# General Auto Crop — Stage 2 / ISNetIS Mask Validation

Status: ACTIVE RESEARCH

Branch:
`research/auto-crop-stage2-isnetis`

Base:
merged v0.3 workflow-recovery architecture checkpoint.

## Why this stage exists

Stage 1 showed:

- DeepGHS person detection recall: 20/20 on the frozen challenge set.
- Raw person boxes are not safe final crops.
- Extended hands/arms and other silhouette extremities can fall outside the person box.
- Comparable multiple people are ambiguous.
- This justified a mature foreground-segmentation check before inventing geometry.

## Upstream reused

- `dghs-imgutils==0.19.0`
- `imgutils.detect.detect_person`
- `imgutils.segment.get_isnetis_mask`
- `deepghs/anime_person_detection / person_detect_v1.3_s`
- `skytnt/anime-seg / isnetis.onnx`
- ISNetIS scale: 1024

No production Auto Crop algorithm is introduced here.

## Frozen challenge set

The first run reads the already-completed legacy Auto Crop review and freezes the exact 20 failure/challenge samples into:

```
_research_output/auto_crop_stage2/challenge_manifest.json
```

Subsequent runs reuse that manifest.

The benchmark refuses to silently change the challenge set.

## Storage policy

All **new** research artifacts stay beside the repository:

```
_research_output/
  auto_crop_stage2/
    .venv-imgutils/
    hf_home/
    xdg_cache/
    temp/
    challenge_manifest.json
    runs/
```

`_research_output/` is gitignored.

The prior LocalAppData review is read-only legacy input. New model/download/temp/output data must not default to C:.

## Run

Double-click:

```
research\运行AutoCrop Stage2 ISNetIS.bat
```

or run it from a terminal.

The launcher:
1. creates an isolated environment under `_research_output`;
2. installs only the mature upstream research stack;
3. redirects Hugging Face/model/temp caches to `_research_output`;
4. freezes/reuses the exact 20 challenge images;
5. runs raw ISNetIS masks;
6. creates five contact sheets.

## Human gate

Inspect:

- hair;
- hands / arms;
- feet;
- clothing silhouette;
- long skirts / coattails;
- weapons;
- large props;
- characteristic accessories.

The question is **not** “is the mask pretty?”

The question is:

> Does the mature mask preserve the meaningful subject content that Stage 1 person boxes missed?

## Stop / go

### PASS direction

If masks reliably protect meaningful silhouette/content:

1. freeze Stage 2 as PASS;
2. research a mature mask-to-safe-trim/crop implementation;
3. do not invent an arbitrary bbox+margin rule.

### FAIL direction

If repeated meaningful weapon/prop/accessory content is absent from the mask:

1. freeze this limitation;
2. follow the previously approved heavier fallback research path;
3. do not threshold-tune ISNetIS or add arbitrary margins to hide the failure.

## Explicit non-goals

- no production UI;
- no PyQtGraph crop editor yet;
- no fixed aspect ratio;
- no automatic final crop;
- no model bundling decision;
- no source modification.
