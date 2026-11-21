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
  [string]$DeltaArtifactId = '',
  [string]$LocalDeltaZip = '',
  [string]$BaseAppRoot = '',
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

function Get-DeltaCandidates {
  if ($BaseAppRoot) { return @([IO.Path]::GetFullPath($BaseAppRoot).TrimEnd('\')) }
  return @(
    'G:\FaceLoRA-Luna-v04-QA\app',
    'G:\FaceLoRA-QA\runtime\Face-LoRA-Dataset-Selector',
    'G:\FaceLoRA-QA\current\app\Face-LoRA-Dataset-Selector',
    'G:\FaceLoRA-QA\current\app'
  )
}
function SafeRelative([string]$Rel,[string]$Parent) {
  Assert (-not [string]::IsNullOrWhiteSpace($Rel)) 'Delta relative path is empty.'
  $relNorm = $Rel.Replace('/','\')
  Assert (-not [IO.Path]::IsPathRooted($relNorm)) "Delta contains rooted path: $Rel"
  Assert (-not ($relNorm -match '(^|\\)\.\.(\\|$)')) "Delta contains parent traversal: $Rel"
  Assert (-not ($relNorm.Contains(':'))) "Delta contains colon path: $Rel"
  Assert (-not $relNorm.StartsWith('_userdata\',[StringComparison]::OrdinalIgnoreCase)) "Delta may not modify user records: $Rel"
  $full = [IO.Path]::GetFullPath((Join-Path $Parent $relNorm))
  $root = [IO.Path]::GetFullPath($Parent).TrimEnd('\')
  Assert ($full.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) "Delta escapes runtime directory: $Rel"
  return $full
}
function Test-DeltaBase([string]$Source,[object]$Manifest) {
  if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return $false }
  try {
    foreach ($entry in @($Manifest.base)) {
      $file = SafeRelative ([string]$entry.relative) $Source
      if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
      if ((Get-Item -LiteralPath $file).Length -ne [long]$entry.size) { return $false }
      if ((HashFile $file) -ne [string]$entry.sha256) { return $false }
    }
    return $true
  } catch { return $false }
}
function Build-DeltaStage([string]$Zip,[string]$Stage) {
  $zipFile=[IO.Path]::GetFullPath($Zip)
  CheckedZip $zipFile
  $sidecar="$zipFile.sha256"
  Assert (Test-Path -LiteralPath $sidecar -PathType Leaf) "Delta ZIP hash sidecar missing: $sidecar"
  $expected=((Get-Content -LiteralPath $sidecar -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
  Assert ($expected -match '^[0-9a-f]{64}$') 'Malformed delta checksum.'
  Assert ((HashFile $zipFile) -eq $expected) 'Delta archive SHA-256 mismatch.'
  $unpacked=Join-Path $work 'delta-unpacked'
  if (Test-Path -LiteralPath $unpacked) { Remove-Item -LiteralPath $unpacked -Recurse -Force }
  Expand-Archive -LiteralPath $zipFile -DestinationPath $unpacked
  $manifestPath=Join-Path $unpacked 'manifest.json'
  Assert (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Delta manifest missing.'
  $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  Assert ($manifest.schema -eq 1) 'Unsupported delta manifest schema.'
  Assert ([string]$manifest.target_artifact_id -eq $artifactId) 'Delta target artifact differs from the requested unified candidate.'
  Assert ([string]$manifest.target_commit -eq $artifactSha) 'Delta commit differs from the pinned unified candidate.'
  Assert ([string]$manifest.base_artifact_id -eq '13578236484') 'Unexpected CPU runtime base.'
  Assert (@($manifest.base).Count -gt 100 -and @($manifest.target).Count -gt 100) 'Delta manifest has an incomplete runtime inventory.'
  foreach ($entry in @($manifest.base) + @($manifest.target)) {
    [void](SafeRelative ([string]$entry.relative) $unpacked)
    Assert ([string]$entry.sha256 -match '^[a-f0-9]{64}$') 'Malformed runtime file hash.'
  }
  $base=$null
  foreach ($candidate in @(Get-DeltaCandidates)) {
    if (Test-DeltaBase $candidate $manifest) { $base=$candidate; break }
  }
  Assert (-not [string]::IsNullOrWhiteSpace($base)) 'No exact compatible CPU QA runtime found on G:. No full package was downloaded. Keep previous QA installs until a compatible base is located.'
  Write-Host "Reusing exact CPU QA runtime from $base (no model/engine re-download)."
  $script:deltaBase=$base
  if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $Stage | Out-Null
  $index=@{}
  foreach ($entry in @($manifest.base)) { $index[[string]$entry.relative]=$entry }
  $reuse=[long]0; $patchBytes=[long]0; $linked=0; $copiedPatch=0
  foreach ($entry in @($manifest.target)) {
    $rel=[string]$entry.relative
    $dst=SafeRelative $rel $Stage
    $oldEntry=$index[$rel]
    $canReuse=($null -ne $oldEntry -and [string]$oldEntry.sha256 -eq [string]$entry.sha256 -and [long]$oldEntry.size -eq [long]$entry.size)
    $source = if ($canReuse) { SafeRelative $rel $base } else { SafeRelative $rel (Join-Path $unpacked 'files') }
    Assert (Test-Path -LiteralPath $source -PathType Leaf) "Delta missing required runtime file: $rel"
    Assert ((Get-Item -LiteralPath $source).Length -eq [long]$entry.size) "Delta size mismatch: $rel"
    Assert ((HashFile $source) -eq [string]$entry.sha256) "Delta source hash mismatch: $rel"
    New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
    $hardlinked=$false
    if ($canReuse -and $rel.StartsWith('_internal\models\',[StringComparison]::OrdinalIgnoreCase)) {
      try {
        New-Item -ItemType HardLink -Path $dst -Target $source -ErrorAction Stop | Out-Null
        $hardlinked=$true
        $linked++
      } catch { $hardlinked=$false }
    }
    if (-not $hardlinked) { Copy-Item -LiteralPath $source -Destination $dst }
    Assert ((HashFile $dst) -eq [string]$entry.sha256) "Staged runtime hash mismatch: $rel"
    if ($canReuse) { $reuse += [long]$entry.size } else { $patchBytes += [long]$entry.size; $copiedPatch++ }
  }
  $script:deltaReuseBytes=$reuse
  $script:deltaPatchBytes=$patchBytes
  $script:deltaModelsHardlinked=$linked
  $script:deltaPatchedFiles=$copiedPatch
  Write-Host "DirectML delta complete: patched $copiedPatch files; reused $([math]::Round($reuse/1MB,1)) MiB locally, including $linked model hardlinks."
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
  delta_base=''
  delta_reused_bytes=0
  delta_patch_bytes=0
  delta_models_hardlinked=0
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
    if ($DeltaArtifactId -or $LocalDeltaZip) {
      # Strict delta-only path: NEVER fall back to the full 438 MB Portable.
      $delta = $LocalDeltaZip
      if (-not $delta) {
        Assert ($DeltaArtifactId -match '^\d+$') 'No immutable delta artifact ID was supplied.'
        $hasCandidate = @(Get-DeltaCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Container }).Count -gt 0
        Assert $hasCandidate 'No old QA runtime found on G:. Refusing a full download.'
        $outerArchive=Join-Path $work 'delta-artifact.zip'
        if (-not (Test-Path -LiteralPath $outerArchive)) {
          Write-Host 'Downloading only the DirectML delta, not a full Portable.'
          FetchPackage "https://nightly.link/JInghoeg/face-lora-dataset-selector/actions/artifacts/$DeltaArtifactId.zip" $outerArchive
        }
        $outerDir=Join-Path $work 'delta-outer'
        if (Test-Path -LiteralPath $outerDir) { Remove-Item -LiteralPath $outerDir -Recurse -Force }
        Expand-Archive -LiteralPath $outerArchive -DestinationPath $outerDir
        $deltaFile=Get-ChildItem -LiteralPath $outerDir -File -Filter 'v04-unified-directml-from-cpu.zip' | Select-Object -First 1
        Assert ($null -ne $deltaFile) 'Delta ZIP missing from GitHub artifact.'
        $delta=$deltaFile.FullName
      }
      $stage=Join-Path $work 'stage-app'
      Build-DeltaStage $delta $stage
      $exe=VerifyApp $stage
      Migrate-OldState $old $stage
      $probe=Start-Process -FilePath $exe -ArgumentList '--self-test' -WorkingDirectory $stage -PassThru -Wait
      Assert ($probe.ExitCode -eq 0) "Incremental DirectML EXE self-test failed: $($probe.ExitCode)"
      Set-Content -LiteralPath (Join-Path $stage '.unified-qa-artifact-id') -Value $artifactId -Encoding UTF8
      Move-Item -LiteralPath $stage -Destination $dest
      $exe=VerifyApp $dest
      $report.mode='verified-incremental-directml'
      $report.delta_base=$script:deltaBase
      $report.delta_reused_bytes=$script:deltaReuseBytes
      $report.delta_patch_bytes=$script:deltaPatchBytes
      $report.delta_models_hardlinked=$script:deltaModelsHardlinked
    } else {
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
  }
  $report.migrated_files = $script:copied
  $report.already_equal = $script:equal
  $report.conflicts = @($script:conflicts)
  Assert ($report.conflicts.Count -eq 0) 'Existing new QA files conflicted with old state; preserved both without overwrite.'
  $cacheDir = Join-Path $dest '_userdata\cache'
  $cacheFiles = @(Get-ChildItem -LiteralPath $cacheDir -Filter '*.json' -File -ErrorAction SilentlyContinue)
  Assert ($cacheFiles.Count -gt 0) 'Old analysis/review cache did not reach the new app.'
  $report['new_cache_json_files'] = $cacheFiles.Count
  foreach ($chunk in @('artifact.zip','outer','unpack','delta-artifact.zip','delta-outer','delta-unpacked')) {
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
