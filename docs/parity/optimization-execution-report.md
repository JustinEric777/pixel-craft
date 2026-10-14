# Luminar Neo 1.28.0 优化计划执行报告与下一阶段计划

> 执行日期：2026-08-21  
> 对齐基线：本机 Luminar Neo `1.28.0 (23071)`  
> 结论口径：只有通过原版输出、候选输出、UI/交互证据和严格门禁的能力才算对齐；`runtime-ready`、模型被调用或已有采样均不等于效果等价。

## 1. 执行结论

本轮完成了采样数据链、精确语义队列、已有制品复用、长耗时推理任务前端、交互契约定义、模型可达性审计和一个真实效果校准。工程回归全部通过，但产品还没有达到“效果、UI、交互完全对齐”：

- smoke 效果门禁从 `15/45` 提升到 `25/45`，仍有 20 项失败。
- exact 队列从 236 个表面可执行项收敛为 96 个具备当前自动化语义证明的项目；1 项已完成，95 项待执行。
- 另外 140 个 exact 锚点被明确阻塞，原因是缺少原生控件绑定，不会以猜测值采样。
- UI 仍为 `0/7`；当前环境没有可用的应用内浏览器，不能生成可信的候选端 UI 执行证据。
- 10 个交互 contract 已全部结构化并通过定义校验，但尚未在浏览器中执行。
- 22 个活动模型案例全部证明调用了要求的模型；16 个活动模型中只有 6 个完成模型专属契约，剩余 10 个继续阻塞 exact 门禁。
- Python `186` 项测试、前端 `10` 项测试、Ruff 和前端生产构建全部通过。

因此，本轮属于“基础链路和一部分产品差异已关闭”，不是最终完全对齐。未完成项保留为明确的门禁失败或待执行状态，没有通过放宽阈值、复用错误输出或声明性覆盖来隐藏。

## 2. 执行前后对比

| 维度 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| smoke 效果对齐 | 15/45 | 25/45 | 本轮新增 10 项通过；20 项待关闭 |
| exact 原始候选 | 236 | 96 可执行 + 140 阻塞 | 去除了自动化无法证明参数语义的假可执行项 |
| exact 已验证 | 0/96 | 1/96 | `details amount=-1` 通过，95 项待后续分批执行 |
| exact 重复/无效语义 | 未建立严格结论 | 0/0 | semantic key 与参数绑定均进入校验 |
| 历史 smoke 队列 | 251 个历史结果 | `ready_filtered=251`、`record_count=0` | 已采样内容不会重复采样 |
| exact 增量队列 | 无可信恢复结论 | `ready_filtered=1`、`record_count=95` | 已完成 exact 项不会再次入队 |
| UI 对齐 | 0/7 | 0/7 | 候选浏览器执行环境缺失，未伪造结果 |
| 交互 contract | 10 个字符串锚点 | 10/10 结构化定义，0/10 执行 | 定义门禁通过，执行门禁待浏览器 |
| 活动模型调用 | 缺少产品可达分级 | 22/22 案例通过、19 个能力覆盖 | 证明真实调用，不代表输出语义已对齐 |
| 活动模型专属契约 | 未按活动图收敛 | 6/16 validated，10/16 pending | exact 模型门禁保持阻塞 |
| 全模型库存 | 10/90 validated | 10/90 validated | 作为库存报告，不用不可达库存阻塞日常 candidate |
| 长耗时推理前端 | 同步等待 | 持久任务、轮询、取消、重试、断开保护 | 完整结果由 worker 分模型 checkpoint 后统一发布 |
| Python 回归 | 160 项 | 186 项 | 186 passed，1 个第三方弃用警告 |
| 前端回归 | 6 项 | 10 项 | 4 files / 10 tests passed，生产构建通过 |

已有采样复用严格遵守“不重复采样”：smoke 251 项全部被历史 canonical 过滤；`details amount=-1` 在已有完整原生导出后采用离线重验证和行政恢复，没有再次启动 Luminar。调试早期曾在尚无有效 canonical 时对该单一语义重试；一旦完整制品存在，后续只复用不可变 attempt。

## 3. 本轮实际完成内容

### 3.1 精确语义队列与数据链

exact 队列现在只接受能够被当前原生自动化证明的参数：

- `primary_slider`、`subject_aware`、`positioned_effect` 只能绑定明确的 `amount`。
- 队列记录携带 `parameter_binding.parameter/value/value_space`。
- `normalized-signed` 的负值只允许映射到原生有符号控件；原生无符号滑杆拒绝负锚点。
- queue fingerprint 包含参数绑定，避免“案例 ID 一样但实际参数不同”被误判为同一采样。
- 数据链按 queue fingerprint 从运行归档读取对应证据；运行 exact 队列不会再覆盖 smoke 队列的有效性结论。
- data-chain validator 校验控件证据、原生最小/最大值、请求值和实际设置值。
- 140 个需要 opacity、半径、几何、素材或多控件组合的锚点保持 `blocked`，直到建立真实原生控件 contract。

当前 semantic diff：

```text
canonical semantic capabilities: 45
existing semantics:              37
executable added:                96
blocked:                        140
duplicates:                       0
invalid:                          0
```

生成的 exact parity case 与 exact queue 使用同一 semantic key、anchors 和 queue record id；发布阶段发现重复语义会直接失败。

### 3.2 已有完整制品恢复

`scripts/recover_validated_capture.py` 用于恢复“原生导出完整、但被旧阈值误拒绝”的不可变 attempt。它不启动 GUI，也不重新执行采样，必须同时通过：

- 队列参数绑定与 attempt 一致；
- 稳定 preview 帧数量满足要求；
- 原生 preview 相对基线存在超过稳定噪声的变化；
- preview 与 native export 的 RGB/luma 差异满足一致性约束；
- 新 canonical 记录保留原失败 attempt 的引用，审计链不被覆盖。

`exact-details-0054c53f89cf` 的恢复结果为 `1/1 ready`、`0 issue`。恢复证据：preview change MAE `0.002655588`，preview/export RGB MAE `0.012756667`，luma MAE `0.008004701`。

### 3.3 Details 效果校准

原实现把负 Details 同时耦合到全局对比度，候选图明显泛白，真实 exact 指标为 MAE `0.08982`、SSIM `0.91171`。本轮根据 Luminar 负向 Details 的梯度响应，将负值实现收敛为按绝对 amount 的轻量高斯模糊，正值保留适度锐化，移除错误的全局对比度耦合。

新的 exact 指标：

- MAE：`0.0096620`
- SSIM：`0.9980028`
- 参考梯度：`0.0174638`
- 候选梯度：`0.0176256`
- 门禁：passed

阈值没有调整，Details 同时具备 smoke 和 exact 证据。

### 3.4 确定性效果小批校准

在不启动 Luminar、不修改阈值的前提下，本轮继续复用已有 smoke reference，按单能力闭环校准了 8 个确定性效果：

- `color_adjustments`
- `high_key`
- `fade`
- `radiance`
- `color_enhancer`
- `color_toning`
- `complex_bleach`
- `glow_orton`

每项都重新生成 candidate、运行 scoped parity，并在全部通过后复跑 45 项门禁。与 `crop_ai`、`details` 合计，本轮新增 10 项 smoke 通过，最终为 `25/45 passed`、`20/45 failed`。这些 8 项目前是 smoke 级证明，不替代后续多锚点 exact 证明。

`lut_mapping`、随机 grain、模型效果和多控件效果没有用单张 smoke 结果强行拟合；它们分别等待素材/随机性 contract、模型 contract 或原生参数绑定。

### 3.5 原生导出耗时分析

事件时间线表明：输入加载、效果设置和稳定 preview 通常约 14 秒；Python finalize 约 0.23 秒；Luminar 原生全分辨率 export 单次约 75–118 秒，个别超过 2 分钟。长等待发生在原生渲染和文件落盘，而不是候选文件重命名、替换或 canonical 发布。

本轮已经保证每个 attempt 使用唯一文件名，避免覆盖等待和错误复用。后续性能策略应保持：

- 同一 Luminar 会话内做小批连续采样，减少启动和导入固定成本；
- 事件驱动监听唯一导出路径，并在文件尺寸/mtime 稳定后发布；
- preview 只用于交互稳定性与一致性证明，不能代替最终全分辨率结果；
- 已有完整 export 优先离线校验恢复，绝不为修复状态记录而重采样；
- 不以降低分辨率换取“完全对齐”的虚假速度收益。

按 95 个待执行 exact 项、单项约 90–120 秒估算，纯原生导出约需 2.4–3.2 小时，尚未计入 AI 稳定等待和异常重试。必须按能力小批执行，而不是一次性无人值守跑完整队列。

### 3.6 长耗时模型推理

前端已经从同步 `/analyze` 切换到持久化 analysis job：

1. 用 idempotency key 创建任务；
2. 每 1.5 秒读取任务状态；
3. worker 每完成一个模型持久化 checkpoint 与 artifact；
4. 到达 `succeeded` 或 `completed-with-errors` 后读取完整结果并刷新项目；
5. 支持显式取消和失败后重试；
6. 页面卸载只停止本地轮询，不取消服务器任务；
7. 项目切换时用 generation token 丢弃旧项目的迟到响应。

worker 必须作为独立进程运行：

```bash
.venv/bin/python scripts/run_inference_worker.py
```

单次排障可使用：

```bash
.venv/bin/python scripts/run_inference_worker.py --once
```

请求线程和 WebSocket 不承担长模型推理，避免浏览器断开导致结果丢失。任务终态只在所有模型到达终态后发布合并结果；单模型失败明确形成 `completed-with-errors`，不会返回看似完整的部分结果。

### 3.7 UI 与交互

10 个交互锚点已变成机器可校验 contract：catalog 导入选择、preset preview/apply、slider drag、折叠切换、图层增删改排、undo/redo、before/after、zoom/pan、export dialog、多图工作流。每个 contract 都包含：

- 初始 fixture；
- 用户事件序列；
- 可见状态断言；
- API 断言；
- 最终截图状态；
- 允许等待条件；
- 失败制品。

定义门禁为 `10/10 passed`、`0 issue`；执行门禁是 `pending-browser-execution`。本轮检查到应用内浏览器列表为空，因此没有用非目标浏览器或静态截图冒充真实交互执行。

### 3.8 模型门禁

模型静态验证为 0 blocking finding。活动候选审计覆盖 22 个模型支持案例、19 个能力和 16 个实际调用模型，22/22 均证明要求模型进入真实执行路径。

当前模型角色分布：

| 角色 | 数量 |
|---|---:|
| active-invoked | 16 |
| active-alternate | 11 |
| configured-not-covered | 33 |
| inventory-unmapped | 30 |

16 个 active-invoked 模型中，6 个模型专属契约已验证，10 个仍 pending。pending 名单由 `diagnostics/candidate-model-invocations.json` 生成，不在文档复制静态真源。`--require-active-contracts` 会在这些活动契约未关闭时阻塞 exact；全 90 模型库存只作为非阻塞报告，避免不可达模型掩盖产品实际路径，也避免用全局低完成率掩盖活动缺口。

## 4. 验证结果与证据入口

本轮最终回归：

```text
Python:   186 passed, 1 third-party deprecation warning
Ruff:     All checks passed
Frontend: 4 test files, 10 tests passed
Build:    TypeScript + Vite production build passed
```

关键机器证据：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/batches/exact-details-smoke-001/data-chain.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/batches/exact-details-smoke-001/parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-contracts.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations.json`

## 5. 遗漏审计

### 5.1 已完成且无已知遗漏

- 历史 smoke canonical 迁移、制品校验和 251 项跳过。
- queue fingerprint、semantic key、attempt/canonical 分离和恢复审计链。
- exact 参数绑定校验与不支持语义阻塞。
- scoped data-chain 校验和 exact case 发布。
- `crop_ai` 非确认态行为修正。
- `details amount=-1` 真实 exact 校准。
- 8 个确定性效果完成 scoped smoke 校准，且 45 项全量回归无既有通过项回退。
- 前端持久 analysis job、取消、重试、迟到响应保护。
- 交互 contract 定义校验。
- 活动模型调用图和活动契约门禁。
- Python、前端、静态检查和构建回归。

### 5.2 明确未完成，不能计入完全对齐

- 20 个 smoke 效果仍未通过。
- 95 个可执行 exact 项尚未采集；它们不会在前置门禁失败时提前跑。
- 140 个 exact 锚点没有原生多控件/素材语义绑定。
- 7 个 UI 状态没有候选端像素证据。
- 10 个交互 contract 没有浏览器执行证据。
- 10 个 active-invoked 模型没有模型专属输入、预处理、输出和后处理契约。
- preset、overlay、sky 目前只有完整参考采样证据，不代表候选端效果已经逐项严格对齐。
- 最终 exact quality gate 尚未通过，因此不能发布“完全复刻”结论。

### 5.3 历史兼容边界

运行时只读取当前 schema v2 和当前活动 reference。v1 文件仅作为离线审计归档，不自动回退、不参与能力判定、不引入兼容分支。后续修改继续直接演进当前契约和迁移数据，不增加双写、旧字段兜底或历史路径探测。

## 6. 下一阶段可执行计划

执行顺序必须保持 `UI/交互执行环境 → 活动模型契约 → smoke 效果 → exact 控件 contract → 增量采样 → 最终验收`。前一阶段未通过时，后一阶段不得用批量采样或阈值调整绕过。

### P0：恢复候选 UI 执行环境

目标：让 7 个 UI 状态和 10 个交互 contract 能在同一候选前端、同一固定 viewport、同一 fixture 上执行。

执行：

1. 启动后端、前端和独立 inference worker。
2. 确认应用内浏览器会话可发现，而不只是系统浏览器可打开。
3. 固定 viewport、DPR、字体、主题、locale 和动画策略。
4. 逐项执行 10 个 contract；只等待 contract 声明的可见状态或 API 终态，禁止固定 sleep。
5. 每个失败保留 before/after、DOM/可访问树、网络状态和控制台错误。
6. 先修共享工作区骨架，再修局部状态，最后重跑 7 个 UI 截图门禁。

验收：UI `7/7`、interaction `10/10`，且浏览器执行报告中无 missing artifact、stale response 或未声明等待。

### P1：关闭 10 个活动模型专属契约

目标：只处理产品真实可达的 10 个 pending 模型，不为 74 个非活动库存模型过度实现。

每个模型依次完成：

1. 从 wrapper 和真实模型 metadata 固化输入名称、dtype、shape、动态轴和色彩空间。
2. 固化 resize、padding、归一化、通道顺序和 batch 规则。
3. 固化输出 tensor 语义、坐标系、阈值、resize-back 和合成规则。
4. 用最小真实 fixture 验证，不用 mock tensor 代替语义测试。
5. 记录资源释放、缓存复用和失败分类。
6. 运行活动 candidate case，确认模型 invocation 与输出 contract 同时通过。

验收：`active_contract_validated=16`、`active_contract_pending=0`，`--require-active-contracts` 通过。全库存 90 项仍作为独立报告，不阻塞此阶段。

### P2：按能力关闭剩余 20 个 smoke 效果

目标：先证明默认产品路径正确，再扩展 exact 锚点。

优先顺序：

1. 确定性颜色/纹理：便于从直方图、梯度和局部差异定位。
2. 深度、天空和场景：依赖已验证的 mask/depth contract。
3. 人像和生成式局部效果：依赖模型输出与合成 contract。

每个能力使用同一闭环：单案例 candidate → 指标/差分图 → 定位算法或参数问题 → 最小实现 → 单元测试 → scoped parity → 全 45 项 smoke 回归。任何修改导致已通过项目回退时停止该批并回滚局部实现。

验收：smoke `45/45`，无阈值放宽，无 candidate 使用参考制品，无能力静默 no-op。

### P3：补齐 140 个 blocked exact 原生 contract

目标：在采样前证明 Luminar 实际设置了目标语义。

按控件类型逐类实现：

- opacity/amount 多滑杆映射；
- radius、size、strength 等非 amount 参数；
- x/y、中心、角度和裁剪等几何参数；
- sky、overlay、preset 等素材标识和选择证据；
- toggle、mode、subject-aware 等离散状态；
- 多控件组合的设置顺序和最终值读取。

每类 contract 必须包含稳定 control id、原生范围、value space、写入动作、回读证据和失败分类。实现一类后重新生成 semantic diff；只有从 blocked 变为 executable 的记录可以进入队列。

验收：blocked 项都有明确的 executable 或 unsupported 结论；unsupported 保留原因，不伪造成通过。

### P4：只运行新增 exact 队列

前置门禁：UI、interaction、活动模型契约和 smoke 必须全部通过；历史队列 dry-run 必须继续是 `record_count=0`。

执行方式：

1. 以单一能力为批次，先运行 1 个锚点。
2. data-chain 和 parity 同时通过后，再运行该能力其余锚点。
3. canonical ready 始终自动跳过；失败 attempt 保留，不覆盖历史证据。
4. 若完整原生导出已经存在，先尝试离线恢复，禁止直接重采样。
5. 每批记录导出时长、稳定等待、失败类型和新增磁盘占用。
6. 连续两次发生相同控件误绑定或输出不一致时停止该能力，修 contract 后再继续。

验收：所有 executable exact 项具备原版 preview/export/UI、候选 preview/export、参数回读证据和通过指标；队列再次 dry-run 为 0。

### P5：最终验收与发布

最终发布必须同时满足：

- smoke 效果 45/45；
- exact 所有 executable 项通过，blocked/unsupported 有审计结论；
- UI 7/7；
- interaction 10/10；
- active model contracts 16/16；
- sampling/data-chain 0 issue；
- Python、前端、静态检查和构建全部通过；
- 新进程、冷缓存、固定 fixture 下复跑结果一致；
- 没有读取历史报告决定运行时能力，没有旧 schema 兼容分支。

只有满足以上条件，才可以把版本结论从 `blocked` 改为 `parity-passed`。在此之前，对外表述应保持“部分能力已严格对齐，整体仍在收敛”。

## 7. 下一次执行起点

下一次不要启动 95 项 exact 批量采样。正确起点是：

1. 恢复应用内浏览器并执行 10 个交互 contract；
2. 同时保持 inference worker 独立运行，验证刷新/断开后的完整结果读取；
3. 关闭 10 个 active model contract；
4. 从剩余 deterministic smoke 效果中选择一个能力做完整小批闭环；
5. smoke 45/45 后再进入 exact 原生控件扩展和增量采样。

这条路径复用现有 251 个历史采样和已完成的 exact 结果，避免在产品逻辑、UI 和模型契约尚未稳定时产生昂贵且可能失效的新参考数据。
