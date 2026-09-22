# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `a227be9b98c7fe0365fd680040bd3d6e3d5b0b00` — merged PR #46, completed OpenSpec Text Cleanup presentation pilot.
- Active UX/UI tracker: Issue #47 — main Dataset View Model/View modernization.
- GitHub product branch and active Draft PRs are authoritative; do not assume a local clone or this file alone is current without checking repository reality.

## Current objective

Continue the accepted **v0.3 Stage 3 UX/UI modernization** with bounded, behavior-preserving slices. Do **not** jump directly to consolidated release QA.

Accepted execution order:

1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete, including Duplicate and Text Cleanup boundaries.
3. **UX/UI modernization — active.**
4. Final unified Portable + consolidated human QA — later, after the UX/UI stage is accepted complete.

The first real Stage 3 slice, PR #46 / `extract-text-cleanup-presentation`, is complete and merged. The clean-context recovery test passed on 2026-09-22, the change was archived under `openspec/changes/archive/2026-09-22-extract-text-cleanup-presentation/`, and all final workflows including Portable self-tests passed. Stage 3 now continues with Issue #47: bounded modernization of the main Dataset View using mature Qt Model/View primitives.

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

Duplicate Review modularization is merged via PR #38 at `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` and AUTO PASS; validation ran on source head `4ca1e90b0b4a0e75b2342b3b7c8560d400843f34`:
- pHash grouping moved out of `features/ranking.analysis` into `features/duplicate`;
- duplicate group queries and review mutations are owned by the Duplicate backend;
- `SelectorApplication` is the Duplicate UI/backend seam;
- `DuplicateReviewDialog` moved out of `app.py` to `ui/qt/duplicate_review.py`;
- Ranking keeps only its internal duplicate-aware recommendation behavior and does not depend on the Duplicate sibling feature;
- Dataset refresh receives duplicate grouping as an optional injected callback, so removing the Duplicate feature does not break refresh/startup;
- Import Linter enforces sibling independence, backend no-Qt, and UI-through-application boundaries.

Validation at that head:
- Project Memory: PASS;
- Architecture Boundaries: PASS;
- Duplicate Boundary Python 3.9 + 3.12: PASS;
- Duplicate backend smoke: PASS;
- full selector self-test: PASS;
- offscreen Duplicate dialog smoke: PASS;
- physical Duplicate feature absence startup smoke: PASS;
- Auto Crop Backend: PASS;
- Auto Crop Manual ROI: PASS;
- UI Polish Regression: PASS;
- Text Cleanup Boundary: PASS;
- Source Organizer: PASS;
- Portable build + packaged EXE self-test: PASS.

Current Portable candidate built from this head:
- artifact: `auto-crop-roi-portable-qa`
- artifact ID: `10673035111`
- digest: `sha256:a521b912101b7cc6ca6e4b24d3bf5fb404abbbacaaca661cacb950cfad08f907`
- expires: 2026-09-29

Project continuity is active:
- `docs/PROJECT_STATE.md` is canonical current state;
- PRs declare state impact;
- local Project Memory Gate is validated;
- `HANDOFF.md` is supplementary only.

## In progress

### Stage 3 UX/UI modernization

Issue #47 is the active tracker for the next bounded slice: **main Dataset View Model/View modernization**.

Why this is next:
- PR #46 proved the OpenSpec/recovery workflow and extracted one low-risk presentation surface;
- the main Dataset View is still implemented as a manually rebuilt `QListWidget` inside `Window`;
- filter/sort/page state, thumbnail lifecycle and item presentation remain tightly coupled there;
- this is now the highest-leverage presentation seam for real Stage 3 work, without reopening feature algorithms.

The next change must settle design before implementation:
- preserve existing `ViewSpec` and manual-status semantics;
- use Qt's native `QAbstractListModel` / `QSortFilterProxyModel` / `QListView` path where it fits;
- decide pagination vs native view virtualization explicitly;
- keep async thumbnail work bounded;
- map stable sample IDs safely through model/proxy indexes;
- keep UI -> `SelectorApplication` -> backend boundaries intact.

PR #46 pilot status is COMPLETE:
- merged at `a227be9b98c7fe0365fd680040bd3d6e3d5b0b00`;
- OpenSpec change archived;
- clean-context recovery PASS;
- implementation verification PASS;
- final 9/9 workflows PASS after archive, including Portable self-tests;
- Engineering-Playbook unchanged.

## Blockers / uncertainties

No current code blocker is known.

Human QA is intentionally still outstanding. AUTO PASS must not be treated as user acceptance of the real interaction flow. This debt is tracked, but it is not the current main phase while Stage 3 UX/UI modernization is active.

## Human QA debt

Issue #17 is authoritative.

Still intentionally batched includes:
- recommendation baseline/manual override behavior after refresh;
- Composite continuous flow, per-output keep/reject, and generated-files-only incremental analysis;
- Duplicate Review post-refactor interaction/persistence checks;
- Auto Crop ROI real interaction/persistence/reset/export checks;
- Text Cleanup post-boundary interaction checks.

Source Organizer must be human-tested first on a disposable/copied dataset, never first on original Valby data.

## Next action

1. For Issue #47, create the bounded OpenSpec proposal/design/tasks for the main Dataset View.
2. Freeze the Model/View migration boundary before implementation, especially `ViewSpec`, pagination, async thumbnails, stable IDs, and manual actions.
3. Implement only that accepted slice; do not use it as a pretext for a whole-`app.py` rewrite.
4. Continue Stage 3 with further bounded UX/UI slices only after the current one is verified.
5. Only after Stage 3 is explicitly accepted complete, build the unified Portable and run the consolidated human-QA checkpoint from Issue #17.

Do not let the existing QA debt silently reorder Stage 3 and Stage 4.

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

Active presentation modernization:
- much of the remaining Qt presentation is still concentrated in `app.py`;
- merged PR #46 proves one bounded presentation surface can move into `ui/qt` while preserving the UI -> `SelectorApplication` -> backend boundary;
- broader visual/interaction improvements and any further Qt Model/View adoption must proceed as bounded Stage 3 slices, not as a whole-application rewrite.

This work is now the active v0.3 phase, but it must remain incremental and reversible.

## Do not repeat

- Do not turn Stage 3 UX/UI modernization into a broad whole-application `app.py` rewrite; use bounded, reviewable slices.
- Do not stop for separate low-risk manual QA after every automated fix; use Issue #17 checkpoint.
- Do not revive failed custom Auto Crop Stage 1 saliency/pose safe-trim.
- Do not use raw DeepGHS person bbox as final crop boundary.
- Do not use every non-zero ISNetIS alpha pixel as foreground.
- Do not restore resolution-scaled 32/1024 padding; fixed 32 px is validated.
- Do not split Text Cleanup into separate detection/repair product modules in this pass.
- Do not rewrite mature PP-OCR / repair algorithms merely for architectural aesthetics.
- Do not add microservices/local HTTP ceremony.
- Do not test Source Organizer first on original Valby data.
- Do not redownload verified reusable models/dependencies.
- Do not default research/temp output to C:.

## Authoritative references

- `docs/ROADMAP_v0.3.md` — v0.3 product roadmap and release gates.
- Issue #47 — active Stage 3 main Dataset View Model/View modernization.
- Issue #45 / PR #46 — completed OpenSpec pilot / Text Cleanup presentation extraction.
- Issue #17 — batched HUMAN UNVERIFIED queue.
- Issue #37 — completed; PR #38 — merged Duplicate Review modularization.
- Issue #21 — General Auto Crop production/release tracking.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
