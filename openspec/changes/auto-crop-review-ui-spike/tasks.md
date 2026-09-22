# Tasks

## 1. Research gate

- [x] 1.1 Confirm current Auto Crop behavior and implementation boundary.
- [x] 1.2 Screen reusable candidates for license, Python 3.9/PySide6 compatibility, maintenance and integration cost.
- [x] 1.3 Select qt-material 2.17 as first spike candidate; retain PySide6-Fluent-Widgets as second candidate if visual quality is insufficient.

## 2. Real-dialog visual spike

- [ ] 2.1 Add an offscreen synthetic Auto Crop dialog fixture using the real AutoCropReviewDialog and existing RectROI.
- [ ] 2.2 Render baseline, qt-material light_blue and qt-material dark_blue screenshots.
- [ ] 2.3 Upload screenshots as a CI artifact for visual inspection.
- [ ] 2.4 Verify ROI edit/reset/decision behavior remains intact on Python 3.9 and 3.12.

## 3. Candidate decision

- [ ] 3.1 Inspect the actual rendered screenshots for both usability and visual quality.
- [ ] 3.2 If qt-material is good enough, make a separate bounded adoption change and measure Portable delta before merge.
- [ ] 3.3 If qt-material is not good enough, do not hand-style it; run one bounded PySide6-Fluent-Widgets spike instead.
- [ ] 3.4 Stop before any whole-app theme or unrelated review-surface redesign.
