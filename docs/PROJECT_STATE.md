# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `4b574df844ffd2d795707eb7c6ea5440b5a61bd1` — merged PR #48, main Dataset View Qt Model/View modernization.
- Active UX/UI tracker: Issue #49 — Auto Crop review-surface reusable UI spike.
- GitHub product branch and active Draft PRs are authoritative; do not assume a local clone or this file alone is current without checking repository reality.

## Current objective

Continue the accepted **v0.3 Stage 3 UX/UI modernization** with bounded, behavior-preserving slices. Do **not** jump directly to consolidated release QA.

Accepted execution order:

1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete, including Duplicate and Text Cleanup boundaries.
3. **UX/UI modernization — active.**
4. Final unified Portable + consolidated human QA — later, after the UX/UI stage is accepted complete.

Stage 3 has completed two bounded slices: PR #46 extracted Text Cleanup presentation and proved OpenSpec continuity; PR #48 migrated the main Dataset View to a Qt Model/View seam and is merged at `4b574df844ffd2d795707eb7c6ea5440b5a61bd1`. Stage 3 now continues with Issue #49: one limited, user-visible Auto Crop review UI spike before the v0.3 release gate.

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

Issue #49 is the active tracker: **Auto Crop review-surface reusable UI spike**.

Why this is next:
- PR #48 already completed the main Dataset View Model/View seam; do not continue internal proxy/pagination work merely for architecture aesthetics;
- v0.3 is close to release and needs one bounded, visible UX/UI improvement rather than a whole-app redesign;
- Auto Crop is a new v0.3 review workflow with validated backend/ROI behavior and a contained presentation surface.

Current UX/UI rule:
- usability and visual quality are equal hard requirements;
- search for and actually reuse mature components/themes/templates before custom UI design;
- do not accept a visually rough solution merely because interaction is mature;
- do not accept a polished solution that weakens the crop-review workflow.

Current spike:
- existing pyqtgraph RectROI remains the crop interaction primitive;
- first reusable visual candidate is qt-material 2.17, tested only in CI initially;
- baseline / light_blue / dark_blue versions of the real Auto Crop dialog are rendered as screenshot artifacts;
- PySide6-Fluent-Widgets remains a second candidate if qt-material is not visually strong enough;
- no production UI library is adopted until the real render and compatibility evidence justify it.

PR #48 status is COMPLETE:
- merged at `4b574df844ffd2d795707eb7c6ea5440b5a61bd1`;
- Dataset View uses `DatasetListModel(QAbstractListModel)` + `DatasetListView(QListView)`;
- stable sample IDs drive UI action mapping;
- existing ViewSpec filter/sort and pagination semantics remain unchanged;
- OpenSpec change archived under `openspec/changes/archive/2026-09-23-modernize-dataset-view-model/`;
- Issue #47 closed.

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

1. Complete Issue #49 visual spike using the real Auto Crop dialog, not a mockup.
2. Inspect the rendered baseline / qt-material candidates for both usability and visual quality.
3. If qt-material is good enough, adopt it in one bounded Auto Crop-only change and measure Portable delta; if not, test PySide6-Fluent-Widgets rather than hand-designing a replacement.
4. Stop Stage 3 after this bounded release-facing UI slice unless a concrete blocker is discovered.
5. Build the unified Portable and run the consolidated human-QA checkpoint from Issue #17, then fix release blockers / obvious experience defects and publish v0.3.

Do not let either architecture cleanup or an open-ended UI redesign delay the release.

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
- Issue #49 — active Auto Crop review-surface reusable UI spike.
- Issue #47 / PR #48 — completed main Dataset View Model/View modernization.
- Issue #45 / PR #46 — completed OpenSpec pilot / Text Cleanup presentation extraction.
- Issue #17 — batched HUMAN UNVERIFIED queue.
- Issue #37 — completed; PR #38 — merged Duplicate Review modularization.
- Issue #21 — General Auto Crop production/release tracking.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
