# Changelog

## v0.3.0 — 2026-09-25

v0.3 turns the selector from a mostly single-pass quality filter into a complete, human-authoritative LoRA dataset workflow.

The final release is based on the post-withdrawal recovery line and passed the consolidated real-use human QA checkpoint on 2026-09-25.

### Dataset workflow

- Add explicit Dataset / View filtering, independent sorting, pagination, saved views and stable sample IDs.
- Add a dedicated Duplicate Review workflow with persistent group decisions and all-groups review.
- Add AI Review Bundle export plus suggestion-only `review_patch.json` import.
- Keep automatic recommendation as an independent baseline; manual 推荐 / 备选 / 淘汰 remains an overlay instead of consuming the automatic quota.
- Make F5 an incremental folder refresh that preserves unchanged analysis state.

### Composite Split

- Add production Composite Split review for multi-view / multi-person source images.
- Support independent output selection: selected outputs become 推荐, deselected outputs become 淘汰.
- Materialize accepted outputs as real active-dataset files, then analyze only those generated files.
- Archive accepted source composites under `_CompositeSplit_Originals/` and exclude that archive from downstream workflows.
- Keep obvious thumbnail/UI grids out of Composite proposals.

### General Auto Crop

- Add conservative ISNetIS-based crop proposals for current active 推荐 images after Composite resolution.
- Keep crop proposals as metadata until Final Training Export; source pixels are not rewritten by Auto Crop.
- Add draggable/resizable pyqtgraph RectROI, reset, Accept, Keep Original and Restore Pending.
- Add Fluent Filmstrip review UI with real candidate thumbnails, scoped Light/Dark, vertical scrolling and a one-row default candidate viewport.
- Download and SHA-verify the Auto Crop segmentation model on first use instead of bloating the base Portable package.

### Source Organizer and Text Cleanup

- Add optional transactional Source Organizer for moving active files into 推荐 / 备选 / 淘汰 while preserving relative provenance.
- Add dry-run/confirmation, collision checks and rollback safeguards for source moves.
- Keep Text Cleanup detection + repair as one feature behind the application boundary while preserving PP-OCRv5, MI-GAN, TELEA and Navier-Stokes behavior.
- Keep training export, text repair output and Auto Crop output separate from source-image pixel data.

### Interface, i18n and architecture

- Add permanent live Qt i18n infrastructure with Chinese (`zh_CN`) as the source/default locale and English (`en_US`) as the first translated locale.
- Persist language choice and allow live switching without restarting the app.
- Establish the bounded UI -> `SelectorApplication` -> feature-backend architecture seam.
- Enforce sibling feature independence and Qt-free backend boundaries in CI.
- Keep PySide6-Essentials; PySide6-Addons is not required.

### Verification

- Python 3.9 / 3.12 production and feature regression coverage.
- Windows Portable packaged EXE self-test.
- 10 / 10 GitHub Actions workflows passed on the accepted recovery candidate.
- Consolidated Stage 4 real-use human QA: **PASS**.
- Source Organizer verified as part of the accepted consolidated QA.
- Auto Crop Light/Dark review verified as part of the accepted consolidated QA.

## v0.2.0 — 2026-09-19

This release focuses on making the project usable by people who did not build the original development environment.

### Distribution and setup

- Add a **Windows x64 Portable** build: extract the ZIP and run the executable without installing Python or CUDA.
- Add `安装.bat` for source users; it creates an isolated local `.venv` and installs dependencies automatically.
- Make `启动.bat` prefer the project-local `.venv`.
- Replace the legacy RapidOCR runtime dependency with a small local Apache-2.0 DB detector around the bundled PP-OCRv5 ONNX model.

### Models and runtime

- Remove the ImageHash/SciPy runtime dependency by using an OpenCV DCT perceptual hash.
- Pin a single OpenCV contrib build to avoid duplicate OpenCV runtimes in Portable.
- Keep MI-GAN out of the repository itself.
- Download MI-GAN automatically on first use when AI repair is selected.
- Verify the downloaded MI-GAN file before loading it.
- Add a packaged-runtime self-test for the core face-quality, pose and OCR models.

### Release engineering

- Slim the Portable dependency graph by using PySide6 Essentials, avoiding eager MediaPipe task-family imports, excluding unused Pillow AVIF support, and dropping OpenCV's unused FFmpeg video codec.
- Reduce the current Windows Portable candidate from about 487 MB unpacked to about 307 MB while keeping the packaged runtime smoke test green.
- Add a reproducible PyInstaller Windows build specification.
- Add GitHub Actions packaging for the Portable ZIP and SHA-256 checksum.
- Attach Portable artifacts automatically to tagged GitHub Releases.
- Expand the README with setup, usage help, common questions and the rationale behind the quality-evaluation pipeline.

## v0.1.0

Initial public source snapshot.
