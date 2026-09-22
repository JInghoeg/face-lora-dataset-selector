# Tasks

## 1. Research gate

- [x] 1.1 Confirm current Auto Crop behavior and implementation boundary.
- [x] 1.2 Screen reusable candidates for license, Python 3.9/PySide6 compatibility, maintenance and integration cost.
- [x] 1.3 Select qt-material 2.17 as first spike candidate; retain PySide6-Fluent-Widgets as second candidate if visual quality is insufficient.

## 2. Real-dialog visual spike

- [x] 2.1 Add an offscreen synthetic Auto Crop dialog fixture using the real AutoCropReviewDialog and existing RectROI.
- [x] 2.2 Render baseline, qt-material light_blue and qt-material dark_blue screenshots.
- [x] 2.3 Upload screenshots as a CI artifact for visual inspection.
- [x] 2.4 Verify ROI edit/reset/decision behavior remains intact on Python 3.9 and 3.12.

## 3. Candidate decision

- [x] 3.1 Inspect the actual rendered screenshots for both usability and visual quality. Candidate A improves cohesion, especially dark_blue, but remains too close to a themed engineering-tool surface to meet the visual-quality gate by itself.
- [x] 3.2 Candidate A was not good enough; no qt-material adoption change was made.
- [x] 3.3 qt-material is not strong enough for direct adoption; do not hand-style it. Run one bounded PySide6-Fluent-Widgets spike instead.
- [x] 3.4 Stop before any whole-app theme or unrelated review-surface redesign.
- [x] 3.5 Candidate B result: Fluent light selected for bounded production adoption; Fluent dark rejected for v0.3; Essentials-only/no-Addons proof PASS; actual Portable delta must be measured in the separate adoption change.
