# v0.3 Roadmap

Status date: 2026-09-22

Canonical current-state summary:
`docs/PROJECT_STATE.md`

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Duplicate Review workflow behavior.
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

### Bounded architecture work — Duplicate Review

Continue feature modularization and frontend/backend separation without turning it into a broad UI rewrite.

Current debt:
- duplicate grouping primitives still live under `features/ranking`;
- `DuplicateReviewDialog` remains legacy Qt in `app.py`.

Target:
```
features/duplicate
-> SelectorApplication contract
-> thin Qt Duplicate Review presentation
```

This work may proceed while low-risk HUMAN UNVERIFIED items remain batched.

Do **not** interpret the human-QA release gate as a requirement to stop bounded modularization first.

Broad `app.py` / `ui/qt` migration remains deferred.

### Human QA queue

Issue #17 remains authoritative for batched HUMAN UNVERIFIED checks.

The current Auto Crop Portable candidate remains useful for the later consolidated checkpoint:
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

Known non-blocking limitation:
- occasional foreground/background adhesion may make a proposal too loose;
- do not reopen Stage 3.2 unless real QA shows this is frequent.

### Architecture state

Backend boundaries currently exist for:
- Ranking
- Composite
- Auto Crop
- Source Organizer
- Text Cleanup

Next boundary:
- Duplicate

Deferred until later:
- broad dedicated `ui/qt` package / whole-application Qt Model-View migration.

## v0.3 remaining gates

Before v0.3 is considered release-complete:

1. complete the bounded Duplicate modularization work without broad UI refactor;
2. run the accumulated human-QA checkpoint in Issue #17;
3. human-test Source Organizer on a disposable copied dataset;
4. run final local Valby end-to-end workflow QA;
5. close remaining production issues such as Auto Crop Issue #21 when their gates pass.

Low-risk automated changes may continue between these gates under the existing risk-based QA policy.
