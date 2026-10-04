# Face LoRA Dataset Selector v0.3.1

发布日期：2026-10-04

v0.3.1 是 v0.3.0 的紧急稳定性补丁。

## 必须升级的原因

v0.3.0 在真实使用中确认存在严重的原生崩溃风险：初始 Dataset Analysis 的后台 QThread 通过无 QObject 上下文的 Python lambda 更新 Qt Widget，可能在工作线程直接进入 QLabel / QProgressBar，最终触发 Windows access violation 并导致程序直接闪退。

v0.3.1 将 Dataset Analysis、Composite Split、Auto Crop、增量分析、Source Organizer 和 Export 的 worker -> UI 通路改为 GUI QObject Slot，并显式使用 Qt QueuedConnection。

## Portable 模型完整性

v0.3.1 Windows Portable 直接包含所有当前确认允许再分发的功能模型：

- DeepGHS person_detect_v1.3_s（Composite Split，MIT）
- DeepGHS head_detect_v2.0_s（Composite Split，MIT）
- skytnt anime-seg ISNetIS（Auto Crop，Apache-2.0）
- MI-GAN migan_pipeline_v2.onnx（Text Cleanup AI Repair，MIT）

构建时下载固定上游文件并验证 SHA-256，打包后再次校验。因此 Composite Split / Auto Crop / MI-GAN 不再在扫描或首次使用途中依赖网络下载。

## Portable 存储修复

v0.3.1 起，程序自身新产生的：

- Dataset cache
- Text Cleanup state
- thumbnails
- runtime / fatal logs
- model cache

全部保存在当前 Portable 文件夹及其子目录。

首次启动 v0.3.1 时，会只读旧 v0.3 的 %LOCALAPPDATA% 状态并将缺失文件非破坏性复制到 Portable 内部；不会删除、移动或覆盖旧记录。

## 数据安全

本补丁不改变 Dataset schema，不重新定义推荐算法，也不覆盖源图片。

原有 v0.3 筛选、人工状态、Composite / Auto Crop 状态和 Text Cleanup 状态继续兼容。
