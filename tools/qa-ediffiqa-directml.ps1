#Requires -Version 5.1
<#
One-command, non-destructive RTX checkpoint handoff.
Default: reuse the existing G: DirectML checkpoint, download only the tiny
official eDifFIQA overlay from the exact PR-head successful CI run, and perform
one profiled GPU-compute bounded probe (CPU shape helpers audited). No Python/CUDA/Conda installation.
CI: -PackageZip <CI-built zip> -PrepareOnly validates offline staging.
#>
[CmdletBinding()]
param(
    [string]$CheckpointRoot = 'G:\ComfyUI-aki\FaceLoRA-DirectML-GPU-Debug\checkpoint',
    [string]$Repo = 'JInghoeg/face-lora-dataset-selector',
    [string]$Branch = 'research/ediffiqa-directml-batch1',
    [long]$RunId = 0,
    [string]$PackageZip = '',
    [switch]$PrepareOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ExpectedModelSha = '7a83be63e6583ec5800fa0762e219b65b4b9f1721c4d210bfe2f16c0478832bb'
$ArtifactName = 'FaceLoRA-eDifFIQA-DirectML-Final-Probe'
$InnerZipName = 'FaceLoRA-eDifFIQA-Candidate-Probe.zip'
$ProbeExeName = 'Face LoRA eDifFIQA Candidate Probe.exe'
$CheckpointExeName = 'Face LoRA DirectML Checkpoint.exe'
$ReportName = 'qa-ediffiqa-last-run.json'
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$report = [ordered]@{
    schema_version = 1
    kind = 'ediffiqa-one-command-target-qa'
    status = 'starting'
    target_gpu_verified = $false
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    artifact_run_id = $null
    artifact_commit = $null
    deployed_model_sha256 = $null
    probe_report = $null
    probe_exit_code = $null
    gpu_compute_verified = $false
    profile_summary = $null
    probe_error = $null
    native_error_lines = @()
    failure = $null
}
$targetDir = $null
$reportPath = $null

function Assert-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit code $LASTEXITCODE)." }
}

function Assert-CorrectFileHash([string]$File, [string]$Expected) {
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
        throw "Expected file missing: $File"
    }
    $got = (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($got -ne $Expected.ToLowerInvariant()) {
        throw "SHA-256 mismatch: $File (expected $Expected, actual $got)"
    }
}

function Find-CheckpointRuntime([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Existing DirectML checkpoint folder was not found: $Root. No reinstall will be attempted."
    }
    $files = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Filter $CheckpointExeName -ErrorAction Stop)
    if ($files.Count -ne 1) {
        throw "Expected exactly one existing DirectML Checkpoint EXE under $Root; found $($files.Count)."
    }
    $dir = $files[0].DirectoryName
    if (-not (Test-Path -LiteralPath (Join-Path $dir '_internal') -PathType Container)) {
        throw "The existing checkpoint's reusable PyInstaller _internal runtime is missing: $dir"
    }
    return $dir
}

function Get-ExactSuccessfulRun([string]$RepoName, [string]$Ref) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'GitHub CLI is unavailable; automated Artifact retrieval cannot run. Do not download or unpack it manually.'
    }
    $refApi = "repos/$RepoName/git/ref/heads/$Ref"
    $currentHead = ((& gh api $refApi --jq '.object.sha') | Out-String).Trim()
    Assert-ExitCode 'Resolve exact branch head'
    if ($currentHead -notmatch '^[0-9a-f]{40}$') { throw 'Could not verify the current GitHub branch SHA.' }
    if ($RunId -gt 0) {
        $selected = (& gh run view $RunId --repo $RepoName --json databaseId,headSha,headBranch,status,conclusion | Out-String) | ConvertFrom-Json
        Assert-ExitCode 'Inspect requested run'
    } else {
        $runJson = (& gh run list --repo $RepoName --workflow 'ediffiqa-directml-probe.yml' --branch $Ref --status success --limit 20 --json databaseId,headSha,headBranch,status,conclusion | Out-String)
        Assert-ExitCode 'Find matching successful final probe run'
        $matches = @($runJson | ConvertFrom-Json) | Where-Object {
            $_.headSha -eq $currentHead -and $_.status -eq 'completed' -and $_.conclusion -eq 'success'
        }
        if (@($matches).Count -lt 1) {
            throw "No successful Final Probe artifact for current head $currentHead. Finish CI before workstation QA."
        }
        $selected = @($matches)[0]
    }
    if ($selected.headSha -ne $currentHead -or $selected.headBranch -ne $Ref -or
        $selected.status -ne 'completed' -or $selected.conclusion -ne 'success') {
        throw "Selected run is not a successful build of the exact current branch head $currentHead."
    }
    return $selected
}

function Verify-Package([string]$Unpacked) {
    $manifestPath = Join-Path $Unpacked 'payload.sha256.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw 'Artifact is missing its CI-generated payload.sha256.json manifest.'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1 -or @($manifest.files).Count -ne 3) {
        throw 'Unexpected final probe checksum manifest schema or file count.'
    }
    $expectedNames = @(
        $ProbeExeName,
        'ediffiqa-candidates/ediffiqa_t_upstream.onnx',
        'ediffiqa-graph-lab.json'
    )
    $seenNames = @()
    foreach ($entry in @($manifest.files)) {
        $relative = [string]$entry.path
        $seenNames += $relative
        if ($expectedNames -notcontains $relative -or [IO.Path]::IsPathRooted($relative) -or
            $relative.Contains('..')) { throw "Unexpected/unsafe package entry: $relative" }
        $file = Join-Path $Unpacked $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        Assert-CorrectFileHash $file ([string]$entry.sha256)
    }
    if (@($seenNames | Sort-Object -Unique).Count -ne 3) { throw 'Duplicate or missing manifest entries.' }
    $model = Join-Path $Unpacked 'ediffiqa-candidates\ediffiqa_t_upstream.onnx'
    Assert-CorrectFileHash $model $ExpectedModelSha
}

try {
    $root = [IO.Path]::GetFullPath($CheckpointRoot)
    $systemDrive = [IO.Path]::GetPathRoot($env:SystemRoot)
    if ([IO.Path]::GetPathRoot($root).TrimEnd('\') -eq $systemDrive.TrimEnd('\')) {
        throw "System-drive downloads/staging are prohibited: $root"
    }
    $targetDir = Find-CheckpointRuntime $root
    $reportPath = Join-Path $targetDir $ReportName
    $stage = Join-Path $targetDir '.qa-ediffiqa'
    $sentinel = Join-Path $stage '.managed-by-qa-ediffiqa'
    if ((Test-Path -LiteralPath $stage) -and -not (Test-Path -LiteralPath $sentinel)) {
        throw "Refusing to touch unmanaged staging directory: $stage"
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    if (-not (Test-Path -LiteralPath $sentinel)) {
        Set-Content -LiteralPath $sentinel -Value 'Managed only by tools/qa-ediffiqa-directml.ps1'
    }
    foreach ($name in @('download', 'expanded', 'tmp')) {
        $p = Join-Path $stage $name
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
    $env:TEMP = Join-Path $stage 'tmp'
    $env:TMP = $env:TEMP
    $download = Join-Path $stage 'download'
    $expanded = Join-Path $stage 'expanded'
    $packagePath = Join-Path $download $InnerZipName

    if (-not [string]::IsNullOrWhiteSpace($PackageZip)) {
        if (-not (Test-Path -LiteralPath $PackageZip -PathType Leaf)) { throw "Missing CI fixture ZIP: $PackageZip" }
        Copy-Item -LiteralPath $PackageZip -Destination $packagePath
        $report.artifact_commit = 'CI_LOCAL_PACKAGE_VALIDATION_ONLY'
    } else {
        $selected = Get-ExactSuccessfulRun $Repo $Branch
        $report.artifact_run_id = [long]$selected.databaseId
        $report.artifact_commit = [string]$selected.headSha
        Write-Host "Reusing existing checkpoint runtime; downloading small verified overlay from run $($selected.databaseId)..."
        & gh run download $selected.databaseId --repo $Repo --name $ArtifactName --dir $download
        Assert-ExitCode "Download $ArtifactName"
    }
    if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
        throw "The selected Artifact does not contain exactly $InnerZipName."
    }
    Expand-Archive -LiteralPath $packagePath -DestinationPath $expanded -Force
    Verify-Package $expanded

    $destModelDir = Join-Path $targetDir 'ediffiqa-candidates'
    New-Item -ItemType Directory -Path $destModelDir -Force | Out-Null
    $modelSrc = Join-Path $expanded 'ediffiqa-candidates\ediffiqa_t_upstream.onnx'
    $modelDst = Join-Path $destModelDir 'ediffiqa_t_upstream.onnx'
    if (-not (Test-Path -LiteralPath $modelDst -PathType Leaf) -or
        (Get-FileHash -LiteralPath $modelDst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedModelSha) {
        Copy-Item -LiteralPath $modelSrc -Destination $modelDst -Force
    }
    Assert-CorrectFileHash $modelDst $ExpectedModelSha
    $report.deployed_model_sha256 = $ExpectedModelSha

    $probeSrc = Join-Path $expanded $ProbeExeName
    $probeDst = Join-Path $targetDir $ProbeExeName
    $probeHash = (Get-FileHash -LiteralPath $probeSrc -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not (Test-Path -LiteralPath $probeDst -PathType Leaf) -or
        (Get-FileHash -LiteralPath $probeDst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $probeHash) {
        Copy-Item -LiteralPath $probeSrc -Destination $probeDst -Force
    }
    Assert-CorrectFileHash $probeDst $probeHash
    $report.status = 'prepared'

    if ($PrepareOnly) {
        Write-Host 'CI/offline preparation PASS. No target GPU result was claimed.'
    } else {
        Write-Host 'Running one profiled eDifFIQA-T DirectML test (Python CPU-only retry disabled; CPU shape helpers audited)...'
        $started = (Get-Date).ToUniversalTime()
        $p = Start-Process -FilePath $probeDst -ArgumentList @('--headless') -WorkingDirectory $targetDir -PassThru
        if (-not $p.WaitForExit(120000)) {
            & taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null
            $report.status = 'timeout'
            $report.failure = 'Probe watchdog exceeded 120 seconds.'
        } else {
            $report.probe_exit_code = $p.ExitCode
        }
        $resultFolder = Join-Path $targetDir 'ediffiqa-candidate-results'
        $candidateReports = @(
            Get-ChildItem -LiteralPath $resultFolder -Recurse -File -Filter 'ediffiqa-directml-candidates.json' -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTimeUtc -ge $started.AddSeconds(-3) } |
            Sort-Object LastWriteTimeUtc -Descending
        )
        if ($candidateReports.Count -gt 0) {
            $rawPath = $candidateReports[0].FullName
            $report.probe_report = $rawPath
            $details = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
            if (@($details.probes).Count -ne 1 -or $details.probes[0].candidate -ne 'upstream_current') {
                throw 'Probe report is not the required single official production-model test.'
            }
            $row = $details.probes[0]
            $gpuProof = ($null -ne $row.PSObject.Properties['gpu_compute_verified'] -and
                $row.gpu_compute_verified -eq $true)
            $report.gpu_compute_verified = $gpuProof
            if ($null -ne $row.PSObject.Properties['profile_summary']) {
                $report.profile_summary = $row.profile_summary
            }
            if ($null -ne $row.PSObject.Properties['error']) {
                $report.probe_error = $row.error
            }
            if ($null -ne $row.PSObject.Properties['log'] -and
                (Test-Path -LiteralPath $row.log -PathType Leaf)) {
                # Windows native redirected output can contain UTF-16 null bytes.
                # Only return relevant final native lines, not huge ORT verbose logs.
                $tail = @(Get-Content -LiteralPath $row.log -Tail 100 -ErrorAction SilentlyContinue)
                $report.native_error_lines = @(
                    $tail |
                    ForEach-Object { ($_ -replace ([string][char]0), '') -replace '\x1b\[[0-9;]*m', '' } |
                    Where-Object { $_ -match 'Error|Exception|\[E:|CPU EP|DmlExecutionProvider|0x[0-9A-Fa-f]+' } |
                    Select-Object -Last 14
                )
            }
            if ($details.winner -eq 'upstream_current' -and $row.status -eq 'pass' -and
                $row.model_sha256 -eq $ExpectedModelSha -and
                @($row.session_providers) -contains 'DmlExecutionProvider' -and
                $gpuProof -and
                $null -ne $report.profile_summary -and
                $report.profile_summary.dml_compute_kernel_events -gt 0 -and
                @($report.profile_summary.cpu_non_helper_ops).Count -eq 0 -and
                $report.probe_exit_code -eq 0) {
                $report.status = 'strict_directml_pass'
                $report.target_gpu_verified = $true
            } else {
                $report.status = 'strict_directml_fail'
                $report.failure = if ($null -ne $row.PSObject.Properties['error']) {
                    [string]$row.error.message
                } else {
                    'No proven DML compute kernel or unexpected CPU compute placement. Inspect the embedded profile_summary.'
                }
            }
        } elseif ($report.status -ne 'timeout') {
            $report.status = 'no_probe_report'
            $report.failure = 'No recent probe result generated; inspect checkpoint logs.'
        }
    }
} catch {
    $report.status = 'automation_error'
    $report.failure = $_.Exception.Message
    Write-Host "QA automation stopped safely: $($report.failure)" -ForegroundColor Red
} finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    if ($null -ne $reportPath) {
        $report.generated_at = (Get-Date).ToUniversalTime().ToString('o')
        $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
        Write-Host "Single QA report: $reportPath"
    }
}
if ($report.status -eq 'strict_directml_pass') {
    Write-Host 'STRICT DIRECTML PASS — return the single QA report above.' -ForegroundColor Green
} elseif ($report.status -eq 'prepared') {
    Write-Host 'PREPARE PASS (CI fixture only; no GPU proof).' -ForegroundColor Yellow
} else {
    throw "QA did not pass ($($report.status)): $($report.failure). Return the single QA report above."
}
