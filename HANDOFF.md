# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Last verified product/code baseline: `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf` — PR #29
- Project continuity infrastructure: active; Project Memory Gate validated by PR #35.

## Just completed in this conversation

- Recovered that Auto Crop manual ROI was already implemented and merged.
- Corrected the stale direction that bounded architecture work must wait for the full human-QA checkpoint.
- Adopted the Engineering-Playbook write-through continuity protocol.
- Added canonical `docs/PROJECT_STATE.md`, `AGENTS.md`, PR continuity declaration, and automated Project Memory Gate.
- Verified the gate on real state-impacting PRs.
- Kept HUMAN UNVERIFIED items batched in Issue #17.

## Currently in flight

Next product work: **Duplicate Review modularization**.

Target:
```
features/duplicate
-> SelectorApplication contract
-> thin Qt Duplicate Review presentation
```

Do not broaden this into a whole-`app.py` / `ui/qt` rewrite.

## Immediate next action

Inspect the current Duplicate grouping/state/dialog dependencies and implement the smallest clean feature boundary.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — batched HUMAN UNVERIFIED
- PR #35 — validated Project Memory Gate
- Engineering-Playbook `PROJECT_CONTINUITY.md`
