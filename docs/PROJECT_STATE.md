# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `7e25f847b8f3964a8fa8ad79e10dd691f1ec55b8` — merged PR #38, Duplicate Review modularization
- Active UX/UI work: Draft PR #46 on `pilot/openspec-text-cleanup-ui` — OpenSpec pilot / Text Cleanup presentation extraction.
- GitHub product branch and active Draft PRs are authoritative; do not assume a local clone or this file alone is current without checking repository reality.

## Current objective

Continue the accepted **v0.3 Stage 3 UX/UI modernization** with bounded, behavior-preserving slices. Do **not** jump directly to consolidated release QA.

Accepted execution order:

1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete, including Duplicate and Text Cleanup boundaries.
3. **UX/UI modernization — active.**
4. Final unified Portable + consolidated human QA — later, after the UX/UI stage is accepted complete.

The first real Stage 3 slice is Draft PR #46, `extract-text-cleanup-presentation`. Its implementation and automated validation are complete, and the clean-context recovery test passed on 2026-09-22: a fresh continuation independently found PR #46 / the OpenSpec change, identified UX/UI modernization as the active phase, and flagged the older QA-first PROJECT_STATE/HANDOFF/ROADMAP direction as stale.

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

Draft PR #46 is the active work item.

Current pilot status:
- OpenSpec 1.13.1 strict validation: PASS;
- Text Cleanup Python 3.9 + 3.12 compile/backend/full-selector/extracted-UI smoke: PASS;
- optional Text Cleanup physical-removal startup: PASS;
- Portable build + packaged EXE self-test: PASS;
- Architecture Boundaries / UI Polish / Duplicate / Auto Crop / Source Organizer regressions: PASS;
- clean-context recovery gate: PASS;
- implementation vs proposal/design/tasks verification: PASS with no mismatch found.

Remaining pilot closeout is administrative/project-state work: finish the OpenSpec completion decision, archive the completed change when appropriate, and merge PR #46 into the product branch.

After PR #46 is finalized, continue Stage 3 with the next bounded UX/UI slice. Consolidated human QA remains deferred to the final Stage 4 checkpoint.

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

1. Finalize the OpenSpec pilot in PR #46: completion decision/archive + merge.
2. Start the next **bounded UX/UI modernization** slice using the same repository-first/OpenSpec workflow.
3. Only after Stage 3 is explicitly accepted complete, build the unified Portable and run the consolidated human-QA checkpoint from Issue #17.
4. Then run Source Organizer human QA on a disposable copied dataset and final local Valby end-to-end workflow QA.

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
- PR #46 proves one bounded presentation surface can move into `ui/qt` while preserving the UI -> `SelectorApplication` -> backend boundary;
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
- Issue #17 — batched HUMAN UNVERIFIED queue.
- Issue #37 — completed; PR #38 — merged Duplicate Review modularization.
- Issue #21 — General Auto Crop production/release tracking.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
