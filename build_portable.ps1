$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$build = Join-Path $PSScriptRoot "build"
$dist = Join-Path $PSScriptRoot "dist"

if (Test-Path $build) { Remove-Item $build -Recurse -Force }
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }

python -m PyInstaller --noconfirm --clean portable.spec

$portable = Join-Path $dist "Face-LoRA-Dataset-Selector"
if (-not (Test-Path $portable)) {
    throw "Portable output directory was not created: $portable"
}

Copy-Item "README.md" $portable -Force
Copy-Item "LICENSE" $portable -Force
Copy-Item "THIRD_PARTY_NOTICES.md" $portable -Force

@"
Face LoRA Dataset Selector - Windows x64 Portable

使用方法：
1. 解压整个 ZIP。
2. 双击 “Face LoRA Dataset Selector.exe”。
3. 不需要安装 Python，也不需要 CUDA。

注意：
- 请不要只把 exe 单独复制出去，_internal 目录也是程序的一部分。
- MI-GAN 不随压缩包分发；第一次使用 AI 修复时程序会自动下载并校验模型。
- 原始图片不会被覆盖。
"@ | Set-Content (Join-Path $portable "使用说明.txt") -Encoding UTF8

Write-Host "Portable build ready: $portable"
