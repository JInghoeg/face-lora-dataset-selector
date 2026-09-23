# v0.3 Roadmap

Status date: 2026-09-24

Canonical current-state summary:
`docs/PROJECT_STATE.md`

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Ranking/recommendation backend boundary.
- Duplicate Review feature module + frontend/backend boundary.
- AI Review Bundle / patch workflow.
- Composite Split production integration + archive lifecycle + per-output keep/reject.
- generated-files-only incremental analysis after Composite Review.
- automatic recommendation baseline separated from final manual override.
- Source Organizer backend/workflow with transaction + recovery safeguards.
- Text Cleanup frontend/backend separation while preserving detection + repair as one product module.
- General Auto Crop backend, manual ROI, persistence and Final Export integration.
- main Dataset View Qt Model/View seam with stable IDs.
- Auto Crop Fluent Filmstrip production UI + scoped Light/Dark.
- permanent live Qt i18n foundation with zh_CN source locale + en_US catalog.
- risk-based batched human-QA policy.
- repository-resident PROJECT_STATE + Project Memory Gate continuity protocol.

## Current

### Stage 4 — unified Portable + consolidated human QA

Stages 1–3 are complete. Issue #17 is authoritative for Stage 4.

Pinned QA code head:
`46bc803b8a806d9c1cf61ab9a6534241ac0cff8e`

Pinned unified Portable:
- workflow run: `35916370063`
- artifact: `auto-crop-fluent-portable-qa`
- artifact ID: `10774289944`
- digest: `sha256:71835391390bcbe41199776565fbfecc9fc8d480af1f3dc4b60a9ca873c1c937`
- unpacked size: `357,015,371 bytes`
- packaged EXE self-test: PASS.

Human QA is now intentionally concentrated into one checkpoint:
1. Portable/global shell + language switching.
2. recommendation/F5 baseline invariants.
3. Duplicate Review.
4. Composite Split.
5. General Auto Crop.
6. Source Organizer on a disposable copy only.
7. Text Cleanup.
8. AI Review Bundle + Final Export.

## Architecture direction

Frozen seam:

```
Qt presentation
-> SelectorApplication
-> feature backends
```

Do not expand Stage 4 into another broad architecture or whole-app UI pass. Only confirmed release blockers/obvious issues justify product code changes before release.

## v0.3 remaining gates

Before v0.3 is release-complete:

1. run the consolidated Issue #17 human-QA checkpoint on the pinned unified Portable;
2. human-test Source Organizer on a disposable copied dataset;
3. apply blocker/obvious-release fixes only;
4. rerun affected automated tests + one final Portable smoke;
5. run final local Valby end-to-end workflow QA;
6. close remaining production trackers whose release gates pass;
7. finalize release notes / changelog / versioning and ship v0.3.

Non-fatal automated fixes do not force separate manual QA; record them and verify at the next explicit checkpoint.
