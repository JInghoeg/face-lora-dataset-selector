# Face LoRA Dataset Selector v0.2.0

这是第一次面向普通 Windows 用户完整整理的公开发行版。

## 推荐下载

**Windows x64 Portable**

下载 `Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip`，完整解压后直接运行：

`Face LoRA Dataset Selector.exe`

不需要安装 Python，也不需要 CUDA。

## v0.2.0 主要变化

- 新增 Windows x64 Portable 发行包。
- 源码版新增 `安装.bat`，自动创建独立 `.venv` 并安装依赖。
- `启动.bat` 优先使用项目自己的虚拟环境。
- MI-GAN 改为第一次使用 AI 修复时按需自动下载并校验，不随仓库直接分发。
- 修复并收紧文字检测依赖，继续使用内置 PP-OCRv5 ONNX 检测模型。
- 去掉 ImageHash / SciPy 作为 pHash 的运行时依赖，同时保持与旧 pHash 结果的兼容性。
- Portable 使用 PySide6 Essentials，并缩减 MediaPipe、Pillow、OpenCV 等不需要的打包内容。
- Portable 解压体积由最初约 487 MB 降到约 307 MB。
- README 补充适用场景、使用帮助，以及 YuNet、eDifFIQA-T、BRISQUE、3DDFA-V2、MediaPipe Pose 等质量评估设计依据。

## 自动验证

Windows Portable 在 GitHub Actions 中会执行：

- 源码运行时 self-test
- YuNet / eDifFIQA-T / BRISQUE / 3DDFA-V2 / MediaPipe Pose 加载
- PP-OCRv5 合成文字检测
- pHash / OpenCV 图像编解码检查
- 打包后 EXE self-test
- ZIP 生成和 SHA-256 校验

## 注意

- MI-GAN 模型不包含在 Portable ZIP 内；第一次选择 AI 修复时会自动下载约 28 MB。
- 当前发行包未做商业代码签名，部分 Windows 机器第一次运行时可能出现 SmartScreen 提示。
- 原图不会被自动覆盖；筛选导出和文字修复均写入新的输出位置。
