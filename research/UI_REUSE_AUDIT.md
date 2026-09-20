# UI Reuse Audit — Auto Crop

Goal: avoid custom image/crop interaction code.

Current selector stack:
- Python 3.9 supported
- PySide6-Essentials >=6.6,<6.9
- Windows Portable
- GPL-3.0 project

## Preferred donor for the production crop editor: PyQtGraph 0.13.7

Why:
- MIT license;
- Python >=3.9;
- mature Qt GraphicsView-based image/ROI system;
- supports PySide6;
- `RectROI` already provides movable/resizable rectangle handles;
- ViewBox/ImageItem provide mature image display, pan, zoom and coordinate transforms;
- wheel/drag/ROI geometry do not need to be reimplemented;
- package is small (~1 MB wheel), far below full annotation suites.

Important compatibility note:
- pin to `pyqtgraph==0.13.7` for the current Python 3.9 stack;
- do not float to current PyQtGraph releases, whose Python/Qt floors have moved upward;
- our project pins PySide6 <6.9, avoiding known PyQtGraph 0.13.7 regressions reported with PySide6 6.9.1/6.10.

Planned use, only after crop backend validation:
- existing image -> PyQtGraph ImageItem;
- algorithm proposal -> one RectROI;
- user drag/resize -> RectROI native interaction;
- ViewBox -> pan/zoom/fit;
- crop metadata -> read ROI bounds in image coordinates;
- our code handles only workflow, persistence, Accept/Keep/Reset and export.

We will not write custom rectangle handles, hit-testing, drag geometry, pan/zoom math, or image-coordinate transforms.

## Labelme v7

Strengths:
- GPL-3.0, same license family as this project;
- PySide6/Qt6;
- mature rectangle/polygon/mask annotation, selection, edit, navigation, undo;
- very strong full annotation application.

Why not first:
- current v7 requires Python >=3.12 and PySide6 >=6.8;
- labelme explicitly exposes no stable internal Python API;
- upstream recommends vendoring internals if an application needs them;
- adopting it now would force a runtime migration or a backport before we have even validated Auto Crop.

Keep as a donor if PyQtGraph proves insufficient.

## CuteCanvas

Strengths:
- PySide6 graphics editor designed for embedding;
- crop, selection, pan/zoom, undo/redo, host policy;
- GPL-3.0-or-later.

Why not first:
- Python >=3.10;
- PySide6 >=6.7.3;
- much broader editor architecture than our one-rectangle crop workflow.

## X-AnyLabeling

Strengths:
- mature annotation application;
- extensive boxes/masks/AI tools;
- GPL-3.0.

Why not first:
- production dependency is PyQt6, not PySide6;
- Python >=3.11;
- large application surface for a small embedded crop editor.

## Existing Dataset Scout crop editor

This remains a reuse candidate because it has already been human-tested in the user's workflow.

Its source is not present in the currently connected GitHub repositories, so no claim is made about its technical portability yet. If/when its source becomes available, audit it before production UI implementation.

## Decision

For the current selector runtime, PyQtGraph 0.13.7 is the first UI implementation candidate.

No UI code is to be implemented until the mature crop backend passes the 20-image challenge gate.
