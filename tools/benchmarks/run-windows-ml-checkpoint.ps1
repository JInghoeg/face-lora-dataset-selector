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
$condaEnvRoot = Join-Path $workRoot ".conda-py312"
$requirements = Join-Path $repoRoot "tools\benchmarks\requirements-windowsml.txt"
$probe = Join-Path $repoRoot "tools\benchmarks\windows_ml_runtime_probe.py"

$build = [Environment]::OSVersion.Version.Build
Write-Host "Windows build: $build"
if ($build -lt 26100) {
    throw "Windows ML catalog-delivered hardware EPs require Windows 11 24H2 / build 26100 or newer."
}

function Get-CompatiblePython {
    param([string]$Candidate)

    if (-not $Candidate) { return $null }

    try {
        $path = $Candidate
        if (-not (Test-Path $path)) {
            $resolved = Get-Command $Candidate -ErrorAction Stop
            $path = $resolved.Source
        }
        if (-not $path) { return $null }

        $probeOutput = & $path -c "import sys; print(sys.executable); print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
        if ($LASTEXITCODE -ne 0 -or $probeOutput.Count -lt 2) {
            return $null
        }

        $actualPath = [string]$probeOutput[-2]
        $versionText = [string]$probeOutput[-1]
        $version = [Version]$versionText

        # The pinned Windows ML stack used by this checkpoint is intentionally
        # constrained to CPython 3.11-3.14. Do not select newer preview/current
        # interpreters merely because the py launcher makes them the default.
        if ($version.Major -ne 3 -or $version.Minor -lt 11 -or $version.Minor -gt 14) {
            return $null
        }

        [PSCustomObject]@{
            Path = $actualPath.Trim()
            Version = $versionText.Trim()
        }
    }
    catch {
        return $null
    }
}

function Resolve-CompatibleSystemPython {
    param([string]$Requested)

    $candidates = New-Object System.Collections.Generic.List[string]

    if ($Requested) {
        $candidates.Add($Requested)
    }

    if ($env:pythonLocation) {
        $candidates.Add((Join-Path $env:pythonLocation "python.exe"))
    }

    if ($env:CONDA_PREFIX) {
        $candidates.Add((Join-Path $env:CONDA_PREFIX "python.exe"))
    }

    try {
        $py = Get-Command "py.exe" -ErrorAction Stop
        foreach ($minor in @(12, 13, 11, 14)) {
            $resolved = & $py.Source "-3.$minor" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $candidates.Add(([string]$resolved).Trim())
            }
        }
    }
    catch {
        # Python launcher is optional.
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
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
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

        $compatible = Get-CompatiblePython $candidate
        if ($compatible) {
            return $compatible
        }
    }

    return $null
}

function Resolve-CondaExecutable {
    $candidates = New-Object System.Collections.Generic.List[string]

    if ($env:CONDA_EXE) {
        $candidates.Add($env:CONDA_EXE)
    }

    foreach ($path in @(
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        "G:\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe"
    )) {
        if ($path) {
            $candidates.Add($path)
        }
    }

    try {
        $command = Get-Command "conda.exe" -ErrorAction Stop
        if ($command.Source) {
            $candidates.Add($command.Source)
        }
    }
    catch {
        # Continue through explicit paths.
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

New-Item -ItemType Directory -Force -Path $workRoot | Out-Null

$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$condaPython = Join-Path $condaEnvRoot "python.exe"
$pythonExe = $null

$existingVenv = Get-CompatiblePython $venvPython
if ($existingVenv) {
    $pythonExe = $existingVenv.Path
    Write-Host "Reusing isolated Python environment: $venvRoot"
}
else {
    $existingConda = Get-CompatiblePython $condaPython
    if ($existingConda) {
        $pythonExe = $existingConda.Path
        Write-Host "Reusing isolated Conda environment: $condaEnvRoot"
    }
}

if (-not $pythonExe) {
    $systemPython = Resolve-CompatibleSystemPython -Requested $Python

    if ($systemPython) {
        Write-Host "Selected Python: $($systemPython.Path)"
        Write-Host "Python version: Python $($systemPython.Version)"
        Write-Host "Creating isolated Python environment: $venvRoot"
        & $systemPython.Path -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create research virtual environment with '$($systemPython.Path)'."
        }
        $pythonExe = $venvPython
    }
    else {
        $condaExe = Resolve-CondaExecutable
        if (-not $condaExe) {
            throw @"
No compatible CPython 3.11-3.14 interpreter was found automatically, and no
Conda executable was available to create an isolated Python 3.12 environment.

The Microsoft Store 'python.exe' execution alias does not count as an installed
Python runtime. This checkpoint does not require changing that alias.

If a compatible interpreter exists in a non-standard location, rerun with:
  run-windows-ml-checkpoint.cmd -Python "<full-path-to-python.exe>"
"@
        }

        Write-Host "No compatible system Python 3.11-3.14 found."
        Write-Host "Using Conda to create isolated Python 3.12 environment:"
        Write-Host "  Conda: $condaExe"
        Write-Host "  Environment: $condaEnvRoot"
        & $condaExe create --yes --prefix $condaEnvRoot "python=3.12" pip
        if ($LASTEXITCODE -ne 0) {
            throw "Conda failed to create the isolated Python 3.12 research environment."
        }

        $createdConda = Get-CompatiblePython $condaPython
        if (-not $createdConda) {
            throw "Conda reported success but the isolated Python 3.12 interpreter is unavailable."
        }
        $pythonExe = $createdConda.Path
    }
}

$selected = Get-CompatiblePython $pythonExe
if (-not $selected) {
    throw "The isolated checkpoint environment is not using a supported CPython 3.11-3.14 interpreter."
}
Write-Host "Checkpoint Python: $($selected.Path)"
Write-Host "Checkpoint Python version: Python $($selected.Version)"

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
