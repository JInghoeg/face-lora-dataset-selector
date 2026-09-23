# v0.3 Roadmap

Status date: 2026-09-24

## Final status

**v0.3.0 RELEASED — COMPLETE**

Release:
`https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.3.0`

Tag:
`8bf51d5b552587dd4d7a5d8ce87a48f89c3136de`

## Completed scope

- [x] correctness redesign and recommendation/manual-override separation
- [x] Dataset/View filters, sorting, paging and saved views
- [x] stable sample IDs
- [x] Duplicate Review
- [x] AI Review Bundle + suggestion-only patch import
- [x] Composite Split + archive lifecycle + per-output keep/reject
- [x] generated-files-only incremental Composite analysis
- [x] General Auto Crop backend + manual ROI + Final Export integration
- [x] transactional Source Organizer
- [x] Text Cleanup frontend/backend boundary
- [x] main Dataset View Model/View seam
- [x] Fluent Filmstrip Auto Crop UI
- [x] permanent live zh_CN/en_US Qt i18n
- [x] architecture-boundary CI
- [x] Stage 4 unified Portable + consolidated human QA

## Release gates

- [x] Stage 4 consolidated human QA
- [x] Source Organizer human test on a disposable/copied dataset
- [x] complete v0.3 stack merged to `main`
- [x] v0.3.0 release notes / changelog / README
- [x] release workflow generalized beyond v0.2.0
- [x] Fluent UI runtime explicitly installed in the official Portable workflow without PySide6-Addons
- [x] Architecture Boundaries PASS on integrated mainline
- [x] final Windows Portable build PASS
- [x] final packaged EXE self-test PASS
- [x] ZIP + SHA-256 produced
- [x] GitHub Release `v0.3.0` published
- [x] completed production / research / QA trackers closed
- [x] historical staged/research Draft PRs closed without replaying old state

## Release artifact

- file: `Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip`
- size: `160,312,419 bytes`
- SHA-256: `fbd73f1a477a1b64f19f0b4f25c31c805dc4f3e710a7f9f8ab3bea3d6fa4c03a`

## After v0.3

This roadmap is frozen as a release record.

Future benchmark/model/UI work should be tracked under a new roadmap or release target instead of reopening v0.3 tasks.
