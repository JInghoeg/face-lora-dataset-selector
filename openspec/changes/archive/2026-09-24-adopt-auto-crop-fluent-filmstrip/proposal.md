# Proposal: Adopt Auto Crop Fluent Filmstrip UI

## Current phase

v0.3 Stage 3 UX/UI modernization remains active. This is the final bounded release-facing UI slice before the unified Portable + consolidated QA gate.

Tracking: Issue #49.

## Accepted user direction

The visual-selection spike is complete. The user explicitly selected:
- PySide6-Fluent-Widgets as the visual/component language;
- Filmstrip as the layout;
- real thumbnails in the candidate strip with reduced dead space;
- Auto Crop-scoped Light/Dark;
- theme toggle at the top-right of the Auto Crop window.

This proposal implements that accepted direction; it does not reopen visual-library or layout selection.

## Frozen behavior

The change must preserve:
- current Auto Crop backend / ISNetIS behavior;
- pyqtgraph RectROI drag/resize/bounds;
- automatic proposal/current box semantics;
- Reset / Accept / Keep Original / Restore Pending;
- feature_state persistence;
- Final Export semantics;
- source immutability.

## Runtime constraint

Keep PySide6-Essentials. Do not silently reintroduce PySide6-Addons through QFluentWidgets package metadata.

## Scope

- production Fluent Filmstrip Auto Crop review surface;
- real thumbnail Filmstrip using the existing shared thumbnail worker/cache;
- top-right Light/Dark toggle scoped to this modal review dialog;
- graceful fallback if Fluent is unavailable in a source environment;
- packaging/install path for the selected Fluent dependencies;
- automated Light/Dark / ROI / thumbnail / Portable validation.

## Non-goals

- no whole-app theme;
- no other module redesign;
- no Auto Crop algorithm rewrite;
- no generic architecture work.
