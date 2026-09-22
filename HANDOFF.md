# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Last verified product/code baseline: `c3aeabf4ec65c92ca3eb29f2b781d9e71cea8baf` — PR #29

## Just completed in this conversation

- Recovered that Auto Crop manual ROI was already implemented and merged.
- Corrected the mistaken idea that bounded architecture work must wait until the full human-QA checkpoint.
- Adopted the Engineering-Playbook write-through project continuity protocol as a pilot.

## Currently in flight

Continuity pilot:
- add canonical `docs/PROJECT_STATE.md`;
- add stable `AGENTS.md`;
- add PR continuity declaration;
- add Project Memory Gate;
- correct stale roadmap direction.

## Immediate next action

After continuity pilot verification, continue **Duplicate Review modularization**:
- separate Duplicate business/state behavior from Ranking / `app.py`;
- expose it through `SelectorApplication`;
- keep presentation thin;
- do not broaden into a whole-`app.py` rewrite.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — batched HUMAN UNVERIFIED
- PR #29 — Auto Crop manual ROI
- Engineering-Playbook `PROJECT_CONTINUITY.md`
