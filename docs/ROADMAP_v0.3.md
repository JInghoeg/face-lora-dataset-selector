# v0.3 Roadmap

Status date: 2026-09-24

## Status

**Implementation complete. Consolidated human QA PASS. Release closeout active.**

The integrated v0.3 product stack is on `main` via `521ac77f22996e2f160964da7c9b96f15ad29eaa`.

## Completed

- correctness redesign and recommendation/manual-override separation;
- Dataset/View filters, sorting, paging and saved views;
- stable sample IDs;
- Duplicate Review;
- AI Review Bundle + suggestion-only patch import;
- Composite Split + archive lifecycle + per-output keep/reject;
- generated-files-only incremental analysis;
- General Auto Crop backend + manual ROI + Final Export integration;
- transactional Source Organizer;
- Text Cleanup frontend/backend boundary;
- main Dataset View Model/View seam;
- Fluent Filmstrip Auto Crop UI;
- permanent live zh_CN/en_US Qt i18n;
- architecture-boundary CI;
- Stage 4 unified Portable + consolidated human QA.

## Final release gates

- [x] Stage 4 consolidated human QA.
- [x] Source Organizer human test on a disposable/copy dataset.
- [x] v0.3 stack merged to `main`.
- [x] v0.3.0 release notes / changelog / README prepared.
- [x] release workflow generalized beyond v0.2.0.
- [ ] final `main` Architecture Boundaries workflow PASS.
- [ ] final v0.3.0 Windows Portable build + packaged EXE self-test PASS.
- [ ] GitHub Release `v0.3.0` created with Portable ZIP + SHA-256.
- [ ] close completed production trackers and superseded Draft PRs.
- [ ] close overarching v0.3 tracker after release is visible.

No further manual QA is required unless the final release-engineering commit changes product code or the final packaged smoke test fails.
