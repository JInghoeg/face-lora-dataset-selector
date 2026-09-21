# v0.3 Roadmap

Status date: 2026-09-21

## Completed / substantially implemented

- v0.3 correctness redesign.
- Dataset/View filters and independent sorting.
- Duplicate Review workflow.
- AI Review Bundle / patch workflow.
- Composite Split detector research and production integration.
- Composite source archive semantics.
- Composite per-output keep/reject behavior.
- generated-files-only incremental analysis after Composite Review.
- automatic recommendation baseline separated from final manual override.
- batched non-fatal human-QA policy.

Some recent interaction fixes are AUTO PASS but HUMAN UNVERIFIED; see Issue #17.

## Current

### Text Cleanup frontend/backend separation

Detection + repair remain one mature product module:

```
features/text_cleanup
```

Scope:
- preserve PP-OCR / suggestion heuristics / manual region workflow;
- preserve MI-GAN / TELEA / Navier-Stokes;
- move model, cache, repair and batch filesystem work behind `SelectorApplication`;
- keep Qt presentation/interaction behavior stable.

Tracking Issue: #26
Draft PR: #27

### Known remaining product gap

General Auto Crop automatic proposal/review is implemented and AUTO PASS, but the planned manual ROI edit/reset workflow is still missing.

Required before declaring feature complete:
- draggable/resizable manual crop ROI;
- persist manually edited crop box;
- reset to automatic proposal;
- final export must use the accepted current box.

### Architecture state

The main product path now has real backend boundaries:
- Ranking
- Composite
- Auto Crop
- Source Organizer
- Text Cleanup

Still deferred:
- Duplicate as its own independent feature package;
- dedicated `ui/qt` package / Qt Model-View migration.

Do not rewrite stable algorithms merely to satisfy architecture aesthetics.

### Human QA checkpoint

Issue #17 remains the authoritative batched HUMAN UNVERIFIED queue.

The consolidated Portable AUTO PASS is not equivalent to release completion.

## v0.3 release gate

v0.3 is not final until:
- Text Cleanup frontend/backend separation passes automated + Portable regression;
- General Auto Crop manual ROI edit/reset is implemented;
- accumulated human-QA checkpoint passes;
- Source Organizer is human-tested on a disposable copied dataset;
- final local Valby end-to-end workflow QA passes.
