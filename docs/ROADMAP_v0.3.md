# v0.3 Roadmap

Status date: 2026-09-22

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Duplicate Review workflow.
- AI Review Bundle / patch workflow.
- Composite Split detector research and production integration.
- Composite source archive semantics.
- Composite per-output keep/reject behavior.
- generated-files-only incremental analysis after Composite Review.
- automatic recommendation baseline separated from final manual override.
- batched non-fatal human-QA policy.
- Source Organizer backend/workflow with transaction + recovery safeguards.
- Text Cleanup frontend/backend separation while preserving detection + repair as one product module.
- General Auto Crop production backend and review workflow.
- General Auto Crop manual draggable/resizable ROI edit/reset workflow.

Some interaction changes are AUTO PASS but HUMAN UNVERIFIED; Issue #17 is the authoritative queue.

## Current

### Human QA checkpoint

The remaining v0.3 product blocker is no longer missing implementation. The project is now at the planned consolidated human-QA checkpoint.

Current Portable candidate:
- workflow: Auto Crop Manual ROI
- head tested before merge: `d8e936f6854670873d6544fca9a86bf487a7cdf5`
- merged product commit: `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf`
- artifact: `auto-crop-roi-portable-qa`
- artifact ID: `10652024749`
- Portable build + packaged EXE self-test: PASS

Automated PASS includes:
- Python 3.9 + 3.12 full selector self-test;
- Auto Crop backend regression;
- Auto Crop manual ROI bounds/persistence/reset/export tests;
- pyqtgraph RectROI offscreen move/resize smoke;
- Architecture Boundaries;
- Source Organizer regression;
- UI Polish regression;
- Text Cleanup Boundary;
- Portable build + packaged EXE self-test.

Human verification remains intentionally batched in Issue #17.

### General Auto Crop status

Manual ROI gap is implemented and merged via PR #29.

Behavior:
- blue dashed immutable automatic proposal;
- green current ROI;
- move + four-edge/four-corner resize;
- ROI bounded to source image;
- live crop preview;
- manual edit persists and returns decision to pending;
- Accept Current Crop explicitly approves current ROI;
- Reset restores `box = auto_box`;
- Keep Original remains available;
- Final Export uses accepted current `box`;
- source pixels remain untouched until export.

Persistence:
- proposal schema v2 stores `auto_box` and editable `box`;
- v1 metadata migrates without re-running ISNetIS.

Architecture:
- pyqtgraph is presentation-only;
- state mutation stays in `features/auto_crop` behind `SelectorApplication`;
- backend packages remain Qt-free.

Tracking:
- implementation issue #28: completed;
- broader Auto Crop production issue #21 remains open until human/release gates pass.

### Architecture state

The main product path has backend boundaries for:
- Ranking
- Composite
- Auto Crop
- Source Organizer
- Text Cleanup

Deferred architecture debt:
- Duplicate as its own independent feature package;
- dedicated `ui/qt` package / Qt Model-View migration.

Do not start a broad UI rewrite before v0.3 release gates are closed.

## v0.3 release gate

v0.3 is not final until:
- accumulated human-QA checkpoint in Issue #17 passes;
- Source Organizer is human-tested on a disposable copied dataset;
- final local Valby end-to-end workflow QA passes.

After those gates:
- close Auto Crop production Issue #21;
- decide whether Duplicate modularization belongs before v0.3 release or immediately after it;
- only then consider broader `ui/qt` presentation migration.
