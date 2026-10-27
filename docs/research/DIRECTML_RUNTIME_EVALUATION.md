# DirectML Runtime Evaluation

## Status

**Active bounded research / optional accelerator profile.**

This work does not replace the universal CPU Portable and does not authorize a
release. It evaluates whether a separate Python 3.12 DirectML profile can
provide a practical GPU path without the multi-gigabyte CUDA/cuDNN payload or
the machine-level Windows ML execution-provider acquisition flow.

## Why this candidate exists

Two earlier deployment candidates established useful boundaries:

1. Direct ONNX Runtime CUDA works technically through the shared provider
   abstraction, but the self-contained NVIDIA runtime proof expanded the
   uncompressed Portable to roughly 3.3 GB.
2. Windows ML can discover the NVIDIA NvTensorRtRtx provider on the target RTX
   workstation, but the Python path is framework-dependent and the
   system-managed EP acquisition checkpoint did not produce a clean completed
   session result. That route is parked rather than productized.

DirectML is not Microsoft's preferred future execution-provider direction.
It is in sustained engineering. It remains supported, works through DirectX 12
across major GPU vendors, and does not require a CUDA toolkit or vendor runtime
bundle. For this project that makes it a useful deployment-cost candidate.

## Runtime profile

The research profile is intentionally separate from the base runtime:

- universal profile: `requirements/runtime.txt`, existing Python compatibility,
  CPU-capable Portable unchanged;
- DirectML profile: `requirements/runtime-directml.txt`, Python 3.12 for the
  production build experiment;
- pinned research runtime: `onnxruntime-directml==1.24.4`;
- shared application semantics remain `Auto / GPU / CPU`;
- CPU fallback remains mandatory.

The upstream Windows CPython 3.12 wheel is approximately 25.1 MB. Installed and
final PyInstaller payload sizes are measured by CI rather than inferred from
the wheel size.

## Shared provider policy

Feature packages do not select hardware.

`src/infrastructure/inference_runtime.py` owns provider choice:

1. CUDA when a CUDA-capable ORT distribution is present;
2. DirectML when a DirectML-capable ORT distribution is present;
3. CPU as the mandatory fallback.

DirectML sessions require:

- sequential ORT execution mode;
- memory-pattern optimization disabled.

Those constraints are applied in the shared infrastructure layer so Auto Crop,
Composite Split, Text Cleanup, Ranking, and future model-backed features do not
gain DirectML-specific code.

## CI evidence required

The DirectML research workflow must prove all of the following before this
profile is considered viable:

1. the pinned DirectML distribution resolves on Windows / Python 3.12;
2. `DmlExecutionProvider` and `CPUExecutionProvider` are exposed;
3. provider-plan and synthetic CPU-fallback tests pass;
4. real project ONNX models can create sessions through the shared provider
   layer;
5. the ordinary source self-test still passes;
6. PyInstaller packages the DirectML runtime;
7. the packaged executable self-test passes;
8. final uncompressed Portable size is recorded.

The hosted runner is not treated as a performance benchmark. If it has no
useful GPU adapter, successful CPU fallback is valid CI evidence.


## CI result — 2026-10-27

The bounded repository-side gate passed.

Measured on the same PR/commit family:

- universal CPU Portable: **622.3 MB** uncompressed;
- DirectML Portable: **647.9 MB** uncompressed;
- DirectML increment: **25.6 MB / ~4.1%**;
- packaged `DirectML.dll`: **17.7 MB**;
- installed `onnxruntime-directml 1.24.4` distribution footprint in the CI
  environment: **74,408,109 bytes**;
- source self-test: PASS;
- PyInstaller build: PASS;
- packaged executable self-test: PASS;
- architecture and feature-boundary workflows: PASS.

The Windows hosted runner exposes `DmlExecutionProvider` and
`CPUExecutionProvider`, but has no matching DirectML device. All seven real
project ONNX models therefore exercised the shared provider path and cleanly
fell back to CPU. The runtime now detects this ORT-managed silent fallback after
session creation and records an explicit fallback reason.

Models covered by the real-project probe:

- eDifFIQA;
- 3DDFA MobileNet;
- PP-OCRv5 detector;
- Composite person detector;
- Composite head detector;
- ISNetIS;
- MI-GAN.

This proves packaging, model loading, shared provider selection, and CPU
fallback. It does **not** prove DirectML GPU execution speed on the target RTX
workstation.

## Current disposition

DirectML passes the repository-side deployment-cost gate and is retained as the
optional accelerator candidate.

It is materially smaller and operationally simpler than the rejected
self-contained CUDA profile, while avoiding the framework/system-EP acquisition
path that blocked the Windows ML candidate.

The remaining decision gate is one real-GPU performance checkpoint. Until that
evidence exists:

- do not make the DirectML profile the universal/default runtime;
- do not claim GPU speedup;
- keep the universal CPU Portable unchanged;
- keep Issue #55 open.

## Decision gate

After CI:

- **Reject** if packaging becomes unexpectedly large, real model sessions are
  incompatible, or fallback is fragile.
- **Keep as optional accelerator candidate** if packaging/runtime behavior is
  clean but real performance remains unmeasured.
- **Proceed to one target-workstation performance checkpoint** only if the
  repository-side evidence is clean enough that the checkpoint measures
  performance rather than debugging deployment.

No further Windows ML launcher experiments are part of this slice.
