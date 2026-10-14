# Luminar Neo 1.28 绝对对齐执行报告（第四轮，2026-08-27）

## 1. 结论

本轮完成了 UI/交互参考扩展、核心前端页面重构、原生交互闭环、Luminar 1.28 素材版本锁定、预设原生封面接入和全量工程回归，但项目仍未达到“绝对对齐”的最终发布条件。

当前必须区分三种结论：

1. **代码与资产完整性通过**：Python 305/305、前端 22/22、Ruff、TypeScript 与 Vite 生产构建通过；天空、图层叠加、LUT 和预设图像资产对齐门禁通过。
2. **原生状态合同显著补齐**：原生 UI 参考由 7 个扩展到 16 个，Native interaction 由 8/10 提升到 10/10。
3. **严格产品对齐仍 blocked**：主效果仍为 29/40、Exact 38/69、UI pixel 0/16、Browser interaction 1/10、多图 2/3。UI 当前只实拍复核了本轮直接改动的工具页和预设页，尚未正式重录完整 16 状态并重建 hash 链。

因此，本轮可以声明“核心 UI、交互和原生素材对齐实现已推进并可运行”，不能声明“已与 Luminar Neo 绝对一致”。

## 2. 冻结目标与素材真值

唯一目标为本机：

- 应用：`/Applications/Luminar Neo.app`
- 版本：`1.28.0`
- build：`23071`
- 平台：macOS
- 语言/时区：`zh-Hans` / `Asia/Shanghai`
- UI：logical 1440×900、DPR 2、physical 2880×1800

用户补充的 Portable 路径已完成只读审计。目录名包含 `1.28.0.17626`，但内部 `AppInfo/appinfo.ini` 实际声明 `1.27.1.17225 x64`。它不能成为目标版本的覆盖源，只能作为交叉证据。

本轮最终采用以下策略：

1. 所有导入素材只从本机 `1.28.0-23071` 应用读取；
2. Portable 不执行批量复制、不覆盖本机 1.28 素材；
3. Portable 中与 1.28 相同 UUID 的 121 个预设图标与本机图标 hash 一致，仅作为旁证；
4. 所有素材导入均生成版本和 hash 索引，并由独立门禁复核。

## 3. 本轮完成项

### 3.1 原生 UI 与交互参考

- 原生 UI 状态扩展为 16 个：catalog、presets、edit、layer-stack、layer-library、tool-expanded、edit-history、more-panel、info-panel、edit-collapsed、black-white-before-conversion、black-white-after-conversion、denoise-level-selected、export-dialog、multi-image、multi-image-complete。
- Native interaction 10/10，issue 0。
- 新增真实图层流程：添加、排序、50% 透明度、删除，预览 hash 变化可证。
- 新增真实 HDR 流程：选择 3 帧、创建 HDR、生成结果、打开并取消导出，且无重复导出。
- 黑白、降噪、导出、编辑历史和多图完成态具备原生观察证据。

### 3.2 目录与编辑器状态

- 目录默认按 `added_at` 排序，单击只选择并停留在目录，进入工具后才切换编辑器。
- 隔离 UI 验证目录已使用 46 条真实记录。
- 开发前端支持独立 API target，避免污染用户原有 5173/8000 服务。
- 前端编辑滑杆改为实时提交；同一效果重复调整会 PATCH 已有 edit，不再不断追加重复节点。
- 工具页、预设页、编辑历史、更多、信息、黑白、降噪、导出和多图状态均已接入真实项目状态。

### 3.3 工具页左侧竖线

原生 `edit.png` 中画布与右侧工具面板之间没有竖向分隔线。浏览器实拍确认旧 Web 构建仍有一像素边框。

本轮同时清除了：

- 编辑画布 `border-right`；
- 工具、预设、编辑历史/更多/信息等右侧面板 `border-left`；
- 图层栏与画布之间不需要的 `border-left`。

浏览器计算样式复核结果为 `canvasRight=0px`、`panelLeft=0px`，当前实拍已无该竖线。

### 3.4 预设、天空和图层素材

新增版本锁定的预设图像导入与运行时接口：

- 22/22 原生集合 `big.jpg` / `small.jpg`；
- 123/123 配置内预设 `icon.jpg`；
- 两个目录 UUID 与 `template.lmps` 内部 UUID 不一致的预设通过解析内部 UUID 正确归位；
- 预设首页使用原生集合封面；
- 集合详情使用原生预设图标；
- 不再为首页一次性请求 123 个效果推理预览。

素材门禁结果：

| 素材族 | 本机 1.28 | 项目 | 结果 |
|---|---:|---:|---|
| SkyTextures | 43 | 43 | 路径和图像 hash 一致；JSON 语义一致 |
| OverlayTextures | 234 | 234 | 路径和图像 hash 一致；JSON/strings 语义一致 |
| DefaultLUTs | 41 | 41 | 路径和原始 hash 全部一致 |
| Preset icons | 123 | 123 | 原始 hash 全部一致 |
| Preset categories | 22 | 22 | big/small 封面原始 hash 全部一致 |

当前资产 manifest 共 1480 条，其中新增 `preset_pack` 168 条（123 图标、44 集合封面、1 个索引），占用约 5.7 MiB。

### 3.5 产品范围规则

原生预设页的分组标题是“已购买”。旧 free-only 检查器把任何包含“购买”的源码都当成付费入口，导致新 UI 被误判。

本轮规则调整为：允许只读原生状态“已购买”，继续禁止“购买”“立即购买”“付费”“订阅”等交易入口；配置中 `paid`、`requires_purchase` 或 `subscription` 预设仍会被拒绝。独立 product-scope 复验已通过。

## 4. 执行前后对比

| 域 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Exact 总门禁 | 21/28 | 21/28（最终复验） | 总数不变；阻断域仍需关闭 |
| Native interaction | 8/10 | 10/10 | 已关闭 |
| Browser interaction | 1/10，11 issues | 1/10，9 missing | 合同更完整，但正式执行仍缺 9 项 |
| UI 参考状态 | 7 | 16 | 覆盖扩展完成 |
| UI pixel | 0/7 | 0/16 | 仍未过阈值；不能声明视觉等价 |
| 当前构建 UI 正式证据 | 0/7 stale | 0/16，5 个 hash/build issues | 本轮只实拍直接改动页，完整证据链未重建 |
| 主效果 | 29/40 | 29/40 | 未进入效果大范围调参 |
| Exact 效果 | 38/69 | 38/69 | 未进入效果大范围调参 |
| 多图 | 2/3 | 2/3 | Panorama 仍失败 |
| 预设原生图像 | 未纳入项目 | 123 图标 + 22 集合封面 | 已关闭 |
| 天空/叠加/LUT 版本门禁 | 无统一 1.28 gate | 全部通过 | 已关闭 |
| Python | 302 | 305 | 全通过 |
| Frontend | 22 | 22 | 全通过 |

效果分数保持不变是有意的阶段控制：UI 与 Browser 证据未准出时，不对单张 reference 做启发式系数硬调，也不把旧 Portable 模型或素材引入 1.28 运行时。

## 5. 当前完整遗漏

### 5.1 UI

- 16 个状态尚未在同一当前 build、同一 1440×900/DPR 2/zh-Hans 环境下完整重录；
- 正式 execution manifest 的 frontend build hash 过期；
- catalog、edit 的候选/source hash 有变更未重新发布；
- 16/16 pixel case 均未达到严格阈值；
- 当前实拍已证明竖线和预设素材改动正确，但不能替代完整矩阵门禁。

### 5.2 Browser interaction

仍缺 9 个正式执行：catalog-import-select、preset-preview-apply、edit-slider-drag、layer-add-reorder-opacity-delete、undo-redo、before-after-compare、zoom-pan、export-dialog、multi-image-workflow。

其中图层删除属于浏览器对本地状态执行删除，按工具安全规则需要在执行删除前取得用户即时确认；未确认前保持 blocked。

### 5.3 效果与模型

主效果仍有 11 项失败：`bw_channels`、`face_ai`、`depth_volume`、`lut_mapping`、`denoise`、`magic_lights`、`new_neon_light`、`blue_hour`、`fog`、`sky_replace`、`sunrays`。

Exact 仍有 31/69 失败。模型库存 92/92 结构有效，26 个具备模型专用验证，66 个仍为 optional pending。不能通过空壳 wrapper 或统一占位调用制造“模型对齐”。

### 5.4 多图

HDR 与 Focus Stacking 通过；Panorama 仍为 MAE `0.081941`、SSIM `0.815541`。差异集中在投影/配准、曝光补偿、seam 与裁切，不应重构已经通过的两个工作流。

## 6. 下一轮可执行计划

### P0：完整重录 16 个 UI 状态

1. 固定当前 frontend build hash、逻辑视口 1440×900、DPR 2、zh-Hans、Asia/Shanghai、reduced motion。
2. 使用同一个隔离目录和同一 fixture 顺序重录 16 个状态。
3. 每张逻辑截图生成 2880×1800 candidate，并发布新的 `ui-browser-execution.json`。
4. 先要求 execution evidence 16/16、issue 0，再进入 pixel diff。
5. 禁止混用旧截图、当前实拍和不同项目输入。

准出：`validate_ui_execution_evidence.py` 为 16/16 passed。

### P1：按几何层级收敛 UI pixel

按以下顺序逐状态修改，避免不同层级互相抵消：

1. 全局窗口：topbar、工作区高度、底部胶片栏、右侧 rail；
2. 主列宽：图层栏、画布、右侧面板；
3. 面板内部：标题、section、卡片、滚动条和空态；
4. 字体：字号、字重、行高、颜色；
5. 图标和选中态；
6. 具体工具控件和素材缩略图。

每次只修改一个状态族，同时检查 edit/catalog anchor，避免修一个页面破坏另一个页面。准出：16/16 UI pixel passed。

### P2：完成 Browser 9 个交互合同

1. 复用已经通过的 Native 10/10 作为动作语义真值。
2. 每个合同保留事件序列、可见断言、API/project 断言、最终截图和 hash。
3. 优先完成无删除的 8 个合同。
4. 图层合同在用户即时确认后执行最后“删除图层”动作。
5. 由 raw trace 构建 execution manifest，禁止手写 passed。

准出：Native 10/10、Browser 10/10，issue 0。

### P3：补独立效果校准样本，再修 11 个主效果

1. 为每个失败能力至少新增一个语义匹配、与当前主 case 不同的 Luminar 原生校准输入；
2. 保留现有主 case 作为 holdout，禁止在同一图片上拟合并验收；
3. 先修接近阈值的 `bw_channels`、`face_ai`、`denoise`；
4. 单独核对 `lut_mapping` 的 1.28 LUT、色域、插值和 Amount 曲线；
5. 将 `blue_hour/fog/sky_replace/sunrays/depth_volume` 作为天空-深度-遮挡共享中间结果批次；
6. 将 `magic_lights/new_neon_light` 作为光源检测-光晕合成批次；
7. 每项同时通过 calibration 与 holdout 后才合入。

准出：主效果 40/40；随后利用共享修复关闭 Exact 31 项，达到 69/69。

### P4：只修 Panorama

依次比较特征点/单应与投影、曝光补偿、seam mask、裁切范围和边缘填充。每一步保存中间图，不用最终整图指标猜根因。HDR 和 Focus Stacking 只跑回归，不改实现。

准出：多图 3/3。

### P5：模型推理层收口

只处理实际被 P3/P4 激活的模型：验证 wrapper 输入输出、归一化、动态 shape、后处理、缓存键、资源释放和 terminal result。未激活的 66 个模型保持 optional，不进入 required 发布路径。

### P6：双轮发布门禁

在代码、配置、素材、输入、reference 和环境 hash 均不变化的条件下，连续运行两次 exact 质量门禁。只有 required 0 failure、UI 16/16、Native/Browser 10/10、多图 3/3、主效果 40/40、Exact 69/69 才允许声明冻结核心合同绝对对齐。

## 7. 可复核证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/asset-alignment-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/external-luminar-assets-17626.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-round-4-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-round-4-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-round-4-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-round-4-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-baseline-round-4-before.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-baseline-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw/1440x900/edit-no-tool-divider.png`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw/1440x900/presets-native-artwork.png`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw/1440x900/preset-detail-native-artwork.png`

## 8. 最终遗漏确认

本轮没有隐藏“已知但未登记”的素材缺口：天空、叠加层、LUT、预设图标和集合封面已经进入独立 gate。未完成项全部集中在 UI 全矩阵正式重录与 pixel、Browser 9 个合同、主效果 11、Exact 31、Panorama 1 和 optional 模型合同 66。

下一轮必须从 P0 重录当前 build 的 16 状态开始；在 P0/P1/P2 准出前，不进入模型和效果的大范围改造。
