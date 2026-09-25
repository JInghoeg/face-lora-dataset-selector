# Project State

Canonical current-state entry point. Repository reality and current user instruction override stale summaries.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- `main` protection: **ACTIVE** via repository ruleset `Protect main`
- Required checks on `main`: **continuity** + **Merge Gate**
- Force pushes/deletion on `main`: **blocked**
- PR requirement: **enabled**
- Automatic head-branch deletion after merge: **enabled and verified**
- Remote branches after historical cleanup: **main + active PR branches only**
- Stable release: **v0.3.0**
- Release target: `432321dacda585371b4728b0b2aee37909341f18`
- Windows Portable SHA-256: `43d7f8404c4311ba397118d174a8531f4a35d5717b1214708acd649b149f7742`
- v0.3 human QA: **PASS — explicitly accepted 2026-09-25**
- Current release line: **v0.4**
- v0.4 umbrella: **Issue #60**
- Release approval record: `.project/release_gate.json`

Historical repository note:
- current public repository: `JInghoeg/face-lora-dataset-selector`;
- old private/history repository: `JInghoeg/face-lora-dataset-selector-dev`.

## Verified complete

- v0.3.0 recovery PR #54 merged and stable v0.3.0 published.
- Final v0.3 pre-release CI: 10 / 10 PASS.
- v0.3 feature trackers closed after accepted human QA.
- Internal project docs moved under `.project/` by PR #61.
- Root-layout cleanup #62 / PR #63 completed with all affected workflows passing.
- Build/packaging helpers live under `tools/` and `packaging/`.
- Composite proposal/runtime implementation is owned by `features/composite/`.
- Chinese + English README switch shipped in PR #64.
- Project-governance hardening PR #67 merged after `continuity`, `Merge Gate`, full Portable and README-sync checks passed.
- `main` protection/ruleset is active and cannot be bypassed by the current user.
- Auto-delete-after-merge was verified on real PR branches.
- Release publishing now requires a matching machine-readable approved release gate with explicit HUMAN PASS.
- Docs-only PRs use a lightweight Portable classification path while still producing the required `Merge Gate`.
- Historical branch cleanup completed: all 42 stale non-main branches were audited and removed.
- Root Layout Phase 2 (#71) completed: product implementation is consolidated under `src/`, tracked runtime assets under `resources/`, and dependency manifests under `requirements/`.
- Root `app.py` and `text_detector.py` are intentionally tiny compatibility/entry shims rather than product implementation.
- Product architecture baseline is a modular monolith with feature-first boundaries.
- Source-data safety remains the baseline.

## In progress

- v0.4 planning / implementation under Issue #60.
- Focused open backlog: #55 / #56 / #57 / #59.
- HUMAN UNVERIFIED layout-migration interactive checkpoint is tracked in Issue #72; automated source/Portable/resource validation is the merge gate.

## Current objective

1. continue v0.4 from Issue #60 on the consolidated src/resources layout;
2. prioritize real-use UX/quality backlog from #59 / #56;
3. evaluate GPU acceleration separately in #55 before changing runtime dependencies;
4. keep README screenshot/document polish in #57 non-blocking;
5. preserve v0.3 behavior, governance gates, source-data safety, and the new root-layout invariant as the baseline.

## Blockers / uncertainties

- Text Cleanup false-positive / false-negative behavior needs real-example evaluation before threshold/model changes (#59).
- Optional NVIDIA CUDA acceleration is research only until benchmarked (#55).
- README screenshots remain non-blocking documentation work (#57).
- The root `text_detector.py` compatibility shim is intentionally retained as an explicit exception until a deliberate compatibility/deprecation decision is made.

## Human QA debt

- **v0.3: none.**
- Issue #72 — src-layout migration interactive startup/resource checkpoint (HUMAN UNVERIFIED; deferred to the next v0.4 checkpoint unless automation exposes a blocker).
- New v0.4 behavior must track HUMAN UNVERIFIED items in GitHub until a checkpoint.
- Destructive/data-loss/startup/release blockers still require prompt human verification when automation is insufficient.
- Process/docs-only changes may use HUMAN NOT REQUIRED when they cannot change runtime/user behavior.

## Next action

1. continue v0.4 work from Issue #60 on the consolidated repository layout;
2. start with the highest real-use impact items from #59 / #56;
3. keep performance research in #55 separate from UX work;
4. carry Issue #72 into the next v0.4 human-QA checkpoint rather than interrupting each bounded change.

## Do not repeat

- Do not infer human QA PASS from ambiguous wording or green CI.
- Do not publish a release without a matching approved release gate and explicit human acceptance.
- Do not write normal changes directly to `main`.
- Do not describe temporary pre-merge state as canonical post-merge state.
- Do not duplicate current state in HANDOFF or permanent workflow docs.
- Do not hardcode current-release Issue numbers into permanent process documentation.
- Do not scatter feature implementation/runtime files back into repository root; product implementation belongs under `src/` and tracked runtime assets under `resources/`.
- Do not move path-sensitive files without updating CI/scripts in the same change.
- Do not let continuity automation point at dead historical branches.
- Do not declare “nothing remains” after checking only open Issues/PRs; audit governance invariants too.
- Do not stop for manual QA after every bounded non-destructive fix; accumulate HUMAN UNVERIFIED items to a checkpoint unless risk requires immediate testing.
- Do not use chat summaries as a substitute for repository state.

## Authoritative trackers

Current:
- #60 — v0.4 umbrella
- #59 — UX backlog from accepted v0.3 QA
- #56 — Text Cleanup review sorting
- #55 — optional NVIDIA CUDA acceleration research
- #57 — README screenshots
- #72 — HUMAN UNVERIFIED src-layout migration interactive checkpoint

Completed baseline:
- PR #54 — v0.3 recovery implementation
- Issue #17 — v0.3 consolidated human QA
- PR #61 — internal documentation hygiene
- Issue #62 / PR #63 — repository root-layout cleanup
- PR #64 — bilingual README
- Issue #65 — docs-only Portable-build optimization
- Issue #66 / PR #67 — project-governance hardening
- Issue #68 — historical branch cleanup + auto-delete policy
- Issue #71 — Root Layout Phase 2 / src-layout consolidation
