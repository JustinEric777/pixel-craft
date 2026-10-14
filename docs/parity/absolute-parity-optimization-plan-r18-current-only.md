# Luminar Neo 1.28 本地核心绝对对齐优化计划（R18，Current-only）

> 本计划将 R17 最终确认的缺口转换为可依次执行、逐项验收的工程工作包。唯一参考对象是本机 Luminar Neo `1.28.0 (23071)` 中文版，范围是当前冻结的 40 个本地免费核心能力、210 个 UI 状态、124 条交互契约和 Native catalog/History schema v155。计划不实现旧 profile、旧状态 ID、旧证据、旧 JSON 项目或旧 schema 的读取、迁移、双写、回退和兼容分支。

## 目录

- [1. 目标与完成标准](#1-目标与完成标准)
- [2. 当前基线](#2-当前基线)
- [3. 执行边界](#3-执行边界)
- [4. 依赖关系与执行顺序](#4-依赖关系与执行顺序)
- [5. WP0：冻结 current-only 基线](#5-wp0冻结-current-only-基线)
- [6. WP1：改造 Browser 采集入口](#6-wp1改造-browser-采集入口)
- [7. WP2：恢复 Native 采集准入](#7-wp2恢复-native-采集准入)
- [8. WP3：完成 210 个 Native UI 参考](#8-wp3完成-210-个-native-ui-参考)
- [9. WP4：完成 210 个 zpixel UI 状态对齐](#9-wp4完成-210-个-zpixel-ui-状态对齐)
- [10. WP5：完成 124 条 Native 交互](#10-wp5完成-124-条-native-交互)
- [11. WP6：完成 124 条 Browser 交互](#11-wp6完成-124-条-browser-交互)
- [12. WP7：实现单一 v155 Native persistence](#12-wp7实现单一-v155-native-persistence)
- [13. WP8：完成效果样本与算法收敛](#13-wp8完成效果样本与算法收敛)
- [14. WP9：全量验收与 current-only 清理](#14-wp9全量验收与-current-only-清理)
- [15. 文件修改入口](#15-文件修改入口)
- [16. 验证矩阵](#16-验证矩阵)
- [17. 风险、停止条件与数据安全](#17-风险停止条件与数据安全)
- [18. 最终执行清单](#18-最终执行清单)

---

## 1. 目标与完成标准

### 1.1 最终目标

在冻结范围内，使 zpixel 当前代码与本机 Luminar Neo 的以下行为同时一致：

1. UI：工作区、工具面板、参数状态的布局、文字、控件、可见性和像素结果一致。
2. 交互：事件顺序、等待条件、可见反馈、API 状态、撤销/重做和最终状态一致。
3. 工具效果：preview/export、参数曲线、素材语义、模型输出和合成结果落入 Native 重复执行方差范围。
4. 持久化：项目、历史、图层、蒙版、工作流、预设、preview/export 可由 Luminar 重开并继续编辑。
5. 证据：所有通过项绑定当前 reference ID、matrix fingerprint、fixture hash、build hash 和 artifact SHA-256。

“绝对对齐”只在上述冻结范围和固定环境内验收，不外推到未采样图片、付费内容、生成式能力或其他 Luminar 版本。

### 1.2 总体验收标准

| 维度 | 完成标准 |
|---|---:|
| UI Native reference | `210/210 verified` |
| UI Browser execution | `210/210 passed` |
| UI parity | `210/210 passed` |
| Native interaction | `124/124 passed` |
| Browser interaction | `124/124 passed` |
| Main output parity | `40/40 passed` |
| Exact incremental parity | `98/98 passed` |
| Native persistence | 7 类 roundtrip 全部通过 |
| Absolute scope | `issue_count=0` |
| Exact quality gates | `37/37 passed` |
| Python | 全量测试通过，R18 新增测试无 skip |
| Frontend | 全量测试和 production build 通过 |

任一指标未满足时，最终状态保持 `blocked`，不得使用“功能可运行”“大部分一致”或旧 evidence 宣布完成。

## 2. 当前基线

### 2.1 冻结标识

| 项目 | 当前值 |
|---|---|
| Reference ID | `luminar-neo-macos-1.28.0-23071` |
| App | Luminar Neo `1.28.0 (23071)` |
| Bundle ID | `com.skylum.luminarneo` |
| Locale | `zh-Hans` |
| Logical viewport | `1440×900` |
| Physical viewport | `2880×1800` |
| Device scale factor | `2.0` |
| UI matrix | 210 records |
| UI fingerprint | `9c23735db6cae91827056f2dea1d88edab0458fbd8938c3c615909d9121549fe` |
| Interaction matrix | 124 records |
| Interaction fingerprint | `e9d5cf0c0c68d670c882d58c2c3c0f385ab6892b6aed0636e4c19421b4edf37f` |
| Native schema | v155 |

### 2.2 R17 未关闭项

| 缺口 | 当前值 |
|---|---:|
| UI Native reference | `0/210` |
| UI Browser execution | `0/210` |
| Native interaction | `0/124` |
| Browser interaction | `0/124` |
| Native parameter handler | 缺 114 |
| Main effect | `35/40` |
| Exact effect | `50 passed / 6 failed / 42 pending-reference` |
| Amount anchor | 缺 9 个能力 |
| Holdout | 40 个能力均不足 |
| 未表示参数 | 6 个 crop 参数 |
| Native persistence | 缺 7 类 roundtrip |
| Exact gates | `26/37 passed` |
| Absolute scope | `933 issues`，存在记录级重叠 |

### 2.3 R18 新确认的采集入口缺口

1. `test_data/parity/ui-browser-capture-plan.json` 仍只有 16 个旧 `state`。
2. `frontend/scripts/capture-ui-dpr2.mjs` 仍以 `state.state` 生成文件名和记录。
3. `frontend/scripts/capture-interaction-dpr2.mjs` 仍读取旧 `contracts.contracts` 结构。
4. Browser interaction recorder 只支持 6 个无 `workflow:` 前缀的旧 contract ID。

这些入口必须在正式采集前改为直接消费当前 210/124 矩阵；不增加旧格式兼容解析。

## 3. 执行边界

### 3.1 必须遵守

1. 先取得 Native 真值，再修改 zpixel UI、交互、持久化或效果算法。
2. 每次只处理一个工作包或一个明确批次，窄范围验证通过后再进入下一批。
3. Native 和 Browser evidence 都写入当前 profile 的活动目录，并原子替换 manifest。
4. 每个 artifact 都保存 SHA-256；修改矩阵、fixture 或 frontend build 后，旧 evidence 自动失效。
5. Native 自动化只使用 accessibility locator、可观察状态和允许的等待条件。
6. Browser 自动化只使用当前 DOM/ARIA 契约、当前 API 状态和当前矩阵 ID。
7. Native persistence 只在隔离临时 catalog/project 上写入，不修改用户正在使用的 Luminar 项目。
8. 算法调整必须由至少两个新 Native holdout 支撑，不使用单图目测调参。

### 3.2 明确禁止的兼容逻辑

- 不读取 UI `state`、来源别名或旧 manifest version 1。
- 不读取无 `workflow:`/`tool:` 前缀的旧 interaction ID。
- 不支持 `contracts.contracts` 与 `records` 双格式。
- 不保留 16 状态 Browser capture plan 作为 fallback。
- 不保留 JSON project 与 Native project 双读、双写或自动迁移。
- 不实现 schema v154 及更早版本 reader/writer。
- 不根据旧报告、旧截图或归档 evidence 决定当前能力是否通过。
- 不在 locator 失败时退回屏幕绝对坐标。
- 不在 Native History 字段未知时写默认猜测值。

### 3.3 当前数据切换原则

JSON workspace 数据不迁移。Native repository 切换时，开发与验证数据从冻结 source fixtures 重新创建；无法由当前 fixture 重建的数据不进入活动验收集。切换完成后删除活动代码中的 `JsonProjectRepository` 组合、导入和专用测试，不保留运行时开关。

## 4. 依赖关系与执行顺序

```text
WP0 冻结 current-only 基线
  │
  ▼
WP1 Browser 采集入口矩阵化
  │
  ▼
WP2 Native 采集环境准入
  │
  ├──────────────┐
  ▼              ▼
WP3 Native UI    WP7A persistence controlled delta
  │              │
  ▼              ▼
WP4 Browser UI   WP7B v155 codec + repository
  │
  ▼
WP5 Native interaction
  │
  ▼
WP6 Browser interaction
  │
  ▼
WP8 Native effect samples → algorithm convergence
  │
  ▼
WP9 全量门禁、current-only 清理与最终报告
```

主执行顺序固定为 WP0 → WP1 → WP2 → WP3 → WP4 → WP5 → WP6 → WP7 → WP8 → WP9。WP7A 可以在 WP3/4 的批次间采集 controlled delta，但 WP7B 的 repository 切换只能在七类 roundtrip 全部通过后执行。

相对工作量用于安排批次，不代表固定工期：

| 工作包 | 优先级 | 相对工作量 | 外部依赖 |
|---|---:|---:|---|
| WP0 current baseline | P0 | S | 无 |
| WP1 Browser recorder | P0 | M | 无 |
| WP2 Native admission | P0 | S | 用户解锁、隔离显示和输入 |
| WP3 Native UI | P0 | L | WP2 |
| WP4 Browser UI | P0 | XL | WP1、WP3 |
| WP5 Native interaction | P0 | XL | WP2、WP3 |
| WP6 Browser interaction | P0 | XL | WP4、WP5 |
| WP7 Native persistence | P0 | XL | WP2、controlled delta |
| WP8 effects | P1 | XL | WP2、Native 样本 |
| WP9 final gates | P0 | M | WP0–WP8 全部 passed |

每个工作包使用以下状态：

- `pending`：前置条件未满足。
- `in-progress`：正在修改或采集。
- `blocked`：外部条件或证据不足，禁止越过。
- `passed`：本工作包的完成定义全部满足。

## 5. WP0：冻结 current-only 基线

### 5.1 目标

确保 R18 执行期间只有一套 210/124 当前契约，并建立变更即失效的指纹规则。

### 5.2 修改入口

- `configs/parity/core-ui-state-matrix.json`
- `configs/parity/core-interaction-matrix.json`
- `configs/reference.yaml`
- `configs/parity/native-capture-environment.json`
- `scripts/validate_absolute_scope_coverage.py`
- `scripts/run_quality_gates.py`

### 5.3 执行步骤

1. 校验 UI matrix 恰好包含 16 个 workspace、80 个 tool-panel、114 个 tool-parameter 状态。
2. 校验 interaction matrix 恰好包含 10 个 workflow、114 个 tool-parameter contract。
3. 校验所有 ID 唯一、非空，且 UI/interaction fingerprint 为 64 位 SHA-256。
4. 校验 reference ID、App version、build、bundle 和 locale 与活动 profile 一致。
5. 在 validator 测试中加入旧 `state`、旧 ID、旧 fingerprint、旧 contract container 必须失败的用例。
6. 记录 R18 起始 absolute scope 与 exact gate snapshot；只用于前后比较，不参与运行时判定。

### 5.4 交付物

- current matrix audit JSON。
- current-only negative tests。
- R18 起始 gate snapshot。

### 5.5 验证

```bash
.venv/bin/python -m pytest \
  tests/test_absolute_scope_coverage.py \
  tests/test_interaction_contracts.py \
  tests/test_interaction_execution.py -q
.venv/bin/python -m ruff check \
  scripts/validate_absolute_scope_coverage.py \
  scripts/validate_interaction_execution.py
```

### 5.6 完成定义

- 矩阵数量为 210/124，分组数量精确匹配。
- 所有旧格式 negative tests 通过，即旧格式被拒绝。
- 本工作包不修改任何 Native 或 Browser evidence。

## 6. WP1：改造 Browser 采集入口

### 6.1 目标

让 UI 和 interaction Browser recorder 直接消费当前矩阵，移除旧 16 状态和旧 interaction container/ID。

### 6.2 UI capture plan

修改入口：

- `test_data/parity/ui-browser-capture-plan.json`
- `frontend/scripts/capture-ui-dpr2.mjs`
- 新增 `scripts/build_ui_browser_capture_plan.py`
- `configs/ui/editor.json`
- `configs/capabilities/parameter-schema.json`

执行步骤：

1. 新增 plan builder，输入当前 UI matrix、editor config 和 parameter schema。
2. 使用 `scripts/prepare_ui_evidence_fixture.py` 从冻结的 46 张输入生成唯一 current fixture 和 `ui-evidence-fixture-manifest.json`。
3. 为 16 个 workspace state 编写显式 Browser recipe。
4. 对 80 个 tool-panel state 由 capability ID 生成“进入 edit → 定位工具 → collapsed/expanded”步骤。
5. 对 114 个 parameter state 由 parameter type 生成步骤：
   - float：101 条，设置 canonical 非默认值并读回。
   - array：5 条，执行 crop box 或 stroke recipe。
   - asset：3 条，选择固定 asset ID。
   - boolean：3 条，切换并读回。
   - enum：2 条，选择固定非默认项并读回。
6. Builder 必须产出恰好 210 条 `matrix_state_id`，不写 `state`。
7. 修改 `capture-ui-dpr2.mjs`，命令行过滤、文件名、capture JSON 和 run summary 全部使用 `matrix_state_id`。
8. 删除旧 16 状态 plan 内容，由 builder 生成 current plan；不保留旧 plan 文件副本在活动路径。
9. 禁止 `wait` 固定毫秒作为状态完成依据；只允许用于截图前短暂绘制稳定，业务完成必须由 selector、文本、API 或 image stability 判断。

### 6.3 Interaction recorder

修改入口：

- `frontend/scripts/capture-interaction-dpr2.mjs`
- `scripts/build_interaction_browser_execution.py`
- `configs/parity/core-interaction-matrix.json`

执行步骤：

1. recorder 只读取 `records`，删除 `contracts.contracts` 解析。
2. contract ID 直接使用当前 `workflow:*` 和 `tool:*` ID。
3. 保留 10 个 workflow 的显式 handler，不把旧 6 ID 映射到新 ID。
4. 新增 5 类参数事件执行器：float、array、asset、boolean、enum。
5. 每条参数 contract 必须有 current locator、canonical value、readback 和 visible/API assertions；参数类型执行器不能包含屏幕坐标 fallback。
6. recorder 对 124 条 contract 做 dry-run 覆盖检查；任何 unsupported contract 使进程退出非零。
7. raw execution 必须写当前 matrix fingerprint、frontend build hash、DPR、locale、timezone 和 contract events。

### 6.4 测试

新增或更新：

- UI plan 恰好覆盖 210 个 ID。
- capture plan 没有 `state` 字段。
- interaction recorder 恰好覆盖 124 个 ID。
- 旧 container、旧 ID、未知 parameter type、无 locator 均失败。
- screenshot、DOM、AX、trace 或 log 缺失时 builder 失败。

### 6.5 验证

```bash
.venv/bin/python scripts/prepare_ui_evidence_fixture.py \
  --data-root test_data/outputs/luminar-1.28.0-23071/ui-evidence-fixture
.venv/bin/python scripts/build_ui_browser_capture_plan.py
node frontend/scripts/capture-ui-dpr2.mjs \
  --plan test_data/parity/ui-browser-capture-plan.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-dry-run \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-dry-run \
  --dry-run true
node frontend/scripts/capture-interaction-dpr2.mjs \
  --contracts configs/parity/core-interaction-matrix.json \
  --fixture test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-manifest.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-dry-run \
  --raw-output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-dry-run.json \
  --dry-run true
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

`--dry-run true` 是本工作包要新增的只读入口；它只验证矩阵、recipe、locator 和参数覆盖，不启动 Chrome、不写正式 evidence。

### 6.6 完成定义

- UI recorder current dry-run 为 `210/210 supported`。
- Interaction recorder current dry-run 为 `124/124 supported`。
- 活动 capture plan 和 raw evidence schema 中不存在旧 `state` 或旧 contract ID。
- 不要求在本工作包产生正式截图。

## 7. WP2：恢复 Native 采集准入

### 7.1 外部前置条件

1. 用户手动解锁 Mac。
2. Luminar Neo `1.28.0 (23071)` 可以启动并进入中文 UI。
3. 自动化期间用户不操作鼠标和键盘。
4. 使用独立于日常工作项目的验证 catalog、fixtures 和输出目录。

### 7.2 修改入口

- `configs/parity/native-capture-environment.json`
- `configs/luminar_sampling.yaml`
- `scripts/luminar_capture/preflight.py`
- `scripts/luminar_capture/app_controller.py`
- `scripts/luminar_capture/accessibility_driver.py`

### 7.3 执行步骤

1. 建立 dedicated display/session，记录 provider 与不可复用的 session ID。
2. 验证 logical/physical viewport、DPR、locale、timezone、bundle、version 和 build。
3. 验证 isolated input：采集期间只允许自动化事件源。
4. 记录 `verified_at`，把 capture environment 的两项 verified 改为 true。
5. 运行 workspace、tool-panel、parameter 三个只读 AX 探针。
6. 对每个探针保存全屏截图、window bounds、AX snapshot 和环境 JSON。
7. 连续运行 preflight 三次；三次结果必须一致，且没有窗口尺寸漂移。

### 7.4 验证

```bash
.venv/bin/python scripts/luminar_capture/run_capture.py --help
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --contract-id workflow:catalog-photo-context-submenu \
  --allow-ui-control
```

第二条命令只在三个只读探针通过后执行；它会产生正式证据，因此必须使用验证 fixture。

### 7.5 停止条件

出现以下任一情况立即停止，不修改 verified 字段：

- Mac 再次锁屏。
- display 或 input 无法证明隔离。
- Luminar 版本、build、locale 或 viewport 不匹配。
- AX tree 为空或关键 workspace 无法定位。
- 用户输入与自动化输入发生混用。

### 7.6 完成定义

- `native-capture-environment.json` 状态为 verified。
- provider、session ID、verified_at 非空。
- 三类探针和三次 preflight 全部通过。

## 8. WP3：完成 210 个 Native UI 参考

### 8.1 批次划分

| 批次 | 内容 | 数量 |
|---|---|---:|
| UI-A | workspace-state | 16 |
| UI-B | tool-panel-state | 80 |
| UI-C1 | float parameter | 101 |
| UI-C2 | array parameter | 5 |
| UI-C3 | asset parameter | 3 |
| UI-C4 | boolean parameter | 3 |
| UI-C5 | enum parameter | 2 |
| 合计 |  | 210 |

### 8.2 修改入口

- `scripts/luminar_capture/queue_handlers.py`
- `scripts/luminar_capture/ui_evidence.py`
- `scripts/luminar_capture/semantic_locator.py`
- `scripts/luminar_capture/stability.py`
- `scripts/build_ui_reference_manifest.py`
- `scripts/validate_ui_references.py`

### 8.3 执行步骤

1. 为 UI-A 的 16 个 workspace 使用显式 recipe；每个 workspace 从 reset fixture 开始。
2. UI-B 按 capability 顺序采集 collapsed/expanded，状态间重置 tool selection。
3. UI-C 使用 WP1 的同一 canonical parameter value，但 Native 操作由 AX locator 完成。
4. 每个状态保存：
   - `matrix_state_id`
   - current matrix fingerprint
   - fixture ID/hash
   - app version/build/bundle
   - viewport/window bounds
   - full-screen screenshot
   - AX snapshot
   - capture environment
   - artifact SHA-256
5. 每个批次结束后重建 manifest 并运行 validator；不能等 210 条全部结束才发现批次错误。
6. 对 workspace、tool-panel、float、array、asset、boolean、enum 各选择一个代表状态，重复采集三次以测量 Native UI 方差。
7. 根据重复采集方差冻结 UI threshold；`configs/parity.yaml` 中 provisional note 必须被实际测量说明替换。
8. 如果同一状态的 Native 重复截图超出方差门限，先消除动画、加载或系统渲染不稳定，再继续采集。

### 8.4 验证命令

```bash
.venv/bin/python scripts/build_ui_reference_manifest.py
.venv/bin/python scripts/validate_ui_references.py
.venv/bin/python scripts/validate_sampling_queue_captures.py
```

### 8.5 完成定义

- Manifest version 2，current fingerprint，`210 verified / 0 invalid / 0 missing`。
- 每种状态类型至少有一个三次重复方差样本。
- UI threshold 有测量依据，不再标记 provisional。
- 没有复制截图、相邻状态代替或人工改写 status。

## 9. WP4：完成 210 个 zpixel UI 状态对齐

### 9.1 原则

按 UI-A → UI-B → UI-C 的相同顺序修改。每次只处理一个组件族，组件单测、Browser capture 和 pixel parity 全过后再进入下一族。

### 9.2 修改入口

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/components/CatalogWorkspace.tsx`
- `frontend/src/components/PresetBrowser.tsx`
- `frontend/src/components/WorkspaceRail.tsx`
- `frontend/src/components/ToolPanel.tsx`
- `frontend/src/components/LayersPanel.tsx`
- `frontend/src/components/EditHistoryPanel.tsx`
- `frontend/src/components/PreviewPanel.tsx`
- `frontend/src/components/ExportDialog.tsx`
- `frontend/src/components/WorkflowWorkspace.tsx`
- `frontend/src/components/AssetPicker.tsx`
- `frontend/src/components/SkyControls.tsx`
- 对应 `*.test.tsx`

### 9.3 执行步骤

1. 使用 WP1 生成的 fixture data root 启动 API，并在 `5175` 启动当前 frontend。
2. UI-A：对齐 16 个 workspace 的整体 grid、header、rail、panels、dialog 和 multi-image 状态。
3. UI-B：对齐 40 个工具的顺序、名称、图标、collapsed/expanded 高度、section 间距和滚动位置。
4. UI-C：按 5 种 parameter type 对齐 label、value、slider/selector/toggle/asset/stroke/crop UI。
5. 所有组件使用 current capability/parameter ID；不增加旧 label 或旧 key 映射。
6. 加入 `data-*`/ARIA 标识时，以用户可见语义为准，不写只为截图脚本服务的隐藏状态。
7. 每个小批次运行组件测试和单状态 DPR2 capture。
8. 小批次通过后运行该组全部状态；全部组通过后生成 210 条 Browser execution。
9. Browser capture 必须保存 PNG、DOM snapshot、AX tree、build hash 和环境信息。
10. 使用 `build_ui_browser_execution.py` 发布证据，再运行 execution validator 和 UI parity。
11. 任何样式修改导致其他已通过状态回归时，先修复回归，不扩大阈值。

### 9.4 建议批次大小

- Workspace：每批 4 个。
- Tool panel：每批 5 个 capability，即 10 个状态。
- Parameter：每批不超过 10 条，crop/asset/stroke 单独成批。

批次大小是上限，不是必须凑满；复杂状态单独处理。

### 9.5 验证

先分别在两个终端启动：

```bash
ZPIXEL_DATA_ROOT=test_data/outputs/luminar-1.28.0-23071/ui-evidence-fixture \
  .venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5175
```

再运行测试和正式 capture：

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix frontend run capture:ui:dpr2 -- \
  --plan test_data/parity/ui-browser-capture-plan.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates
.venv/bin/python scripts/build_ui_browser_execution.py \
  --fixture-manifest test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-manifest.json \
  --browser-version <actual-browser-version>
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

`<actual-browser-version>` 必须来自本次 capture run，不能手写或沿用旧值。

### 9.6 完成定义

- Browser execution `210/210`，无 missing、stale、duplicate 或 empty artifact。
- UI parity `210/210 passed`。
- Frontend tests/build 通过。
- 没有为通过门禁而放宽已测量阈值。

## 10. WP5：完成 124 条 Native 交互

### 10.1 目标

为 10 个 workflow 和 114 个 parameter contract 生成完整、可重复、当前 fingerprint 绑定的 Native observation。

### 10.2 修改入口

- `scripts/run_luminar_interaction_observations.py`
- `scripts/luminar_capture/accessibility_driver.py`
- `scripts/luminar_capture/semantic_locator.py`
- `scripts/luminar_capture/stability.py`
- `scripts/validate_interaction_execution.py`
- `configs/parity/core-interaction-matrix.json`

### 10.3 Handler 设计

1. 10 个 workflow 保持显式 handler，每个 handler 逐条执行 matrix events。
2. 114 个 parameter contract 不写 114 份重复流程；使用 5 个严格类型执行器和 114 条显式 locator/value binding。
3. Locator binding 必须包含 capability、Native tool、parameter、AX role、label/value 语义和 readback 方法。
4. 类型执行器只处理事件机制，不猜测控件：
   - float：定位 slider/text value，设置 canonical value，读回容差内数值。
   - array：执行 crop/stroke 专用 recipe，校验几何或点序列。
   - asset：打开 picker，按 asset ID/可见名称选择并读回。
   - boolean：toggle 后读回 checked/value。
   - enum：选择固定 option 并读回。
5. 控件无法定位时 contract 记为 blocked，不使用坐标、OCR 猜测或相似 label。

### 10.4 执行顺序

1. 重采 10 个 workflow，确认 R17 handler 在 current environment 下仍成立。
2. 参数按 float → boolean → enum → asset → array 顺序实现。
3. float 以 capability 每批 5 个；其余复杂类型逐条执行。
4. 每条 contract 从 source reset 开始，执行 matrix events，只使用 declared wait conditions。
5. 保存 before/after screenshot、AX snapshot、fixture hash、assertion evidence、environment 和 hashes。
6. 每批运行 native-only validator；批次全部通过后再开始下一批。

### 10.5 验证

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py --dry-run
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --allow-ui-control --resume
.venv/bin/python scripts/validate_interaction_execution.py \
  --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-validation-r18.json
```

### 10.6 完成定义

- Dry-run `124 supported / 0 unsupported`。
- Native validator `124/124 passed`、issue count 0。
- 每条 observation 的 fingerprint、fixture、环境和 artifact hash 完整。
- 无 fixed sleep、坐标 fallback 或 undeclared wait。

## 11. WP6：完成 124 条 Browser 交互

### 11.1 前置条件

- WP4 UI `210/210` 已通过。
- WP5 Native interaction `124/124` 已通过。
- Frontend build hash 已冻结；开始正式 Browser capture 后不再修改代码。

### 11.2 修改入口

- `frontend/scripts/capture-interaction-dpr2.mjs`
- `frontend/src/components/*.tsx`
- `frontend/src/api.ts`
- `api/http/router.py`
- `services/editor/service.py`
- `services/multi_image/service.py`
- `scripts/build_interaction_browser_execution.py`
- `scripts/validate_interaction_execution.py`

### 11.3 执行步骤

1. 按 10 个 workflow 逐条重放 current matrix events。
2. 按与 Native 相同的五类参数批次执行 114 条 contract。
3. visible assertion 由 DOM/AX/截图证明，API assertion 由响应和最终 readback 证明。
4. 每条 contract 保存 final screenshot、DOM、AX tree、execution trace、network trace、console log。
5. 每条 Browser record 绑定对应 Native observation path 和 SHA-256。
6. 禁止固定 sleep；等待必须来自 contract 的 `allowed_wait_conditions`。
7. 任一 console error、未声明网络失败或空 artifact 使该 contract 失败。
8. 每批构建 execution JSON 并运行 validator；最后重新完整执行 124 条，不能拼接不同 build 的批次。

### 11.4 验证

```bash
node frontend/scripts/capture-interaction-dpr2.mjs \
  --contracts configs/parity/core-interaction-matrix.json \
  --fixture test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-manifest.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw \
  --raw-output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw.json
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw.json \
  --evidence-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw
.venv/bin/python scripts/validate_interaction_execution.py
```

具体 fixture 参数以 WP1 完成后的 current-only CLI 为准；若 CLI 与上述命令不同，应同步更新本计划和 `docs/parity/README.md`。

### 11.5 完成定义

- Browser interaction `124/124 passed`。
- 每条 contract 与 current Native observation 一一绑定。
- issue count 为 0，所有 artifact 非空且 hash 匹配。

## 12. WP7：实现单一 v155 Native persistence

### 12.1 目标

用受控差分建立完整 v155 写入契约，实现唯一 Native project repository，并在验证通过后删除 JSON project 运行路径。

### 12.2 WP7A：Controlled delta 证据

输入：隔离的 Luminar 验证 catalog/project 和冻结 fixtures。

执行步骤：

1. 为七类状态分别创建 clean project baseline：project、edit-history、layer、mask、workflow、preset、preview-export。
2. 每次只在 Luminar 修改一个字段或执行一个事件。
3. 修改前后保存：catalog snapshot、History JSON、resources、preview/export、文件树和 SHA-256。
4. 对 40 个工具分别记录：Native tool ID、edit ID、parameter name、type、default、min/max/options、resource link、mask link。
5. 对 undo/redo 记录 state proxy、current 标志、history 顺序和 reload 后状态。
6. 对 layer/mask 记录 alive/enabled、blend、opacity、transformation、mask/effect_masks 的关系。
7. 形成 `configs/parity/luminar-v155-tool-map.json`；只有 Native delta 已证明的字段才能进入映射。
8. 为映射文件编写完整性 validator，要求覆盖当前 40 个 capability 和 parameter schema。

停止条件：任一字段无法由单变量差分确定时，保持 unknown 并阻塞 codec；不得写猜测值。

### 12.3 WP7B：Codec 与 repository

修改入口：

- 新增 `storage/projects/luminar_v155_codec.py`
- 新增 `storage/projects/luminar_repository.py`
- `storage/catalogs/luminar_sqlite.py`
- `services/ports/editing.py`
- `api/app.py`
- `core/project/entities.py`
- `core/project/serialization.py`
- `storage/projects/json_repository.py`
- `scripts/validate_native_persistence_roundtrip.py`
- `tests/test_native_persistence_roundtrip.py`

执行步骤：

1. Codec 只接受 schema v155 和 current tool map。
2. 实现 ProjectState → v155 catalog/History/resources 写入。
3. 实现 v155 catalog/History → ProjectState 读取，用于 API reload 和断言。
4. 所有写入采用临时文件/事务，成功后原子提交；失败时不留下 current proxy 指向半成品 state。
5. 首先在临时 catalog 上完成单元与集成测试。
6. 使用 Luminar 重开验证七类状态、undo/redo、继续编辑和导出。
7. 生成 `native-persistence-roundtrip-manifest.json`，记录 provenance、七类 hashes、restart status 和唯一 active repository。
8. 七类全部通过后修改 `api/app.py`，只组合 `LuminarProjectRepository`。
9. 删除 `JsonProjectRepository` 的活动导入、组合、运行配置和专用测试；若文件无其他用途，删除文件。
10. 删除 JSON project migration、dual-write 或 fallback 的任何草稿代码。

### 12.4 数据安全

- 永远不对 `/Users/iknow/Works/luminarneo/未命名` 原项目做写入试验。
- 每个 roundtrip 使用新建的临时验证目录和源文件副本。
- SQLite 写入前开启 foreign key 检查；完成后运行 integrity check。
- Luminar 进程正在写同一 catalog 时，repository 不得并发写入。

### 12.5 验证

```bash
.venv/bin/python -m pytest \
  tests/test_luminar_catalog.py \
  tests/test_native_persistence_roundtrip.py -q
.venv/bin/python scripts/validate_native_persistence_roundtrip.py \
  --manifest test_data/outputs/luminar-1.28.0-23071/diagnostics/native-persistence-roundtrip-manifest.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/native-persistence-roundtrip-r18.json
```

### 12.6 完成定义

- 七类 roundtrip 全部 passed，serialized/reload hash 一致。
- Luminar 重启后可打开、继续编辑、undo/redo 和导出。
- `api/app.py` 只组合 Native repository。
- 活动代码没有 JSON project、dual-write、compatibility-reader 或 runtime migration。

## 13. WP8：完成效果样本与算法收敛

### 13.1 必须先补齐的 Native 样本

#### Holdout

40 个 capability 每个至少补 2 个新的、内容不同的 Native 输入，使每能力 distinct input 达到门禁要求。每个输入都保存 source hash、参数、素材 ID、Native preview/export 和环境。

正式比较前，按普通像素效果、噪声/颗粒、AI 人像、天空合成、光效、局部笔刷和几何裁切七类各选择一个代表能力，连续执行三次 Native preview/export。只根据 Native 自身重复方差冻结 comparator 和 threshold，不查看 candidate 结果后反向放宽阈值。

#### 9 个 amount anchor 能力

- `clone`
- `color_transfer`
- `complex_bleach`
- `crop_ai`
- `deblur`
- `dodge_burn`
- `erase`
- `lut_mapping`
- `skin_smooth`

每个能力至少覆盖 current schema 所需的低/中/高三个 anchor；无法使用 amount 的交互型工具必须通过当前 matrix 明确参数语义，不能伪造 amount。

#### 6 个未表示 crop 参数

- `crop_box`
- `crop_ratio`
- `crop_rotation`
- `flip_x`
- `flip_y`
- `straighten`

#### 42 个 pending Exact reference

| Capability | 数量 |
|---|---:|
| `sky_replace` | 28 |
| `default_effects` | 3 |
| `new_neon_light` | 3 |
| `ai_enhance` | 2 |
| `denoise` | 2 |
| `sunrays` | 2 |
| `magic_lights` | 1 |
| `slim_people` | 1 |

### 13.2 收敛优先级

1. Main 失败：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。
2. Exact 额外失败：`structure_ai`、`landscape_enhancer`；`face_ai` 有两条失败 case。
3. 42 个 pending-reference 能力。
4. 其他能力只做回归，不主动重写。

### 13.3 修改边界

- 模型 wrapper、加载、输入输出契约问题只修改 `ai/model`。
- 调用编排问题修改 `ai/pipeline`。
- 像素公式、compositing、mask 和 blend 问题修改 `image_ops` 或对应 effect 实现。
- 素材选择问题修改 manifest/asset binding，不用算法补偿错误素材。
- 一个能力一个变更集，不进行全 pipeline 大改。

### 13.4 单能力循环

1. 选一个失败 capability。
2. 对比 Native 与 candidate 的输入、参数、素材、模型调用、intermediate、preview 和 export。
3. 判断根因属于模型、参数映射、色彩空间、mask、blend、几何或导出。
4. 写一个能复现根因的窄测试。
5. 做最小修改。
6. 运行该能力的 main、exact、两个新 holdout 和 preview/export consistency。
7. 运行所有已通过能力的回归。
8. 未通过时保留诊断 artifact，不扩大阈值。

### 13.5 模型专项验证

涉及 `ai/model` 时运行：

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
```

并检查：模型注册、动态实例化、缓存、本地权重加载、输入输出、资源释放和真实 invocation evidence。

### 13.6 完成定义

- 40 个能力 holdout 和参数覆盖均满足 absolute scope。
- Main `40/40 passed`。
- Exact `98/98 passed`，无 pending-reference。
- 没有通过放宽 provisional threshold、复用输入或复制 Native 输出关闭失败。

## 14. WP9：全量验收与 current-only 清理

### 14.1 清理检查

使用文本搜索确认活动代码不存在：

- `contracts.contracts`
- 旧 UI `state` evidence 字段
- 旧 interaction ID
- 16 状态 capture fallback
- `JsonProjectRepository` 活动组合
- `dual-write`
- `compatibility-reader`
- `runtime-migration`
- schema v154 及更早分支

历史文档和归档 artifact 可以保留用于人工审计，但不得被 import、配置、脚本或门禁读取。

### 14.2 全量验证顺序

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
.venv/bin/python scripts/validate_interaction_execution.py --native-only
.venv/bin/python scripts/validate_interaction_execution.py
.venv/bin/python scripts/validate_absolute_scope_coverage.py
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id r18-current-only-final
```

### 14.3 最终证据审计

1. 检查所有 evidence 的 reference ID 和 fingerprint。
2. 检查所有 Native/Browser artifact hash。
3. 检查 frontend build hash 在正式 Browser capture 期间未变化。
4. 检查 Native environment session 未跨锁屏或重新登录复用。
5. 检查 exact run 只读取本次活动 evidence。
6. 检查 absolute scope 的每类 issue 数量都为 0。

### 14.4 完成定义

- Python、Ruff、Frontend tests/build 全部通过。
- 37 个 exact required gates 全部通过。
- Absolute scope issue count 为 0。
- R18 最终报告提供执行前后对比、证据链接和零遗漏结论。

## 15. 文件修改入口

| 目标 | 主要文件 | 验证 |
|---|---|---|
| Current matrix audit | `configs/parity/core-*.json`、`scripts/validate_absolute_scope_coverage.py` | matrix/validator tests |
| UI Browser plan | `scripts/build_ui_browser_capture_plan.py`、`test_data/parity/ui-browser-capture-plan.json` | 210 ID coverage |
| UI Browser capture | `frontend/scripts/capture-ui-dpr2.mjs` | dry-run、DPR2 capture |
| Interaction Browser capture | `frontend/scripts/capture-interaction-dpr2.mjs` | 124 ID dry-run |
| Native UI capture | `scripts/luminar_capture/*.py` | manifest/reference validator |
| Native interaction | `scripts/run_luminar_interaction_observations.py` | native-only validator |
| Browser evidence | `scripts/build_*_browser_execution.py` | execution validators |
| Frontend UI | `frontend/src/components/`、`frontend/src/styles.css` | Vitest、UI parity |
| Native catalog | `storage/catalogs/luminar_sqlite.py` | catalog tests、integrity check |
| Native project | `storage/projects/luminar_v155_codec.py`、`luminar_repository.py` | 7 roundtrips |
| Repository cutover | `api/app.py`、`services/ports/editing.py` | API/integration tests |
| Models | `ai/model/` | model validator、invocation audit |
| Effects | `ai/pipeline/`、`image_ops/` | main/exact/holdout |
| Final gates | `scripts/run_quality_gates.py` | 37/37 |

## 16. 验证矩阵

| 工作包 | 窄验证 | 批次验证 | 最终门禁 |
|---|---|---|---|
| WP0 | matrix unit tests | absolute scope dry audit | absolute-scope-coverage |
| WP1 | plan/recorder unit tests | 210/124 dry-run | ui/interaction execution schema |
| WP2 | preflight probe | 3 repeated preflights | Native environment validation |
| WP3 | single Native state | state-type batch | luminar-reference-captures |
| WP4 | component test + single screenshot | UI-A/B/C parity | ui-execution-evidence、ui-parity |
| WP5 | single Native contract | handler-type batch | native interaction validation |
| WP6 | single Browser contract | workflow/parameter batch | interaction-execution |
| WP7 | codec unit test | seven roundtrips | native-persistence-roundtrip |
| WP8 | single capability | main/exact/holdout | output/exact parity |
| WP9 | full tests | evidence audit | 37 exact gates |

## 17. 风险、停止条件与数据安全

### 17.1 Native 环境风险

| 症状 | 处理 |
|---|---|
| Mac 锁屏 | 停止采集，废弃该 session 后的证据 |
| viewport 漂移 | 停止当前批次，重新 preflight |
| AX locator 不唯一 | 修正语义 locator，不使用坐标 |
| Luminar 崩溃或重启 | 新建 session，重采本批次 |
| UI 动画不稳定 | 增加可观察稳定条件，不使用长固定 sleep |

### 17.2 证据风险

| 症状 | 处理 |
|---|---|
| fingerprint 改变 | 当前矩阵相关 evidence 全部重采 |
| frontend build hash 改变 | Browser UI/interaction 全部重采 |
| fixture hash 改变 | 依赖该 fixture 的 evidence 全部重采 |
| artifact hash 不匹配 | 该 record 无效，不手工修正 hash |
| Native reference 缺失 | Browser 对应状态不得执行或发布 |

### 17.3 Persistence 风险

| 症状 | 处理 |
|---|---|
| 字段语义不确定 | 停止 codec 实现，补 controlled delta |
| Luminar 无法重开 | roundtrip 失败，禁止 repository cutover |
| SQLite integrity/foreign key 失败 | 丢弃临时 catalog，修复 writer |
| 用户项目路径被选中 | 立即停止，不进行写入 |
| JSON/Native 双写需求出现 | 拒绝双写；先完成 Native cutover，再删除 JSON 路径 |

### 17.4 效果收敛风险

| 症状 | 处理 |
|---|---|
| 只有一个参考输入 | 不调参，先补两个 Native holdout |
| 素材 ID 不一致 | 修复素材绑定，不改算法补偿 |
| Native 重复导出波动 | 测量并记录方差，先稳定采集环境 |
| 一个修改影响多个已通过能力 | 回退该修改，缩小变更边界 |
| 只能通过放宽阈值 | 视为未完成，继续定位根因 |

## 18. 最终执行清单

### 18.1 代码与契约

- [ ] UI/interaction matrices 数量与 fingerprint 冻结。
- [ ] 旧 evidence/container/ID negative tests 全部通过。
- [ ] UI Browser plan 为 current 210，活动路径无 16 状态 fallback。
- [ ] UI/interaction Browser recorder dry-run 为 210/124。
- [ ] 活动代码无历史兼容分支。

### 18.2 Native 与 Browser UI

- [ ] Native display/input/session 验证通过。
- [ ] 210 Native UI reference 全部 verified。
- [ ] UI 重复采集方差已测量并冻结 threshold。
- [ ] 210 Browser UI execution 全部通过。
- [ ] UI parity 210/210。

### 18.3 Native 与 Browser interaction

- [ ] 10 workflow Native handler 通过。
- [ ] 114 parameter locator binding 完整。
- [ ] Native interaction 124/124。
- [ ] Browser interaction 124/124。
- [ ] 所有 Browser record 与 Native observation 一一绑定。

### 18.4 Persistence

- [ ] 40 capability v155 tool map 完整。
- [ ] 七类 controlled delta 完成。
- [ ] 七类 roundtrip 通过。
- [ ] Luminar 重启、继续编辑、undo/redo、导出通过。
- [ ] API 只使用 Native repository。
- [ ] JSON project 活动路径已删除。

### 18.5 Effects 与最终门禁

- [ ] 40 个能力各有足量 holdout。
- [ ] 9 个 amount anchor 能力完成。
- [ ] 6 个 crop 参数完成。
- [ ] 42 个 pending Exact reference 完成。
- [ ] Main 40/40。
- [ ] Exact 98/98。
- [ ] Python、Ruff、Frontend tests/build 通过。
- [ ] Absolute scope 0 issues。
- [ ] Exact required gates 37/37。

只有本清单全部勾选后，才能在冻结范围内声明与本地 Luminar Neo `1.28.0 (23071)` 完全对齐。
