# Project State

Canonical current-state entry point. Repository reality and current user instruction override stale summaries.

Repository artifacts describe reality; they do **not** by themselves authorize execution. Current user instruction determines the active implementation slice.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- `main` protection: **ACTIVE** via repository ruleset `Protect main`
- Required checks on `main`: **continuity** + **Merge Gate**
- Force pushes/deletion on `main`: **blocked**
- PR requirement: **enabled**
- Automatic head-branch deletion after merge: **enabled and verified**
- Stable release: **v0.3.1**
- Release target: `9c6195856ae373128092a4dda4a0a945468f6102`
- Windows Portable SHA-256: `ca8bb94cc5970d296b6a49d0bd1619c2832bdea59b1452a61c96512ad4626413`
- v0.3 human QA: **PASS — explicitly accepted 2026-09-25**
- Current release line: **v0.4**
- v0.4 umbrella: **Issue #60**
- Release approval record: `.project/release_gate.json`

Historical repository note:
- current public repository: `JInghoeg/face-lora-dataset-selector`;
- old private/history repository: `JInghoeg/face-lora-dataset-selector-dev`.

## Verified complete

- v0.3.0 recovery PR #54 merged and stable v0.3.0 published.
- Emergency v0.3.1 was published on 2026-10-04 after a reproduced Windows native access violation during initial Dataset Analysis. It carries the queued worker→GUI delivery fix, application-folder-only persistent state/logging, and bundled redistributable Composite / ISNetIS / MI-GAN weights. The official Portable SHA is recorded above.
- v0.3.1 was deployed on the target Windows workstation and the user confirmed normal operation after the corrected packaged-EXE self-test and real application launch. This is real-use verification; do not rewrite it as a generic future HUMAN PASS for unrelated v0.4 behavior.
- Final v0.3 pre-release CI: 10 / 10 PASS.
- v0.3 feature trackers closed after accepted human QA.
- Internal project docs moved under `.project/` by PR #61.
- Root-layout cleanup #62 / PR #63 completed with all affected workflows passing.
- Build/packaging helpers live under `tools/` and `packaging/`.
- Composite proposal/runtime implementation is owned by `src/features/composite/`.
- Chinese + English README switch shipped in PR #64.
- Project-governance hardening PR #67 merged after `continuity`, `Merge Gate`, full Portable and README-sync checks passed.
- `main` protection/ruleset is active and cannot be bypassed by the current user.
- Auto-delete-after-merge was verified on real PR branches.
- Release publishing requires a matching machine-readable approved release gate with explicit HUMAN PASS.
- Historical branch cleanup completed: all 42 stale non-main branches were audited and removed.
- Root Layout Phase 2 (#71 / PR #73) completed: product implementation is consolidated under `src/`, tracked runtime assets under `resources/`, and dependency manifests under `requirements/`.
- Root `app.py` and `text_detector.py` are intentionally tiny compatibility/entry shims rather than product implementation.
- Product architecture baseline is a modular monolith with feature-first boundaries.
- Source-data safety remains the baseline.
- Deferred v0.3 UI-polish Issue #16 was actually implemented and AUTO PASSed before closure; it is not lost carry-forward work.
- Long-operation progress/cancellation, Text Cleanup folder auto-scan, rollback-safe batch repair, shutdown handling and reusable QA workspace were recovered in PR #54 and accepted in v0.3.
- Old v0.3 research items for Valby benchmark, dataset-level recommendation, conditional semantic similarity and model upgrades were carried into v0.4 Issue #60; the 2026-09-25 audit restored two details that had been omitted during migration: disentanglement value where justified, and the quality-first rule for bundling required redistributable default models.
- Carry-forward audit on 2026-09-25 found one missing high-confidence product mainline: whole-product UI/UX modernization. It is now restored as Issue #75 and linked from #60.
- Accepted-plan / execution-authorization continuity hardening is complete via Issue #76 / PR #77: future directions now have canonical status, plan-impact metadata is gated, and product/runtime PRs must record current-user execution authorization.
- PR #78 merged at `016ff44a799e6ab95046a15a7cbd2f3dce55f631`: the research-only GPU benchmark harness and cost note are now on main. It also includes a continuity-gate bug fix that scopes State impact matching to the full Yes/No state-choice text. No production GPU provider decision was made.

## In progress

- v0.4 scope is tracked under Issue #60.
- v0.4 bootstrap #80 / PR #81 is **COMPLETE** on `main` at `89be1d8aa6f24e87131ce81343297309ba748ed8`.
- #83 / PR #84 — the merged Dataset Review UI candidate was explicitly rejected by the user on 2026-10-05 because it violated the previously established UI process and visual direction.
- PR #87 completed the exact rollback on `main` at `3b7e13d0497c2c0f0dcc8a466954a2561a104ae6`; the rejected Dataset Review shell is no longer on the production branch.
- Duplicate Review visual prototype #88 established the accepted shared review pattern. Production implementation Draft PR #90 is complete enough for automated validation (all latest gates PASS) but remains **HUMAN UNVERIFIED** and unmerged because the user explicitly chose to defer HUMAN PASS.
- Composite Split visual prototype #91 received explicit HUMAN PASS on 2026-10-10 and was closed unmerged as accepted visual reference evidence.
- Composite Split production PR #93 received explicit HUMAN PASS and was squash-merged to `main` at `472cbb1b81c549ac6fa04d987bd9a2d1f564b386`.
- **Active authorized UI slice: bounded main Dataset Review visual re-evaluation under Draft PR #94.** The prerequisite small-module patterns are now established by Auto Crop / Duplicate / Composite. #94 remains prototype-only until the user accepts a concrete render, must not revive rejected #83/#84 structure, and its current real-Qt render workflow is PASS.
- GPU benchmark infrastructure from #55 / PR #78 is already merged. Running target-workstation CPU/GPU measurements remains research/evaluation work; production GPU integration is still unauthorized.
- Draft PR #74 exists on `ux/text-cleanup-review-navigation`, but it came from an unapproved scope expansion. It is **frozen and non-canonical**: do not continue, merge, or treat #56 as complete unless the user explicitly adopts that implementation.
- HUMAN UNVERIFIED layout-migration interactive checkpoint is tracked in Issue #72.

## Current objective

1. keep Duplicate Review production PR #90 Draft and HUMAN UNVERIFIED until the user explicitly returns to that checkpoint;
2. prototype a new bounded main Dataset Review information architecture from current `main`, explicitly avoiding the rejected #83/#84 stacked-card shell;
3. require a concrete real-Qt render and explicit visual acceptance before any production Dataset Review replacement;
4. preserve current DatasetListModel / filtering / sorting / recommendation / persistence behavior during this visual phase.

No production main Dataset Review replacement, production GPU integration, PR #74 adoption, recommendation/model change, or manual Auto Crop entry-point implementation is active.

## Accepted future directions

This section is the compact recovery index for user-confirmed work that is **not the current authorized implementation slice**. Detailed scope remains in the linked Issues.

- **ACTIVE VISUAL DESIGN:** whole-product UI/UX modernization (#75) has completed Composite Split production (#93 merged). The current authorized slice is Draft PR #94, a bounded main Dataset Review visual re-evaluation that must not reuse the rejected #83/#84 stacked-card structure. Duplicate Review production PR #90 remains Draft/HUMAN UNVERIFIED by explicit user choice.
- **ACCEPTED — NOT SCHEDULED:** remaining real-use Text Cleanup UX/quality backlog (#59), including review navigation/wording/manual-box discoverability/existing-box editing/real-example detection-quality work. #56 is a focused sorting item, but Draft #74 is not adopted merely because it exists.
- **ACCEPTED — NOT SCHEDULED:** Valby v0.2 vs v0.3 benchmark, frozen Benchmark v1, dataset-level coverage/redundancy/marginal-value/disentanglement-value/per-sample explanation work carried by #60; validate dataset-level logic before making it default.
- **CONDITIONAL RESEARCH — NOT SCHEDULED:** semantic-similarity review only if it adds value beyond Duplicate Review; model upgrades only against confirmed selector failure modes with license/redistribution review (#60). If a model is required for the default product path and redistribution is permitted, do not drop it merely to reduce Portable size when that would reduce quality.
- **EVALUATE ONLY — IMPLEMENTATION NOT AUTHORIZED:** optional user-selected/manual Auto Crop entry point for missed crop-worthy images (#59). The user explicitly said to assess cost and not implement it yet.
- **DEFERRED / NON-BLOCKING:** real README product screenshots and public-facing screenshot polish (#57).

Execution ordering among these directions is intentionally **not inferred here**. The current user instruction selects the active slice.

## Blockers / uncertainties

- Text Cleanup false-positive / false-negative behavior needs real-example evaluation before threshold/model changes (#59).
- Optional NVIDIA CUDA acceleration is research only until benchmarked (#55).
- Whole-product UI/UX modernization needs bounded surface-by-surface design decisions; #75 does not authorize a broad rewrite.
- README screenshots remain non-blocking documentation work (#57).
- The root `text_detector.py` compatibility shim is intentionally retained until a deliberate compatibility/deprecation decision is made.

## Human QA debt

- **v0.3: none.**
- Issue #72 — src-layout migration interactive startup/resource checkpoint (HUMAN UNVERIFIED; deferred to the next v0.4 checkpoint unless automation exposes a blocker).
- #80 carry-forward behavior is **HUMAN UNVERIFIED on the v0.4/src-layout build** until the next coherent v0.4 checkpoint. v0.3.1 itself was real-use verified; do not infer that verification automatically covers the newly ported src-layout build.
- Duplicate Review production PR #90 is **HUMAN UNVERIFIED** despite green automation; the user explicitly deferred that HUMAN PASS while continuing the UI project.
- Composite Split prototype #91 is HUMAN PASS and closed unmerged as visual reference evidence.
- Composite Split production PR #93 received HUMAN PASS and is merged.
- New v0.4 behavior must track HUMAN UNVERIFIED items in GitHub until a checkpoint.
- Destructive/data-loss/startup/release blockers still require prompt human verification when automation is insufficient.
- Process/docs-only changes may use HUMAN NOT REQUIRED when they cannot change runtime/user behavior.

## Next action

1. render and inspect the bounded Dataset Review v2 visual prototype from current `main`;
2. keep it isolated from production `src/` until explicit user visual acceptance;
3. keep Duplicate Review PR #90 Draft and unmerged until the user explicitly returns to its HUMAN PASS;
4. keep PR #74 frozen unless the user explicitly adopts its Text Cleanup scope.

## Do not repeat

- Do not infer human QA PASS from ambiguous wording or green CI.
- Do not publish a release without a matching approved release gate and explicit human acceptance.
- Do not write normal changes directly to `main`.
- Do not describe temporary pre-merge state as canonical post-merge state.
- Do not duplicate current state in HANDOFF or permanent workflow docs.
- Do not hardcode current-release Issue numbers into permanent process documentation.
- Do not scatter feature implementation/runtime files back into repository root.
- Do not move path-sensitive files without updating CI/scripts in the same change.
- Do not let continuity automation point at dead historical branches.
- Do not declare “nothing remains” after checking only open Issues/PRs; audit governance invariants and closed trackers with deferred/future items.
- Do not stop for manual QA after every bounded non-destructive fix; accumulate HUMAN UNVERIFIED items to a checkpoint unless risk requires immediate testing.
- Do not use chat summaries as a substitute for repository state.
- Do not let an accepted future direction disappear when a release/umbrella/roadmap closes; perform the carry-forward audit.
- Do not treat an Issue, backlog entry, branch, Draft PR, PROJECT_STATE “next action”, or previous-agent activity as execution authorization.
- Do not treat a closed Issue as proof that every deferred/unchecked item inside it was completed; verify its disposition and successor tracker.

## Authoritative trackers

Current:
- #60 — v0.4 umbrella / accepted scope
- #75 — whole-product UI/UX modernization
- #59 — UX/quality backlog from accepted v0.3 QA
- #56 — Text Cleanup review sorting
- #55 — optional NVIDIA CUDA acceleration research
- #57 — README screenshots
- #72 — HUMAN UNVERIFIED src-layout migration interactive checkpoint

Non-canonical existing work:
- Draft PR #74 — unauthorized Text Cleanup navigation/sorting implementation; frozen pending explicit user decision

Accepted visual reference / pending production QA:
- Draft PR #88 — Duplicate Review visual prototype/reference evidence
- Draft PR #90 — Duplicate Review production implementation; all latest automated gates PASS, but HUMAN UNVERIFIED and intentionally unmerged

Accepted Composite visual reference:
- PR #91 — HUMAN PASS visual prototype; closed unmerged as reference evidence

Active Dataset Review visual prototype:
- Draft PR #94 — bounded v2 visual re-evaluation; production `src/` unchanged; HUMAN UNVERIFIED pending user visual review

Completed Composite production work:
- PR #93 — HUMAN PASS; squash-merged to `main` at `472cbb1b81c549ac6fa04d987bd9a2d1f564b386`

Rejected / corrective history:
- #83 / PR #84 — rejected Dataset Review UI candidate
- PR #87 — completed rollback of #84 on `main` at `3b7e13d0497c2c0f0dcc8a466954a2561a104ae6`

Completed baseline:
- #80 / PR #81 — v0.3.1 stability baseline carried into v0.4/main; merged at `89be1d8aa6f24e87131ce81343297309ba748ed8`
- PR #54 — v0.3 recovery implementation
- Issue #17 — v0.3 consolidated human QA
- PR #61 — internal documentation hygiene
- Issue #62 / PR #63 — repository root-layout cleanup
- PR #64 — bilingual README
- Issue #65 — docs-only Portable-build optimization
- Issue #66 / PR #67 — project-governance hardening
- Issue #68 — historical branch cleanup + auto-delete policy
- Issue #71 / PR #73 — Root Layout Phase 2 / src-layout consolidation
- Issue #76 / PR #77 — accepted-plan / execution-authorization continuity hardening
