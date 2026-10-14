# Luminar Neo 1.28 本地核心严格对齐优化计划（R13 已执行版）

更新时间：2026-08-30  
目标应用：本机 Luminar Neo `1.28.0 (23071)`  
执行基线：`alignment-r12-single-final-20260830`  
产品范围：免费、本地、可执行的照片编辑、目录、预设、图层、遮罩、多图工作流与导出  
明确排除：付费内容、商店、账户、云服务、教程、帮助、推广和授权购买流程

> 本文是 R13 已执行计划，保留用于审计 R13 决策。R14 当前唯一实施计划见
> `docs/parity/absolute-parity-core-convergence-plan-r14-current.md`。R13 的目标是在固定 Luminar build、固定素材、固定环境和上述范围内取得
> 可复现的严格对齐证据。实现不保留历史兼容逻辑，不引入 JSON catalog、JSON/SQLite 双写、旧
> schema/model/preset fallback、伪 `.lnpc`，也不允许按 case id、输入 hash 或文件名选择算法。

## 目录

- [1. 成功标准与范围边界](#1-成功标准与范围边界)
- [2. R12 权威基线](#2-r12-权威基线)
- [3. 执行原则与依赖](#3-执行原则与依赖)
- [4. P0：冻结 R13 worklist 和证据合同](#4-p0冻结-r13-worklist-和证据合同)
- [5. P1：隔离全屏 Native 环境](#5-p1隔离全屏-native-环境)
- [6. P2：补齐 59 项范围与 reference 缺口](#6-p2补齐-59-项范围与-reference-缺口)
- [7. P3：关闭 13 个效果失败点](#7-p3关闭-13-个效果失败点)
- [8. P4：模型合同与推理守护](#8-p4模型合同与推理守护)
- [9. P5：预设、交互和多图合同 10/10](#9-p5预设交互和多图合同-1010)
- [10. P6：current-build UI exact](#10-p6current-build-ui-exact)
- [11. P7：SQLite 单轨和数据一致性](#11-p7sqlite-单轨和数据一致性)
- [12. P8：全量回归与单轮 exact 36/36](#12-p8全量回归与单轮-exact-3636)
- [13. P9：同指纹 A/B 两轮](#13-p9同指纹-ab-两轮)
- [14. 修改与验证矩阵](#14-修改与验证矩阵)
- [15. 停止、回退与阻塞规则](#15-停止回退与阻塞规则)
- [16. 最终遗漏审计](#16-最终遗漏审计)

---

## 1. 成功标准与范围边界

### 1.1 严格对齐的可验证定义

只有以下条件同时成立，才能在本文限定范围内声明严格对齐：

1. **范围完整**：40 个显式本地工具、全部已声明参数、关键 UI 状态和关键交互都有合同与证据；
2. **效果精确**：Native preview/export 与候选输出通过现有 MAE/SSIM/shape 阈值，不降低阈值；
3. **UI 精确**：current-build screenshot、DOM、AX、viewport、DPR、fixture、浏览器和源码 hash 完整；
4. **交互精确**：Native 与 Browser 的事件、等待、API readback、持久化和输出 hash 一致；
5. **模型真实**：model-specific contract 通过且候选执行图实际调用对应模型；
6. **数据单轨**：catalog 只使用当前 Native SQLite schema，无 JSON 或双写兼容层；
7. **可重复**：完全相同的 source/model/reference/fixture/environment 指纹连续两轮 exact 全绿。

功能可运行、人工观感相似、单张 canonical 通过或模型 wrapper 可加载，都不能替代上述结论。

### 1.2 UI 范围冲突的处理

Luminar 整屏可能显示付费、商店、教程或帮助入口，而本项目明确排除这些功能。两者不能同时满足
“候选不显示排除项”和“整屏每个像素相同”。UI evidence 因此必须遵守：

- 保存完整 Native 和 Browser 整屏截图，供布局上下文审计；
- exact 只比较预先由 Native AX、状态合同和产品范围确定的 in-scope 区域；
- comparison region 必须在查看候选差异前冻结，Native/Browser 对称使用；
- 禁止为失败截图临时新增遮罩或改变阈值；
- 全局 shell、顶栏、目录、画布、工具、预设、图层、遮罩、多图和导出仍属于比较范围；
- 付费、账户、商店、教程、帮助及其专属区域不计入完成分母。

若 validator 尚不支持不可变区域合同，先增加合同字段、builder 校验和单元测试，再校准 UI；不能直接
裁剪图片绕过失败。

### 1.3 非目标

- 不外推到其他 Luminar 版本、locale、硬件或未知模型权重；
- 不实现付费、云端、账户、教程、帮助和推广流程；
- 不复刻 Luminar 数据库中与本地核心无关的业务表；
- 不为历史 JSON catalog、旧 preset 格式或旧模型保留兼容路径。

## 2. R12 权威基线

权威输入：

- `docs/parity/absolute-parity-execution-report-r12-current.md`；
- `docs/parity/in-scope-feature-matrix.md`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r12-single-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r12-current.json`。

| 维度 | R12 | R13 准出目标 |
|---|---:|---:|
| exact required gate | 31/36 | 36/36，连续两轮 |
| scope coverage | blocked，59 issues | 0 issues |
| 主效果 | 35/40 | 40/40 |
| Exact 增量 | 61/69 | 69/69 |
| 活动模型 contract | 22/22，0 pending | 继续全部通过 |
| 活动模型调用 | 18/18 | 全部 model-backed case 实际调用 |
| Native interaction | 9/10 | 10/10 |
| Browser interaction | 8/10 | 10/10 current-build |
| UI execution | 16/16 current-build | 16/16 及新增状态全部通过 |
| UI pixel | 0/16 | 16/16 及新增状态全部通过 |
| SQLite | passed | 单轨继续通过 |

R12 冻结指纹：

- release：`821bbd3680b1388c0aad0417c6b9f9f8f5f7fc3931e228b5c3a05db382d058d4`；
- source：`92cc621f3fe27d9e5b97406b91e878a7ca67cb4a848442909158799842c67285`；
- models：`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`；
- validation：`fbabacff11e25c3e14a6dfd2c9b39bad345bd5f7bc9f7574e5b0eb9b838eb8a7`；
- environment：`74a0cef157fd581a280daec90a6df2f474bff03ecd2729092caf53ce41f0bb05`；
- frontend build：`66fa7257d0bcdd02308e90f73d3ecc3004eb490e76e90281965849f06a746d89`；
- UI fixture：`c642001438c18634e41c56d798c2ca83f634b5b9ca371ecd21941e58d9e68799`。

R12 是只读回归基线。R13 的失败尝试使用新 run id，不覆盖 R12 artifact。

### 2.1 当前 5 个失败门禁

`absolute-scope-coverage`、`output-parity`、`exact-incremental-parity`、
`ui-parity`、`interaction-execution`。`ui-execution-evidence` 已在 R12 达到 16/16，R13 只做守护。

### 2.2 当前 59 项范围缺口

- 10 个工具缺完整 exact amount 锚点：`clone`、`color_transfer`、`complex_bleach`、`crop_ai`、
  `deblur`、`dodge_burn`、`erase`、`lut_mapping`、`skin_smooth`、`sky_replace`；
- 全部 40 个工具少于 3 个不同输入；
- `crop_ai` 缺 `crop_box`、`crop_ratio`、`crop_rotation`、`straighten`、`flip_x`、`flip_y`；
- Native 缺 `preset-import-preview-apply`；
- Browser 缺 `preset-import-preview-apply`、`multi-image-three-workflows`。

### 2.3 当前效果失败

主效果 5 项：Face AI 0.4、Depth Volume 0.4、Blue Hour 0.4、Sky Replace 0.4、Sunrays 0.4。

Exact 增量 8 项：Face AI 0.5/1.0、Depth Volume 1.0、Blue Hour 1.0、Sunrays 1.0、
Structure AI 1.0、AI Enhance 1.0、Landscape Enhancer 1.0。

### 2.4 当前机器 worklist

R12 最终 worklist 为 95 项：scope 59、主效果 5、Exact 增量 8、UI pixel 16、interaction 7。
按依赖拆分为：Native holdout 40、Native amount anchor 10、Native Crop 参数 6、Native interaction 1、
Browser interaction 2、效果 canonical 5、效果 anchor 8、UI 校准 16。一个工作项只能由对应 gate 的
新证据关闭，不能用其他 gate 的通过结果代替。

### 2.5 当前 UI 优先级

R12 UI evidence 已完整，但 16 个像素状态全部失败。优先按共享根因处理：

1. 多图完成页 `MAE 0.179788`、Denoise 选择态 `0.143594`；
2. Catalog `0.131490`、Presets `0.121704`；
3. Export `0.083716`、多图入口 `0.072468`；
4. editor family `0.029531–0.050599`，同时解决较高的 changed-pixel ratio。

MAE 接近阈值不等于通过；所有状态还必须满足 changed-pixel ratio `≤ 0.02`。

## 3. 执行原则与依赖

```text
P0 冻结 R13 worklist/合同
  ├────────────► P4 模型守护（只读）
  ├────────────► P5 Browser interaction current-build
  └────────────► P6 UI comparison-region 合同
  ▼
P1 隔离全屏 Native 环境
  ▼
P2 补 reference、锚点、holdout、Crop 参数
  ├────────────► P5 真实 preset Native 合同
  ▼
P3 效果校准 40/40 + 69/69
  ▼
P5 交互冻结与 Native/Browser 10/10
  ▼
P6 UI exact/current-build evidence
  ▼
P7 SQLite/数据一致性
  ▼
P8 单轮 exact 36/36
  ▼
P9 同指纹 A/B
  ▼
最终遗漏审计
```

每个工作项固定执行：假设与 reference → 单一修改 → unit/targeted → holdout → 同域 → 全效果 → exact。
canonical 改善但 holdout、zero identity、preview/export 或已通过 case 回归时立即回退。frontend hash
变化后全部 UI/Browser evidence 失效。单轮 exact 非零失败时不运行 A/B。

### 3.1 无 Native 隔离时允许继续的工作

- 更新 R13 worklist、validator 和不可变 UI region 合同；
- 使用项目自己的 headless Chrome/CDP 录制 current-build Browser interaction；
- 校准 UI 共享布局、字体、图标和 in-scope 状态；
- 运行模型、SQLite、测试和 build 守护；
- 分析既有 reference 和 intermediate，但不据此提交效果算法修改。

### 3.2 必须等待 Native 隔离的工作

- 新增或覆盖任何 Luminar preview/export/reference；
- 关闭 40 个 holdout、10 个 amount anchor、6 个 Crop 参数缺口；
- 录制 preset Native interaction 或提取真实 `.lnpc`；
- 基于新 reference 校准 5 个主效果和 8 个 Exact failure；
- 更改 Native persistence/schema 结论。

这两个清单是执行边界，不允许用 Browser smoke 或人工观察替代 Native evidence。

## 4. P0：冻结 R13 worklist 和证据合同

生成：

- `diagnostics/scope-coverage-r13-baseline.json`；
- `diagnostics/absolute-alignment-worklist-r13-baseline.json`；
- R13 reference/fixture/source 指纹；
- 不可变 UI comparison-region 合同；
- 95 项问题逐项依赖、输入、输出和验证命令。

```bash
.venv/bin/python scripts/validate_absolute_scope_coverage.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/scope-coverage-r13-baseline.json

.venv/bin/python scripts/build_absolute_alignment_worklist.py \
  --scope test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/absolute-scope-coverage.json \
  --main test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/parity-report.json \
  --exact test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/exact-incremental-parity.json \
  --ui-execution test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/ui-execution-evidence.json \
  --ui-parity test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/ui-parity.json \
  --interaction test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/interaction-execution.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r13-baseline.json
```

当前返回 blocked 是预期结果，不能手工删除问题。

若实施 scope-aware UI gate，必须先完成：

1. 从 Native AX 标注 in-scope 元素和稳定祖先区域；
2. 将 region id、Native bounds、state id、reference hash 写入 manifest；
3. builder 校验区域在整屏内、无歧义且 Native/Browser 都存在；
4. validator 同时输出区域指标和整屏诊断；
5. 增加“候选失败后不能改变 region”的不可变 hash 测试；
6. 排除项只能来自本文固定非目标，不能由像素差异决定。

P0 准出：R12 artifact 未修改；95 项机器问题全部进入 worklist；输入报告路径和 SHA-256 完整；
exact gate 总数继续为 36；不存在手工删除、合并或改名后丢失的失败项。

## 5. P1：隔离全屏 Native 环境

### 5.1 硬前提

只有以下条件全部满足才允许 Native UI 控制：

1. 独立 macOS 登录会话、VM 或独立远程桌面；
2. 虚拟显示和虚拟鼠标不共享用户正在使用的外设；
3. Luminar Neo 为前台且处于 macOS 全屏；
4. 版本严格是 `1.28.0 (23071)`，bundle id 为 `com.skylum.luminarneo`；
5. locale 为 `zh-Hans`；
6. 记录 display id、screen/window bounds、scale factor 和全屏状态；
7. 使用 disposable catalog/project；
8. 不打开付费、账户、商店、教程或帮助页面。

预检 artifact 固定为
`test_data/outputs/luminar-1.28.0-23071/diagnostics/native-isolation-preflight-r13.json`，至少包含：
`session_id`、`display_id`、`display_bounds`、`scale_factor`、`virtual_display`、`input_route`、
`input_isolated`、`luminar_version`、`bundle_id`、`locale`、`fullscreen`、`disposable_workspace`、
`ui_control_allowed` 和逐字段证据路径。任何布尔字段缺失都按 false 处理。

Computer Use 本身不等于输入隔离。无法证明隔离时保持 Native 9/10 和现有 reference 不变，只继续
Browser、代码诊断、模型守护和文档工作；exact 必须保持 blocked。

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run --preflight
.venv/bin/python scripts/run_luminar_interaction_observations.py --dry-run
```

只有 artifact 中 `virtual_display=true`、`input_isolated=true`、`fullscreen=true`、版本/locale/workspace
全部正确且 `ui_control_allowed=true` 后，单次正式命令才可增加 `--allow-ui-control` 或调用 Computer Use。
调用前后都保存全屏截图和 window/display bounds；中途退出全屏立即终止当前 capture，并将 attempt 标记
invalid，不自动重试。

P1 准出：保存隔离和全屏证据；若本机仍无隔离虚拟显示/输入，则明确记录
`blocked-no-isolated-input`，保持 Native、现有 reference 和用户外设不变，仅转入 3.1 的安全工作。

## 6. P2：补齐 59 项范围与 reference 缺口

### 6.1 批次顺序

1. **R13-2A：13 个当前失败 case**：先为对应能力补两个语义 holdout 和连续 anchor；
2. **R13-2B：10 个缺 amount anchor 工具**：至少 zero/mid/max，支持负值时增加 negative；
3. **R13-2C：Crop 六个几何参数**：逐参数单变量合同加一次组合 roundtrip；
4. **R13-2D：其余已通过工具**：补到 canonical + 两个不同 source hash；
5. **R13-2E：preset/interaction reference**：真实 Native 预设集合和缺失交互。

每批只在前一批 capture validator、data-chain validator 和 scope delta 都符合预期后进入下一批。
2A 只关闭所采能力的 holdout/anchor；不得在 2A 完成后一次性宣称 40 个工具覆盖完成。

### 6.2 输入与参数合同

每个工具至少三个不同 source hash：当前 canonical、语义强相关 holdout、保护/边界 holdout。禁止同一
照片改名充当 holdout。新 fixture 必须记录来源、许可、sha256、尺寸和选择理由。

- 通用连续 amount：`0/0.25/0.4/0.5/0.75/1`；
- 支持负值：增加 `-1/-0.5`；
- brush：半径、路径、强度和 source/target 语义；
- asset 工具：固定素材采 amount，再换至少一个合法素材；
- Crop：box、ratio、rotation、straighten、flip x/y 和组合 roundtrip；
- Sky Replace：scale、horizon、offset、rotation、亮度/对比度/饱和度/温度、edge、relight。

### 6.3 创建和采集单条队列

```bash
.venv/bin/python scripts/build_effect_calibration_queue.py \
  --capability sky_replace \
  --input test_data/parity/inputs/summer-outdoor/<holdout>.jpg \
  --parameters '{"amount":0.5,"opacity":1.0}' \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r13-sky-replace-holdout-a.json \
  --audit-output test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r13-sky-replace-holdout-a-audit.json

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r13-sky-replace-holdout-a.json \
  --preflight

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r13-sky-replace-holdout-a.json \
  --allow-ui-control
```

`<holdout>` 必须替换为已冻结文件。每条 capture 必须保存 input/asset hash、参数/readback、source reset、
before/preview/export、整窗截图、AX、两次 export 一致性、稳定等待和唯一 attempt。错误 source、非全屏、
无预期变化或输出路径复用全部标 invalid。

```bash
.venv/bin/python scripts/reconcile_sampling_queue_state.py
.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/<r13-batch>.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/<r13-batch>-captures.json
.venv/bin/python scripts/validate_sampling_data_chain.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/<r13-batch>.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/<r13-batch>-data-chain.json
.venv/bin/python scripts/validate_absolute_scope_coverage.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/scope-coverage-r13-after-capture.json
```

`<r13-batch>` 和 `<holdout>` 是执行前必须替换的占位符，不得原样运行。每个 batch 的准出条件：

- selected/ready/captured 数量一致，pending/invalid/failed 为 0；
- input、asset、parameters、readback、preview、export、AX 和 screenshot hash 完整；
- preview/export 非预期相同或未产生变化时失败关闭；zero identity 按合同单独验证；
- 两次独立 export hash 相同，且未复用旧 attempt 路径；
- scope issue 只按新增证据预期下降，无其他项回归。

P2 准出：10 个 amount 缺口、40 个 holdout 缺口和 6 个 Crop 参数缺口全部清零；pending/invalid 不进入
active reference。

## 7. P3：关闭 13 个效果失败点

### 7.1 修改边界

| 诊断结果 | 允许修改 | 禁止做法 |
|---|---|---|
| 输入/归一化/输出语义错误 | `ai/model/<task>/` wrapper/contract | 在 pipeline 重写 preprocess |
| 模型输出正确、组合错误 | `ai/pipeline/`、execution graph | 把效果编排塞进 wrapper |
| mask/geometry/blend 错误 | `image_ops/effects/`、compositor | 读取 case/hash 决策 |
| 加载/缓存/释放错误 | loader/backend | 失败后伪装 ready |

修改前保存 mask、depth、feature 和 blend intermediate。只有模型 I/O 证据错误才改 `ai/model`。
没有完成 P2 对应能力的 canonical + holdout A/B 时，不提交该能力的算法修改。

### 7.2 固定顺序

1. **Sky foundation/Sky Replace/Blue Hour**：先验证 sky probability、horizon、edge、foreground 和
   highlight mask；再校准 geometry、blend、relight 和颜色；覆盖细枝、建筑、无天空；关闭 0.4/1.0。
2. **Sunrays**：分离 light source、occlusion、ray density、falloff、core、bloom；先结构后颜色；
   覆盖开放天空和遮挡；关闭 0.4/1.0。
3. **Depth Volume**：验证 depth 近远方向、尺度和分位数，再做连续近/中/远局部重照明；平面场景保护，
   禁止用 y 坐标冒充深度；关闭 0.4/1.0。
4. **Face AI**：验证 face box、landmark、skin、eye、hair edge 和 foreground；先区域后强度；无脸和非脸
   背景保护；关闭 0.4/0.5/1.0。
5. **Structure/AI Enhance/Landscape**：拆分频段、tone/detail、sky/foliage/foreground 响应；验证
   0/0.25/0.5/0.75/1；关闭三个 1.0。

只读标量外推已证明不足：三项最优 MAE 仍约 0.03713、0.05970、0.03186，禁止继续用单一 amount
multiplier 拟合。

每个效果域使用独立短生命周期分支思路，但不引入新的通用框架：先写能重现当前 failure 的 targeted
测试，只改一个根因，保留 before/after intermediate。以下任一情况立即回退本次修改：

- canonical 通过但任一 holdout 失败；
- amount 0 不再恒等，或曲线出现非预期跳变；
- preview 与 export 走不同算法；
- 已通过的同域 case 退化；
- 模型调用、合同或资源释放退化；
- 需要读取 case id、文件名、source hash 或 reference hash 才能改善。

### 7.3 Targeted 模板

```bash
ZPIXEL_TARGET_RUN=r13-sky-replace-01
.venv/bin/python scripts/generate_candidate_outputs.py \
  --capability sky_replace \
  --output-root "test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/$ZPIXEL_TARGET_RUN/candidates" \
  --output "test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/$ZPIXEL_TARGET_RUN/generation.json" \
  --force
.venv/bin/python scripts/run_parity_suite.py \
  --capability sky_replace \
  --candidate-root "test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/$ZPIXEL_TARGET_RUN/candidates" \
  --output "test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/$ZPIXEL_TARGET_RUN/parity.json"
```

每项依次跑 unit → canonical → holdout A/B → 同域 → 主 40 → Exact 69。

每个效果域的提交前 artifact 至少包含：假设、修改文件、intermediate 路径、canonical 指标、两个
holdout 指标、zero identity、preview/export 一致性、同域回归和全量 parity delta。一次只关闭实际通过的
case；Face AI 0.4 仅差 `0.000175` 也不得放宽 `MAE 0.03`。

P3 准出：40/40、69/69、新增 anchor/holdout 全部通过；zero identity、preview/export、重复运行和既有
case 无回归；无阈值或特判。

## 8. P4：模型合同与推理守护

当前模型合同已通过，本阶段默认只守护，不做无证据重构。

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-r13.json
.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-runtime-audit-r13.json
```

ONNX 为 primary；OpenVINO IR 仅作同一逻辑模型且 backend parity 已验证的 fallback；不隐式下载；新增活动
模型先完成 model-specific normalization/postprocess/signature/runtime contract。22/22 通过不能替代
Luminar effect parity，也不重新引入旧 92/65 库存口径。

只有 intermediate 证明颜色顺序、resize、normalization、tensor layout、输出范围或 postprocess 语义错误时
才修改 `ai/model`。`load_model()` 必须在完整成功后才设置 loaded；失败不得写入缓存；淘汰和清理必须调用
`unload_model()`；权重只从本地路径加载，不允许推理时联网。效果 geometry/blend/relight 保持在
`ai/pipeline` 或 `image_ops/effects`，不塞进 wrapper。

P4 准出：0 blocking、活动合同 0 pending、所有 model-backed case 实际调用、加载/释放无泄漏。
P4 在 R13 开始时、每个 model-backed 效果域合并后、P8 前各执行一次；任一次失败都阻止继续合并效果修改。

## 9. P5：预设、交互和多图合同 10/10

### 9.1 真实 preset collection

当前 `.lnp` 目录只能证明单个本地预设内容，不能证明 Luminar 的预设集合导入。严格流程：

1. 取得 Luminar 生成或原生接受、provenance/hash 完整的真实 `.lnpc`；
2. 记录导入后 `.lnp/template.lmps`、图标、顺序和参数图；
3. 隔离全屏录制 import → visible → preview → apply → restart persistence；
4. 根据真实容器实现 zpixel 同一路径；
5. 针对 collection import 一次性切换到真实权威格式并删除旧适配路径，不把 `.lnp` 当作 `.lnpc`
   fallback；若 Native 证明二者是不同现役功能，分别建合同，不共享兼容解析器；
6. 无真实 `.lnpc` 时保持 unsupported/blocked，不伪造。

### 9.2 10 个合同

依次验证：目录照片右键；目录文件夹右键/滚动；工具/Crop；照片切换/历史；preset import；图层；遮罩；
compare/zoom/pan；HDR/Focus/Panorama；导出。每条使用 disposable workspace，等待为可观察状态，
`fixed_sleep=false`。

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py --dry-run
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --contract-id preset-import-preview-apply --allow-ui-control
.venv/bin/python scripts/validate_interaction_execution.py \
  --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-r13.json
```

正式 Browser raw record 必须包含 events、visible/API assertions、waits、screenshot、DOM、AX、execution、
network、console、API/project readback、export hash 和同 contract id Native observation。

R13 先补一个最小的 headless CDP interaction recorder，复用
`frontend/scripts/capture-ui-dpr2.mjs` 已验证的 browser 启动、DPR、DOM/AX 和截图逻辑，不抽象新的浏览器
框架。新增入口固定为 `frontend/scripts/capture-interaction-dpr2.mjs`；builder/validator 回归放入现有
`tests/test_interaction_browser_execution_builder.py` 和 `tests/test_interaction_execution.py`。recorder 必须：

- 使用 logical `1440×900`、DPR `2`、physical `2880×1800`、`zh-Hans`、`Asia/Shanghai`；
- 通过 DOM/CDP 设置 `<input type=file>`，不打开系统文件选择器，不使用共享鼠标键盘；
- 记录每个用户事件及其前后可观察断言，禁止 fixed sleep；
- 保存 Network、Console、DOM、AX、final screenshot、API/project readback 和 export SHA-256；
- 环境必须带 current frontend build hash、browser/version、fixture fingerprint；
- 失败的 contract 保持 failed，不由 builder 补默认字段伪装完成。

多图合同固定使用：

- `test_data/multi_image/hdr_merge/`；
- `test_data/multi_image/focus_stacking/`；
- `test_data/multi_image/panorama_stitching/`。

三种 workflow 分别验证输入顺序、处理中状态、完成态、preview、export、持久化和重新打开，不允许仅用
HDR 状态代替 Focus/Panorama。

runner 完成后的固定执行合同：

```bash
node frontend/scripts/capture-interaction-dpr2.mjs \
  --contracts configs/parity/interaction-contracts.json \
  --fixture test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r13-01.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-r13 \
  --raw-output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw-r13.json
```

这是 R13 计划新增的 runner 命令合同；实现时先用单个现有 contract 写失败测试，再扩展到 10 个合同，
不得先生成一份手工 raw JSON 再让 builder 接受。

```bash
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw-r13.json \
  --evidence-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-r13 \
  --native-root test_data/outputs/luminar-1.28.0-23071/observations/interactions \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution.json
.venv/bin/python scripts/validate_interaction_execution.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-r13.json
```

执行分两次准出：

1. **Browser-safe checkpoint**：当前 build 环境字段全部正确，现有 8 个合同重录通过，
   `multi-image-three-workflows` 正式通过；preset 仍可因 Native evidence 缺失而 blocked；
2. **最终 checkpoint**：真实 `.lnpc` 和 Native observation 完成后，preset Browser 合同通过，Native
   10/10、Browser 10/10、issue 0。

## 10. P6：current-build UI exact

### 10.1 冻结与 fixture

P0 先冻结现有路由、ARIA、DOM 和 API 状态机，允许在无 Native 隔离时开展 UI 工作。P3/P5 若修改这些
合同，完成后重新冻结并使此前 UI/Browser evidence 全部 stale。每次 frontend hash 变化都重录全部状态。

```bash
.venv/bin/python scripts/prepare_ui_evidence_fixture.py \
  --data-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-workspace-r13-01 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r13-01.json
```

要求 46/46 唯一照片、fixture fingerprint 稳定、SQLite 正确，不复用 R12 workspace。

在改 CSS 前完成 `configs/parity/ui-regions.json`：只从冻结的 Native screenshot、AX、产品范围和固定排除项
生成 include/exclude region。全局 shell、顶栏、目录、画布、工具、预设、图层、遮罩、多图、导出全部
include；只允许排除付费、商店、账户、云、教程、帮助、推广专属区域。region manifest 必须包含 state、
bounds、Native AX selector、reference hash、scope reason 和整体 SHA-256。

`scripts/validate_ui_references.py` 需要同时输出 in-scope exact 指标和 full-screen diagnostic 指标；
`scripts/build_ui_browser_execution.py` 必须绑定 region manifest hash。新增测试确保：

- region 越界、重叠歧义、缺 Native AX 或缺 reason 时 blocked；
- candidate failure 后修改 region hash 会使 evidence stale；
- Browser 和 Native 使用同一 bounds；
- full-screen screenshot 始终保留，不能只保存裁剪结果。

### 10.2 修复顺序

按共享根因和当前指标执行：

1. 字体文件/字重/行高、图标资源、颜色和阴影 token；
2. Catalog、Presets、多图完成页、Denoise 选择态的数据内容、素材和状态正确性；
3. shell、栏宽、canvas fit、crop、zoom、scroll 和 panel 几何；
4. layer/mask/history/more/info、dialog/popover/context menu；
5. export 和 HDR/Focus/Panorama loading/complete/error；
6. editor family 的细节与 changed-pixel ratio 收敛。

每次只改一个共享根因。targeted 状态必须改善，其他 15 状态不得回归；若共享修改不能解释至少两个状态，
优先检查 DOM/fixture 是否错误，不直接增加 state-specific CSS。确属 Native 不同状态结构时才使用状态级
布局，并同时补组件测试。

### 10.3 正式环境和采集

必须同时满足 logical `1440×900`、DPR `2`、physical `2880×1800`、`zh-Hans`、`Asia/Shanghai`、
reduced motion、独立 profile。in-app Browser 不满足 viewport 时只做 smoke。

```bash
node frontend/scripts/capture-ui-dpr2.mjs \
  --plan test_data/parity/ui-browser-capture-plan.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-r13 \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r13 \
  --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ZPIXEL_BROWSER_VERSION="$(jq -r '.browser' \
  test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-r13/capture-run.json)"
.venv/bin/python scripts/build_ui_browser_execution.py \
  --fixture-manifest test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r13-01.json \
  --source-captures test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-r13 \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r13 \
  --browser "Google Chrome Headless" \
  --browser-version "$ZPIXEL_BROWSER_VERSION" \
  --capture-engine chrome-cdp-page-capture-screenshot \
  --logical-width 1440 --logical-height 900 --device-scale-factor 2 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution.json
.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --execution test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution.json \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r13 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-r13.json
.venv/bin/python scripts/validate_ui_references.py \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r13 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-r13.json
```

P6 准出：current-build 最低 16/16 和新增状态全部通过；full screenshot、DOM、AX、region、DPR、viewport、
browser、locale、timezone、fixture/build hash 完整；任何 in-scope 失败区域都未被移出合同。

## 11. P7：SQLite 单轨和数据一致性

```bash
.venv/bin/python scripts/validate_luminar_catalog_schema.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/luminar-catalog-schema-r13.json
```

R13 已从本机 Group Container 找到真实 Native catalog，并以 SQLite URI
`mode=ro&immutable=1` 只读校验。当前唯一合同保持 schema 155、29 objects、26 tables、结构 hash
`af8a747826542f67922bab359d4c9567fee7739fc5aaf430e8bb1132dc96c86b`、
`compatibility_layers=[]`；validator 还必须绑定 Native catalog 文件 SHA-256 和结构 hash。旧自验证结构
`7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79` 已一次性替换，不保留迁移适配、
旧 schema reader、fallback、JSON catalog 或双写。API restart 后 catalog/preset/project/layer/mask/history 必须可读。

R13 额外审计 project/workflow/job/manifest 的 JSON primary repository。它们当前不是 JSON catalog 或双写，
但 Native persistence 等价仍未证明。处理规则：

1. 在隔离 Native disposable workspace 创建一个可识别项目，完成图层、遮罩、历史和三类 workflow；
2. 关闭 Luminar 后只读枚举新增/修改文件，记录 magic、SQLite header、表/对象、mtime 和 SHA-256；
3. 找到真实 SQLite 或其他 Native store 后，先建立字段映射和 roundtrip test；
4. 若证据证明这些状态应进入 SQLite，执行一次性数据迁移并删除对应 JSON repository、配置和测试路径；
5. 不保留读旧写新、双写、自动探测旧格式或旧 schema fallback；
6. 若 Native 证据表明这些状态不属于 catalog DB，则保留当前 primary store，但在报告中明确其 Native
   对应物和等价证据。

P7 准出：catalog schema validator 通过；workspace restart 后所有 in-scope 状态可读；文件清单中无 JSON
catalog、双写或 compatibility layer；project persistence 的结论有真实 Native provenance，而不是猜测。

## 12. P8：全量回归与单轮 exact 36/36

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --run-id alignment-r13-single-final-20260830 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-single-final.json
```

同时重跑 model、sampling/reference、sky/overlay、preset、多图、UI、interaction、catalog 和 export validators。

P8 准出：36/36、scope issue 0、R13 worklist 0、40/40、69/69、新增 holdout/anchor 全通过、UI execution
和 pixel 全通过、Native/Browser 10/10、模型/SQLite/sampling/export 无 pending/invalid、release fingerprint
完整。任一 required failure 非零就停止，不运行 A/B。

## 13. P9：同指纹 A/B 两轮

冻结 source、models、reference、fixture、Native observation、字体、frontend、Python/Node/browser 和环境。
A/B 使用不同 run 目录重新生成 candidate，不复用输出。

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --run-id alignment-r13-release-a-20260830 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-release-a.json
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --run-id alignment-r13-release-b-20260830 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-release-b.json

.venv/bin/python scripts/compare_exact_runs.py \
  --first test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-release-a.json \
  --second test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-release-b.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-r13-release-comparison.json
```

两轮都必须 36/36，且 source/model/reference/validation/environment/fixture/frontend/release fingerprint
完全一致。A 通过而 B 失败即 nondeterministic blocked；定位随机种子、线程、backend、缓存、字体、硬件和
文件排序，不运行第三轮碰运气。

## 14. 修改与验证矩阵

| 修改类型 | 最小验证 | 域回归 | 最终门禁 |
|---|---|---|---|
| deterministic effect | helper/unit + targeted | canonical + 两 holdout + 主/增量 | exact 36 |
| model-backed pipeline | intermediate + targeted | 同域 + invocation + 全效果 | exact 36 |
| `ai/model` wrapper | wrapper test + validator | contract/backend/invocation | exact 36 |
| sky/sunrays/depth/face | 区域指标和保护场景 | 共享域 + 全效果 | exact 36 |
| preset import | parser/service/persistence | Native/Browser preset | exact 36 |
| multi-image | 每 workflow 独立 preview/export | 三 workflow + interaction | exact 36 |
| UI/CSS | component + 单状态 | current-build 全状态 | exact 36 |
| interaction | 单合同 raw/evidence | Native/Browser 10/10 | exact 36 |
| catalog/schema | schema + service | restart/catalog/project | exact 36 |
| evidence 工具 | builder/validator unit | 全量重录 | exact 36 |

## 15. 停止、回退与阻塞规则

立即停止当前方向的条件：

- 需要降低任何像素或 artifact 阈值；
- 需要 case id、reference hash、文件名或 fixture 特判；
- canonical 改善但 holdout、zero、preview/export 或已通过 case 回归；
- 需要拼接不同 frontend hash 的证据；
- UI region 是看过候选差异后增加；
- Native 非全屏或输入未隔离；
- preset collection 不是真实原生 `.lnpc`；
- 同一 collection import 需要 `.lnp`/`.lnpc` fallback、JSON catalog、旧 schema/model/preset fallback；
- model load 失败却伪装 ready；
- 单轮 exact 未全绿却运行 A/B 或声明绝对对齐。

阻塞处理：无隔离 Native 时 P1/P2 Native/P5 Native blocked；无真实 `.lnpc` 时 preset blocked；
reference 不足时不改对应效果；Browser viewport 不合格时只做 smoke；单轮 exact 非零时不运行 A/B。

回退只撤销当前失败尝试，保留诊断，不覆盖 R12，也不修改用户无关文件。

## 16. 最终遗漏审计

Release B 后逐项检查，必须全部为“否”：

1. 是否有 in-scope UI 工具未映射 backend？
2. 是否有参数未覆盖 zero/min/mid/max/negative 或离散状态？
3. 是否有工具少于 canonical + 两个不同输入？
4. 是否有素材、画笔、几何、混合或开关没有 Native reference？
5. 是否只有 preview 通过而 export 未通过？
6. 是否有 current-build UI 缺 screenshot、DOM、AX、region、fixture 或 build hash？
7. 是否有 in-scope UI 区域被事后排除？
8. 是否有交互缺 Native、Browser、API、持久化或输出 hash？
9. 是否有活动模型未完成合同或未真实调用？
10. 是否存在 JSON catalog、双写或旧 fallback？
11. 是否把付费、账户、商店、教程、帮助计入完成分母？
12. 是否有 A/B 指纹不一致或 nondeterministic 输出？
13. 是否有 invalid/failed evidence 被人工改成 passed？
14. 是否有命令依赖共享鼠标键盘或非全屏 Luminar？
15. 是否有 project/workflow/job persistence 仍缺 Native provenance？
16. 是否仍有 R13 worklist 项未关闭，或 gate 数量/分母发生未审计变化？

最终验收：scope issue 0；40/40；69/69；新增 holdout/anchor 全通过；模型合同/调用通过；UI 全通过；
交互 10/10；SQLite 单轨；单轮 36/36；A/B 两轮 36/36 且指纹相同；遗漏审计 16 项全为“否”。

只有这些条件全部完成，才能声明：在本机 Luminar Neo `1.28.0 (23071)`、固定素材、固定环境和本文
明确的免费本地核心范围内，zpixel_edit 已达到可复现的严格对齐。
