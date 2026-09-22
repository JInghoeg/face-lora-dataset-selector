# v0.3 Roadmap

Status date: 2026-09-22

Canonical current-state summary:
`docs/PROJECT_STATE.md`

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Ranking/recommendation backend boundary.
- Duplicate Review feature module + frontend/backend boundary.
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
- repository-resident PROJECT_STATE + Project Memory Gate continuity protocol.

Some interaction changes are AUTO PASS but HUMAN UNVERIFIED; Issue #17 is authoritative.

## Current

### v0.3 release validation

The bounded architecture pass for the known main workflow is complete.

Current feature boundaries:
- Ranking
- Duplicate
- Composite
- Auto Crop
- Source Organizer
- Text Cleanup

Duplicate Review AUTO PASS evidence:
- merged PR #38: `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8`;
- validated source head: `4ca1e90b0b4a0e75b2342b3b7c8560d400843f34`;
- Python 3.9 + 3.12 Duplicate Boundary: PASS;
- full selector self-test: PASS;
- Duplicate backend smoke: PASS;
- offscreen Duplicate dialog smoke: PASS;
- optional Duplicate feature removal/startup smoke: PASS;
- Architecture Boundaries: PASS;
- Auto Crop / Text Cleanup / Source Organizer / UI regression: PASS;
- Portable build + packaged EXE self-test: PASS.

Current Portable QA candidate:
- artifact: `auto-crop-roi-portable-qa`
- artifact ID: `10673035111`
- built from PR #38 source head
- expires: 2026-09-29

### Human QA queue

Issue #17 remains authoritative for batched HUMAN UNVERIFIED checks.

The next checkpoint should cover the accumulated real interaction flow, including the newly refactored Duplicate Review.

### General Auto Crop status

Manual ROI gap remains implemented and AUTO PASS.

Known non-blocking limitation:
- occasional foreground/background adhesion may make a proposal too loose;
- do not reopen Stage 3.2 unless real QA shows this is frequent.

### Architecture state

Main backend/feature boundaries are now in place for the frozen workflow.

Remaining architecture debt:
- broad presentation concentration in `app.py`;
- full dedicated `ui/qt` / Qt Model-View migration.

These are deferred until after v0.3 release gates; do not turn them into a pre-release rewrite.

## v0.3 remaining gates

Before v0.3 is considered release-complete:

1. run the accumulated human-QA checkpoint in Issue #17;
2. human-test Source Organizer on a disposable copied dataset;
3. run final local Valby end-to-end workflow QA;
4. close remaining production issues such as Auto Crop Issue #21 when their gates pass.

Low-risk automated fixes may continue between these gates under the existing risk-based QA policy.
