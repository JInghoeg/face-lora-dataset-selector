# Face LoRA Dataset Selector

为 **真人 / 人物 LoRA 训练** 整理图片数据集的 Windows 桌面工具。

当你已经收集了几十、几百张照片，真正麻烦的往往不是开始训练，而是先把素材整理成一套能用的数据集：删掉明显差图和重复图，检查正脸、侧脸、半身、全身是不是太偏科，处理拼图、水印和裁剪，最后把真正要训练的图片导出来。

Face LoRA Dataset Selector 把这些步骤放进一个本地工作流里。自动分析用来缩小范围，最后保留什么仍由你决定。

<!-- README hero screenshot: docs/assets/readme/hero.png -->

## 适合什么人？

如果你正在准备自己的真人 LoRA、角色身份 LoRA，或者其他以人物照片为主要训练素材的微调数据集，这个工具可以用来做训练前的图片整理。

它尤其适合这几种情况：

- 手里已经有大量照片，但不知道该从哪里开始筛；
- 连拍、视频抽帧、写真图集里有很多相似图片；
- 想检查正脸 / 3⁄4 / 侧脸、近景 / 半身 / 全身是否失衡；
- 图片里混有多宫格、多人物、字幕、水印或不理想的构图；
- 不想让一个“自动评分”直接替自己决定训练集，而是希望先自动整理，再人工确认。

---

## 主要功能

### 数据集分析与筛选

程序会分析人脸、画面质量、头部朝向、身体可见范围和近重复关系，并把结果整理成更容易检查的候选。

你可以按这些信息筛选、排序和人工修改结果，而不是从头到尾逐张翻图。

### 近重复处理

连拍、视频抽帧和同一套写真里经常会出现大量“几乎一样”的图片。

程序会把近重复素材找出来，并优先展示更值得保留的候选，方便快速比较。

### 组合图拆分

对于多视角、多人物或拼在一起的素材，可以先生成拆分候选，再由你确认哪些区域值得保留。

不会因为检测到了几个人，就直接把所有区域当成训练图。

### 自动裁剪

对需要收紧构图的图片给出裁剪建议，并允许手动调整 ROI。

裁剪建议本身不会改写原图；只有最终导出训练集时，接受的裁剪才会写入输出图片。

### 字幕 / 水印 / 文字清理

Text Cleanup 可以检测图片中的文字区域，并允许手动增删检测框。

修复方式包括：

- TELEA
- Navier-Stokes
- 可选的 MI-GAN AI 修复

支持预览和批量输出，源图片不会被覆盖。

### 最终整理与导出

完成筛选、重复图复核、拆分和裁剪后，可以把最终保留的素材导出为训练集。

如果你希望把原始素材按状态整理到不同目录，也有单独的 Source Organizer 工作流，并在真正移动文件前给出明确提示。

---

## 一个典型的整理流程

```text
收集到的原始照片
        ↓
初始分析与筛选
        ↓
近重复复核
        ↓
组合图拆分
        ↓
自动裁剪 / 人工调整
        ↓
源文件整理（可选）
        ↓
导出训练集
```

Text Cleanup 是独立功能，需要处理字幕、水印或图片文字时再使用。

<!-- Feature screenshots:
docs/assets/readme/duplicate-review.png
docs/assets/readme/auto-crop.png
docs/assets/readme/text-cleanup.png
-->

---

## 为什么不直接按“质量分数”选前 N 张？

因为训练人物 LoRA 时，单张图片质量高，不代表整套数据集就合适。

如果只按总分选图，很容易出现这样的结果：留下来的几乎全是正脸大头照，同一套连拍占了一大半，侧脸和全身图反而很少。

所以这里不会只看一个分数，而是把几个问题分开处理：

```text
图片是否基本可用
→ 人脸与整图质量
→ 近重复
→ 头部角度
→ 景别 / 身体可见范围
→ 人工确认
```

目标不是替你定义“最好的训练集”，而是让真正需要你判断的图片变少。

---

## 下载

### 当前稳定版：v0.2.0

Windows 用户可以直接下载 Portable 版本：

**[下载 v0.2.0 Release](https://github.com/JInghoeg/face-lora-dataset-selector/releases/tag/v0.2.0)**

下载：

```text
Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip
```

完整解压后运行：

```text
Face LoRA Dataset Selector.exe
```

Portable 版已经包含 Python 和运行依赖，不需要另外安装 Python，也不需要 CUDA。

> v0.2.0 是目前的稳定 Release。当前仓库正在开发 v0.3；组合图拆分、自动裁剪、Source Organizer 等较新的工作流会随下一稳定版本发布。

<details>
<summary><strong>从源码运行</strong></summary>

环境：

- Windows 10 / 11 x64
- Python 3.9–3.12
- 推荐 Python 3.12 x64

下载或克隆仓库后，可以直接运行：

```text
安装.bat
```

安装完成后：

```text
启动.bat
```

也可以手动创建虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

暂不建议 Python 3.13+。

</details>

---

## 快速开始

### 整理 LoRA 数据集

1. 选择训练图片目录。
2. 等待程序完成初始分析。
3. 先处理明显差图和近重复图片。
4. 检查不同头部角度和景别的数量是否失衡。
5. 有组合图时再做拆分，有需要时调整自动裁剪。
6. 最后人工确认并导出训练图片。

自动结果只是辅助。人物一致性、表情、服装、姿态，以及你希望 LoRA 最终学到什么，仍然需要自己判断。

### 清理字幕 / 水印

1. 选择输入图片目录。
2. 等待文字检测完成。
3. 检查检测框，必要时手动添加或删除。
4. 选择修复方式并先看预览。
5. 确认后批量输出到新目录。

如果文字正好覆盖眼睛、五官等关键身份特征，很多时候直接不用这张图会比强行修复更合适。

---

## 分析用了什么？

Face LoRA Dataset Selector 不是依赖一个“万能评分模型”，而是把不同任务交给不同方法：

| 用途 | 方法 |
| --- | --- |
| 人脸检测 | YuNet |
| 人脸质量 | eDifFIQA-T |
| 整图质量 | BRISQUE |
| 头部姿态 / Yaw | 3DDFA-V2 |
| 身体关键点 / 景别辅助 | MediaPipe Pose |
| 近重复 | pHash + 质量排序 |
| 文字区域检测 | PP-OCRv5 |

这些指标负责提供信息和候选排序，不会单独决定一张图片最终该不该进训练集。

如果你想了解这些方法本身：

- [eDifFIQA](https://github.com/LSIbabnikz/eDifFIQA)
- [BRISQUE / OpenCV Quality](https://docs.opencv.org/4.x/d8/d99/classcv_1_1quality_1_1QualityBRISQUE.html)
- [3DDFA-V2](https://github.com/cleardusk/3DDFA_V2)
- [YuNet / OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [MediaPipe Pose Landmarker](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)

---

## 会不会动我的原图？

大多数工作流不会覆盖原始图片。

分析、筛选状态、自动裁剪建议、训练导出和 Text Cleanup 修复都会把结果保存在缓存或新的输出位置。

有两类操作会改变文件位置，因此会明确提示：

- 接受组合图拆分后，原组合图会被移动到数据集内的隔离目录；
- Source Organizer 会在你确认计划后，把活动图片移动到不同状态目录。

第一次使用这类文件整理功能时，建议先拿数据集副本熟悉流程。

---

## 模型下载与缓存

大部分基础功能所需的模型会随程序提供。

少数可选功能会在第一次使用时按需下载模型，例如 MI-GAN。下载完成后会进行完整性校验，并保存到 FaceLoRA 的模型缓存中，之后升级程序时可以继续复用。

可选模型下载失败不会影响与它无关的其他功能。

---

## 当前适用范围

目前主要针对 **单人真人 / Face LoRA 数据集**。

对于二次元角色、纯风格 LoRA、产品数据集或其他类型的训练集，部分功能仍然可以使用，但人脸质量、姿态和景别判断未必有参考意义。

复杂杂志版式、网页拼贴和扫描页也不是当前重点。如果素材结构很复杂，仍建议先做人工整理，再交给筛选流程。

---

## 文档与开发

完整的用户教程会逐步整理到 GitHub Wiki。

如果你想了解项目架构或参与开发：

- [Architecture](docs/ARCHITECTURE.md)
- [Module Guide](docs/MODULE_GUIDE.md)
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)
- [v0.3 Roadmap](docs/ROADMAP_v0.3.md)

第三方模型、组件和许可证信息见：

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

---

## License

本项目代码采用 **GPL-3.0-only**。

你可以使用、修改和分发本项目；如果分发基于本项目的衍生版本，需要继续遵守 GPLv3 的相关要求。

第三方模型、库和资源遵循各自的许可证。
