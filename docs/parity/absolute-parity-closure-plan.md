# Luminar Neo 1.28.0 效果、UI、交互绝对对齐收敛计划

> 本文保留为上一轮计划归档。最新基线、修正后的 Browser 执行约束、受控校准采样和后续批次见 `docs/parity/absolute-parity-optimization-plan-2026-08-22.md`。

> 本文面向继续实施对齐工作的开发者，基于 2026-08-22 的真实工程状态，给出从当前 `25/45` 效果、`0/7` UI、`0/10` 交互执行门禁收敛到可发布状态的依赖顺序、修改入口、批次方法、验证命令、停止条件和完成定义。唯一产品真值源是本机 Luminar Neo `1.28.0 (23071)`，语言为 `zh-Hans`，平台为 macOS。

## 目录

- [1. 目标、口径与范围](#1-目标口径与范围)
- [2. 当前基线](#2-当前基线)
- [3. 统一数据链和硬约束](#3-统一数据链和硬约束)
- [4. 总体依赖顺序](#4-总体依赖顺序)
- [5. P0：冻结真值和执行环境](#5-p0冻结真值和执行环境)
- [6. P1：补齐 UI、交互和 exact 门禁基础设施](#6-p1补齐-ui交互和-exact-门禁基础设施)
- [7. P2：关闭活动模型专属契约](#7-p2关闭活动模型专属契约)
- [8. P3：关闭剩余效果差异](#8-p3关闭剩余效果差异)
- [9. P4：关闭 7 个 UI 状态](#9-p4关闭-7-个-ui-状态)
- [10. P5：关闭 10 个交互契约](#10-p5关闭-10-个交互契约)
- [11. P6：补齐 exact 控件语义并只运行增量采样](#11-p6补齐-exact-控件语义并只运行增量采样)
- [12. P7：内容、工作流和全链验收](#12-p7内容工作流和全链验收)
- [13. 批次执行模板](#13-批次执行模板)
- [14. 风险、停止条件和回滚](#14-风险停止条件和回滚)
- [15. 最终完成定义](#15-最终完成定义)

---

## 1. 目标、口径与范围

### 1.1 最终目标

在固定本机基线、固定输入、固定参数、固定素材、固定浏览器渲染环境下，使 zpixel 在以下三层与 Luminar Neo 对齐：

1. **效果层**：相同输入和参数产生通过门禁的 preview、export、mask/geometry 和素材合成结果。
2. **UI 层**：7 个固定状态在布局、尺寸、内容、层级、控件状态和截图指标上通过。
3. **交互层**：10 条用户事件链在可见状态、API 状态、编辑栈、导出结果和错误处理上通过。

最终结论是“在冻结的本机可达范围内 parity-passed”，不是宣称复制 Luminar 未安装、不可访问、付费未授权或云端不可用的能力。

### 1.2 “绝对对齐”的工程定义

原生 macOS UI 与浏览器的字体栅格、色彩管理和合成器不同，不能把逐字节相同作为合理目标。本文中的绝对对齐指：**范围完整、语义相同、证据完整、指标预先冻结、所有必需门禁通过**。

| 领域 | 必需证据 | 当前阈值/判定 | 最终要求 |
|---|---|---|---|
| 确定性效果 | 原版与候选 preview/export、参数回读、输入/输出 hash | shape match、SSIM ≥ 0.98、MAE ≤ 0.03 | 所有 in-scope case 通过 |
| 随机/生成效果 | 多次分布证据、频谱/统计指标、结构指标 | P1 冻结，禁止后验放宽 | 分布等价且结构门禁通过 |
| 局部/几何效果 | 全图、ROI、mask/边界、geometry | P1 按 effect family 冻结 | 全图与局部同时通过 |
| UI | reference/candidate screenshot、状态断言 | 当前 provisional：MAE ≤ 0.03、changed pixel ratio ≤ 0.02 | 7/7，且无 pending |
| 交互 | 事件 trace、可见断言、API 断言、最终截图、失败制品 | contract 全断言通过 | 10/10，且无固定 sleep |
| 模型 | 真实调用 trace、模型专属输入输出契约 | active contract gate | 16/16 active-invoked 通过 |

阈值只能在实现修改前，通过原版重复性或历史 attempt 证据冻结。不得为了让候选通过而事后调整。

### 1.3 当前范围

范围由以下当前真源共同确定：

- `configs/reference.yaml`：活动版本、路径和 exact gate 开关。
- `configs/parity.yaml`：输入角色、7 个 UI 状态和门禁阈值。
- `test_data/parity/references/luminar-1.28.0-23071/cases.json`：效果 case。
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json`：251 个已采样项目。
- `configs/parity/interaction-contracts.json`：10 个交互契约。

本机当前可达但需要付费或云端授权的入口只对齐可见 blocked/disabled 状态，不伪造输出。若以后取得合法可执行权限，应新增当前版本的独立 case 和 semantic key，不修改已有 case 含义。

### 1.4 非目标

- 不兼容旧 schema，不双写旧字段，不运行时探测旧目录。
- 不读取历史 parity 报告决定运行时能力。
- 不复制 Luminar 内部模型、私有实现或受限服务；只依据合法本机黑盒输入输出实现等价行为。
- 不为不可达的 74 个库存模型提前实现专属契约。
- 不用 preview 代替最终全分辨率 export。
- 不用单张 smoke 图过拟合随机、素材、多控件或模型能力。

## 2. 当前基线

### 2.1 已通过

| 项目 | 当前结果 |
|---|---:|
| smoke 效果 | 25/45 |
| 历史 smoke canonical | 251/251 ready，0 issue |
| smoke 队列 dry-run | 251 filtered，0 pending |
| exact 可执行项 | 96 |
| exact 已通过 | 1/96 |
| exact 重复/无效语义 | 0/0 |
| 模型真实调用案例 | 22/22 |
| 活动模型专属契约 | 6/16 |
| 交互 contract 定义 | 10/10 |
| Python 测试 | 186 passed |
| 前端测试 | 10 passed |
| Ruff / 前端 build | passed / passed |

### 2.2 尚未通过

| 缺口 | 数量 | 直接阻塞 |
|---|---:|---|
| smoke 效果失败 | 20 case / 17 capability | 效果 exact 发布 |
| exact 待执行 | 95 | exact 效果结论 |
| exact 缺少原生绑定 | 140 | 多参数和素材语义 |
| UI | 0/7 | UI 发布 |
| 交互执行 | 0/10 | 交互发布 |
| active model contract | 10 | AI 效果 exact |

20 个失败 case 涉及：`bokeh_ai`、`face_ai`、`slim_people`、`ai_enhance`、`color_transfer`、`default_effects`、`depth_volume`、`grain`、`lut_mapping`、`pro_contrast`、`structure_ai`、`vignette`、`blue_hour`、`fog`、`landscape_enhancer`、`sky_replace`、`sunrays`。其中 `ai_enhance`、`default_effects`、`sunrays` 各有多个输入 case。

### 2.3 当前基础设施缺口

1. 当前工程没有可执行的候选浏览器截图/交互 runner。
2. `validate_interaction_contracts.py` 只验证 contract 定义，不能证明浏览器已执行。
3. `run_quality_gates.py --level exact` 尚未把 interaction execution 和增量 exact queue 完成度作为独立必需 gate。
4. `configs/parity.yaml` 的 UI 阈值仍明确标注 provisional。
5. 当前 1.28 reference 目录没有 `ui-contract.json`；UI 真值实际位于 `ui_reference_root` 的 PNG/AX 文件和 `configs/parity.yaml`，文档不得再引用不存在的文件。

## 3. 统一数据链和硬约束

### 3.1 单向数据链

```text
本机 Luminar Neo 1.28.0
  │  原生控件写入 + 回读
  ▼
canonical attempt（不可变）
  │  preview / export / UI / AX / metadata / hash
  ▼
版本化 reference case
  │  相同输入 / 参数 / 素材
  ▼
zpixel candidate execution
  │  preview / export / trace / UI / API state
  ▼
统一 comparator
  │
  ▼
scoped gate → full gate → release decision
```

任何环节缺少证据都保持 `pending` 或 `blocked`，不能从“功能存在”“模型被调用”推导“效果已对齐”。

### 3.2 运行时边界

- 运行时只读取当前 schema v2、活动 reference 和当前配置。
- v1/旧版本文件仅作离线审计，不自动回退。
- canonical 与 attempt 分离；失败 attempt 不覆盖 ready canonical。
- 相同 semantic key 的 ready canonical 永远跳过。
- 已有完整 export 先运行离线恢复，不重新采样。
- 所有模型只从本地权重加载，不在推理路径隐式联网。

### 3.3 每个 case 的最小证据

| 证据 | 效果 | UI | 交互 |
|---|---:|---:|---:|
| 固定 fixture/hash | 必需 | 必需 | 必需 |
| 参数/素材/控件回读 | 必需 | 状态相关 | API 相关 |
| Luminar reference | preview + export | PNG + AX | 起止状态 + 事件观察 |
| candidate | preview + export + trace | PNG + DOM/AX | trace + screenshot + API state |
| comparator report | 必需 | 必需 | contract report |
| failure artifact | diff/metrics | diff/DOM/console | screenshot/network/state |

## 4. 总体依赖顺序

```text
P0 冻结真值和环境
  │
  ▼
P1 补齐可执行门禁基础设施
  ├──────────────┐
  ▼              ▼
P2 模型契约      P4 UI 共享骨架
  │              │
  ▼              ▼
P3 效果 smoke    P5 交互执行
  └──────┬───────┘
         ▼
P6 exact 控件 + 增量采样
         │
         ▼
P7 内容/工作流/全链发布
```

P2/P3 与 P4 可以在 P1 完成后并行推进，但同一开发批次只修改一个领域。P6 必须等待效果 smoke、活动模型契约、UI 和交互全部通过，避免在产品行为仍变化时产生昂贵的新 reference。

## 5. P0：冻结真值和执行环境

### P0.1 校正 reference 真源

修改范围：

- `configs/reference.yaml`
- `configs/parity.yaml`
- `docs/parity/README.md`
- `test_data/parity/references/luminar-1.28.0-23071/manifest.json`

执行：

1. 确认活动 reference 是 `luminar-neo-macos-1.28.0-23071`。
2. 删除文档中对不存在的 1.28 `ui-contract.json` 和 `install-manifest.json` 的当前真源声明；不创建无消费者的占位文件。
3. manifest 在最终门禁前保持 `pending-reference`；只有 P7 全通过才改为 `parity-passed`。
4. 冻结 locale、窗口/viewport、输入 hash、素材 hash、色彩空间和 export 格式。

验证：

```bash
.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run
```

退出条件：251/251 canonical ready、0 issue、`record_count=0`。

### P0.2 恢复候选浏览器环境

当前原版 UI 已有 7 个 `2880x1800` PNG/AX reference；缺的是候选浏览器执行环境。

执行：

1. 启动后端、前端和独立 inference worker。
2. 固定 Chromium 版本、viewport `2880x1800`、DPR、locale `zh-Hans`、时区和动画策略。
3. 固定本地字体；不引入远程字体、图片或追踪资源。
4. 确认浏览器可访问候选应用、上传 fixture、读取网络/console、保存截图。
5. 记录运行环境到每次 UI/interaction report。

如果产品环境提供应用内浏览器，优先使用该固定会话。若仍不可用，P1 只增加 Playwright Chromium 这一项浏览器测试依赖，不并存第二套 E2E 框架。

退出条件：候选应用可以稳定打开同一 fixture，并生成一张形状为 `1800×2880` 的候选截图。

### P0.3 冻结阈值而不是调阈值

执行：

1. 优先从已有 preview 稳定帧和历史 attempt 计算 Luminar 自身噪声。
2. 只有随机/AI case 没有足够历史帧时，创建独立 `variance-calibration` semantic key；不重跑 canonical case。
3. UI 分离全屏像素指标与稳定区域指标；动态文件名、进度和时间只允许使用预声明 mask。
4. 为随机 grain 冻结均值、方差、频谱、颗粒尺寸和亮度相关性指标。
5. 为 mask/sky/bokeh 冻结前景、背景、边界带和全图指标。
6. 写回 `configs/parity.yaml`，删除 provisional 注释。

退出条件：每种 comparator 都有数据依据、固定阈值和单元测试；实现修改后不得再改。

## 6. P1：补齐 UI、交互和 exact 门禁基础设施

### P1.1 候选 UI capture runner

计划新增：

- `frontend/playwright.config.ts`
- `frontend/e2e/parity-ui.spec.ts`
- `frontend/e2e/fixtures/`
- `frontend/e2e/helpers/`
- `frontend/package.json` 中 `e2e:parity` 命令

runner 必须：

1. 从 `configs/parity.yaml` 读取 viewport 和 7 个状态，不复制第二份状态清单。
2. 使用稳定 fixture 初始化 catalog、project、layers 和 workflows。
3. 只等待 DOM/API 明确终态，不使用固定 sleep。
4. 输出到 `diagnostics/ui-candidates/2880x1800/<state>.png`。
5. 同时保存 DOM/可访问树、console 和失败网络请求。
6. 禁止更新 reference；测试 runner 只能写 candidate 和 diagnostics。

阶段验证（P1 创建命令后）：

```bash
cd frontend
npm run e2e:parity -- --grep catalog
cd ..
.venv/bin/python scripts/validate_ui_references.py
```

### P1.2 交互 execution runner

计划新增：

- `frontend/e2e/parity-interactions.spec.ts`
- `scripts/validate_interaction_execution.py`
- `diagnostics/interaction-execution.json`

执行规则：

- 从 `configs/parity/interaction-contracts.json` 读取 contract。
- 每个事件必须映射到一个稳定 target；缺 target 直接失败。
- `allowed_wait_conditions` 是唯一允许的等待集合。
- visible assertion、API assertion、最终截图必须全部通过。
- 失败时收集 contract 声明的全部 `failure_artifacts`。
- report 区分 `defined`、`executed`、`passed`，不能把定义通过当执行通过。

### P1.3 exact 总门禁补全

修改 `scripts/run_quality_gates.py`：

1. 增加必需 gate `interaction-execution`。
2. 增加必需 gate `exact-incremental-data-chain`，显式传入 exact queue。
3. 增加必需 gate `exact-incremental-parity`，显式使用 exact cases。
4. 增加 preset/overlay/sky/workflow 的候选输出 parity gate。
5. 保留全模型库存为 optional；活动模型 contract 继续 required。
6. gate report 必须输出 required failure 与 optional failure，禁止 metric masking。

退出条件：

- exact dry-run 显示新增 gate；
- 缺 candidate UI、交互 execution、exact case 时按预期失败；
- 不存在“未执行却 passed”的路径。

## 7. P2：关闭活动模型专属契约

### 7.1 处理范围

只处理当前 10 个 active-invoked pending 模型：

| 分组 | 模型 |
|---|---|
| 分割/显著性 | `MulticlassSegmentationV2`、`human_clothes_exp13_v2_onnx`、`saliency_map_i8_onnx`、`salient_object_improve_exp19_it150k` |
| 人像/增强 | `GFPGANv1.3_2023`、`mobilenet_exp78_portrait_BOKEH12` |
| 图像恢复 | `model_luminocity_denoise`、`srn_deblur_512` |
| 语义/创意 | `SemanticSearchImage`、`magic_lights_exp37_dataset123_1024_onnx` |

### 7.2 单模型固定循环

修改范围限制在 `ai/model`、模型注册/contract 和对应测试；调用编排问题留在 pipeline 批次。

1. 读取本地模型 metadata、wrapper 和真实 execution trace。
2. 固化输入名称、dtype、shape、动态轴、RGB/BGR、数值范围。
3. 固化 resize、padding、归一化、通道顺序和 batch 规则。
4. 让 `predict()` 只负责前向，`postprocess()` 负责语义转换。
5. 固化输出 tensor 名称、坐标系、阈值、resize-back、mask/embedding 范围。
6. 实现完整 `load_model()` / `unload_model()`；失败不能置 `_loaded=True`。
7. 用最小真实 fixture 验证，不用 mock tensor 代替模型语义。
8. 运行对应 candidate case，确认 invocation 和 contract 同时通过。

每个模型验证：

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model

.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --require-active-contracts
```

### 7.3 长任务完整性

独立运行 worker：

```bash
.venv/bin/python scripts/run_inference_worker.py
```

对每个长任务验证：

- 刷新页面后任务仍在运行；
- 已完成模型不重复执行；
- 最后一个模型结束后才发布完整结果；
- 部分失败返回 `completed-with-errors`；
- 取消后旧 worker 不能覆盖终态；
- artifact hash、模型清单和 checkpoint 一致。

P2 退出条件：`active_contract_validated=16`、`active_contract_pending=0`，22/22 invocation case 保持通过。

## 8. P3：关闭剩余效果差异

### 8.1 批次顺序

| 批次 | 能力 | 前置依赖 | 主要 comparator |
|---|---|---|---|
| E1 确定性全局 | `default_effects`、`pro_contrast`、`vignette`、`blue_hour` | P0 阈值冻结 | 全图、直方图、梯度、色彩统计 |
| E2 素材/随机 | `lut_mapping`、`grain`、`color_transfer` | 素材 hash、随机 contract | LUT 语义、频谱、统计分布 |
| E3 深度/分割 | `depth_volume`、`structure_ai`、`ai_enhance` | P2 分割 contract | mask/ROI/边界 + 全图 |
| E4 人像 | `bokeh_ai`、`face_ai`、`slim_people` | P2 人像 contract | 人像 ROI、背景、几何 |
| E5 场景/天空 | `fog`、`landscape_enhancer`、`sky_replace`、`sunrays` | P2 + 素材 contract | sky ROI、前景保护、边界 |

### 8.2 单能力闭环

每次只处理一个 capability：

1. 从 `parity-report-final.json` 记录 baseline 指标和失败区域。
2. 检查 reference 的控件、参数、素材和 source delta 是否可信。
3. 若证据不足，停止实现；先修 reference contract，不按单图均值调参数。
4. 只修改该能力必需的 effect/pipeline/wrapper。
5. 增加语义单元测试：零值、正负值、边界值、尺寸和 no-op 禁止条件。
6. 强制重建选中 candidate。
7. 运行 scoped parity。
8. scoped 通过后运行全 45 case，检查既有 25 个通过项不回退。
9. 记录 batch manifest、before/after、修改文件和回滚点。

命令模板：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --capability <capability_id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --capability <capability_id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/batches/<batch-id>/parity.json

.venv/bin/python scripts/run_parity_suite.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-current.json
```

### 8.3 特殊能力规则

#### LUT

- 校验选中的 `.cube` asset hash、domain、size、插值方式和 amount 混合空间。
- reference source delta 过小时先判定是否选错素材或参数，禁止把 candidate 强度改成近零来通过。

#### Grain

- 固化随机种子只能保证候选可重复，不代表 Luminar 粒子逐像素相同。
- 使用亮度相关性、噪声方差、频谱、颗粒尺度和阴影/高光分布；结构内容仍用 SSIM 保护。

#### Bokeh / Slim People

- 分离人像 mask、背景变换和几何变换。
- 原始人脸/主体 ROI 必须保持身份和纹理；不能用全图均值掩盖局部失败。

#### Sky / Sunrays / Fog

- 分别比较 sky、前景、边界带和反射区域。
- asset id、太阳中心、角度、半径、强度和 blending mode 都必须进入 semantic key。

P3 退出条件：smoke `45/45`，无阈值修改、无静默 no-op、无 reference 文件进入候选运行时。

## 9. P4：关闭 7 个 UI 状态

### 9.1 视觉方向

统一采用“精密工作台 + 沉浸预览”：画布/图片是最高视觉优先级，侧栏紧凑，选中态明确，装饰克制。不是重新设计产品，而是依据本机 Luminar reference 收敛尺寸、层级和状态。

### 9.2 修改入口

| UI 状态 | 主要文件 |
|---|---|
| 共享壳/导航 | `frontend/src/App.tsx`、`WorkspaceRail.tsx`、`EditorHeader.tsx` |
| Catalog | `CatalogWorkspace.tsx` |
| Presets | `PresetBrowser.tsx` |
| Edit/Tool expanded | `PreviewPanel.tsx`、`ToolPanel.tsx` |
| Layer stack/library | `LayersPanel.tsx`、`AssetPicker.tsx` |
| Multi-image | `WorkflowWorkspace.tsx` |
| 令牌、布局、状态 | `frontend/src/styles.css` |

### 9.3 实施顺序

1. **共享令牌**：背景、表面、文字、强调色、语义色、边框、圆角、间距、动效。
2. **应用壳**：顶部栏、工作区 rail、主画布、右侧面板的宽高和滚动所有权。
3. **Catalog / Presets**：资源密度、缩略图比例、选中/悬停/加载/空态。
4. **Edit / Tool expanded**：画布尺寸、工具分组、滑杆、折叠、应用状态。
5. **Layers**：图层行高、缩略图、顺序、opacity、删除和素材库。
6. **Multi-image**：输入帧、分析、preview、导出状态。
7. **通用状态**：loading、error、blocked、before-after、undo-redo、export。

每个 UI 批次：

```text
reference PNG + AX
  → 标注共享/局部差异
  → 修改最小组件和令牌
  → 组件行为测试
  → 单状态候选截图
  → UI comparator
  → 7 状态全回归
```

### 9.4 UI 必查项

- viewport、DPR、字体和 locale 一致；
- 主画布不会被侧栏和说明文案挤压；
- 同一方向只有一个主要滚动容器；
- `min-width: 0` / `min-height: 0` 防止网格溢出；
- hover、focus-visible、selected、disabled、loading、empty、error 完整；
- 图片加载前后尺寸不跳动；
- 长文件名、路径和错误文本可截断或复制；
- 异步旧响应不能覆盖新选择和新 preview；
- 不使用远程字体或一次性装饰资源。

P4 退出条件：7/7 UI passed、0 pending、0 missing artifact；AX/DOM 状态与截图一致。

## 10. P5：关闭 10 个交互契约

### 10.1 依赖顺序

1. `catalog-import-select`
2. `edit-slider-drag`
3. `edit-toggle-collapse`
4. `preset-preview-apply`
5. `layer-add-reorder-opacity-delete`
6. `undo-redo`
7. `before-after-compare`
8. `zoom-pan`
9. `export-dialog`
10. `multi-image-workflow`

这个顺序先建立项目/preview 主链，再实现编辑状态、图层和历史，最后处理导出与多图。

### 10.2 单 contract 闭环

1. 创建 contract 声明的 `initial_fixture`，不依赖上一个测试残留状态。
2. 逐事件执行，target 必须稳定可定位。
3. 只等待 `allowed_wait_conditions`。
4. 每次 mutation 记录 request id、次数和最终项目状态。
5. 执行 visible assertions 和 API assertions。
6. 保存 `final_screenshot_state`。
7. 失败时收齐 contract 声明的 artifacts。
8. 单 contract 通过后运行前面所有 contract，防止状态机回退。

### 10.3 状态一致性硬门禁

- slider 拖动值、API 参数和最终显示值一致；
- preset preview 不写编辑栈，apply 只写一次；
- layer reorder/opacity/delete 与 preview 和持久状态一致；
- undo/redo 恢复相同 edit id 和参数；
- before-after 不发送 edit mutation；
- zoom/pan 不改变项目数据；
- export 只发送一次请求，尺寸和项目一致；
- 多图必须持久化全部帧 hash，preview 完成前禁止 export；
- 页面卸载停止轮询但不自动取消服务器任务；
- 项目切换后迟到响应不能覆盖当前项目。

P5 退出条件：`defined=10`、`executed=10`、`passed=10`、0 missing artifact、0 undeclared wait。

## 11. P6：补齐 exact 控件语义并只运行增量采样

### 11.1 处理 140 个 blocked 锚点

按控件类型分批，不按 capability 混做：

| 批次 | 控件语义 | 必需证据 |
|---|---|---|
| X1 | opacity / amount 多滑杆 | control id、范围、写入、回读 |
| X2 | radius / size / strength | value space、单位、边界 |
| X3 | x/y / center / angle / crop | 坐标系、原点、方向、geometry |
| X4 | sky / overlay / preset / LUT | asset id、hash、选择回读 |
| X5 | toggle / mode / subject-aware | 枚举、默认态、最终态 |
| X6 | 多控件组合 | 设置顺序、最终全部回读 |

每条 contract 必须包含：稳定原生 identifier、原生 min/max、产品 value space、转换函数、写入动作、回读值、失败分类。

### 11.2 重新生成 semantic diff

每完成一种控件 contract：

```bash
.venv/bin/python scripts/build_incremental_sampling_queue.py \
  --matrix test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-sampling-matrix.json \
  --smoke-queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json \
  --capture-root test_data/outputs/luminar-1.28.0-23071/captures \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --diff-output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json

.venv/bin/python scripts/build_exact_parity_cases.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json
```

检查：

- duplicate = 0；
- invalid = 0；
- 已有 ready canonical 仍在 filtered 集合；
- 只有真正获得语义证明的 blocked 项转为 executable。

### 11.3 只采新增项

前置条件：P2、P3、P4、P5 全部通过。

每个 capability 先做 1 个 anchor：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> \
  --allow-ui-control
```

然后 scoped 校验：

```bash
.venv/bin/python scripts/validate_sampling_data_chain.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --case-id <case-id>

.venv/bin/python scripts/generate_candidate_outputs.py \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --case-id <case-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --case-id <case-id>
```

只有单 anchor 数据链和 parity 都通过，才运行该 capability 的其余 anchor。

### 11.4 性能策略

- 保持同一 Luminar 会话进行小批连续运行。
- 每批 3–5 项，批次间校验和发布 canonical。
- 使用唯一 export 文件名和稳定文件监听。
- 原生 export 已存在时先离线恢复。
- 不降低输出分辨率，不用 preview 替代 export。
- 当前 95 项按 90–120 秒原生导出估算约 2.4–3.2 小时；AI 稳定等待另计。

P6 退出条件：所有 executable exact case 通过，队列 dry-run `record_count=0`；unsupported 项有明确原因，不混入通过率。

## 12. P7：内容、工作流和全链验收

### 12.1 素材与内容对齐

251 个 reference 包含 123 preset、38 overlay、35 sky、45 effect、7 UI、3 workflow。已有 reference 不等于 candidate 已对齐。

执行：

1. 将 preset/overlay/sky/workflow 生成可执行 candidate case，不复制 reference 输出到 candidate。
2. 每个素材 case 校验 asset id、hash、blend mode、opacity、position 和参数。
3. preset 校验完整 effect graph、执行顺序和最终输出。
4. overlay/sky 校验前景保护、边界、反射和几何。
5. 3 个 workflow 校验输入帧 hash、分析结果、preview 和 export。
6. 将这些 parity report 接入 exact required gates。

### 12.2 最终质量门禁

先查看计划：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact --dry-run
```

最终执行：

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-final.json
```

然后在新进程、冷缓存、固定 fixture 下重复一次；两次 required gate 都必须通过。

### 12.3 发布动作

只有最终门禁通过后：

1. 将 1.28 manifest 状态改为 `parity-passed`。
2. 生成最终 before/after、case 清单、阈值、环境和失败为零的报告。
3. 记录 unsupported/blocked UI 入口，不把不可达能力声明成已实现。
4. 保留当前 v2 canonical 和 attempts；不添加旧 schema runtime 兼容逻辑。

## 13. 批次执行模板

每个批次创建一个最小 JSON manifest：

```json
{
  "batch_id": "effect-vignette-002",
  "reference_id": "luminar-neo-macos-1.28.0-23071",
  "domain": "effect",
  "scope": ["vignette"],
  "baseline_report": "diagnostics/parity-report-current.json",
  "expected_cases": 1,
  "changed_files": [],
  "verification": [],
  "result": "in-progress",
  "rollback": "revert only files listed in changed_files"
}
```

### 13.1 开始前

- 确认 scope、reference case、参数和素材。
- 记录 baseline 和已通过回归集合。
- 确认不会触发已有 canonical 重采样。
- 列出允许修改的文件。

### 13.2 实现中

- 一次只改一个 capability、一个 UI 共享层或一个 interaction contract。
- 先补失败测试或 contract，再改实现。
- 不清理无关代码，不做跨域重构。
- 若发现 reference 证据不可信，停止候选实现并修数据链。

### 13.3 验证

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
.venv/bin/ruff check .
cd frontend && npm test -- --run && npm run build
```

再运行该领域 scoped gate 和全部已通过 case 的回归。

### 13.4 完成

- manifest 写入 before/after 和最终状态。
- 所有输出路径存在且 hash 可校验。
- 没有阈值修改、reference 复用、missing artifact 或 silent fallback。
- 更新当前报告，不覆盖历史不可变 attempt。

## 14. 风险、停止条件和回滚

### 14.1 必须停止的情况

- reference 参数与原生控件回读不一致；
- source delta 表明效果未真正应用；
- asset id/hash 不一致；
- candidate 读取 reference 输出或历史报告决定运行时能力；
- scoped 通过但既有通过 case 回退；
- UI 依赖未固定字体、viewport 或动态内容；
- interaction 使用未声明 sleep 或跳过 API assertion；
- 模型 wrapper 只有 runtime signature，没有模型专属语义；
- 连续两次出现同类原生控件误绑定或 preview/export 不一致；
- 已存在完整 export 却准备重新采样。

### 14.2 回滚边界

- 效果批次只回滚该 capability 的 effect/pipeline 和对应测试。
- UI 批次按共享令牌、共享壳、单页面拆分，避免一次回滚全部 UI。
- 模型批次只回滚目标 wrapper/contract，不回滚独立 job 系统。
- runner 和 comparator 变更独立批次，不能与产品算法同批提交。
- canonical、attempt、reference 不执行破坏性回滚；错误 canonical 只能失效并保留审计记录。

### 14.3 常见误判

| 现象 | 不能得出的结论 | 正确处理 |
|---|---|---|
| 模型被调用 | 模型效果已对齐 | 检查专属 contract 和输出 parity |
| UI 截图接近 | 交互已对齐 | 执行 10 条 contract |
| smoke 通过 | 参数曲线已对齐 | 运行多 anchor exact |
| reference 已采样 | candidate 已实现 | 生成 candidate 并比较 |
| MAE 低 | 局部 mask/边界正确 | 检查 ROI 和边界指标 |
| preview 一致 | export 完整 | 等待原生全分辨率 export |

## 15. 最终完成定义

所有条件必须同时满足：

- [ ] 活动 reference 固定为 Luminar Neo `1.28.0 (23071)`。
- [ ] 251 个历史 canonical 数据链 0 issue，且不重复采样。
- [ ] smoke effect 45/45。
- [ ] 所有 executable exact case 通过，队列 pending 为 0。
- [ ] 140 个原 blocked 锚点都有 executable 或明确 unsupported 结论。
- [ ] 16/16 active-invoked model contract 通过。
- [ ] 7/7 UI 状态通过固定截图和状态门禁。
- [ ] 10/10 interaction contract 已执行并通过。
- [ ] 123 preset、38 overlay、35 sky 和 3 workflow 有候选端证据与门禁结论。
- [ ] 长任务刷新、重启、取消、部分失败和完整结果发布通过。
- [ ] Python、Ruff、前端测试和 build 通过。
- [ ] exact quality gates 在新进程、冷缓存下连续两次通过。
- [ ] required gate 没有 optional 化、阈值放宽或 missing artifact。
- [ ] 运行时没有旧 schema 回退、双写或历史路径探测。
- [ ] manifest 状态更新为 `parity-passed`，最终报告可追溯到全部机器证据。

只要任一项未满足，对外结论必须保持 `blocked` 或“部分严格对齐”，不能声明绝对复刻完成。
