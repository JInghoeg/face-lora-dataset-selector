<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US" sourcelanguage="zh_CN">
  <context>
    <name>AutoCropReviewDialog</name>
    <message><source>自动裁剪复核</source><translation>Auto Crop Review</translation></message>
    <message><source>蓝虚线＝自动建议 ｜ 绿框＝当前裁剪框（可拖动 / 四边四角缩放）</source><translation>Blue dashed = automatic proposal | Green = current crop (drag or resize from edges/corners)</translation></message>
    <message><source>当前裁剪结果</source><translation>Current Crop Result</translation></message>
    <message><source>选择自动裁剪候选</source><translation>Select an Auto Crop candidate</translation></message>
    <message><source>候选</source><translation>Candidates</translation></message>
    <message><source>接受当前裁剪框</source><translation>Accept Current Crop</translation></message>
    <message><source>重置为自动建议</source><translation>Reset to Automatic Proposal</translation></message>
    <message><source>保留原图</source><translation>Keep Original</translation></message>
    <message><source>恢复待定</source><translation>Restore Pending</translation></message>
    <message><source>关闭</source><translation>Close</translation></message>
    <message><source>当前裁剪结果预览</source><translation>Current Crop Preview</translation></message>
    <message><source>无建议</source><translation>No proposal</translation></message>
    <message><source>已接受</source><translation>Accepted</translation></message>
    <message><source>待定</source><translation>Pending</translation></message>
    <message><source> · 手调</source><translation> · Manual</translation></message>
    <message><source>{count} 张</source><translation>{count} items</translation></message>
    <message><source>当前没有自动裁剪候选</source><translation>No Auto Crop candidates</translation></message>
    <message><source>手动调整</source><translation>Manual adjustment</translation></message>
    <message><source>自动建议</source><translation>Automatic proposal</translation></message>
    <message><source>无</source><translation>None</translation></message>
    <message><source>{state}{edited} · 去除 {ratio}</source><translation>{state}{edited} · Removed {ratio}</translation></message>
    <message><source>原图 {width} × {height} → 当前 {crop_width} × {crop_height} · 去除 {removed}</source><translation>Original {width} × {height} → Current {crop_width} × {crop_height} · Removed {removed}</translation></message>
    <message><source>状态：{state} · 当前框：{kind}</source><translation>Status: {state} · Crop: {kind}</translation></message>
    <message><source>alpha≥{alpha} · padding {padding}px</source><translation>alpha≥{alpha} · padding {padding}px</translation></message>
    <message><source>提示：{warning}</source><translation>Notes: {warning}</translation></message>
    <message><source>主体遮罩触及原图边缘</source><translation>Subject mask touches the source edge</translation></message>
    <message><source>裁剪框无效</source><translation>Invalid Crop</translation></message>
    <message><source>无法重置裁剪框</source><translation>Unable to Reset Crop</translation></message>
    <message><source>切换到浅色模式</source><translation>Switch to Light Mode</translation></message>
    <message><source>切换到深色模式</source><translation>Switch to Dark Mode</translation></message>
  </context>
  <context>
    <name>CompositeSplitReviewDialog</name>
    <message><source>组合图拆分复核</source><translation>Composite Split Review</translation></message>
    <message><source>建议输出预览（默认全选；取消勾选 = 生成后直接送入淘汰）</source><translation>Suggested output preview (all selected by default; uncheck to send the generated output directly to Rejected)</translation></message>
    <message><source>接受建议</source><translation>Accept Suggestion</translation></message>
    <message><source>拒绝</source><translation>Reject</translation></message>
    <message><source>恢复待定</source><translation>Restore Pending</translation></message>
    <message><source>关闭</source><translation>Close</translation></message>
    <message><source>当前没有待复核的组合图拆分推荐图</source><translation>No recommended images are awaiting Composite Split review</translation></message>
    <message><source>已接受</source><translation>Accepted</translation></message>
    <message><source>已拒绝</source><translation>Rejected</translation></message>
    <message><source>待定</source><translation>Pending</translation></message>
    <message><source>拆分</source><translation>Split</translation></message>
    <message><source>群组裁剪</source><translation>Group Crop</translation></message>
    <message><source>{mode} · {count} 个输出</source><translation>{mode} · {count} outputs</translation></message>
    <message><source>拆成独立人物/视角</source><translation>Split into individual subjects/views</translation></message>
    <message><source>重叠多人合并裁剪</source><translation>Combined crop for overlapping subjects</translation></message>
    <message><source>{mode} · 输出 {count} 张</source><translation>{mode} · {count} outputs</translation></message>
    <message><source>状态：{state}</source><translation>Status: {state}</translation></message>
    <message><source>推荐</source><translation>Recommended</translation></message>
    <message><source>淘汰</source><translation>Rejected</translation></message>
    <message><source>输出 {index}</source><translation>Output {index}</translation></message>
  </context>
  <context>
    <name>MainWindow</name>
    <message><source>LoRA 数据集筛选与字幕清理</source><translation>LoRA Dataset Selector &amp; Text Cleanup</translation></message>
    <message><source>LoRA 数据集筛选</source><translation>LoRA Dataset Selector</translation></message>
    <message><source>批量去字幕 / 水印</source><translation>Batch Text / Watermark Cleanup</translation></message>
    <message><source>组合图拆分 复核…</source><translation>Composite Split Review…</translation></message>
    <message><source>组合图拆分 复核… ({total} / 待定 {pending})</source><translation>Composite Split Review… ({total} / Pending {pending})</translation></message>
    <message><source>请先完成组合图拆分</source><translation>Complete Composite Split First</translation></message>
    <message><source>还有 {count} 张推荐图等待组合图拆分复核。\n\n自动裁剪只处理组合图拆分之后的单主体推荐图。</source><translation>{count} recommended images are still waiting for Composite Split review.\n\nAuto Crop only processes single-subject recommended images after Composite Split.</translation></message>
    <message><source>当前推荐图片中没有检测到需要组合图拆分的图片。</source><translation>No current recommended images require Composite Split.</translation></message>
    <message><source>组合图拆分扫描准备中：{todo} 张待检查</source><translation>Preparing Composite Split scan: {todo} images to check</translation></message>
    <message><source>组合图拆分 {current}/{total}：{name}</source><translation>Composite Split {current}/{total}: {name}</translation></message>
    <message><source>组合图拆分扫描完成：{count} 张推荐候选</source><translation>Composite Split scan complete: {count} recommended candidates</translation></message>
    <message><source>组合图拆分扫描失败</source><translation>Composite Split Scan Failed</translation></message>
    <message><source>组合图拆分写入失败</source><translation>Composite Split Write Failed</translation></message>
    <message><source>还有组合图拆分待复核</source><translation>Composite Split Review Pending</translation></message>
    <message><source>推荐图片中还有 {count} 张组合图拆分建议未确认。\n\n请先完成组合图拆分复核，再导出训练图片。</source><translation>{count} recommended images still have unconfirmed Composite Split suggestions.\n\nComplete Composite Split review before exporting training images.</translation></message>
    <message><source>已导出 {count} 张当前推荐图片。\n\n组合图拆分已在前置阶段实体化，隔离原图不会进入导出。\n源图片未被修改。</source><translation>Exported {count} current recommended images.\n\nComposite Split outputs were materialized earlier in the workflow; archived originals are excluded from export.\nSource images were not modified.</translation></message>
    <message><source>自动裁剪 复核…</source><translation>Auto Crop Review…</translation></message>
    <message><source>自动裁剪 复核… ({total} / 待定 {pending} / 未扫 {todo})</source><translation>Auto Crop Review… ({total} / Pending {pending} / Unscanned {todo})</translation></message>
    <message><source>自动裁剪 复核…（未扫 {todo}）</source><translation>Auto Crop Review… (Unscanned {todo})</translation></message>
    <message><source>没有数据</source><translation>No Data</translation></message>
    <message><source>请先完成图片分析。</source><translation>Please complete image analysis first.</translation></message>
    <message><source>请先完成 Composite Split</source><translation>Complete Composite Split First</translation></message>
    <message><source>还有 {count} 张推荐图等待 Composite Split 复核。\n\n自动裁剪只处理 Composite 之后的单主体推荐图。</source><translation>{count} recommended images are still waiting for Composite Split review.\n\nAuto Crop only processes single-subject recommended images after Composite Split.</translation></message>
    <message><source>没有候选</source><translation>No Candidates</translation></message>
    <message><source>当前推荐图片没有需要自动裁剪复核的候选。</source><translation>No current recommended images require Auto Crop review.</translation></message>
    <message><source>自动裁剪扫描准备中：{todo} 张；首次使用如未缓存会下载 ISNetIS 模型</source><translation>Preparing Auto Crop scan: {todo} images. ISNetIS will be downloaded on first use if not cached.</translation></message>
    <message><source>自动裁剪 {current}/{total}：{name}</source><translation>Auto Crop {current}/{total}: {name}</translation></message>
    <message><source>自动裁剪扫描完成：新扫 {scanned} · 候选 {candidates} · 无需裁 {no_candidate} · 已缓存 {cached}</source><translation>Auto Crop scan complete: Scanned {scanned} · Candidates {candidates} · No crop needed {no_candidate} · Cached {cached}</translation></message>
    <message><source>自动裁剪扫描失败</source><translation>Auto Crop Scan Failed</translation></message>
    <message><source>还有自动裁剪未扫描</source><translation>Auto Crop Scan Incomplete</translation></message>
    <message><source>推荐图片中还有 {count} 张未完成自动裁剪扫描。\n\n请先完成自动裁剪，再导出训练图片。</source><translation>{count} recommended images have not completed Auto Crop scanning.\n\nComplete Auto Crop before exporting training images.</translation></message>
    <message><source>还有自动裁剪待复核</source><translation>Auto Crop Review Pending</translation></message>
    <message><source>推荐图片中还有 {count} 张自动裁剪候选未确认。\n\n请接受裁剪或选择保留原图后再导出。</source><translation>{count} Auto Crop candidates are still unconfirmed.\n\nAccept the crop or choose Keep Original before exporting.</translation></message>
  </context>
</TS>
