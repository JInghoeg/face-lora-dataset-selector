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


## Spike outcome

Candidate A — qt-material 2.17:
- behavior/ROI compatibility: PASS on Python 3.9 and 3.12;
- visual result: improved, especially dark_blue, but not strong enough for production adoption by itself;
- decision: reject for v0.3 rather than hand-style it.

Candidate B — PySide6-Fluent-Widgets 1.11.3:
- Fluent light visual result: PASS for bounded production adoption;
- existing Auto Crop workflow and real pyqtgraph RectROI/backend path: PASS;
- Fluent dark result: reject for v0.3 because the surrounding application is not a complete dark-mode system;
- normal pip resolution downloads PySide6-Addons 6.8.3 (~127.9 MB), which conflicts with the existing Essentials-only runtime strategy;
- explicit Essentials-only/no-deps proof: PASS with no PySide6 Addons available.

Production decision:
- keep PySide6-Essentials;
- adopt Fluent light only for the Auto Crop review surface in a separate bounded production change;
- use an explicit no-deps UI dependency installation path so package metadata cannot reintroduce Addons;
- measure final Portable size delta before production merge;
- do not expand this into a global theme/dark-mode redesign.
