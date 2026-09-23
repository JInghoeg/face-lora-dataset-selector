# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product merge: `4b574df844ffd2d795707eb7c6ea5440b5a61bd1` — PR #48 main Dataset View Model/View modernization.
- Active tracker: Issue #49 — Auto Crop Fluent Filmstrip production adoption.
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

Stage 3 UX/UI modernization continues under Issue #49, but the research/visual-choice phase is complete.

User-confirmed production direction:
- Fluent component/visual language;
- Filmstrip layout;
- real thumbnail candidate strip with reduced dead space;
- current-item highlight + lightweight decision state;
- Auto Crop-scoped Light/Dark;
- theme toggle at the top-right of the Auto Crop window;
- existing RectROI/backend/persistence/export behavior unchanged.

The accepted product sequence remains:
1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete.
3. **UX/UI modernization — active only for this bounded Auto Crop production adoption.**
4. Unified Portable + consolidated human QA — next.

Issue #17 remains the batched HUMAN UNVERIFIED queue.

## Immediate next action

1. Implement the confirmed Fluent Filmstrip Auto Crop UI in production.
2. Add thumbnail-backed Filmstrip and scoped Light/Dark toggle.
3. Keep PySide6-Essentials/no-Addons.
4. Verify Python 3.9/3.12, ROI behavior, Light/Dark screenshots and Portable delta.
5. Then move to the v0.3 unified Portable + consolidated QA gate.

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
