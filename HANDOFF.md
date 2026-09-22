# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Duplicate Review implementation validated at PR #38 source head `4ca1e90b0b4a0e75b2342b3b7c8560d400843f34`.
- Project Memory Gate is active.

## Just completed in this conversation

- Established write-through project continuity.
- Corrected stale direction that bounded modularization must wait for human QA.
- Completed Duplicate Review modularization without broad `app.py` rewrite.
- Added `features/duplicate` backend.
- Routed Duplicate through `SelectorApplication`.
- Moved only Duplicate Review presentation to `ui/qt/duplicate_review.py`.
- Preserved Ranking sibling independence.
- Added Duplicate-specific 3.9/3.12 CI and optional-feature-removal smoke.
- Full architecture/regression/Portable validation passed.

## Currently in flight

PR #38 is being finalized/merged.

HUMAN UNVERIFIED remains batched in Issue #17.

## Immediate next action

Run the consolidated Portable human-QA checkpoint from Issue #17.

Then test Source Organizer on a disposable copied dataset and run final local Valby end-to-end QA.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — batched HUMAN UNVERIFIED
- Issue #37 / PR #38 — Duplicate modularization
- Issue #21 — Auto Crop production/release tracking
- Engineering-Playbook `PROJECT_CONTINUITY.md`
