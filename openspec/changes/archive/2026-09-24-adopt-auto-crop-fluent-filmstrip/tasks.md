# Tasks

## 1. Production presentation

- [x] 1.1 Move Auto Crop review presentation into `ui/qt/auto_crop_review.py` while preserving `app.AutoCropROIWidget` / `app.AutoCropReviewDialog` compatibility imports.
- [x] 1.2 Implement the accepted Fluent Filmstrip layout.
- [x] 1.3 Use real thumbnails through the existing `ThumbnailWorker` / cache pipeline with stable sample IDs.
- [x] 1.4 Add the top-right Auto Crop-scoped Light/Dark toggle and coherent scoped dark surfaces.
- [x] 1.5 Preserve a legacy presentation fallback when Fluent is unavailable.
- [x] 1.6 Make the candidate area vertically resizable via QSplitter, wrap thumbnails into more rows as height grows, and use mouse wheel + native vertical scrollbar for overflow.
- [x] 1.7 Localize all user-facing Auto Crop text to “自动裁剪” and style the candidate scrollbar coherently for Light/Dark.

## 2. Runtime / packaging

- [x] 2.1 Add an explicit no-Addons Fluent dependency installer and wire `安装.bat`.
- [x] 2.2 Wire Portable CI/build preparation without adding PySide6-Addons.
- [x] 2.3 Ensure third-party notices cover newly distributed packages/licenses.

## 3. Verification

- [x] 3.1 Python 3.9 + 3.12 Auto Crop production UI smoke.
- [x] 3.2 Verify RectROI edit/reset/accept/keep/restore behavior.
- [x] 3.3 Verify Filmstrip thumbnails and stable-ID selection.
- [x] 3.4 Render production Light and Dark screenshots for user review.
- [x] 3.5 Verify app startup still works with Fluent physically unavailable.
- [x] 3.6 Build Portable, run packaged self-test, and record final size delta.
- [x] 3.7 Verify candidate overflow exposes a vertical scrollbar, mouse-wheel scrolling changes its position, and increasing candidate-area height reveals more rows / reduces scroll range.
- [x] 3.8 Verify the production title is localized to “自动裁剪复核” and Dark mode applies the scoped dark scrollbar style.

## 4. Closeout

- [x] 4.1 User reviews the real production Light/Dark result.
- [x] 4.2 Reconcile implementation against proposal/design/tasks.
- [x] 4.3 Archive this change and merge only after accepted verification.

### Verification evidence

- Python 3.9 / 3.12 production UI smoke: PASS.
- RectROI edit/reset/accept/keep/restore regression: PASS.
- Real Filmstrip thumbnails + stable sample-id selection: PASS.
- Production Light/Dark screenshots generated from the real dialog.
- Fluent-unavailable source startup fallback: PASS.
- Candidate overflow / vertical scrollbar / mouse wheel / splitter expansion behavior: PASS.
- Localized “自动裁剪复核” title + scoped Dark scrollbar style: PASS.
- Portable build + packaged self-test: PASS.
- Portable directory size: base 354,107,175 bytes -> current 357,014,677 bytes; delta +2,907,502 bytes (~2.77 MiB, +0.82%).
- Compressed QA artifact: base 157,449,121 bytes -> current 159,692,348 bytes; delta +2,243,227 bytes (~2.14 MiB, +1.42%).
- User visual review: PASS.
- Final accepted correction: default candidate viewport shows one fully visible row; the second row is fully hidden until the user expands the splitter.
- Strict one-row geometry smoke passes on Python 3.9 and 3.12 while splitter expansion / wrapped rows / vertical scrolling remain functional.
