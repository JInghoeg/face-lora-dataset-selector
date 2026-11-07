#Requires -Version 5.1
<#
Offline, self-contained, restart-safe stable delta installer for a Portable.
This script is packaged with the application and copied next to it BEFORE
the app exits. It never invokes downloaded scripts or touches user datasets.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$AppRoot,
    [Parameter(Mandatory)][string]$Pending,
    [Parameter(Mandatory)][int]$WaitPid
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
function Require([bool]$condition, [string]$errorText) {
    if (-not $condition) { throw $errorText }
}
function FileHash([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function SafePath([string]$root, [string]$relative) {
    Require (-not [string]::IsNullOrWhiteSpace($relative)) 'Empty patch path.'
    Require (-not [IO.Path]::IsPathRooted($relative)) 'Rooted patch path.'
    Require (-not $relative.Contains(':')) 'Drive or ADS in patch path.'
    Require (-not ($relative -match '(^|[\\/])\.\.([\\/]|$)')) 'Path escapes Portable.'
    $parts=@($relative.Replace('/','\').Split('\'))
    Require (-not (@($parts | Where-Object { $_ -eq '.' -or $_ -eq '' }).Count -gt 0)) 'Invalid empty/dot patch segment.'
    $blocked=@('_userdata','cache','logs','_FaceLoRA_ModelCache','.face-lora-updates','.updates')
    Require ($parts[0] -notin $blocked) 'Patch may not alter user data.'
    $base=[IO.Path]::GetFullPath($root).TrimEnd('\')
    $resolved=[IO.Path]::GetFullPath((Join-Path $base ($parts -join '\')))
    Require ($resolved.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)) 'Patch path escapes target root.'
    # Prevent a linked _internal/models directory from redirecting writes to a
    # user's external LoRA dataset or an unrelated installation.
    $prefix=$base
    foreach ($part in $parts) {
        $prefix=Join-Path $prefix $part
        if (Test-Path -LiteralPath $prefix) {
            $entry=Get-Item -LiteralPath $prefix -Force
            Require (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Update refuses junctions/symlinks inside Portable.'
        }
    }
    return $resolved
}
function JsonAtomic([string]$path,[object]$data) {
    $tmp="$path.tmp"
    $data | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $path -Force
}
function CheckInventory([string]$base,[object[]]$entries) {
    foreach ($item in $entries) {
        $file=SafePath $base ([string]$item.relative)
        Require (Test-Path -LiteralPath $file -PathType Leaf) "Missing runtime file: $($item.relative)"
        Require ((Get-Item -LiteralPath $file).Length -eq [long]$item.size) "Runtime size differs: $($item.relative)"
        Require ((FileHash $file) -eq [string]$item.sha256) "Runtime SHA differs: $($item.relative)"
    }
}
$app=[IO.Path]::GetFullPath($AppRoot).TrimEnd('\')
$rootDrive=[IO.Path]::GetPathRoot($app).TrimEnd('\')
Require ($app -ne $rootDrive -and $app.Length -gt 12) 'Unsafe application directory.'
Require (Test-Path -LiteralPath (Join-Path $app 'Face LoRA Dataset Selector.exe') -PathType Leaf) 'The target is not a Face LoRA Portable.'
Require ((Get-Item -LiteralPath $app).Attributes -band [IO.FileAttributes]::ReparsePoint -eq 0) 'Portable root is a symlink.'
$updateRoot=Join-Path (Split-Path $app -Parent) '.face-lora-updates'
$pendingFull=[IO.Path]::GetFullPath($Pending)
Require ($pendingFull -eq (Join-Path $updateRoot 'pending.json')) 'Pending record must reside next to the Portable.'
$reportFile=Join-Path $updateRoot 'result.json'
$lock=Join-Path $updateRoot 'apply.lock'
$backup=Join-Path $updateRoot 'rollback'
$staging=Join-Path $updateRoot 'staged-files'
$archive=$null
$applied=[collections.generic.list[string]]::new()
$hadFile=[collections.generic.list[string]]::new()
$report=[ordered]@{status='starting';at=(Get-Date).ToUniversalTime().ToString('o');error='';app_root=$app;from_version='';to_version=''}
try {
    # Prevent two concurrently running installers from touching the same EXE.
    if (Test-Path -LiteralPath $lock) { throw 'An update install is already in progress.' }
    'running' | Set-Content -LiteralPath $lock -Encoding ascii
    $data=Get-Content -LiteralPath $pendingFull -Raw | ConvertFrom-Json
    Require ($data.schema -eq 1) 'Invalid pending update schema.'
    Require (([IO.Path]::GetFullPath([string]$data.app_root).TrimEnd('\')) -eq $app) 'Pending update belongs to a different Portable.'
    Require ([string]$data.archive_name -match '^v?\d+\.\d+\.\d+-to-v?\d+\.\d+\.\d+\.zip$') 'Unexpected update archive name.'
    Require ([string]$data.archive_sha256 -match '^[a-fA-F0-9]{64}$') 'Invalid delta checksum.'
    $archive=Join-Path $updateRoot ([string]$data.archive_name)
    Require (Test-Path -LiteralPath $archive -PathType Leaf) 'Downloaded update ZIP is missing.'
    Require ((FileHash $archive) -eq [string]$data.archive_sha256) 'Downloaded ZIP SHA mismatch.'
    $report.from_version=[string]$data.from_version
    $report.to_version=[string]$data.to_version
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $manifestEntry=$zip.GetEntry('manifest.json')
        Require ($null -ne $manifestEntry -and $manifestEntry.Length -le 1048576) 'Missing or large update manifest.'
        $reader=[IO.StreamReader]::new($manifestEntry.Open(),[Text.Encoding]::UTF8)
        try { $manifest=$reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        Require ($manifest.schema -eq 1) 'Unsupported delta schema.'
        Require ([string]$manifest.from_version -eq $report.from_version) 'Delta base version mismatch.'
        Require ([string]$manifest.to_version -eq $report.to_version) 'Delta target version mismatch.'
        $base=@($manifest.base);$target=@($manifest.target)
        Require ($base.Count -gt 0 -and $target.Count -gt 0) 'Incomplete delta inventory.'
        # Validate ALL paths BEFORE altering the installation.
        $baseMap=@{}; $targetMap=@{}
        foreach ($item in $base) {
            [void](SafePath $app ([string]$item.relative))
            $key=([string]$item.relative).Replace('/','\').ToLowerInvariant()
            Require (-not $baseMap.ContainsKey($key)) 'Duplicate base inventory path.'
            $baseMap[$key]=$item
        }
        foreach ($item in $target) {
            [void](SafePath $app ([string]$item.relative))
            $key=([string]$item.relative).Replace('/','\').ToLowerInvariant()
            Require (-not $targetMap.ContainsKey($key)) 'Duplicate target inventory path.'
            $targetMap[$key]=$item
        }
        $changed=@($manifest.changed);$removed=@($manifest.removed)
        foreach ($rel in $changed + $removed) { [void](SafePath $app ([string]$rel)) }
        CheckInventory $app $base
        Require (-not (Test-Path -LiteralPath $backup)) 'Stale rollback folder; not overwriting a previous recovery.'
        Require (-not (Test-Path -LiteralPath $staging)) 'Stale staging folder; not overwriting a previous recovery.'
        New-Item -ItemType Directory -Path $backup,$staging -Force | Out-Null
        $changedMap=@{}
        foreach ($rel in $changed) {
            $key=([string]$rel).Replace('/','\').ToLowerInvariant()
            Require (-not $changedMap.ContainsKey($key) -and $targetMap.ContainsKey($key)) 'Invalid changed-file list.'
            $changedMap[$key]=$true
            $entry=$zip.GetEntry('files/'+([string]$rel).Replace('\','/'))
            Require ($null -ne $entry) "Missing update file: $rel"
            $info=$targetMap[$key]
            Require ($entry.Length -eq [long]$info.size) "Update file size mismatch: $rel"
            $output=SafePath $staging ([string]$rel)
            New-Item -ItemType Directory -Path (Split-Path $output -Parent) -Force | Out-Null
            $src=$entry.Open();$dst=[IO.File]::Create($output)
            try { $src.CopyTo($dst) } finally { $dst.Dispose();$src.Dispose() }
            Require ((FileHash $output) -eq [string]$info.sha256) "Update file SHA mismatch: $rel"
        }
        # Verify that all differing target entries are present in changed files.
        foreach ($key in $targetMap.Keys) {
            $expected=$targetMap[$key]
            $was=$baseMap[$key]
            if ($null -eq $was -or $was.sha256 -ne $expected.sha256) {
                Require ($changedMap.ContainsKey($key)) 'Delta is missing a changed file.'
            }
        }
        foreach ($rel in $removed) {
            $key=([string]$rel).Replace('/','\').ToLowerInvariant()
            Require ($baseMap.ContainsKey($key) -and -not $targetMap.ContainsKey($key)) 'Invalid deleted-file list.'
        }
        $oldVersion=(Get-Content -LiteralPath (Join-Path $app 'VERSION.txt') -Raw).Trim()
        Require ($oldVersion -eq $report.from_version) 'Installed version was changed during update preparation.'
    } finally { $zip.Dispose() }

    # Wait for the GUI to finish writing all record/cache files.
    $elapsed=0
    while ((Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) -and $elapsed -lt 180) {
        Start-Sleep -Seconds 1
        $elapsed++
    }
    Require (-not (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue)) 'Application did not exit; update aborted.'
    CheckInventory $app $base
    $report.status='installing'
    JsonAtomic $reportFile $report
    foreach ($rel in @($manifest.changed) + @($manifest.removed)) {
        $path=SafePath $app ([string]$rel)
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $save=SafePath $backup ([string]$rel)
            New-Item -ItemType Directory -Path (Split-Path $save -Parent) -Force | Out-Null
            Copy-Item -LiteralPath $path -Destination $save
            Require ((FileHash $path) -eq (FileHash $save)) 'Rollback file checksum failure.'
            $hadFile.Add([string]$rel)
        }
    }
    foreach ($rel in @($manifest.changed)) {
        $source=SafePath $staging ([string]$rel)
        $destination=SafePath $app ([string]$rel)
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        # Remove the destination's directory entry first. Some QA builds use
        # hardlinked unchanged model files; overwriting the link in place could
        # mutate a different installed version's model weights.
        $applied.Add([string]$rel)
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            Remove-Item -LiteralPath $destination -Force
        }
        Copy-Item -LiteralPath $source -Destination $destination
    }
    foreach ($rel in @($manifest.removed)) {
        $destination=SafePath $app ([string]$rel)
        if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Force }
        $applied.Add([string]$rel)
    }
    CheckInventory $app $target
    $exe=Join-Path $app 'Face LoRA Dataset Selector.exe'
    $process=Start-Process -FilePath $exe -WorkingDirectory $app -PassThru
    Start-Sleep -Seconds 5
    Require (-not ($process.HasExited -and $process.ExitCode -ne 0)) 'Updated application failed to start.'
    $report.status='installed'
    $report['process_id']=$process.Id
    # Keep only a small receipt. No extra runtime, old models or full installer.
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
    if (Test-Path -LiteralPath $pendingFull) { Remove-Item -LiteralPath $pendingFull -Force }
} catch {
    $report.status='failed'
    $report.error=$_.Exception.Message
    # Do not touch any real user state: restore only the versioned runtime files.
    try {
        foreach ($rel in $applied) {
            $destination=SafePath $app $rel
            $saved=SafePath $backup $rel
            if (Test-Path -LiteralPath $destination -PathType Leaf) {
                Remove-Item -LiteralPath $destination -Force
            }
            if (Test-Path -LiteralPath $saved -PathType Leaf) {
                New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
                Copy-Item -LiteralPath $saved -Destination $destination
            }
        }
        $report['rollback']='attempted'
    } catch {
        $report['rollback']='failed; recovery files preserved'
        $report['rollback_error']=$_.Exception.Message
    }
} finally {
    try { JsonAtomic $reportFile $report } catch {}
    if (Test-Path -LiteralPath $lock) { Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue }
}
