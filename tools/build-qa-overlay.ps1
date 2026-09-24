param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,

    [Parameter(Mandatory = $true)]
    [string]$OverlayRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$portable = [System.IO.Path]::GetFullPath($PortableRoot)
$overlay = [System.IO.Path]::GetFullPath($OverlayRoot)

if (-not (Test-Path -LiteralPath $portable -PathType Container)) {
    throw "Portable root does not exist: $portable"
}

$mutable = @(
    "Face LoRA Dataset Selector.exe",
    "_internal\translations\app_en_US.qm",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "使用说明.txt"
)

$metadata = @(
    "qa-runtime-fingerprint.txt",
    "qa-runtime-manifest.txt",
    "qa-runtime-identity.txt",
    "qa-overlay-info.txt"
)

$excluded = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($item in ($mutable + $metadata)) {
    [void]$excluded.Add($item.Replace("/", "\"))
}

$manifestLines = New-Object System.Collections.Generic.List[string]
$stableFiles = Get-ChildItem -LiteralPath $portable -Recurse -File |
    ForEach-Object {
        $relative = $_.FullName.Substring($portable.Length + 1).Replace("/", "\")
        [pscustomobject]@{
            File = $_
            Relative = $relative
        }
    } |
    Where-Object {
        if ($excluded.Contains($_.Relative)) {
            return $false
        }
        if ($_.Relative -ieq "_internal\base_library.zip") {
            return $false
        }
        if ($_.Relative -match '(?i)\\[^\\]+\.dist-info\\RECORD
foreach ($item in $stableFiles) {
    $hash = (Get-FileHash -LiteralPath $item.File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestLines.Add(("{0}  {1}  {2}" -f $hash, $item.File.Length, $item.Relative))
}

$manifestText = ($manifestLines -join "`n") + "`n"
$manifestPath = Join-Path $portable "qa-runtime-manifest.txt"
$manifestText | Set-Content -LiteralPath $manifestPath -Encoding UTF8 -NoNewline

$pythonIdentity = (& python -VV 2>&1 | Out-String).Trim()
$pyInstallerVersion = (& python -c "import PyInstaller; print(PyInstaller.__version__)" | Out-String).Trim()
$packages = @(& python -m pip freeze) | Sort-Object
$identityText = @(
    "Python=$pythonIdentity"
    "PyInstaller=$pyInstallerVersion"
    "Packages:"
    ($packages -join "`n")
) -join "`n"
$identityText += "`n"
$identityPath = Join-Path $portable "qa-runtime-identity.txt"
$identityText | Set-Content -LiteralPath $identityPath -Encoding UTF8 -NoNewline

$fingerprintInput = $identityText + "---FILES---`n" + $manifestText
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprintInput)
    $fingerprint = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
}
finally {
    $sha.Dispose()
}

$fingerprintPath = Join-Path $portable "qa-runtime-fingerprint.txt"
$fingerprint | Set-Content -LiteralPath $fingerprintPath -Encoding ASCII -NoNewline

if (Test-Path -LiteralPath $overlay) {
    Remove-Item -LiteralPath $overlay -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $overlay | Out-Null

foreach ($relative in $mutable) {
    $source = Join-Path $portable $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "QA overlay source file missing: $relative"
    }

    $destination = Join-Path $overlay $relative
    $parent = Split-Path $destination -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $overlay "qa-runtime-manifest.txt") -Force
Copy-Item -LiteralPath $identityPath -Destination (Join-Path $overlay "qa-runtime-identity.txt") -Force
Copy-Item -LiteralPath $fingerprintPath -Destination (Join-Path $overlay "qa-runtime-fingerprint.txt") -Force

@(
    "Face LoRA Dataset Selector QA Overlay"
    "RuntimeFingerprint=$fingerprint"
    "StableFileCount=$($stableFiles.Count)"
    "MutableFileCount=$($mutable.Count)"
    "Generated=$(Get-Date -Format o)"
) | Set-Content -LiteralPath (Join-Path $overlay "qa-overlay-info.txt") -Encoding UTF8

Write-Host "QA runtime fingerprint: $fingerprint"
Write-Host "Stable runtime files: $($stableFiles.Count)"
Write-Host "QA overlay ready: $overlay"
) {
            return $false
        }
        return $true
    } |
    Sort-Object Relative

foreach ($item in $stableFiles) {
    $hash = (Get-FileHash -LiteralPath $item.File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestLines.Add(("{0}  {1}  {2}" -f $hash, $item.File.Length, $item.Relative))
}

$manifestText = ($manifestLines -join "`n") + "`n"
$manifestPath = Join-Path $portable "qa-runtime-manifest.txt"
$manifestText | Set-Content -LiteralPath $manifestPath -Encoding UTF8 -NoNewline

$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($manifestText)
    $fingerprint = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
}
finally {
    $sha.Dispose()
}

$fingerprintPath = Join-Path $portable "qa-runtime-fingerprint.txt"
$fingerprint | Set-Content -LiteralPath $fingerprintPath -Encoding ASCII -NoNewline

if (Test-Path -LiteralPath $overlay) {
    Remove-Item -LiteralPath $overlay -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $overlay | Out-Null

foreach ($relative in $mutable) {
    $source = Join-Path $portable $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "QA overlay source file missing: $relative"
    }

    $destination = Join-Path $overlay $relative
    $parent = Split-Path $destination -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $overlay "qa-runtime-manifest.txt") -Force
Copy-Item -LiteralPath $fingerprintPath -Destination (Join-Path $overlay "qa-runtime-fingerprint.txt") -Force

@(
    "Face LoRA Dataset Selector QA Overlay"
    "RuntimeFingerprint=$fingerprint"
    "StableFileCount=$($stableFiles.Count)"
    "MutableFileCount=$($mutable.Count)"
    "Generated=$(Get-Date -Format o)"
) | Set-Content -LiteralPath (Join-Path $overlay "qa-overlay-info.txt") -Encoding UTF8

Write-Host "QA runtime fingerprint: $fingerprint"
Write-Host "Stable runtime files: $($stableFiles.Count)"
Write-Host "QA overlay ready: $overlay"
