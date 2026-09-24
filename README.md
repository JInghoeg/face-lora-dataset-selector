# Face LoRA Dataset Selector

一个面向 **真人 / 人脸 LoRA 数据集** 的本地整理与人工复核工具。

它的目标不是替你“一键决定哪些图最好”，而是把最耗时间、最容易重复劳动的部分先整理好：质量分析、近重复复核、角度与景别覆盖、组合图拆分、自动裁剪建议、文字 / 水印处理，以及最终训练集导出。

**自动化负责减少人工工作量，人负责最终决定。**

<!-- README hero screenshot: docs/assets/readme/hero.png -->

> 当前项目仍处于 v0.3 发布前恢复与人工 QA 阶段。之前发布的 v0.3.0 已撤回；在新的人工 QA 明确通过前，不把任何旧 Release 视为当前稳定版本。

---

## 它能做什么？

### 数据集分析与推荐

对一批真人照片进行本地分析，辅助识别：

- 人脸是否存在、大小是否足够；
- 人脸质量与整图质量；
- 头部朝向；
- 近景 / 半身 / 全身等景别；
- 连拍、视频抽帧和写真图集中的近重复素材。

自动结果会整理成 **推荐 / 备选 / 淘汰**，但所有结果都可以由人重新判断。

### 近重复复核

把视觉上高度相似的图片分组，减少在连拍、抽帧和同套写真里反复比较的时间。

系统会优先把质量更好的候选放在前面，但最终保留哪一张由人决定。

### 组合图拆分

用于处理多视角、多人物或拼接在一起的素材。

系统给出拆分候选后，由人确认真正需要进入数据集的输出，而不是直接把所有检测结果当成最终数据。

### 自动裁剪 + 手动 ROI

对当前推荐图给出保守的自动裁剪建议，并允许人工调整裁剪框。

接受的裁剪不会直接覆盖源图，而是在训练导出时真正落到输出像素。

### 文字 / 水印清理

独立的 Text Cleanup 工作流支持：

- PP-OCRv5 文字区域检测；
- 手动添加、删除和选择区域；
- TELEA；
- Navier-Stokes；
- 可选 MI-GAN AI 修复；
- 预览修复；
- 批量输出到单独目录；
- 长任务进度与取消。

原图不会被文字修复流程覆盖。

### 整理与导出

可按当前人工决定整理活动数据集，并最终导出真正用于训练的图片。

对会移动文件的操作，程序会显式区分并提供预览 / 冲突检查 / 回滚保护；不会把“整理”和“无损分析”混成一个不可逆步骤。

---

## 推荐工作流

当前主流程是：

```text
Analyze / Recommend
        ↓
Duplicate Review
        ↓
Composite Split
        ↓
Auto Crop Review
        ↓
Source Organizer (optional)
        ↓
Final Export
```

Text Cleanup 是独立的可选工作流，可以在需要时单独使用。

<!-- README workflow / feature screenshots:
docs/assets/readme/duplicate-review.png
docs/assets/readme/auto-crop.png
docs/assets/readme/text-cleanup.png
-->

---

## 为什么不是“质量 Top N”？

真人 LoRA 数据集不是单纯把分数最高的图片留下就结束。

如果只按一个总分排序，很容易得到：

- 几乎全是正脸大头照；
- 左 3/4 很多、右 3/4 很少；
- 同一套连拍占据大部分数据；
- 单张图片都不错，但整个数据集覆盖失衡。

因此当前推荐逻辑更接近：

```text
基础可用性检查
→ 质量门槛
→ 近重复组保留代表图
→ 景别 × Yaw 分桶
→ 桶内质量排序
→ 人工最终确认
```

目标是同时兼顾：

**单张素材质量 + 整套数据覆盖 + 人类训练目标。**

---

## 使用的方法

项目没有把某个“总分模型”包装成万能判断器，而是组合多个负责不同问题的方法：

| 负责什么 | 方法 | 用途 |
| --- | --- | --- |
| 人脸检测 | **YuNet** | 判断是否有人脸、脸部大小是否足够 |
| 人脸质量 | **eDifFIQA-T** | 评估脸本身是否适合作为身份训练素材 |
| 整图质量 | **BRISQUE** | 辅助发现明显失真、劣化和低质量图片 |
| 头部朝向 | **3DDFA-V2** | 估计 yaw / pitch / roll，区分正脸、3/4、侧脸 |
| 身体可见范围 | **MediaPipe Pose** | 辅助判断近景、半身、全身等景别 |
| 近重复 | **pHash + 质量排序** | 发现连拍 / 抽帧中的高相似图片 |
| 文字区域 | **PP-OCRv5** | 检测字幕、水印和其他文字区域 |

这些底层方法都有公开论文、官方实现或成熟工程来源；而本项目具体的推荐阈值和组合策略，是针对真人 LoRA 数据集筛选做的工程化设计，不把它们描述成行业统一标准。

参考：

- [eDifFIQA — official repository / IEEE TBIOM](https://github.com/LSIbabnikz/eDifFIQA)
- [BRISQUE — OpenCV Quality](https://docs.opencv.org/4.x/d8/d99/classcv_1_1quality_1_1QualityBRISQUE.html)
- [3DDFA-V2 — ECCV 2020](https://github.com/cleardusk/3DDFA_V2)
- [YuNet — OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- [MediaPipe Pose Landmarker — Google](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)

---

## 下载与安装

### Windows Portable

项目的目标发行形式是 Windows x64 Portable：

```text
Face-LoRA-Dataset-Selector-Windows-x64-Portable.zip
```

解压完整目录后运行：

```text
Face LoRA Dataset Selector.exe
```

Portable 包包含 Python 与运行依赖，不要求用户额外安装 Python，也不要求 NVIDIA GPU / CUDA。

> 当前稳定 Release 暂未重新发布。v0.3 仍在人工 QA 阶段；请不要把已撤回的旧 v0.3.0 包当成当前稳定版本。

### 从源码运行

环境：

- Windows 10 / 11 x64
- Python 3.9–3.12
- 推荐 Python 3.12 x64

最简单的方式：

1. 下载或克隆仓库；
2. 双击 `安装.bat`；
3. 安装完成后双击 `启动.bat`。

安装脚本会在项目目录创建独立的 `.venv`，不会把依赖直接安装进其他 Python 项目。

命令行方式：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

暂不建议 Python 3.13+。

---

## 5 分钟快速开始

### 数据集筛选

1. 选择训练图片目录。
2. 等待初始分析完成。
3. 先查看推荐 / 备选 / 淘汰结果。
4. 进入重复组复核，处理连拍和近重复。
5. 有组合图时进入组合图拆分。
6. 对推荐图进入自动裁剪复核，必要时手动调整 ROI。
7. 如需整理源文件，再单独使用 Source Organizer。
8. 最后导出训练图片。

人工判断始终优先于自动建议。

### 文字 / 水印清理

1. 选择输入目录。
2. 等待文字扫描。
3. 检查检测框，必要时手动增删。
4. 选择 TELEA、Navier-Stokes 或 MI-GAN。
5. 先预览。
6. 再批量输出到新的目录。

如果文字正好压在人眼、五官等关键身份特征上，通常直接弃用该图比强行修复更稳。

---

## 数据安全

这个项目刻意区分 **分析 / 输出** 和 **会移动源文件的显式操作**。

### 默认不会覆盖源图

以下流程不会覆盖原始图片像素：

- 数据集分析；
- 推荐 / 备选 / 淘汰判断；
- 自动裁剪建议；
- 训练导出；
- Text Cleanup 修复输出。

### 会改变文件位置的显式操作

目前需要特别注意两类：

- 接受组合图拆分后，原组合图会被移动到数据集内的隔离目录，新的拆分结果成为活动素材；
- Source Organizer 会在确认计划后，把活动图片移动到对应状态目录。

这类操作会明确提示，并带有冲突检查或回滚保护。

第一次熟悉工作流时，仍建议在数据集副本上操作。

---

## 模型与缓存

项目包含一部分随程序分发的轻量模型，也有少数按需下载的可选模型。

例如 MI-GAN 不直接作为仓库源码的一部分分发。第一次使用相关能力时，如果本地没有对应模型，程序会下载并校验后保存到 FaceLoRA 的模型缓存中。

Windows Portable 下，按需模型缓存与程序 runtime 分开保存，便于后续升级程序时继续复用，而不是每个版本重新下载。

如果可选模型下载失败，其他不依赖该模型的功能仍可继续使用。

---

## 当前边界

当前版本主要针对：

**单人真人 / Face LoRA 数据集。**

它不是：

- 全自动美学选图器；
- 任意类型数据集的通用评分器；
- 任意复杂杂志版式 / 网页拼贴解析器；
- 能完全替代人工检查的数据清洗系统。

明显的 UI 缩略图网格会刻意排除在组合图拆分候选之外；复杂扫描版式仍建议先人工处理。

当前公开开发仍处于 v0.3 人工 QA / release-blocker recovery 阶段。

---

## 文档

README 只负责项目介绍和快速上手。

完整的用户教程 / 使用说明将逐步迁移到 **GitHub Wiki**；Wiki 会单独维护，不作为架构与项目状态的事实源。

开发者文档继续保留在主仓库：

- [Architecture](docs/ARCHITECTURE.md) — 模块边界与依赖方向
- [Module Guide](docs/MODULE_GUIDE.md) — 新增功能模块的固定流程
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md) — Issue / Branch / PR / CI / QA 规则
- [v0.3 Roadmap](docs/ROADMAP_v0.3.md) — 当前开发路线与 release gate
- [ADR-0001](docs/decisions/ADR-0001-modular-monolith.md) — 模块化单体架构决策

第三方模型、组件及许可证信息：

- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

---

## 后续方向

当前优先级仍然是先完成 v0.3 的真实人工 QA 和 release blocker 收口。

已经记录但不会塞进当前 blocker 批次的后续事项包括：

- Text Cleanup / 水印去除模块的复核排序能力；
- 可选 NVIDIA GPU 加速的成本与收益评估；
- 更完整的用户 Wiki；
- 继续完善当前新版 UI 和跨模块一致性。

---

## License

项目自身代码采用 **GNU General Public License v3.0 only（GPL-3.0-only）**。

允许使用、修改、分发和商业使用。分发基于本项目的衍生版本时，需要继续遵守 GPLv3 对源代码和许可证的相关要求。

第三方模型、库和资源继续遵循各自原始许可证。
