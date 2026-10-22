param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$output = [System.IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $output | Out-Null

$ortVersion = (& python -c "import onnxruntime as ort; print(ort.__version__)" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $ortVersion -ne "1.26.0") {
    throw "NVIDIA accelerator pack requires onnxruntime-gpu 1.26.0; found '$ortVersion'."
}

$providers = (& python -c "import onnxruntime as ort; print(';'.join(ort.get_available_providers()))" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $providers -notmatch 'CUDAExecutionProvider') {
    throw "CUDAExecutionProvider is unavailable in the installed NVIDIA runtime."
}

$ortCapi = (& python -c "import pathlib, onnxruntime; print(pathlib.Path(onnxruntime.__file__).resolve().parent / 'capi')" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ortCapi -PathType Container)) {
    throw "Unable to locate ONNX Runtime native package directory: $ortCapi"
}

$nvidiaRoot = (& python -c "import pathlib, site; roots=[pathlib.Path(p)/'nvidia' for p in site.getsitepackages()]; print(next(str(p) for p in roots if p.is_dir()))" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $nvidiaRoot -PathType Container)) {
    throw "Unable to locate NVIDIA runtime wheel directory: $nvidiaRoot"
}

$ortDestination = Join-Path $output "_internal\onnxruntime\capi"
New-Item -ItemType Directory -Force -Path $ortDestination | Out-Null
$ortFiles = @(
    Get-ChildItem -LiteralPath $ortCapi -File |
        Where-Object { $_.Extension -in @(".dll", ".pyd") }
)
foreach ($file in $ortFiles) {
    Copy-Item -LiteralPath $file.FullName -Destination $ortDestination -Force
}

$cudaProvider = Join-Path $ortDestination "onnxruntime_providers_cuda.dll"
if (-not (Test-Path -LiteralPath $cudaProvider -PathType Leaf)) {
    throw "Accelerator pack is missing onnxruntime_providers_cuda.dll"
}

$nvidiaDestination = Join-Path $output "_internal\nvidia"
$dllCount = 0
foreach ($component in @(Get-ChildItem -LiteralPath $nvidiaRoot -Directory)) {
    $bin = Join-Path $component.FullName "bin"
    if (-not (Test-Path -LiteralPath $bin -PathType Container)) {
        continue
    }

    $dlls = @(Get-ChildItem -LiteralPath $bin -File -Filter "*.dll")
    if (-not $dlls.Count) {
        continue
    }

    $destination = Join-Path $nvidiaDestination ($component.Name + "\bin")
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    foreach ($dll in $dlls) {
        Copy-Item -LiteralPath $dll.FullName -Destination $destination -Force
        $dllCount += 1
    }
}

if ($dllCount -lt 1) {
    throw "Accelerator pack contains no NVIDIA runtime DLLs."
}

@"
Face LoRA Dataset Selector - NVIDIA Accelerator Pack

ORT version: $ortVersion
Providers: $providers
NVIDIA runtime DLLs: $dllCount

安装：
1. 先准备同版本的 Face LoRA Dataset Selector Windows x64 Portable。
2. 完全关闭程序。
3. 将本压缩包内的全部内容解压到 Face-LoRA-Dataset-Selector 根目录。
4. 允许覆盖 _internal\onnxruntime\capi 中的同名文件。
5. 重新启动程序。推理设备保持“自动”时会优先使用 CUDA；GPU 初始化失败时自动回退 CPU。

说明：
- 本加速包不包含另一套应用代码、模型或数据缓存。
- 它只覆盖同版本 ONNX Runtime native binaries，并增加 NVIDIA CUDA/cuDNN runtime DLL。
- 若要恢复纯 CPU 运行时，可重新解压基础 Portable；_userdata 中的用户状态不会因此被删除。
"@ | Set-Content -LiteralPath (Join-Path $output "NVIDIA_ACCELERATOR_PACK_INFO.txt") -Encoding UTF8

$totalBytes = (
    Get-ChildItem -LiteralPath $output -Recurse -File |
        Measure-Object Length -Sum
).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 1)

Write-Host "NVIDIA accelerator pack ready: $output"
Write-Host "ORT native files: $($ortFiles.Count)"
Write-Host "NVIDIA runtime DLLs: $dllCount"
Write-Host "Uncompressed accelerator pack: $totalMB MB"
