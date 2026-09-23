$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -c "import qfluentwidgets" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Missing Fluent UI runtime. Run: python install_ui_dependencies.py"
}

python compile_translations.py
if ($LASTEXITCODE -ne 0) {
    throw "Qt translation compilation failed."
}

$build = Join-Path $PSScriptRoot "build"
$dist = Join-Path $PSScriptRoot "dist"

if (Test-Path $build) { Remove-Item $build -Recurse -Force }
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }

# MediaPipe's package __init__ files eagerly import every task family
# (audio/text/all vision tools), even though this app only uses PoseLandmarker.
# For packaging only, temporarily make those two initializers lazy/empty so
# PyInstaller follows the actual imports instead of bundling unrelated modules.
$mpRoot = python -c "import pathlib, mediapipe; print(pathlib.Path(mediapipe.__file__).parent)"
$mpRoot = $mpRoot.Trim()
$mpInitFiles = @(
    (Join-Path $mpRoot "tasks\python\__init__.py"),
    (Join-Path $mpRoot "tasks\python\vision\__init__.py")
)
$mpBackups = @{}

try {
    foreach ($file in $mpInitFiles) {
        if (-not (Test-Path $file)) {
            throw "MediaPipe package initializer not found: $file"
        }
        $mpBackups[$file] = Get-Content $file -Raw
        "# Portable build: intentionally minimal package initializer." | Set-Content $file -Encoding UTF8
    }

    python -m PyInstaller --noconfirm --clean portable.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    foreach ($file in $mpBackups.Keys) {
        $mpBackups[$file] | Set-Content $file -Encoding UTF8 -NoNewline
    }
}

$portable = Join-Path $dist "Face-LoRA-Dataset-Selector"
if (-not (Test-Path $portable)) {
    throw "Portable output directory was not created: $portable"
}

# This application reads image files only; it never opens video streams.
# OpenCV's FFmpeg plugin is therefore unused but costs about 27 MB unpacked.
$ffmpeg = Get-ChildItem (Join-Path $portable "_internal\cv2") -Filter "opencv_videoio_ffmpeg*.dll" -ErrorAction SilentlyContinue
foreach ($file in $ffmpeg) {
    Remove-Item $file.FullName -Force
    Write-Host "Removed unused OpenCV video codec: $($file.Name)"
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
- Composite Split 人物/头部检测模型不随压缩包分发；第一次使用 Composite Split 时会自动下载并缓存。
- Auto Crop 的 ISNetIS 模型不随基础压缩包分发；第一次使用自动裁剪时会自动下载并做完整性校验。
- 训练导出、文字修复和自动裁剪不会覆盖源图片像素。
- 接受组合图拆分会把原组合图移入 _CompositeSplit_Originals；“整理源文件”会在你确认后真实移动文件位置。
"@ | Set-Content (Join-Path $portable "使用说明.txt") -Encoding UTF8

Write-Host "Portable build ready: $portable"
