# Manual QA Workspace

This is the canonical way to prepare and clean Windows Portable builds for human QA.

The goals are:

- one stable QA location across conversations;
- keep downloaded models and unchanged Portable runtime files;
- download a small incremental overlay when the runtime is unchanged;
- automatically fall back to a full Portable when dependencies/runtime really changed;
- keep disposable QA outputs easy to delete.

## Canonical QA root

`tools/qa-portable.ps1` resolves the QA root in this order:

1. `FACE_LORA_QA_ROOT`, when explicitly configured;
2. `G:\FaceLoRA-QA` when drive G exists;
3. `%LOCALAPPDATA%\FaceLoRA-QA` as fallback.

Do not invent another QA root in manual instructions unless the user explicitly requests one.

The managed layout is:

```text
FaceLoRA-QA/
├─ .face-lora-qa-root
├─ runtime/
│  ├─ Face-LoRA-Dataset-Selector/   # persistent Portable runtime
│  │  ├─ Face LoRA Dataset Selector.exe
│  │  ├─ _internal/
│  │  ├─ qa-runtime-fingerprint.txt
│  │  └─ qa-runtime-manifest.txt
│  └─ _FaceLoRA_ModelCache/         # persistent on-demand model cache
└─ current/
   ├─ scratch/                       # disposable outputs/test copies
   └─ QA_INFO.txt                    # currently prepared run/commit/mode
```

`runtime` is deliberately persistent.

`current` is disposable and is replaced for every candidate.

## Incremental update model

The Build Windows Portable workflow publishes two artifacts:

- `Face-LoRA-Dataset-Selector-Windows-x64-Portable` — full Portable fallback;
- `Face-LoRA-Dataset-Selector-Windows-x64-QA-Overlay` — small candidate overlay.

The full build records a runtime fingerprint derived from every stable Portable file except the candidate-changing files such as the EXE, compiled translation catalog and top-level product docs.

During `Prepare`:

1. the helper downloads the small QA Overlay first;
2. it compares the overlay runtime fingerprint with the locally cached runtime;
3. if they match, only the overlay files are applied;
4. if they do not match, the helper downloads and installs the full Portable;
5. the persistent `_FaceLoRA_ModelCache` is never removed by either path.

A fingerprint change means something in the reusable runtime really changed, for example:

- Python/runtime files;
- packaged dependencies;
- bundled model files;
- PyInstaller-collected resources;
- packaging structure.

This prevents unsafe mixtures of a new executable with an incompatible old runtime.

## Persistent downloaded models

The frozen application already resolves its model cache one level above the Portable directory.

With the canonical layout this becomes:

```text
G:\FaceLoRA-QA\runtime\_FaceLoRA_ModelCache
```

This cache is preserved across:

- normal `Prepare`;
- incremental overlay updates;
- full Portable fallback refreshes;
- `Clean`;
- `ResetRuntime`.

It can contain on-demand models such as Auto Crop ISNetIS, Composite Split detectors and MI-GAN.

Do not delete this cache as part of ordinary QA cleanup.

## Prepare a verified candidate

From a checkout containing the helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Prepare -RunId <verified-run-id>
```

Use an explicit verified run ID when a release/recovery checkpoint has been pinned.

If `-RunId` is omitted, the helper resolves the latest successful `Build Windows Portable` run for the requested/current branch.

The helper prints whether the update used:

```text
Update mode : overlay
```

or:

```text
Update mode : full
```

After the first compatible full runtime is installed, ordinary code-only QA candidates should normally use `overlay`.

## Stable EXE path

The executable path no longer changes with each commit:

```text
G:\FaceLoRA-QA\runtime\Face-LoRA-Dataset-Selector\Face LoRA Dataset Selector.exe
```

Future assistant instructions must not invent commit-named app directories.

## Show current QA state

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Status
```

This shows the cached runtime, model cache, current QA metadata and scratch location.

## Clean disposable QA state

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Clean
```

This removes only `current` state/scratch.

It preserves:

- the Portable runtime;
- the runtime fingerprint;
- downloaded model cache.

## Force a fresh Portable runtime

If the local Portable runtime itself is suspected to be damaged:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action ResetRuntime
```

This removes only:

```text
runtime\Face-LoRA-Dataset-Selector
```

It still preserves:

```text
runtime\_FaceLoRA_ModelCache
```

The next `Prepare` will perform a full Portable download.

## Clean old ad-hoc QA directories

First preview exactly what would be removed:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action CleanLegacy
```

Then delete the listed legacy directories:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action CleanLegacy -Force
```

Legacy cleanup only targets sibling directories named:

```text
FaceLoRA-QA-*
FaceLoRA_QA-*
```

Before deleting each legacy directory, `-Force` searches it for `_FaceLoRA_ModelCache` directories and copies previously downloaded model files into the canonical persistent model cache. Partial `.part` downloads are ignored.

The canonical `G:\FaceLoRA-QA` root is explicitly excluded.

## QA output rule

Any disposable output created only for manual testing goes under:

```text
<QA root>\current\scratch
```

Do not use the real source dataset for destructive/source-moving checks.

For Source Organizer or other source-mutating QA, first copy the smallest representative test dataset into `scratch`.

## Assistant / future-thread rule

When giving the user a Portable manual-QA instruction:

1. read the verified Build Windows Portable run ID from the active project state / Draft PR;
2. use `tools/qa-portable.ps1 -Action Prepare -RunId ...`;
3. never use raw `gh run download ... -D <new random path>` as the normal QA instruction;
4. never invent a commit-named top-level test folder;
5. preserve `runtime` and `runtime\_FaceLoRA_ModelCache`;
6. let the helper decide overlay vs full refresh from the runtime fingerprint;
7. put disposable outputs in `current\scratch`;
8. use `CleanLegacy` for pre-convention ad-hoc directories.

GitHub Actions artifacts remain server-side and expire according to their configured retention. The incremental overlay exists specifically to reduce repeated local download traffic.
