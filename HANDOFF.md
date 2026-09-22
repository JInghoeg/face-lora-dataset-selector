# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product merge: `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` — PR #38 Duplicate Review modularization.
- Project Memory Gate is active.

## Just completed in this conversation

- Established write-through project continuity.
- Completed Duplicate Review modularization without broad `app.py` rewrite.
- Added `features/duplicate` backend.
- Routed Duplicate behavior through `SelectorApplication`.
- Moved only Duplicate Review presentation to `ui/qt/duplicate_review.py`.
- Preserved Ranking sibling independence.
- Added Duplicate-specific Python 3.9/3.12 CI and optional-feature-removal smoke.
- Full architecture, cross-feature regression, Portable build and packaged EXE validation passed.
- PR #38 merged; Issue #37 closed.
- Duplicate post-refactor interaction checks were added to Issue #17 as HUMAN UNVERIFIED.

## Currently in flight

No known implementation blocker in the frozen v0.3 workflow.

Remaining work is release validation.

## Immediate next action

Run the consolidated Portable human-QA checkpoint from Issue #17.

Then:
1. Source Organizer human QA on a disposable copied dataset;
2. final local Valby end-to-end QA.

Do not start a broad whole-application UI rewrite before these release gates.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — batched HUMAN UNVERIFIED
- PR #38 — merged Duplicate modularization
- Issue #21 — Auto Crop production/release tracking
- Engineering-Playbook `PROJECT_CONTINUITY.md`
