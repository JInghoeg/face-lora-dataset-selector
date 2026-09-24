param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,

    [Parameter(Mandatory = $true)]
    [string]$OverlayRoot,

    [Parameter(Mandatory = $true)]
    [string]$FullZip,

    [Parameter(Mandatory = $true)]
    [string]$FullChecksum
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$portable = [System.IO.Path]::GetFullPath($PortableRoot)
$overlay = [System.IO.Path]::GetFullPath($OverlayRoot)
$zip = [System.IO.Path]::GetFullPath($FullZip)
$checksum = [System.IO.Path]::GetFullPath($FullChecksum)

foreach ($path in @($repo, $portable, $overlay)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Required directory missing: $path"
    }
}
foreach ($path in @($zip, $checksum)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file missing: $path"
    }
}

$qaHelper = Join-Path $repo "tools\qa-portable.ps1"
if (-not (Test-Path -LiteralPath $qaHelper -PathType Leaf)) {
    throw "QA helper missing: $qaHelper"
}

$work = Join-Path $env:RUNNER_TEMP "face-lora-qa-prepare-roundtrip"
$fakeBin = Join-Path $work "bin"
$qaRoot = Join-Path $work "FaceLoRA-QA"
$countFile = Join-Path $work "full-download-count.txt"

if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $fakeBin | Out-Null

$fakePs1 = Join-Path $fakeBin "gh.ps1"
@'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($args.Count -ge 2 -and $args[0] -eq "run" -and $args[1] -eq "view") {
    [pscustomobject]@{
        databaseId = 123456
        headSha = "qa-helper-smoke"
        headBranch = "qa-helper-smoke"
        status = "completed"
        conclusion = "success"
        url = "https://example.invalid/qa-helper-smoke"
    } | ConvertTo-Json -Compress
    exit 0
}

if ($args.Count -ge 2 -and $args[0] -eq "run" -and $args[1] -eq "download") {
    $nameIndex = [Array]::IndexOf($args, "--name")
    $dirIndex = [Array]::IndexOf($args, "--dir")
    if ($nameIndex -lt 0 -or $dirIndex -lt 0) {
        throw "Fake gh download missing --name/--dir."
    }

    $name = $args[$nameIndex + 1]
    $destination = $args[$dirIndex + 1]
    New-Item -ItemType Directory -Force -Path $destination | Out-Null

    if ($name -eq "Face-LoRA-Dataset-Selector-Windows-x64-QA-Overlay") {
        Copy-Item -Path (Join-Path $env:QA_FAKE_OVERLAY "*") -Destination $destination -Recurse -Force
        exit 0
    }

    if ($name -eq "Face-LoRA-Dataset-Selector-Windows-x64-Portable") {
        Add-Content -LiteralPath $env:QA_FAKE_FULL_COUNT -Value "download"
        Copy-Item -LiteralPath $env:QA_FAKE_FULL_ZIP -Destination $destination -Force
        Copy-Item -LiteralPath $env:QA_FAKE_FULL_SUM -Destination $destination -Force
        exit 0
    }

    throw "Unexpected fake artifact request: $name"
}

throw "Unexpected fake gh arguments: $($args -join ' ')"
'@ | Set-Content -LiteralPath $fakePs1 -Encoding UTF8

$fakeCmd = Join-Path $fakeBin "gh.cmd"
@'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" %*
exit /b %errorlevel%
'@ | Set-Content -LiteralPath $fakeCmd -Encoding ASCII

$oldPath = $env:PATH
$env:PATH = "$fakeBin;$oldPath"
$env:QA_FAKE_OVERLAY = $overlay
$env:QA_FAKE_FULL_ZIP = $zip
$env:QA_FAKE_FULL_SUM = $checksum
$env:QA_FAKE_FULL_COUNT = $countFile

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $qaHelper -Action Prepare -Root $qaRoot -RunId 123456
    if ($LASTEXITCODE -ne 0) {
        throw "First QA Prepare failed."
    }

    $info = Get-Content -LiteralPath (Join-Path $qaRoot "current\QA_INFO.txt") -Raw
    if ($info -notmatch '(?m)^Mode=full$') {
        throw "First QA Prepare did not use full mode."
    }

    $runtimeRoot = Join-Path $qaRoot "runtime"
    $preparedPortable = Join-Path $runtimeRoot "Face-LoRA-Dataset-Selector"
    $preparedExe = Join-Path $preparedPortable "Face LoRA Dataset Selector.exe"
    $modelCache = Join-Path $runtimeRoot "_FaceLoRA_ModelCache\smoke"
    New-Item -ItemType Directory -Force -Path $modelCache | Out-Null
    $modelMarker = Join-Path $modelCache "model.onnx"
    "keep-model-cache" | Set-Content -LiteralPath $modelMarker -Encoding ASCII

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $qaHelper -Action Prepare -Root $qaRoot -RunId 123456
    if ($LASTEXITCODE -ne 0) {
        throw "Second QA Prepare failed."
    }

    $info = Get-Content -LiteralPath (Join-Path $qaRoot "current\QA_INFO.txt") -Raw
    if ($info -notmatch '(?m)^Mode=overlay$') {
        throw "Second QA Prepare did not use overlay mode."
    }

    $fullRequests = @(
        Get-Content -LiteralPath $countFile -ErrorAction SilentlyContinue
    )
    if ($fullRequests.Count -ne 1) {
        throw "Expected exactly one full artifact request, got $($fullRequests.Count)."
    }

    if (-not (Test-Path -LiteralPath $modelMarker -PathType Leaf)) {
        throw "Model cache was not preserved across overlay Prepare."
    }

    $sourceExe = Join-Path $portable "Face LoRA Dataset Selector.exe"
    $sourceHash = (Get-FileHash -LiteralPath $sourceExe -Algorithm SHA256).Hash
    $preparedHash = (Get-FileHash -LiteralPath $preparedExe -Algorithm SHA256).Hash
    if ($sourceHash -ne $preparedHash) {
        throw "Overlay-prepared EXE does not match the built candidate."
    }

    $p = Start-Process -FilePath $preparedExe -ArgumentList "--self-test" -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        throw "Overlay-prepared Portable self-test failed with exit code $($p.ExitCode)."
    }

    Write-Host "QA Prepare roundtrip OK: full -> overlay; model cache preserved; full downloaded once."
}
finally {
    $env:PATH = $oldPath
    Remove-Item Env:QA_FAKE_OVERLAY -ErrorAction SilentlyContinue
    Remove-Item Env:QA_FAKE_FULL_ZIP -ErrorAction SilentlyContinue
    Remove-Item Env:QA_FAKE_FULL_SUM -ErrorAction SilentlyContinue
    Remove-Item Env:QA_FAKE_FULL_COUNT -ErrorAction SilentlyContinue
}
