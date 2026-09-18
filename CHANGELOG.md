# Changelog

## v0.2.0 — in progress

The next public release focuses on making the project usable by people who did not build the original development environment.

### Distribution and setup

- Add a **Windows x64 Portable** build: extract the ZIP and run the executable without installing Python or CUDA.
- Add `安装.bat` for source users; it creates an isolated local `.venv` and installs dependencies automatically.
- Make `启动.bat` prefer the project-local `.venv`.
- Pin the compatible legacy RapidOCR package used by the current text-detection implementation.

### Models and runtime

- Keep MI-GAN out of the repository itself.
- Download MI-GAN automatically on first use when AI repair is selected.
- Verify the downloaded MI-GAN file before loading it.
- Add a packaged-runtime self-test for the core face-quality, pose and OCR models.

### Release engineering

- Add a reproducible PyInstaller Windows build specification.
- Add GitHub Actions packaging for the Portable ZIP and SHA-256 checksum.
- Attach Portable artifacts automatically to tagged GitHub Releases.
- Expand the README with setup, usage help, common questions and the rationale behind the quality-evaluation pipeline.

## v0.1.0

Initial public source snapshot.
