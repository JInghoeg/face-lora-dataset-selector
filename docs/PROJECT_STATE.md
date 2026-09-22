# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` — merged PR #38, Duplicate Review modularization
- GitHub product branch is authoritative; do not assume a local clone is current without checking fetch/status.

## Current objective

Finish the remaining v0.3 release-validation gates.

The bounded feature modularization pass for the known main workflow is complete:
- Ranking
- Duplicate Review
- Composite Split
- General Auto Crop
- Source Organizer
- Text Cleanup

Broad whole-application `app.py` / Qt Model-View migration remains deferred until after the v0.3 release gates.

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

### v0.3 release validation

No known implementation blocker remains in the frozen workflow.

Remaining work is the planned human/release validation:
- consolidated HUMAN UNVERIFIED checkpoint in Issue #17;
- Source Organizer human QA on a disposable/copied dataset;
- final local Valby end-to-end workflow QA.

## Blockers / uncertainties

No current code blocker is known.

Human QA is intentionally still outstanding. AUTO PASS must not be treated as user acceptance of the real interaction flow.

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

Run the consolidated Portable human-QA checkpoint from Issue #17.

Then:
1. Source Organizer human QA on a disposable copied dataset;
2. final local Valby end-to-end workflow QA;
3. close remaining production/release issues if all pass.

Do not start a broad UI rewrite before these gates are cleared.

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

Known presentation debt:
- much of the remaining Qt presentation is still concentrated in `app.py`;
- broader dedicated `ui/qt` / Qt Model-View migration is deferred.

This debt is not a current v0.3 implementation blocker.

## Do not repeat

- Do not reopen bounded feature modularization as a broad `app.py` rewrite before release validation.
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
- Issue #17 — batched HUMAN UNVERIFIED queue.
- Issue #37 — completed; PR #38 — merged Duplicate Review modularization.
- Issue #21 — General Auto Crop production/release tracking.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
