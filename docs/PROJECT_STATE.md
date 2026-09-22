# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Last verified product/code baseline: `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf` — PR #29, Auto Crop manual ROI
- GitHub product branch is authoritative; do not assume a local clone is current without checking fetch/status.

## Current objective

Continue v0.3 development with bounded feature modularization and frontend/backend separation.

Immediate architecture target: **Duplicate Review**.

The current direction is:
- extract Duplicate business/state behavior into a clear feature boundary;
- expose it through `SelectorApplication`;
- keep Qt presentation thin;
- do not use this as an excuse for a broad `app.py` / `ui/qt` rewrite.

Batched human QA remains visible and required before release, but it is **not** a prerequisite for continuing this bounded modularization work.

## Verified complete

Current major backend/product boundaries already implemented:
- Ranking / recommendation behavior;
- Composite Split;
- General Auto Crop, including manual draggable/resizable ROI;
- Source Organizer backend/workflow;
- Text Cleanup as one detection + repair product module with backend separation.

Current architecture seam:
```
Qt presentation
-> SelectorApplication
-> feature backends
```

Import Linter enforces dependency direction and Qt-free backend boundaries.

Auto Crop manual ROI PR #29 passed Python 3.9/3.12 tests, full selector self-test, RectROI smoke, Portable build/EXE self-test, architecture regression, Source Organizer regression, UI regression, and Text Cleanup boundary checks.

## In progress

### Project continuity pilot

The Engineering-Playbook write-through continuity protocol is installed:
- `docs/PROJECT_STATE.md` is the canonical current-state entry point;
- PRs declare whether they change canonical project state;
- `HANDOFF.md` is supplementary rather than the sole recovery source;
- this smoke PR validates the Project Memory Gate against a real state-impacting change.

### Next bounded architecture work

Duplicate Review remains the next modularization target.

Known debt:
- duplicate grouping primitives still live under `features/ranking`;
- `DuplicateReviewDialog` remains legacy Qt inside `app.py`.

Target shape:
```
features/duplicate
-> SelectorApplication contract
-> thin Qt Duplicate Review presentation
```

## Blockers / uncertainties

No known missing implementation blocker currently prevents Duplicate modularization.

The reusable cross-repository Project Memory Gate must pass this smoke PR. If GitHub private-repository reusable-workflow access blocks it, keep the protocol and replace only the caller with a local gate implementation rather than weakening the continuity rule.

## Human QA debt

Issue #17 is authoritative for accumulated HUMAN UNVERIFIED checks.

Still intentionally batched includes:
- Composite continuous flow and per-output keep/reject behavior;
- generated-files-only incremental analysis;
- recommendation baseline/manual override behavior after refresh;
- Auto Crop ROI move/resize/bounds/live preview/persistence/reset/accept/Keep Original/export.

Source Organizer must be human-tested first on a disposable/copied dataset, never first on original Valby data.

Release still requires the consolidated QA checkpoint, copied-dataset Source Organizer QA, and final local Valby end-to-end QA.

## Next action

After this continuity pilot is merged and its gate behavior is verified, continue **Duplicate Review modularization**.

Do not pause for a broad manual-QA pass first unless new work crosses the existing risk-based immediate-validation boundary.

## Architecture / workflow state

Frozen user workflow:
```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

Current feature packages include:
- `features/ranking`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

Desired next package:
- `features/duplicate`

Broad presentation migration out of `app.py` remains deferred. Local UI extraction that naturally belongs to Duplicate modularization is allowed; whole-application UI refactoring is not the current objective.

## Do not repeat

- Do not stop bounded modularization merely because batched HUMAN UNVERIFIED items exist.
- Do not start a broad `app.py` / `ui/qt` rewrite now.
- Do not revive failed custom Auto Crop Stage 1 saliency/pose safe-trim.
- Do not use raw DeepGHS person bbox as final crop boundary.
- Do not use every non-zero ISNetIS alpha pixel as foreground.
- Do not restore resolution-scaled 32/1024 padding; fixed 32 px is validated.
- Do not split Text Cleanup into separate detection/repair product modules in this pass.
- Do not rewrite mature PP-OCR / repair algorithms merely for architectural aesthetics.
- Do not add microservices/local HTTP ceremony.
- Do not test Source Organizer first on original Valby data.
- Do not redownload verified reusable models/dependencies.
- Do not default research/temp output to C:.

## Authoritative references

- `docs/ROADMAP_v0.3.md` — v0.3 product roadmap and release gates.
- Issue #17 — batched HUMAN UNVERIFIED queue.
- Issue #21 — General Auto Crop production workflow/release tracking.
- PR #29 — Auto Crop manual ROI implementation.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
