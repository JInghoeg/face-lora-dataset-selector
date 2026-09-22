# Design: Auto Crop Review Reusable UI Spike

## Existing surface

The current Auto Crop review dialog already has the required behavior:
- candidate list;
- original image with automatic proposal and editable pyqtgraph RectROI;
- live crop preview;
- Accept current crop;
- Reset to automatic proposal;
- Keep original;
- Restore pending;
- persistence through the existing backend;
- accepted/keep decisions advance review.

The spike must preserve all of this.

## Decision 1: interaction stays on pyqtgraph

Do not replace RectROI in this spike.

pyqtgraph is already validated in this repository for:
- direct drag;
- edge/corner resize;
- bounded ROI;
- reset;
- persistence/export behavior.

The visual candidate wraps the existing interaction surface; it does not reimplement crop hit-testing.

## Decision 2: test a real theme on the real dialog before adopting it

The first candidate is qt-material 2.17.

The spike installs it only in the dedicated CI job initially. It is not added to production requirements until:
1. the real Auto Crop dialog renders acceptably;
2. RectROI behavior remains intact on Python 3.9 and 3.12;
3. the user-visible result is materially better than the current dialog;
4. a later adoption commit measures Portable cost.

Render at least:
- current unthemed baseline;
- qt-material light_blue;
- qt-material dark_blue.

Screenshots are artifacts, not a hand-authored mockup.

## Decision 3: do not compensate for a weak reusable candidate with custom design

If qt-material is visually insufficient, record that result and run a second bounded spike with PySide6-Fluent-Widgets.

Do not respond to a weak first candidate by inventing a custom toolbar/card/status-chip system.

## Decision 4: no behavior changes during visual candidate comparison

For candidate screenshots and smoke:
- use synthetic local image data;
- create a real Auto Crop proposal in feature_state;
- instantiate the actual AutoCropReviewDialog;
- verify a current ROI exists;
- programmatically move/resize the ROI and verify normalized coordinates;
- verify Reset/decision methods remain callable without backend contract changes.

## Acceptance for the spike

The spike is successful only if it produces evidence sufficient to decide:
- adopt candidate A;
- reject candidate A and test candidate B;
- or stop UI work because neither reusable option is worth release risk.

No candidate is adopted solely because automated tests pass; rendered visual quality is part of acceptance.
