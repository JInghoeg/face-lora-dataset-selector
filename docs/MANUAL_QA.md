# Manual QA Workspace

This is the canonical way to prepare and clean Windows Portable builds for human QA.

The purpose is to stop ad-hoc QA folders such as:

```text
G:\FaceLoRA-QA-8ce96a9
G:\FaceLoRA-QA-some-other-build
G:\random-test-folder
```

from accumulating across conversations.

## Canonical QA root

`tools/qa-portable.ps1` resolves the QA root in this order:

1. `FACE_LORA_QA_ROOT`, when explicitly configured;
2. `G:\FaceLoRA-QA` when drive G exists;
3. `%LOCALAPPDATA%\FaceLoRA-QA` as fallback.

Do not invent another QA root in manual instructions unless the user explicitly requests one.

The managed layout is always:

```text
FaceLoRA-QA/
├─ .face-lora-qa-root
└─ current/
   ├─ app/          # extracted GitHub Actions Portable artifact
   ├─ scratch/      # disposable QA outputs / temporary test material
   └─ QA_INFO.txt   # run id, commit, branch, artifact and EXE path
```

Only one candidate is kept under `current`.

Preparing the next candidate removes the previous `current` first.

## Prepare a verified candidate

From a checkout containing the helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Prepare -RunId <verified-run-id>
```

Use an explicit verified run ID when a release/recovery checkpoint has been pinned.

If `-RunId` is omitted, the helper resolves the latest successful `Build Windows Portable` run for the requested/current branch.

The helper:

- validates that the selected run completed successfully;
- removes the old managed `current` workspace;
- downloads the stable artifact name `Face-LoRA-Dataset-Selector-Windows-x64-Portable`;
- extracts directly into `current\app`;
- creates `current\scratch`;
- writes `current\QA_INFO.txt`;
- prints the actual EXE path.

Do not manually create commit-named QA directories.

## Show the current candidate

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Status
```

## Clean the current managed candidate

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\qa-portable.ps1 -Action Clean
```

The script will only delete `current` when the QA-root sentinel exists.

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

It explicitly excludes the canonical `FaceLoRA-QA` root.

## QA output rule

Any disposable output created only for manual testing should go under:

```text
<QA root>\current\scratch
```

Do not use the real source dataset for destructive/source-moving checks.

For Source Organizer or any other source-mutating QA, first copy the smallest representative test dataset into `scratch` and operate on that copy.

## Assistant / future-thread rule

When giving the user a Portable manual-QA instruction:

1. read the current verified run ID from `docs/PROJECT_STATE.md` / the active Draft PR;
2. use `tools/qa-portable.ps1 -Action Prepare -RunId ...`;
3. never invent a new top-level test path or candidate folder name;
4. never ask the user to keep multiple extracted candidates unless a comparison explicitly requires it;
5. put disposable test outputs in `current\scratch`;
6. after a candidate is superseded, the next Prepare should replace it automatically;
7. use `CleanLegacy` only for historical ad-hoc folders created before this convention.

GitHub Actions artifacts are server-side and expire according to their configured retention. This workspace rule controls only local QA files.
