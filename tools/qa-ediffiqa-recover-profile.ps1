#Requires -Version 5.1
<#
Recovers kernel-execution evidence from the previous failed eDifFIQA probe.
No network, download, model/session creation or GPU execution.
Reads the exact old one-command report and the ORT JSON profile already saved
after three successful session.run calls, before the log-event keyword bug.
#>
[CmdletBinding()]
param(
    [string]$CheckpointRoot = 'G:\ComfyUI-aki\FaceLoRA-DirectML-GPU-Debug\checkpoint',
    [string]$ExpectedArtifactCommit = '9dd48e94e47afebb5eb09d88653156ac07eb1bc9'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$expectedModel = '7a83be63e6583ec5800fa0762e219b65b4b9f1721c4d210bfe2f16c0478832bb'
$helper = @('Shape', 'Size', 'Gather', 'GatherElements', 'Slice',
    'Concat', 'Unsqueeze', 'Squeeze', 'Reshape', 'Flatten', 'Expand',
    'Cast', 'Identity', 'Constant', 'ConstantOfShape')
$gpuMath = @('Conv', 'FusedConv', 'Gemm', 'MatMul', 'FusedMatMul', 'DmlFusedNode', 'DmlFused')

function Assert-WithinRoot([string]$Filename, [string]$Root) {
    $full = [IO.Path]::GetFullPath($Filename)
    $prefix = $Root.TrimEnd([char]'\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing a file outside the existing checkpoint: $full"
    }
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        throw "The earlier probe evidence is missing: $full"
    }
    return $full
}

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$root = [IO.Path]::GetFullPath($CheckpointRoot)
Require (Test-Path -LiteralPath $root -PathType Container) "Existing checkpoint directory is missing: $root"
$systemDrive = [IO.Path]::GetPathRoot($env:SystemRoot)
Require (-not [IO.Path]::GetPathRoot($root).Equals($systemDrive, [StringComparison]::OrdinalIgnoreCase)) 'Refusing system-drive output.'
$prior = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter 'qa-ediffiqa-last-run.json' |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1)
Require ($prior.Count -eq 1) 'No previous one-command report found.'

$output = Join-Path $prior[0].DirectoryName 'qa-ediffiqa-recovered-profile.json'
$recovered = [ordered]@{
    schema_version = 1
    kind = 'ediffiqa-recovered-ort-profile'
    status = 'unverified'
    source_qa_report = $prior[0].FullName
    source_artifact_commit = $null
    source_artifact_run_id = $null
    source_probe_report = $null
    source_execution_profile = $null
    model_sha256 = $null
    inference_runs_returned = 0
    provider_kernel_events = [ordered]@{}
    operators_by_provider = [ordered]@{}
    dml_compute_kernel_events = 0
    cpu_non_helper_ops = @()
    unexpected_cpu_compute_ops = @()
    cpu_gelu_kernel_events = 0
    cpu_nodes_executed = $false
    gpu_compute_verified = $false
    production_mixed_execution_accepted = $false
    performance_verified = $false
    human_qa = 'HUMAN_UNVERIFIED'
    error = $null
}

try {
    $qa = Get-Content -LiteralPath $prior[0].FullName -Raw | ConvertFrom-Json
    Require ($qa.status -eq 'strict_directml_fail') 'Previous QA status was not the expected failed probe.'
    Require ($qa.artifact_commit -eq $ExpectedArtifactCommit) 'The saved QA report is not from the verified previous official-model build.'
    Require ($qa.deployed_model_sha256 -eq $expectedModel) 'Previous QA model SHA did not match.'
    $recovered.source_artifact_commit = $qa.artifact_commit
    $recovered.source_artifact_run_id = $qa.artifact_run_id
    $probeFile = Assert-WithinRoot ([string]$qa.probe_report) $root
    $recovered.source_probe_report = $probeFile
    $details = Get-Content -LiteralPath $probeFile -Raw | ConvertFrom-Json
    Require (@($details.probes).Count -eq 1) 'Expected one production-model probe.'
    $row = $details.probes[0]
    Require ($row.candidate -eq 'upstream_current') 'Probe candidate mismatch.'
    Require ($row.model_sha256 -eq $expectedModel) 'Probe model SHA mismatch.'
    $recovered.model_sha256 = $row.model_sha256
    Require ($row.provider_requested -eq 'directml') 'Probe did not request DirectML.'
    Require (@($row.session_providers) -contains 'DmlExecutionProvider') 'Probe never had a DML session.'
    Require ($row.status -eq 'error') 'This is not the expected profile-saving exception.'
    Require ($row.error.message -match '^append_event\(\) got multiple values for argument .path.$') 'Previous failure was not the known profile_saved keyword bug.'
    $seeds = @($row.outputs | ForEach-Object { [int]$_.seed })
    Require ((@($seeds).Count -eq 3) -and ($seeds[0] -eq 11) -and
        ($seeds[1] -eq 29) -and ($seeds[2] -eq 47)) 'Three completed inference results were not found.'
    $recovered.inference_runs_returned = 3

    $profilePath = Assert-WithinRoot ([string]$row.execution_profile) $root
    $recovered.source_execution_profile = $profilePath
    $events = @(Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json)
    $providers = @{}
    $opsByProvider = @{}
    foreach ($e in $events) {
        if ($e.cat -ne 'Node' -or -not ([string]$e.name).EndsWith('_kernel_time')) { continue }
        if ($null -eq $e.args) { continue }
        $ep = [string]$e.args.provider
        $op = [string]$e.args.op_name
        if (@('DmlExecutionProvider', 'CPUExecutionProvider') -notcontains $ep) { continue }
        if (-not $providers.ContainsKey($ep)) { $providers[$ep] = 0; $opsByProvider[$ep] = @{} }
        $providers[$ep]++
        if (-not $opsByProvider[$ep].ContainsKey($op)) { $opsByProvider[$ep][$op] = 0 }
        $opsByProvider[$ep][$op]++
    }
    $cpuNonHelper = @()
    $mathEvents = 0
    foreach ($ep in @($opsByProvider.Keys | Sort-Object)) {
        $recovered.provider_kernel_events[$ep] = $providers[$ep]
        $sorted = [ordered]@{}
        foreach ($op in @($opsByProvider[$ep].Keys | Sort-Object)) {
            $sorted[$op] = $opsByProvider[$ep][$op]
            if ($ep -eq 'DmlExecutionProvider' -and $gpuMath -contains $op) {
                $mathEvents += $opsByProvider[$ep][$op]
            }
            if ($ep -eq 'CPUExecutionProvider' -and $helper -notcontains $op) {
                $cpuNonHelper += $op
            }
        }
        $recovered.operators_by_provider[$ep] = $sorted
    }
    $recovered.dml_compute_kernel_events = $mathEvents
    $recovered.cpu_non_helper_ops = @($cpuNonHelper | Sort-Object -Unique)
    $recovered.unexpected_cpu_compute_ops = @($cpuNonHelper | Where-Object { $_ -ne 'Gelu' } | Sort-Object -Unique)
    $recovered.cpu_nodes_executed = $providers.ContainsKey('CPUExecutionProvider')
    $convEvents = 0
    $gemmEvents = 0
    $cpuGelu = 0
    if ($opsByProvider.ContainsKey('DmlExecutionProvider')) {
        $dmlOps = $opsByProvider['DmlExecutionProvider']
        if ($dmlOps.ContainsKey('Conv')) { $convEvents = $dmlOps['Conv'] }
        if ($dmlOps.ContainsKey('Gemm')) { $gemmEvents = $dmlOps['Gemm'] }
    }
    if ($opsByProvider.ContainsKey('CPUExecutionProvider')) {
        $cpuOps = $opsByProvider['CPUExecutionProvider']
        if ($cpuOps.ContainsKey('Gelu')) { $cpuGelu = $cpuOps['Gelu'] }
    }
    $recovered.cpu_gelu_kernel_events = $cpuGelu
    # Truthful DML execution evidence does not disappear because CPU Gelu ran.
    $recovered.gpu_compute_verified = ($mathEvents -gt 0)
    $recovered.production_mixed_execution_accepted = (
        $recovered.gpu_compute_verified -and
        $convEvents -gt 0 -and $gemmEvents -gt 0 -and
        @($recovered.unexpected_cpu_compute_ops).Count -eq 0 -and
        $cpuGelu -le $recovered.inference_runs_returned
    )
    if ($recovered.production_mixed_execution_accepted) {
        $recovered.status = if ($cpuGelu -gt 0) {
            'gpu_core_with_cpu_gelu_verified'
        } else {
            'gpu_execution_evidence_recovered'
        }
    } elseif ($recovered.gpu_compute_verified) {
        $recovered.status = 'gpu_compute_verified_cpu_placement_unreviewed'
    } else {
        $recovered.status = 'profile_does_not_prove_gpu_compute'
    }
} catch {
    $recovered.status = 'recovery_error'
    $recovered.error = $_.Exception.Message
} finally {
    $recovered | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $output -Encoding UTF8
    Write-Host "Recovered profile report: $output"
    Write-Host "Status: $($recovered.status); DML arithmetic kernel events: $($recovered.dml_compute_kernel_events)"
}
if ($recovered.production_mixed_execution_accepted) {
    Write-Host "DML core execution confirmed; CPU Gelu events: $($recovered.cpu_gelu_kernel_events). Performance remains unmeasured." -ForegroundColor Green
} else {
    Write-Warning 'Core DirectML/CPU-placement acceptance remains incomplete; see the report. Do not label it a CPU-only run without evidence.'
}
