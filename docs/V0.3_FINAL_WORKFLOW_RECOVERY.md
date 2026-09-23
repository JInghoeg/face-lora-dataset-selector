# v0.3 Final Workflow Recovery

Status: FROZEN PRODUCT WORKFLOW

This document restores the end-to-end workflow that was agreed before Composite Split production integration drifted into being treated as the whole v0.3 release.

## Development principles

- Result first.
- Reuse mature implementations before custom algorithms or UI primitives.
- Only fix real blockers.
- Do not overturn already validated behavior without new evidence.
- Automation reduces human workload; human review remains authoritative.
- Discussion ideas do not become product rules until validated.
- Source images are never silently rewritten.
- Research / benchmark / temporary outputs default to a disposable project-drive directory such as `<project>/_research_output/`, not C:.

## End-to-end order

1. Initial analysis / selection / recommendation.
2. Duplicate Review.
3. Composite Split on final recommended images only.
4. General Auto Crop candidate detection and Auto Crop Review on the current active recommended dataset.
5. Optional: Organize Source Folder.
6. Final: Export Recommended Training Images.

Composite Split and Auto Crop are related crop workflows, but they solve different problems.

## Active dataset vs Composite source archive

Composite Split is a destructive workflow change to dataset membership, but never a destructive pixel edit.

The selector therefore maintains two physical areas inside/alongside the source dataset:

- **Active dataset**: images still participating in analysis, recommendation, Duplicate Review, Composite Split, Auto Crop, organization, AI bundle export and final training export.
- **Composite source archive**: original composite images that were accepted and split/group-cropped.

Reserved archive directory:

```
_CompositeSplit_Originals/
```

Rules:

- the archive directory and all descendants are excluded from every normal dataset enumeration;
- archived originals are not re-analysed on F5;
- archived originals do not enter Duplicate Review;
- archived originals do not enter Composite Split again;
- archived originals do not enter General Auto Crop;
- archived originals are not moved by Organize Source Folder;
- archived originals are not included in AI Review Bundles;
- archived originals are never included in Final Training Export;
- the archive exists only as a recoverable copy of the original composite source;
- accepting a Composite Split may move the source file into this archive, but must never overwrite or delete it.

## Composite Split

Purpose: normalize already-recommended composite material before General Auto Crop.

### Scan scope

Composite Split scans **only currently active images whose effective final selector status is 推荐**.

It must not spend detector work on:
- 备选;
- 淘汰;
- archived Composite originals;
- unrelated excluded folders.

### Detection behavior

- Independent people/views -> N split crops.
- Tightly overlapping people -> one conservative group crop.
- Noisy thumbnail/UI grids -> do not surface as candidates.
- Duplicate/fragment detections -> suppress before proposing outputs.
- Headless partial-body/equipment composites -> do not surface.

The validated DeepGHS person/head detector behavior remains unchanged unless real QA exposes a blocker.

### Reject

Reject means the image is not treated as a Composite Split source.

- the original remains in the active dataset;
- its existing 推荐 state remains;
- it continues through General Auto Crop like an ordinary recommended image.

### Pending

A pending recommended Composite proposal is not allowed to pass downstream silently.

- it does not enter General Auto Crop until resolved;
- it does not enter Final Training Export until resolved.

### Accept — materialize immediately

Accept is not merely metadata for a later export.

When a proposal is accepted:

1. Generate the approved split/group crop image files immediately from the original source.
2. Write those new files into the active source dataset.
3. Give each generated image a new persistent sample identity.
4. Set each generated image's effective selector state directly to 推荐.
5. Move the original composite source into the reserved `_CompositeSplit_Originals/` archive, preserving enough relative-path information to avoid collisions.
6. Remove the archived source from active in-memory records.
7. Add the generated split/group files to active in-memory records/cache without requiring a full unrelated-folder re-analysis.
8. After this commit, the generated images are ordinary active dataset images. Downstream stages do not need special Composite semantics for them.

Example:

```
Before:
dataset/
  A.jpg                  # 推荐 composite

After Accept:
dataset/
  A__split_01.jpg        # 推荐
  A__split_02.jpg        # 推荐
  _CompositeSplit_Originals/
    A.jpg                # archived, excluded forever from normal workflow
```

For a tightly overlapping group:

```
dataset/
  A__group_01.jpg        # 推荐
  _CompositeSplit_Originals/
    A.jpg
```

### Refresh semantics

After Accept, F5 must see only the generated active images, not the archived source.

Generated split/group images must behave like normal source-dataset images thereafter.

Composite Split is therefore a one-time dataset normalization stage, not a virtual derived-asset layer.

## General Auto Crop

Purpose: after Composite normalization, identify active recommended images that materially benefit from conservative trimming, including ordinary single-person images and newly generated split/group images.

Rules:
- scan only the current active 推荐 set;
- do not scan the Composite source archive;
- do not crop every image merely for aesthetics;
- do not assume ordinary single-person images should remain untouched;
- prefer extra background over cutting meaningful subject content;
- protect hair, hands, feet, clothing silhouette, skirts/coattails, weapons, props and characteristic accessories;
- no fixed target aspect ratio;
- only crop-worthy candidates enter Auto Crop Review;
- human review is authoritative.

Because Composite Split outputs are materialized as normal 推荐 files before this stage, Auto Crop does not need special Composite-aware coordinate chaining.

Auto Crop research status:
- retired custom MediaPipe + saliency baseline;
- DeepGHS raw person bbox Stage 1: detection useful, raw box unsafe as final crop;
- ISNetIS Stage 2 benchmark code exists but was not completed/validated;
- therefore no general Auto Crop production backend is currently approved.

Until Stage 2 (or another mature solution) passes real-data validation, do not invent a production crop algorithm.

## Auto Crop output semantics

Auto Crop Review stores an accepted crop decision/rectangle as metadata on the active image. It does not overwrite that active source image.

Actual Auto Crop pixels are written only by Final Training Export:

- accepted Auto Crop -> export the accepted crop;
- no accepted Auto Crop -> export/copy the current active image;
- source-folder organization never applies Auto Crop.

## Organize Source Folder

This is separate from training export.

Purpose: physically organize **active dataset images only** by final selector status.

Behavior:
- move active image originals into 推荐 / 备选 / 淘汰;
- do not touch `_CompositeSplit_Originals/`;
- do not crop, resize, recompress or otherwise alter pixels;
- non-image files stay where they are;
- preserve relative subdirectory structure by default;
- avoid filename collisions safely;
- repeated organization moves images between the three status roots instead of nesting 推荐/推荐 etc.;
- update in-memory paths and cache after moves;
- unchanged images must not require re-analysis solely because organization changed their path.

Composite Split-generated files are already ordinary active images, so they organize exactly like any other 推荐 image.

This action is optional.

## Final Training Export

Final Training Export operates only on the current active dataset.

Only final 推荐 images are exported.

Per recommended active image:
1. Auto Crop accepted -> export the accepted crop.
2. Otherwise -> copy/export the current image as-is.

Final Training Export does **not** need to regenerate Composite Split outputs or inspect archived Composite originals, because accepted Composite Split results were already materialized into the active dataset earlier.

Export always targets a separate user-selected output directory, never the source folder or its children.

## Recovery implementation order

The workflow recovery must proceed in this order:

1. Add one canonical active-image enumeration rule that excludes `_CompositeSplit_Originals/`.
2. Change Composite Scan scope from all records to active 推荐 records only.
3. Change Composite Accept to immediate materialization + source archival + in-memory/cache update.
4. Remove obsolete final-export-time Composite generation logic.
5. Run a small real Valby regression:
   - ordinary recommended image remains unchanged;
   - independent composite Accept -> N generated 推荐 images;
   - overlapping group Accept -> one generated 推荐 group crop;
   - original source moves into archive;
   - archive is invisible after F5;
   - generated images remain normal active 推荐 records.
6. Only after this passes, resume General Auto Crop Stage 2 research.

## Release gate

The current `feature/v0.3-composite-split` Portable is a Composite Split QA artifact only, not the final v0.3 release candidate.

v0.3 cannot be called final until:
- corrected Composite Split materialization semantics pass real Valby QA;
- general Auto Crop backend passes real Valby validation;
- Auto Crop Review is integrated;
- Organize Source Folder is integrated;
- final export applies accepted Auto Crop over the active recommended dataset;
- the full workflow passes local Valby UI QA.


## Confirmed QA blocker resolution — 2026-09-21

These semantics were confirmed before implementation and are part of the recovery contract.

### Composite Review continuity

- Opening/scanning Composite candidates must not clear or rebuild the main dataset grid.
- Composite scanning remains scoped to active 推荐 images and reports explicit progress.
- Review is a continuous batch workflow: accepting one candidate moves directly to the next candidate.
- Accepting a candidate must not call the full-folder `Window.start()` / Analyzer path.
- Materialized outputs from the whole review session are queued and analyzed once, incrementally, after the review batch.
- Only generated files are analyzed in that incremental pass.
- Existing records stay in memory; archived Composite sources are removed locally.
- Page/filter/sort state is preserved during this workflow.

### Per-output selection

Every proposed split/group output is shown as an independently selectable output.

- all outputs are selected by default;
- user may deselect unwanted outputs;
- Accept materializes all proposed outputs;
- selected outputs receive manual status 推荐;
- deselected outputs receive manual status 淘汰;
- the original Composite source is archived exactly once;
- Reject keeps the original active 推荐 image unchanged;
- Pending remains unresolved.

The output selection exists to let the user preserve useful crops while explicitly sending bad crops to 淘汰 without abandoning the whole Composite candidate.

### Automatic target is independent from manual overrides

The automatic target N means N recommendations chosen by the algorithm from images that are **not manually pinned**.

- any record with `manual_status != None` is excluded from the automatic quota pool;
- manual 推荐 is additive and never consumes an automatic slot;
- manual 备选/淘汰 also does not consume an automatic slot;
- effective status remains `manual_status ?? auto_status`;
- when a manual state is added/changed/cleared, the lightweight in-memory recommendation pass may rerun to backfill the automatic target;
- F5/incremental analysis must not demote old automatic recommendations merely because manual recommendations exist.

### Scope

Only these version blockers are fixed in this recovery iteration. Deferred pagination/custom-target/progress polish remains tracked separately in Issue #16, except progress directly required to make the Composite/background operation understandable.
