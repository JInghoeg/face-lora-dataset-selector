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
- Release approval record: `.project/release_gate.json`

Historical repository note:
- current public repository: `JInghoeg/face-lora-dataset-selector`;
- old private/history repository: `JInghoeg/face-lora-dataset-selector-dev`.

## Verified complete

- v0.3.0 recovery PR #54 merged and stable v0.3.0 published.
- Final v0.3 pre-release CI: 10 / 10 PASS.
- v0.3 feature trackers closed after accepted human QA.
- Internal project docs moved under `.project/` by PR #61.
- Root-layout cleanup #62 / PR #63 completed with all 8 affected workflows passing.
- Build/packaging helpers live under `tools/` and `packaging/`.
- Composite proposal/runtime implementation is owned by `features/composite/`.
- Chinese + English README switch shipped in PR #64.
- Product architecture baseline is a modular monolith with feature-first boundaries.
- Source-data safety remains the baseline.

## In progress

- Issue #66 — project governance hardening.
- Issue #65 — docs-only PR Portable-build filtering; resolved by the governance hardening change once merged.
- Repository-level `main` protection/ruleset still requires administrator configuration after the workflow changes land.
- Issue #68 tracks stale remote branches and `delete_branch_on_merge: false`.

## Current objective

1. merge the governance-hardening PR only after its workflow changes pass;
2. configure `main` protection/ruleset to require PRs and required checks;
3. close #65 when docs-only Portable filtering is verified;
4. keep #66 open until repository protection is confirmed;
5. then resume v0.4 implementation from #60.

## Blockers / uncertainties

- GitHub reports `main` as **protected: false** and repository Rulesets API returns no rulesets.
- Repository currently has **44 remote branches / 43 non-main branches**, and `delete_branch_on_merge` is false (#68).
- Text Cleanup false-positive / false-negative behavior needs real-example evaluation before threshold/model changes (#59).
- Optional NVIDIA CUDA acceleration is research only until benchmarked (#55).
- README screenshots remain non-blocking documentation work (#57).
- The root `text_detector.py` compatibility shim is intentionally retained until a deliberate compatibility/deprecation decision is made.

## Human QA debt

- **v0.3: none.**
- New v0.4 behavior must track HUMAN UNVERIFIED items in GitHub until a checkpoint.
- Destructive/data-loss/startup/release blockers still require prompt human verification when automation is insufficient.
- Process/docs-only changes may use HUMAN NOT REQUIRED when they cannot change runtime/user behavior.

## Next action

1. complete Issue #66 workflow/process hardening and verify CI;
2. configure the GitHub `main` branch ruleset/protection;
3. re-audit current state after protection is active;
4. begin v0.4 work from Issue #60.

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
- #65 — avoid full Portable builds for docs-only PRs
- #66 — project governance hardening
- #68 — stale branch cleanup + auto-delete policy

Completed baseline:
- PR #54 — v0.3 recovery implementation
- Issue #17 — v0.3 consolidated human QA
- PR #61 — internal documentation hygiene
- Issue #62 / PR #63 — repository root-layout cleanup
- PR #64 — bilingual README
