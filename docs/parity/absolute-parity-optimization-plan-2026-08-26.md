# Luminar Neo 1.28 效果、UI、交互绝对对齐可执行优化计划（2026-08-26）

> 本计划面向当前代码维护者，目标是在本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`、冻结输入/素材和 `2880×1800` UI viewport 范围内，关闭当前 5 个 required 质量门禁。计划只针对活动 1.28 合同，不增加 1.25/1.26 兼容逻辑，不重复采样已有可信效果 reference。

## 目录

- [1. 成功标准和非目标](#1-成功标准和非目标)
- [2. 冻结基线](#2-冻结基线)
- [3. 执行原则](#3-执行原则)
- [4. 依赖顺序和批次](#4-依赖顺序和批次)
- [5. P0：冻结基线与失败注册表](#5-p0冻结基线与失败注册表)
- [6. P1：原生交互 observation 采集器](#6-p1原生交互-observation-采集器)
- [7. P2：UI 七状态结构对齐](#7-p2ui-七状态结构对齐)
- [8. P3：本项目十条交互合同](#8-p3本项目十条交互合同)
- [9. P4：效果算法收敛](#9-p4效果算法收敛)
- [10. P5：Panorama 原生语义](#10-p5panorama-原生语义)
- [11. P6：模型和长任务保护性回归](#11-p6模型和长任务保护性回归)
- [12. P7：全量门禁、清理和发布](#12-p7全量门禁清理和发布)
- [13. 修改入口和验证矩阵](#13-修改入口和验证矩阵)
- [14. 单能力执行模板](#14-单能力执行模板)
- [15. 停止条件与回退](#15-停止条件与回退)
- [16. 最终验收清单](#16-最终验收清单)

---

## 1. 成功标准和非目标

### 1.1 最终成功标准

只有以下条件同时成立，才能把冻结范围标记为对齐完成：

| 域 | 必须达到的结果 |
|---|---|
| 数据链 | 主采样 `251/251`；exact `69/69`；duplicate、invalid、pending 均为 0 |
| 主效果 | `45/45`，shape 一致，使用 `configs/parity.yaml` 原有 MAE/SSIM 门限 |
| Exact | `69/69`，不修改门限，不删除 required case |
| 内容 | Preset、Sky、Overlay 既有通过项不回退；Overlay 保持 `38/38` |
| Multi-image | HDR、Focus、Panorama `3/3` |
| UI | 七状态 `7/7`；`MAE <= 0.03`、changed pixel ratio `<= 0.02` |
| 交互 | native observation `10/10`、Browser execution `10/10`、issue 0、fixed sleep 0 |
| 模型 | required logical model `22/22`；真实调用和生命周期门禁保持通过 |
| 回归 | Python、Ruff、frontend test/build 全通过 |
| 发布 | 28 项门禁连续两轮 required failure 为 0，关键候选 hash 稳定 |

这里的“绝对对齐”仅指上述冻结版本、输入、素材、参数和 viewport，不外推到付费资源、未冻结输入、未来 Luminar 版本或当前产品不可达的 optional 模型。

### 1.2 本计划不做的事情

- 不重新设计一个“类似 Luminar”的界面；UI 以本机原生 reference 为唯一视觉方向。
- 不为单张图片、单个 case id 或单个 hash 写运行时特例。
- 不放宽 MAE、SSIM、UI changed-pixel 或 shape 门限。
- 不用最终 resize、手工改 reference/hash、删除 required case 来制造通过。
- 不全量重采已经 ready 的效果、Preset、Sky、Overlay 或 exact reference。
- 不优先实现 66 个 optional、当前产品不可达的模型合同。
- 不增加历史 payload、样式或行为兼容层。

## 2. 冻结基线

基线来源：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final.json`。

| 域 | 当前结果 | 下一目标 |
|---|---:|---:|
| 总门禁 | 22 passed / 5 required failed / 1 optional failed | required failure 0 |
| 主效果 | 36/45 | 45/45 |
| Exact | 38/69，31 failed，0 pending | 69/69 |
| Overlay | 38/38 | 保持 |
| Multi-image | 2/3 | 3/3 |
| UI current-build evidence | 7/7 | 保持 |
| UI parity | 0/7 | 7/7 |
| Interaction definition | 10/10 | 保持 |
| Interaction execution | 0/10 | 10/10 |
| Required model | 22/22 | 保持 |
| Python / frontend | 277 / 13 passed | 不回退 |
| 清理 postcheck | 0 path / 0 byte | 每批结束保持 0 |

当前 required 失败集合固定为：

1. `multi-image`；
2. `output-parity`；
3. `exact-incremental-parity`；
4. `ui-parity`；
5. `interaction-execution`。

## 3. 执行原则

### 3.1 一个修改只关闭一个可解释根因

每个批次必须能回答：哪个共享语义错了、改了哪些文件、哪些 case 预期变化、哪些已通过 case 必须保持不变。只有第二次出现真实重复逻辑时才提取新抽象。

### 3.2 Reference 默认只读

69 条 exact、45 条主效果、38 条 Overlay 的当前可信 reference 默认不变。只有同时满足以下条件才允许 targeted reobserve：

1. source hash、素材 hash 或 app build 不一致；
2. AX 控件 readback 与合同不一致；
3. 非中性效果导出时 `ResetAllEdits` 不可用；
4. preview/export 不一致或导出相对源图无变化；
5. 先把异常写入 invalid-reference registry；
6. dry-run 只选中一个明确 record id；
7. 使用 `--limit 1 --allow-ui-control` 定向执行。

算法失败、MAE 高或 SSIM 低本身不是重采理由。

### 3.3 先合同、后结构、再像素

- 交互：先采原生状态机，再实现本项目行为。
- UI：先壳层几何和滚动所有权，再组件状态，最后颜色/阴影。
- 效果：先输入/模型/mask/坐标合同，再曲线和像素参数。
- Panorama：先几何投影和有效边界，再接缝、融合和颜色。

### 3.4 任何阶段都 fail closed

缺少 artifact、hash、模型结果、原生 observation 或最终截图时保持 blocked。不得以单测通过、接口 200、点击成功或人工观感替代结果门禁。

## 4. 依赖顺序和批次

```text
P0 冻结基线与失败注册表
  │
  ├──> P1 原生 interaction observations 10/10
  │       │
  │       ├──> P2 UI 七状态 7/7
  │       │       │
  │       │       └──> P3 Browser interaction 10/10
  │       │
  │       └──> 固定原生等待条件和状态语义
  │
  ├──> P4 效果：主效果 45/45 + exact 69/69
  │
  └──> P5 Panorama：Multi-image 3/3
             │
             ▼
      P6 模型/长任务保护性回归
             │
             ▼
      P7 全量门禁双跑、清理、冻结发布
```

推荐按 P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 执行。P4 与 P2/P3 代码边界不同，可以在人工排期上交错，但最终验收不得跳过依赖。

## 5. P0：冻结基线与失败注册表

### 5.1 目标

建立本轮不可漂移的输入、失败集合和产物清单，确保后续指标变化能归因到代码，而不是 reference、候选目录或环境漂移。

### 5.2 工作项

1. 复制最终门禁摘要为本轮 baseline，不复制大图；记录报告 SHA-256。
2. 从主效果和 exact 报告生成机器可读 failure registry，字段至少包括：
   - `case_id`、`capability_id`；
   - source/reference/candidate hash；
   - 当前 MAE、SSIM、shape；
   - 初步根因域：contract、tone、mask、geometry、asset、noise、color-management；
   - owner batch 和状态。
3. 记录七个 UI 状态的 MAE、changed pixel ratio、reference/candidate hash。
4. 记录 10 个 interaction contract 当前缺失项。
5. 运行采样和清理 dry-run，确认没有 ready 记录重新进入队列。

建议新增产物：

- `diagnostics/convergence-baseline-2026-08-26.json`；
- `diagnostics/convergence-failures-2026-08-26.json`。

### 5.3 验证

```bash
.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-p0-dry-run.json
```

### 5.4 准出

- baseline 能重建当前 `22/5/1` 门禁摘要；
- 主效果失败为 9、exact 失败为 31、UI 失败为 7、interaction 缺失为 10；
- exact pending 为 0；
- 清理 dry-run 为 0；
- 不执行任何原生效果采样。

## 6. P1：原生交互 observation 采集器

### 6.1 根因

应用内 Browser 已经可用；当前 interaction `0/10` 的第一阻塞是原生 observation 目录为空，以及仓库不存在 `scripts/run_luminar_interaction_observations.py`。

### 6.2 最小实现范围

新增：

- `scripts/run_luminar_interaction_observations.py`；
- `tests/test_luminar_interaction_observations.py`。

同时给 `scripts/validate_interaction_execution.py` 增加最小的 `--native-only` 模式，复用现有 `_validate_native_observation` 规则，在 Browser execution 尚未生成时独立验收原生 10 条记录；不复制第二套 observation schema。

优先复用：

- `scripts/luminar_capture/ui_evidence.py`；
- 现有 AX helper、前台控制、截图和版本预检；
- `configs/parity/interaction-contracts.json`。

不要设计通用桌面自动化框架。只实现当前合同真实出现的动作：`upload`、`wait`、`click`、`focus`、`drag`、`assert`、`wheel`。

### 6.3 CLI 合同

计划新增以下最小参数：

```text
--contract-id <id>     只执行一条合同
--resume               跳过 hash 完整且 app build 一致的 observation
--dry-run              只输出选中合同和前置条件
--allow-ui-control     明确允许 Luminar 获得前台控制
```

禁止没有 `--allow-ui-control` 时操作本机 GUI。

### 6.4 每条 observation 产物

写入 `test_data/outputs/luminar-1.28.0-23071/observations/interactions/<contract-id>/`：

- `observation.json`；
- `before.png`；
- `after.png`；
- `accessibility.json` 或 `accessibility.txt`；
- 失败时额外保存最后一步截图和 AX snapshot。

`observation.json` 必须满足现有 validator：

- `contract_id`、`reference_id`；
- `app_version={version,build,bundle_id}`；
- events 与合同完全一致；
- final state 与合同一致；
- visible assertions 完整；
- wait 只能来自 `allowed_wait_conditions`；
- fixture SHA-256 为 64 位；
- 三个主要 artifact 路径和 SHA-256 完整。

### 6.5 执行顺序

先做低风险、无项目写入的合同，再做有写入和导出的合同：

1. `edit-toggle-collapse`；
2. `before-after-compare`；
3. `zoom-pan`；
4. `edit-slider-drag`；
5. `undo-redo`；
6. `catalog-import-select`；
7. `preset-preview-apply`；
8. `layer-add-reorder-opacity-delete`；
9. `export-dialog`；
10. `multi-image-workflow`。

每条先 dry-run，再单条真实执行；成功后才进入下一条。不得一次把 10 条交给 GUI 连跑。

### 6.6 验证与准出

```bash
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py \
  --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-observations.json
```

P1 阶段允许 Browser execution 仍为空，但 native observation 必须达到 10/10，且 native 审计 issue 为 0。随后 P3 再关闭 aggregate validator。

## 7. P2：UI 七状态结构对齐

### 7.1 视觉方向

唯一方向是“Luminar 1.28 原生精密编辑工作台”：画布/内容是视觉中心，侧栏紧凑，背景克制，状态清晰。这里不是通用美化，不新增渐变、漂浮卡片或营销式视觉。

### 7.2 分三层收敛

#### 第一层：应用壳和几何

主要入口：

- `frontend/src/App.tsx`；
- `frontend/src/components/WorkspaceRail.tsx`；
- `frontend/src/components/EditorHeader.tsx`；
- `frontend/src/components/PreviewPanel.tsx`；
- `frontend/src/styles.css`。

工作项：

1. 固定顶栏、工作区导航、左右栏、画布和底部区域的尺寸关系；
2. 明确每个状态唯一纵向滚动容器；
3. 为 flex/grid 子项设置正确的 `min-width/min-height: 0`；
4. 空态、加载态和图片加载失败时保持画布尺寸；
5. 先使七张截图的大分区边界与原生一致，再处理组件细节。

#### 第二层：组件和状态

主要入口：

- `CatalogWorkspace.tsx`；
- `PresetBrowser.tsx`；
- `ToolPanel.tsx`；
- `LayersPanel.tsx`；
- `AssetPicker.tsx`；
- `WorkflowWorkspace.tsx`。

必须覆盖：selected、hover、focus-visible、disabled、expanded/collapsed、loading、empty、error。保持已经通过的黑白“先转换后调参”和降噪等级状态，不因视觉重构改变行为。

#### 第三层：设计令牌

只在同一值已跨多个组件重复时，把背景、表面、文字、边框、强调色、间距、控件高度、圆角和短动效收敛到 `styles.css` 的语义变量。页面层不另建第二套 token。

### 7.3 状态顺序

按共享结构影响从大到小：

1. `catalog`：应用壳、资源网格、底部胶片区；
2. `edit`：画布、右侧编辑栏、顶栏动作；
3. `presets`：预置资源密度和选中态；
4. `tool-expanded`：工具标题、滑杆、分栏、应用状态；
5. `layer-stack`；
6. `layer-library`；
7. `multi-image`。

共享壳层改动后必须重跑全部七状态；局部组件改动至少重跑目标状态和一个共享壳状态。

### 7.4 单状态循环

1. 用应用内 Browser 固定 `2880×1800`、locale、timezone 和 motion；
2. 截取 current-build 状态；
3. 运行 UI comparator；
4. 根据最大连续误差区域判断是 geometry、typography、component state 还是 token；
5. 只修一个层级；
6. 重截目标状态；
7. 运行 frontend test/build 和七状态回归。

### 7.5 验证

```bash
cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

### 7.6 准出

- 七状态均 shape match；
- 每项 `MAE <= 0.03`、changed pixel ratio `<= 0.02`；
- execution evidence 仍是当前 frontend build；
- 黑白、图层、Workspace 和 Preview 行为测试不回退；
- 冻结桌面 viewport 通过前，不扩展移动端像素对齐工作。

## 8. P3：本项目十条交互合同

### 8.1 实现策略

以 P1 原生 observation 为状态真值。只在缺少稳定可访问目标时增加语义 accessible name 或 `data-testid`；它们不能改变视觉布局。

为 Browser 执行增加一个最小聚合器，例如：

- `scripts/build_interaction_browser_execution.py`；
- `tests/test_interaction_browser_execution_builder.py`。

Browser 原始 trace 由 Codex App 的 in-app Browser 采集，聚合器只负责验证字段、计算 hash 和生成 `interaction-browser-execution.json`，不在 Python 中复制浏览器自动化。

### 8.2 逐合同状态要求

| 合同 | 必须对齐的核心状态 |
|---|---|
| Catalog import/select | asset/project 只创建一次；source hash 一致；选择后进入 Edit |
| Preset preview/apply | preview 不写 edit；apply 只写一次；顺序一致 |
| Slider drag | 数值显示和 project 参数均为 `0.65`；只产生一条语义编辑 |
| Panel collapse | 画布扩展；恢复后 edit stack 不变 |
| Layer lifecycle | 创建、排序、50% opacity、删除在 UI/project 同步 |
| Undo/redo | 恢复相同 edit id 和参数，不新建等价 edit |
| Before/after | 只切 view state，不发 edit mutation |
| Zoom/pan/fit | 只改 view state；fit 恢复画布 |
| Export | 只发一个请求；busy 清除；content-type 和尺寸正确 |
| Multi-image | preview ready 前禁用导出；frame hash 和最终 render hash 稳定 |

### 8.3 异步一致性

涉及 preview、项目切换和长任务的请求必须使用稳定 generation/key：

- 新选择发生后，旧响应不得覆盖当前 preview/project；
- 组件卸载停止轮询，但不取消服务端 job；
- 终态前导出保持 disabled；
- terminal 结果完整读取后才 merge 到项目。

主要入口：`frontend/src/App.tsx`、`frontend/src/api.ts`、`frontend/src/useAnalysisJob.ts` 和相关组件。

### 8.4 验证与准出

```bash
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

准出要求：executed `10/10`、passed `10/10`、issue count 0；每条 final screenshot 和 native observation link/hash 有效；所有 waits 已声明；`fixed_sleep=false`。

## 9. P4：效果算法收敛

### 9.1 先做失败分类，不先改参数

对每个失败 case 生成并保存：

- source/native/candidate 三联图；
- RGB 和 luma delta；
- heatmap、边缘 ROI、天空/人物/背景 ROI；
- shape、MAE、SSIM、均值、梯度和 changed-pixel；
- candidate 双跑 hash。

先把失败归入 contract、tone、mask、geometry、asset、noise/randomness 或 color-management。若无法解释根因，不进入实现。

### 9.2 单能力闭环

每个能力严格执行：

1. 选一个主失败 case、一个 exact anchor、一个 holdout 和一个中性/no-op；
2. 写能复现共享根因的窄测试；
3. 只改一个 helper、pipeline 或 wrapper；
4. 只 force 该 capability 的候选；
5. 跑主 case、exact、holdout 和同域已通过项；
6. 指标改善但未过时保持 failed；
7. 通过后锁定 candidate hash，再进入下一能力。

### 9.3 批次顺序

#### E1：低误差和合同类

- `face_ai` 主 case：MAE `0.030197`，先检查 mask/ROI 边界尾差；
- `lut_mapping`：MAE `0.035247`、SSIM `0.999137`，先核对工作色域、LUT 插值和 opacity；
- `pro_contrast`、`color_adjustments`、`color_enhancer`、`high_key`、`fade`：优先关闭曲线和值域问题。

这一批目标是验证效果收敛循环和共享颜色合同，不为快速变绿修改门限。

#### E2：纹理和噪声

- `denoise`、`denoise_laplacian`：原生等级与强度分开建模，保留 Mid 前置；
- `grain`：大小、强度、分布和确定性 seed 分开；
- `structure_ai`、`ai_enhance`：检查局部结构 mask 和 halo；
- `radiance`：检查低频 glow 与高光保护。

使用现有 sensor-noise fixture；不重新采样已 valid 的 Denoise reference。

#### E3：人物和深度

- `face_ai`、`face_enhancer`、`bokeh_ai`、`slim_people`、`depth_volume`；
- 统一 detector/landmark/portrait mask 的坐标、排序、padding 和 feather；
- Slim People 只做人体局部 warp，保护背景直线；
- depth 固定 near/far、值域、resize 和无效值语义；
- 无脸/无人输入必须 no-op 或符合原生合同，不能全图变化。

模型 wrapper 的加载、预处理和稳定输出只在 `ai/model` 修改；效果强度、mask 合成和业务顺序留在 `ai/pipeline`/`image_ops`。

#### E4：天空和光照

- `blue_hour`、`fog`、`sunrays`、`magic_lights`、`new_neon_light`、`landscape_enhancer`；
- 复用经过验证的 sky/human/reflection/horizon 合同；
- Blue Hour 分离天空冷色、地面曝光和暖光；
- Fog 固定深度方向和边缘保护；
- Sunrays 固定太阳坐标、遮挡积分和衰减；
- Magic/Neon 的低全局 MAE 不代表通过，必须检查局部 ROI、stroke 和光源位置。

Sky E2E 和 Overlay `38/38` 是硬回归门禁。

#### E5：全局风格和组合效果

- `default_effects`、`color_toning`、`vignette`、`grain` 剩余锚点；
- Default Effects 先拆解真实编辑图顺序，不用单个全局 tone curve 近似组合效果；
- Vignette 对齐中心、半径、羽化、曝光曲线和高光保护；
- 中性锚点必须保持中性，正负值必须保持方向一致。

### 9.4 定向候选和比较命令

主效果：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/work/<capability-id>-smoke.json
```

Exact：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-exact-incremental \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-exact-incremental \
  --capability <capability-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/work/<capability-id>-exact.json
```

### 9.5 原生重观察的唯一允许方式

若 failure registry 先证明 reference 无效：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --dry-run

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --allow-ui-control
```

第二条必须确认第一条只选择一个记录后才能执行。

### 9.6 准出

- 主效果 45/45；
- exact 69/69；
- Preset、Sky、Overlay、黑白 3 个锚点不回退；
- candidate 双跑 hash 稳定；
- required 模型仍 22/22；
- 没有新增 fixture/hash 特例或阈值例外。

## 10. P5：Panorama 原生语义

### 10.1 当前问题

`image_ops/merge/panorama.py` 当前仍是 overlap translation + feather，并使用测量比例做最终 resize。它能匹配 shape，但不能解释 Luminar 的投影、warp、接缝和非对称 crop，当前 MAE 约 `0.0819`、SSIM 约 `0.8155`。

### 10.2 执行分解

#### G1：几何诊断

1. 比较三张输入和原生输出的稳定特征/边缘位置；
2. 判断误差是否需要旋转、透视或柱面投影，而不只平移；
3. 保存估计变换、有效 canvas 和 reference 边界；
4. 删除最终比例 resize 之前先写 shape/crop 回归，防止用 resize 掩盖问题。

#### G2：最小几何实现

- 如果平移/旋转即可解释 reference，继续使用 NumPy/Pillow；
- 只有诊断明确需要 homography/局部 warp 时，才评估增加单一、离线可用的图像配准依赖；不得先引入大依赖再寻找用途；
- 实现特征匹配、异常匹配剔除、变换和 canvas bounds；
- 根据有效像素 mask 推导 auto-crop，不使用固定 `1070/1080`、`1410/1440` 比例。

#### G3：接缝和颜色

1. 对齐重叠区曝光和白平衡；
2. 从局部误差选择 seam；
3. 先 feather，再在确有收益时增加 multiband blending；
4. 对接缝 ROI、结构线和天空区域分别验证。

主要入口：

- `image_ops/merge/panorama.py`；
- `services/multi_image/service.py`；
- `tests/test_panorama_merge.py`。

### 10.3 验证

```bash
.venv/bin/python -m pytest tests/test_panorama_merge.py tests/test_multi_image_validation_data.py -q
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke.json
```

### 10.4 准出

- Panorama shape、MAE、SSIM 全过；
- 接缝 ROI 没有明显结构断裂；
- HDR、Focus 继续通过；
- 不存在最终强制 resize 或冻结输入专用 crop 常量；
- Multi-image `3/3`。

## 11. P6：模型和长任务保护性回归

### 11.1 范围

Required 模型和长任务当前已经通过，本阶段只保护效果/UI 修改不破坏现有合同，不扩展 66 个 optional 模型。

### 11.2 模型层边界

- `ai/model` 只负责本地权重、preprocess、predict、postprocess、稳定 `InferenceResult` 和 unload；
- factory 只实例化，loader 只管理缓存和生命周期；
- mask 合成、工具强度、模型选择和调用顺序不进入 model wrapper；
- 不在运行时隐式下载权重；
- 加载失败不得设置 `_loaded=True` 或返回伪成功。

### 11.3 长任务故障回归

保持并验证：

- 第 N 个模型后 worker 重启，已完成 checkpoint 不重跑；
- lease 持续续租，旧 worker 不覆盖新 owner/cancel/terminal；
- 页面卸载只停止轮询，不取消服务端 job；
- 刷新/切项目后恢复正确 latest job；
- terminal 后完整 result/artifact 拉取成功才 merge project；
- artifact 缺失/hash 错误时 data-chain fail closed；
- loader 淘汰调用 `unload_model()`。

### 11.4 验证

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root .
.venv/bin/python -m pytest \
  tests/test_active_model_contracts.py \
  tests/test_candidate_model_invocations.py \
  tests/test_model_loader.py \
  tests/test_model_outputs.py \
  tests/test_model_source_map.py -q

cd frontend
npm test -- useAnalysisJob
cd ..
```

准出：required model `22/22`、pipeline blocked 0、candidate invocation `22/22`；长任务恢复后结果完整且无重复推理。

## 12. P7：全量门禁、清理和发布

### 12.1 回归顺序

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/run_overlay_e2e_validation.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

### 12.2 质量门禁连续双跑

第一次：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-1.json
```

在不修改代码、配置、输入、reference、素材、viewport 和环境的情况下执行第二次：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-2.json
```

比较两轮：gate id/status/case count、candidate tree hash、UI/interaction evidence hash、模型合同 hash。任何 required failure 或非预期 hash 漂移都停止发布。

### 12.3 最终清理

先 dry-run：

```bash
.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-release-dry-run.json
```

只在清单全部属于可重建 workspace/临时文件时执行 `--apply`。随后再次 dry-run，要求 path count 和 reclaimable bytes 都为 0，并重跑数据链和最终门禁。Canonical、reference、current candidate、interaction observation 和发布报告不得删除。

### 12.4 发布产物

- 两轮 quality gate 报告及 SHA-256；
- source/reference/candidate/UI/interaction manifest；
- 当前 failure registry 应为空；
- 前后对比报告；
- 明确写作“冻结范围内可审计等价”，不扩大结论。

## 13. 修改入口和验证矩阵

| 目标 | 修改位置 | 窄验证 |
|---|---|---|
| 原生 interaction observer | `scripts/run_luminar_interaction_observations.py`、`scripts/luminar_capture/` | observer tests、单合同 dry-run、native schema/hash |
| Browser interaction evidence | 新 aggregate builder、interaction diagnostics | builder tests、`validate_interaction_execution.py` |
| UI 壳和状态 | `frontend/src/App.tsx`、`frontend/src/components/`、`frontend/src/styles.css` | 组件测试、build、七状态 comparator |
| UI 配置 | `configs/ui/editor.json` | UI manifest、七状态截图，不增加视觉分支 |
| 效果语义 | `image_ops/effects/`、`ai/pipeline/` | capability test、smoke/exact/holdout |
| 模型 wrapper | `ai/model/`、`configs/model.yaml` | model validator、真实 invocation、loader tests |
| Panorama | `image_ops/merge/panorama.py`、`services/multi_image/` | panorama tests、Multi-image 3-case |
| 长任务 | `services/jobs/`、storage、`frontend/src/useAnalysisJob.ts` | checkpoint/lease/hook 故障测试 |
| 采样合同 | `scripts/luminar_capture/`、queue builders | resume dry-run、effect-change/data-chain |
| 门禁 | `scripts/run_quality_gates.py`、validators | 窄 gate + 最终连续双跑 |
| 数据治理 | `scripts/cleanup_test_data.py`、prune scripts | dry-run、postcheck、数据链回归 |

## 14. 单能力执行模板

每个效果、UI 状态或交互合同都使用同一闭环：

1. **基线**：记录目标 case/state/contract、当前指标、artifact hash。
2. **假设**：只写一个可证伪根因；列出可能受影响的通过项。
3. **窄测试**：先增加或选择能复现根因的最小测试。
4. **最小实现**：只改根因所在层，不顺手重构邻接代码。
5. **目标验证**：重新生成目标候选/截图/执行记录。
6. **同域回归**：跑 exact、holdout、中性 anchor 和已通过同域项。
7. **全域保护**：对应 UI/模型/Sky/Overlay/Multi-image 门禁不回退。
8. **记录**：保存 before/after、命令、指标和 hash。
9. **决定**：通过则锁定；未过则保留真实失败；出现系统性回退立即回滚本批代码。

一个批次完成的定义不是“代码写完”，而是目标门禁通过且保护门禁不回退。

## 15. 停止条件与回退

### 15.1 立即停止条件

- ready semantic key 再次进入 effect sampling 队列；
- app build、source、素材、viewport、readback 或 Reset 状态不匹配；
- Browser screenshot 不属于当前 frontend build；
- 需要放宽阈值、固定 resize、删除 required case 或手改 hash 才能通过；
- 单案例改善导致 holdout、已通过能力、Preset、Sky、Overlay、HDR/Focus 回退；
- 模型 success 但 result/artifact 不完整；
- interaction 使用未声明 wait 或 fixed sleep；
- 同一共享根因批次中多数 case 同方向恶化。

### 15.2 回退原则

- 代码按最小批次回退；不回退无关代码；
- canonical、attempt、observation、失败截图和 comparator 报告不随代码回退删除；
- 算法、合同、素材、阈值修改必须分开批次，方便定位；
- 清理只删除脚本明确识别的可重建数据；
- 任何历史版本逻辑都不作为回退方案重新引入。

## 16. 最终验收清单

- [ ] P0 baseline/failure registry 与当前门禁完全一致。
- [ ] 已有 ready 效果 reference 没有被全量重采。
- [ ] 原生 interaction observations 10/10，app/fixture/artifact hash 完整。
- [ ] UI current-build evidence 7/7 且 UI parity 7/7。
- [ ] Browser interaction execution 10/10，issue 0，fixed sleep 0。
- [ ] 主效果 45/45。
- [ ] Exact 69/69，pending/invalid/duplicate 0。
- [ ] Preset、Sky、Overlay 38/38 保持通过。
- [ ] HDR、Focus、Panorama 3/3。
- [ ] Required logical model 22/22；模型模块/调用/生命周期门禁保持通过。
- [ ] 长任务重启、刷新、切项目后结果完整且 hash 可验证。
- [ ] Python、Ruff、frontend test/build 全通过。
- [ ] 两轮 exact quality gate required failure 均为 0，关键 hash 稳定。
- [ ] 最终 cleanup postcheck 为 0，数据链无新增 issue。
- [ ] 当前运行代码不存在 1.25/1.26 兼容分支和单 fixture 特例。
- [ ] 只有以上全部完成后更新 manifest 和对齐声明。
