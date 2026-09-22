# Project Handoff

Supplementary conversation cursor only. Canonical current truth is in `docs/PROJECT_STATE.md`.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product merge: `a227be9b98c7fe0365fd680040bd3d6e3d5b0b00` — PR #46 OpenSpec Text Cleanup presentation pilot.
- Active tracker: Issue #47 — main Dataset View Model/View modernization.
- Current accepted phase: v0.3 Stage 3 UX/UI modernization.
- Project Memory Gate is active.

## Just completed in this continuation

- Recovered project state from GitHub rather than old chat memory.
- Clean-context recovery gate for PR #46: PASS.
- Verified implementation against proposal/design/tasks with no mismatch.
- Synchronized stale QA-first PROJECT_STATE/HANDOFF/ROADMAP back to the accepted Stage 3 order.
- Archived `extract-text-cleanup-presentation` in one atomic commit.
- Final archive head passed all 9 current workflows, including Portable build/self-tests.
- Squash-merged PR #46 into the product branch at `a227be9b98c7fe0365fd680040bd3d6e3d5b0b00`.
- Closed completed stale UI polish Issue #16.
- Opened Issue #47 for the next bounded main Dataset View Model/View modernization slice.
- Engineering-Playbook remains untouched.

## Currently in flight

Stage 3 UX/UI modernization continues under Issue #47.

The accepted product sequence is:
1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete.
3. **UX/UI modernization — active.**
4. Unified Portable + consolidated human QA — later.

Issue #17 remains the batched HUMAN UNVERIFIED queue, but it is not the immediate mainline action.

## Immediate next action

1. Create the OpenSpec proposal/design/tasks for Issue #47.
2. Freeze the main Dataset View migration boundary before implementation: Qt Model/View roles, existing ViewSpec semantics, pagination/virtualization, thumbnail loading, stable IDs and manual actions.
3. Implement only the accepted bounded slice.

Do not jump to consolidated Portable human QA until Stage 3 is explicitly accepted complete.

## Relevant links only

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP_v0.3.md`
- Issue #47 — active Dataset View Model/View modernization
- Issue #45 / PR #46 — completed OpenSpec pilot
- Issue #17 — batched HUMAN UNVERIFIED for later consolidated QA
- PR #38 — merged Duplicate modularization
- Issue #21 — Auto Crop production/release tracking
- Engineering-Playbook `PROJECT_CONTINUITY.md`
