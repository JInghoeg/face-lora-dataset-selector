# Project State

Canonical current-state entry point.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Default branch: `main`
- Current public release: **v0.3.0**
- Release tag / code: `8bf51d5b552587dd4d7a5d8ce87a48f89c3136de`
- Release date: 2026-09-24
- v0.3 implementation, Stage 4 human QA and release closeout: **COMPLETE**
- All v0.3 product/research/QA trackers are closed.

Release:
`https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0`

## v0.3.0 verification

Final release workflow:
- run: `35919809384`
- result: **PASS**
- source runtime self-test: PASS
- Fluent UI Essentials-only installation: PASS
- PyInstaller Portable build: PASS
- packaged EXE self-test: PASS
- ZIP + SHA-256 generation: PASS
- GitHub Release upload: PASS

Release Portable:
- `Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip`
- size: `160,312,419 bytes`
- SHA-256: `fbd73f1a477a1b64f19f0b4f25c31c805dc4f3e710a7f9f8ab3bea3d6fa4c03a`

Stage 4 consolidated human QA:
- result: **PASS**
- Issue #17: completed / closed
- no product-code fix was required after the accepted human checkpoint.

Architecture gate on the integrated v0.3 mainline: **PASS**.

## Released workflow

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

Architecture seam:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Released feature packages:
- `features/ranking`
- `features/duplicate`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

v0.3.0 also includes:
- Dataset / View filtering, sorting, paging and saved views;
- stable sample IDs;
- Duplicate Review;
- AI Review Bundle + suggestion-only patch import;
- Composite Split + archive lifecycle + per-output keep/reject;
- General Auto Crop + manual ROI + Final Export materialization;
- transactional Source Organizer;
- Text Cleanup application boundary;
- Fluent Filmstrip Auto Crop review;
- permanent live `zh_CN` / `en_US` Qt i18n;
- architecture-boundary CI and risk-based batched human QA.

## Current status

There is no active v0.3 implementation or release blocker.

Do not continue adding features under the completed v0.3 release scope. New product work should start from current `main` with a new issue / branch / explicit release target.

Historical staged/research branches were intentionally retained for reference; their old Draft PRs were closed rather than replayed into main.

## Future work

Potential future work is not part of v0.3.0:
- real cross-version benchmark snapshots;
- dataset-level marginal-value / redundancy research;
- model upgrades justified by confirmed failure modes;
- further bounded UI modernization;
- release-signing / distribution polish.

These are candidates, not committed release requirements.

## Authoritative references

- `CHANGELOG.md`
- `RELEASE_NOTES_v0.3.0.md`
- `docs/ROADMAP_v0.3.md`
- Issue #17 — completed Stage 4 human QA
- tag `v0.3.0`
