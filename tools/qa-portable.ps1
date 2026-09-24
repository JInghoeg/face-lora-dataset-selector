param(
    [ValidateSet("Prepare", "Clean", "CleanLegacy", "Status")]
    [string]$Action = "Prepare",
    [string]$Root = $env:FACE_LORA_QA_ROOT,
    [long]$RunId = 0,
    [string]$Branch = "",
    [string]$Repo = "JInghoeg/face-lora-dataset-selector",
    [string]$Artifact = "Face-LoRA-Dataset-Selector-Windows-x64-Portable",
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
            "Only qa-portable.ps1 should automatically clean this directory."
        ) | Set-Content -Path $sentinel -Encoding UTF8
    }
}

function Assert-ManagedRoot {
    param([string]$Path)
    Assert-SafeRoot $Path
    $sentinel = Join-Path $Path ".face-lora-qa-root"
    if (-not (Test-Path $sentinel)) {
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

$QaRoot = Resolve-QaRoot $Root
$Current = Join-Path $QaRoot "current"
$AppDir = Join-Path $Current "app"
$ScratchDir = Join-Path $Current "scratch"
$InfoPath = Join-Path $Current "QA_INFO.txt"

switch ($Action) {
    "Status" {
        Write-Host "QA root : $QaRoot"
        Write-Host "Current : $Current"
        if (Test-Path $InfoPath) {
            Write-Host ""
            Get-Content $InfoPath
        }
        elseif (Test-Path $Current) {
            Write-Host "Current QA directory exists, but QA_INFO.txt is missing."
        }
        else {
            Write-Host "No current QA candidate is prepared."
        }
        exit 0
    }

    "Clean" {
        Assert-ManagedRoot $QaRoot
        if (Test-Path $Current) {
            Remove-Item -LiteralPath $Current -Recurse -Force
            Write-Host "Removed current QA workspace: $Current"
        }
        else {
            Write-Host "Current QA workspace is already clean: $Current"
        }
        exit 0
    }

    "CleanLegacy" {
        $parent = Split-Path $QaRoot -Parent
        if ([string]::IsNullOrWhiteSpace($parent)) {
            throw "Unable to resolve QA root parent."
        }

        $canonical = [System.IO.Path]::GetFullPath($QaRoot).TrimEnd("\")
        $legacy = @(
            Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue |
                Where-Object {
                    $full = $_.FullName.TrimEnd("\")
                    $full -ne $canonical -and (
                        $_.Name -like "FaceLoRA-QA-*" -or
                        $_.Name -like "FaceLoRA_QA-*"
                    )
                }
        )

        if ($legacy.Count -eq 0) {
            Write-Host "No legacy FaceLoRA QA directories found under $parent"
            exit 0
        }

        Write-Host "Legacy QA directories:"
        $legacy | ForEach-Object { Write-Host "  $($_.FullName)" }

        if (-not $Force) {
            Write-Host ""
            Write-Host "Preview only. Re-run with -Force to delete exactly the directories listed above."
            exit 0
        }

        foreach ($item in $legacy) {
            Remove-Item -LiteralPath $item.FullName -Recurse -Force
            Write-Host "Removed: $($item.FullName)"
        }
        exit 0
    }

    "Prepare" {
        Ensure-QaRoot $QaRoot
        Assert-ManagedRoot $QaRoot

        $run = Get-RunInfo -RequestedRunId $RunId -RequestedBranch $Branch
        if ($run.status -ne "completed" -or $run.conclusion -ne "success") {
            throw "Run $($run.databaseId) is not a completed successful run."
        }

        if (Test-Path $Current) {
            Remove-Item -LiteralPath $Current -Recurse -Force
        }

        New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
        New-Item -ItemType Directory -Force -Path $ScratchDir | Out-Null

        Write-Host "Downloading QA candidate..."
        Write-Host "  Run      : $($run.databaseId)"
        Write-Host "  Commit   : $($run.headSha)"
        Write-Host "  Branch   : $($run.headBranch)"
        Write-Host "  Artifact : $Artifact"
        Write-Host "  Target   : $AppDir"

        & gh run download $run.databaseId --repo $Repo --name $Artifact --dir $AppDir

        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $Current -Recurse -Force -ErrorAction SilentlyContinue
            throw "Artifact download failed; partial current workspace was removed."
        }

        $exe = Get-ChildItem -LiteralPath $AppDir -Recurse -File -Filter "Face LoRA Dataset Selector.exe" | Select-Object -First 1

        @(
            "Face LoRA Dataset Selector QA Candidate"
            "RunId=$($run.databaseId)"
            "Commit=$($run.headSha)"
            "Branch=$($run.headBranch)"
            "Artifact=$Artifact"
            "RunUrl=$($run.url)"
            "Prepared=$(Get-Date -Format o)"
            "AppDir=$AppDir"
            "ScratchDir=$ScratchDir"
            $(if ($null -ne $exe) { "Exe=$($exe.FullName)" } else { "Exe=NOT_FOUND" })
        ) | Set-Content -Path $InfoPath -Encoding UTF8

        Write-Host ""
        Write-Host "QA candidate ready."
        Write-Host "App     : $AppDir"
        Write-Host "Scratch : $ScratchDir"
        if ($null -ne $exe) {
            Write-Host "EXE     : $($exe.FullName)"
        }
        else {
            Write-Warning "Portable EXE was not found after artifact download."
        }
        Write-Host ""
        Write-Host "Next Prepare automatically removes the previous 'current' workspace."
    }
}
