# v0.4 integrated Draft QA checkpoint (2026-11-21)

This branch is **not a release** and does not imply a human PASS. It exists to test the combined features together without merging the original feature Draft PRs into `main`.

## Included implementation sources

- Base: `feat/v04-stable-incremental-updater` at `120ea3d` (#110), providing Settings / stable release metadata checks / SHA-verified delta-only updates. No full-Portable fallback; model/userdata are not downloaded as part of an update.
- Applied `feat/v04-text-cleanup-review-ux` at `248b523` (#111): Text Cleanup sort/navigation, manual ROI affordances, source-preserving review workflow and dynamic selected-state sorting.
- Applied `qa/v04-unified-human-acceptance` at `f670699` (#109): integrated Duplicate Review UI and regression, Windows QA launch and DirectML delta scripts. Duplicate Review's original production proposal is #90; its independent HUMAN QA is still pending.
- Combined **rather than replaced** the English i18n catalog so Settings, Text Cleanup and Duplicate Review translation strings all remain present.
- This is a **file-level integration** of the named completed modules. It is not a Git history merge of their separate feature branches, nor proof that they have been approved by a user.

## Verification gates

1. GitHub Windows CI: project state/architecture, i18n, Text Cleanup, Duplicate Review, Settings, stable updates, full Portable build, unified QA workflows. Fix new branch-only integration failures rather than altering unrelated feature branches.
2. On the actual Windows workstation, reuse previously downloaded Portable/model resources, confirm real Settings/Text Cleanup/Duplicate Review actions, keep v0.3.1 and datasets untouched.
3. Investigate #112 frequent QA Portable crashes using the **existing local logs and exact build SHA**, not a guessed root cause. A reproducible native crash blocks v0.4 release.
4. A matching release gate and explicit HUMAN PASS remain necessary before any release or non-draft merge.

## Boundaries

- UI presentation -> SelectorApplication -> features/infrastructure.
- No original source-image mutation, no repeated full Portable/model downloads.
- Existing-box resize/move, broader whole-product UI and analysis quality are separate subsequent scopes.
- Original #110/#111/#109/#90 remain Draft; no automatic merge of abandoned #74/#88 or UI-redesign drafts.
