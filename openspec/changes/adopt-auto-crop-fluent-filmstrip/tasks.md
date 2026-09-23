# Tasks

## 1. Production presentation

- [x] 1.1 Move Auto Crop review presentation into `ui/qt/auto_crop_review.py` while preserving `app.AutoCropROIWidget` / `app.AutoCropReviewDialog` compatibility imports.
- [x] 1.2 Implement the accepted Fluent Filmstrip layout.
- [x] 1.3 Use real thumbnails through the existing `ThumbnailWorker` / cache pipeline with stable sample IDs.
- [x] 1.4 Add the top-right Auto Crop-scoped Light/Dark toggle and coherent scoped dark surfaces.
- [x] 1.5 Preserve a legacy presentation fallback when Fluent is unavailable.
- [x] 1.6 Make the candidate area vertically resizable via QSplitter, wrap thumbnails into more rows as height grows, and use mouse wheel + native vertical scrollbar for overflow.

## 2. Runtime / packaging

- [x] 2.1 Add an explicit no-Addons Fluent dependency installer and wire `安装.bat`.
- [x] 2.2 Wire Portable CI/build preparation without adding PySide6-Addons.
- [x] 2.3 Ensure third-party notices cover newly distributed packages/licenses.

## 3. Verification

- [ ] 3.1 Python 3.9 + 3.12 Auto Crop production UI smoke.
- [ ] 3.2 Verify RectROI edit/reset/accept/keep/restore behavior.
- [ ] 3.3 Verify Filmstrip thumbnails and stable-ID selection.
- [ ] 3.4 Render production Light and Dark screenshots for user review.
- [ ] 3.5 Verify app startup still works with Fluent physically unavailable.
- [ ] 3.6 Build Portable, run packaged self-test, and record final size delta.
- [ ] 3.7 Verify candidate overflow exposes a vertical scrollbar, mouse-wheel scrolling changes its position, and increasing candidate-area height reveals more rows / reduces scroll range.

## 4. Closeout

- [ ] 4.1 User reviews the real production Light/Dark result.
- [ ] 4.2 Reconcile implementation against proposal/design/tasks.
- [ ] 4.3 Archive this change and merge only after accepted verification.
