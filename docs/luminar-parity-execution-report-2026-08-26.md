# Luminar Neo 1.28 UI 优先对齐执行报告（2026-08-26）

> 本文记录本轮实际代码修改、Browser 证据、门禁结果、数据清理、未完成项和下一阶段执行顺序。参考版本固定为 Luminar Neo 1.28.0（build 23071，macOS，zh-Hans）。

## 目录

- [1. 最终结论](#1-最终结论)
- [2. 本轮实际修改](#2-本轮实际修改)
- [3. 执行前后对比](#3-执行前后对比)
- [4. UI 七状态结果](#4-ui-七状态结果)
- [5. 交互、效果、多图和模型结果](#5-交互效果多图和模型结果)
- [6. 数据清理与历史队列审计](#6-数据清理与历史队列审计)
- [7. 完整遗漏确认](#7-完整遗漏确认)
- [8. 下一阶段可执行顺序](#8-下一阶段可执行顺序)
- [9. 验证入口](#9-验证入口)

---

## 1. 最终结论

本轮完成了 UI 优先计划的代码修改和全量复验，但项目仍未达到“与本机 Luminar Neo 绝对对齐”。最终 exact 质量门禁为 28 项中 22 项通过，仍有 5 个必需门禁和 1 个可选门禁失败。

必需阻断项：

1. multi-image
2. output-parity
3. exact-incremental-parity
4. ui-parity
5. interaction-execution

可选阻断项为 model-contract-inventory。

产品范围门禁、UI 当前构建证据、Python/前端测试、静态检查、实际调用模型契约和模型管线审计均通过。未通过项没有被降级、跳过或伪造为通过。

最终汇总：

- test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-ui-first-execution-final.json
- test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-ui-first-final.json
- test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-ui-first-final.json

## 2. 本轮实际修改

### 2.1 编辑工作区共享壳层

frontend/src/styles.css 对齐了固定 56px 顶栏、76px 右侧工作区导航、图层栏、预览顶部位置、胶片栏、底部控制栏、工具侧栏、目录网格和中性色背景。

预览几何在 1440×900 逻辑视口下收敛到原生参考附近：

- 预览左上位置约为 x=332, y=74。
- 胶片缩略图顶部约为 y=760。
- 底部控制栏顶部约为 y=824。

frontend/src/components/PreviewPanel.tsx 将当前选中照片稳定放在可见胶片栏末端，并保持真实选图行为；缩放和平移状态仍由组件自身维护。

frontend/src/components/ToolPanel.tsx 不再在工具初始态错误高亮默认能力；已有黑白“先转换为黑白”前置条件继续保留。

### 2.2 多图工作区

frontend/src/components/WorkflowWorkspace.tsx 从无样式的浏览器默认表单改为与 Luminar 目录工作区同构的界面：

- 目录式左侧栏。
- HDR、焦点堆叠、全景拼接工作流入口。
- 真实多文件选择和缩略图。
- 选择计数、取消选择、运行、预览和导出状态。
- 原生风格底部控制栏。

该修改没有引入仅为截图服务的假数据，也没有绕过真实 File[] -> onRun -> preview -> export 数据流。

frontend/src/components/Icon.tsx 增加搜索和图片空态图标，避免多图工作区使用文字占位。

### 2.3 Browser 证据

Codex In-app Browser 本轮可用。页签不能跨调用稳定保留，因此采用单次调用内完成导航、状态建立和截图写入的方式。

固定环境：

- 逻辑视口：1440×900。
- 物理候选：2880×1800。
- Browser：Codex In-app Browser 26.818.22352。
- 语言：zh-Hans。
- 时区：Asia/Shanghai。
- 2× 候选由逻辑截图确定性 Lanczos 派生。

最终 7 个截图全部通过当前构建哈希、原始截图哈希、派生关系和参考 fixture 校验。

## 3. 执行前后对比

| 验收域 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| exact 质量门禁 | 21/28 | 22/28 | 产品范围修复后增加 1 项；整体仍阻断 |
| UI 当前构建证据 | 0/7 | 7/7 | 已闭环 |
| UI 像素门禁 | 0/7 | 0/7 | 证据可信，但像素仍未达标 |
| edit UI MAE | 0.147445 | 0.030773 | 显著下降，距 0.03 上限约 0.000773 |
| multi-image UI MAE | 0.110286 | 0.072490 | 已完成结构重做，仍缺原生三图状态 |
| 原生交互 | 8/10 | 8/10 | 缺 2 条原生观察 |
| Browser 交互 | 1/10 | 1/10 | 缺 9 条当前 Browser 执行记录 |
| 主效果 | 36/45 | 36/45 | 9 项仍失败 |
| exact 效果 | 38/69 | 38/69 | 31 项仍失败 |
| 多图工作流 | 1/3 | 2/3 | HDR、焦点堆叠通过；全景失败 |
| Python 测试 | 290/290 | 290/290 | 通过 |
| 前端测试 | 13/13 | 13/13 | 通过 |
| Ruff | 通过 | 通过 | 通过 |
| 前端生产构建 | 通过 | 通过 | 通过 |
| 可再生成工作区 | 2 个 | 0 个 | 已释放 171,255,172 字节 |

## 4. UI 七状态结果

阈值来自 configs/parity.yaml：MAE 不高于 0.03，changed pixel ratio 不高于 0.02。

| 状态 | 最终 MAE | Changed pixel ratio | 状态 | 主要差异 |
|---|---:|---:|---|---|
| catalog | 0.150737 | 0.769110 | 失败 | 当前目录为扁平 46 图；原生参考含 66 图、文件夹/相册层级和不同排序 |
| presets | 0.092873 | 0.524677 | 失败 | 当前仍使用旧免费预置分类；原生为推荐、已购买、基本功能、新品结构 |
| edit | 0.030773 | 0.317442 | 失败 | 主几何已接近；字体栅格、底栏控制组、图片重采样仍不同 |
| layer-stack | 0.030773 | 0.317442 | 失败 | 原生参考与 edit 图像相同；同受 edit 剩余误差影响 |
| layer-library | 0.052385 | 0.445854 | 失败 | 图层素材库宽度、内容卡片和控制密度仍不同 |
| tool-expanded | 0.037263 | 0.354837 | 失败 | 工具检查器层级、滑杆、字体和间距未完全一致 |
| multi-image | 0.072490 | 0.736189 | 失败 | 结构已对齐；Browser 无文件上传接口，最终证据是可信空态而不是伪造三图态 |

edit 已进入最后的共享壳层微调阶段；catalog、presets、multi-image 仍是数据模型和状态建立问题，继续只调 CSS 不会得到可信的绝对对齐。

## 5. 交互、效果、多图和模型结果

### 5.1 交互

原生 10 条契约通过 8 条，缺少：

1. layer-add-reorder-opacity-delete
2. multi-image-workflow

现有原生观察脚本对这两条返回 unsupported，不能通过重复运行已有脚本补齐。

Browser 当前只有 edit-toggle-collapse 完整执行证据。其余 9 条缺少执行记录；其中图层和多图还同时缺少原生观察。

本轮 Browser 插件可以点击、输入、截图和读取 DOM，但没有 setInputFiles，页面 evaluate 环境也不暴露 File、Blob、DataTransfer 或 fetch。因此没有伪造多图文件状态。

### 5.2 效果与无变化导出

主效果保持 36/45，失败能力为：

- face_ai
- slim_people
- depth_volume
- lut_mapping
- blue_hour
- fog
- sky_replace
- sunrays 两个样例

exact 保持 38/69，31 个失败覆盖 25 个能力族。

sampling-effect-change-audit.json 识别出 10 个 invalid-unchanged-export，其中包含：

- 黑白未完成“转换为黑白”的旧流程。
- 降噪未选择等级的旧流程。
- LUT、Magic Lights、Neon Light 和部分人像能力未产生有效变化的旧结果。

这些记录不应被视为有效效果参考。它们暂时保留为失败证据；在同一 record 获得按正确交互产生的有效替代结果之前，不应直接删除状态与失败审计，否则会丢失问题归因。

### 5.3 多图

| 工作流 | 状态 | MAE | SSIM |
|---|---|---:|---:|
| HDR merge | 通过 | 0.025352 | 0.992789 |
| Focus stacking | 通过 | 0.009250 | 0.994731 |
| Panorama stitching | 失败 | 0.081941 | 0.815541 |

全景剩余问题属于几何估计、变换、接缝、曝光补偿和裁切链，而不是 UI 问题。

### 5.4 模型与长耗时任务

- 实际模型管线：12 ready、0 blocked、0 failed。
- 实际被候选效果调用的模型：16/16 契约通过。
- 模型支撑的 active cases：22/22 通过。
- 全注册表：92 个模型均有基础契约，26 个有模型特定契约，66 个仍 pending，故可选 exact 模型库存门禁阻断。
- 长任务租约、心跳、防重复领取、输出契约、模型 lease 和资源释放测试均包含在 290 个 Python 测试中并通过。

本轮没有宣称真实权重的 92 个模型全部 runtime-ready；当前审计明确为 0 个全量 runtime-ready。

## 6. 数据清理与历史队列审计

### 6.1 已执行清理

精确删除了两个可再生成工作区：

- diagnostics/overlay-workspace/workspace
- diagnostics/ui-workspace/workspace

释放 171,255,172 字节。清理后 dry-run 为 0 路径、0 字节。

保留 canonical captures、native exports、current candidate outputs、versioned references、源数据集和每个失败记录最近三组稳定性帧。

这些工作区只能通过重新导入或渲染生成，不能从回收站恢复；它们不属于原生参考或唯一采样。

### 6.2 活跃队列

最终存储审计：

- 活跃队列记录：251。
- 缺失状态：0。
- 活跃记录 ready：251。
- 孤立状态：100，主要为 calibration 和 exact 历史记录。
- capture 根目录：3,204,133,331 字节。

安全清理脚本将 495 个历史路径、880,912,942 字节列为“非活跃队列路径”，但其中包含当前 exact/calibration 报告仍引用的原生输出和状态。本轮没有执行删除，避免破坏现有效果参考链。

### 6.3 物理重复

存储审计发现 195 个相同字节组、425 个额外物理副本，理论重复字节为 435,961,313。

这些文件大多是不同采样记录独立保存的 before 截图、export/native-export 配对、attempt 日志和状态审计。现有 prune_redundant_native_exports.py 认定可安全删除的 redundant exports 和 transient paths 均为 0，因此本轮未按纯哈希重复直接删除。

## 7. 完整遗漏确认

以下事项继续阻断“绝对对齐”：

1. UI 像素门禁 0/7；尤其 catalog、presets、multi-image 需要先对齐数据模型和状态。
2. 原生交互缺图层和多图两条观察。
3. Browser 交互缺 9 条执行证据。
4. 黑白转换、降噪等级、恢复原图和导出前效果变化虽已有代码或采样规则，但 10 个旧无变化结果尚未由有效结果替换。
5. 主效果 9 个失败，exact 31 个失败。
6. Panorama stitching 未通过。
7. 66 个非活跃模型缺模型特定契约。
8. 100 个历史 orphan capture states 尚未迁移到显式 archive manifest。
9. 未完成两个独立的全绿 release run；当前多次 exact run 结果稳定为 blocked。

## 8. 下一阶段可执行顺序

### P0：前端状态和数据模型

1. 给 catalog record 增加 folder_id、album_id、relative_path、稳定导入顺序和相册计数；使用现有 46 图重建“夏日户外拍照”状态，不重复采样。
2. 将 preset inventory 从旧免费分类替换为 1.28 的推荐、购买、基本功能、新品结构；效果图只能来自现有 preset preview API，不放静态假图。
3. 为 Browser 增加受控的文件输入测试通道，或升级 Browser 控制层支持真实 setInputFiles；然后建立三图 HDR 状态。
4. 完成 edit 的最后共享几何修正，再统一 layer/tool 状态，避免逐页补丁。

### P1：交互证据

1. 为原生观察器实现图层新增、排序、50% 不透明度和删除处理器。
2. 为原生观察器实现复用已有 HDR 项目的多图处理器，不重复执行已有长耗时采样。
3. 按 10 条契约生成 Browser raw trace，并同时记录 API 响应、项目状态和最终截图。
4. 导出契约必须验证：存在可恢复原图状态、效果区域变化超过阈值、文件名写入后读回一致、取消或完成后退出导出页。

### P2：无变化样本和效果

1. 先修正确认交互：黑白必须转换，降噪必须选等级，所有输入必须恢复原图。
2. 仅对 10 个 invalid record 执行定向修复采样；其余 241 个 active record 不重复采样。
3. 新结果通过 source-change gate 后，使旧 canonical 失效，再运行安全清理。
4. 按能力族修复 9 个主失败，再处理 exact 的剩余参数点。

### P3：多图、模型和发布

1. 单独修复 panorama 的特征匹配、稳健变换、接缝、曝光补偿和裁切。
2. 只为实际启用的模型建立模型特定契约；不为 66 个未启用模型制造空壳 runtime-ready 状态。
3. 为 100 个 orphan states 生成 archive manifest，验证无报告引用后再运行 stale prune。
4. 连续执行两次 exact/release gate；仅当两次都为 0 必需失败时声明绝对对齐。

## 9. 验证入口

- Python：.venv/bin/pytest
- 静态检查：.venv/bin/ruff check .
- 前端测试：cd frontend 后执行 npm test -- --run
- 前端构建：cd frontend 后执行 npm run build
- UI 证据：.venv/bin/python scripts/validate_ui_execution_evidence.py
- UI 像素：.venv/bin/python scripts/validate_ui_references.py
- 原生交互：.venv/bin/python scripts/validate_interaction_execution.py --native-only
- 完整交互：.venv/bin/python scripts/validate_interaction_execution.py
- 多图：.venv/bin/python scripts/run_multi_image_workflow_smoke.py
- 模型契约：.venv/bin/python scripts/check_model_contracts.py
- 实际模型调用：.venv/bin/python scripts/audit_candidate_model_invocations.py --require-active-contracts
- 最终门禁：.venv/bin/python scripts/run_quality_gates.py --level exact
