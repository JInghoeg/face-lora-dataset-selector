# Project Handoff

Use this as the concise continuation point for the current v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Last verified code merge: `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf` — PR #29 manual Auto Crop ROI
- Previous verified product head: `0d8c6952ed89f7dfbcf16ad2ec2bd16e791e9106` — PR #27 Text Cleanup boundary
- GitHub product branch is authoritative. Do not assume a local clone is current without fetch/status.

Environment notes:
- Windows 11 x64
- Python: `G:\miniconda3` / Python 3.9
- QA install: `G:\ComfyUI-aki\数据集\人脸LoRA数据集筛选器_v0.3测试\Face-LoRA-Dataset-Selector`
- Auto Crop research clone: `G:\AI_Research\FaceLoRA_AutoCrop_Stage2`
- shared cache: `G:\AI_Research\_shared_cache\face-lora-dataset-selector\`
- original source tool folder must not be casually modified: `G:\ComfyUI-aki\数据集\人脸LoRA数据集筛选器`
- Valby dataset: `G:\ComfyUI-aki\数据集\渥尔比`

## Current objective

Finish v0.3 without another architecture detour.

The Auto Crop manual ROI blocker is now implemented and automatically validated. The project is at the planned consolidated HUMAN QA checkpoint.

Do not start broad UI refactoring before this checkpoint and final release gates are cleared.

Frozen workflow order:

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

## Verified complete

### Core recommendation behavior

- automatic recommendation baseline is independent of manual overrides;
- effective status is manual override over automatic status;
- F5/incremental refresh recomputes automatic recommendation correctly.

### Composite Split

- scans current active effective 推荐 only;
- accept materializes generated images immediately;
- generated outputs support per-output 推荐 / 淘汰;
- accepted source moves to `_CompositeSplit_Originals\`;
- archive is excluded from active dataset enumeration;
- generated outputs are incrementally analyzed instead of full-folder reanalysis.

### General Auto Crop backend

- post-Composite active 推荐 input;
- ISNetIS production runtime;
- alpha >= 0.10 support bbox + fixed 32 px padding;
- <5% removed-area no-op filter;
- source pixels untouched until export;
- accepted crop materialized only at Final Export;
- production parity against dghs-imgutils 0.19.0 passed.

Known non-blocking limitation:
- occasional foreground/background adhesion can make a proposal too loose;
- record it, do not reopen Stage 3.2 unless real QA shows it is frequent.

### Auto Crop manual ROI

Merged via PR #29 at `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf`.

Implemented:
- pyqtgraph `RectROI` 0.13.7;
- blue dashed immutable `auto_box`;
- green editable current `box`;
- whole-box drag;
- four-edge/four-corner resize;
- ROI bounded to image;
- live crop preview;
- manual edits persist;
- manual edit invalidates prior acceptance and returns to pending;
- Accept Current Crop;
- Reset to Automatic Proposal;
- Keep Original;
- Final Export uses accepted current box;
- v1 -> v2 metadata migration without ISNetIS rescan;
- backend edit/reset functions stay Qt-free behind `SelectorApplication`.

### Source Organizer

- optional independent feature;
- dry-run plan + explicit confirmation;
- 推荐 / 备选 / 淘汰 organization;
- preserves origin relative path/source semantics;
- ignores Composite archive;
- transaction staging;
- swap/cycle-safe rollback;
- persisted journal + crash recovery before next refresh;
- successful organize does not rerun analysis models.

### Text Cleanup

Detection + repair intentionally remain one mature module.

Completed:
- PP-OCR detector behind `features/text_cleanup`;
- existing suggestion heuristic preserved;
- state persistence behind backend;
- MI-GAN / TELEA / Navier-Stokes behind backend;
- batch filesystem output behind backend;
- `SubtitleTab` consumes `SelectorApplication`;
- removing the feature still allows main-window startup.

### Architecture

Current feature packages:
- `features/ranking`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

Boundary:
- Qt UI -> `SelectorApplication` -> feature backends;
- Import Linter enforces dependency direction and backend no-Qt rules.

Deferred debt:
- Duplicate primitives still under ranking and `DuplicateReviewDialog` remains legacy Qt in `app.py`;
- presentation is still largely in `app.py`; dedicated `ui/qt` migration is deferred.

## Validation performed

PR #29 head `d8e936f6854670873d6544fca9a86bf487a7cdf5`:
- Auto Crop Manual ROI Python 3.9: PASS
- Auto Crop Manual ROI Python 3.12: PASS
- Full selector self-test: PASS
- RectROI offscreen move/resize smoke: PASS
- Portable build: PASS
- packaged EXE self-test: PASS
- Architecture Boundaries: PASS
- Source Organizer: PASS
- UI Polish Regression: PASS
- Auto Crop Backend: PASS
- Text Cleanup Boundary: PASS

Portable QA artifact:
- name: `auto-crop-roi-portable-qa`
- artifact ID: `10652024749`
- size: 157,441,807 bytes
- generated from PR #29 tested head
- GitHub retention expiry: 2026-09-28

## Human QA state

Issue #17 is authoritative.

Still HUMAN UNVERIFIED as one consolidated checkpoint:
- Composite continuous batch flow;
- Composite per-output 推荐/淘汰;
- generated-files-only incremental analysis;
- recommendation baseline/manual override behavior after refresh;
- Auto Crop ROI drag;
- four-edge/four-corner resize;
- real interaction bounds;
- live crop preview;
- persistence after close/reopen;
- Reset;
- Accept edited crop;
- Keep Original;
- Final Export using edited ROI.

Source Organizer must be human-tested first on a disposable/copied dataset, never first on original Valby data.

## Immediate next action

Run the consolidated Portable human QA checkpoint from Issue #17.

Release gate after that:
1. Source Organizer human test on disposable copied dataset;
2. final local Valby end-to-end workflow QA;
3. close remaining production issues if all pass.

Only after those gates should architecture work resume.

The next bounded architecture debt is Duplicate modularization. A broad `app.py` / `ui/qt` rewrite is not the immediate next task.

## Relevant issues / PRs

- #17 — batched human QA checkpoint
- #21 — General Auto Crop production workflow; keep open until release/human gates pass
- #28 — manual draggable Auto Crop ROI; completed
- #29 — manual ROI implementation; merged
- #26 / #27 — Text Cleanup frontend/backend separation; completed/merged

## Do not repeat

- Do not revive failed custom Auto Crop Stage 1 saliency/pose safe-trim.
- Do not use raw DeepGHS person bbox as final crop boundary.
- Do not use every non-zero ISNetIS alpha pixel as foreground.
- Do not restore resolution-scaled 32/1024 padding; fixed 32 px is the validated behavior.
- Do not tune the single foreground/background adhesion case unless real QA proves it frequent.
- Do not split Text Cleanup into separate detection/repair product modules in this pass.
- Do not rewrite mature PP-OCR / repair algorithms during boundary work.
- Do not add microservices/local HTTP ceremony.
- Do not start a broad UI rewrite before v0.3 gates.
- Do not stop for separate human QA after every low-risk automated fix.
- Do not test Source Organizer first on original Valby data.
- Do not redownload reusable models/dependencies when verified cache exists.
- Do not default research/temp output to C:.

## User acceptance state

- Stage 2 ISNetIS subject-protection result: accepted.
- Stage 3.1: accepted as sufficient to proceed; one adhesion case recorded as non-blocking.
- Batched non-fatal manual QA policy: explicitly required.
- Feature modularity + frontend/backend separation: explicitly required.
- Text Cleanup remains one module: explicitly required and implemented.
- Auto Crop manual ROI was identified as missing; it is now implemented and AUTO PASS.
- v0.3 is not yet release-complete until consolidated human QA and final workflow gates pass.
