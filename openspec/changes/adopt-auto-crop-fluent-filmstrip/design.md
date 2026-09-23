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


## Production-render adjustment

The first real production render exposed two presentation-specific issues without changing accepted intent:

1. QFluentWidgets `ListWidget` is optimized for row-list presentation. Its delegate compressed the requested `IconMode` cells, producing thin thumbnail strips and leaving the Filmstrip visually under-filled.
   - Resolution: use Qt's mature native `QListWidget` in `IconMode` **inside the Fluent Filmstrip card**.
   - Fluent remains the accepted visual/component language for the dialog, cards, labels and actions.
   - Only minimal dialog-scoped hover/selection styling is applied to the native icon view.
   - This is not a new custom widget and does not change layout/product behavior.

2. QFluent card backgrounds animate for roughly 120 ms on theme changes.
   - Production behavior is valid, but screenshot verification must wait until the animation settles before judging Dark coherence.
   - CI also loads a temporary CJK font only for screenshots because GitHub Windows runners do not include the user's normal Chinese UI fonts.

These adjustments preserve the user-approved Fluent + Filmstrip + thumbnail + scoped Light/Dark direction.


## Candidate-area sizing and navigation adjustment

User review of the production layout added one bounded interaction requirement before merge:

- the primary work area and bottom candidate area are separated by a vertical `QSplitter`, so the candidate area can be dragged up/down;
- thumbnails wrap naturally into additional rows as the candidate area becomes taller;
- when rows overflow the available height, Qt's native vertical scrollbar appears as needed;
- a normal mouse wheel scrolls the candidate area vertically;
- horizontal scrolling is disabled;
- dragging the candidate area upward should reveal more thumbnail rows and reduce the remaining vertical scroll range;
- no additional splitter is added inside the right inspector.

This remains presentation-only and does not change Auto Crop backend or review semantics.


## Final visual/localization correction

User review added two final pre-merge presentation corrections:

- user-facing `Auto Crop` wording is localized consistently to **“自动裁剪”** across the review window, main action button, progress text, warnings and export-blocking messages; internal module/class/feature identifiers remain unchanged;
- the candidate area's vertical scrollbar receives a dialog-scoped Fluent-compatible Light/Dark style so Dark mode does not leave a light scrollbar.

These changes are presentation-only and do not alter Auto Crop backend semantics.
