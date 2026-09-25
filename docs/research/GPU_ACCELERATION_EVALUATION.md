# GPU acceleration evaluation — v0.4 research

Status: **research only; production GPU integration is not authorized**

Tracker: Issue #55

## Question

Would optional GPU inference materially improve Face LoRA Dataset Selector enough to justify the dependency, packaging, compatibility, and maintenance cost?

The decision must be based on real end-to-end workflow measurements, not isolated model throughput.

## Current product split

### ONNX Runtime work that can plausibly move to an accelerator

- Ranking:
  - eDifFIQA — 112×112 face-quality inference
  - 3DDFA — 120×120 head-pose inference
- Composite Split:
  - DeepGHS person detector
  - DeepGHS head detector
- General Auto Crop:
  - ISNetIS at a 1024×1024 inference canvas
- Text Cleanup:
  - PP-OCRv5 DB detector
  - MI-GAN repair

### Work that remains CPU-side in the current architecture

- OpenCV YuNet face detection
- OpenCV BRISQUE
- MediaPipe Pose
- image decode / resize / colorspace conversion
- pHash
- OCR / YOLO / mask post-processing
- TELEA / Navier-Stokes
- filesystem, hashing, cache work

Therefore a faster ONNX provider cannot be assumed to accelerate the whole initial-analysis pipeline by the same factor as model inference.

The strongest expected GPU value is currently:

1. General Auto Crop;
2. Text Cleanup detection / MI-GAN;
3. Composite Split;
4. full Ranking only as a secondary target.

## Candidate A — direct ONNX Runtime CUDA EP

Official ONNX Runtime documentation:
https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html

Current facts checked 2026-09-26:

- ONNX Runtime GPU packages from 1.27 use CUDA 13 by default on PyPI.
- CUDA EP can be ordered before CPU EP so unsupported work has a CPU fallback.
- CUDA / cuDNN DLLs can be preloaded, including libraries installed from NVIDIA Python packages.
- Provider fallback and host/device transfers mean an individual model can still fail to deliver useful end-to-end gain.

### Distribution cost

Current Windows x64 PyPI artifacts checked 2026-09-26:

- onnxruntime 1.30.0, CPython 3.12: about 14.3 MB
- onnxruntime-gpu 1.30.0, CPython 3.12: about 160.5 MB
- nvidia-cudnn-cu13 9.26.0.51: about 419.6 MB
- nvidia-cublas 13.8.0.4: about 423.3 MB

Sources:
- https://pypi.org/project/onnxruntime/1.30.0/
- https://pypi.org/project/onnxruntime-gpu/1.30.0/
- https://pypi.org/project/nvidia-cudnn-cu13/9.26.0.51/
- https://pypi.org/project/nvidia-cublas/13.8.0.4/

These are compressed wheel sizes, not final installed Portable size, and CUDA requires additional runtime pieces beyond the two NVIDIA examples above. The important conclusion is directional: a fully self-contained CUDA runtime would add **hundreds of megabytes** and can plausibly dominate the existing Portable size.

Do not bundle a self-contained CUDA stack into the base Portable unless real workflow gains justify it.

### Python support consideration

The project still validates Python 3.9 compatibility. The current ONNX Runtime GPU 1.30 Windows artifacts are for newer CPython versions, so modern GPU packaging cannot silently replace the universal current runtime while retaining the existing support floor.

Changing the Python support floor is a separate product decision and is out of scope for this benchmark.

## Candidate B — Windows ML + vendor execution provider

Official Windows ML documentation:
- https://learn.microsoft.com/windows/ai/new-windows-ml/overview
- https://learn.microsoft.com/windows/ai/new-windows-ml/supported-execution-providers
- https://learn.microsoft.com/windows/ai/new-windows-ml/distributing-your-app

Current Windows ML can dynamically acquire hardware-specific execution providers on Windows 11 24H2 or later. NVIDIA's current Windows ML provider is:

\`NvTensorRtRtxExecutionProvider\`

Current documented target:
- GeForce RTX 30-series and newer;
- compatible driver / CUDA requirements.

DirectML is now documented as a legacy provider; it is not the preferred new-performance route.

### Why Windows ML is interesting

It can keep hardware-vendor execution providers outside the main application payload and let Windows manage/download them. This could avoid shipping a very large CUDA runtime inside the base Portable.

The current \`onnxruntime-windowsml\` 1.30 CPython 3.12 Windows wheel is about 27.4 MB:
https://pypi.org/project/onnxruntime-windowsml/1.30.0.202609102321/

### Why Windows ML is not automatically better

For Python, current Windows ML documentation supports Python 3.10–3.13 and uses framework-dependent deployment. The Windows App SDK Runtime must be present on the end user's machine.

That conflicts with the project's current preference for a genuinely self-contained Portable. The deployment prerequisite therefore has to be evaluated alongside speed.

## Preliminary necessity assessment

GPU acceleration is:

- **not required for correctness**;
- **not a release blocker**;
- **not justified as a default runtime change from architecture inspection alone**;
- **worth benchmarking** because several optional workflows are dominated by medium/large ONNX models.

The likely product outcome, if speedups are material, is more plausibly an **optional accelerator with automatic CPU fallback** than a mandatory CUDA base Portable.

## Research benchmark

Tool:
\`tools/benchmarks/gpu_runtime_benchmark.py\`

The harness does not edit production provider selection. It overrides ONNX Runtime provider selection only inside its own research process and then calls the existing feature runtimes.

Stages:

- \`ranking\`
- \`auto_crop\`
- \`composite\`
- \`text_scan\`
- \`migan\`

Outputs include:

- wall time;
- process CPU time / approximate core-equivalents;
- best-effort NVIDIA utilization and device memory telemetry;
- actual provider list used by each ONNX Runtime session;
- output signatures for CPU/GPU parity screening;
- model-cache mutation warning, so a first-time model download is not mistaken for inference cost.

CPU and CUDA must be run in separate environments with the same Python version, same dataset, same selected files, and already-primed model caches.

## Decision gate

Do not integrate a production GPU provider merely because isolated inference is faster.

A candidate should proceed only if:

1. real workflow wall-time gain is material after preprocessing/post-processing;
2. results remain behavior-compatible;
3. CPU fallback is automatic and verified;
4. cold-start / first-session cost is acceptable;
5. UI responsiveness improves or at least does not regress;
6. VRAM use is acceptable;
7. deployment size / external prerequisite cost is proportionate;
8. the chosen path does not silently break supported non-GPU systems.

Possible outcomes after measurement:

- **Keep CPU** — gain is too small or deployment cost is too high.
- **Optional accelerator** — material gain for model-heavy workflows while base Portable remains universal.
- **Production GPU path** — only if the data clearly supports a default path and fallback/deployment remains robust.

No production-runtime decision is made by this research note.
