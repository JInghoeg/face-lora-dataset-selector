#Requires -Version 7.0
<#
Create a SHA-pinned file delta between an immutable CPU Portable and the
unified DirectML Portable. Used on Windows CI, never on the user's PC.
User downloads only this delta. Unchanged bundled models are not included.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$BaseRoot,
  [Parameter(Mandatory)][string]$TargetRoot,
  [Parameter(Mandatory)][string]$OutputRoot,
  [string]$BaseArtifactId = '13578236484',
  [string]$TargetArtifactId = '13582688113',
  [string]$TargetCommit = 'ecca7d52f4ff1bb02b61aeee6f999d2893dce72e'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Fail([bool]$Condition,[string]$ErrorText) { if (-not $Condition) { throw $ErrorText } }
function Inventory([string]$Root) {
  $rootPath = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path.TrimEnd('\')
  $list = [collections.generic.list[object]]::new()
  foreach ($file in @(Get-ChildItem -LiteralPath $rootPath -File -Recurse -Force -ErrorAction Stop)) {
    Fail (([int]($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) -eq 0) "Symlinks prohibited in Portable: $($file.FullName)"
    $rel = $file.FullName.Substring($rootPath.Length).TrimStart('\').Replace('/','\')
    # CI's application self-test can create _userdata/.legacy_appdata_migrated_v031.
    # This is per-install state, never part of the reusable runtime or its delta.
    if ($rel.StartsWith('_userdata\',[StringComparison]::OrdinalIgnoreCase) -or
        $rel.StartsWith('_FaceLoRA_ModelCache\',[StringComparison]::OrdinalIgnoreCase) -or
        $rel.StartsWith('logs\',[StringComparison]::OrdinalIgnoreCase)) { continue }
    $list.Add([pscustomobject]@{
      relative = $rel
      size = [int64]$file.Length
      sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    })
  }
  return @($list | Sort-Object relative)
}
$baseDir=(Resolve-Path -LiteralPath $BaseRoot).Path.TrimEnd('\')
$targetDir=(Resolve-Path -LiteralPath $TargetRoot).Path.TrimEnd('\')
Fail ($baseDir -ne $targetDir) 'Base and target Portable directories must differ.'
Fail (-not (Test-Path -LiteralPath $OutputRoot)) "Output directory must be fresh: $OutputRoot"
$base=@(Inventory $baseDir)
$target=@(Inventory $targetDir)
Fail ($base.Count -gt 100 -and $target.Count -gt 100) 'Portable inventory is unexpectedly small.'
$index=@{}
foreach ($item in $base) { $index[$item.relative]=$item }
$patch=[collections.generic.list[string]]::new()
$changedBytes=[long]0
foreach ($item in $target) {
  if ($index.ContainsKey($item.relative) -and $index[$item.relative].sha256 -eq $item.sha256 -and $index[$item.relative].size -eq $item.size) { continue }
  $patch.Add($item.relative)
  $changedBytes += $item.size
}
Fail ($patch.Count -gt 0) 'No Portable changes found.'
$dir=[IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$files=Join-Path $dir 'files'
New-Item -ItemType Directory -Path $files -Force | Out-Null
foreach ($rel in $patch) {
  $src=Join-Path $targetDir $rel
  $dst=Join-Path $files $rel
  New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst
}
$targetIndex=@{}
foreach ($item in $target) { $targetIndex[$item.relative]=$item }
$deleted = @($base | Where-Object { -not $targetIndex.ContainsKey($_.relative) } | ForEach-Object { $_.relative })
$manifest=[ordered]@{
  schema=1
  base_artifact_id=$BaseArtifactId
  target_artifact_id=$TargetArtifactId
  target_commit=$TargetCommit
  source_runtime='CPU ONNX Runtime Portable'
  target_runtime='DirectML + CPU fallback'
  base=$base
  target=$target
  changed=@($patch)
  removed=$deleted
  unchanged_count=($target.Count-$patch.Count)
  changed_bytes=$changedBytes
}
$manifest | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $dir 'manifest.json') -Encoding utf8
# Verify every staged patch file before publishing the archive.
foreach ($rel in $patch) {
  $dst=Join-Path $files $rel
  Fail (((Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant()) -eq $targetIndex[$rel].sha256) "Patch hash mismatch: $rel"
}
Write-Host "CPU base files: $($base.Count)"
Write-Host "DirectML target files: $($target.Count)"
Write-Host "Changed/added: $($patch.Count); removed: $($deleted.Count); unchanged: $($manifest.unchanged_count)"
Write-Host "Required delta raw bytes: $changedBytes"
Write-Host "Unchanged bundled models are excluded; all base and target SHA-256 checks are included."
