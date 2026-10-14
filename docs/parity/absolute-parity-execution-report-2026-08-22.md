# Luminar Neo 1.28.0 绝对对齐优化计划执行报告

> 执行日期：2026-08-22  
> 真值版本：本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`  
> 结论口径：缺少原生效果、UI 或交互证据时保持 blocked；通过单元测试、模型可运行或视觉接近均不能替代 parity。

## 1. 执行结论

本轮已完成证据门禁、Magic Lights 活跃模型契约、采样去重与失败恢复、7 个 smoke 失败案例的效果闭环，以及全量工程回归。整体从 `29/45` 提升到 `36/45`，活动模型专属契约从 `15/16` 提升到 `16/16`。

产品整体仍不能声明与 Luminar Neo 完全对齐，原因是：

- 效果仍有 9 个 smoke 案例失败；
- UI 为 `0/7`，当前没有可用的应用内 Browser 会话；
- 交互执行为 `0/10`，缺少 Luminar 原生 observation 和候选浏览器执行；
- exact 仅 `1/96` 具备完整证据，95 项保持待执行；
- exact 质量门禁为 26 项，当前 18 项通过、7 个 required 阻断、1 个 optional 阻断；
- preset、overlay、sky、workflow 的完整候选严格验收仍未完成。

因此当前可发布表述只能是：**数据链和部分能力已严格收敛，整体绝对对齐继续被效果、UI、交互和 exact 证据阻断。**

## 2. 执行前后对比

| 指标 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| smoke 效果 | 29/45 | 36/45 | 新增 7 个案例通过，仍有 9 个失败 |
| 活动模型调用 | 22/22 | 22/22 | 保持通过 |
| 活动模型专属契约 | 15/16 | 16/16 | Magic Lights 模型契约关闭 |
| 全模型专属契约 | 19/90 | 20/90 | 70 个非活动库存模型仍是 pending |
| UI | 0/7 | 0/7 | 无真实 Browser，会话缺失时 fail-closed |
| 交互定义 | 10/10 | 10/10 | 定义完整 |
| 交互执行 | 0/10 | 0/10 | 原生 observation 和浏览器执行均缺失 |
| smoke 队列 | 251 ready，0 pending | `ready_filtered=251`、`record_count=0` | 已采样项未重复采样 |
| exact 队列 | 1 ready + 95 pending | 不变 | 前置门禁未通过，未提前批量采样 |
| exact gate 数量 | 25 | 26 | 新增当前前端 build/fixture/screenshot 新鲜度门禁 |
| Python 回归 | 203 passed | 224 passed | 全通过 |
| 前端回归 | 10 passed | 10 passed | 全通过 |
| 生产构建 | passed | passed | TypeScript/Vite 通过 |

## 3. 分阶段结果

| 阶段 | 结果 | 状态 |
|---|---|---|
| P0 基线冻结 | 固定 1.28.0/23071、smoke 29/45、active 15/16、UI 0/7、interaction 0/10 | 完成 |
| P1 UI/交互证据门禁 | UI 证据绑定当前 build hash、fixture hash、viewport、截图路径/尺寸/hash；交互强制绑定 Luminar 原生 observation | 完成 |
| P2 Magic Lights | 真实 ONNX 正/负 fixture 验证 3 个输出尺度、anchors、confidence、NMS、有限框；active 16/16 | 完成 |
| P3 采样去重与性能 | 新语义键才入队；ready canonical 与 failed attempt 都跳过；完整无变化导出不再重复原生执行 | 完成 |
| P4 效果批次 | Pro Contrast、Vignette、AI Enhance、Structure AI、Landscape Enhancer、Color Transfer 通过校准和严格留出 | 完成当前安全批次 |
| P5 UI | Browser runtime 返回无可用浏览器 | 阻塞 |
| P6 交互 | 10 个 contract 均缺原生 observation 和候选执行 | 阻塞 |
| P7 exact | 1 ready、95 pending；未越过前置门禁 | 未启动增量采样 |
| P8 内容 | 未建立全量候选严格证据 | 待执行 |
| P9 回归/报告 | Python、前端、Ruff、模型模块、构建、exact gate 均已执行 | 完成 |

## 4. 关键实现与证据

### 4.1 UI 与交互 fail-closed

新增 UI 执行证据 validator，要求每个 UI 状态同时具备当前前端源码/build hash、reference id、browser family/version、viewport、locale、timezone、fixture id/hash，以及 candidate screenshot 的精确路径、尺寸和 SHA-256。7 个状态必须完整覆盖。

交互 validator 现在为每条 contract 强制读取 Luminar 原生 observation，并验证应用版本、fixture hash、事件、断言、允许等待、前后截图和 AX snapshot hash；候选执行必须绑定同一 observation。缺少任一项时不能通过。

当前 Browser runtime 没有可用浏览器，会话列表为空。因此没有使用系统浏览器、独立 Playwright 或静态截图作为替代证据。

### 4.2 Magic Lights 模型契约

`yolo_light_boxes` 现在明确拥有 confidence、NMS IoU 和最大检测数，并严格校验 batch=1、3 anchors、支持的方形尺度、每 anchor 6 个值。找不到兼容输出时直接失败，不再静默返回空框。

真实 probe 位于 `test_data/outputs/luminar-1.28.0-23071/diagnostics/magic-lights-contract-probe.json`：正 fixture 得到 9 个检测，负 fixture 得到 0 个检测。该结果关闭的是模型输入输出契约；Luminar 最终灯光渲染仍属于效果 parity。

### 4.3 历史队列与重复输出

历史 1.25 队列与当前 1.28 smoke 的精确 semantic key 公共项为 0，因为 semantic key 正确包含 reference version/build；逻辑库存公共项为 246。结论是：

- 旧版本逻辑库存可用于发现能力，不可作为 1.28 当前真值；
- 当前 251 个 smoke canonical 已全部命中恢复过滤；
- 已有 ready canonical 不重新采样；
- 已产生 deterministic failed attempt 的同一 semantic key 也不重新采样；
- 新输入、参数或资产必须产生新 semantic key 和新 capture id。

重复输出的主要来源不是简单文件重复，而是旧队列跨版本、不同参数/资产组合，以及失败恢复时的 attempt/staging 证据。canonical、attempt、staging、candidate 和 report 是不同责任层，不应按文件名相似直接删除。

### 4.4 原生导出耗时与长模型任务

原生“重命名/替换”等待的主要耗时实际发生在 Luminar 全分辨率重渲染、预览稳定检测和 native export 文件稳定检测，不是 Python `rename` 本身。

本轮增加 `NonRetryableCaptureError`：当一次完整 native export 已证明与源图无有效差异时立即结束，不再为同一确定性无变化结果执行第二次完整导出。预览 AXImage 瞬时缺失等可恢复问题仍允许有限重试。

模型长任务继续以持久化 job/checkpoint/终态发布为边界。客户端轮询断开或页面切换不取消服务器任务，只有完整终态结果才能发布，避免长推理被同步请求超时截断。

## 5. 效果闭环详情

### 5.1 本轮新增通过

- `pro_contrast`：原生 control 是 Highlights contrast，不是通用全局 contrast；3 张校准来源生成紧凑单调响应，另 1 张严格留出通过。
- `vignette`：原生正 Amount 在当前操作下提亮外缘；修正中心保护半径、羽化与强度；严格留出通过。
- `ai_enhance` 两个 smoke：3 张来源校准内容自适应曲线，第 4 张严格留出通过。
- `structure_ai`：两张来源校准固定单调响应，第 3 张严格留出通过；分割模型 forward 仍是前置条件。
- `landscape_enhancer`：两张来源校准，第 3 张严格留出通过；专用 sky 模型仍 fail-closed。
- `color_transfer`：从均值/方差匹配改为逐通道经验 CDF/分位数映射，并保留 SemanticSearchImage 语义权重；校准和严格留出通过。

上述新增 canonical 的 data-chain 校验均为 passed。当前共有 15 个新的 ready calibration canonical：Pro Contrast 3、Vignette 2、AI Enhance 2、Structure AI 2、Landscape 2、Blue Hour 2、Color Transfer 2。

### 5.2 明确拒绝合并

- `blue_hour`：新增校准与留出上的全局曲线表现良好，但原 general 样本仍为 MAE 约 0.0345，高于 0.03，证明存在空间/内容相关响应。实现保持未修改。
- `lut_mapping`：新语义键中 Anaheim 和 Amount=100 可被定位，但 Luminar 最终 export 与源图无有效差异，未发布 canonical；旧 reference 同样缺少可信 apply/readback。不能把候选改成 no-op 刷过旧 reference。
- `magic_lights` 正效果采样：模型正 fixture 有检测，但 Luminar Amount=100 的新原生导出无变化；模型契约已关闭，最终渲染 parity 仍阻塞。

### 5.3 当前 9 个失败案例

- `face_ai`
- `slim_people`
- `depth_volume`
- `lut_mapping`
- `blue_hour`
- `fog`
- `sky_replace`
- `sunrays` 两个案例

这些能力需要 ROI、mask、depth、geometry、asset placement 或空间响应证据；不再用少量全局色调曲线继续拟合。

## 6. 最终工程验证

```text
Python:                 224 passed, 1 third-party deprecation warning
Frontend:               4 files / 10 tests passed
Ruff（项目源码范围）:    All checks passed
Model module validator: 0 blocking findings
Frontend build:         TypeScript + Vite production build passed
Smoke parity:           36 passed / 9 failed / 0 pending
Candidate invocation:   22/22 passed
Active contracts:       16/16 passed
UI:                     0/7
Interaction execution:  0/10
Exact queue:            1 ready + 95 pending
Exact quality gates:    26 total / 18 passed / 7 required failed / 1 optional failed
```

exact required blockers：

- `model-source-map`：全库存 90 个模型中仅 20 个模型专属 contract 完成；
- `exact-incremental-data-chain`：95 个 exact case 尚无 state；
- `output-parity`：9 个 smoke 失败；
- `exact-incremental-parity`：1 passed、95 pending；
- `ui-execution-evidence`：0/7；
- `ui-parity`：0/7；
- `interaction-execution`：0/10。

optional blocker 是 `model-contract-inventory`，当前 20/90 model-specific validated。

核心机器证据：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/historical-queue-alignment.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/magic-lights-contract-probe.json`

## 7. 遗漏审计

### 已完成且未发现遗漏

- 版本、输入、参数、资产和 semantic key 的真值边界固定；
- ready canonical 与 failed semantic attempt 均不会重复采样；
- Magic Lights 活跃模型输入输出契约有真实正/负 forward 证据；
- UI candidate 新鲜度和交互双边 observation 进入 required exact gate；
- 所有新增通过效果均有独立留出，不使用留出反向调参；
- 所有新增 ready calibration 均通过 data-chain；
- Blue Hour、LUT 和 Magic Lights 的无效/不足证据没有被伪造为通过；
- smoke、模型、Python、前端、Ruff、构建和 exact gate 均已重跑；
- 未加入 v1 fallback、双写、旧目录探测或运行时历史报告依赖。

### 仍存在的真实遗漏

- 9 个 smoke 案例未通过；
- UI 7 个状态无当前 build 的真实 Browser 执行证据；
- 10 个交互 contract 无 Luminar observation 和候选执行；
- 95 个 exact case 未采样；
- 70 个非活动库存模型未完成模型专属 contract；
- preset、overlay、sky、workflow 的全候选内容验收未完成；
- manifest 不得标为 `parity-passed`。

## 8. 下一步建议

### N1：恢复应用内 Browser，先关闭 UI/交互共同阻塞

恢复可发现的应用内 Browser 会话，固定 viewport、DPR、字体、locale、timezone、主题、动画和 fixture。先执行 10 条交互双边 observation，再按共享 workspace 骨架关闭 7 个 UI 状态。验收必须为 UI `7/7`、interaction `10/10`，不能用系统浏览器或人工截图替代。

### N2：按共享模型/几何契约关闭剩余效果

1. `face_ai` + `slim_people`：固定 face/body mask、坐标系、padding、feather 与几何位移 comparator；至少多脸、无人脸、边缘人像和不同体型留出。
2. `depth_volume` + `fog`：先冻结 depth orientation、归一化、near/far 语义和恢复尺寸，再校准空间 alpha；共享同一 depth contract。
3. `sky_replace` + `sunrays`：冻结 sky mask、horizon、太阳中心、ray geometry、asset placement 与 foreground/reflection；使用 ROI/mask/geometry comparator，不只看全图 MAE。
4. `blue_hour`：增加空间响应和语义区域证据，不能继续用全局曲线。
5. `lut_mapping`：先修原生 menu choice 的可验证 readback/commit；当前 failed semantic key 不重试，只有控制策略或输入/资产语义发生真实变化时才生成新 key。

### N3：校正 exact 模型门禁的产品范围

当前 active contract 已是 `16/16`，但 required `model-source-map` 同时要求 90 个本地库存模型全部模型专属验证。下一步应先确定哪些模型能被冻结的免费产品能力实际触达：可触达模型进入 required；纯库存、重复 backend 或未被产品调用的模型保留 optional inventory。该调整是校正产品范围，不是降低数值阈值。若 90 个模型都被声明为可达范围，则必须逐个完成真实输入输出 contract，不能绕过。

### N4：前置门禁通过后才执行 exact 增量采样

只有 smoke 45/45、UI 7/7、interaction 10/10 和 required active model scope 通过后，才按 capability 小批运行 95 个 exact case。继续使用 `--resume`；每批先 1 个 anchor，data-chain/parity 通过后再放行其余项。已 ready 的 1 项永远跳过。

### N5：最后关闭内容与发布

为 preset、overlay、sky、workflow 建立完整候选 evidence、asset hash、execution trace 和能力专属 comparator。所有 26 个 required exact gate 连续两次通过后，才允许修改 manifest 并声明在冻结的本机可达范围内完全对齐。
