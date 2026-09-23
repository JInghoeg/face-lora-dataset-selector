# Design: Auto Crop Fluent Filmstrip Production Adoption

## Presentation structure

Use the user-selected Filmstrip pattern:

1. compact header:
   - Auto Crop title;
   - current/total progress;
   - top-right theme toggle.
2. primary work area:
   - large existing pyqtgraph RectROI crop editor;
   - compact right-side crop preview + information inspector.
3. bottom Filmstrip:
   - real cached thumbnails;
   - horizontal browsing;
   - current selection highlight;
   - lightweight pending / accepted / keep-original state text;
   - no large empty list area.
4. decision row:
   - Accept current crop;
   - Reset to automatic proposal;
   - Keep original;
   - Restore pending;
   - Close.

## Reuse

- Keep `AutoCropROIWidget` / pyqtgraph RectROI.
- Reuse `ui.qt.thumbnail.ThumbnailWorker` and the existing thumbnail cache directory.
- Use QFluentWidgets controls/cards rather than hand-built substitute components.

## Stable identity

Filmstrip items store `sample_id`, not transient row indexes. Selection is resolved back to the current record list by stable ID.

Async thumbnail callbacks use a generation token. Stale callbacks are ignored.

## Theme isolation

QFluentWidgets uses a process-level theme setting, but Auto Crop is modal and is the only production Fluent surface in this release slice.

- capture the pre-dialog Fluent theme;
- apply the Auto Crop preferred Light/Dark while the dialog is active;
- use a dialog-scoped stylesheet only for ordinary Qt surfaces not covered by Fluent;
- set the pyqtgraph canvas background explicitly;
- restore the previous global Fluent theme when the dialog finishes;
- keep the user's preferred Auto Crop theme for subsequent Auto Crop dialogs within the same app session.

Default is Light.

## Optional dependency behavior

The module itself must remain importable without QFluentWidgets.

If Fluent is missing:
- the app starts normally;
- Auto Crop review falls back to its legacy Qt presentation;
- backend behavior remains available.

The normal installer and Portable build include the selected Fluent dependencies.

## Dependency installation

Do not add the PySide6 meta-package.

Install:
- darkdetect 0.8.0;
- pywin32 312;
- PySideSix-Frameless-Window 0.8.2 with --no-deps;
- PySide6-Fluent-Widgets 1.11.3 with --no-deps.

The existing PySide6-Essentials requirement remains authoritative.

## Verification

- Python 3.9 and 3.12 production dialog smoke;
- real Filmstrip thumbnails;
- stable-ID selection;
- RectROI edit/reset/decision behavior;
- Light/Dark toggle and scoped ordinary-Qt/pyqtgraph surfaces;
- app startup without Fluent installed;
- Portable build and packaged self-test;
- record Portable size delta against the previous validated candidate.
