#Requires -Version 5.1
<#
One-command user-data-preserving unified v0.4 human-QA build.
All new payload/temp/app files live under a dedicated G: root. Old v0.3.1 is read-only.
Separate DirectML Portable artifact, not the CPU-only #108 candidate.
#>
[CmdletBinding()]
param(
  [string]$Root = 'G:\FaceLoRA-v04-Unified-QA',
  [string]$OldRoot = '',
  [string]$LocalPackageZip = '',
  [string]$ArtifactId = '',
  [string]$ArtifactCommit = '',
  [switch]$PrepareOnly,
  [switch]$CiFixture
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$artifactId = $ArtifactId
$artifactSha = $ArtifactCommit
$modelSha = '7a83be63e6583ec5800fa0762e219b65b4b9f1721c4d210bfe2f16c0478832bb'
$packageUrl = "https://nightly.link/JInghoeg/face-lora-dataset-selector/actions/artifacts/$artifactId.zip"
function Assert([bool]$Ok,[string]$Message) { if (-not $Ok) { throw $Message } }
function HashFile([string]$File) { (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-OldDataFiles([string]$Base) {
  @(
    Join-Path $Base '_userdata\cache'
    Join-Path $Base 'cache'
  ) | ForEach-Object {
    if (Test-Path -LiteralPath $_ -PathType Container) {
      Get-ChildItem -LiteralPath $_ -File -Filter '*.json' -ErrorAction SilentlyContinue
    }
  }
}
function IsOldRoot([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
  $exe = Join-Path $Path 'Face LoRA Dataset Selector.exe'
  if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { return $false }
  return @(Get-OldDataFiles $Path).Count -gt 0
}
function Find-OldRoot {
  if ($OldRoot) {
    $candidate = [IO.Path]::GetFullPath($OldRoot).TrimEnd('\')
    Assert (IsOldRoot $candidate) "OldRoot must contain the v0.3.1 EXE and saved cache JSON: $candidate"
    return $candidate
  }
  $preferred = @(
    'G:\Face-LoRA-Dataset-Selector-v0.3.1',
    'G:\Face-LoRA-Dataset-Selector',
    'G:\Face LoRA Dataset Selector',
    'G:\FaceLoRA\Face-LoRA-Dataset-Selector-v0.3.1',
    'G:\FaceLoRA\Face-LoRA-Dataset-Selector'
  )
  foreach ($p in $preferred) { if (IsOldRoot $p) { return $p } }

  # Bounded directory discovery: G: root and two levels down. Do not recursively crawl datasets.
  $found = [collections.generic.list[string]]::new()
  $candidates = @(Get-ChildItem -LiteralPath 'G:\' -Directory -ErrorAction SilentlyContinue)
  foreach ($first in $candidates) {
    if ($first.Name -match '^Face-LoRA-Dataset-Selector(?:-v0\.3\.1)?$' -and (IsOldRoot $first.FullName)) {
      $found.Add($first.FullName)
    }
    if ($first.Name -match '^(Windows|Program Files|System Volume Information|\$RECYCLE.BIN)$') { continue }
    $secondLevel = @(Get-ChildItem -LiteralPath $first.FullName -Directory -ErrorAction SilentlyContinue)
    foreach ($second in $secondLevel) {
      if ($second.Name -match '^Face-LoRA-Dataset-Selector(?:-v0\.3\.1)?$' -and (IsOldRoot $second.FullName)) {
        $found.Add($second.FullName)
      }
      if ($second.Name -match '^FaceLoRA|^(apps?|tools?|portable|releases?|software|lora|models?)$') {
        foreach ($third in @(Get-ChildItem -LiteralPath $second.FullName -Directory -ErrorAction SilentlyContinue)) {
          if ($third.Name -match '^Face-LoRA-Dataset-Selector(?:-v0\.3\.1)?$' -and (IsOldRoot $third.FullName)) {
            $found.Add($third.FullName)
          }
        }
      }
    }
  }
  $found = @($found | Select-Object -Unique)
  Assert ($found.Count -eq 1) "Cannot uniquely locate old v0.3.1 saved state (matches=$($found.Count)). Re-run with -OldRoot 'G:\path\Face-LoRA-Dataset-Selector-v0.3.1'. No files have been altered."
  return [string]$found[0]
}
function CheckedZip([string]$Zip) {
  Assert (Test-Path -LiteralPath $Zip -PathType Leaf) "Missing ZIP: $Zip"
  $f = [IO.File]::OpenRead($Zip)
  try {
    Assert ($f.Length -gt 100) "ZIP is too small: $Zip"
    Assert (($f.ReadByte() -eq 0x50) -and ($f.ReadByte() -eq 0x4B)) "Not ZIP data: $Zip"
  } finally { $f.Dispose() }
}
function FetchPackage([string]$Url,[string]$Dst) {
  $part = "$Dst.part"
  if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
  Invoke-WebRequest -Uri $Url -OutFile $part -MaximumRedirection 12 -ErrorAction Stop
  CheckedZip $part
  Move-Item -LiteralPath $part -Destination $Dst -Force
}
function VerifyApp([string]$Dir) {
  $exe = Join-Path $Dir 'Face LoRA Dataset Selector.exe'
  $model = Join-Path $Dir '_internal\models\ediffiqa_t.onnx'
  Assert (Test-Path -LiteralPath $exe -PathType Leaf) 'Unified QA executable is missing.'
  Assert (Test-Path -LiteralPath $model -PathType Leaf) 'Bundled eDifFIQA model is missing.'
  Assert ((HashFile $model) -eq $modelSha) 'Bundled eDifFIQA SHA-256 mismatch.'
  $dml = @(Get-ChildItem -LiteralPath (Join-Path $Dir '_internal') -Recurse -File -Filter 'DirectML.dll' -ErrorAction SilentlyContinue)
  Assert ($dml.Count -gt 0) 'This package is CPU-only: DirectML.dll is missing.'
  return $exe
}
$script:copied = 0
$script:equal = 0
$script:conflicts = [collections.generic.list[string]]::new()
$script:copiedPaths = [collections.generic.list[string]]::new()
function CopyMissingTree([string]$From,[string]$To,[string]$Label) {
  if (-not (Test-Path -LiteralPath $From -PathType Container)) { return }
  $sourceFolder = (Get-Item -LiteralPath $From).FullName.TrimEnd('\')
  Assert (-not ($To.StartsWith($sourceFolder + '\',[StringComparison]::OrdinalIgnoreCase))) 'Refusing recursive migration destination inside source.'
  foreach ($source in @(Get-ChildItem -LiteralPath $From -Recurse -File -ErrorAction Stop)) {
    if (($source.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
    $relative = $source.FullName.Substring($sourceFolder.Length).TrimStart('\')
    $dst = Join-Path $To $relative
    if (Test-Path -LiteralPath $dst -PathType Leaf) {
      if ((HashFile $source.FullName) -eq (HashFile $dst)) { $script:equal++; continue }
      $script:conflicts.Add("$Label/$relative")
      continue
    }
    New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $source.FullName -Destination $dst -ErrorAction Stop
    Assert ((HashFile $source.FullName) -eq (HashFile $dst)) "Migration hash mismatch: $Label/$relative"
    $script:copied++
    $script:copiedPaths.Add("$Label/$relative")
  }
}
function Migrate-OldState([string]$From,[string]$To) {
  CopyMissingTree (Join-Path $From '_userdata') (Join-Path $To '_userdata') '_userdata'
  CopyMissingTree (Join-Path $From 'cache') (Join-Path $To '_userdata\cache') 'cache-legacy'
  CopyMissingTree (Join-Path $From '_FaceLoRA_ModelCache') (Join-Path $To '_FaceLoRA_ModelCache') '_FaceLoRA_ModelCache'
  $uiFile = Join-Path $From 'ui.ini'
  $uiDest = Join-Path $To 'ui.ini'
  if ((Test-Path -LiteralPath $uiFile -PathType Leaf) -and -not (Test-Path -LiteralPath $uiDest)) {
    Copy-Item -LiteralPath $uiFile -Destination $uiDest
    Assert ((HashFile $uiFile) -eq (HashFile $uiDest)) 'Legacy UI preferences copy SHA mismatch.'
    $script:copied++
    $script:copiedPaths.Add('ui.ini')
  }
}
$target = [IO.Path]::GetFullPath($Root).TrimEnd('\')
Assert ($target.Length -gt 12) 'QA path is unsafe.'
if (-not ($CiFixture -and $env:GITHUB_ACTIONS -eq 'true')) {
  Assert ($target.StartsWith('G:\',[StringComparison]::OrdinalIgnoreCase)) 'QA runtime/downloads must be on G:.'
}
$sentinel = Join-Path $target '.face-lora-v04-unified-qa'
if (Test-Path -LiteralPath $target -PathType Container) {
  $items = @(Get-ChildItem -LiteralPath $target -Force)
  Assert ($items.Count -eq 0 -or (Test-Path -LiteralPath $sentinel -PathType Leaf)) 'QA directory contains unmanaged files. Refusing overwrite.'
}
$old = Find-OldRoot
Assert (-not $old.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase)) 'Old root cannot be inside the QA destination.'
Write-Host "Old v0.3.1 records: $old (READ ONLY)"
New-Item -ItemType Directory -Path $target -Force | Out-Null
if (-not (Test-Path -LiteralPath $sentinel)) {
  "Unified v0.4 QA only" | Set-Content -LiteralPath $sentinel -Encoding UTF8
}
$work = Join-Path $target '.work'
$reports = Join-Path $target 'reports'
$dest = Join-Path $target 'app'
$reportPath = Join-Path $target 'QA_REPORT.json'
New-Item -ItemType Directory -Force -Path $work,$reports | Out-Null
$tmp = Join-Path $work 'tmp'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$oldTemp = $env:TEMP; $oldTmp = $env:TMP
$env:TEMP = $tmp; $env:TMP = $tmp
$report = [ordered]@{
  kind='v04-unified-human-qa'
  status='preparing'
  artifact_id=$artifactId
  artifact_commit=$artifactSha
  old_root=$old
  app_root=$dest
  mode=''
  migrated_files=0
  already_equal=0
  conflicts=@()
  old_cache_json_files=@(Get-OldDataFiles $old).Count
  run_device='Auto (DirectML preferred if available; CPU fallback permitted)'
  error=$null
}
try {
  Assert ($report.old_cache_json_files -gt 0) 'Old installation has no persisted cache JSON. Refusing empty migration.'
  $marker = Join-Path $dest '.unified-qa-artifact-id'
  if (Test-Path -LiteralPath $marker -PathType Leaf) {
    Assert (((Get-Content -LiteralPath $marker -Raw).Trim()) -eq $artifactId) 'Existing QA app is a different build; refusing to overwrite.'
    $exe = VerifyApp $dest
    Migrate-OldState $old $dest
    $report.mode = 'cached-existing-app'
  } else {
    Assert (-not (Test-Path -LiteralPath $dest)) 'Existing QA app not managed by this launcher; refusing overwrite.'
    $package = $LocalPackageZip
    if (-not $package) {
      Assert ($artifactId -match '^\d+$') 'Pinned unified artifact is not ready yet.'
      $archive = Join-Path $work 'artifact.zip'
      if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host 'Downloading pinned DirectML unified Portable to G: ...'
        FetchPackage $packageUrl $archive
      }
      $outer = Join-Path $work 'outer'
      if (Test-Path -LiteralPath $outer) { Remove-Item -LiteralPath $outer -Recurse -Force }
      Expand-Archive -LiteralPath $archive -DestinationPath $outer
      $inner = Get-ChildItem -LiteralPath $outer -Recurse -File -Filter '*Portable.zip' | Select-Object -First 1
      Assert ($null -ne $inner) 'No Portable ZIP inside artifact.'
      $package = $inner.FullName
    }
    $package = [IO.Path]::GetFullPath($package)
    CheckedZip $package
    $sidecar = "$package.sha256"
    Assert (Test-Path -LiteralPath $sidecar -PathType Leaf) "SHA-256 sidecar is required: $sidecar"
    $expected = ((Get-Content -LiteralPath $sidecar -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    Assert ($expected -match '^[a-f0-9]{64}$') 'Portable checksum file is malformed.'
    Assert ((HashFile $package) -eq $expected) 'Portable ZIP SHA-256 mismatch.'
    $unpack = Join-Path $work 'unpack'
    if (Test-Path -LiteralPath $unpack) { Remove-Item -LiteralPath $unpack -Recurse -Force }
    Expand-Archive -LiteralPath $package -DestinationPath $unpack
    $found = Get-ChildItem -LiteralPath $unpack -Recurse -File -Filter 'Face LoRA Dataset Selector.exe' | Select-Object -First 1
    Assert ($null -ne $found) 'Packaged application executable not found.'
    $sourceApp = $found.Directory.FullName
    $stage = Join-Path $work 'stage-app'
    Assert (-not (Test-Path -LiteralPath $stage)) 'Staging folder already exists; refusing destructive overwrite.'
    Move-Item -LiteralPath $sourceApp -Destination $stage
    $exe = VerifyApp $stage
    Migrate-OldState $old $stage
    $probe = Start-Process -FilePath $exe -ArgumentList '--self-test' -WorkingDirectory $stage -PassThru -Wait
    Assert ($probe.ExitCode -eq 0) "Packaged self-test failed: $($probe.ExitCode)"
    Set-Content -LiteralPath (Join-Path $stage '.unified-qa-artifact-id') -Value $artifactId -Encoding UTF8
    Move-Item -LiteralPath $stage -Destination $dest
    $exe = VerifyApp $dest
    $report.mode = 'verified-full-directml'
  }
  $report.migrated_files = $script:copied
  $report.already_equal = $script:equal
  $report.conflicts = @($script:conflicts)
  Assert ($report.conflicts.Count -eq 0) 'Existing new QA files conflicted with old state; preserved both without overwrite.'
  $cacheDir = Join-Path $dest '_userdata\cache'
  $cacheFiles = @(Get-ChildItem -LiteralPath $cacheDir -Filter '*.json' -File -ErrorAction SilentlyContinue)
  Assert ($cacheFiles.Count -gt 0) 'Old analysis/review cache did not reach the new app.'
  $report['new_cache_json_files'] = $cacheFiles.Count
  foreach ($chunk in @('artifact.zip','outer','unpack')) {
    $file = Join-Path $work $chunk
    if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Recurse -Force }
  }
  $report['executable'] = $exe
  if ($PrepareOnly) {
    $report.status='prepared'
    Write-Host "Unified v0.4 QA is prepared: $exe"
  } else {
    Write-Host "Launching unified v0.4 QA: $exe"
    $p = Start-Process -FilePath $exe -WorkingDirectory $dest -PassThru
    Start-Sleep -Seconds 4
    if ($p.HasExited -and $p.ExitCode -ne 0) { throw "GUI startup failed: exit $($p.ExitCode)" }
    $report.status='launched'
    $report['process_id']=$p.Id
  }
} catch {
  $report.status='failed'
  $report.error=$_.Exception.Message
  Write-Host "UNIFIED QA FAILED: $($report.error)" -ForegroundColor Red
  throw
} finally {
  $report['generated_at']=(Get-Date).ToUniversalTime().ToString('o')
  $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding UTF8
  $env:TEMP=$oldTemp; $env:TMP=$oldTmp
}
