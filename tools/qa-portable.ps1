param(
    [ValidateSet("Prepare", "Clean", "CleanLegacy", "ResetRuntime", "Status")]
    [string]$Action = "Prepare",
    [string]$Root = $env:FACE_LORA_QA_ROOT,
    [long]$RunId = 0,
    [string]$Branch = "",
    [string]$Repo = "JInghoeg/face-lora-dataset-selector",
    [string]$Artifact = "Face-LoRA-Dataset-Selector-Windows-x64-Portable",
    [string]$OverlayArtifact = "Face-LoRA-Dataset-Selector-Windows-x64-QA-Overlay",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-QaRoot {
    param([string]$Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        return [System.IO.Path]::GetFullPath($Requested)
    }
    if (Test-Path "G:\") {
        return "G:\FaceLoRA-QA"
    }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "FACE_LORA_QA_ROOT is not set and LOCALAPPDATA is unavailable."
    }
    return (Join-Path $env:LOCALAPPDATA "FaceLoRA-QA")
}

function Assert-SafeRoot {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $driveRoot = [System.IO.Path]::GetPathRoot($full)
    if ($full.TrimEnd("\") -eq $driveRoot.TrimEnd("\")) {
        throw "Refusing to use a drive root as QA root: $full"
    }
    if ($full.Length -lt 12) {
        throw "QA root is unexpectedly short; refusing destructive cleanup: $full"
    }
}

function Ensure-QaRoot {
    param([string]$Path)
    Assert-SafeRoot $Path
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    $sentinel = Join-Path $Path ".face-lora-qa-root"
    if (-not (Test-Path $sentinel)) {
        @(
            "Face LoRA Dataset Selector QA root"
            "Created: $(Get-Date -Format o)"
            "Managed by tools/qa-portable.ps1"
        ) | Set-Content -LiteralPath $sentinel -Encoding UTF8
    }
}

function Assert-ManagedRoot {
    param([string]$Path)
    Assert-SafeRoot $Path
    $sentinel = Join-Path $Path ".face-lora-qa-root"
    if (-not (Test-Path -LiteralPath $sentinel)) {
        throw "Refusing cleanup because the QA sentinel is missing: $sentinel"
    }
}

function Resolve-Branch {
    param([string]$Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        return $Requested
    }
    try {
        $gitBranch = (& git branch --show-current 2>$null).Trim()
        if (-not [string]::IsNullOrWhiteSpace($gitBranch)) {
            return $gitBranch
        }
    }
    catch {
    }
    return "main"
}

function Require-Gh {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI (gh) is required for Prepare."
    }
}

function Get-RunInfo {
    param(
        [long]$RequestedRunId,
        [string]$RequestedBranch
    )

    Require-Gh

    if ($RequestedRunId -gt 0) {
        $json = & gh run view $RequestedRunId --repo $Repo --json databaseId,headSha,headBranch,status,conclusion,url
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to read GitHub Actions run $RequestedRunId."
        }
        return ($json | ConvertFrom-Json)
    }

    $resolvedBranch = Resolve-Branch $RequestedBranch
    $json = & gh run list --repo $Repo --workflow "Build Windows Portable" --branch $resolvedBranch --status success --limit 1 --json databaseId,headSha,headBranch,status,conclusion,url
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to query the latest successful Portable run."
    }

    $runs = @($json | ConvertFrom-Json)
    if ($runs.Count -eq 0) {
        throw "No successful Build Windows Portable run found for branch '$resolvedBranch'."
    }

    return $runs[0]
}

function Merge-ModelCache {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        return 0
    }

    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    $copied = 0

    foreach ($file in Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -ErrorAction SilentlyContinue) {
        if ($file.Name.EndsWith(".part", [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        $relative = $file.FullName.Substring($SourceRoot.Length).TrimStart("\")
        $destination = Join-Path $DestinationRoot $relative
        if (Test-Path -LiteralPath $destination) {
            continue
        }

        New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination
        $copied += 1
    }

    return $copied
}

function Preserve-ManagedLegacyModels {
    param(
        [string]$SearchRoot,
        [string]$DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $SearchRoot -PathType Container)) {
        return 0
    }

    $total = 0
    $caches = @(
        Get-ChildItem -LiteralPath $SearchRoot -Recurse -Directory -Filter "_FaceLoRA_ModelCache" -ErrorAction SilentlyContinue
    )

    foreach ($cache in $caches) {
        $total += Merge-ModelCache -SourceRoot $cache.FullName -DestinationRoot $DestinationRoot
    }

    return $total
}

function Get-TextFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    return (Get-Content -LiteralPath $Path -Raw).Trim()
}

function Test-RuntimeManifest {
    param(
        [string]$CandidateRoot,
        [string]$ManifestPath
    )

    if (
        -not (Test-Path -LiteralPath $CandidateRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)
    ) {
        return $false
    }

    foreach ($line in Get-Content -LiteralPath $ManifestPath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -notmatch '^([0-9a-fA-F]{64})  ([0-9]+)  (.+)$') {
            return $false
        }

        $expectedHash = $Matches[1].ToLowerInvariant()
        $expectedLength = [int64]$Matches[2]
        $relative = $Matches[3]
        $path = Join-Path $CandidateRoot $relative

        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            return $false
        }

        $file = Get-Item -LiteralPath $path
        if ($file.Length -ne $expectedLength) {
            return $false
        }

        $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            return $false
        }
    }

    return $true
}

function Download-Artifact {
    param(
        [long]$SelectedRunId,
        [string]$Name,
        [string]$Destination,
        [switch]$AllowMissing
    )

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    & gh run download $SelectedRunId --repo $Repo --name $Name --dir $Destination
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $Destination -Recurse -Force -ErrorAction SilentlyContinue
        if ($AllowMissing) {
            return $false
        }
        throw "Artifact download failed: $Name"
    }

    return $true
}

function Apply-Overlay {
    param(
        [string]$OverlayRoot,
        [string]$PortableRoot
    )

    foreach ($file in Get-ChildItem -LiteralPath $OverlayRoot -Recurse -File) {
        $relative = $file.FullName.Substring($OverlayRoot.Length).TrimStart("\")
        $destination = Join-Path $PortableRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
}

function Install-FullPortable {
    param(
        [string]$ArtifactDownload,
        [string]$PortableRoot,
        [string]$StagingRoot
    )

    $zip = Get-ChildItem -LiteralPath $ArtifactDownload -Recurse -File -Filter "*Portable.zip" | Select-Object -First 1
    if ($null -eq $zip) {
        throw "Full Portable artifact did not contain a Portable ZIP."
    }

    $sumFile = Get-ChildItem -LiteralPath $ArtifactDownload -Recurse -File -Filter "*.zip.sha256" | Select-Object -First 1
    if ($null -ne $sumFile) {
        $expected = ((Get-Content -LiteralPath $sumFile.FullName -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
        $actual = (Get-FileHash -LiteralPath $zip.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expected -ne $actual) {
            throw "Portable ZIP checksum mismatch. Expected $expected, got $actual."
        }
    }

    if (Test-Path -LiteralPath $StagingRoot) {
        Remove-Item -LiteralPath $StagingRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null
    Expand-Archive -LiteralPath $zip.FullName -DestinationPath $StagingRoot -Force

    $exe = Get-ChildItem -LiteralPath $StagingRoot -Recurse -File -Filter "Face LoRA Dataset Selector.exe" | Select-Object -First 1
    if ($null -eq $exe) {
        throw "Portable EXE was not found after expanding the full artifact."
    }

    $sourceRoot = $exe.Directory.FullName

    if (Test-Path -LiteralPath $PortableRoot) {
        Remove-Item -LiteralPath $PortableRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $PortableRoot -Parent) | Out-Null
    Move-Item -LiteralPath $sourceRoot -Destination $PortableRoot
}

function Get-LegacyQaDirectories {
    param([string]$CanonicalRoot)

    $parent = Split-Path $CanonicalRoot -Parent
    if ([string]::IsNullOrWhiteSpace($parent)) {
        return @()
    }

    $canonical = [System.IO.Path]::GetFullPath($CanonicalRoot).TrimEnd("\")
    return @(
        Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue |
            Where-Object {
                $full = $_.FullName.TrimEnd("\")
                $full -ne $canonical -and (
                    $_.Name -like "FaceLoRA-QA-*" -or
                    $_.Name -like "FaceLoRA_QA-*"
                )
            }
    )
}

function Try-Adopt-Portable {
    param(
        [string]$SearchRoot,
        [string]$ManifestPath,
        [string]$DestinationRoot,
        [string]$ModelCacheRoot
    )

    if (-not (Test-Path -LiteralPath $SearchRoot -PathType Container)) {
        return $false
    }

    $executables = @(
        Get-ChildItem -LiteralPath $SearchRoot -Recurse -File -Filter "Face LoRA Dataset Selector.exe" -ErrorAction SilentlyContinue
    )

    foreach ($exe in $executables) {
        $candidate = $exe.Directory.FullName
        Write-Host "Checking reusable local Portable: $candidate"
        if (-not (Test-RuntimeManifest -CandidateRoot $candidate -ManifestPath $ManifestPath)) {
            continue
        }

        [void](Preserve-ManagedLegacyModels -SearchRoot $SearchRoot -DestinationRoot $ModelCacheRoot)

        if (Test-Path -LiteralPath $DestinationRoot) {
            Remove-Item -LiteralPath $DestinationRoot -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path (Split-Path $DestinationRoot -Parent) | Out-Null

        if ((Split-Path $candidate -Leaf) -eq "Face-LoRA-Dataset-Selector") {
            Move-Item -LiteralPath $candidate -Destination $DestinationRoot
        }
        else {
            Copy-Item -LiteralPath $candidate -Destination $DestinationRoot -Recurse
        }

        Write-Host "Reused existing local Portable runtime without a full download."
        return $true
    }

    return $false
}

$QaRoot = Resolve-QaRoot $Root
$RuntimeRoot = Join-Path $QaRoot "runtime"
$PortableRoot = Join-Path $RuntimeRoot "Face-LoRA-Dataset-Selector"
$ModelCacheRoot = Join-Path $RuntimeRoot "_FaceLoRA_ModelCache"
$Current = Join-Path $QaRoot "current"
$ScratchDir = Join-Path $Current "scratch"
$InfoPath = Join-Path $Current "QA_INFO.txt"
$Downloads = Join-Path $QaRoot ".downloads"
$Staging = Join-Path $QaRoot ".staging"
$RuntimeFingerprintPath = Join-Path $PortableRoot "qa-runtime-fingerprint.txt"
$ExePath = Join-Path $PortableRoot "Face LoRA Dataset Selector.exe"

switch ($Action) {
    "Status" {
        Write-Host "QA root     : $QaRoot"
        Write-Host "Portable    : $PortableRoot"
        Write-Host "Model cache : $ModelCacheRoot"
        Write-Host "Scratch     : $ScratchDir"
        if (Test-Path -LiteralPath $InfoPath) {
            Write-Host ""
            Get-Content -LiteralPath $InfoPath
        }
        elseif (Test-Path -LiteralPath $PortableRoot) {
            Write-Host ""
            Write-Host "Portable runtime exists, but no current QA candidate metadata is prepared."
        }
        else {
            Write-Host ""
            Write-Host "No QA runtime is prepared yet."
        }
        exit 0
    }

    "Clean" {
        Assert-ManagedRoot $QaRoot
        if (Test-Path -LiteralPath $Current) {
            Remove-Item -LiteralPath $Current -Recurse -Force
            Write-Host "Removed disposable current QA state: $Current"
        }
        else {
            Write-Host "Current QA state is already clean: $Current"
        }
        Write-Host "Portable runtime preserved: $PortableRoot"
        Write-Host "Downloaded model cache preserved: $ModelCacheRoot"
        exit 0
    }

    "ResetRuntime" {
        Assert-ManagedRoot $QaRoot
        if (Test-Path -LiteralPath $PortableRoot) {
            Remove-Item -LiteralPath $PortableRoot -Recurse -Force
            Write-Host "Removed cached Portable runtime: $PortableRoot"
        }
        else {
            Write-Host "Portable runtime is already absent."
        }
        Write-Host "Downloaded model cache preserved: $ModelCacheRoot"
        exit 0
    }

    "CleanLegacy" {
        Ensure-QaRoot $QaRoot
        Assert-ManagedRoot $QaRoot
        $legacy = @(Get-LegacyQaDirectories -CanonicalRoot $QaRoot)

        if ($legacy.Count -eq 0) {
            Write-Host "No legacy FaceLoRA QA directories found."
            exit 0
        }

        Write-Host "Legacy QA directories:"
        $legacy | ForEach-Object { Write-Host "  $($_.FullName)" }
        Write-Host ""
        Write-Host "Any _FaceLoRA_ModelCache found inside these directories will be copied into:"
        Write-Host "  $ModelCacheRoot"

        if (-not $Force) {
            Write-Host ""
            Write-Host "Preview only. Run Prepare first if you want it to reuse a compatible old Portable, then re-run CleanLegacy with -Force."
            exit 0
        }

        foreach ($item in $legacy) {
            $copied = Preserve-ManagedLegacyModels -SearchRoot $item.FullName -DestinationRoot $ModelCacheRoot
            if ($copied -gt 0) {
                Write-Host "Preserved $copied cached model file(s) from: $($item.FullName)"
            }
            Remove-Item -LiteralPath $item.FullName -Recurse -Force
            Write-Host "Removed: $($item.FullName)"
        }
        exit 0
    }

    "Prepare" {
        Ensure-QaRoot $QaRoot
        Assert-ManagedRoot $QaRoot
        Require-Gh

        $run = Get-RunInfo -RequestedRunId $RunId -RequestedBranch $Branch
        if ($run.status -ne "completed" -or $run.conclusion -ne "success") {
            throw "Run $($run.databaseId) is not a completed successful run."
        }

        if (Test-Path -LiteralPath $Downloads) {
            Remove-Item -LiteralPath $Downloads -Recurse -Force
        }
        if (Test-Path -LiteralPath $Staging) {
            Remove-Item -LiteralPath $Staging -Recurse -Force
        }

        New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

        Write-Host "Preparing QA candidate..."
        Write-Host "  Run    : $($run.databaseId)"
        Write-Host "  Commit : $($run.headSha)"
        Write-Host "  Branch : $($run.headBranch)"

        $mode = "full"
        $overlayDownload = Join-Path $Downloads "overlay"
        $hasOverlay = Download-Artifact -SelectedRunId $run.databaseId -Name $OverlayArtifact -Destination $overlayDownload -AllowMissing

        if ($hasOverlay) {
            $overlayFingerprintFile = Get-ChildItem -LiteralPath $overlayDownload -Recurse -File -Filter "qa-runtime-fingerprint.txt" | Select-Object -First 1
            $overlayManifestFile = Get-ChildItem -LiteralPath $overlayDownload -Recurse -File -Filter "qa-runtime-manifest.txt" | Select-Object -First 1

            if ($null -ne $overlayFingerprintFile -and $null -ne $overlayManifestFile) {
                $overlayRoot = $overlayFingerprintFile.Directory.FullName
                $newFingerprint = Get-TextFile $overlayFingerprintFile.FullName
                $oldFingerprint = Get-TextFile $RuntimeFingerprintPath
                $reusable = $false

                if (
                    -not [string]::IsNullOrWhiteSpace($newFingerprint) -and
                    $newFingerprint -eq $oldFingerprint -and
                    (Test-Path -LiteralPath $ExePath -PathType Leaf)
                ) {
                    $reusable = $true
                }
                elseif (Test-RuntimeManifest -CandidateRoot $PortableRoot -ManifestPath $overlayManifestFile.FullName) {
                    Write-Host "Existing canonical runtime matches the new manifest; adopting its fingerprint."
                    $reusable = $true
                }
                else {
                    $oldManagedApp = Join-Path $Current "app"
                    if (Try-Adopt-Portable -SearchRoot $oldManagedApp -ManifestPath $overlayManifestFile.FullName -DestinationRoot $PortableRoot -ModelCacheRoot $ModelCacheRoot) {
                        $reusable = $true
                    }
                    else {
                        foreach ($legacyDir in @(Get-LegacyQaDirectories -CanonicalRoot $QaRoot)) {
                            if (Try-Adopt-Portable -SearchRoot $legacyDir.FullName -ManifestPath $overlayManifestFile.FullName -DestinationRoot $PortableRoot -ModelCacheRoot $ModelCacheRoot) {
                                $reusable = $true
                                break
                            }
                        }
                    }
                }

                if ($reusable) {
                    Write-Host "Stable runtime matches; applying small QA overlay."
                    Apply-Overlay -OverlayRoot $overlayRoot -PortableRoot $PortableRoot
                    $mode = "overlay"
                }
                else {
                    Write-Host "No compatible local runtime found; full Portable refresh required."
                }
            }
        }

        if ($mode -eq "full") {
            $fullDownload = Join-Path $Downloads "full"
            [void](Download-Artifact -SelectedRunId $run.databaseId -Name $Artifact -Destination $fullDownload)
            Install-FullPortable -ArtifactDownload $fullDownload -PortableRoot $PortableRoot -StagingRoot $Staging
        }

        if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
            throw "Prepared QA runtime does not contain the Portable EXE: $ExePath"
        }

        if (Test-Path -LiteralPath $Current) {
            [void](Preserve-ManagedLegacyModels -SearchRoot $Current -DestinationRoot $ModelCacheRoot)
            Remove-Item -LiteralPath $Current -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $ScratchDir | Out-Null

        $runtimeFingerprint = Get-TextFile $RuntimeFingerprintPath
        $modelFiles = @(
            Get-ChildItem -LiteralPath $ModelCacheRoot -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { -not $_.Name.EndsWith(".part", [System.StringComparison]::OrdinalIgnoreCase) }
        )

        @(
            "Face LoRA Dataset Selector QA Candidate"
            "RunId=$($run.databaseId)"
            "Commit=$($run.headSha)"
            "Branch=$($run.headBranch)"
            "Mode=$mode"
            "RuntimeFingerprint=$runtimeFingerprint"
            "Prepared=$(Get-Date -Format o)"
            "RunUrl=$($run.url)"
            "Exe=$ExePath"
            "ScratchDir=$ScratchDir"
            "ModelCache=$ModelCacheRoot"
            "CachedModelFiles=$($modelFiles.Count)"
        ) | Set-Content -LiteralPath $InfoPath -Encoding UTF8

        Remove-Item -LiteralPath $Downloads -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "QA candidate ready."
        Write-Host "Update mode : $mode"
        Write-Host "EXE         : $ExePath"
        Write-Host "Scratch     : $ScratchDir"
        Write-Host "Model cache : $ModelCacheRoot"
        if ($mode -eq "overlay") {
            Write-Host "Only the incremental QA overlay was downloaded; stable runtime/model files were reused."
        }
        else {
            Write-Host "Full Portable was refreshed because no compatible local runtime was available."
        }
    }
}
