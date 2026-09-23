# Project State

Canonical current-state entry point for the active v0.3 product line.

## Repository state

- Repository: `JInghoeg/face-lora-dataset-selector`
- Product branch: `feature/v0.3-workflow-recovery`
- Latest verified product/code baseline: `46bc803b8a806d9c1cf61ab9a6534241ac0cff8e` — merged PR #51, Fluent Filmstrip Auto Crop + permanent live Qt i18n foundation.
- Active release tracker: Issue #17 — **v0.3 Stage 4 — unified Portable + consolidated human QA**.
- PR #15 remains the product-stack integration PR.
- GitHub product branch / PR / Issue #17 are authoritative; do not infer current state from an older local clone.

## Current objective

**Stage 4 is active. Stage 3 is complete.**

Accepted execution order:

1. Auto Crop manual ROI — complete.
2. Limited architecture closeout — complete.
3. UX/UI modernization — complete.
4. **Unified Portable + consolidated human QA — active.**

No new UX/UI or architecture expansion is planned before the QA checkpoint unless a concrete release blocker requires it.

## Verified complete

Architecture seam:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Feature packages:
- `features/ranking`
- `features/duplicate`
- `features/composite`
- `features/auto_crop`
- `features/source_organizer`
- `features/text_cleanup`

Stage 3 completed bounded slices:
- PR #46 — Text Cleanup presentation extraction / OpenSpec pilot.
- PR #48 — main Dataset View Qt Model/View seam with stable-ID action mapping.
- PR #51 — Auto Crop Fluent Filmstrip production UI, scoped Light/Dark, real thumbnails, vertically resizable candidate area, one-row default viewport, permanent live Qt i18n foundation.

PR #51 closeout:
- user visual review: PASS;
- default candidate viewport: exactly one full thumbnail row; second row hidden until splitter expansion;
- Python 3.9 / 3.12 production UI smoke: PASS;
- RectROI edit/reset/decision behavior: PASS;
- Fluent-absent fallback startup: PASS;
- PySide6-Essentials retained; no PySide6-Addons;
- OpenSpec archived under `openspec/changes/archive/2026-09-24-adopt-auto-crop-fluent-filmstrip/`;
- i18n OpenSpec archived under `openspec/changes/archive/2026-09-24-add-i18n-foundation/`.

## Stage 4 unified QA candidate

Pinned code head:
`46bc803b8a806d9c1cf61ab9a6534241ac0cff8e`

Workflow run:
`35916370063`

Portable artifact:
- name: `auto-crop-fluent-portable-qa`
- artifact ID: `10774289944`
- artifact digest: `sha256:71835391390bcbe41199776565fbfecc9fc8d480af1f3dc4b60a9ca873c1c937`
- artifact ZIP size: `159,693,034 bytes`
- unpacked Portable size: `357,015,371 bytes`
- expires: `2026-09-30T20:34:24Z`

Candidate automated evidence:
- Python 3.9 production UI smoke: PASS;
- Python 3.12 production UI smoke: PASS;
- Fluent-absent fallback startup: PASS;
- packaged Portable EXE self-test: PASS.

This candidate is pinned for human QA even if later documentation-only commits advance the product branch head.

## Human QA

Issue #17 is authoritative and now contains the single consolidated checklist.

The checkpoint covers:
- Portable/global shell and live zh_CN/en_US switching;
- recommendation baseline/manual override behavior after F5;
- Duplicate Review all-groups interaction/persistence;
- Composite continuous review, per-output keep/reject, archive exclusion and generated-files-only incremental analysis;
- Auto Crop one-row Filmstrip, splitter/scrolling, ROI edit/reset/decision persistence, Light/Dark and export behavior;
- Source Organizer on a disposable copied dataset only;
- Text Cleanup interaction and non-destructive output;
- AI Review Bundle / review_patch suggestion semantics;
- Final Training Export semantics.

Source Organizer must **not** be human-tested first on the original Valby source dataset.

## Blockers / uncertainties

No current automated/code blocker is known.

Remaining release risk is human interaction validation. AUTO PASS is not a substitute for the Stage 4 real workflow checkpoint.

## Next action

1. Run the pinned unified Portable from Issue #17.
2. Execute the consolidated checklist in workflow order.
3. Record failures in Issue #17; do not stop for cosmetic/non-fatal findings already covered by automation.
4. Stop immediately for startup failure, data loss, unexpected source mutation, state loss, or release-blocking workflow failure.
5. Apply blocker/obvious-release fixes only.
6. Run affected automated regressions + one final Portable smoke.
7. Run final real Valby end-to-end workflow QA.
8. Close release trackers (#21 Auto Crop, #23 Source Organizer, #26 Text Cleanup, etc.) when their gates pass.

## Frozen product workflow

```
Initial analysis / recommendation
-> Duplicate Review
-> Composite Split
-> General Auto Crop
-> Optional Source Organizer
-> Final Export
```

## Do not repeat

- Do not restart broad Stage 3 UI modernization during Stage 4.
- Do not stop for separate low-risk human QA after every automated fix; use Issue #17.
- Do not test Source Organizer first on original Valby data.
- Do not revive failed Auto Crop Stage 1 saliency/pose safe-trim.
- Do not use raw DeepGHS person bbox as final crop boundary.
- Do not use every non-zero ISNetIS alpha pixel as foreground.
- Do not restore resolution-scaled padding; fixed 32 px is validated.
- Do not split Text Cleanup detection/repair into separate product modules in this release.
- Do not rewrite mature PP-OCR / repair algorithms for architecture aesthetics.
- Do not add microservices/local HTTP ceremony.
- Do not redownload verified reusable models/dependencies.
- Do not default research/temp output to C:.

## Authoritative references

- Issue #17 — Stage 4 unified Portable + consolidated human QA.
- `docs/ROADMAP_v0.3.md` — release gates.
- PR #15 — product-stack integration.
- PR #51 / Issue #49 — completed Auto Crop Fluent Filmstrip + i18n production adoption.
- Issue #21 — Auto Crop release tracking.
- Issue #23 — Source Organizer release tracking.
- Issue #26 — Text Cleanup release tracking.
- Engineering-Playbook `PROJECT_CONTINUITY.md` — continuity protocol.
