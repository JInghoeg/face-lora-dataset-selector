# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Pilot branch: `pilot/plan-recovery`
- Latest verified product/code baseline: `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` — merged PR #38, Duplicate Review modularization.
- GitHub product branch is authoritative for implementation reality.

## Accepted execution plan

During this pilot, the **accepted stage order is canonical in Issue #41**.

- Stage 1: COMPLETE — Auto Crop manual ROI (#28 / PR #29)
- Stage 2: COMPLETE — limited architecture wrap-up, including Text Cleanup (#26 / PR #27) and Duplicate (#37 / PR #38)
- Stage 3: ACTIVE — UX/UI modernization (#42)
- Stage 4: NOT STARTED — unified Portable + consolidated QA (#43)

Do not reconstruct or reorder this sequence from HANDOFF, ROADMAP summaries, commit recency, or inferred release status.

If another repository summary conflicts with Issue #41, report the conflict instead of silently choosing the newer wording.

## Current objective

Continue Stage 3: **UX/UI modernization** (#42).

Stage 3 scope:
- establish/expand `ui/qt`;
- progressively move presentation out of `app.py`;
- research Qt Model/View for relevant dataset/review surfaces;
- research and reuse mature Qt UI components where they fit;
- keep backend contracts stable; UI work must not trigger another broad backend redesign.

## Verified complete

Current architecture seam:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Feature packages:
- `features/ranking`
- `features/duplicate`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

Duplicate Review modularization is merged via PR #38 at `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` and AUTO PASS.

Auto Crop manual ROI is implemented through `pyqtgraph RectROI` and merged via PR #29.

Text Cleanup frontend/backend separation is merged via PR #27.

## Blockers / uncertainties

No known code blocker prevents entering Stage 3.

Human QA remains intentionally outstanding and accumulates in Issue #17 for Stage 4.

Source Organizer must be human-tested first on a disposable/copied dataset, never first on original Valby data.

## Human QA debt

Issue #17 is authoritative for accumulated HUMAN UNVERIFIED checks.

These checks do **not** redefine the current development phase. They feed Stage 4 (#43) unless a newly discovered destructive/release-blocking defect requires immediate interruption.

## Next action

Work from Stage 3 Issue #42.

Do not start Stage 4 as the main phase while Stage 3 remains active.

## Known stale/conflicting summaries under test

This pilot intentionally leaves older `docs/ROADMAP_v0.3.md` / `HANDOFF.md` wording untouched for the recovery test. Some of that wording says release QA comes before the broad UX/UI phase.

That wording conflicts with the accepted execution order in Issue #41 and must be treated as stale during this pilot.

The purpose is to test whether a fresh continuation can detect and surface the contradiction instead of following the stale summary.

## Architecture / workflow state

Frozen product workflow:

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

This product workflow is separate from the four-stage development execution plan in Issue #41.

## Do not repeat

- Do not reinterpret Issue #41 into a different stage order.
- Do not turn Stage 3 into another broad backend architecture pass.
- Do not stop for separate low-risk manual QA after every automated fix; use Issue #17 checkpoint.
- Do not revive failed custom Auto Crop Stage 1 saliency/pose safe-trim.
- Do not split Text Cleanup into separate detection/repair product modules in this pass.
- Do not test Source Organizer first on original Valby data.
- Do not default research/temp output to C:.

## Authoritative references

- Issue #41 — accepted v0.3 four-stage execution order for this pilot.
- Issue #42 — current active Stage 3 UX/UI modernization.
- Issue #43 — Stage 4 unified Portable + consolidated QA.
- Issue #17 — accumulated HUMAN UNVERIFIED queue.
- Issue #28 / PR #29 — completed Auto Crop manual ROI.
- Issue #26 / PR #27 — completed Text Cleanup boundary.
- Issue #37 / PR #38 — completed Duplicate boundary.
