#Requires -Version 5.1
<#
One-command isolated v0.4 Composite Split QA launcher for Luna datasets.
Uses an immutable GitHub Actions artifact from the accepted #106 Portable build.
No gh, Python, Conda or system installation. Never alters the old Portable.
The selected dataset is opened by the user in the application itself.
#>
[CmdletBinding()]
param(
    [string]$Root = 'G:\FaceLoRA-Luna-v04-QA',
    [string]$LocalPackageZip = '',
    [switch]$PrepareOnly,
    [switch]$CiFixture
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$run = 42382490831
$artifact = 13578236484
$overlayArtifact = 13577229815
$modelSha = '7a83be63e6583ec5800fa0762e219b65b4b9f1721c4d210bfe2f16c0478832bb'
$fullUrl = "https://nightly.link/JInghoeg/face-lora-dataset-selector/actions/artifacts/$artifact.zip"
$overlayUrl = "https://nightly.link/JInghoeg/face-lora-dataset-selector/actions/artifacts/$overlayArtifact.zip"

function Require([bool]$Good, [string]$Why) {
    if (-not $Good) { throw $Why }
}
function Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Check-Zip([string]$Path) {
    Require (Test-Path -LiteralPath $Path -PathType Leaf) "Missing ZIP: $Path"
    $file = [IO.File]::OpenRead($Path)
    try {
        Require ($file.Length -gt 100) "Downloaded file is too small to be a ZIP: $Path"
        $a = $file.ReadByte(); $b = $file.ReadByte()
        Require ($a -eq 0x50 -and $b -eq 0x4B) "Download is not a ZIP (possibly a rate-limit/error response): $Path"
    } finally { $file.Dispose() }
}
function Fetch-Zip([string]$Uri, [string]$Path) {
    Write-Host "Downloading a verified Windows QA artifact to G: ..."
    $tempPart = "$Path.part"
    if (Test-Path -LiteralPath $tempPart) { Remove-Item -LiteralPath $tempPart -Force }
    Invoke-WebRequest -Uri $Uri -OutFile $tempPart -MaximumRedirection 12 -ErrorAction Stop
    Check-Zip $tempPart
    Move-Item -LiteralPath $tempPart -Destination $Path -Force
}
function Check-Model([string]$AppDir) {
    $exe = Join-Path $AppDir 'Face LoRA Dataset Selector.exe'
    $model = Join-Path $AppDir '_internal\models\ediffiqa_t.onnx'
    Require (Test-Path -LiteralPath $exe -PathType Leaf) "Packaged application EXE missing."
    Require (Test-Path -LiteralPath $model -PathType Leaf) "Packaged eDifFIQA model missing."
    Require ((Sha256 $model) -eq $modelSha) "SHA-pinned eDifFIQA model mismatch."
    return $exe
}
function Matches-RuntimeManifest([string]$AppDir, [string]$Manifest) {
    if (-not (Test-Path -LiteralPath $AppDir -PathType Container)) { return $false }
    foreach ($line in Get-Content -LiteralPath $Manifest) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^([A-Fa-f0-9]{64})  ([0-9]+)  (.+)$') { return $false }
        $sha = $Matches[1].ToLowerInvariant()
        $length = [long]$Matches[2]
        $rel = $Matches[3]
        if ([IO.Path]::IsPathRooted($rel) -or $rel.Contains('..')) { return $false }
        $path = Join-Path $AppDir $rel
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
        if ((Get-Item -LiteralPath $path).Length -ne $length) { return $false }
        if ((Sha256 $path) -ne $sha) { return $false }
    }
    return $true
}
function Expand-CheckedZip([string]$Zip, [string]$Destination) {
    Check-Zip $Zip
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Expand-Archive -LiteralPath $Zip -DestinationPath $Destination -Force
}

$target = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$systemDrive = [IO.Path]::GetPathRoot($env:SystemRoot)
Require ($target.Length -gt 12 -and $target -ne [IO.Path]::GetPathRoot($target).TrimEnd('\')) 'Unsafe QA root.'
if (-not ($CiFixture -and $env:GITHUB_ACTIONS -eq 'true')) {
    Require ($target.StartsWith('G:\',[StringComparison]::OrdinalIgnoreCase)) 'This workstation QA must remain on G:.'
    Require (-not [IO.Path]::GetPathRoot($target).Equals($systemDrive,[StringComparison]::OrdinalIgnoreCase)) 'Refusing system-drive QA.'
}
$sentinel = Join-Path $target '.face-lora-luna-qa'
if (Test-Path -LiteralPath $target -PathType Container) {
    $contents = @(Get-ChildItem -LiteralPath $target -Force -ErrorAction SilentlyContinue)
    Require ($contents.Count -eq 0 -or (Test-Path -LiteralPath $sentinel -PathType Leaf)) "Existing folder isn't managed by this launcher: $target"
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
if (-not (Test-Path -LiteralPath $sentinel)) {
    "Managed Luna Composite QA only | RunId=$run" | Set-Content -LiteralPath $sentinel -Encoding UTF8
}
$work = Join-Path $target '.work'
$logs = Join-Path $target 'reports'
$app = Join-Path $target 'app'
$info = Join-Path $target 'QA_INFO.json'
New-Item -ItemType Directory -Force -Path $work,$logs | Out-Null
$temp = Join-Path $work 'tmp'
New-Item -ItemType Directory -Force -Path $temp | Out-Null
$oldTemp = $env:TEMP; $oldTmp = $env:TMP
$env:TEMP = $temp; $env:TMP = $temp
$report = [ordered]@{
    kind = 'isolated-luna-composite-qa'
    run_id = $run
    artifact_id = $artifact
    status = 'preparing'
    mode = $null
    app = $app
    executable = $null
    model_sha256 = $modelSha
    error = $null
    generated_at = $null
}
try {
    $prepared = $false
    if (Test-Path -LiteralPath (Join-Path $app '.luna-artifact-id') -PathType Leaf) {
        $installed = (Get-Content -LiteralPath (Join-Path $app '.luna-artifact-id') -Raw).Trim()
        if ($installed -eq [string]$artifact) {
            $exe = Check-Model $app
            $report.mode = 'cached'
            $prepared = $true
        }
    }
    if (-not $prepared) {
        $stage = Join-Path $work 'candidate'
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Force -Recurse }
        $usedOverlay = $false

        # Reuse the QA Portable's verified runtime contract, but COPY it.
        # Never move/overwrite the pre-existing QA runtime or v0.3.1 installation.
        $cache = 'G:\FaceLoRA-QA\runtime\Face-LoRA-Dataset-Selector'
        if (-not $LocalPackageZip -and (Test-Path -LiteralPath $cache -PathType Container)) {
            try {
                $overlayZip = Join-Path $work 'overlay.zip'
                if (-not (Test-Path -LiteralPath $overlayZip)) { Fetch-Zip $overlayUrl $overlayZip }
                $over = Join-Path $work 'overlay'
                Expand-CheckedZip $overlayZip $over
                $manifest = Get-ChildItem -LiteralPath $over -Recurse -File -Filter 'qa-runtime-manifest.txt' | Select-Object -First 1
                if ($null -ne $manifest -and (Matches-RuntimeManifest $cache $manifest.FullName)) {
                    Write-Host 'Compatible QA runtime verified; copying it to the isolated folder.'
                    Copy-Item -LiteralPath $cache -Destination $stage -Recurse
                    $overlayRoot = $manifest.Directory.FullName
                    Copy-Item -Path (Join-Path $overlayRoot '*') -Destination $stage -Recurse -Force
                    $exe = Check-Model $stage
                    $report.mode = 'overlay-from-copied-cache'
                    $usedOverlay = $true
                }
            } catch {
                Write-Warning "QA cache overlay not usable, falling back to full Portable: $($_.Exception.Message)"
                if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
            }
        }

        if (-not $usedOverlay) {
            $package = $LocalPackageZip
            if (-not $package) {
                $outerZip = Join-Path $work 'artifact.zip'
                if (-not (Test-Path -LiteralPath $outerZip)) { Fetch-Zip $fullUrl $outerZip }
                $outer = Join-Path $work 'artifact'
                Expand-CheckedZip $outerZip $outer
                $item = Get-ChildItem -LiteralPath $outer -Recurse -File -Filter '*Portable.zip' | Select-Object -First 1
                Require ($null -ne $item) 'The GitHub artifact contained no Portable ZIP.'
                $package = $item.FullName
            }
            $package = [IO.Path]::GetFullPath($package)
            Check-Zip $package
            $checksumPath = "$package.sha256"
            Require (Test-Path -LiteralPath $checksumPath -PathType Leaf) "Portable SHA-256 sidecar missing: $checksumPath"
            $expectedHash = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
            Require ($expectedHash -match '^[a-f0-9]{64}$') 'Portable SHA-256 sidecar invalid.'
            Require ((Sha256 $package) -eq $expectedHash) 'Portable ZIP failed SHA-256.'
            $unpack = Join-Path $work 'unpack'
            Expand-CheckedZip $package $unpack
            $found = Get-ChildItem -LiteralPath $unpack -Recurse -File -Filter 'Face LoRA Dataset Selector.exe' | Select-Object -First 1
            Require ($null -ne $found) 'Portable ZIP did not contain the app EXE.'
            $sourceApp = $found.Directory.FullName
            Move-Item -LiteralPath $sourceApp -Destination $stage
            $exe = Check-Model $stage
            $report.mode = 'full-verified-portable'
        }

        # In CI this is a real packaged EXE smoke; never claims interactive HUMAN PASS.
        $test = Start-Process -FilePath $exe -ArgumentList '--self-test' -WorkingDirectory $stage -PassThru -Wait
        Require ($test.ExitCode -eq 0) "Packaged self-test failed: exit $($test.ExitCode)"
        Require (-not (Test-Path -LiteralPath $app -PathType Container)) "Refusing to replace an existing application folder: $app"
        "$artifact" | Set-Content -LiteralPath (Join-Path $stage '.luna-artifact-id') -Encoding UTF8
        Move-Item -LiteralPath $stage -Destination $app
        $exe = Check-Model $app
    }
    $report.executable = $exe
    # Once the verified application is staged, release the big temporary ZIPs.
    # Cleanup is strictly confined to this sentinel-owned G: work directory.
    foreach ($piece in @('artifact', 'unpack', 'overlay', 'artifact.zip', 'overlay.zip')) {
        $scratch = Join-Path $work $piece
        if (Test-Path -LiteralPath $scratch) {
            Remove-Item -LiteralPath $scratch -Recurse -Force
        }
    }
    if ($PrepareOnly) {
        $report.status = 'prepared'
        Write-Host "Isolated v0.4 QA prepared: $exe"
    } else {
        Write-Host "Launching isolated Luna Composite Split QA: $exe"
        $p = Start-Process -FilePath $exe -WorkingDirectory $app -PassThru
        Start-Sleep -Seconds 4
        if ($p.HasExited -and $p.ExitCode -ne 0) {
            throw "GUI startup failed with exit code $($p.ExitCode). Check startup-error.txt in the isolated app folder."
        }
        $report.status = 'launched'
        $report['process_id'] = $p.Id
    }
} catch {
    $report.status = 'failed'
    $report.error = $_.Exception.Message
    Write-Host "QA deployment failed: $($report.error)" -ForegroundColor Red
    throw
} finally {
    $report.generated_at = (Get-Date).ToUniversalTime().ToString('o')
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $info -Encoding UTF8
    $env:TEMP = $oldTemp; $env:TMP = $oldTmp
}
