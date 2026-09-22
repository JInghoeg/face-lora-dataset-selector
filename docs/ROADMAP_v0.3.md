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

### Stage 3 — UX/UI modernization

The accepted execution order is:

1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete.
3. **UX/UI modernization — active.**
4. Unified Portable + consolidated human QA — final checkpoint.

PR #46 (`pilot/openspec-text-cleanup-ui`) was the first bounded Stage 3 slice and repository OpenSpec pilot; it is now merged at `a227be9b98c7fe0365fd680040bd3d6e3d5b0b00`.

Completed PR #46 evidence:
- Text Cleanup presentation moved out of `app.py` into `ui/qt/text_cleanup.py`;
- shared `ImagePreview` and `ThumbnailWorker` extracted into reusable `ui/qt` components after code inspection showed real cross-surface reuse;
- UI dependencies are explicit through `SelectorApplication` and presentation/cache paths;
- no Text Cleanup backend/model/repair algorithm redesign;
- OpenSpec 1.13.1 strict validation: PASS;
- Python 3.9/3.12 Text Cleanup and extracted-UI smoke: PASS;
- Architecture / UI Polish / Duplicate / Auto Crop / Source Organizer regressions: PASS;
- Portable build + packaged EXE self-test: PASS;
- clean-context recovery test: PASS;
- proposal/design/tasks implementation verification: PASS.

The older QA-first state was intentionally retained long enough to test recovery drift detection. That test passed; the completed change is archived at `openspec/changes/archive/2026-09-22-extract-text-cleanup-presentation/` and final post-archive workflows are green.

Next bounded Stage 3 tracker: Issue #47 — main Dataset View Model/View modernization. It must use mature Qt Model/View primitives, preserve current application/backend boundaries, and freeze pagination/thumbnail/stable-ID behavior before implementation.

### Human QA queue

Issue #17 remains authoritative for accumulated HUMAN UNVERIFIED interaction checks.

Those checks are still required before release, but they are intentionally batched for Stage 4 rather than interrupting each bounded Stage 3 UX/UI change.

### Architecture / presentation direction

The backend/feature seam remains:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Stage 3 should reduce presentation concentration in `app.py` through bounded, reversible slices. It must not become a broad whole-application rewrite merely for architectural aesthetics.

## v0.3 remaining gates

Before v0.3 is considered release-complete:

1. complete and merge the bounded Stage 3 UX/UI modernization work;
2. build the final unified Portable candidate;
3. run the accumulated human-QA checkpoint in Issue #17;
4. human-test Source Organizer on a disposable copied dataset;
5. run final local Valby end-to-end workflow QA;
6. close remaining production issues such as Auto Crop Issue #21 when their gates pass.

Low-risk automated fixes may continue under the existing risk-based QA policy; they do not reorder the accepted Stage 3 -> Stage 4 sequence.
