# Luminar Neo 1.28.0 效果、UI、交互绝对对齐优化计划

> 本文基于 2026-08-22 最新代码与机器证据编制。真值固定为本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`；起点为效果 `36/45`、UI `0/7`、交互执行 `0/10`、exact `1/96`。计划只处理当前冻结产品范围，不新增历史兼容分支，也不重复采样已有证据。

## 目录

- [1. 目标与完成定义](#1-目标与完成定义)
- [2. 当前基线与遗漏](#2-当前基线与遗漏)
- [3. 执行原则与禁止事项](#3-执行原则与禁止事项)
- [4. 总体依赖与执行顺序](#4-总体依赖与执行顺序)
- [5. P0：冻结当前基线与执行账本](#5-p0冻结当前基线与执行账本)
- [6. P1：校正模型可达范围与 exact 门禁](#6-p1校正模型可达范围与-exact-门禁)
- [7. P2：修复原生采样可信度与等待耗时](#7-p2修复原生采样可信度与等待耗时)
- [8. P3：关闭剩余 9 个效果案例](#8-p3关闭剩余-9-个效果案例)
- [9. P4：建立 Luminar 原生 UI 与交互观察](#9-p4建立-luminar-原生-ui-与交互观察)
- [10. P5：关闭 7 个 UI 状态](#10-p5关闭-7-个-ui-状态)
- [11. P6：关闭 10 个交互契约](#11-p6关闭-10-个交互契约)
- [12. P7：增量关闭 95 个 exact 待办](#12-p7增量关闭-95-个-exact-待办)
- [13. P8：关闭内容链](#13-p8关闭内容链)
- [14. P9：长模型任务与整体性能收敛](#14-p9长模型任务与整体性能收敛)
- [15. P10：全量回归、遗漏审计与发布](#15-p10全量回归遗漏审计与发布)
- [16. 批次模板、停止条件与回滚](#16-批次模板停止条件与回滚)
- [17. 里程碑、目标增量与最终检查表](#17-里程碑目标增量与最终检查表)

---

## 1. 目标与完成定义

### 1.1 对齐目标

本计划中的“绝对对齐”是指：在冻结的本机免费、可达、可合法使用范围内，相同输入、参数、素材、顺序和用户事件，在 zpixel 与 Luminar Neo 两端得到预先定义门禁下不可区分的可观察结果。

对齐分为四层，不能互相替代：

1. **效果层**：preview、export、mask、depth、ROI、geometry、asset placement 和合成结果一致。
2. **UI 层**：固定环境下 7 个状态的布局、层级、控件、文本、素材与视觉结果一致。
3. **交互层**：10 条事件链的可见状态、编辑栈、API 状态、等待语义与导出结果一致。
4. **数据链层**：输入、参数、素材、模型调用、原生证据、候选证据、指标和发布状态可追溯且不可串版本。

这不是对 Luminar 私有源码或算法实现的逐字节复刻；完成声明只覆盖本计划冻结的可观察产品范围。字体栅格等平台噪声也不能靠临时放宽阈值处理，必须先由原生重复性证据定义容差。

### 1.2 最终硬门禁

| 领域 | 完成条件 |
|---|---|
| smoke 效果 | `45/45 passed`、`0 failed`、`0 pending` |
| 活动模型调用 | `22/22 passed`、无 stale trace |
| 活动模型契约 | 当前 `16/16` 保持通过 |
| 模型可达范围 | 所有模型均被分类；所有产品可达模型具备专属契约和真实推理证据 |
| UI | `7/7 passed`，且当前 build/fixture/browser 证据门禁通过 |
| 交互 | `10/10 passed`，每条都有 Luminar 原生 observation 与候选 Browser 执行 |
| exact | 96 项全部具备 canonical、candidate、data-chain 与 parity；重建队列后 `record_count=0` |
| 内容 | 123 preset、38 overlay、35 sky、3 workflow 均有候选严格证据 |
| 工程质量 | Python、Ruff、前端测试、生产构建、模型模块校验全部通过 |
| 发布 | 25 个 required exact gate 连续两次通过；26 个总 gate 的 optional 状态有明确结论 |

任一 required 条件未满足前，manifest 不得标记为 `parity-passed`。

## 2. 当前基线与遗漏

### 2.1 最新机器基线

| 指标 | 当前值 | 证据 |
|---|---:|---|
| smoke 效果 | 36/45 | `diagnostics/parity-report-current.json` |
| 活动模型调用 | 22/22 | `diagnostics/candidate-model-invocations.json` |
| 活动模型专属契约 | 16/16 | 同上 |
| 全模型专属契约 | 20/90 | `diagnostics/model-contract-audit.json` |
| 模型 consumer 映射 | 60 mapped / 30 unmapped | `diagnostics/model-source-map.json` |
| UI | 0/7 | `diagnostics/ui-parity.json` |
| UI 当前执行证据 | 0/7 | `diagnostics/ui-execution-evidence.json` |
| 交互定义 | 10/10 | `configs/parity/interaction-contracts.json` |
| 交互执行 | 0/10 | `diagnostics/interaction-execution.json` |
| smoke 采样恢复过滤 | 251 ready / 0 待采 | smoke queue dry-run |
| exact | 1 ready + 95 pending | exact incremental evidence |
| exact gate | 18 passed / 7 required failed / 1 optional failed | `diagnostics/quality-gates-exact-current.json` |
| 工程回归 | Python 224、前端 10、build passed | 最新执行报告 |

上述 `diagnostics` 均位于 `test_data/outputs/luminar-1.28.0-23071/`。

### 2.2 剩余效果失败

| 共享问题域 | capability | smoke case 数 | 当前主要问题 |
|---|---|---:|---|
| 人像 ROI/几何 | `face_ai`、`slim_people` | 2 | box/mask 坐标、padding、feather、局部形变语义未对齐 |
| 深度场 | `depth_volume`、`fog` | 2 | depth 方向、归一化、near/far 与空间 alpha 未冻结 |
| 天空与光线几何 | `sky_replace`、`sunrays` | 3 | sky mask、horizon、太阳中心、光线、素材定位和前景保护未对齐 |
| 空间色彩 | `blue_hour` | 1 | 全局色调曲线无法解释已有 general 样本 |
| 原生控件可信度 | `lut_mapping` | 1 | Luminar 菜单选择/提交/readback 未形成可信 reference |

### 2.3 已确认的 UI 根因

`frontend/src/styles.css` 先定义了 Luminar 1.28 workspace 几何，后面仍有 `Luminar Neo 1.25.1 workspace shell` 规则。CSS 后定义规则会覆盖前面的 1.28 规则，这是当前 UI 偏差的明确来源之一，也是“不需要历史兼容逻辑”必须清理的具体对象。

旧 UI candidate 缺少当前 build hash、browser environment 与 fixture 绑定，只能作为诊断素材，不能继续作为验收证据。

### 2.4 当前阻断

required：`model-source-map`、`exact-incremental-data-chain`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`。optional 阻断为 `model-contract-inventory`。

## 3. 执行原则与禁止事项

### 3.1 单一数据链

```text
冻结版本 + 输入 hash + 参数 + 素材 hash + 用户事件
                    │
                    ▼
Luminar canonical / native observation
                    │
            semantic key + provenance
                    ▼
当前代码 candidate + model/execution trace
                    │
                    ▼
effect / UI / interaction comparator
                    │
                    ▼
scoped gate → full gate → exact gate → release manifest
```

### 3.2 必须遵守

- 先验证 reference 的输入、控件、参数、素材与输出确实有效，再修改实现。
- 校准集与留出集严格分离；留出失败时停止合并，不用留出反向调参。
- 模型 wrapper 只负责加载、预处理、forward、后处理和稳定输出契约；业务编排与效果合成留在 `ai/pipeline`。
- UI 以本机 reference 为设计规范，不做主观“美化”；方向固定为精密工作台与沉浸预览。
- 每批只修改一个共享契约或状态族，并先跑窄范围验证。
- 局部、几何、随机、纹理和素材效果使用能力专属 comparator。
- 所有异步 UI 请求使用当前 request/job key，禁止旧响应覆盖当前图片、状态或结果。

### 3.3 禁止事项

- 不重复采样已有 ready canonical，包括当前 251 个 smoke/内容/UI 原生记录。
- 不使用 `--retry-failed` 重跑已证明确定性失败的相同 semantic key。
- 不以相同 case id 偷换输入、参数、素材或控件策略；语义真实变化时必须生成新 semantic key。
- 不从 1.25/1.26 输出推导 1.28 真值；历史队列只用于库存发现。
- 不新增 v1 fallback、双写、旧目录探测、旧 CSS 主题或运行时历史报告依赖。
- 不用系统浏览器、独立 Playwright、静态截图或人工声明替代应用内 Browser 证据。
- 不提高 `MAE 0.03`、降低 `SSIM 0.98` 或放宽 UI 阈值刷过门禁。
- 不把“模型成功 forward”“功能可运行”或“肉眼接近”写成最终 parity 通过。

## 4. 总体依赖与执行顺序

```text
P0 基线/账本
  ├── P1 模型可达范围 ───────────────┐
  ├── P2 采样可信度与耗时 ── P3 效果 ┤
  └── P4 原生 UI/交互观察 ── P5 UI ── P6 交互
                                      │
                                      ▼
                              smoke 45/45
                                      │
                                      ▼
                         P7 exact 95 项增量闭环
                                      │
                                      ▼
                         P8 内容链 + P9 性能稳定性
                                      │
                                      ▼
                              P10 最终发布
```

不同证据域可以推进，但实施时仍应按批次提交，禁止把多个未验证域混入同一改动。P7 必须等待 smoke、UI、交互和 required 模型范围全部通过。

## 5. P0：冻结当前基线与执行账本

### 5.1 动作

1. 固定 reference `luminar-neo-macos-1.28.0-23071`。
2. 保存当前 45 smoke、7 UI、10 interaction、96 exact 的不可变列表与状态。
3. 对 251 个 ready canonical 和已有 failed semantic attempt 生成 skip 清单。
4. 记录 frontend source hash、模型 registry hash、case/matrix/queue fingerprint。
5. 后续每批分配唯一 `batch_id`，记录修改、输入证据、输出报告和回滚点。

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-plan-baseline.json

.venv/bin/python scripts/run_luminar_sampling_queue.py --resume --dry-run
```

第二条命令必须显示已有 smoke 队列 `record_count=0`；若 ready 项重新入队，停止并修复 semantic dedup，不能继续原生采样。

### 5.2 准出

基线与 36/45、0/7、0/10、1+95 一致；不一致时以新机器报告为准并同步更新本文。

## 6. P1：校正模型可达范围与 exact 门禁

### 6.1 问题

活动调用契约已 `16/16`，但 required `model-source-map` 按 90 个库存模型要求 exact 行为，其中只有 20 个完成，30 个模型没有 consumer 映射。给所有库存补虚假合同或直接排除 pending 都不严谨。

### 6.2 动作

1. 从 `configs/ui/editor.json` 的冻结可见能力出发，经 `configs/capabilities/execution-graphs.json`、`ai/pipeline` 调用点和 `configs/model.yaml` 建立可达图。
2. 每个模型归入且只能归入：`required-direct`、`required-transitive`、`inventory-unreachable`、`invalid-orphan`。
3. `inventory-unreachable` 必须保存无 UI/API/执行图调用路径证据；仍留在库存审计，但不参与当前产品 exact 声明。
4. required 模型逐个补齐 `models/contracts/<model_id>.json`：layout、颜色、归一化、动态尺寸、输出语义、postprocess、runtime status、资源释放。
5. 每个 required 模型用本地权重执行真实正 fixture；检测/分割模型还需负 fixture。禁止仅用随机 tensor。
6. 修改 `scripts/build_model_source_map.py` 的 exact 判定，使 required gate 检查“全部可达模型已验证 + 全库存已分类”，optional inventory 继续报告 90 个模型完整度。
7. 不改变 `ai/model` 与 `ai/pipeline` 边界，不在 wrapper 加入 UI、任务排期或效果调参。

### 6.3 验证

```bash
.venv/bin/python scripts/build_model_source_map.py --require-exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map.json

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contract-audit.json

.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations.json

.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
```

### 6.4 准出

- 90/90 模型已分类，`unclassified=0`、`invalid-orphan=0`。
- 全部 required 模型有专属合同与真实推理证据。
- 活动调用保持 22/22，活动合同保持 16/16；若真实新增调用则同步增加并全部通过。
- `model-source-map` required gate 通过。

## 7. P2：修复原生采样可信度与等待耗时

### 7.1 耗时拆分

慢点主要是 Luminar 重渲染、预览稳定和导出稳定检测，不是 Python rename。先在 `scripts/luminar_capture/state_machine.py`、`stability.py`、`export_watcher.py`、`attempt_store.py`、`auto_sampler.py` 按 semantic key/attempt 记录：

`navigate_ms`、`control_locate_ms`、`control_commit_ms`、`preview_stable_ms`、`native_render_export_ms`、`file_stable_ms`、`validate_ms`、`canonical_publish_ms`、`total_ms`。

### 7.2 优化动作

1. attempt 使用唯一导出路径，Luminar 不直接覆盖 canonical。
2. 文件大小、mtime 和可解码图像连续稳定后，只做一次同文件系统原子发布。
3. 原生渲染 timeout 与 canonical publish 分离；replace 不承担 180 秒 export timeout。
4. 已验证 no-op 的确定性结果继续抛出 `NonRetryableCaptureError`，相同 semantic key 不再二次导出。
5. AXImage 瞬时缺失等可恢复错误保留有限重试；控件不存在、readback 不一致、完整导出无变化属于确定性失败。
6. 预览仍使用连续稳定帧；只有重复性数据支持时才缩短 `stable_samples`/`stable_seconds`。
7. 新采样批次先跑一个 anchor，比较 cold/warm 时间，再决定是否放行。

### 7.3 LUT 专项

当前 LUT failed semantic 不重试。先为 `menu_choice` 补齐点击前值、Anaheim 唯一定位、点击后 title/value readback、Amount=100 readback、收起再展开后的持久化 readback、preview/export 双变化门禁。

只有控制策略真实变化且 readback 证明已提交，才能用新的输入/参数/策略生成新 semantic key。若仍无变化，reference 保持 blocked，不把 zpixel 改为 no-op。

### 7.4 性能准出

- `canonical_publish_ms` 与原生渲染完全分离。
- ready 与 deterministic failed semantic 的恢复运行不启动 Luminar。
- no-op/失败恢复路径 p50/p95 相比 P0 降低至少 30%。
- 有效导出 total p95 不回退超过 10%，输出 hash/data-chain 不变。

## 8. P3：关闭剩余 9 个效果案例

### 8.1 通用规则

每个问题域按：reference 有效性 → 中间产物合同 → 最小实现 → 校准 → 独立留出 → 当前 smoke → 全 smoke。已有证据直接复用；只有缺少新空间/参数语义时才补采样。

候选生成不会触发 Luminar：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py --capability <capability> --force
.venv/bin/python scripts/run_parity_suite.py --capability <capability>
```

### 8.2 P3-A：`face_ai` 与 `slim_people`

入口：`ai/pipeline/image_effect_pipelines.py`、模型 contract、`tests/test_active_model_contracts.py` 与效果 parity 测试。

1. 固定输入 resize/letterbox 与原图坐标恢复。
2. `face_ai` 明确 box、置信度、多人排序、padding、feather 和面部 ROI 处理。
3. `slim_people` 明确人体 class、mask 去噪、主体中心线、位移场、边缘与画布保护。
4. 增加 ROI/geometry comparator：主体误差、背景稳定度、轮廓位移、边界连续性。
5. 覆盖单人、多脸、无人脸、人物触边、不同体型；无人目标必须稳定 no-op。

准出：两项 smoke 与独立留出通过，背景非目标区无明显位移，trace 与合同一致。

### 8.3 P3-B：`depth_volume` 与 `fog`

入口：`ai/pipeline/image_effect_pipelines.py` 的 depth 恢复与 `_apply_depth_effect`，以及 depth 模型合同。

1. 冻结 near-high/far-high，不允许效果自行反转。
2. 固定 resize 恢复、无效值、percentile normalization 和动态范围。
3. 定义共享 `DepthField`：原图尺寸、方向、有效范围、置信度/边缘。
4. `depth_volume` 按深度分层控制局部体积感；`fog` 用近远场 alpha 与边缘保护合成。
5. comparator 增加深度分层 ROI、前景泄漏、天空/地面分区和局部梯度。

准出：两个 smoke 通过，同一输入消费同一 depth contract，近景边缘无明显 halo。

### 8.4 P3-C：`sky_replace` 与 `sunrays`

入口：`ai/pipeline/image_effect_pipelines.py`、`image_ops/effects/sky_compositor.py`、天空/地平线/前景模型合同。

1. 固定 sky mask 阈值、软边、孔洞处理和原图坐标。
2. 固定 horizon angle/fraction、素材 cover/scale/offset/rotation。
3. 固定 foreground 与 reflection mask 的合成顺序。
4. `sunrays` 使用参数太阳位置，不再只用 sky mask 中位数猜测；冻结 ray count、角度、长度、宽度、衰减、色温和遮挡。
5. comparator 分别检查天空 ROI、地平线带、前景、反射、太阳中心和光线方向。
6. 两类现有 sunrays smoke 必须同时通过。

准出：`sky_replace` 1 项与 `sunrays` 2 项全部通过，asset hash、placement、trace 完整。

### 8.5 P3-D：`blue_hour`

入口：`image_ops/effects/basic.py`；不得继续叠加全局 RGB 常数。

1. 对现有 general、sky、校准、留出做 residual heatmap、亮度/色相分桶和天空/非天空 ROI 分析。
2. 判断响应属于亮度、语义区域还是空间渐变，只实现证据支持的最小模型。
3. 优先可解释的分区 tone mapping/soft mask；没有 trace 证据时不新增重模型。
4. 原 general smoke 是硬留出，MAE 仍高于 0.03 时不得合并。

准出：原 smoke 与全部现有留出同时通过，无留出反向调参。

### 8.6 P3-E：`lut_mapping`

先完成 P2 readback。reference 可信后，检查 `image_ops/effects/lut.py` 的 CUBE domain、三线性插值、Amount、contrast、saturation、颜色空间和量化。

准出：控件 readback、preview/export 变化和 asset hash 完整，当前 smoke 通过；reference 不可信则保持 blocked。

### 8.7 P3 总准出

```bash
.venv/bin/python scripts/run_parity_suite.py
.venv/bin/python scripts/audit_candidate_model_invocations.py --require-active-contracts
```

必须达到 45/45、模型调用无失败、全部新增 evidence data-chain 通过。

## 9. P4：建立 Luminar 原生 UI 与交互观察

### 9.1 UI reference

7 个原生 UI reference 已存在，不重复采样。只校验 `2880x1800`、locale/timezone/theme/font、fixture id/hash、7 个状态入口、截图 path/size/SHA-256。metadata 缺失时优先恢复已有 capture 的可验证元数据；无法证明属于当前 build/fixture 时标为 invalid，不静默复用。

### 9.2 原生交互 observation

按 `configs/parity/interaction-contracts.json` 扩展现有 `scripts/luminar_capture` 驱动，逐条生成：

```text
observations/interactions/<contract-id>/
├── observation.json
├── before.png
├── after.png
└── accessibility.json
```

`observation.json` 包含 contract/reference/app version、fixture hash、原始 events、final state、visible assertions、wait conditions、artifact path 与 hash。

批次顺序：

1. `catalog-import-select`、`preset-preview-apply`。
2. `edit-slider-drag`、`edit-toggle-collapse`、`undo-redo`、`before-after-compare`。
3. `zoom-pan`、`layer-add-reorder-opacity-delete`。
4. `export-dialog`、`multi-image-workflow`。

每条 observation 独立提交；失败不阻断其他观察，但不得生成 passed 候选记录。

## 10. P5：关闭 7 个 UI 状态

### 10.1 前置条件

必须恢复可发现的应用内 Browser 会话。runtime browser 列表为空时本阶段保持 blocked；可继续 P1/P2/P3/P4，但不能使用替代浏览器。

### 10.2 清理与实现

1. 删除 `frontend/src/styles.css` 中运行时生效的 1.25.1 workspace shell 覆盖。
2. 将 1.28 token、workspace geometry、组件状态收敛为唯一当前样式。
3. 历史截图/报告仅作离线审计，不保留历史主题选择器或 CSS 分支。
4. 审计 `App.tsx` 与组件，移除只服务旧布局的重复壳层，不重写已满足行为的组件。
5. 固定 Browser family/version、`2880x1800`、DPR、`zh-Hans`、timezone、build hash、fixture hash和动效等待。
6. 截图写入 `diagnostics/ui-candidates/2880x1800/<state>.png`。

### 10.3 状态族顺序

1. 共享壳层：topbar、workspace rail、全屏高度、滚动所有权、基础 token。
2. 内容工作区：catalog、presets、edit。
3. 编辑子状态：layer-stack、layer-library、tool-expanded。
4. 多图状态：multi-image。

每状态执行：截图 → diff/heatmap → 最大误差区域 → 最小改动 → 行为测试 → 新截图。

### 10.4 验收

冻结阈值：`MAE <= 0.03`、`changed_pixel_ratio <= 0.02`、尺寸一致。

```bash
cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

准出：7/7 状态与 current-build evidence 同时通过，无 stale candidate。

## 11. P6：关闭 10 个交互契约

### 11.1 原则与顺序

候选端使用 P5 同一 Browser/build/fixture。事件间只允许 contract 声明的条件等待，禁止 fixed sleep。

1. 导航/加载：导入只创建一次 asset/project；预设 preview/apply 不重复提交。
2. 编辑栈：slider、collapse、undo/redo、before/after 的顺序与状态一致。
3. 图层/画布：新增、排序、opacity、删除、zoom/pan/fit 的可见和持久状态一致。
4. 长任务：export 只有一次请求；multi-image 保存全部 frame hash、analysis、preview、render hash。

每条 execution record 绑定原生 observation 的路径与 SHA-256，并记录 event count、visible/API assertions、wait conditions、final screenshot。

### 11.2 异步专项

- 新请求开始清理旧 preview/error/result。
- request/job id 防止晚返回覆盖当前项目。
- 页面切换只停止 UI 轮询，不取消服务器任务。
- 组件卸载清理 timer/observer，轮询遇终态停止。
- 导出与 workflow 按钮只反映最新任务。

```bash
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

准出：`contract_count=10`、`executed=10`、`passed=10`、`issue_count=0`。

## 12. P7：增量关闭 95 个 exact 待办

### 12.1 启动条件

smoke 45/45、UI 7/7、interaction 10/10、required model source map 通过、ready canonical 恢复过滤仍为 0 待采。

### 12.2 重建队列

每批从 exact matrix、smoke queue 和 canonical 重建，不延用静态旧队列：

```bash
.venv/bin/python scripts/build_incremental_sampling_queue.py \
  --matrix test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-sampling-matrix.json \
  --smoke-queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json \
  --capture-root test_data/outputs/luminar-1.28.0-23071/captures \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --diff-output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json
```

已 ready 的 1 项不得入队，预计只剩 95 项。

### 12.3 批次策略

1. 按 capability 分组；每组先 1 个边界 anchor。
2. data-chain、原生变化、候选和 parity 全通过后才放行同组。
3. 顺序：零点/默认 → 正边界 → 负边界 → 素材变体 → 空目标/多目标。
4. AI 重任务一次一个；轻量效果可小批，但每批独立报告。
5. 只用 `--resume`，禁止 `--retry-failed`。

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> --limit 1 --resume --allow-ui-control

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --case-id <case-id>
```

每批 canonical 发布后重建 exact cases、生成 candidate、跑 scoped parity；失败则停止该 capability。通过后重建队列，确认本批 key 消失且历史 ready 未入队。

### 12.4 准出

exact 96/96 data-chain/parity 通过；重建队列 `record_count=0`；无重复 key、orphan attempt 或 staging 冒充 canonical。

## 13. P8：关闭内容链

123 preset、38 overlay、35 sky、3 workflow 的 Luminar canonical 已在 251 ready 集合中，不重复采样；只生成或修复 candidate、trace 与 comparator。

### 13.1 Preset

校验 preset id、完整 source effect graph、参数顺序与素材；不能只渲染第一个 effect。模型效果保留 invocation trace，比较最终 export 和 edit graph。

```bash
.venv/bin/python scripts/run_preset_validation.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/preset-validation.json
```

### 13.2 Overlay

校验 asset hash、blend mode、opacity、scale、offset、裁切；comparator 增加非透明 ROI、边界和高亮纹理。thumbnail 匹配不能替代最终合成 parity。

### 13.3 Sky

复用 P3-C 的 mask/horizon/placement/foreground/reflection contract；每项绑定 asset hash，分别验收天空、地平线、前景、反射。

```bash
.venv/bin/python scripts/run_sky_e2e_validation.py
```

### 13.4 Workflow

固定输入顺序、每帧 hash、分析终态、preview/export；断开重连仍取得完整结果；重复运行 render hash 稳定，失败不发布部分结果。

```bash
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke.json
```

准出：四类内容全 passed，asset/fixture/model/trace 完整，没有重新启动 251 个原生记录。

## 14. P9：长模型任务与整体性能收敛

### 14.1 长任务

复用 `scripts/run_inference_worker.py`、现有后端 job 状态和 `frontend/src/useAnalysisJob.ts`，不新建第二套任务系统。

必须具备：持久化 job/input/parameter/model hash；明确 `queued/running/succeeded/failed/cancelled`；checkpoint 但 partial output 不参与 parity；客户端断开后按 job id 重查；完整结果原子发布；可诊断失败；模型/session/processor 卸载和 LRU 可验证。

测试正常完成、轮询断开重连、页面切换、worker 失败、幂等查询、连续任务缓存/卸载六类场景。

### 14.2 性能报告

分别报告原生采样 cold/warm 与阶段 p50/p95、模型 load/preprocess/predict/postprocess、preview/export、UI 首屏/图片 ready/交互、长任务重连和 canonical publish。

优化不得改变输出 hash、合同、等待语义或 gate。优先消除重复执行、错误等待归属和缓存未命中，再做算法微优化。

## 15. P10：全量回归、遗漏审计与发布

### 15.1 回归

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model

.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-1.json

.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-2.json
```

两次 exact 必须在相同代码、配置、fixture、reference 下连续通过，第二次不能依赖临时状态或 stale candidate。

### 15.2 遗漏审计

- 45 smoke、96 exact、7 UI、10 interaction 无 pending/failed。
- 251 ready 没有重复执行。
- 90 模型全部分类，required 全验证。
- preset/overlay/sky/workflow 候选完整。
- 无 stale trace、orphan attempt、staging、partial result。
- 无 1.25/1.26 运行时 UI 覆盖、旧目录探测、双写、历史报告能力判定。
- 文档数字与机器报告一致；manifest 未提前修改。

### 15.3 发布

仅在两次 exact required gate 全通过后更新 manifest。发布绑定代码版本、frontend build hash、reference id、case/matrix/queue hash、模型 registry/contracts hash、asset manifest hash 和两份 exact 报告 hash。

发布后证据失效时回滚 manifest 与本批代码，不删除 canonical；失效项标为 blocked，返回对应阶段。

## 16. 批次模板、停止条件与回滚

### 16.1 批次字段

| 字段 | 内容 |
|---|---|
| `batch_id` | 唯一标识 |
| `scope` | 单 capability、共享合同、UI/交互状态族 |
| `reference_id` | 1.28.0/23071 |
| `semantic_keys` | 涉及语义 |
| `existing_evidence` | 复用 canonical/observation |
| `new_sampling_reason` | 无新采样则为空；有时说明真实缺口 |
| `files_changed` | 实际路径 |
| `scoped_tests` | 窄范围结果 |
| `holdouts` | 未调参证据 |
| `full_gates` | 全量结果 |
| `rollback` | 最小回滚边界 |

### 16.2 立即停止条件

- reference 与 source 无有效差异且 readback 不可信。
- semantic key 已有 ready 或 deterministic failed evidence。
- fixture/asset/build/reference hash 不一致。
- 留出失败、非目标区退化或已通过 smoke 回归。
- 模型输出非有限值或不符合合同。
- Browser 不是应用内 runtime 或 evidence 不完整。
- 需要放宽冻结阈值。
- 长任务只得到 partial output。
- 改动引入历史兼容分支或第二套并行架构。

### 16.3 回滚

- 只回滚当前批代码、配置、candidate/report；canonical 不覆盖、不删除。
- 模型合同失败时回滚合同与 wrapper，不能模糊标记成功。
- UI 状态失败时回滚当前状态族，不恢复 1.25 CSS。
- 新采样失败保留 attempt 审计，不发布 canonical，也不自动重试。

## 17. 里程碑、目标增量与最终检查表

### 17.1 里程碑

| 里程碑 | 目标 | 下一阶段 |
|---|---|---|
| M0 | 36/45、0/7、0/10、1+95 可重现 | 可进入收敛 |
| M1 | 90/90 分类、required 全合同 | 可进入完整模型声明 |
| M2 | 效果 45/45 | P7 必要条件 |
| M3 | UI 7/7 + current-build evidence | P7 必要条件 |
| M4 | interaction 10/10 双边执行 | P7 必要条件 |
| M5 | exact 96/96、增量队列为 0 | 可进入内容发布 |
| M6 | 内容通过、长任务完整、性能无退化 | 可进入发布 |
| M7 | exact required gates 连续两次通过 | 可发布 |

### 17.2 目标增量

| 指标 | 当前 | 目标 | 增量 |
|---|---:|---:|---:|
| smoke | 36/45 | 45/45 | +9 |
| UI | 0/7 | 7/7 | +7 |
| interaction | 0/10 | 10/10 | +10 |
| exact | 1/96 | 96/96 | +95 |
| 模型合同 | 20/90 inventory | 所有 required 可达模型通过 | P1 确定 |
| required exact blockers | 7 | 0 | -7 |
| optional blockers | 1 | 0 或严格不可达结论 | 不允许未分类 |

### 17.3 最终检查表

- [ ] reference 仍为 Luminar Neo 1.28.0 build 23071。
- [ ] 251 个 ready canonical 没有重复采样。
- [ ] deterministic failed semantic 没有相同语义重试。
- [ ] 效果 45/45，局部/几何效果使用专属 comparator。
- [ ] required 模型合同、真实输入输出、资源释放通过。
- [ ] UI 7/7，旧 1.25 workspace CSS 不再运行时生效。
- [ ] 交互 10/10，每条绑定原生 observation。
- [ ] exact 96/96，重建增量队列为 0。
- [ ] preset、overlay、sky、workflow 候选链完整。
- [ ] 长模型任务断线可恢复，只发布完整终态。
- [ ] Python、Ruff、前端测试、build 全通过。
- [ ] exact required gates 连续两次通过。
- [ ] 报告、文档导航、manifest 一致。
- [ ] 无历史兼容逻辑、阈值漂移、stale evidence 或伪成功。
