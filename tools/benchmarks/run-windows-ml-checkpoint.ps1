param(
    [string]$Python = "python",
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

New-Item -ItemType Directory -Force -Path $workRoot | Out-Null

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating isolated Python environment: $venvRoot"
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create research virtual environment with '$Python'."
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
        Write-Host "Windows ML Python packages are present but the Windows App SDK runtime/bootstrap is not usable."
        Write-Host "Do not install anything automatically yet; keep this report as deployment evidence."
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
