# Luminar Neo 1.28.0 效果、UI、交互绝对对齐优化计划（2026-08-24）

> 本文基于 2026-08-23 的最终机器报告，给出下一轮可直接执行的收敛计划。目标是在冻结的本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans` 和固定输入环境内，使 zpixel_edit 的效果、UI、交互和完整数据链达到可审计的等价；已有可信采样不重复，历史版本不进入当前产品运行逻辑。

## 目录

- [1. 执行结论](#1-执行结论)
- [2. 绝对对齐的可验证定义](#2-绝对对齐的可验证定义)
- [3. 当前冻结基线与遗漏](#3-当前冻结基线与遗漏)
- [4. 数据链和采样纪律](#4-数据链和采样纪律)
- [5. 总体依赖与批次顺序](#5-总体依赖与批次顺序)
- [6. P0：冻结证据、阈值和执行账本](#6-p0冻结证据阈值和执行账本)
- [7. P1：恢复 UI Browser 证据通道](#7-p1恢复-ui-browser-证据通道)
- [8. P2：补齐原生交互 observation](#8-p2补齐原生交互-observation)
- [9. P3：关闭模型运行时和输出合同](#9-p3关闭模型运行时和输出合同)
- [10. P4：关闭 9 个效果失败案例](#10-p4关闭-9-个效果失败案例)
- [11. P5：关闭 7 个 UI 状态](#11-p5关闭-7-个-ui-状态)
- [12. P6：关闭 10 个交互契约](#12-p6关闭-10-个交互契约)
- [13. P7：关闭 Overlay 与多图 Workflow](#13-p7关闭-overlay-与多图-workflow)
- [14. P8：增量关闭 95 个 exact 待办](#14-p8增量关闭-95-个-exact-待办)
- [15. P9：采样耗时、推理长任务和资源治理](#15-p9采样耗时推理长任务和资源治理)
- [16. P10：全量回归、双跑和发布](#16-p10全量回归双跑和发布)
- [17. 修改入口与测试矩阵](#17-修改入口与测试矩阵)
- [18. 风险、停止条件与回滚](#18-风险停止条件与回滚)
- [19. 执行前后目标对比](#19-执行前后目标对比)
- [20. 最终完成检查表](#20-最终完成检查表)

---

## 1. 执行结论

下一轮不能直接运行剩余 95 条 exact 原生采样。正确顺序是：

```text
冻结证据与阈值
  │
  ├── UI Browser 可执行证据 ──> 7 个 UI 状态
  │
  ├── 原生 interaction observation ──> 10 个候选交互执行
  │
  └── 模型运行时与合同 ──> 人像/深度/天空共享语义
                              │
                              ▼
                       9 个 smoke 效果关闭
                              │
             Overlay + 3 个多图 workflow 关闭
                              │
                              ▼
                   95 个 exact 分批增量关闭
                              │
                              ▼
                  全量回归 + exact 连续双跑
```

执行重点不是继续微调单图系数，而是先关闭共享合同：人脸/人体 ROI、深度方向、天空/前景遮挡、太阳位置、模型输出语义、UI 当前构建证据和交互状态机。共享根因通过后再跑 exact，才能减少 Luminar 原生导出次数并避免对单个 reference 过拟合。

## 2. 绝对对齐的可验证定义

### 2.1 范围

“绝对对齐”仅指以下冻结边界：

| 维度 | 冻结值 |
|---|---|
| 原版应用 | Luminar Neo `1.28.0 (23071)` |
| Bundle ID | `com.skylum.luminarneo` |
| 平台 | 当前本机 macOS |
| 语言 | `zh-Hans` |
| 输入 | 当前 parity fixture、multi-image fixture 和合法免费素材 |
| UI 视口 | `2880×1800`，其余系统缩放、DPR、字体、主题写入证据 |
| 产品范围 | 当前 40 个可见免费能力、123 个预置、38 个叠加素材、46 个 Sky E2E、3 个多图 workflow、7 个 UI 状态、10 个交互契约 |

未知输入、未来 Luminar 版本、付费或生成式能力不属于本轮声明范围。不能把黑盒算法的未知内部实现宣称为数学意义上的源码一致；发布声明必须写成“冻结范围内、证据覆盖下等价”。

### 2.2 效果完成定义

每个效果必须同时满足：

1. 参数、素材、输入 hash、输出尺寸和色彩空间一致。
2. 目标区域、背景保护、遮挡顺序和无目标 no-op 语义一致。
3. smoke `45/45` 通过。
4. exact `96/96` 通过；当前为 `1 passed + 95 pending`。
5. 单样本 AI 域必须至少有独立 holdout，不能只用同一图片校准和验收。
6. 视觉门限以 Luminar 历史重复输出可证明的原生噪声上界为优先；无法证明时继续使用当前 `MAE <= 0.03`、`SSIM >= 0.98`、尺寸一致，不得放宽。

### 2.3 UI 完成定义

7 个状态必须同时具备：

- 经独立 manifest 验证的原生 reference；
- current-build 候选截图和 `ui-browser-execution.json`；
- `build_hash`、fixture hash、浏览器版本、viewport、locale、timezone、DPR、字体和动效稳定条件；
- 几何、文字、图标、层级、滚动、焦点、选中、禁用、加载、空态和错误态一致；
- 当前冻结门限 `MAE <= 0.03`、`changed_pixel_ratio <= 0.02` 全部通过；若原生 UI 噪声上界更严格则收紧。

### 2.4 交互完成定义

10 个 contract 必须全部具备：

- Luminar 原生 before/after 截图、AX snapshot、事件序列和可见断言；
- zpixel current-build Browser 执行记录、API 断言和最终截图；
- 相同 fixture、相同事件顺序、相同最终可见状态；
- 只使用声明过的可见/API 等待条件，`fixed_sleep=false`；
- 长任务在断开、切页、重载后能恢复并取得完整终态结果。

### 2.5 最终发布门禁

只有连续两次执行以下命令，执行时注册的所有 required gate 均通过，且两次失败集合为空，才允许更新 manifest。当前基线为 26 个 gate；P7 接入 Overlay required gate 后预计为 27 个，最终以报告中的 `gate_count` 为准：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-1.json

.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-2.json
```

## 3. 当前冻结基线与遗漏

| 项目 | 当前值 | 目标值 | 当前结论 |
|---|---:|---:|---|
| Python 测试 | 231/231 | 全过 | 稳定 |
| 前端测试 | 11/11 | 全过 | 稳定 |
| Ruff / 前端 build / 模型静态验证 | passed | passed | 稳定 |
| smoke 效果 | 36/45 | 45/45 | 9 个失败 |
| UI current-build | 0/7 | 7/7 | Browser 无可发现实例，旧 candidate 失效 |
| interaction 定义 | 10/10 | 10/10 | 已完成 |
| 原生 interaction observation | 0/10 | 10/10 | 缺失 |
| 候选 interaction execution | 0/10 | 10/10 | 缺失 |
| exact | 1/96 | 96/96 | 剩余 95，尚未放行 |
| model source/artifact/wrapper | 95/95、90/90、90/90 | 全 exact | 文件链通过 |
| 活动模型调用/合同 | 22/22、16/16 | 全过 | 已通过部分保持 |
| 待补 ONNX 合同 | 4 | 0 | 未关闭 |
| macOS 不可达 logical model | 4 | 0 | 未关闭 |
| Preset / Sky E2E | 123/123、46/46 | 保持全过 | 稳定 |
| Overlay 最终 parity 报告 | 无 | 38/38 | 缺独立报告 |
| Workflow | 0/3 | 3/3 | HDR、Focus、Panorama 均失败 |
| exact 质量门禁 | 17/26 passed | required 全过 | 8 required + 1 optional 失败 |

剩余 9 个效果案例：`face_ai`、`slim_people`、`depth_volume`、`lut_mapping`、`blue_hour`、`fog`、`sky_replace`、两个 `sunrays`。

当前 required gate 阻塞：`model-source-map`、`multi-image`、`exact-incremental-data-chain`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`。

## 4. 数据链和采样纪律

### 4.1 唯一事实链

```text
冻结输入/素材
  -> semantic key
  -> queue record
  -> attempt state/log
  -> Luminar canonical reference
  -> candidate output/current-build screenshot
  -> comparator report
  -> quality gate
  -> manifest（仅最终发布）
```

任何 `runtime-ready`、模型文件存在、效果产生变化或本地 workflow 可运行，都不能替代 parity passed。

### 4.2 已采样不重复规则

1. canonical state 为 `ready`：不再次启动相同 semantic key 的 Luminar 采样。
2. terminal state 为 deterministic `failed`：相同 semantic key 不自动重试。
3. exact 队列每批开始前必须重建，自动排除 smoke 或 exact 中已 ready 的语义。
4. 新采样只允许用于真正新增的语义覆盖，例如多人、无目标、触边、深度方向、不同太阳位置；新语义必须生成新 semantic key。
5. UI reference 优先从现有 screenshot、AX、state 和 attempt 日志恢复 manifest。只有某一状态无法证明 app build/fixture 时才标记 `invalid-evidence`；不得把它当 ready，也不得无差别重采全部 7 个状态。
6. 两个 deterministic failed calibration（LUT、Magic Lights）保留审计。只有控制策略、选择项或素材 hash 真实变化时才允许新 key。

这里必须区分“已可信采样”和“只有文件、证据不完整的 legacy import”。前者绝不重复；后者若无法从现有 state/log/AX 恢复 app build 和 fixture 归属，只能对 invalid 状态做一次定向原生 UI 重观察并生成新 evidence identity，否则该状态永久 blocked，项目不能声明 UI 绝对对齐。

### 4.3 不增加历史兼容逻辑

- 产品运行路径只实现当前 1.28 行为，不新增 `if version <= 1.26` 一类分支。
- 1.25/1.26 的 reference 和报告只作为只读审计资料；不参与当前 UI、效果、模型选择或交互决策。
- 新合同直接替换当前错误合同，并同步更新调用方和测试，不保留双字段、旧 payload 适配器或迁移开关。
- 不为未来未知模型、未知页面或未知后端提前抽象框架。

## 5. 总体依赖与批次顺序

| 阶段 | 输入 | 核心产物 | 准出条件 | 依赖 |
|---|---|---|---|---|
| P0 | 当前机器报告与历史输出 | 冻结账本、reference/UI manifest、阈值依据 | 基线可复现、0 重复队列 | 无 |
| P1 | 前端 current build | 7 条 Browser UI execution | `ui-execution-evidence` passed | P0 |
| P2 | interaction contracts | 10 条原生 observation | 原生 10/10 完整 | P0 |
| P3 | model source map | 4 个 ONNX 合同、4 个可达决策 | `model-source-map` passed | P0 |
| P4 | P3 共享语义 | 9 个效果修复与 holdout | smoke 45/45 | P3 |
| P5 | P1 current-build 截图 | 7 个 UI 状态修复 | UI 7/7 | P1 |
| P6 | P2 原生观察 + P1 Browser | 10 个候选执行 | interaction 10/10 | P1、P2 |
| P7 | 现有 canonical | Overlay 38/38、Workflow 3/3 | 内容链全过 | P0，可与 P4-P6 交错 |
| P8 | P3-P7 全部通过 | 95 个 exact 增量结果 | exact 96/96 | P3-P7 |
| P9 | 阶段计时与 job 记录 | 性能报告、长任务恢复报告 | 正确性不回退、可恢复 | 贯穿执行 |
| P10 | 全部产物 | 连续两次 exact 全绿 | 更新 manifest | P8、P9 |

同一时间只推进一个共享根因批次。一个批次包含：基线、最小实现、窄测试、候选生成、reference 对比、holdout、全量回归、账本更新。

## 6. P0：冻结证据、阈值和执行账本

### 6.1 动作

1. 复制当前关键指标到新执行账本，不修改旧报告：
   - exact 两次稳定为 `17/26 passed`；
   - smoke `36/45`；
   - UI `0/7`；
   - interaction 双边 `0/10`；
   - exact `1 + 95`；
   - workflow `0/3`。
2. 对主队列和 exact 队列执行只读 dry-run，确认 ready 不回队。
3. 运行 storage/data-chain 审计，确认不存在 staging/attempt 孤儿和 canonical hash 漂移。
4. 用历史重复 attempt 构建 repeatability manifest，优先复用已有的多次 exact attempt，不启动重复采样。
5. 新增 UI reference manifest，建议路径：
   `test_data/outputs/luminar-1.28.0-23071/ui/reference-manifest.json`。
6. manifest 每条记录至少包含：`reference_id`、app version/build/bundle、state、viewport、screenshot/AX 路径与 hash、fixture id/hash、locale、capture timestamp、evidence source。
7. 扩展 `scripts/validate_ui_references.py`：先验证 reference manifest，再做像素比较；metadata 缺失必须 fail closed。
8. 当前 legacy UI attempt 只有 state、截图、AX、viewport 和时间，没有独立 app build/fixture 字段。先查同次 capture 的 preflight、队列 fingerprint 和应用版本记录；仍无法形成可验证关联时，仅重观察对应 invalid state，不重跑效果、preset、overlay、sky、workflow 或 exact。

### 6.2 命令

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py --resume --dry-run

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --resume --dry-run

.venv/bin/python scripts/audit_sampling_storage.py \
  --capture-root test_data/outputs/luminar-1.28.0-23071/captures \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json
.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/validate_sampling_queue_captures.py
```

### 6.3 准出

- 主队列 `ready_filtered=251`、待执行 `0`。
- exact 队列仅剩未 ready 的 95 条。
- 重复、孤儿、hash 漂移均为 0。
- 7 个 UI reference 要么 manifest valid，要么明确列为 invalid；不能继续使用“截图存在即可信”的规则。
- 阈值没有因候选失败而放宽。

## 7. P1：恢复 UI Browser 证据通道

### 7.1 前置条件

必须使用应用内 Browser 的真实会话控制 zpixel 页面。独立 Playwright、手工替换截图或历史 candidate 不能作为 current-build 证据。

### 7.2 实施

1. 启动后端和前端，确认应用内 Browser 能发现并打开本地页面。
2. 固定：viewport `2880×1800`、DPR、locale `zh-Hans`、timezone、字体、主题、缩放和 motion preference。
3. 每次 build 后计算现有 `frontend_build_hash()`，旧 execution 自动失效。
4. 为 7 个状态建立确定性 fixture：`catalog`、`presets`、`edit`、`layer-stack`、`layer-library`、`tool-expanded`、`multi-image`。
5. 候选截图只在以下条件全部满足后采集：网络空闲不是唯一条件；图片解码完成、spinner 消失、请求 generation 未过期、目标面板可见、字体加载完成。
6. 生成：
   - `diagnostics/ui-candidates/2880x1800/<state>.png`
   - `diagnostics/ui-browser-execution.json`
7. execution record 写入 browser/version、viewport、locale、timezone、DPR、build hash、fixture hash、screenshot hash 和稳定条件。

### 7.3 准出

```bash
.venv/bin/python scripts/validate_ui_execution_evidence.py
```

必须 `expected=7`、`executed=7`、`passed=7`、`issue_count=0`。这一步只证明 current-build 证据可信，不代表视觉已经通过。

### 7.4 阻塞处理

如果 Browser discovery 仍为 `[]`，停止 P5/P6，不生成伪证据；记录 `browser-session-unavailable`。其余不依赖 Browser 的 P2、P3、P4、P7 可继续。

## 8. P2：补齐原生交互 observation

### 8.1 实施边界

在 `scripts/luminar_capture/` 内复用现有 `LuminarAppController`、`LuminarAccessibilityDriver`、semantic locator 和稳定帧等待，新增交互 observation runner；不另建第二套 AX 自动化框架。

建议新增：

- `scripts/luminar_capture/interaction_observer.py`：按 contract 执行原生事件并采集 before/after/AX；
- `scripts/run_luminar_interaction_observations.py`：筛选、resume、dry-run 和账本输出；
- `tests/test_luminar_interaction_observer.py`：事件映射、等待白名单、resume 和失败证据测试。

### 8.2 执行顺序

1. `catalog-import-select`
2. `preset-preview-apply`
3. 工具展开和 slider 提交
4. undo/redo
5. before/after compare
6. layer add/select/visibility
7. layer library
8. zoom/pan
9. export dialog
10. multi-image workflow

以 `configs/parity/interaction-contracts.json` 为唯一合同。每条 observation 输出到：

```text
test_data/outputs/luminar-1.28.0-23071/observations/interactions/<contract-id>/
  observation.json
  before.png
  after.png
  accessibility.json
```

### 8.3 证据字段

`observation.json` 必须包含 contract/reference/app version、fixture hash、原始 events、实际 wait conditions、visible assertions、final state、四个 artifact 路径与 SHA-256。事件失败时同样保存 after/AX 和错误定位，不吞错、不改 contract 为 passed。

### 8.4 准出

- 10/10 observation 存在且通过 `validate_interaction_execution.py` 的原生侧检查。
- 所有等待条件都来自 contract 的 `allowed_wait_conditions`。
- 无固定 sleep，无坐标兜底冒充语义控件定位。
- 已有可信 UI/effect canonical 不被重采。

## 9. P3：关闭模型运行时和输出合同

### 9.1 现状

待补 model-specific contract：

- `eyes_detector_i8_onnx`
- `face_detector_retinaface`
- `face_landmarks_i8_onnx`
- `segmentator_i8_onnx`

当前 macOS 不可达 logical model：

- `HumanLandmarks`
- `IrisLandmarks`
- `crop_decoder_i8`
- `crop_encoder_i8`

### 9.2 合同实施

每个 wrapper 只负责模型边界：输入颜色/布局/尺寸、归一化、forward、decode、坐标还原、输出结构和资源释放。业务 ROI、效果强度、图层合成继续留在 `ai/pipeline/`，不得塞进 `ai/model/`。

每个合同必须记录并测试：

| 类型 | 必需内容 |
|---|---|
| 检测 | 输入尺寸、letterbox、tensor 名、box 格式、置信度、NMS、坐标范围、空结果 |
| landmarks/eyes | 点数、顺序、坐标空间、face ROI 逆变换、置信度、多人顺序 |
| segmentation | class id、logit/概率、resize 方式、阈值、mask 范围、原图恢复 |
| interactive crop | encoder/decoder tensor 对接、point/box 输入、mask low-res/high-res 语义 |

### 9.3 不可达模型决策

逐个执行以下决策树：

1. registry 中存在当前 macOS 可用的 ONNX 资产：补 registry 变体和 wrapper 合同。
2. 只有现有 OpenVINO IR：使用当前 `scripts/convert_ir.py` / `scripts/run_openvino2onnx.py` 在合法本地资产上转换，并用固定 tensor fixture 做 IR/ONNX 数值对照；禁止运行时下载。
3. 转换不可行但能力的执行图确实需要该语义：保持 required blocked，并在报告中写清外部运行时/转换阻塞；不能从执行图删除来换绿。
4. 只有静态执行图误报且真实产品调用证明该逻辑不可达：必须同时提供调用审计和 UI 产品范围证据，才可从当前执行图删除。删除不保留旧兼容分支。

### 9.4 测试与准出

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contract-audit.json

.venv/bin/python scripts/audit_model_pipelines.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-pipeline-audit.json

.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations.json

.venv/bin/python scripts/build_model_source_map.py \
  --require-exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map.json
```

准出要求：required logical model 全部可解析；selected required contract 无 pending；活动调用和 pipeline 审计全过；加载失败抛可诊断错误；LRU 淘汰调用 `unload_model()`。

## 10. P4：关闭 9 个效果失败案例

### 10.1 通用批次规则

每个效果域先生成残差诊断：全图指标、ROI 指标、背景保护、边缘带、亮/暗区、分辨率和颜色统计。只修改能解释多张图片共同残差的最小逻辑。

每个域必须覆盖：默认值、当前 smoke、独立 holdout、无目标 no-op、边缘/遮挡。smoke 通过而 holdout 失败时，不进入下一域。

### 10.2 P4-A：`face_ai` 与 `slim_people`

修改入口：`ai/pipeline/analysis_pipelines.py`、`ai/pipeline/image_effect_pipelines.py`、对应检测/landmark/segmentation wrappers 和合同。

动作：

1. 完成 RetinaFace decode/NMS 和 face landmark/eye 输出合同。
2. 统一 face box 为一种显式坐标结构，修正当前 `_apply_face_ai` 对 box 分量顺序的隐式假设。
3. 以 landmarks 构建额头、眼、面中和下颌 ROI；局部亮度/锐度只作用于 Luminar 实际响应区域。
4. 多脸按稳定置信度/位置顺序处理；触边 ROI 正确裁剪和 feather。
5. `slim_people` 使用人体 mask + landmarks/主体中心线构造二维 displacement field；背景通过 mask feather 保持稳定，不能只按全 mask 中位数做统一横向挤压。
6. 增加单人、多人、无脸/无人、主体触边、复杂背景 holdout。

准出：两项 smoke 与全部 holdout 通过；无目标输出 hash 与输入一致或只存在已定义的编码噪声；背景非目标区误差不超过冻结上界。

### 10.3 P4-B：`depth_volume` 与 `fog`

动作：

1. 在 pipeline 层引入一个小型 `DepthField` 值对象，仅表达原图尺寸 depth、near/far 方向、有效范围和稳健分位数；不改 `BaseInference` 公共合同。
2. 用现有 Luminar reference 固定“值大代表近/远”的方向，禁止各效果各自猜测或反转。
3. 清理 NaN/Inf，使用稳健百分位归一化，恢复到原图时锁定插值方法。
4. `fog` 明确大气颜色、深度 alpha、前景保护和边缘 feather。
5. `depth_volume` 明确近/远区域的亮度/对比响应，不再使用无法解释的单一全图乘法。
6. holdout 覆盖近景主体、远景天空、室内低深度差和无可靠深度图。

准出：两项 smoke/holdout 通过；方向测试和分辨率测试稳定；背景边缘无 halo 回退。

### 10.4 P4-C：`sky_replace` 与两个 `sunrays`

动作：

1. 固定 sky mask、horizon、foreground、reflection 的坐标和分辨率合同。
2. 明确合成顺序：天空 fit/crop、色彩匹配、地平线 feather、前景恢复、反射/水面、全局 amount。
3. 对 sky reference 分别输出 mask、horizon、foreground、composite 中间件诊断。
4. `sunrays` 从 `sun_x`/`sun_y` 参数直接得到光源，不再仅用天空 mask 中位数推断。
5. 光线几何、角分布、半径、光晕、穿透和前景遮挡分开实现与验证。
6. 现有两个位置案例分别通过；新位置只在确有未覆盖语义时建立新 semantic key。

准出：`sky_replace` + 2 个 `sunrays` 全过；天空前景边缘 ROI 通过；太阳位置偏差有机器指标而非肉眼判断。

### 10.5 P4-D：`blue_hour`

动作：

1. 对 calibration 与 general hard holdout 同时输出色相、饱和、亮度、暗部/天空/主体分区残差。
2. 判断 residual 是全局 tone、亮度分段还是 semantic mask；只增加能被两组证据支持的最小分支。
3. 锁定颜色空间、操作顺序和 clipping；避免对单图拟合矩阵。
4. general hard holdout 未过时保持 blocked。

### 10.6 P4-E：`lut_mapping`

动作：

1. 保持旧 unchanged-source calibration 为 terminal failed，不重试。
2. 先验证菜单 choice 与持久 readback；策略/素材未变化时不产生新采样。
3. 对现有可信 canonical 检查 `.cube` domain、1D/3D LUT、插值、色彩空间、强度混合和 clipping。
4. 若需要改变原生控制策略，使用新 strategy version 和新 semantic key，只补受影响案例。

### 10.7 P4 总准出

```bash
.venv/bin/python scripts/generate_candidate_outputs.py
.venv/bin/python scripts/run_parity_suite.py
```

必须 `45/45 passed`。任何参数只让 smoke 变绿但 holdout 变差，立即回滚该批次。

## 11. P5：关闭 7 个 UI 状态

### 11.1 视觉方向与边界

采用单一“沉浸预览 + 精密工作台”方向：预览区最大、最安静；右侧工具紧凑；顶部导航、素材栏和图层区只服务当前任务。不得重新引入已删除的 1.25 CSS 覆盖层。

### 11.2 收敛顺序

1. `catalog`：应用壳、顶部栏、空态/导入、选中记录。
2. `presets`：缩略图密度、分类、选中/hover、预览稳定尺寸。
3. `edit`：主画布、工具栏、右侧栏、图片 fit/zoom。
4. `tool-expanded`：工具标题、滑杆、数值、开关、折叠和滚动。
5. `layer-stack`：行高、缩略图、可见性、选中和混合控制。
6. `layer-library`：素材网格、分组、加载/失败占位。
7. `multi-image`：多图列表、分析状态、预览和导出可用性。

### 11.3 每状态迭代

1. current-build 截图与 reference 比较。
2. 先修布局几何和滚动所有权，再修字体/控件，再修颜色/边框/图标。
3. 生成 diff mask，按区域统计 changed pixel，不做整页盲调。
4. 每次只改一个共享 token 或一个组件族。
5. 重新执行该状态的 Browser capture 和行为测试。
6. 该状态通过后锁定，后续共享 token 修改必须回归已锁状态。

修改入口：`frontend/src/styles.css`、主题/组件现有文件、`configs/ui/editor.json`；只有真实重复值才提取 token，不建立第二套 design system。

### 11.4 准出

```bash
cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

UI `7/7 passed`；所有 current-build evidence valid；主要滚动容器唯一；异步旧响应不能覆盖当前选择；关键空/加载/错误/选中状态有行为测试。

## 12. P6：关闭 10 个交互契约

### 12.1 候选执行器

通过应用内 Browser 按原生 observation 的事件序列执行当前页面，生成 `diagnostics/interaction-browser-execution.json` 和每条 final screenshot。执行器必须同时记录可见断言、API 断言、网络请求数量、wait condition 和 linked native observation hash。

### 12.2 状态机要求

- import 只能创建一个 asset/project，选择后预览 hash 对应 fixture。
- preset hover/preview 和 click/apply 不能互相污染；edit 顺序稳定。
- slider 拖动可预览，commit 只落一条语义编辑；undo/redo 一致。
- before/after compare 不能改变 edit stack。
- layer 新增、选择、可见性、混合模式和删除顺序稳定。
- zoom/pan 只改变 viewport，不改变导出像素。
- export 在响应完成后解除 busy，尺寸和 content-type 正确。
- multi-image 只有 preview ready 后才能导出。

### 12.3 长任务专项

模型推理和多图处理允许耗时长，但必须保证：

1. 服务器 job 持续运行，组件卸载只停止轮询。
2. mount 或 project change 后通过 latest job 恢复。
3. terminal job 先拉完整 result，再刷新 project。
4. stale generation 不能覆盖新项目。
5. worker 失败、租约过期、取消和重试都有确定终态和诊断。

### 12.4 准出

```bash
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

必须 definition `10/10`、native `10/10`、candidate `10/10`、issues `0`，并且所有 record 的 `fixed_sleep=false`。

## 13. P7：关闭 Overlay 与多图 Workflow

### 13.1 Overlay 38 项

当前只有素材和 layer material 规则，没有同 preset/sky/workflow 等级的最终合成报告。新增最小脚本 `scripts/run_overlay_e2e_validation.py`，复用现有 editor/layer 合成路径和 38 个 canonical：

- 校验 source/overlay hash、fit/crop、screen blending、opacity、色彩空间和输出尺寸；
- 输出 38 个 candidate 和逐项指标；
- 报告接入 `run_quality_gates.py` required gate；
- 不重新采原生 overlay。

准出：38/38 通过，且 `scripts/validate_layer_materials.py` 继续通过。

### 13.2 HDR merge

当前 `MAE 0.103737`、`SSIM 0.944482`。在 `image_ops/merge/hdr.py` 和共享 helper 中分离：曝光对齐、相机响应/权重、ghost 抑制、radiance merge、tone mapping。先用现有三帧 canonical 校验中间曝光权重，再调 tone；不得用最终全图常数修补。

### 13.3 Focus stacking

当前 `MAE 0.030116`、`SSIM 0.979591`，接近但未达门限。在 `image_ops/merge/focus.py` 诊断 focus measure、局部 winner mask、mask 平滑、边缘融合和颜色保持。优先修局部 seam/halo，不做全图锐化补偿。

### 13.4 Panorama stitching

当前 reference `1070×1410`，candidate `1078×1440`。在 `image_ops/merge/panorama.py` 先关闭几何尺寸：feature match、单应/投影、canvas bounds、黑边检测和 crop。尺寸完全一致后再调 blend/exposure，不允许 resize candidate 伪装 shape match。

### 13.5 准出

```bash
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke.json
```

Workflow `3/3`、Overlay `38/38`；所有输入 frame hash 与 reference metadata 一致；Preset `123/123` 和 Sky E2E `46/46` 无回退。

## 14. P8：增量关闭 95 个 exact 待办

### 14.1 放行条件

同时满足以下条件才可启动 Luminar exact 原生队列：

- model source map passed；
- smoke `45/45`；
- UI execution/UI parity `7/7`；
- interaction `10/10`；
- Overlay `38/38`、Workflow `3/3`；
- 主队列 resume dry-run 为 0；
- 当前增量队列重复/invalid 为 0。

### 14.2 重建队列

```bash
.venv/bin/python scripts/build_incremental_sampling_queue.py \
  --matrix test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-sampling-matrix.json \
  --smoke-queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json \
  --capture-root test_data/outputs/luminar-1.28.0-23071/captures \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --diff-output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --resume --dry-run
```

### 14.3 批次策略

按共享风险而不是队列顺序分批：

1. defaults/no-op anchors；
2. 已通过非 AI 基础色调和局部效果；
3. LUT/素材映射；
4. portrait；
5. depth；
6. sky/sunrays；
7. 其余 AI 与高成本模型。

每批建议 5–10 条。执行前 dry-run；执行后立即校验 data chain、生成 candidate、运行 exact incremental parity；通过后重建队列。失败时停止同域剩余采样，先修共享根因。

原生执行必须在专用 GUI 会话并显式授权：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --resume --limit 5 --allow-ui-control
```

### 14.4 准出

- exact queue `record_count=0`；
- exact semantic diff `existing_count=96`、duplicate/invalid/blocked 为 0；
- exact data chain 全部 ready；
- exact parity `96/96`。

## 15. P9：采样耗时、推理长任务和资源治理

### 15.1 采样耗时

历史 p50/p95：prepare→baseline `9.852/54.685s`，apply `0.913/3.965s`，preview stable `7.744/10.155s`，Luminar native export `47.488/106.096s`，canonical publish `1.623/1.668s`，总计 `75.123/123.794s`。

优化顺序：

1. 最大收益来自不重复采样和小批停止，而不是继续优化 1.6 秒 publish。
2. 不降低 export file-stable 和 preview-stable 阈值，除非历史阶段数据证明不会产生截断文件或未完成帧。
3. RGB PNG 保持 fast-copy；带 alpha、非 PNG、色彩规范化输入继续转换。
4. canonical publish 用临时文件 + atomic replace；每个子阶段继续记录耗时。
5. 将 UI 等待从通用 timeout 收敛为语义条件，失败立即保存 AX/截图，不空等到总 timeout。
6. 报告分别展示“Luminar 不可控 export 时间”和“本地可控 publish 时间”，不把二者混为重命名耗时。

目标：不牺牲稳定性的前提下，本地 publish p50 至少下降 25% 或稳定小于 1.2s；原生 export 只做观测，不设置不真实的强 SLA。

### 15.2 候选推理性能

1. `generate_candidate_outputs.py`、Sky/Overlay/exact 批处理复用同一个 model service/session，避免每案例重复加载。
2. 通过 `ModelLoader` 的现有缓存管理生命周期，不增加业务层全局单例。
3. 输出 hash 必须与优化前一致；性能优化不能改变模型语义或精度。
4. 扩展性能报告到多次 warm 运行，记录模型加载、preprocess、predict、postprocess 和合成阶段。

```bash
.venv/bin/python scripts/run_performance_suite.py \
  --image test_data/parity/inputs/summer-outdoor/a_7637493472862011940/008_e45cd3c34a.jpg \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/performance-report-current.json
```

### 15.3 长任务完整结果

保留现有 job repository/latest API/前端自动恢复，并新增以下故障测试：

- worker 在第 N 个模型后重启，从 checkpoint 恢复；
- 浏览器刷新、切项目、返回后恢复同一个 job；
- terminal result 大对象完整读取后才 merge project；
- lease 过期 worker 不能覆盖新 generation；
- failed/cancelled 保留错误和已完成 checkpoint；
- 缓存淘汰时模型资源被卸载。

准出：长任务断开重连测试全过；结果字段和 artifact hash 完整；页面卸载不取消服务端任务；无轮询泄漏。

## 16. P10：全量回归、双跑和发布

### 16.1 全量回归

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/run_preset_validation.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/preset-validation.json
.venv/bin/python scripts/run_sky_e2e_validation.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/validation-sky-e2e-report.json
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke.json
.venv/bin/python scripts/run_parity_suite.py
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

### 16.2 遗漏审计

逐项检查：

- 所有 ready canonical 有 state、attempt、log、metadata 和 hash；
- deterministic failed 未被自动重试或删除；
- 95 条 exact 已全部转为 existing ready；
- 模型 required direct/transitive 均可达且合同明确；
- UI reference manifest 和 Browser execution 都是 1.28/current build；
- interaction native/candidate 双边 10/10；
- Overlay/Workflow 有独立 comparator 报告；
- performance/long-job 不改变结果 hash；
- 运行代码没有 1.25/1.26 样式、参数或 payload 兼容分支；
- 所有阈值变化都来自原生噪声或产品语义证据，不来自候选失败。

### 16.3 连续双跑和发布

连续两次 exact required 全过后：

1. 比较两次 gate id、状态、case count 和关键 report hash。
2. 生成执行前后对比报告和最终遗漏清单。
3. 仅此时更新活动 `manifest.json` 和 parity 文档入口。
4. manifest 记录 Luminar build、输入/素材 hash、合同版本、前端 build hash、阈值依据和两次 gate report hash。

任意 required gate 失败：不更新 manifest，不使用“功能可用”替代“绝对对齐”。

## 17. 修改入口与测试矩阵

| 目标 | 主要修改位置 | 窄测试/验证 |
|---|---|---|
| 模型 wrapper/合同 | `ai/model/`、`models/contracts/`、`configs/model.yaml` | model validator、contract audit、固定 tensor tests |
| 模型编排 | `ai/pipeline/analysis_pipelines.py` | pipeline audit、analysis tests |
| 效果合成 | `ai/pipeline/image_effect_pipelines.py` | helper tests、smoke、holdout comparator |
| 深度合同 | pipeline 内小型值对象和 depth helpers | orientation/range/resize tests |
| 多图算法 | `image_ops/merge/`、`services/multi_image/service.py` | `tests/test_workflows.py`、workflow smoke |
| Overlay | `services/editor/service.py`、现有 layer/effect 路径、新 validator | layer material + overlay E2E |
| UI | `frontend/src/`、`frontend/src/styles.css`、`configs/ui/editor.json` | Vitest、build、Browser screenshot diff |
| 长任务 | `services/jobs/`、API repository、前端 job hook | repository/API/hook reconnect tests |
| 原生采样 | `scripts/luminar_capture/` | queue/observer/state/storage tests |
| 门禁 | `scripts/run_quality_gates.py`、各 validator | dry-run + exact report |

实现原则：修根因、保持局部、直接替换错误合同；只有已有重复代码证明需要时才提取抽象。任何新增字段都必须有当前消费者和测试。

## 18. 风险、停止条件与回滚

### 18.1 立即停止条件

- 相同 semantic key 被再次加入 ready 或 deterministic failed 队列；
- reference app/build、fixture hash、素材 hash 或 viewport 不匹配；
- Browser candidate 的 build hash 不是当前前端；
- 原生 readback 与目标参数/choice 不一致；
- 新模型合同只对单个最终图有效，固定 tensor/holdout 失败；
- smoke 变好但已通过案例、holdout 或背景保护回退；
- workflow 通过依赖 resize/crop reference 或放宽阈值；
- interaction 使用 undeclared wait 或 fixed sleep；
- 长任务返回 success 但 result/artifact 不完整；
- exact 任一批出现同域系统性失败。

### 18.2 回滚单位

按批次回滚代码，不删除机器证据。失败 candidate、diff、日志和报告保留；canonical reference、state 和 attempt 永不由效果修复覆盖。阈值、合同、素材和代码必须独立提交/记录，便于定位回退来源。

### 18.3 外部阻塞

Browser 不可用、Luminar GUI 不可控、合法模型变体不存在或系统权限不足时，明确标记 blocked 并继续其他无依赖阶段。不得用 standalone browser、假 observation、移除 required 模型或手工改 JSON 绕过。

## 19. 执行前后目标对比

| 指标 | 执行前 | 本计划完成后 |
|---|---:|---:|
| smoke 效果 | 36/45 | 45/45 |
| exact | 1/96 | 96/96 |
| UI current-build | 0/7 | 7/7 |
| interaction 原生/候选 | 0/10、0/10 | 10/10、10/10 |
| selected required model contract | 4 pending + 4 runtime unavailable | 0 pending、0 unavailable |
| Preset / Sky | 123/123、46/46 | 保持不回退 |
| Overlay | 无完整报告 | 38/38 独立 parity |
| Workflow | 0/3 | 3/3 |
| exact required gate | 8 failed | 0 failed，连续两次 |
| 重复采样 | 主队列已 0；exact 未放行 | ready/failed semantic 仍不重复 |
| manifest | 未更新 | 仅双跑全绿后更新 |

## 20. 最终完成检查表

- [ ] P0 基线、UI reference manifest、repeatability/阈值依据冻结。
- [ ] 主队列 251 ready 全部被 resume 过滤，exact 只含真实 pending。
- [ ] UI Browser current-build evidence 7/7。
- [ ] 原生 interaction observation 10/10。
- [ ] 候选 interaction execution 10/10，无 fixed sleep。
- [ ] 4 个 ONNX model-specific contract 完成。
- [ ] 4 个 macOS 不可达 logical model 有真实可用变体或经证据纠正执行图。
- [ ] `face_ai`、`slim_people` 与 holdout 通过。
- [ ] `depth_volume`、`fog` 与 holdout 通过。
- [ ] `sky_replace`、两个 `sunrays` 与 holdout 通过。
- [ ] `blue_hour` general hard holdout 通过。
- [ ] `lut_mapping` reference/readback 可信并通过。
- [ ] smoke 45/45。
- [ ] UI 7/7。
- [ ] Overlay 38/38，Workflow 3/3。
- [ ] exact 96/96，队列归零。
- [ ] 长模型任务断开恢复后得到完整 result。
- [ ] 性能优化前后输出 hash 不变。
- [ ] Python、Ruff、前端测试/build、模型验证全过。
- [ ] exact required gate 连续两次全过。
- [ ] 运行路径无历史版本兼容分支。
- [ ] 最终遗漏审计为 0 后才更新 manifest。
