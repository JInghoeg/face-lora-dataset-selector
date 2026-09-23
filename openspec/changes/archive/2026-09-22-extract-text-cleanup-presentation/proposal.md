# Proposal: Extract Text Cleanup Presentation from app.py

## Why

The Text Cleanup backend boundary is already complete, but its Qt workers and `SubtitleTab` presentation still live inside the large legacy `app.py`. The accepted v0.3 plan is now in the UX/UI modernization phase, so this is a bounded brownfield slice that proves presentation can move independently without reopening backend or algorithm work.

This change is also the first OpenSpec pilot on the repository. It must prove that accepted intent and implementation scope survive context changes better than the previous PROJECT_STATE/HANDOFF-only approach.

## What Changes

- Move Text Cleanup-specific Qt presentation and thin Qt workers from `app.py` into `ui/qt/text_cleanup.py`.
- Extract `ImagePreview` and `ThumbnailWorker` as reusable `ui/qt` presentation components because code inspection confirmed they are shared by Text Cleanup and other existing UI surfaces.
- Make the Text Cleanup presentation receive `SelectorApplication` and presentation/cache paths explicitly instead of depending on the `app.py` global `BACKEND`.
- Keep current Text Cleanup interaction, persistence, scan, preview-repair, pagination, thumbnail, and batch-repair behavior unchanged.
- Keep PP-OCR, suggestion heuristics, MI-GAN, TELEA, Navier-Stokes, state persistence semantics, and batch filesystem behavior unchanged behind `SelectorApplication` / `features/text_cleanup`.
- Update `app.py` to compose/import the moved presentation and shared UI components rather than own them.
- Add/retain automated smoke coverage proving the moved Qt presentation can import/instantiate without violating backend boundaries.

### Accepted surrounding execution order — unchanged by this change

1. **补 Auto Crop 手动 ROI** — complete.
2. **做一次很有限的架构收尾** — complete, including Duplicate and Text Cleanup boundaries.
3. **真正的 UX/UI 升级** — active; this change is one bounded slice of this stage.
4. **最后重新出统一 Portable，跑一次集中 QA** — not the current main phase.

This change must not silently turn step 4 into the next action before the UX/UI stage is actually complete.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is intentionally a behavior-preserving presentation refactor, so the change declares `skip_specs: true` rather than inventing a fake behavioral requirement.
