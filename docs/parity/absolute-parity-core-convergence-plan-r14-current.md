# Luminar Neo 1.28 本地核心完全收敛计划（R14 当前执行版）

更新时间：2026-08-31  
目标应用：本机 Luminar Neo `1.28.0 (23071)`  
执行基线：`alignment-r13-final-20260831`  
产品范围：免费、本地、可执行的目录、预设、40 个编辑能力、图层、遮罩、多图工作流与导出  
明确排除：付费内容、商店、账户、云服务、教程、帮助、推广、授权购买流程

> 本文是 R14 唯一当前实施计划。目标不是继续增加功能数量，而是关闭 R13 留下的 5 个 required gate，
> 使本地核心在固定 Luminar build、固定输入、固定模型、固定环境和固定证据合同下完整收敛。实现不保留
> 历史兼容逻辑，不引入旧 schema/model/preset reader、JSON catalog、JSON/SQLite 双写、伪 `.lnpc`，
> 也不允许根据 case id、文件名、输入 hash 或 reference hash 选择算法。

## 目录

- [1. 最终成功标准](#1-最终成功标准)
- [2. R13 权威基线](#2-r13-权威基线)
- [3. 范围、假设和硬约束](#3-范围假设和硬约束)
- [4. 执行依赖和批次总览](#4-执行依赖和批次总览)
- [5. P0：冻结 R14 基线和机器 worklist](#5-p0冻结-r14-基线和机器-worklist)
- [6. P1：建立隔离全屏 Native 采样环境](#6-p1建立隔离全屏-native-采样环境)
- [7. P2：补齐 Native reference 与 59 项范围缺口](#7-p2补齐-native-reference-与-59-项范围缺口)
- [8. P3：效果域逐项收敛到 40/40 和 69/69](#8-p3效果域逐项收敛到-4040-和-6969)
- [9. P4：交互、预设和多图收敛到 10/10](#9-p4交互预设和多图收敛到-1010)
- [10. P5：UI 16/16 像素收敛](#10-p5ui-1616-像素收敛)
- [11. P6：Native 持久化单轨](#11-p6native-持久化单轨)
- [12. P7：模型、性能和全量回归守护](#12-p7模型性能和全量回归守护)
- [13. P8：单轮 exact 37/37](#13-p8单轮-exact-3737)
- [14. P9：同指纹 A/B 两轮](#14-p9同指纹-ab-两轮)
- [15. 修改与验证矩阵](#15-修改与验证矩阵)
- [16. 停止、回退和阻塞规则](#16-停止回退和阻塞规则)
- [17. 最终遗漏审计](#17-最终遗漏审计)
- [18. 交付物清单](#18-交付物清单)

---

## 1. 最终成功标准

只有以下条件同时成立，才能声明本文限定范围内的本地核心完全收敛：

| 维度 | 最终要求 | 禁止替代项 |
|---|---:|---|
| exact required gate | 37/37，连续两轮 | 功能可运行、人工观感相似 |
| absolute scope | 0 issue | 手工删除、改分母、改名隐藏 |
| 主效果 | 40/40 | 单张 canonical 通过 |
| Exact 增量 | 69/69 | 只通过低 amount |
| holdout | 40/40 工具均为 canonical + 两个不同 source | 同图改名、同 hash 重复 |
| amount/参数 | 10 个 anchor 与 6 个 Crop 参数全部覆盖 | 只测默认值 |
| UI evidence | 16/16 current-build | 旧 build 截图 |
| UI pixel | 16/16 | 修改 region 或降低阈值 |
| Native interaction | 10/10 | 人工叙述 |
| Browser interaction | 10/10，同一 frontend build | 拼接不同 build artifact |
| 模型合同 | 22/22，0 pending | runtime-ready 代替 contract |
| 模型真实调用 | 18/18 | wrapper 可加载代替 invocation |
| catalog | 真实 Native schema 155、29 objects、26 tables | 项目自定义相似 schema |
| persistence | layer/mask/history/workflow/preset Native roundtrip | JSON primary + SQLite projection |
| 可重复性 | source/model/reference/fixture/environment 指纹一致 | 重跑到偶然通过 |

现有阈值保持不变：默认效果 `SSIM >= 0.98`、`MAE <= 0.03`、shape 必须一致；UI
`MAE <= 0.03` 且 changed pixel ratio `<= 0.02`。Grain 继续使用既有统计比较合同。阈值只能通过新的
Luminar 重复导出方差研究收紧，不能为关闭失败而放宽。

## 2. R13 权威基线

权威输入：

- `docs/parity/absolute-parity-execution-report-r13-current.md`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/persistence-storage-audit-r13.json`。

| 维度 | R13 | R14 目标 |
|---|---:|---:|
| exact | 31/36，5 failed | 37/37 × 2（新增 persistence gate） |
| scope | 59 issues | 0 |
| 主效果 | 35/40 | 40/40 |
| Exact 增量 | 61/69 | 69/69 |
| worklist | 95 | 0 |
| UI evidence | 16/16 | 16/16 current-build |
| UI pixel | 0/16 | 16/16 |
| Native interaction | 9/10 | 10/10 |
| Browser interaction | 8/10；多图另有 current-build 1/1 | 10/10 单一汇总 |
| 模型 | 22/22；runtime 18/18 | 保持全绿 |
| catalog | Native schema matched | 保持全绿 |
| 非 catalog persistence | blocked | Native roundtrip + 单轨 |

R13 失败 gate 固定为：`absolute-scope-coverage`、`output-parity`、
`exact-incremental-parity`、`ui-parity`、`interaction-execution`。

R13 release fingerprint：
`50fe4dd570ffb8e034a8d94d327c51e0473cee0f11faea61a2067a88a94ab2e3`。R13 artifact 只读，
R14 使用新 run id 和新目录，禁止覆盖或重标 R13 证据。

## 3. 范围、假设和硬约束

### 3.1 包含范围

1. 目录导入、选择、滚动、评分、旋转、右键菜单和照片切换；
2. `configs/ui/editor.json` 中声明的 40 个免费本地编辑能力及其活动参数；
3. 本地预设集合导入、预览、应用和重启持久化；
4. 图层创建、排序、显隐、混合、变换、删除；
5. 遮罩创建、画笔参数、undo/redo、重置；
6. compare、zoom、pan、history；
7. HDR Merge、Focus Stacking、Panorama Stitching；
8. PNG/JPEG 等当前本地导出、尺寸、色彩空间和文件结果；
9. 以上能力所需的 SQLite catalog 与 Native 状态持久化。

### 3.2 排除范围

付费扩展、商店、订阅、账户、云同步、教程、帮助、推广、授权购买和仅服务这些功能的数据/UI 不进入
完成分母。全屏截图仍保留用于审计；exact region 只排除 `configs/parity/ui-regions.json` 已冻结的明确
非目标区域，不能因候选失败新增排除。

### 3.3 已知假设

- Native 目标固定为 `1.28.0 (23071)`、bundle id `com.skylum.luminarneo`、`zh-Hans`；
- Browser 固定 logical 1440×900、DPR 2、physical 2880×1800、Asia/Shanghai；
- 模型和素材均使用本地合法文件，不在运行时联网下载；
- Computer Use 只有在 Luminar 全屏且虚拟显示、虚拟输入、输入路由都被证明隔离后才能使用；
- 无隔离环境时保持用户桌面和外设现状，Native 阶段继续 blocked，不用 Browser 结果冒充 Native。

## 4. 执行依赖和批次总览

```text
P0 冻结 R14 基线
  │
  ├── Browser-safe 轨 ── P4-A recorder/功能实现与 smoke ── P5 UI 根因修复
  │                                                    └── P4-B 同 build 10/10 正式重录
  │
  └── Native-critical 轨
       P1 隔离全屏环境
         │
         ├── P2 holdout / anchor / Crop / preset 真值
         │      ├── P3 效果收敛
         │      └── P4 Native preset + 10/10 汇总
         │
         └── P6 Native persistence delta / roundtrip / 单轨

P3 + P4 + P5 + P6 全绿
  └── P7 全量守护 ── P8 单轮 37/37 ── P9 同指纹 A/B 37/37
```

执行顺序以依赖为准，不以日历为准。Browser-safe 工作可以在等待隔离环境时推进，但不能关闭 Native scope、
Native interaction 或 persistence 项。

## 5. P0：冻结 R14 基线和机器 worklist

### 5.1 操作

1. 以 R13 final run 生成 R14 scope、worklist、source/release fingerprint；
2. 冻结当前 gate 数量 36、40 个主能力、69 个 Exact case、16 个 UI 状态、10 个 interaction contract；
3. 保存输入报告路径和 SHA-256；
4. 检查 `configs/parity.yaml`、`configs/parity/ui-regions.json`、
   `configs/parity/interaction-contracts.json` 没有未审计的分母变化；
5. 将 95 项 worklist 分配到 P2/P3/P4/P5，不允许人工删除；
6. 记录一个有依据的 R14 门禁增强：P6 新增 `native-persistence-roundtrip` required gate，使最终分母从
   36 增加为 37。除该项外，禁止未审计的分母变化。

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact --dry-run \
  --run-id alignment-r14-plan-baseline-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-plan-baseline.json

.venv/bin/python scripts/validate_absolute_scope_coverage.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/scope-coverage-r14-baseline.json

.venv/bin/python scripts/build_absolute_alignment_worklist.py \
  --scope test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/absolute-scope-coverage.json \
  --main test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/parity-report.json \
  --exact test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/exact-incremental-parity.json \
  --ui-execution test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/ui-execution-evidence.json \
  --ui-parity test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/ui-parity.json \
  --interaction test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/interaction-execution.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r14-baseline.json
```

### 5.2 准出

- R13 artifact 未修改；
- R14 baseline 如实为 blocked；
- 基线 36/40/69/16/10 分母与 R13 一致，并单独登记 P6 将增加的第 37 个门禁；
- 95 项全部可追溯到原报告和 hash；
- 没有阈值、region 或 scope 变更。

## 6. P1：建立隔离全屏 Native 采样环境

### 6.1 允许方案

按优先级选择：独立 macOS VM；独立登录会话加独立远程桌面；能证明显示和输入独立路由的虚拟显示方案。
仅创建虚拟屏幕但鼠标键盘仍共享，不满足准入。Computer Use 能操作 UI，但本身不能证明隔离。

### 6.2 预检字段

`native-isolation-preflight-r14.json` 必须记录：session id、display id/bounds、scale factor、虚拟显示实现、
输入设备/路由、input isolated、Luminar version/build、bundle id、locale、全屏状态、前台状态、disposable
workspace、UI control allowed、采集前后截图和证据 hash。缺字段按 false 处理。

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run --preflight
.venv/bin/python scripts/run_luminar_interaction_observations.py --dry-run
```

只有 `virtual_display=true`、`input_isolated=true`、`fullscreen=true`、版本/locale/workspace 正确且
`ui_control_allowed=true` 后，才允许正式命令带 `--allow-ui-control` 或调用 Computer Use。

### 6.3 运行纪律

- 每个批次开始和结束都记录 window/display bounds；
- Luminar 一旦退出全屏、丢失前台或显示器变化，当前 attempt 立即 invalid；
- 不自动移动到用户主屏，不接管真实鼠标键盘，不打开系统文件选择器；
- 使用 disposable catalog/project，Native 主 catalog 只读；
- 不进入排除范围页面；
- 无隔离时 artifact 写 `blocked-no-isolated-input`，保持现状。

### 6.4 准出

隔离证据完整，试采一条无副作用 UI 状态成功且用户主屏输入未发生变化。否则 P2、P4 Native、P6 全部
保持 blocked，只继续 Browser-safe 轨。

## 7. P2：补齐 Native reference 与 59 项范围缺口

### 7.1 目标分解

当前 59 项由以下四类组成：

- 40 个工具缺两个不同 source holdout；
- 10 个工具缺 amount anchor：Clone、Color Transfer、Complex Bleach、Crop AI、Deblur、Dodge & Burn、
  Erase、LUT Mapping、Skin Smooth、Sky Replace；
- Crop 缺 box、ratio、rotation、straighten、flip X、flip Y；
- Native preset import 1 项、Browser preset/multi 2 项。

holdout 最少形成 80 个新的工具-输入证据对；anchor 可复用同一合法输入，但不能用重复 source hash 关闭
holdout。每条同时保存 preview 和 export。

### 7.2 输入选择合同

每个工具固定三个不同 source：现有 canonical、语义主场景 holdout A、保护/边界 holdout B。

| 工具域 | holdout A | holdout B |
|---|---|---|
| sky / Blue Hour / Sunrays | 开放天空、明确地平线 | 细枝/建筑遮挡或无天空 |
| face / skin / slim | 单人正脸、清晰五官 | 多人/侧脸/无脸保护 |
| depth / bokeh | 近中远层次明显 | 平面、低纹理保护 |
| denoise / deblur / details | 高 ISO 或运动模糊 | 干净低噪/细纹理保护 |
| color / LUT / toning | 色彩丰富、灰阶完整 | 低饱和/高光暗部边界 |
| clone / erase / dodge-burn | 明确目标和背景纹理 | 边缘、重复纹理、保护区 |
| grain / glow / fog / radiance | 明暗结构丰富 | 平坦区域与高光保护 |
| crop | 明确水平线和主体 | 非标准比例与旋转 EXIF |

每个输入记录 provenance、许可、相对路径、SHA-256、尺寸、颜色空间和选择理由。禁止新增绝对路径到运行合同。

### 7.3 参数矩阵

- 通用正向连续量：`0/0.25/0.4/0.5/0.75/1`；
- 支持负值：增加 `-1/-0.5`；
- 开关/枚举：每个活动值至少一条；
- brush：半径、柔和度、强度、规范化路径、source/target；
- asset：固定 asset 完成 amount 曲线，再换一个合法 asset 做保护验证；
- Crop：六个单变量合同 + 一次组合 roundtrip；
- Sky Replace：geometry、horizon、offset、rotation、edge、relight 和颜色子参数分别单变量验证。

### 7.4 批次顺序

1. P2-A：当前 13 个 effect failure 对应工具的 holdout/anchor；
2. P2-B：其余 10 个缺 amount anchor 工具；
3. P2-C：Crop 六参数；
4. P2-D：其余已通过工具补齐 holdout；
5. P2-E：真实 `.lnpc` provenance 和 Native preset observation。

单条 queue 示例：

```bash
.venv/bin/python scripts/build_effect_calibration_queue.py \
  --capability sky_replace \
  --input test_data/parity/inputs/summer-outdoor/<frozen-holdout>.jpg \
  --parameters '{"amount":0.5,"opacity":1.0}' \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r14-sky-replace-holdout-a.json \
  --audit-output test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r14-sky-replace-holdout-a-audit.json

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r14-sky-replace-holdout-a.json \
  --preflight

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/r14-sky-replace-holdout-a.json \
  --allow-ui-control
```

`<frozen-holdout>` 必须替换为 P2.2 冻结的真实相对路径，不能原样运行。

每批完成后：

```bash
.venv/bin/python scripts/reconcile_sampling_queue_state.py
.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/<r14-batch>.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/<r14-batch>-captures.json
.venv/bin/python scripts/validate_sampling_data_chain.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/queues/<r14-batch>.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/<r14-batch>-data-chain.json
.venv/bin/python scripts/validate_absolute_scope_coverage.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/scope-coverage-r14-after-<batch>.json
```

### 7.5 每条证据准出

- input/asset/parameters/readback/before/preview/export/fullscreen screenshot/AX hash 完整；
- source reset 和稳定等待可观察，`fixed_sleep=false`；
- 两次独立 export 一致，未复用旧 attempt 路径；
- zero identity 单独通过；非 zero 输出产生预期变化；
- source、全屏、版本、locale 任一错误即 invalid；
- pending/invalid/failed 不进入 active reference；
- scope 只能按新增证据预期下降。

P2 最终准出：scope 中 40 holdout、10 anchor、6 Crop 和 Native preset 缺口全部为 0。

## 8. P3：效果域逐项收敛到 40/40 和 69/69

### 8.1 修改边界

| 根因证据 | 允许修改 | 不允许修改 |
|---|---|---|
| 模型颜色/尺寸/归一化/输出语义 | `ai/model/<task>/` wrapper/contract | 在 pipeline 重复 preprocess |
| 模型输出正确、调用组合错误 | `ai/pipeline/`、execution graph | 把业务 blend 塞入 wrapper |
| mask/geometry/blend/relight 错误 | `image_ops/effects/`、compositor | case/hash/文件名特判 |
| loader/cache/release 错误 | `ai/model/loader.py`、backend | load 失败伪装 ready |
| 参数曲线错误 | 对应效果参数映射 | 为单个 reference 添加常数表 |

先保存 intermediate，再决定修改层。intermediate 至少包含模型原输出、规范化 mask/depth/landmark、geometry、
blend 前后图和最终色彩空间。P2 对应工具没有 canonical + holdout A/B 时，禁止提交算法修改。

### 8.2 固定效果顺序

1. **Sky Replace + Blue Hour**：sky probability、horizon、edge、foreground、highlight mask；随后 geometry、
   relight、temperature/saturation。覆盖开放天空、细枝建筑、无天空保护。
2. **Sunrays**：光源、遮挡、ray density、falloff、core、bloom；先结构后颜色，关闭 0.4/1.0。
3. **Depth Volume**：确认深度方向、尺度、分位数与近中远响应；禁止用 y 坐标假装深度。
4. **Face AI**：face box、landmark、skin/eye/hair edge；先区域后强度，并验证多人、侧脸、无脸保护。
5. **Structure AI / AI Enhance / Landscape Enhancer**：分离频段、tone/detail、sky/foliage/foreground 响应，
   验证完整 amount 曲线。
6. 以上失败关闭后，再对其余 35 个已通过主工具跑新 holdout，发现回归时按工具域局部处理。

### 8.3 单次修复循环

1. 用当前 failure 写 targeted test；
2. 记录根因假设和允许修改文件；
3. 生成 before intermediate 和指标；
4. 只改一个根因；
5. 依次运行 unit → canonical → holdout A → holdout B → amount curve → 同域 → 主 40 → Exact 69；
6. 保存 after intermediate 和全量 delta；
7. 任一保护条件失败即撤销该次算法修改，保留诊断 artifact。

```bash
ZPIXEL_TARGET_RUN=r14-sky-replace-01
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

### 8.4 守护条件

- zero 必须恒等；
- 参数曲线不能出现未被 Native 证据支持的跳变；
- preview/export 使用同一执行图；
- canonical 和两个 holdout 全部过现有阈值；
- 已通过 case、模型 invocation、加载释放不回归；
- 不读取 case id、输入路径、文件名或任何 reference hash；
- Face AI 只差很小数值也不能放宽 `MAE 0.03`。

P3 准出：主效果 40/40、Exact 69/69、全部新增 holdout/anchor 通过，无 pending/invalid。

## 9. P4：交互、预设和多图收敛到 10/10

### 9.1 真实 preset collection

只接受 Luminar 生成或原生接受、provenance 与 SHA-256 完整的真实 `.lnpc`。录制 import → visible →
preview → apply → restart persistence。根据真实容器只实现当前格式；不把 `.lnp` 当作 `.lnpc` fallback，
不做双格式兼容。取得真值后同步把 `configs/parity/interaction-contracts.json` 中 preset 合同的
`fixture_file` 从当前泛化占位标识改为冻结的 `.lnpc` fixture id/hash，并增加合同测试；无真实文件时
preset 保持 blocked。

### 9.2 Browser recorder 收敛

扩展 `frontend/scripts/capture-interaction-dpr2.mjs`，从当前只支持多图扩展到全部 10 个合同：目录照片右键、
目录文件夹右键/滚动、工具/Crop、照片切换/历史、preset、图层、遮罩、compare/zoom/pan、多图、导出。

每个合同必须记录：事件序列、可见断言、API 断言、可观察等待、screenshot、DOM、AX、network、console、
trace、API/project readback、preview/export hash、frontend build、browser/version、fixture fingerprint。
Browser 文件输入继续使用 DOM/CDP，不打开系统 chooser，不使用共享鼠标键盘。

实现顺序：

1. 先用一个旧合同增加失败测试，确保 stale build、DPR、physical viewport 或缺 readback 时 blocked；
2. P4-A 先让 10 项在开发 fixture 上全部 smoke 通过，但不发布最终 formal evidence；
3. P5 完成 UI 修改并冻结 frontend build 后进入 P4-B，从空 evidence 目录重录现有 8 项、多图和 preset；
4. 生成单一 10 项汇总，删除对旧 Browser evidence 的活动引用，不保留兼容读取。

```bash
node frontend/scripts/capture-interaction-dpr2.mjs \
  --contracts configs/parity/interaction-contracts.json \
  --fixture test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r14.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-r14 \
  --raw-output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw-r14.json

.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw-r14.json \
  --evidence-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-r14 \
  --native-root test_data/outputs/luminar-1.28.0-23071/observations/interactions \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution-r14.json

.venv/bin/python scripts/validate_interaction_execution.py \
  --execution test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution-r14.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-r14.json
```

### 9.3 Native 10 项

Native observation 必须同 contract id、同初始 fixture 语义、同可观察状态。仅在 P1 通过后执行：

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --contract-id preset-import-preview-apply --allow-ui-control
.venv/bin/python scripts/validate_interaction_execution.py --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-r14.json
```

P4-A 准出：recorder、preset/多图/图层/遮罩等候选功能和 10 项 smoke 全部通过。P4-B 只能在 P5 frontend
build 冻结后执行；最终准出为 Native 10/10、Browser 10/10、issue 0，10 项都属于同一
source/frontend/fixture 合同；三类多图分别验证输入顺序、处理中、完成态、preview、export、持久化和
重新打开。P5 之后若再改 frontend，P4-B 必须全部重录。

## 10. P5：UI 16/16 像素收敛

### 10.1 不可变证据合同

继续使用 `configs/parity/ui-regions.json`。完整 screenshot、DOM、AX、region、DPR、viewport、locale、timezone、
fixture 和 frontend build hash 都必须存在。任何 frontend hash 变化都让此前 16 项 candidate/evidence stale，
必须全部重录。

### 10.2 修复分组与顺序

R13 16 项全部失败。按共享根因而不是按截图逐张打补丁：

1. **U0 数据/状态真实性**：catalog、presets、denoise 选择、多图完成内容、缩略图、计数、文件名和顺序；
2. **U1 全局渲染 token**：字体文件、字重、行高、图标、颜色、border、shadow、scrollbar；
3. **U2 shell/几何**：顶栏、侧栏、工具栏、canvas fit、zoom、crop、panel 宽度；
4. **U3 编辑面板族**：edit、collapsed、history、tool-expanded、layers、masks、more、info、B&W；
5. **U4 结构性页面**：catalog、presets、export dialog、multi-image loading/complete；
6. **U5 亚像素收尾**：仅在共享结构正确后处理 text baseline、icon alignment 和 1px 边界。

优先修复结构性差异：R13 `export-dialog` changed ratio 约 0.997，catalog 约 0.748，多图约 0.720，
不能靠颜色微调解决。`edit`/`info`/`edit-collapsed` MAE 已接近 0.03，但 changed ratio 仍约 0.28–0.32，
应检查字体渲染、图标和整体 1–2px 几何，而不是降低 changed-pixel 阈值。

### 10.3 单次 UI 循环

1. 根据 diff heatmap/DOM/AX 选一个共享根因；
2. 先写组件或状态测试；
3. 修改最小共享 CSS/component/fixture；
4. targeted state 改善后重录全部 16 状态；
5. 比较 per-state MAE、changed ratio 和 full-screen diagnostic；
6. 任一已改善状态回归则撤销该次修改；
7. 不为单状态增加无 Native 结构依据的 CSS 分支。

```bash
.venv/bin/python scripts/prepare_ui_evidence_fixture.py \
  --data-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-workspace-r14 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r14.json

node frontend/scripts/capture-ui-dpr2.mjs \
  --plan test_data/parity/ui-browser-capture-plan.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-r14 \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r14 \
  --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

.venv/bin/python scripts/build_ui_browser_execution.py \
  --fixture-manifest test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-evidence-fixture-r14.json \
  --source-captures test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-r14 \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r14 \
  --regions configs/parity/ui-regions.json \
  --browser "Google Chrome Headless" --browser-version <captured-browser-version> \
  --capture-engine chrome-cdp-page-capture-screenshot \
  --logical-width 1440 --logical-height 900 --device-scale-factor 2 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution-r14.json

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --execution test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution-r14.json \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r14 \
  --regions configs/parity/ui-regions.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-r14.json

.venv/bin/python scripts/validate_ui_references.py \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-r14 \
  --regions configs/parity/ui-regions.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-r14.json
```

`<captured-browser-version>` 必须来自本轮 `capture-run.json`，不能手填旧版本。

P5 准出：16/16 evidence、16/16 pixel；每项 MAE 与 changed ratio 都通过原阈值；full-screen diagnostic
保留；region hash 未变化。

## 11. P6：Native 持久化单轨

### 11.1 已完成部分

catalog 已与真实 Native schema 完全一致：schema 155、29 objects、26 tables、structure hash
`af8a747826542f67922bab359d4c9567fee7739fc5aaf430e8bb1132dc96c86b`，无 catalog JSON、dual write 或
compatibility layer。该结构只做守护，不再次设计 schema。

### 11.2 未完成部分

当前仍有 46 个 project JSON、4 个 workflow session JSON、本地 preset index，以及 project/layer/mask/history
JSON primary 与 SQLite history projection 两种表示。核心目标是确定 Native 的真实状态映射后一次性单轨化。

### 11.3 Native delta 实验

在 P1 隔离 disposable workspace 中依次执行，每次只做一个状态变化：

1. 新建 project；
2. 增加/删除 edit；
3. undo/redo；
4. 新建/排序/隐藏/删除 layer；
5. 新建/undo/redo/reset mask；
6. 创建 HDR/Focus/Panorama workflow；
7. 导入、应用、重启后读取 preset。

每步关闭 Luminar 后，以只读 immutable 模式记录数据库文件、WAL/SHM、资源文件、mtime、size、SHA-256、
表级 row count 和变更行。新增一个最小工具 `scripts/capture_native_persistence_delta.py` 及单元测试；该工具
只读取两个冻结 snapshot，输出结构/行/资源差异，不写 Native catalog、不解释未知 blob。

随后对 `img_history_states.data_wide_ch`、资源 linkage 和 workflow/preset 记录建立字段映射。每个映射必须有
Native state → serialized state → project reload → preview/export hash 的 roundtrip 证据。

### 11.4 一次性切换规则

- 映射未证明前不删除现有数据，也不增加猜测性字段；
- 映射证明后，直接把 active repository 切到 Native 对应 store；
- 删除 JSON primary repository、serializer、配置、活动测试 fixture 和 SQLite 重复 projection；
- 不保留读旧写新、双写、格式探测、旧 schema reader 或 runtime migration；
- disposable/test workspace 直接按新结构重建，不把历史兼容逻辑带入产品运行时；
- restart 后 project/layer/mask/history/workflow/preset 全部可读，preview/export hash 不变。

### 11.5 把已知遗漏纳入 required gate

新增 `scripts/validate_native_persistence_roundtrip.py` 和对应单元测试，读取 P6 的冻结 mapping/roundtrip
manifest，验证 Native provenance、每类状态 roundtrip、active repository 清单、restart/output hash，以及
不存在 JSON primary、重复 projection、dual write、old reader 或 runtime migration。随后在
`scripts/run_quality_gates.py` 注册 `native-persistence-roundtrip` 为 exact required gate。

R13 当前 36 个 gate 没有独立覆盖这一已知阻塞；R14 加入后最终分母为 37。gate 增加必须由
`tests/test_quality_gates.py` 固定顺序、required 属性和 fail-closed 行为，不能用修改现有 passed gate 的语义
来隐藏新增责任。

```bash
.venv/bin/python scripts/validate_luminar_catalog_schema.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/luminar-catalog-schema-r14.json
```

P6 准出：Native delta 和 roundtrip 完整；active workspace 不再包含上述 JSON primary 或重复 projection；
无兼容层；restart、undo/redo、多图、preset 和导出全部通过；第 37 个 required gate 为 passed。

## 12. P7：模型、性能和全量回归守护

模型当前已经通过，默认只守护。只有 P3 intermediate 证明颜色顺序、resize、normalization、tensor layout、
输出范围或 postprocess 错误时才改 `ai/model`；geometry、blend、relight 继续留在 pipeline/effect 层。

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-r14.json
.venv/bin/python scripts/audit_candidate_model_invocations.py --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-runtime-audit-r14.json
.venv/bin/ruff check .
.venv/bin/pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

守护时机：R14 开始；每个 model-backed 效果域完成后；P4/P5/P6 合并后；P8 前。模型要求继续为 22/22、
0 pending、18/18 invocation。ONNX primary；OpenVINO 仅限同逻辑模型且 backend parity 已验证的 fallback；
不隐式联网，不把 load 失败写入缓存，淘汰必须调用 `unload_model()`。

性能不得通过降低分辨率、跳过模型或改为近似算法换取。若性能 gate 回归，先定位重复加载、无界缓存、
不必要复制和并发，不改变输出语义。

## 13. P8：单轮 exact 37/37

P2–P7 全部准出且第 37 个 persistence gate 已进入 dry-run 后才运行：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --run-id alignment-r14-single-final-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-single-final.json
```

同时重建 R14 final worklist。准出必须满足：37/37、scope 0、worklist 0、40/40、69/69、UI 16/16、
Native/Browser 10/10、模型/SQLite/persistence/sampling/export 全绿、pending/invalid/failed evidence 为 0、
release fingerprint 完整。任一 required failure 非零，停止并回到拥有该 failure 的唯一阶段，不运行 P9。

## 14. P9：同指纹 A/B 两轮

冻结 source、models、reference、fixture、Native observation、region、字体、frontend、Python/Node/browser 和
environment。A/B 使用不同 run 目录，从头生成 candidate，不复用输出。

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --run-id alignment-r14-release-a-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-release-a.json
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --run-id alignment-r14-release-b-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-release-b.json
.venv/bin/python scripts/compare_exact_runs.py \
  --first test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-release-a.json \
  --second test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r14-release-b.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-r14-release-comparison.json
```

两轮都必须 37/37，且 source/model/reference/validation/environment/fixture/frontend/region/release fingerprint
完全一致。A 通过、B 失败即 nondeterministic blocked；定位随机种子、线程、backend、缓存、字体、文件排序
和硬件差异，不运行第三轮碰运气。

## 15. 修改与验证矩阵

| 修改类型 | 最小验证 | 域回归 | 最终门禁 |
|---|---|---|---|
| reference/evidence | 单 record validator | batch data-chain + scope delta | exact 37 |
| deterministic effect | helper/unit + targeted | canonical + holdout A/B + 主/Exact | exact 37 |
| model-backed pipeline | intermediate + targeted | 同域 + invocation + 全效果 | exact 37 |
| `ai/model` wrapper | model validator + wrapper test | contract/backend/invocation | exact 37 |
| preset parser/service | provenance + parser + restart | Native/Browser preset | exact 37 |
| interaction recorder | 单合同 raw/evidence | 同 build 10/10 | exact 37 |
| UI/CSS/component | component + targeted state | current-build 16 状态 | exact 37 |
| persistence | delta parser + roundtrip | restart/history/layer/mask/workflow | exact 37 |
| catalog schema | Native RO validator | service/restart | exact 37 |
| evidence builder | malformed artifact tests | 全量重录 | exact 37 |

每次修改只触碰与根因直接相关的文件。发现相邻问题时记录到 worklist，不顺手做无关重构。

## 16. 停止、回退和阻塞规则

立即停止当前方向：

- 需要降低 MAE、SSIM、changed-pixel 或 artifact 完整性阈值；
- 需要 case id、文件名、source/reference hash 或 fixture 特判；
- canonical 改善但 holdout、zero、preview/export 或已通过 case 回归；
- 需要拼接不同 build、fixture、browser 或 region hash 的 evidence；
- 看过 candidate failure 后修改 UI region；
- Luminar 非全屏、输入未隔离或即将影响用户外设；
- preset 不是来源可信的真实 `.lnpc`；
- 需要旧 preset/schema/model reader、JSON catalog 或 JSON/SQLite 双写；
- model load 失败却伪装 ready；
- 单轮 exact 未达到 37/37 却运行 A/B 或声明完成。

回退单位是当前最小根因补丁；保留失败 diagnostic，恢复修改前候选实现，不覆盖 Native/R13 reference，
不修改用户无关文件。阻塞时继续能独立推进的 Browser-safe 或只读诊断，但报告必须保留 blocked。

## 17. 最终遗漏审计

Release B 后逐项回答，必须全部为“否”：

1. 是否有 in-scope 工具或参数未进入合同？
2. 是否有工具少于 canonical + 两个不同 source？
3. 是否有 amount/negative/enum/brush/asset/geometry 状态未覆盖？
4. 是否有 preview 通过而 export 未通过或不稳定？
5. 是否有 current-build UI 缺 screenshot、DOM、AX、region、fixture、build hash？
6. 是否有 in-scope UI 区域在看到差异后被排除？
7. 是否有 Native 或 Browser interaction 缺事件、断言、持久化、输出 hash？
8. 是否有 10 个合同来自不同 frontend/fixture 汇总？
9. 是否有活动模型 contract pending 或 model-backed case 未真实调用？
10. 是否有项目状态仍使用 JSON primary、双写或重复 projection？
11. 是否存在旧 schema/model/preset reader、fallback 或 runtime migration？
12. 是否把付费、账户、商店、云、教程、帮助、推广计入完成分母？
13. 是否有 pending/invalid/failed evidence 被人工改成 passed？
14. 是否有命令依赖共享鼠标键盘、系统 chooser 或非全屏 Luminar？
15. 是否有 scope/worklist 项未关闭或分母变化未审计？
16. 是否有 A/B 指纹、输出或 gate 结果不一致？

## 18. 交付物清单

最终交付至少包含：

- R14 baseline/final scope 与 worklist；
- Native isolation preflight；
- 新 holdout/anchor/Crop/preset queue、capture、data-chain 和 provenance；
- 每个失败效果域的 before/after intermediate 与 parity delta；
- Native/Browser interaction 10/10 raw、evidence 和汇总；
- current-build UI 16/16 capture、DOM、AX、region、execution 和 pixel 报告；
- Native persistence delta、字段映射、roundtrip 和单轨审计；
- model contract/runtime、Ruff、Python、Frontend、build、performance 报告；
- P8 单轮 exact 37/37；
- P9 A/B 两轮 37/37 和指纹比较；
- R14 执行前后对比、遗漏审计和最终声明范围。

只有上述交付物全部存在且机器门禁全绿，才能声明：在本机 Luminar Neo `1.28.0 (23071)`、固定素材、
固定模型、固定环境和本文明确的免费本地核心范围内，zpixel_edit 已达到可复现的严格对齐。
