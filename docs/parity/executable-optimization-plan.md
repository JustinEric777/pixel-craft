# Luminar Neo 1.28.0 可执行优化计划

> 本文面向后续实际实施，基于 2026-08-21 已验证的采样数据链和 exact 门禁，规定优化顺序、修改边界、批次产物、验证命令、回滚点与完成标准。活动参考固定为本机 Luminar Neo 1.28.0 build 23071；已有 251 条 canonical 证据不得重复采样。

## 目录

- [1. 目标和硬约束](#1-目标和硬约束)
- [2. 当前基线与关键发现](#2-当前基线与关键发现)
- [3. 总体执行顺序](#3-总体执行顺序)
- [4. A 阶段：先优化迭代闭环](#4-a-阶段先优化迭代闭环)
- [5. B 阶段：关闭 30 个效果差异](#5-b-阶段关闭-30-个效果差异)
- [6. C 阶段：关闭 7 个 UI 差异](#6-c-阶段关闭-7-个-ui-差异)
- [7. D 阶段：关闭 10 个交互锚点](#7-d-阶段关闭-10-个交互锚点)
- [8. E 阶段：收敛模型契约和长任务 UI](#8-e-阶段收敛模型契约和长任务-ui)
- [9. F 阶段：只执行增量 exact 采样](#9-f-阶段只执行增量-exact-采样)
- [10. G 阶段：最终验收和发布](#10-g-阶段最终验收和发布)
- [11. 批次执行模板](#11-批次执行模板)
- [12. 风险、停止条件与回滚](#12-风险停止条件与回滚)
- [13. 完成定义](#13-完成定义)

## 1. 目标和硬约束

### 1.1 可验证目标

| 编号 | 目标 | 当前值 | 完成值 |
|---|---|---:|---:|
| O1 | sampling data chain | 251/251，0 issue | 持续 251/251；新增项也为 0 issue |
| O2 | smoke 效果输出 | 15/45 passed | 45/45 passed |
| O3 | 固定视口 UI | 0/7 passed | 7/7 passed |
| O4 | 交互行为 | 10 个锚点仅有清单 | 10/10 行为和终态证据通过 |
| O5 | 模型专用契约 | 10/90 validated | 产品可达图内模型全部 validated |
| O6 | exact 增量矩阵 | 366 条原始记录 | 0 重复语义，只采集 canonical semantic diff |
| O7 | 工程回归 | Python 160、前端 6、构建通过 | 所有回归持续通过 |

### 1.2 硬约束

- 每次启动 Luminar 前必须先执行 queue dry-run；已有 canonical case 必须被过滤。
- 不修改 `configs/parity.yaml` 的阈值来掩盖差异。阈值只有在获得独立重复性证据后才能单独评审。
- 不让 runtime 读取 v1 archive、历史报告或旧版本输出来决定功能状态。
- 不重写整个渲染器、模型层或前端；一个批次只解决一个能力、一个共享算子或一个 UI 层级。
- 不把注册成功、模型文件存在、功能可运行当成 Luminar exact 等价。
- 不增加 Redis、消息队列、数据库或 WebSocket。长任务继续使用现有 JSON job、lease 和 HTTP 轮询。
- 不并行控制 Luminar 前台窗口。candidate 生成可以按批次串行执行，避免模型资源和输出路径竞争。
- 不删除 canonical、native export、metadata、attempt、UI/AX 或全局日志。

### 1.3 非目标

- 不为 Luminar 旧版本增加运行时兼容分支。
- 不覆盖付费、生成式或当前 product scope 外的能力。
- 不在没有参考证据时推测 Luminar 私有算法的内部实现。
- 不为了让 90 个注册项“看起来完成”而给未映射模型虚构业务消费者。

## 2. 当前基线与关键发现

### 2.1 已经可依赖的基础

- 当前 queue 共 251 条，`ready_filtered=251`、`record_count=0`。
- schema v2 使用 canonical + attempt；失败 retry 不覆盖成功证据。
- 原生导出和归一化 PNG 已分离，数据链验证为 0 issue。
- 推理 job 支持 checkpoint、取消、lease 接管、完整 `.npy/.npz` 制品及哈希。
- Python 160 项、前端 6 项、前端构建和 Ruff 已通过。

### 2.2 计划开始前必须修正的矩阵问题

当前 `exact-sampling-matrix.json` 有 366 条效果记录。按以下字段计算语义：

```text
reference_id
+ capability_id
+ input.sha256
+ asset_id / asset_sha256
+ canonical parameters JSON
```

当前只有 273 个不同语义，存在 40 个重复组、93 条额外重复记录。主要原因是：

- `defaults` 与参数自己的 default anchor 重复；
- 多个参数的 default 值生成相同完整参数集；
- builder 没有把 source case 的 `asset_id` 独立带入 exact record；
- fingerprint 当前基于原始记录顺序，而不是去重后的稳定语义集合。

因此 366 不是待采样数量；在 A 阶段修复、去重并与当前 canonical 做差之前，禁止据此启动采样。

### 2.3 当前产品差异

效果方面有 30 个失败 case，其中 `crop_ai` 是唯一明确的 shape mismatch。其余主要分为：

- 确定性颜色/纹理：`color_adjustments`、`color_enhancer`、`color_toning`、`color_transfer`、`complex_bleach`、`details`、`fade`、`grain`、`lut_mapping`、`pro_contrast`、`radiance`、`vignette`、`high_key`、`glow_orton`、`default_effects`。
- 场景/深度：`blue_hour`、`depth_volume`、`fog`、`landscape_enhancer`、`sky_replace`、`sunrays`。
- AI/人像：`ai_enhance`、`structure_ai`、`bokeh_ai`、`face_ai`、`slim_people`。

UI 七个状态的 shape 都一致，但 MAE 为 0.0979–0.1568，changed pixel ratio 为 95.35%–96.31%，属于工作区骨架、表面和排版的系统差异，不是局部颜色误差。

## 3. 总体执行顺序

```text
A：优化矩阵和局部验证闭环
  │
  ├── B：效果 smoke 45/45
  │     └── 为 E 提供真实模型/后处理优先级
  │
  ├── C：UI 骨架和 7 个固定状态
  │     └── D：10 个交互状态机
  │
  └── E：产品可达模型契约 + 长任务 UI
        │
        ▼
F：exact semantic diff，只采新增记录
        │
        ▼
G：全量 exact 门禁和发布结论
```

执行规则：

1. A 必须最先完成。
2. B 与 C 在文件边界明确时可以交替推进，但同一个批次不能同时改效果算法和 UI。
3. D 依赖 C 的组件结构稳定。
4. E 优先处理 B 实际调用的模型，不盲目从 90 个注册项顺序扫描。
5. F 只能在 smoke 效果、UI 和交互闭环可稳定复现后执行。
6. 任一阶段出现数据链 issue，立即停止产品校准并先恢复数据链。

## 4. A 阶段：先优化迭代闭环

### A1：修正 exact matrix builder

修改范围：

- `scripts/build_exact_sampling_matrix.py`
- `tests/test_validation_scripts.py` 或新增一个同级 matrix 测试文件

执行内容：

1. exact record 显式携带 `asset_id` 和可用的 `asset_sha256`。
2. 以稳定 canonical JSON 计算 `semantic_key`，不包含扫描顺序和本机绝对路径。
3. 先生成 anchors，再按 semantic key 去重；同语义保留一个 record，并记录合并的 anchor 来源。
4. fingerprint 基于排序后的唯一语义记录和 interaction records。
5. 增加 fail-closed 校验：重复 semantic key、缺输入哈希、素材型能力缺素材标识时构建失败。

验收：

- 输出 `duplicate_semantic_count=0`。
- 同一输入反复构建 fingerprint 完全一致。
- `sky_replace` 等素材型能力的 record 可解析到真实素材。
- 原始 366 条应下降，但最终数量以修复后的报告为准，不在代码中硬编码 273。

### A2：生成 canonical semantic diff

新增一个单用途脚本，例如：

```text
scripts/build_incremental_sampling_queue.py
```

输入：

- 修正后的 exact matrix；
- 当前 `sampling-queue.json`；
- 当前 state/canonical；
- 活动 reference profile。

输出：

- `exact-semantic-diff.json`：`existing`、`added`、`invalid`、`duplicate`；
- `sampling-queue-exact-incremental.json`：只包含 added；
- 独立 fingerprint。

禁止行为：

- 不把 record ID 不同但语义相同的项算作新增；
- 不因旧 attempt 最后失败而忽略 canonical ready；
- 不直接修改当前 smoke queue；exact incremental 使用独立 profile。

验收：

- 当前 251 条 canonical 不出现在 added 集合；
- `duplicate=0`、`invalid=0`；
- dry-run 的 `record_count` 等于 diff 的 added 数量；
- 未执行 Luminar 时不会创建或修改 capture 文件。

### A3：增加窄范围 candidate/parity 入口

当前 candidate 生成已经支持 `--capability`，parity suite 只支持全量或 scope 文件。做以下最小扩展：

- `scripts/run_parity_suite.py` 增加可重复的 `--capability` 和 `--case-id`；
- `scripts/generate_candidate_outputs.py` 增加 `--case-id`；
- 输出报告仍使用同一比较实现和阈值，不复制第二套比较器；
- 为筛选和“不覆盖未选择 case”补单元测试。

A 阶段完成后，单能力循环统一为：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --capability <capability_id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --capability <capability_id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/batches/<batch-id>/parity.json
```

### A4：建立最小批次记录

每个优化批次只需要一个 JSON manifest，不建立新数据库：

```json
{
  "batch_id": "effect-crop-ai-001",
  "reference_id": "luminar-neo-macos-1.28.0-23071",
  "scope": ["crop_ai"],
  "baseline_report": ".../parity-report.json",
  "changed_paths": [],
  "commands": [],
  "before": {},
  "after": {},
  "status": "draft"
}
```

目录固定为：

```text
diagnostics/batches/<batch-id>/
├── manifest.json
├── candidate-report.json
├── parity.json
└── notes.md
```

只有产生真实诊断价值的图像才保存；不复制 canonical reference。

A 阶段退出条件：

- matrix 0 重复、0 invalid；
- incremental diff 可重建且 fingerprint 稳定；
- 单能力和单 case 可独立生成、比较；
- current smoke dry-run 仍为 251 filtered、0 records；
- 数据链仍为 0 issue。

## 5. B 阶段：关闭 30 个效果差异

### 5.1 每个效果批次的固定循环

1. 从当前 `parity-report.json` 冻结 before metrics。
2. 检查 execution trace，确认实际执行了预期模型/算子和参数。
3. 若 shape、颜色空间或 alpha 不一致，先修结构，不调视觉系数。
4. 为该能力增加至少一个直接单元测试；共享算子修改要增加受影响能力的回归测试。
5. 只重新生成该 capability 的 zpixel candidate；不启动 Luminar。
6. 运行该能力 parity。
7. 运行全部 45 个 smoke parity，确认已通过的 15 个没有回退。
8. 保存 before/after metrics 和 changed paths。

任一批次的提交边界：一个 capability，或一个被多个 capability 明确共享的基础算子。不得按“所有颜色效果”“所有 AI 效果”做一次大改。

### B1：先修 `crop_ai` 结构错误

修改入口：

- `ai/pipeline/image_effect_pipelines.py` 的 `crop_ai` 分支；
- 对应 saliency wrapper 和 `ResizeTransform`，仅在证据显示契约有误时修改；
- renderer/export 的尺寸语义测试。

需要先回答：

- Luminar reference 是裁剪后画布，还是原画布内的 crop metadata？
- preview 与 export 的输出尺寸是否相同？
- amount 是否控制裁剪强度、边界留白还是置信阈值？

验收顺序：shape match → crop bounds/主体位置 → MAE/SSIM。shape 未通过前不调整颜色或锐度。

### B2：确定性颜色与纹理能力

建议批次顺序：

1. `color_adjustments`：当前 MAE 0.0308，最接近门禁，用于校正基础颜色空间和 amount 映射。
2. `lut_mapping`、`fade`、`radiance`：验证 LUT、混合和 tone curve 公共路径。
3. `details`、`grain`、`vignette`、`pro_contrast`：验证局部频率、噪声种子和空间权重。
4. `color_enhancer`、`color_toning`、`color_transfer`、`complex_bleach`、`high_key`、`glow_orton`。
5. `default_effects`：最后处理，避免它掩盖底层共享效果差异。

实现原则：

- 所有计算使用明确的 RGB/线性或非线性色彩约定；不在多个效果里重复隐式转换。
- 需要确定性噪声的效果固定 seed，并把 seed 纳入 case parameters。
- amount 映射来自参考锚点，不用单点拟合高阶曲线。
- 一个共享算子只有被至少两个实际能力使用时才抽取。

批次验收：目标能力所有 smoke case passed；全量 passed 数只能增加或保持，不能下降。

### B3：场景、天空和深度能力

建议顺序：

1. `depth_volume`、`fog`：先验证 depth 方向、范围、归一化和 resize restore。
2. `blue_hour`、`landscape_enhancer`：分离全局色调与区域 mask 误差。
3. `sky_replace`：分别检查 mask、地平线、边缘、前景遮挡、纹理几何和 relight。
4. `sunrays`：最后处理位置、遮挡、半径和强度，因为它依赖天空 mask。

`sky_replace` 不用整图单指标调参。批次报告至少记录：

- sky mask 区域；
- horizon band；
- foreground protection；
- non-sky unchanged 区域；
- 全图指标。

### B4：AI 与人像能力

建议顺序：

1. `structure_ai`、`ai_enhance`：确认 segmentation 输出是否真的参与像素计算，不能只调用模型后使用固定 Pillow 增强。
2. `bokeh_ai`：验证前景/背景 mask 方向、边缘过渡和 blur kernel。
3. `face_ai`：按人脸 ROI 比较，不让背景像素稀释误差。
4. `slim_people`：同时检查几何位移场、边界连续性和非人体区域保护。

模型 wrapper 只负责稳定推理契约；Luminar 风格映射和图像合成留在 pipeline/image ops，不把业务效果塞入 `ai/model`。

B 阶段退出条件：

- 45/45 smoke effect passed；
- 45 个 case 均有 execution trace；
- 已通过能力没有回退；
- 未修改阈值；
- 没有新的 Luminar 采样。

## 6. C 阶段：关闭 7 个 UI 差异

视觉方向固定为“精密工作台 + 沉浸预览”：图片画布是最高优先级，导航和工具面板紧凑退后。不要引入另一套品牌风格。

### C1：先建立可重复 candidate 截图入口

当前 UI candidate 已存在，但仓库没有统一生成脚本。增加一个最小截图入口，固定：

- viewport `2880x1800`；
- device scale factor、字体、locale 和动画关闭策略；
- 每个 state 的准备动作和 ready selector；
- 输出到 `diagnostics/ui-candidates/2880x1800/<state>.png`；
- 页面状态准备失败时 fail closed，不保存半加载截图。

优先复用现有前端工具链；只有现有能力无法稳定截图时才引入 Playwright，并只作为 dev dependency。不要建立远程视觉测试服务。

### C2：工作区骨架

修改入口优先为：

- `frontend/src/styles.css`：主题、表面、布局、尺寸和状态令牌；
- `frontend/src/App.tsx`：只调整应用壳组合和状态，不堆积局部样式；
- `EditorHeader`、`WorkspaceRail`、`PreviewPanel`、`ToolPanel`、`LayersPanel`。

按以下顺序处理：

1. 应用壳高度、顶栏、左 rail、中心画布、右 panel 的几何。
2. 明确滚动所有权；同一方向只保留一个主滚动容器。
3. 固定画布 contain 规则、背景、边界和 loading/error 占位尺寸。
4. 对齐表面层级、边框、文字层级、间距和控件密度。
5. 最后处理图标、滑杆、hover、focus、selected 和 disabled。

每完成一层都重新生成 7 张 candidate 并比较；不要先在七个页面分别微调颜色。

### C3：七个状态按共享程度关闭

建议顺序：

1. `edit`：工作区基础骨架。
2. `tool-expanded`：编辑态右侧工具结构。
3. `layer-stack`、`layer-library`：共享右侧面板和素材网格。
4. `catalog`、`presets`：资源画廊布局。
5. `multi-image`：独立 workflow 工作区。

行为测试至少覆盖：

- 空态、加载态、错误态；
- 当前 mode/tool/layer 的选中态；
- busy 时按钮禁用；
- 长文件名和空素材列表；
- 旧异步响应不能覆盖当前选择；
- 主要面板滚动不带动整个页面。

C 阶段退出条件：

- 7/7 UI parity passed；
- 前端测试和 build 通过；
- 七个 state 可以由同一脚本从空数据重建；
- 没有通过页面级绝对定位硬贴截图而破坏真实交互。

## 7. D 阶段：关闭 10 个交互锚点

### D1：把字符串清单变成结构化 contract

每个 interaction record 至少包含：

- `id`；
- 初始 fixture；
- 用户事件序列；
- 每一步可见断言；
- 项目/API 状态断言；
- 最终 screenshot state；
- 允许的异步等待条件；
- 失败时保留的日志和截图。

不使用固定 sleep 作为 ready 条件；等待真实 DOM 状态、请求终态或图片加载完成。

### D2：按依赖顺序实现

1. `catalog-import-select`
2. `preset-preview-apply`
3. `edit-slider-drag`
4. `edit-toggle-collapse`
5. `layer-add-reorder-opacity-delete`
6. `undo-redo`
7. `before-after-compare`
8. `zoom-pan`
9. `export-dialog`
10. `multi-image-workflow`

每条 contract 需要双重断言：用户看到的 UI 状态正确，并且项目/导出终态正确。截图相似但项目 edit stack 错误，或行为正确但视觉终态错误，都不能通过。

### D3：处理异步一致性

针对 preview、preset preview、analysis 和 workflow：

- 新请求开始后清理旧 error/result；
- 以 request/job ID 识别当前请求；
- 页面切换和组件卸载时停止轮询；
- 晚返回的旧结果不能覆盖新选择；
- loading、disabled、cancel 和 retry 状态必须来自同一任务状态。

D 阶段退出条件：10/10 interaction contracts passed，且 7 个 UI 固定状态没有回退。

## 8. E 阶段：收敛模型契约和长任务 UI

### E1：按产品可达图重新分级

不要直接逐个处理 80 个 pending。以现有 source map 和真实 invocation audit 分为：

1. `active-invoked`：优先，当前候选实际运行过。
2. `active-alternate`：验证同 task 输出契约和切换条件。
3. `configured-not-covered`：只有产品 scope 内存在真实消费者时补 coverage。
4. `inventory-unmapped`：必须二选一——映射到明确能力，或从活动产品注册中移除；不创建虚假消费者。

exact model gate 应只统计活动产品图中的 required models，同时单独报告未映射库存，避免“库存存在”与“产品需要”混为一谈。

### E2：每个模型的完成内容

模型 wrapper 修改范围严格限制在 `ai/model`：

- 本地离线加载；
- input color/layout/resize/normalization；
- output name、shape、dtype 和语义；
- task 内稳定 postprocess 字段；
- unload 和 loader 淘汰释放。

pipeline 负责：

- 模型选择；
- 多模型组合；
- mask/geometry 恢复；
- Luminar 风格效果；
- artifact 和 project 合并。

每个模型验收：

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model

.venv/bin/python scripts/check_model_contracts.py
.venv/bin/python scripts/audit_candidate_model_invocations.py
```

同时为实际 tensor shape、数值范围、序列化输出和 unload 增加模型级测试。

### E3：前端切换到持久化 analysis job

当前前端仍调用同步 `/analyze`。最小改造为：

1. `frontend/src/api.ts` 增加 enqueue、get result、cancel 方法和 job 类型。
2. `App.tsx` 创建 job 后每 1–2 秒轮询一次；成功、部分失败、失败和取消都停止。
3. 页面切换或卸载时清理 timer；不自动取消服务端 job，除非用户点击取消。
4. 展示总状态、已完成模型、失败模型和可重试动作。
5. 完成后重新读取 project，保证 UI 展示的是已落盘结果。

不增加 WebSocket。只有 HTTP 轮询被实际测量为不可接受时才重新评估。

测试覆盖：

- enqueue 返回 202；
- 同 idempotency key 返回同一 job；
- 轮询成功停止；
- cancelled/failed 停止并显示原因；
- 组件卸载停止轮询；
- stale response 不覆盖新的 job。

E 阶段退出条件：

- 产品可达图内 required models 全部 model-specific validated；
- inventory-unmapped 为 0，或明确移出活动产品注册并保留独立库存；
- 长任务 UI 可以查询、取消、恢复展示完整结果；
- 完整 `.npy/.npz` artifact hash 验证通过。

## 9. F 阶段：只执行增量 exact 采样

### F1：采样前门禁

每个 batch 启动 Luminar 前必须全部满足：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run
.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/validate_sampling_queue_captures.py
```

并人工确认：

- 输入 queue 是 `exact-incremental`，不是 current smoke queue；
- `record_count == exact-semantic-diff.added`；
- added 列表不包含任何当前 canonical semantic key；
- 每条素材型记录有 asset ID 和 hash；
- 一个 batch 只覆盖一个 capability 或一条 interaction。

### F2：小批执行

建议批次大小：

- 效果参数：一个 capability 的新增 anchors；
- UI：一个 state；
- 交互：一个 interaction contract；
- 模型长任务：一个 project + 一组明确 models。

每批完成后立即：

1. 校验 state/canonical/attempt；
2. 校验 native export 和 metadata hash；
3. 生成 immutable run report；
4. 运行 data-chain validator；
5. 生成 zpixel candidate；
6. 运行本批 parity；
7. 发布 batch manifest；
8. 才进入下一批。

失败 attempt 不覆盖 canonical；重试只针对 added 且无 canonical 的 record。

### F3：9 个 normalized fallback 的处理

默认不重采样。这 9 个 case 继续明确标记为历史 normalized fallback。

只有当某个 fallback 成为 exact 发布的唯一阻塞，并且无法通过现有 preview/export 证据验收时，才单独提交补采决策；补采应使用新的 attempt，不伪造旧 native export。未经该决策，不进入采样队列。

F 阶段退出条件：exact incremental queue 为 0 pending、0 failed、0 invalid、0 stale。

## 10. G 阶段：最终验收和发布

### G1：完整验证

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/run_quality_gates.py --level functional
.venv/bin/python scripts/run_quality_gates.py --level exact
```

### G2：一致性复核

- 所有报告使用活动 reference ID 和最新 fingerprint。
- queue、canonical、candidate、parity report 的 case 集合一致。
- 没有 candidate 路径指向旧版本输出。
- runtime 不读取 diagnostics 决定功能是否可用。
- exact gate 失败时发布状态保持 blocked。
- 所有 batch 的 before/after、修改路径和验证命令可追溯。

### G3：发布结论

只有第 13 节全部满足时，才能声明“在已定义的本地免费 product scope、固定系统环境和固定输入下，与 Luminar Neo 1.28.0 的效果、UI 和交互达到 exact gate 对齐”。

不要把该结论扩展为未知输入、未知硬件、付费能力或其他 Luminar 版本的普遍等价。

## 11. 批次执行模板

每个批次按以下顺序执行：

### 11.1 开始前

- [ ] 记录 batch ID、scope、reference ID、queue fingerprint。
- [ ] 保存目标 case 的 before metrics。
- [ ] 执行 current queue dry-run，确认已有 canonical 不会运行。
- [ ] 明确最多修改哪些文件。
- [ ] 明确至少一个失败复现和一个回归保护。

### 11.2 实现中

- [ ] 先写或更新失败测试。
- [ ] 做满足当前证据的最小修改。
- [ ] 不顺手重构相邻模块。
- [ ] 不修改 parity 阈值。
- [ ] 生成本 scope candidate，不采 Luminar。

### 11.3 验证

- [ ] 窄范围单元测试通过。
- [ ] 目标 capability/state/interaction gate 通过。
- [ ] 共享回归集通过。
- [ ] 全量 smoke gate 没有新增失败。
- [ ] 数据链为 0 issue。
- [ ] batch manifest 写入 before/after。

### 11.4 发布或回滚

- 所有检查通过：状态改为 `verified`，再合并到活动结果。
- 目标改善但共享回归退化：保持 `blocked`，恢复该批算法修改，保留诊断报告。
- 数据链出现 issue：立即停止，先恢复 queue/canonical/hash 一致性。

## 12. 风险、停止条件与回滚

| 风险 | 识别信号 | 停止条件 | 回滚方式 |
|---|---|---|---|
| 重复采样 | dry-run 出现已有 canonical | added 集合含 canonical semantic key | 丢弃增量 queue，重建 semantic diff |
| 单点过拟合 | 一个 case 改善、同能力其他 case 退化 | 全能力或 smoke 回归下降 | 回滚本批参数，增加第二输入诊断 |
| 阈值遮蔽 | 代码未改善但 gate 变绿 | `configs/parity.yaml` 被修改 | 回滚阈值，恢复原始门禁 |
| UI 截图不可复现 | 同代码截图尺寸/字体漂移 | candidate capture 环境不稳定 | 固定环境后重新生成 candidate，不动 reference |
| 模型语义错位 | shape 正确但 mask/类别方向错误 | contract 只有 runtime signature | 回滚 wrapper，补真实 task postprocess 测试 |
| stale worker | 取消任务又变 running/completed | lease owner 不一致 | 保留 job 文件，停止 worker，检查锁和 lease |
| 存储膨胀 | batches 重复复制 reference | batch 目录包含 canonical 副本 | 删除可重建 candidate 临时件，保留 manifest/report |
| 范围膨胀 | 为未映射库存新增无产品需求代码 | 没有 capability consumer | 不实现；移出活动注册或留在独立库存 |

回滚粒度始终为一个 batch。state v1 archive 仅供人工审计，运行时不提供自动历史回退。

## 13. 完成定义

全部条件必须同时满足：

- [ ] current 251 条 canonical 完整，已有项没有重复采样。
- [ ] exact matrix 为 0 duplicate、0 invalid，素材型 record 有完整 provenance。
- [ ] smoke 效果 45/45 passed。
- [ ] exact 增量效果 anchors 全部 passed。
- [ ] UI 7/7 passed。
- [ ] interaction 10/10 passed。
- [ ] 123 个预置、35 个天空、38 个叠加和 3 个 workflow 的要求门禁通过。
- [ ] 产品可达模型全部 model-specific validated，完整 artifact 可恢复、可校验。
- [ ] Python、前端测试、前端 build、Ruff 全部通过。
- [ ] sampling data chain 为 0 issue。
- [ ] exact required gates 为 0 pending、0 invalid、0 failed、0 stale。
- [ ] 发布报告明确 product scope、reference build、环境和已知边界。

任何一项未满足，最终状态都应保持 `blocked`，并从对应 batch 继续，而不是扩大采样或放宽门禁。
