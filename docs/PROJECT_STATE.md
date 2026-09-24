# Project State

Canonical current-state entry point.

## Repository identity

- Current canonical product/development repository: `JInghoeg/face-lora-dataset-selector`.
- Current repository ID: `1375744778`; visibility: **public**.
- Historical original/private repository was renamed to `JInghoeg/face-lora-dataset-selector-dev`.
- Historical repository ID: `1364913841`; visibility: **private**.
- Despite the `-dev` suffix, it is the old repository/history. **Current development also happens in the public `face-lora-dataset-selector` repository.**
- Never treat the historical “private baseline” fact as the visibility/state of the current repository.
- Do not warn the user merely because the current repository is public; that is the intended state.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- Stable release: **v0.3.0 — published 2026-09-25**.
- Release commit/tag target: `432321dacda585371b4728b0b2aee37909341f18`.
- Windows Portable SHA-256: `43d7f8404c4311ba397118d174a8531f4a35d5717b1214708acd649b149f7742`.
- v0.3 recovery PR #54: **MERGED**.
- v0.3 final pre-release CI: **10 / 10 PASS**.
- v0.3 human QA: **PASS — explicitly accepted by the user on 2026-09-25**.
- Current phase: **v0.3 released; repository cleanup + v0.4 planning**.

The prematurely published/withdrawn v0.3.0 artifact from 2026-09-24 is obsolete historical evidence. The valid stable v0.3.0 is the release targeting commit `432321d`.

## Latest recovery batch

At code commit `8ce96a9`, the current recovery branch includes:

- truthful live zh_CN / en_US coverage across the currently exposed Dataset Selector and Text Cleanup surfaces;
- Auto Crop fit-to-view / ROI-handle / splitter interaction fixes;
- explicit asynchronous final-export progress;
- cooperative cancellation for initial/refresh/re-analysis, Auto Crop, Text Cleanup scan, and duplicate grouping;
- conservative native-runtime CPU thread budgeting so background inference does not consume every logical CPU and freeze the Qt process;
- Text Cleanup input-folder selection automatically starts the real scan worker instead of appearing to do nothing;
- Text Cleanup batch repair is cooperatively cancellable and stages the whole run before commit; cancellation/failure removes staging and commit rollback protects pre-existing destination files;
- main-window shutdown now owns/stops Text Cleanup scan/batch and Text Cleanup thumbnail QThreads;
- regression coverage for long-operation controls, transactional Text Cleanup cancellation, shutdown lifecycle and Text Cleanup auto-scan.
- manual Portable QA now uses the canonical `tools/qa-portable.ps1` workspace helper with a persistent Portable runtime and persistent `_FaceLoRA_ModelCache`; `current` contains only disposable QA metadata/scratch.
- Build Windows Portable publishes both the full Portable and a fingerprinted QA Overlay. `Prepare` reuses compatible stable runtime files and downloads only the overlay; it automatically falls back to a full refresh when Python/dependency/packaged-runtime identity changes.
- pre-convention `FaceLoRA-QA-*` directories are handled safely: `Prepare` may reuse a manifest-compatible old extracted runtime, while `CleanLegacy -Force` migrates cached models before deleting legacy folders.

The GPU question is **not implemented yet**. Current inference remains CPU-oriented. GPU acceleration must be evaluated as a dependency/packaging/runtime decision before introducing `onnxruntime-gpu` or another GPU runtime.

The optional self-selected/manual crop expansion requested during QA remains explicitly deferred; do not pull it into the current blocker batch.

## Automated validation

For `8ce96a9`:

- 10 / 10 GitHub Actions workflows: **PASS**.
- Windows Portable artifact: `10795898471`.
- Portable artifact digest: `sha256:2a50cfd5232671bf65c2f0f262ca47c0265669f991c29c0e055dd566cd7fcbc7`.
- Automated evidence is useful diagnostic evidence only and is **not** human release acceptance.

## QA workspace / bandwidth validation

QA infrastructure was end-to-end validated at commit `9b0c17133ddd1a0c742e3ab00d693f60ddfa0bed` with Build Windows Portable run `35975899284`:

- packaged Portable self-test: **PASS**;
- incremental QA Overlay build: **PASS**;
- full ZIP/checksum build: **PASS**;
- real helper roundtrip smoke: first `Prepare` = `full`, second `Prepare` = `overlay`: **PASS**;
- the full artifact was requested exactly once across the two prepares;
- a model-cache marker survived the overlay prepare;
- the overlay-prepared EXE matched the built candidate and passed `--self-test`;
- UI Polish helper safety smoke passed on Python 3.9 and 3.12: `Clean` preserves runtime/models, `ResetRuntime` preserves models, and `CleanLegacy -Force` migrates legacy model cache before deletion.

Validated artifact sizes:

- full Portable artifact: `10798038264` — 159,788,262 bytes;
- QA Overlay artifact: `10798043254` — 10,930,018 bytes.

For ordinary code-only QA updates with unchanged runtime identity, this reduces candidate download traffic by about **93%**, while on-demand model downloads are reused instead of downloaded again.

## Human QA acceptance

The consolidated real v0.3 QA checkpoint was explicitly accepted by the user on **2026-09-25**.

Result: **PASS**.

Non-blocking findings from the accepted QA are deferred to v0.4 rather than reopening the v0.3 gate. Canonical tracker: **Issue #59 — v0.4 UX backlog from v0.3 human QA**.

Key deferred items include:
- Text Cleanup pagination/navigation discoverability;
- Text Cleanup zero-result ordering and review sorting;
- clearer manual-box interaction and possible direct box editing;
- Text Cleanup false-positive / false-negative tuning;
- optional user-selected/manual Auto Crop entry point;
- related backlog #56 and GPU research #55 remain separate as appropriate.

## Current objective

1. close/archive completed v0.3 trackers;
2. recheck and finish repo-hygiene PR #58 without changing product behavior;
3. use Issue #60 as the v0.4 umbrella;
4. keep #55 / #56 / #57 / #59 as focused v0.4 backlog items;
5. begin v0.4 implementation only after repository cleanup is settled.

## Frozen workflow under test

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

Text Cleanup remains an optional sibling module and is verified separately as part of the release checkpoint.

## Release rule

The real v0.3 human QA requirement has now been explicitly satisfied on **2026-09-25**.

Do not confuse this accepted checkpoint with the previously withdrawn premature v0.3.0 release. The old Release/tag/artifact remains invalid historical evidence; final release closeout must use the current accepted recovery line and current automated evidence.

Future release checkpoints must continue to require explicit human acceptance rather than inferring PASS from CI or ambiguous wording.

## Authoritative trackers

Completed v0.3:
- PR #54 — merged recovery implementation
- Issue #17 — Stage 4 consolidated human QA (PASS)
- Issue #2 — v0.3 umbrella
- Issue #9 — v0.3 QA
- Issue #13 — Composite Split
- Issue #21 — General Auto Crop
- Issue #23 — Source Organizer
- Issue #26 — Text Cleanup
- Issue #52 — permanent Qt i18n foundation

Current / next:
- PR #58 — repository documentation hygiene
- Issue #55 — optional NVIDIA CUDA acceleration research
- Issue #56 — Text Cleanup review sorting controls
- Issue #57 — README screenshots
- Issue #59 — UX backlog from accepted v0.3 QA
- Issue #60 — v0.4 umbrella
