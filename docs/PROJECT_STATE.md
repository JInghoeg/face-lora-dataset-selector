# Project State

Canonical current-state entry point. Repository reality and current user instruction override stale summaries.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- Stable release: **v0.3.0**
- Release target: `432321dacda585371b4728b0b2aee37909341f18`
- Windows Portable SHA-256: `43d7f8404c4311ba397118d174a8531f4a35d5717b1214708acd649b149f7742`
- v0.3 human QA: **PASS — explicitly accepted 2026-09-25**
- Current release line: **v0.4**
- v0.4 umbrella: **Issue #60**

Historical repository note:
- current public repository: `JInghoeg/face-lora-dataset-selector`;
- old private/history repository: `JInghoeg/face-lora-dataset-selector-dev`.

## Verified complete

- v0.3.0 recovery PR #54 merged.
- Final v0.3 pre-release CI: 10 / 10 PASS.
- Stable v0.3.0 Release and Portable published.
- v0.3 feature trackers closed after accepted human QA.
- Internal project docs moved under `.project/` by PR #61.
- Product architecture baseline is a modular monolith with feature-first boundaries.
- Long-running analysis/export operations have explicit progress/cancellation where implemented.
- Source-data safety remains the baseline: analysis/export/repair/crop workflows do not silently overwrite source pixels.

## In progress

- Issue #62 — clean repository root layout and finish feature ownership.
- No open product PR is allowed to bypass the Project Memory Gate once #62 lands.

## Current objective

1. finish #62 with no product behavior change;
2. keep root limited to deliberate project/user entrypoints, standard configs and source directories;
3. use #60 as the v0.4 release-level entry point;
4. prioritize real-use UX/quality backlog from #59 / #56;
5. evaluate GPU acceleration separately in #55 before changing runtime dependencies.

## Blockers / uncertainties

- Text Cleanup false-positive / false-negative behavior needs real-example evaluation before threshold/model changes (#59).
- Optional NVIDIA CUDA acceleration is research only until benchmarked (#55).
- README screenshots remain non-blocking documentation work (#57).
- The root `text_detector.py` compatibility shim is intentionally retained until a deliberate compatibility/deprecation decision is made.

## Human QA debt

- **v0.3: none.** The release was explicitly accepted.
- New v0.4 behavior must track HUMAN UNVERIFIED items in GitHub until a checkpoint.
- Destructive/data-loss/startup/release blockers still require prompt human verification when automation is insufficient.

## Next action

1. complete #62 root-layout CI and merge only if all affected workflows pass;
2. verify the final root tree after merge;
3. close #62;
4. begin v0.4 implementation from #60, starting with the highest real-use impact items.

## Do not repeat

- Do not infer human QA PASS from ambiguous wording or green CI.
- Do not publish a release before explicit human acceptance.
- Do not scatter feature implementation/runtime files back into repository root.
- Do not move path-sensitive files without updating CI/scripts in the same change.
- Do not let Project Memory/continuity automation point at dead historical branches.
- Do not stop for manual QA after every bounded non-destructive fix; accumulate HUMAN UNVERIFIED items to a checkpoint unless risk requires immediate testing.
- Do not use chat summaries as a substitute for repository state.

## Authoritative trackers

Current:
- #60 — v0.4 umbrella
- #59 — UX backlog from accepted v0.3 QA
- #56 — Text Cleanup review sorting
- #55 — optional NVIDIA CUDA acceleration research
- #57 — README screenshots
- #62 — repository root-layout cleanup

Completed baseline:
- PR #54 — v0.3 recovery implementation
- Issue #17 — v0.3 consolidated human QA
- PR #61 — internal documentation hygiene
