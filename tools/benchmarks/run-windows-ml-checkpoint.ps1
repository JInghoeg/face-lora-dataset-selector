param(
    [string]$Python = "",
    [string]$Model = "",
    [switch]$EnsureEp,
    [switch]$FixWinrtRuntime
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$workRoot = Join-Path $repoRoot "_research_output\windows-ml-runtime"
$venvRoot = Join-Path $workRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
$requirements = Join-Path $repoRoot "tools\benchmarks\requirements-windowsml.txt"
$probe = Join-Path $repoRoot "tools\benchmarks\windows_ml_runtime_probe.py"

$build = [Environment]::OSVersion.Version.Build
Write-Host "Windows build: $build"
if ($build -lt 26100) {
    throw "Windows ML catalog-delivered hardware EPs require Windows 11 24H2 / build 26100 or newer."
}

function Test-PythonExecutable {
    param([string]$Candidate)
    if (-not $Candidate) { return $false }

    try {
        if (-not (Test-Path $Candidate)) {
            $resolved = Get-Command $Candidate -ErrorAction Stop
            $Candidate = $resolved.Source
        }

        $versionOutput = & $Candidate --version 2>&1
        if ($LASTEXITCODE -ne 0) { return $false }
        if ($versionOutput -notmatch '^Python\s+3\.') { return $false }
        return $true
    }
    catch {
        return $false
    }
}

function Resolve-ResearchPython {
    param([string]$Requested)

    $candidates = New-Object System.Collections.Generic.List[string]

    if ($Requested) {
        $candidates.Add($Requested)
    }

    if ($env:CONDA_PREFIX) {
        $candidates.Add((Join-Path $env:CONDA_PREFIX "python.exe"))
    }

    try {
        $py = Get-Command "py.exe" -ErrorAction Stop
        $pyResolved = & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $pyResolved) {
            $candidates.Add(([string]$pyResolved).Trim())
        }
    }
    catch {
        # py launcher is optional.
    }

    foreach ($name in @("python.exe", "python3.exe")) {
        try {
            $command = Get-Command $name -ErrorAction Stop
            if ($command.Source) {
                $candidates.Add($command.Source)
            }
        }
        catch {
            # Continue through filesystem candidates.
        }
    }

    foreach ($path in @(
        (Join-Path $env:USERPROFILE "miniconda3\python.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        "G:\miniconda3\python.exe",
        "C:\ProgramData\miniconda3\python.exe",
        "C:\ProgramData\anaconda3\python.exe"
    )) {
        if ($path) {
            $candidates.Add($path)
        }
    }

    $seen = @{}
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $key = $candidate.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true

        if (Test-PythonExecutable $candidate) {
            if (Test-Path $candidate) {
                return (Resolve-Path $candidate).Path
            }
            return (Get-Command $candidate -ErrorAction Stop).Source
        }
    }

    throw @"
No usable Python 3 interpreter was found automatically.

The Microsoft Store 'python.exe' execution alias does not count as an installed
Python runtime. This checkpoint does not require changing that alias.

If Python is installed in a non-standard location, rerun with:
  run-windows-ml-checkpoint.cmd -Python "<full-path-to-python.exe>"
"@
}

New-Item -ItemType Directory -Force -Path $workRoot | Out-Null

if (-not (Test-Path $pythonExe)) {
    $resolvedPython = Resolve-ResearchPython -Requested $Python
    $resolvedVersion = & $resolvedPython --version 2>&1
    Write-Host "Selected Python: $resolvedPython"
    Write-Host "Python version: $resolvedVersion"
    Write-Host "Creating isolated Python environment: $venvRoot"
    & $resolvedPython -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create research virtual environment with '$resolvedPython'."
    }
}

Write-Host "Installing pinned research dependencies..."
& $pythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in research environment."
}
& $pythonExe -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Windows ML research dependencies."
}

$reportName = if ($Model) { "windows-ml-session.json" } elseif ($EnsureEp) { "windows-ml-ready.json" } else { "windows-ml-discovery.json" }
$report = Join-Path $workRoot $reportName

$probeArgs = @($probe, "--output", $report)
if ($EnsureEp) {
    $probeArgs += "--ensure"
}
if ($Model) {
    $resolvedModel = (Resolve-Path $Model).Path
    $probeArgs += @("--model", $resolvedModel, "--check-cpu-fallback")
}
if ($FixWinrtRuntime) {
    $probeArgs += "--fix-winrt-runtime"
}

Write-Host ""
Write-Host "Running Windows ML probe..."
Write-Host "  EP download allowed: $([bool]$EnsureEp)"
Write-Host "  Model: $(if ($Model) { $Model } else { '<none>' })"
Write-Host "  Report: $report"
Write-Host ""

& $pythonExe @probeArgs
$probeExit = $LASTEXITCODE

if (-not (Test-Path $report)) {
    throw "Probe exited with code $probeExit without writing its JSON report."
}

$result = Get-Content $report -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "Checkpoint status: $($result.status)"
Write-Host "Target provider: $($result.target_provider)"

switch ([string]$result.status) {
    "pass" {
        Write-Host "Windows ML feasibility checkpoint PASS."
        exit 0
    }
    "download_required" {
        Write-Host "The NVIDIA EP is compatible but not installed."
        Write-Host "Re-run this helper with -EnsureEp only if you approve the system-managed EP download."
        exit 0
    }
    "dependency_import_failed" {
        Write-Host "Windows ML Python packages could not be imported."
        Write-Host "Keep this report as dependency evidence; do not alter the product environment."
        exit 0
    }
    "app_sdk_runtime_unavailable" {
        Write-Host "Windows ML Python packages and ORT are present, but the matching Windows App SDK Runtime is unavailable."
        Write-Host "Do not install a system runtime automatically; keep this report as deployment evidence."
        exit 0
    }
    "target_provider_unavailable" {
        Write-Host "Windows ML did not advertise NvTensorRtRtxExecutionProvider on this device/driver state."
        exit 0
    }
    default {
        throw "Unexpected Windows ML checkpoint status '$($result.status)' (probe exit $probeExit). See $report"
    }
}
