# Project State

Canonical current-state entry point.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- **Public v0.3.0 release: WITHDRAWN**
- v0.3.0 human QA: **NOT COMPLETE / NOT PASSED**
- User reported multiple bugs after the release candidate was published.
- Issue #17 and the v0.3 product trackers have been reopened.
- Current phase: **v0.3 bug triage + real human QA recovery**.

The previously published `v0.3.0` Release and tag are intentionally removed. Do not treat the old release artifact, old SHA-256, or the previous “QA PASS” documentation as valid release evidence.

## What remains valid

Automated evidence remains useful but is not release acceptance:
- architecture-boundary CI passed on the integrated mainline;
- Python 3.9 / 3.12 automated regression suites passed for covered paths;
- the official Portable can build and pass packaged EXE self-test;
- Fluent UI is packaged with PySide6-Essentials only.

These automated results did **not** replace the missing real manual workflow QA.

## Current objective

1. collect and reproduce the user-reported bugs;
2. record each issue in the reopened Stage 4 / feature trackers;
3. fix blockers and obvious workflow defects;
4. rebuild a new QA Portable candidate;
5. run the full manual workflow QA before any new public v0.3 release;
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

## Release rule

**Do not create or restore v0.3.0 until real human QA is explicitly completed and accepted.**

No future assistant response may infer QA PASS from “完成了”, “好了”, CI green, Portable self-test, or any other ambiguous wording. The user must explicitly report that the manual QA passed.

## Authoritative trackers

- Issue #17 — Stage 4 consolidated human QA (REOPENED)
- Issue #2 — v0.3 umbrella (REOPENED)
- Issue #9 — v0.3 QA (REOPENED)
- Issue #13 — Composite Split (REOPENED)
- Issue #21 — General Auto Crop (REOPENED)
- Issue #23 — Source Organizer (REOPENED)
- Issue #26 — Text Cleanup (REOPENED)
