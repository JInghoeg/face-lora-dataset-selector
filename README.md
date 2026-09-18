# Face LoRA Dataset Selector

一个面向 **人脸 / 真人 LoRA 数据集** 的 Windows 本地筛选工具。它把质量评估、重复检测、姿态覆盖和人工复核放在同一个桌面界面里，目标不是“全自动替你决定”，而是先把明显问题和高价值候选整理出来，再由人做最后确认。

## 主要功能

- **人脸质量与基础质量检查**：YuNet、eDifFIQA-T、BRISQUE、Sharpness、曝光、人脸像素与占比。
- **姿态与景别分析**：3DDFA-V2 估计 Yaw / Pitch / Roll，MediaPipe Pose 辅助判断近景、半身、大半身、全身。
- **近重复检测**：基于 pHash 分组，并优先保留组内质量更高的图片。
- **自动推荐 + 人工状态**：推荐 / 备选 / 淘汰，人工修改优先于自动结果，可随时恢复自动判断。
- **筛选与排序**：按状态、景别、Yaw、Pitch、Face Quality、BRISQUE、Sharpness、Duplicate Group 等查看。
- **安全导出**：源图片只读，导出时复制到新目录，不覆盖原图。
- **批量文字 / 水印处理**：PP-OCRv5 检测文字区域，支持人工增删区域，以及 TELEA / Navier-Stokes 修复；MI-GAN 为可选修复模型。

## 当前适用范围

当前版本主要针对 **单人真人图片数据集**。自动指标只是辅助筛选依据，不应被当作绝对审美评分；最终是否进入训练集仍建议人工确认。

## 环境

当前公开版面向：

- Windows 10 / 11 x64
- Python 3.9–3.12
- 推荐 Python 3.12 x64

v0.1.0 暂不建议使用 Python 3.13+。默认依赖使用 CPU 版 ONNX Runtime，不要求 CUDA。

## 安装

克隆或下载仓库后，在项目目录执行。推荐使用 Python 3.12：

```powershell
py -3.12 -m pip install -r requirements.txt
```

如果 `python --version` 已确认是 Python 3.9–3.12，也可以：

```powershell
python -m pip install -r requirements.txt
```

## 启动

```powershell
python app.py
```

或直接双击：

```text
启动.bat
```

`启动.bat` 会按 3.12 → 3.11 → 3.10 → 3.9 的顺序寻找可用 Python；如果找不到受支持版本，会提示安装 Python 3.12 x64。

## 模型说明

公开版仓库会保留运行筛选流程所需的轻量模型 / 资源。模型与第三方组件仍遵循各自原始许可证，详见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

### MI-GAN（可选）

AI 修复使用的 `migan_pipeline_v2.onnx` **不随公开仓库直接分发**。

首次使用 **AI 修复（MI-GAN）** 时，如果本地没有该模型，程序会自动从上游下载约 28 MB 的模型文件到：

```text
models/migan_pipeline_v2.onnx
```

下载完成后会校验文件大小与 SHA-256，校验通过后才会加载。下载失败时仍可继续使用 **TELEA** 或 **Navier-Stokes** 修复。

上游模型页面：

https://huggingface.co/andraniksargsyan/migan/blob/main/migan_pipeline_v2.onnx

## 数据与缓存

- 原始图片不会被覆盖。
- LoRA 推荐导出只会复制当前“推荐”状态的图片。
- 文字修复批处理只写入用户指定的新目录。
- 程序会在项目目录创建 `cache/` 保存分析结果和缩略图，以减少重复分析。删除该目录不会影响原图，只会让相关内容在下次使用时重新分析。

## 许可证

本项目自身代码采用 **GNU General Public License v3.0 only（GPL-3.0-only）**。

你可以使用、修改、分发和商业使用本项目；如果分发基于本项目的衍生版本，需要遵守 GPLv3 的源代码公开与同许可证要求。

第三方模型、库和资源不因本项目使用 GPL-3.0-only 而改变其原始许可证，详见 `THIRD_PARTY_NOTICES.md`。

## 当前状态

当前版本适合在 Windows 本地完成 **单人真人 Face LoRA 数据集** 的质量筛选、重复检测、姿态覆盖检查、人工复核、导出，以及文字 / 水印区域处理。

目前尚未内置多宫格自动拆分和杂志页主体裁取；这类素材建议先完成拆分或裁取，再导入筛选流程。
