# Windows ML runtime feasibility — v0.4

Status: **active bounded research slice**  
Branch: `research/v0.4-windows-ml-runtime`  
Tracker: #55

## Why this slice exists

Draft PR #96 proved that the shared ONNX Runtime provider abstraction and GPU -> CPU fallback work, but the self-contained CUDA/cuDNN distribution path is not a viable default product package.

Observed #96 packaging evidence:

- base Windows Portable remained roughly 426 MB as a CI artifact;
- the NVIDIA accelerator artifact was roughly 1.9 GB compressed;
- the combined/uncompressed product footprint was roughly 3.3 GB;
- most added size came from CUDA/cuDNN/ORT GPU runtime binaries, not product feature code.

Therefore #96 is retained only as technical evidence and is closed unmerged.

## Candidate: Windows ML system-managed execution providers

Windows ML can discover compatible execution providers through `ExecutionProviderCatalog` and download them on demand instead of requiring the application to redistribute the full vendor runtime.

Current Microsoft documentation checked on 2026-10-22 states:

- catalog-delivered hardware EPs require Windows 11 24H2 / build 26100 or later;
- NVIDIA is exposed as `NvTensorRtRtxExecutionProvider`;
- the documented NVIDIA requirement is GeForce RTX 30-series or newer, subject to driver/device compatibility;
- Python registers a downloaded provider with `onnxruntime.register_execution_provider_library()`;
- first-time `ensure_ready_async()` can download provider packages and may take seconds or minutes, so production UX must not trigger it silently.

References:

- https://learn.microsoft.com/windows/ai/new-windows-ml/supported-execution-providers
- https://learn.microsoft.com/windows/ai/new-windows-ml/initialize-execution-providers
- https://learn.microsoft.com/windows/ai/new-windows-ml/api-reference
- https://pypi.org/project/onnxruntime-windowsml/

The current CPython 3.12 x64 `onnxruntime-windowsml` wheel is about 27 MB, which is small enough to justify this feasibility check. This is **not** yet a claim that the final packaged application remains fully standalone.

## Important deployment uncertainty

Python Windows ML uses Windows App SDK / pywinrt projections. Microsoft also documents two deployment details that must be treated as product constraints:

1. Windows App SDK must be initialized before Windows ML calls.
2. `winrt-runtime` can include an `msvcp140.dll` that conflicts with other libraries; Microsoft recommends removing that copy and relying on the Microsoft Visual C++ Redistributable.

This may weaken the current "unzip and run" Portable property. The research slice must measure that cost before any production dependency change.

## Probe added by this branch

`tools/benchmarks/windows_ml_runtime_probe.py` performs only infrastructure feasibility checks:

- verifies the Windows build;
- enumerates Windows ML providers;
- targets only `NvTensorRtRtxExecutionProvider`;
- does **not** download anything unless `--ensure` is explicitly passed;
- registers the ready provider with Python ONNX Runtime;
- optionally creates a real project-model session;
- optionally creates a CPU-only session for fallback validation;
- writes a machine-readable JSON report;
- makes the documented pywinrt DLL workaround opt-in and reversible.

It does not change feature code, product provider defaults, or production requirements.

## Target-workstation checkpoint

Use a clean research environment on the target Windows workstation. Do not
modify the released Portable for this checkpoint.

### Preferred launcher

Run the checkpoint from **Command Prompt** through the CMD launcher:

```bat
tools\benchmarks\run-windows-ml-checkpoint.cmd
```

The launcher sets `POWERSHELL_UPDATECHECK=Off` only for its child process
before starting `pwsh`. This works around the upstream PowerShell 7.6.x
localized update-notification startup crash that can terminate `pwsh` before
any profile or script runs (for example the zh-Hans
`totalWidth ('-17')` failure). If `pwsh.exe` is unavailable, the launcher
falls back to Windows PowerShell.

The underlying PowerShell helper creates its isolated venv and reports only
under the gitignored `_research_output/windows-ml-runtime/` folder. It does
not install the Windows App SDK Runtime and does not download an execution
provider unless `-EnsureEp` is explicitly supplied.

If discovery reports `download_required` and the system-managed EP download
is explicitly accepted:

```bat
tools\benchmarks\run-windows-ml-checkpoint.cmd -EnsureEp
```

For the real-model pass:

```bat
tools\benchmarks\run-windows-ml-checkpoint.cmd -EnsureEp -Model "<path-to-existing-project-model.onnx>"
```

Only add `-FixWinrtRuntime` in the isolated research environment if the
documented pywinrt `msvcp140.dll` conflict is actually encountered.

Upstream PowerShell references:
- https://github.com/PowerShell/PowerShell/issues/28239
- https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_update_notifications

### Lower-level probe commands

The Python probe remains available for diagnosis after the isolated research
environment has been prepared:

```powershell
python tools/benchmarks/windows_ml_runtime_probe.py --output .project/qa/windows-ml-discovery.json
```

```powershell
python tools/benchmarks/windows_ml_runtime_probe.py --ensure --output .project/qa/windows-ml-ready.json
```

```powershell
python tools/benchmarks/windows_ml_runtime_probe.py --ensure --model "<path-to-existing-project-model.onnx>" --check-cpu-fallback --output .project/qa/windows-ml-session.json
```

## Target-workstation discovery evidence (2026-10-27)

The target Windows workstation produced a successful Windows ML catalog discovery
on Windows build 26200 using the isolated Python 3.12 environment.

Observed facts:
- Windows ML bootstrap succeeded.
- ONNX Runtime exposed CPU + DirectML devices before dynamic provider registration.
- The Windows ML catalog advertised the NVIDIA provider as
  `NvTensorRTRTXExecutionProvider` with `NOT_PRESENT` state.
- Microsoft documentation names the same EP
  `NvTensorRtRtxExecutionProvider`.
- The original probe compared provider names case-sensitively and therefore
  misclassified this machine as `target_provider_unavailable`.
- The probe now matches EP names case-insensitively and uses the catalog-returned
  provider name for Python ORT registration.

Interpretation: the target machine has passed hardware/catalog discovery far
enough to proceed to the explicit `EnsureReadyAsync` acquisition checkpoint.
The NVIDIA EP is not yet installed/prepared, so production feasibility is not
yet proven.

## Decision gate

Do **not** integrate Windows ML into `src/infrastructure/inference_runtime.py` until the target-workstation checkpoint answers all of these:

1. Does the RTX workstation advertise `NvTensorRtRtxExecutionProvider`?
2. Can the provider be prepared and registered without bundling CUDA/cuDNN?
3. Can at least one real project ONNX model create a session with that EP?
4. Does the CPU-only session remain available as a reliable fallback?
5. What Windows App Runtime / VC++ prerequisite is actually required on a clean machine?
6. Does the installation/download UX preserve an acceptable Portable product experience?
7. After feasibility passes, does the existing real-workflow benchmark show enough gain on Auto Crop / Composite / Text Cleanup to justify integration?

If the deployment/Portable answers are unacceptable, Windows ML remains a research result and the project returns to other accelerator deployment options. Feature modules remain unchanged either way.


## Reproducible research environment

The branch now pins the Windows ML Python research stack in
`tools/benchmarks/requirements-windowsml.txt` rather than adding it to the
product runtime requirements:

- `wasdk-Microsoft.Windows.AI.MachineLearning[all]==2.3.0`
- `wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap==2.3.0`
- `onnxruntime-windowsml==1.25.2.202605110140`

These versions are for this feasibility checkpoint only. The ORT pin is not an arbitrary downgrade: `wasdk-Microsoft.Windows.AI.MachineLearning==2.3.0` declares an exact dependency on `onnxruntime-windowsml==1.25.2.202605110140`. The first CI resolver pass intentionally caught and rejected an invalid mix with ORT 1.30.0. These research pins do not become product support commitments merely because CI resolves them.

The dedicated `Windows ML Research` workflow runs on `windows-latest` with
Python 3.12 and verifies:

1. the pinned distributions resolve exactly;
2. the probe compiles and exposes its CLI;
3. discovery executes without `--ensure`, so CI can never trigger an EP
   download;
4. a machine-readable report is always produced;
5. expected hosted-runner outcomes such as missing Windows App SDK Runtime,
   no NVIDIA provider, or download-required state are recorded as observations
   rather than misclassified as product failures.

Actual NVIDIA session execution remains a target-workstation checkpoint.


## Hosted-runner deployment evidence

The dedicated Windows ML CI produced a useful negative deployment result on a
Windows Server 2025 / build 26100 hosted runner:

- the matched Windows ML Python packages resolved successfully;
- `onnxruntime-windowsml 1.25.2` imported and exposed the required dynamic EP
  APIs;
- CPU and DirectML EP devices were visible before any dynamic registration;
- Windows App SDK bootstrap then failed non-interactively with
  `Package dependency criteria could not be resolved`.

The probe classifies this as `app_sdk_runtime_unavailable`, not as a product or
Python-package failure. This is concrete evidence that installing the Python
wheels alone does not preserve the current Portable contract: a matching
Windows App SDK Runtime is a separate machine-level prerequisite.


## Deployment interpretation: optional accelerator remains viable

The framework-dependent prerequisite does not automatically disqualify Windows
ML, but it changes the product model.

Microsoft supports unpackaged/framework-dependent applications by distributing
the matching x64 `WindowsAppRuntimeInstall.exe` or the required MSIX packages.
The standalone installer deploys the Framework, Main, Singleton and DDLM
runtime packages and can be used as part of an application's setup flow.

Official deployment references:

- https://learn.microsoft.com/windows/apps/windows-app-sdk/downloads
- https://learn.microsoft.com/windows/apps/windows-app-sdk/deploy-unpackaged-apps
- https://learn.microsoft.com/windows/apps/windows-app-sdk/deployment-architecture

Therefore the feasible product shape, if target-workstation performance later
justifies Windows ML, is **not** "replace the base Portable runtime". It is:

1. preserve the current CPU-capable Portable as the zero-install baseline;
2. expose GPU acceleration as an explicit optional capability;
3. detect whether the matching Windows App SDK Runtime and NVIDIA EP are ready;
4. only after explicit user action, guide/deploy the Microsoft runtime and
   acquire the system-managed NVIDIA EP;
5. always retain the existing CPU fallback.

This keeps the multi-gigabyte CUDA/cuDNN stack out of the application payload,
but it introduces machine-level state and first-run installation UX. That trade
off must be reviewed before production integration; this PR does not implement
an installer or change product dependencies.
