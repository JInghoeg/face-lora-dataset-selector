# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product merge: `4b574df844ffd2d795707eb7c6ea5440b5a61bd1` — PR #48 main Dataset View Model/View modernization.
- Active tracker: Issue #49 — Auto Crop review-surface reusable UI spike.
- Current accepted phase: v0.3 Stage 3 UX/UI modernization.
- Project Memory Gate is active.

## Just completed in this continuation

- Completed and merged PR #48 at `4b574df844ffd2d795707eb7c6ea5440b5a61bd1`.
- Main Dataset View now has a bounded Qt Model/View seam with stable-ID action mapping.
- Archived `modernize-dataset-view-model` under `openspec/changes/archive/2026-09-23-modernize-dataset-view-model/`.
- Closed Issue #47.
- Hardened project-level UX/UI rules: usability and visual quality are equal hard requirements; mature reusable UI assets precede custom design.
- Opened Issue #49 and branch `ux/auto-crop-review-spike`.
- First visual spike uses the real Auto Crop dialog + existing pyqtgraph RectROI and renders reusable theme candidates in CI.
- Engineering-Playbook remains untouched.

## Currently in flight

Stage 3 UX/UI modernization continues under Issue #49.

The accepted product sequence is:
1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete.
3. **UX/UI modernization — active, now intentionally limited to the Auto Crop release-facing spike.**
4. Unified Portable + consolidated human QA — next after this bounded slice.

Issue #17 remains the batched HUMAN UNVERIFIED queue.

## Immediate next action

1. Adopt the selected Fluent light components in the real Auto Crop review dialog only.
2. Keep the existing RectROI/backend behavior and PySide6-Essentials runtime; install the UI package without Addons.
3. Measure Portable delta and verify the real production dialog before merge.
4. Then stop Stage 3 and move to unified Portable + consolidated QA for v0.3.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #49 — active Auto Crop reusable UI spike
- Issue #47 / PR #48 — completed Dataset View Model/View modernization
- Issue #45 / PR #46 — completed OpenSpec pilot
- Issue #17 — batched HUMAN UNVERIFIED for later consolidated QA
- PR #38 — merged Duplicate modularization
- Issue #21 — Auto Crop production/release tracking
- Engineering-Playbook `PROJECT_CONTINUITY.md`
