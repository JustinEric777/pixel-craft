# Luminar Neo 1.28 UI、交互、效果绝对对齐可执行优化计划（第五轮，2026-08-27）

> 本计划面向继续维护和执行本项目对齐工作的开发者。唯一目标是本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`。计划覆盖 UI、交互、素材、效果、模型、多图和发布证据；每个阶段均给出输入、修改入口、操作步骤、产物、准出条件、停止条件和回退方式。

## 目录

- [1. 目标与成功标准](#1-目标与成功标准)
- [2. 当前冻结基线](#2-当前冻结基线)
- [3. 绝对对齐范围](#3-绝对对齐范围)
- [4. 不可破坏规则](#4-不可破坏规则)
- [5. 阶段依赖与执行顺序](#5-阶段依赖与执行顺序)
- [6. P0：冻结第五轮输入和环境](#6-p0冻结第五轮输入和环境)
- [7. P1：重建 16 个当前构建 UI 证据](#7-p1重建-16-个当前构建-ui-证据)
- [8. P2：按状态族收敛 UI 像素](#8-p2按状态族收敛-ui-像素)
- [9. P3：完成 Browser 10 个交互合同](#9-p3完成-browser-10-个交互合同)
- [10. P4：建立独立效果校准集](#10-p4建立独立效果校准集)
- [11. P5：关闭 11 个主效果差异](#11-p5关闭-11-个主效果差异)
- [12. P6：关闭 31 个 Exact 差异](#12-p6关闭-31-个-exact-差异)
- [13. P7：只修复 Panorama](#13-p7只修复-panorama)
- [14. P8：模型推理层收口](#14-p8模型推理层收口)
- [15. P9：双轮发布门禁](#15-p9双轮发布门禁)
- [16. 修改入口与验证矩阵](#16-修改入口与验证矩阵)
- [17. 单批次执行模板](#17-单批次执行模板)
- [18. 风险、停止和回退](#18-风险停止和回退)
- [19. 完整验收清单](#19-完整验收清单)
- [20. 立即执行的第一批工作](#20-立即执行的第一批工作)

---

## 1. 目标与成功标准

### 1.1 核心目标

在冻结的本地目标合同内，使本项目与 Luminar Neo `1.28.0 (23071)` 在以下层面可重复对齐：

1. 页面信息架构、尺寸、字体、颜色、图标、素材和状态反馈；
2. 目录、预设、工具、编辑历史、图层、导出和多图工作流的交互状态转换；
3. 本地免费效果的 preview/export 输出；
4. 实际产品路径调用的本地模型输入、输出和资源生命周期；
5. HDR、Focus Stacking 和 Panorama；
6. 版本、输入、素材、reference、环境和执行证据的完整 hash 链。

### 1.2 最终成功标准

| 验收域 | 当前 | 最终标准 |
|---|---:|---:|
| Exact 质量门禁 | 21/28 | required 连续两轮 0 failure |
| 主效果 | 29/40 | 40/40 |
| Exact 效果 | 38/69 | 69/69 |
| UI 当前构建证据 | 0/16，5 个 build/hash issue | 16/16，issue 0 |
| UI 像素 | 0/16 | 16/16 |
| Native interaction | 10/10 | 保持 10/10 |
| Browser interaction | 1/10 | 10/10 |
| Multi-image | 2/3 | 3/3 |
| 素材 gate | passed | 保持 passed |
| 主采样队列 | 246/246 ready | hash 不变、issue 0 |
| Python / Frontend | 305 / 22 passed | 不回退 |

UI 严格门限继续使用 `configs/parity.yaml`：MAE ≤ `0.03`、changed-pixel-ratio ≤ `0.02`、shape 必须一致。效果默认门限为 MAE ≤ `0.03`、SSIM ≥ `0.98`、shape 必须一致。不得为通过而放宽。

## 2. 当前冻结基线

第五轮执行前的权威输入为：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-baseline-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-round-4-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/asset-alignment-current.json`
- `docs/luminar-parity-execution-report-2026-08-27-round-4.md`

当前 6 个 required 阻断项：

1. `ui-execution-evidence`；
2. `ui-parity`；
3. `interaction-execution`；
4. `output-parity`；
5. `exact-incremental-parity`；
6. `multi-image`。

可选 `model-contract-inventory` 仍有 66 个模型专用合同 pending。它不应被提前提升为主路径 required，也不能使用空壳 wrapper 制造覆盖率。

### 2.1 已关闭项

- 本机 Luminar Neo 版本已确认：`1.28.0 (23071)`；
- 原生 UI 参考已扩展为 16 状态；
- Native interaction 已达 10/10；
- 工具面板左侧竖线已移除；
- 天空、叠加层、Default LUT、123 个预设图标和 22 个集合封面素材 gate 已通过；
- Portable 目录已确认实际为 Windows `1.27.1.17225`，不会覆盖 1.28 素材；
- Python 305/305、Frontend 22/22、Ruff、TypeScript、Vite build 通过。

### 2.2 仍需关闭项

- 16 个 Web UI 状态完整当前构建证据；
- 16 个 UI pixel case；
- 9 个 Browser interaction；
- 11 个主效果；
- 31 个 Exact case；
- Panorama；
- 实际被失败效果激活的模型专用合同和调用语义。

## 3. 绝对对齐范围

### 3.1 A 层：本地核心，required

- 目录、胶片栏、单图编辑；
- 免费内置预设；
- 工具、编辑历史、更多、信息；
- 天空、图层、LUT 和预设素材；
- 本地免费效果和本地模型；
- 图层、undo/redo、前后对比、缩放平移；
- HDR、Focus Stacking、Panorama；
- 本地导出。

### 3.2 B 层：受限入口状态，required

升级、账号、付费集合和生成式服务只对齐本机当前可见状态、锁定状态和提示语义。不得在本地伪造购买、账号或云端结果。

### 3.3 C 层：外部服务，条件 blocked

若本机 Luminar 的生成式擦除、替换、扩展等依赖账号、网络或 Skylum 服务，只有在具备合法账号、稳定接口和可重复 reference 时才能纳入 required。否则最终声明必须限定为“冻结的本地核心合同绝对对齐”，不能声称所有云服务已验证。

## 4. 不可破坏规则

1. 活动 target 只允许 `luminar-neo-macos-1.28.0-23071`。
2. 246 条 ready canonical 默认只读；候选失败、UI 失败不是重采理由。
3. Portable `1.27.1.17225` 只作旁证，不进入 1.28 运行时素材或模型。
4. 不修改 reference、输入、case、阈值或 comparator 来制造通过。
5. 不允许运行时代码读取 case id、失败报告或 reference hash 选择算法。
6. 每个效果修改必须有 calibration 和独立 holdout；同一图片不能同时承担拟合与验收。
7. 每次只解决一个可证伪根因；没有第二次真实重复前不增加共享抽象。
8. UI build hash 变化后，旧 Browser 截图自动失效，必须重录。
9. Native 和 Browser interaction 的 `passed` 必须由原始事件、截图和 API 证据构建，不能手写。
10. 图层删除属于浏览器本地删除动作，执行最后一步前必须取得用户即时确认。
11. 只有中间证据证明误差来自模型 wrapper 时才修改 `ai/model`；效果组合误差优先在 pipeline/compositor 修复。
12. 前一阶段未达到准出条件时，不进入下一阶段做大范围修改。

## 5. 阶段依赖与执行顺序

```text
P0 冻结环境、输入和基线
  │
  ▼
P1 16 个当前构建 UI 证据
  │
  ▼
P2 UI 16/16 像素收敛
  │
  ▼
P3 Native/Browser 10/10 交互
  │
  ▼
P4 独立效果校准集和 reference 有效性
  │
  ▼
P5 主效果 40/40
  │
  ▼
P6 Exact 69/69
  │
  ├──────────────┐
  ▼              ▼
P7 Panorama   P8 激活模型合同
  │              │
  └──────┬───────┘
         ▼
P9 连续双轮发布门禁
```

P7 与 P8 可在 P5/P6 稳定后并行分析，但不能与 UI 大范围改造混在同一批次。

## 6. P0：冻结第五轮输入和环境

### 6.1 目标

保证后续差异来自代码，而不是版本、素材、输入、reference、浏览器环境或陈旧证据变化。

### 6.2 操作步骤

1. 记录应用版本/build、bundle、locale 和平台。
2. 运行素材 gate，确认本机 1.28 与项目素材无漂移。
3. 验证 246 条主采样队列和数据链。
4. 记录 frontend build hash、Python、Node、浏览器版本、逻辑/物理视口、DPR、timezone、motion。
5. 再次运行 Python、Frontend、Ruff 和生产构建，建立第五轮 before baseline。
6. 对参与结果的源码、配置、输入、reference 和素材生成 SHA-256 manifest。

### 6.3 验证命令

```bash
.venv/bin/python scripts/validate_luminar_asset_alignment.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/asset-alignment-round-5-before.json

.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
```

### 6.4 产物和准出

- `source-manifest-round-5-before.sha256`
- `convergence-baseline-round-5-before.json`
- `convergence-failures-round-5-before.json`
- asset gate `passed`
- sampling issue `0`
- Python/Frontend/Ruff/build 全通过

任一输入或 reference hash 漂移时停止，先解释变化；不能继续生成候选。

## 7. P1：重建 16 个当前构建 UI 证据

### 7.1 目标

先关闭 `ui-execution-evidence`，使每个 UI diff 都绑定当前 frontend build 和固定 fixture。

### 7.2 固定环境

| 项目 | 固定值 |
|---|---|
| logical viewport | 1440×900 |
| DPR | 2 |
| physical viewport | 2880×1800 |
| locale | zh-Hans |
| timezone | Asia/Shanghai |
| motion | reduce |
| 数据目录 | `diagnostics/ui-workspace` 隔离目录 |
| 输入 | `configs/parity.yaml` 对应 validation samples |

### 7.3 操作步骤

1. 使用 `seed_ui_validation_catalog.py --reset` 重建隔离目录，不修改用户正常工作区。
2. 启动隔离 backend 和 frontend，记录实际端口与 build hash。
3. 按以下顺序重录，避免前一状态污染后一状态：

   - catalog；
   - presets；
   - edit；
   - layer-stack；
   - layer-library；
   - tool-expanded；
   - edit-history；
   - more-panel；
   - info-panel；
   - edit-collapsed；
   - black-white-before-conversion；
   - black-white-after-conversion；
   - denoise-level-selected；
   - export-dialog；
   - multi-image；
   - multi-image-complete。

4. 每个状态保存 logical screenshot，并校验尺寸、fixture id、fixture hash、项目状态和截图 hash。
5. 使用 Lanczos 生成 2880×1800 candidate。
6. 使用实际浏览器版本构建 `ui-browser-execution.json`。
7. 运行 fail-closed evidence validator。

### 7.4 修改和脚本入口

- `scripts/seed_ui_validation_catalog.py`
- `scripts/prepare_ui_candidate.py`
- `scripts/build_ui_browser_execution.py`
- `scripts/validate_ui_execution_evidence.py`
- `configs/parity.yaml` 的 `capture.ui_states`

### 7.5 准出条件

- expected 16；
- executed 16；
- passed 16；
- issue_count 0；
- build、source capture、candidate、fixture 和 viewport hash 全匹配。

P1 不修 CSS；如果当前截图暴露布局问题，只登记到 P2 diff 清单。

## 8. P2：按状态族收敛 UI 像素

### 8.1 目标

使 16 个 UI case 同时达到 MAE、changed-pixel-ratio 和 shape 门限，避免只优化一个截图。

### 8.2 状态族顺序

#### U1：全局外壳和编辑锚点

状态：`edit`、`edit-collapsed`、`presets`。

依次对齐：

1. topbar 高度和 breadcrumb；
2. 图层栏、画布、右侧面板和 Rail 列宽；
3. 胶片栏和底部工具条；
4. 工具面板左侧无竖线；
5. 画布图片 fit/position；
6. 全局背景、边框和滚动区域。

#### U2：目录

状态：`catalog`。

对齐目录 sidebar、集合选中态、照片网格、thumbnail 比例、右侧 inspector、排序和选中行为。目录单击必须停留目录，进入工具才切换编辑器。

#### U3：右侧面板族

状态：`tool-expanded`、`edit-history`、`more-panel`、`info-panel`。

共享面板宽度和 heading 只调整一次；各面板内部独立对齐 section、行高、图标、空态和滚动条。

#### U4：图层和素材

状态：`layer-stack`、`layer-library`。

对齐添加入口、图层 thumbnail、选中框、blend/opacity、集合封面和真实 Luminar 1.28 素材。禁止使用占位图。

#### U5：状态型工具

状态：`black-white-before-conversion`、`black-white-after-conversion`、`denoise-level-selected`、`export-dialog`。

重点对齐 enabled/disabled、默认值、选中等级、busy、弹窗尺寸、字段、按钮顺序和返回状态。

#### U6：多图

状态：`multi-image`、`multi-image-complete`。

对齐帧列表、空态、进度、preview、导出按钮启用条件和结果视图。

### 8.3 每个 UI 批次的执行循环

1. 从 diff heatmap 确认主要误差区域。
2. 只提出一个几何或样式根因。
3. 修改最小 CSS/组件范围。
4. 运行对应组件测试和 frontend build。
5. 只重录受影响状态及至少一个共享 anchor。
6. 比较目标状态和 anchor 指标。
7. 目标改善且 anchor 不回退才保留；否则回退本批修改。

### 8.4 主要修改入口

- `frontend/src/styles.css`
- `frontend/src/App.tsx`
- `frontend/src/components/CatalogWorkspace.tsx`
- `frontend/src/components/PresetBrowser.tsx`
- `frontend/src/components/ToolPanel.tsx`
- `frontend/src/components/LayersPanel.tsx`
- `frontend/src/components/EditHistoryPanel.tsx`
- `frontend/src/components/MorePanel.tsx`
- `frontend/src/components/InfoPanel.tsx`
- `frontend/src/components/ExportDialog.tsx`
- `frontend/src/components/WorkflowWorkspace.tsx`

### 8.5 准出条件

```bash
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

- evidence 16/16；
- pixel 16/16；
- UI issue 0；
- frontend 22/22、build 通过；
- 当前 build hash 与正式证据一致。

## 9. P3：完成 Browser 10 个交互合同

### 9.1 当前状态

Native 10/10 已通过；Browser 仅 `edit-toggle-collapse` 正式通过，仍缺 9 个。

### 9.2 执行顺序

| 顺序 | 合同 | 关键断言 |
|---:|---|---|
| 1 | catalog-import-select | 数量不变、选择留在目录、进入编辑后 preview ready |
| 2 | preset-preview-apply | 图只应用一次、edit 顺序匹配 preset graph |
| 3 | edit-slider-drag | 只有一个 details edit、amount 精确为 0.65 |
| 4 | undo-redo | undo 移除最后 edit，redo 恢复相同 id/参数 |
| 5 | before-after-compare | source/edited preview 切换，项目状态不变 |
| 6 | zoom-pan | 200%、pan、fit 恢复，项目状态不变 |
| 7 | export-dialog | 文件名回读、取消、无重复导出 |
| 8 | multi-image-workflow | 3 帧 hash、preview、analysis、export hash 稳定 |
| 9 | layer-add-reorder-opacity-delete | 添加一次、排序、50% 透明度、删除 |

图层合同最后一步删除隔离项目中的测试图层。只有用户即时确认后才能执行；此前可以完成添加、排序和透明度证据，但合同保持 blocked。

### 9.3 证据要求

每个合同必须记录：

- initial fixture 和 project JSON；
- 与合同完全一致的 event 列表；
- visible assertions；
- API assertions；
- 允许的 wait condition，`fixed_sleep=false`；
- final screenshot；
- native observation hash；
- network/API/project/export 证据。

### 9.4 构建与验证

```bash
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw <raw-execution.json> \
  --evidence-root <browser-evidence-root>

.venv/bin/python scripts/validate_interaction_execution.py
.venv/bin/python scripts/validate_interaction_execution.py --native-only
```

准出：Native 10/10、Browser 10/10、issue 0。

## 10. P4：建立独立效果校准集

### 10.1 目标

在修改效果实现前，先分离 calibration 与 holdout，排除无效 reference、错误输入和单图过拟合。

### 10.2 操作步骤

1. 运行 `validate_invalid_references.py`，确认 `invalid-references.json` 中的记录不会进入 active parity。
2. 检查当前 LUT 主 case 是否被标记 invalid 却仍参与 baseline；若是，修复 reference 过滤链，不改指标或 reference 文件。
3. 为每个主效果失败项选择至少一个语义匹配、未被当前主 case 使用的输入。
4. 使用 `build_effect_calibration_queue.py` 创建语义去重记录。
5. 在 Luminar 中按统一恢复原图合同采集 calibration preview/export。
6. 校验输入 hash、参数 readback、素材 id/hash、Reset 状态和导出变化。
7. 保留现有主 case 作为 holdout；不得重新采样它来配合候选。

### 10.3 生成单条校准记录

```bash
.venv/bin/python scripts/build_effect_calibration_queue.py \
  --capability <capability-id> \
  --input <semantic-input> \
  --parameters '<json-object>' \
  --output <queue-record.json> \
  --audit-output <dedup-audit.json>
```

### 10.4 准出条件

- 11 个主失败能力都有独立 calibration；
- calibration 与 holdout 输入 hash 不同；
- 所有新原生记录数据链通过；
- 现有 246 条 canonical 未被无理由重采；
- invalid reference 不再进入 active suite。

## 11. P5：关闭 11 个主效果差异

### 11.1 失败清单

| 批次 | 能力 | 当前主要问题 |
|---|---|---|
| E1 近阈值 | bw_channels、face_ai、denoise | 强度曲线、通道权重、mask/细节恢复 |
| E2 色彩/LUT | lut_mapping | 1.28 LUT、色域、插值、Amount 曲线、ICC |
| E3 深度/天空 | depth_volume、blue_hour、fog、sky_replace、sunrays | 深度、天空 mask、地平线、遮挡、反射和色调 |
| E4 光源 | magic_lights、new_neon_light | 光源检测、光晕位置/尺度、颜色和混合 |

### 11.2 E1：先处理接近阈值能力

#### bw_channels

1. 比较 RGB 到单色的中间通道贡献。
2. 核对综合色调、曝光和局部对比处理顺序。
3. 用 calibration 调整；用原主 case holdout 验收。

#### face_ai

1. 保存 face detection、landmark、区域 mask 和 feather 中间图。
2. 先修区域位置/边界，再调效果强度。
3. 检查非人脸区域必须近似不变。

#### denoise

1. 固定 `middle` 等级语义。
2. 分离亮度噪声、色彩噪声和细节恢复。
3. 同时比较平坦区 residual 和边缘梯度，避免只降低 MAE 而抹平细节。

准出：每项 calibration 和 holdout 都通过默认阈值，同组已通过 case 不回退。

### 11.3 E2：LUT

1. 确认候选使用项目中与本机 1.28 hash 相同的 LUT。
2. 校验输入色域、LUT domain、三线性/四面体插值和输出色域。
3. 验证 Amount 是否线性；若原生表现非线性，以多点 readback 建立通用曲线，不写 case 特例。
4. 校验导出 ICC 和 RGB 范围。

### 11.4 E3：共享天空、深度和遮挡中间结果

建议建立一次共享诊断数据，不提前重构运行时：

```text
输入
  ├─ 天空/地平线 mask
  ├─ 深度图
  ├─ 遮挡图
  └─ 主体/反射区域
          │
          ▼
  各能力独立合成与色调
```

先验证 mask/深度几何，再验证合成，最后验证颜色。只有第二个能力证明需要同一运行时逻辑时，才提取共享组件。

### 11.5 E4：光源检测和合成

1. 保存候选亮点/线条检测图。
2. 与 Luminar 输出的光晕中心和结构位置比较。
3. 先关闭结构差异，再调 blur、falloff、颜色和 blend。
4. `new_neon_light` 的低 SSIM 表明结构误差优先，禁止先靠整体加色降低 MAE。

### 11.6 代码入口

- `ai/pipeline/image_effect_pipelines.py`
- `image_ops/rendering.py`
- `configs/capabilities/execution-graphs.json`
- 对应的 effect/compositor 测试

如果中间 mask 和几何正确，但模型原始输出已经偏离 Luminar 语义，再进入 P8 修改 `ai/model`。

### 11.7 单能力验证

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --capability <capability-id>
```

准出：主效果 40/40，且每项 calibration/holdout 双通过。

## 12. P6：关闭 31 个 Exact 差异

### 12.1 处理原则

先重新运行 Exact，吸收 P5 的共享修复；只处理剩余失败，不重复修改已通过能力。

当前 Exact 失败聚类：

- `face_enhancer` 2；
- `grain` 2；
- `default_effects` 2；
- `face_ai` 2；
- `depth_volume` 2；
- `vignette` 2；
- 其余 high_key、sunrays、pro_contrast、bokeh_ai、structure_ai、ai_enhance、color_toning、color_adjustments、blue_hour、color_enhancer、radiance、landscape_enhancer、fog、fade、new_neon_light、denoise_laplacian、magic_lights、slim_people、denoise 各 1。

### 12.2 批次顺序

1. X1：P5 同能力传播失败；
2. X2：确定性色调和对比度；
3. X3：vignette、fade、radiance 等空间效果；
4. X4：portrait/bokeh/slim_people；
5. X5：grain 和 denoise_laplacian 统计效果；
6. X6：default_effects 复合图顺序和默认参数。

### 12.3 复合图检查

对 `default_effects` 和预设复合图逐节点比较：

- 节点顺序；
- 参数归一化；
- permanent/blend 语义；
- LUT/素材解析；
- 每个节点的中间输出；
- 最终颜色空间和导出。

禁止通过调整最终统一增益掩盖中间节点顺序错误。

### 12.4 准出条件

- Exact 69/69；
- 主效果继续 40/40；
- calibration/holdout 不回退；
- 失败注册表中 output-parity 和 exact-parity 均为 0。

## 13. P7：只修复 Panorama

### 13.1 当前状态

- HDR：passed；
- Focus Stacking：passed；
- Panorama：MAE `0.081941`、SSIM `0.815541`。

### 13.2 分解诊断

1. 输入方向和 EXIF/旋转规范化；
2. 特征点数量、分布和筛选；
3. 图像排序和单应/相机参数；
4. 投影类型与焦距；
5. 曝光和白平衡补偿；
6. seam mask；
7. blending；
8. 自动裁切和边缘填充。

每一步保存中间图和几何参数，先比较结构对齐，再比较颜色。不要只用最终 MAE 猜根因。

### 13.3 修改入口

- `services/multi_image/service.py`
- `image_ops/` 中 Panorama 使用的配准、投影和合成实现
- `scripts/run_multi_image_workflow_smoke.py`

### 13.4 回归

```bash
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-round-5.json
```

准出：3/3；HDR 和 Focus Stacking 指标不得回退。

## 14. P8：模型推理层收口

### 14.1 触发条件

只有满足以下证据之一才修改 `ai/model`：

- wrapper 输入 shape/dtype/layout 与模型真实合同不符；
- 归一化、色彩空间或 padding 错误；
- 输出解码、resize、softmax/sigmoid 或阈值错误；
- 动态 shape、缓存键或资源释放错误；
- 模型原始输出本身已经与目标中间语义不符。

效果组合、mask feather、blend、tone 或导出错误不属于 `ai/model`。

### 14.2 检查项

1. `BaseInference` 输入输出合同；
2. `InferenceResult` 字段、shape、dtype 和 metadata；
3. 模型注册、动态实例化和 manifest 对应；
4. 本地权重 hash 和 backend；
5. ONNX Runtime 主路径、OpenVINO fallback；
6. 禁止 CoreML；
7. 缓存命中与失效；
8. 长任务必须等待 terminal result；
9. 异常和取消后的资源释放。

### 14.3 验证命令

```bash
.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-invocations-round-5.json

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-round-5.json
```

准出：实际调用模型 100% 有专用合同、invocation 和 terminal result；66 个未激活模型允许保持 optional。

## 15. P9：双轮发布门禁

### 15.1 第一轮

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-5-run-1.json
```

### 15.2 第二轮

第一轮后不修改源码、配置、输入、reference、素材、环境或依赖，重新执行同一命令并输出 `run-2.json`。

### 15.3 双轮一致性

比较：

- 28 个 gate 状态；
- 所有 candidate/export hash；
- UI screenshot hash；
- interaction evidence hash；
- 模型调用和 backend；
- 运行环境；
- 输入、reference、素材和源码 manifest。

只有两轮 required failure 都为 0 且 hash 稳定，才允许发布。

## 16. 修改入口与验证矩阵

| 目标 | 修改入口 | 窄验证 | 最终验证 |
|---|---|---|---|
| UI 布局 | `frontend/src/styles.css`、对应组件 | Vitest + 目标状态截图 | UI 16/16 |
| 预设 UI/素材 | `PresetBrowser.tsx`、preset artwork API | API test + 预设状态 | asset gate + UI |
| 目录交互 | `CatalogWorkspace.tsx`、editor service | 目录/API tests | Browser contract |
| 滑杆编辑 | `ToolPanel.tsx`、`App.tsx`、edit API | ToolPanel test + API test | edit-slider-drag |
| 图层 | `LayersPanel.tsx`、editor layer methods | LayersPanel/API tests | layer Browser contract |
| 导出 | `ExportDialog.tsx`、export route | export tests | export-dialog |
| 主效果 | `ai/pipeline/image_effect_pipelines.py`、renderer | 单能力 candidate/parity | 40/40 |
| Exact | execution graph、参数和对应 adapter | 单 case/capability | 69/69 |
| Panorama | multi-image service / image ops | workflow smoke | 3/3 |
| 模型 wrapper | `ai/model` | 模型专用合同 | active invocation gate |

## 17. 单批次执行模板

每个批次必须填写：

```text
批次 ID：
目标 state / contract / capability / case：
当前指标：
输入和 reference hash：
根因假设：
将修改的最小文件范围：
明确不修改的范围：
窄测试：
目标验证：
共享 anchor / holdout：
修改后指标：
继续、回退或转交下一根因：
```

提交批次前检查：

1. 假设可被验证或证伪；
2. 没有修改 reference、阈值或输入；
3. 没有 case-id 分支；
4. 目标改善；
5. anchor/holdout 不回退；
6. 证据写入新的批次路径，不覆盖通过的 canonical。

## 18. 风险、停止和回退

### 18.1 UI 过拟合

症状：一个状态 MAE 改善，其他共享布局状态回退。

处理：每次至少验证目标状态和一个共享 anchor；若 anchor 越过门限或明显恶化，回退本批 CSS。

### 18.2 参考无效

症状：reference 被登记 invalid、输入 hash 不匹配、原生输出无变化或参数 readback 不一致。

处理：停止算法修改，先修过滤/采样证据；不得修改候选迎合无效 reference。

### 18.3 单图过拟合

症状：主 case 改善但 calibration 或同能力 Exact 回退。

处理：回退系数修改，重新定位算法或中间模型根因。

### 18.4 模型和 pipeline 边界混淆

症状：为了修 blend/mask/颜色问题修改 wrapper。

处理：保存模型原始输出与后处理输出；原始输出正确时停止修改 `ai/model`。

### 18.5 旧版本素材污染

症状：素材来源指向 Portable `1.27.1.17225` 或 asset gate 失败。

处理：立即回退该批素材，重新从本机目标 1.28 版本导入并重建 manifest。

### 18.6 证据过期

症状：frontend build hash、source screenshot 或 candidate hash mismatch。

处理：重新录制受影响的完整状态族；禁止编辑 execution JSON 绕过。

## 19. 完整验收清单

### 环境与数据

- [ ] 目标版本/build、locale、viewport、DPR 和 timezone 固定。
- [ ] 素材 gate passed。
- [ ] 246/246 主采样数据链通过，hash 无漂移。
- [ ] invalid reference 不进入 active suite。

### UI

- [ ] 16/16 当前 build execution evidence。
- [ ] 16/16 UI pixel parity。
- [ ] 工具面板左侧无竖线。
- [ ] 预设、天空、图层素材来自目标 1.28。

### 交互

- [ ] Native 10/10。
- [ ] Browser 10/10。
- [ ] 无固定 sleep、无手写 passed、无重复导出。

### 效果与模型

- [ ] 11 个主失败能力都有独立 calibration。
- [ ] 主效果 40/40。
- [ ] Exact 69/69。
- [ ] 实际激活模型全部有专用合同和调用证据。
- [ ] 资源释放和 terminal result 完整。

### 多图和发布

- [ ] HDR、Focus Stacking、Panorama 3/3。
- [ ] Python、Frontend、Ruff、build 全通过。
- [ ] Exact required 连续两轮 0 failure。
- [ ] 两轮源码、配置、输入、reference、素材、环境和输出 hash 稳定。
- [ ] 外部服务未验证项在发布说明中明确 blocked，不扩大声明范围。

## 20. 立即执行的第一批工作

第五轮开始后只执行以下内容：

1. 建立 round-5 before manifest；
2. 重建隔离 UI 目录；
3. 使用当前 build 完整录制 16 个 UI 状态；
4. 使 `ui-execution-evidence` 达到 16/16；
5. 生成 16 状态指标排序和 diff heatmap；
6. 从 `edit/presets/edit-collapsed` 全局外壳状态族开始第一个 UI 像素批次。

在这六项完成前，不修改效果、Panorama 或 `ai/model`。
