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
- Active recovery branch: `fix/v0.3-manual-qa-blockers`
- Active PR: Draft #54 — `fix: address v0.3 manual QA blockers`
- Last verified code commit: `8ce96a9bb085012649a8020d4b290e25e5324874`
- **Public v0.3.0 release: WITHDRAWN**
- v0.3.0 human QA: **NOT COMPLETE / NOT PASSED**
- Current phase: **v0.3 release-blocker recovery + new human-QA candidate**.

The previously published `v0.3.0` Release and tag are intentionally removed. Do not treat the old release artifact, old SHA-256, or the previous “QA PASS” documentation as valid release evidence.

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

The GPU question is **not implemented yet**. Current inference remains CPU-oriented. GPU acceleration must be evaluated as a dependency/packaging/runtime decision before introducing `onnxruntime-gpu` or another GPU runtime.

The optional self-selected/manual crop expansion requested during QA remains explicitly deferred; do not pull it into the current blocker batch.

## Automated validation

For `8ce96a9`:

- 10 / 10 GitHub Actions workflows: **PASS**.
- Windows Portable artifact: `10795898471`.
- Portable artifact digest: `sha256:2a50cfd5232671bf65c2f0f262ca47c0265669f991c29c0e055dd566cd7fcbc7`.
- Automated evidence is useful diagnostic evidence only and is **not** human release acceptance.

## Human-unverified items on the latest candidate

The following latest fixes are automated but still require the next consolidated real QA checkpoint:

- export progress and completion behavior;
- cancellation behavior during long analyses;
- UI responsiveness during analysis on the real workstation/data;
- Text Cleanup folder selection -> automatic scan -> review -> batch repair flow, including cancelling a batch and verifying no partial batch output remains;
- the rest of the reopened Stage 4 end-to-end checklist.

## Current objective

1. keep Draft #54 as the single recovery line;
2. preserve the latest passing Portable candidate and the exact human-unverified list;
3. perform the consolidated human QA checkpoint on the new candidate before release;
4. fix only confirmed remaining blockers/obvious workflow defects from that pass;
5. evaluate GPU acceleration separately before changing runtime dependencies;
6. publish only after the user explicitly reports QA PASS.

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

**Do not create or restore v0.3.0 until real human QA is explicitly completed and accepted.**

No future assistant response may infer QA PASS from “完成了”, “好了”, CI green, Portable self-test, or any other ambiguous wording. The user must explicitly report that the manual QA passed.

## Authoritative trackers

- PR #54 — current recovery implementation and QA candidate
- Issue #17 — Stage 4 consolidated human QA (REOPENED)
- Issue #2 — v0.3 umbrella (REOPENED)
- Issue #9 — v0.3 QA (REOPENED)
- Issue #13 — Composite Split (REOPENED)
- Issue #21 — General Auto Crop (REOPENED)
- Issue #23 — Source Organizer (REOPENED)
- Issue #26 — Text Cleanup (REOPENED)
- Issue #55 — optional NVIDIA CUDA acceleration research
