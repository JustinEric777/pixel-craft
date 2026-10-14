# Luminar Neo 1.28 本地核心严格对齐可执行优化计划

> 本文保留完整阶段设计。最新执行状态已更新为 `execution-plan-after-20260829` 的正式 `29/34 exact gate`；该 run 的 lint 已在运行后修复并单独复验，当前仍有 4 个产品门禁失败。实际结果、遗漏和剩余顺序以 [2026-08-29 执行报告](absolute-parity-execution-report-2026-08-29.md) 为准。范围只覆盖免费、离线、可重复验证的本地核心能力；付费、升级、教程、帮助、账号、商店、云生成和商业内容均不实现、不采样、不进入 required gate。

## 目录

- [1. 目标和完成定义](#1-目标和完成定义)
- [2. 当前基线](#2-当前基线)
- [3. 硬约束](#3-硬约束)
- [4. 总体依赖顺序](#4-总体依赖顺序)
- [5. P0：冻结范围和执行环境](#5-p0冻结范围和执行环境)
- [6. P1：Native 全屏观察和 Browser dry-run](#6-p1native-全屏观察和-browser-dry-run)
- [7. P2：活动模型合同收敛](#7-p2活动模型合同收敛)
- [8. P3：主效果 40/40](#8-p3主效果-4040)
- [9. P4：扩展 Exact 69/69](#9-p4扩展-exact-6969)
- [10. P5：交互实现 10/10](#10-p5交互实现-1010)
- [11. P6：UI 像素 16/16](#11-p6ui-像素-1616)
- [12. P7：正式 Browser/Native 10/10](#12-p7正式-browsernative-1010)
- [13. P8：移除历史兼容入口](#13-p8移除历史兼容入口)
- [14. P9：连续两轮 exact 发布门禁](#14-p9连续两轮-exact-发布门禁)
- [15. 测试分层和回归频率](#15-测试分层和回归频率)
- [16. 排期和任务拆分](#16-排期和任务拆分)
- [17. 缺陷记录模板](#17-缺陷记录模板)
- [18. 最终验收清单](#18-最终验收清单)

---

## 1. 目标和完成定义

### 1.1 唯一目标

在以下冻结条件下，相同输入、参数、素材、事件顺序和导出配置必须得到预定义门禁内不可区分的可观察结果：

| 项目 | 固定值 |
|---|---|
| 原生应用 | Luminar Neo `1.28.0 (23071)` |
| Bundle ID | `com.skylum.luminarneo` |
| 平台 | macOS |
| 语言 | `zh-Hans` |
| 时区 | `Asia/Shanghai` |
| 原生采样状态 | macOS 全屏 |
| Browser 逻辑 viewport | `1440x900` |
| UI 物理 viewport | `2880x1800`，DPR 2 |
| 主运行时 | ONNX Runtime |
| 兜底运行时 | 通过同一模型合同验证的 OpenVINO IR |
| 主效果阈值 | `SSIM >= 0.98`、`MAE <= 0.03` |
| UI 阈值 | `MAE <= 0.03`、changed pixel ratio `<= 0.02` |

### 1.2 完成定义

只有以下条件同时满足，才允许声明“冻结的本地核心合同与本机 Luminar Neo 严格对齐”：

1. 模型结构和 model-specific contract 全部通过，pending=0；
2. 主效果 40/40；
3. 扩展 Exact 69/69；
4. UI evidence 16/16 且 UI pixel 16/16；
5. Native observation 10/10；
6. Browser execution 10/10；
7. HDR、Focus Stacking、Panorama 3/3；
8. preview/export、尺寸、颜色配置和 hash 全部通过，并且 catalog 持久化已按真实 Native schema 单轨实现；
9. 连续两个 exact run 都是 required failure=0；
10. 两轮 source、model、validation、environment、reference fingerprint 完全相同。

### 1.3 不在范围内

- 付费或升级入口；
- 教程、帮助、引导页；
- 账号、订阅、商店、Marketplace；
- 依赖 Skylum 云端的生成式服务；
- 历史 Luminar 版本；
- JSON catalog、旧 schema、双写、catalog/storage fallback 或旧交互合同兼容层。

这些功能不应以 disabled 按钮、伪响应或空实现进入 required 流程。若原生 UI 的占位元素影响整体几何，只允许保留无业务行为的视觉占位，并在 UI fixture 中明确标记。

### 1.4 声明边界

本文中的“严格/绝对对齐”是工程验收声明：在冻结版本、平台、语言、素材、参数、事件、viewport、模型和 reference 范围内，全部 required gate 连续两轮通过。它不表示对未采样输入、排除功能、其他 Luminar 版本或其他操作系统作无限外推，也不把 `MAE/SSIM` 门禁偷换成数学意义上的逐字节恒等。

## 2. 当前基线

权威 run：`execution-plan-after-20260829`。

权威汇总：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/execution-plan-after-20260829/quality-gates-exact.json`。

| 域 | 当前 | 目标 | 状态 |
|---|---:|---:|---|
| Exact gate | 29/34 | 34/34 | blocked |
| 活跃模型结构 | 22/22 | 所有活动调用路径 | passed |
| model-specific | 22/22 | 22/22 | passed |
| 模型 pending | 0 | 0 | passed |
| runtime-ready | 22/22 | 所有活动调用路径 ready | passed |
| OpenVINO IR | 41 ready、1 retired、0 failed | 活动 fallback 全部 ready | passed |
| 主效果候选生成 | 40/40、failed=0 | 40/40、failed=0 | passed |
| 主效果 | 33/40 | 40/40 | blocked |
| 扩展候选生成 | 69/69、failed=0 | 69/69、failed=0 | passed |
| 扩展 Exact | 41/69 | 69/69 | blocked |
| UI current-build evidence | 16/16、原生 DPR 2、issue=0 | 16/16、issue=0 | passed |
| UI pixel | 0/16 | 16/16 | blocked |
| Native v2 | 8/10 | 10/10 | blocked |
| Browser v2 | 8/10 | 10/10 | blocked |
| Sky E2E | 48/48 | 48/48 | passed |
| Overlay E2E | 38/38 | 38/38 | passed |
| 多图工作流 | 3/3 | 3/3 | passed |
| Python | 本轮相关 31/31、Ruff passed | 不回退 | passed |
| Frontend | 41/41 + build | 不回退 | passed |

当前 4 个产品 required 失败域：

- `output-parity`；
- `exact-incremental-parity`；
- `ui-parity`；
- `interaction-execution`。

最新正式 run 还记录了一个 `python-lint` 失败，已在 run 后通过 import 排序修复并由 `ruff check .` 复验；完整 exact 尚未为这项纯测试导入顺序修改重跑，因此不手工改写正式汇总数。

最新正式 run 记录的 source fingerprint 为 `2eafd0265c2fd9703139d18b6bf45f0707253b09edd56d11d63c8057d2fc30f2`。本计划文档和后续实现发生变化后，必须生成新 fingerprint 和新 run，不得把该值继续标成当前源码 fingerprint，也不得覆盖既有证据。

## 3. 硬约束

### 3.1 证据约束

1. Luminar Native 采样前必须验证应用处于 macOS 全屏；窗口化、被系统对话框遮挡或其他应用覆盖的截图一律作废。
2. 每个原生观察必须绑定 app version、build、bundle id、locale、viewport、fixture hash 和事件列表。
3. canonical reference 默认只读。候选失败不是重新采样 reference 的理由。
4. 只有 reference 缺证据、输入 hash 错误或原生导出被证明不稳定时，才允许登记原因后重采。
5. frontend build hash 变化后，全部 UI 16 和正式 Browser 10 evidence 作废。
6. 模型、输入、reference、素材或 comparator 变化后，相关候选全部重新生成。

### 3.2 实现约束

1. 不降低 `configs/parity.yaml` 中 MAE、SSIM 和 changed-pixel-ratio 阈值。
2. 不读取 case ID、失败列表、reference 文件名或 reference hash 选择算法。
3. 不用最终 resize、原图回退、全零 mask、固定输出或 fixture 特判制造通过。
4. ONNX 可用时优先 ONNX；IR 只在 ONNX 不可用且 IR 自身 contract 通过时接管。
5. smoke、signature valid、finite output 或 IR ready 不能代替 model-specific validated。
6. 不删除仍由产品路径调用的模型来缩小 pending 数量。
7. 不新增 JSON catalog、SQLite 双写或历史 schema 适配器。

### 3.3 合并约束

每个变更批次必须具备：

- 一个明确根因；
- calibration fixture；
- 至少一个独立 holdout；
- 窄范围测试；
- 受影响的全量 parity 回归；
- 回退判断；
- 新证据路径。

## 4. 总体依赖顺序

```text
P0 冻结范围和环境
 │
 ▼
P1 Native 全屏观察 + Browser dry-run
 │            只发现行为差距，不发布正式 Browser evidence
 ▼
P2 活动模型合同 22/22（已完成，持续回归）
 │
 ▼
P3 主效果 33/40 → 40/40
 │
 ▼
P4 扩展 Exact 41/69 → 69/69
 │
 ▼
P5 交互实现 dry-run 10/10
 │
 ▼
P6 UI pixel 0/16 → 16/16，冻结 frontend hash
 │
 ▼
P7 正式 Native/Browser 10/10
 │
 ▼
P8 删除一次性兼容/迁移入口
 │
 ▼
P9 identical-fingerprint exact A/B
```

Native observation 可在前期完成，因为它不依赖项目源码。正式 Browser evidence 必须在 UI 和行为全部冻结后生成，以免重复作废。

### 4.1 阶段门禁矩阵

| 阶段 | 必需输入 | 交付物 | 进入下一阶段的硬条件 | 失败时动作 |
|---|---|---|---|---|
| P0 | v4 summary、配置、素材和 reference | 冻结 manifest、scope 清单 | fingerprint 可复算、排除项不在 required scope | 修正配置，不进入采样 |
| P1 | v2 contracts、全屏 Luminar、Browser preflight | 补齐 2 条 Native observations、Browser gap backlog | Native 10/10；阻断必须有正式记录 | 不生成伪 evidence |
| P2 | 活动模型清单、调用 trace、runtime probe | 22/22 活动合同和退役处置表 | exact pending=0，模型门禁不回退 | 回退时立即阻断效果校准 |
| P3 | 已验证模型、中间产物、40 个 reference | 40 个候选、根因报告 | 40/40、candidate failed=0 | 回退本批修复并重新定位根因 |
| P4 | P3 通过、69 个 exact case | 参数/素材 holdout 报告 | 69/69、pending=0 | 不进入交互/UI 发布阶段 |
| P5 | Native 行为合同、Browser gap | 功能代码和自动化测试 | dry-run 10/10 | 修复行为，不发布正式证据 |
| P6 | 当前 frontend build、16 个 reference | 16 份 hash-linked evidence 和 diff | evidence 16/16、pixel 16/16 | 修改 UI 后全量重录 16 状态 |
| P7 | 冻结 frontend hash、Native 10/10 | Browser raw/execution/validation | Browser 10/10、issue=0 | 策略阻断则保持 blocked |
| P8 | 真实 Native catalog schema、所有活动 catalog 引用 | Native schema 单轨实现和无兼容入口审计 | 仅真实 schema、无项目旧 schema/迁移/双写/v1 路径 | 未取得 Native schema 时保持 exact blocked |
| P9 | 单轮 exact 已 34/34 | exact A、B、comparison | 两轮 required failure=0 且 fingerprint 相同 | 停止发布声明 |

### 4.2 从当前状态开始的执行包

| 包 | 优先级 | 依赖 | 工作内容 | 可验收输出 | 完成条件 |
|---|---:|---|---|---|---|
| R0 | P0 | 无 | 固化最新失败清单，重跑 lint、相关测试和 frontend build | 新 baseline run、失败 case 清单 | 工具链全绿，产品失败数可复算 |
| R1 | P0 | Luminar 可正常操作、真实 fixture | 全屏补采 Preset 和 Multi-image Native 证据 | 2 份 Native observation、AX、截图、事件和 hash | Native 10/10；阻塞则有 fail-closed 记录 |
| R2 | P0 | R0、活动模型门禁持续通过 | 校准 `face_ai`、`magic_lights`、depth 和天空/大气共享链 | 中间产物 diff、calibration/holdout、40-case 报告 | 主效果 40/40 |
| R3 | P1 | R2 | 按共享根因关闭剩余 28 个扩展失败 | 69-case 报告、受益/回退列表 | 扩展 69/69，主效果不回退 |
| R4 | P0 | 当前 DPR 2 reference | 先修全局 shell，再修 16 个页面状态 | 每批 16-state raw/DOM/AX/diff | UI evidence 16/16 且 pixel 16/16 |
| R5 | P1 | R1、行为实现稳定 | 补齐 Preset/Multi-image 功能并完成 10-contract dry-run | 10 条可重复事件 trace | dry-run 10/10、持久化和输出一致 |
| R6 | P1 | R4、R5、frontend 冻结 | 全量重录正式 Browser 10/10，不复用旧 8 条 | Browser raw/execution/validation | 10/10、issue=0、同一 frontend hash |
| R7 | P2 | 获得真实 Native catalog schema | 一次性替换项目 catalog schema；未获得时只审计 | schema diff、round-trip、单轨实现 | 无 JSON、双写、旧 schema 或 fallback |
| R8 | P0 | R1–R7 全部通过 | 新 exact 预检，然后同 fingerprint 连续 A/B | 两个 immutable run 和 comparison | 两轮 34/34、required failure=0 |

R2 和 R4 可以在不同工作分支或不重叠文件批次并行推进；R3 必须等待 R2，R6 必须等待 R4/R5 和 frontend hash 冻结，R8 必须等待所有域清零。任何阶段修改 reference、阈值或 case 集合，都回到 R0 重新冻结，不允许沿用旧 run 的通过结论。

## 5. P0：冻结范围和执行环境

### 5.1 工作项

1. 以 `configs/reference.yaml` 和 `configs/parity.yaml` 为唯一版本、素材、case 和阈值入口。
2. 记录当前 source、model、validation、environment fingerprint。
3. 固定 UI fixture root、catalog SQLite、预设素材和三类多图输入。
4. 确认 required scope 中不存在付费、教程、帮助、账号或商店功能。
5. 为每一阶段建立不可覆盖 run id，禁止写回另一个 run 的报告。

### 5.2 修改入口

| 目标 | 路径 |
|---|---|
| 版本和 reference | `configs/reference.yaml` |
| 阈值、fixture、UI state | `configs/parity.yaml` |
| 产品能力范围 | `configs/capabilities/registry.json`、`configs/capabilities/policy.json` |
| 指纹 | `scripts/build_source_manifest.py`、`scripts/build_release_fingerprint.py` |
| 综合门禁 | `scripts/run_quality_gates.py` |

### 5.3 准出条件

- fingerprint 报告 `status=passed`；
- scope audit 不包含排除功能；
- fixture 和 reference 全部可复算 hash；
- 新 run 不覆盖既有 run。

## 6. P1：Native 全屏观察和 Browser dry-run

当前 v2 交互合同的 Native 正式证据和 Browser 执行均为 8/10。缺口集中在 `preset-import-preview-apply` 和 `multi-image-three-workflows`；已有 8 条 Browser 证据还存在 viewport 不匹配和 frontend build 过期问题，最终必须在 frontend 冻结后全量重录。历史 v1 observation 不允许通过 ID 映射或字段补写复用。

### 6.1 采样前置检查

1. Native：确认实际 Luminar Neo 处于 macOS 全屏、版本/build/locale 正确，没有系统弹窗或其他窗口覆盖。
2. 输入设备：当前未发现可与用户真实显示器、鼠标完全隔离的虚拟屏幕/虚拟鼠标环境，因此保持现有 Computer Use 路径，不切换显示器、不改变分辨率、不占用用户外设；只有用户明确允许且隔离能力被验证后才启用虚拟输入。
3. Browser：功能调试优先使用应用内 Browser；正式无外设 UI 采集使用仓库现有的独立 headless Chrome CDP runner，并绑定 Chrome 版本、DPR、viewport、DOM、AX、截图和 frontend hash。若本地服务或安全策略阻断，记录 `blocked`，不得降低浏览器安全策略或伪造执行记录。
4. Fixture：Native 与 Browser 都从合同指定的独立初态开始；未确认 reset 成功时不得继续。

### 6.2 Native 采样协议

每个合同执行前：

1. 使用 Computer Use 读取 Luminar Neo app state；
2. 确认全屏、版本 `1.28.0`、build `23071`、`zh-Hans`；
3. 关闭菜单、弹窗和系统文件选择器；
4. 载入合同指定 fixture 并恢复无编辑初态；
5. 保存 before screenshot 和 AX；
6. 优先使用当次 AX tree 的 element index 执行；每次动作后重新读取 app state，禁止复用旧 element index；AX 不完整时才退回截图坐标；
7. 按合同事件顺序执行，等待只绑定可见/AX/导出/持久化状态，不用固定 sleep 作为成功条件；
8. 保存 after screenshot、AX、fixture hash、等待条件和断言结果。

任何一步无法确认全屏，当前合同立即停止，不生成 observation。

### 6.3 10 个合同工作包

| 合同 | 事件数 | 当前主要风险 | Native 必查点 |
|---|---:|---|---|
| `catalog-photo-context-submenu` | 12 | 二级菜单、旋转、回收站 ID 稳定 | 父子菜单同时可见、恢复后 asset ID 不变 |
| `catalog-folder-context-scroll` | 8 | collection 归属、虚拟滚动 | 导入位置、到底/回顶、选择保持 |
| `edit-tool-expand-crop` | 9 | crop 坐标、旋转、输出尺寸 | 比例、拖框、应用后的画布和历史 |
| `photo-switch-history` | 10 | 两图 history 隔离 | A/B 切换、undo/redo 不串图 |
| `preset-import-preview-apply` | 8 | `.lnp` 索引和只应用一次 | 导入、预览、graph 顺序 |
| `layer-lifecycle` | 11 | 排序、blend、transform | preview/export 与 layer stack 一致 |
| `mask-lifecycle` | 10 | mask 数据、羽化、undo/redo | 反转、密度、删除和合成 |
| `compare-zoom-pan` | 8 | 视图状态污染项目 | 200%、pan、fit 后项目 hash 不变 |
| `multi-image-three-workflows` | 9 | 三分支输入顺序和导出 | HDR/Focus/Panorama 各自完成态 |
| `export-dialog-file` | 11 | 格式、尺寸、profile、重复导出 | 取消无输出、最终只有一个文件 |

### 6.4 Browser dry-run

Browser dry-run 只用于发现缺失行为，不发布正式 evidence：

- 每个合同从独立 SQLite/项目 fixture 开始；
- 对照 Native observation 执行同一事件；
- 记录 UI、API、持久化和输出差距；
- 缺失行为进入 P5；
- 不把 dry-run 截图写成正式 10/10。

### 6.5 执行命令

先对单个合同做无 UI 控制的预检，确认 contract、handler、fixture 和输出目录；再显式允许 UI 控制。不得在未检查 dry-run 输出时直接批量驱动 Native：

执行前把 `CONTRACT_ID` 替换为当前 v2 合同 ID。

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --contract-id CONTRACT_ID \
  --dry-run

.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --contract-id CONTRACT_ID \
  --allow-ui-control

.venv/bin/python scripts/validate_interaction_execution.py \
  --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/native-interaction-validation-next.json
```

### 6.6 验收

- 10 个 Native observation 文件均可通过 `--native-only` 校验；
- 每个 observation 的 events 与 v2 合同逐项相同；
- Browser dry-run 为每个失败生成可定位缺陷；
- 没有窗口化 Native 证据。

## 7. P2：活动模型合同收敛

> 执行状态：已完成。原 92 条库存记录经过消费者、执行图和产品调用 trace 审计后，22 条保留为活动模型并全部 model-specific validated；70 条冻结核心路径不可达的 artifact 已从活动 registry/config/graph 退役，没有保留 alias 或历史兼容入口。以下 92 行规则保留为审计依据，不再表示当前仍有 65 条 pending。

### 7.1 固定统计口径

模型报告提供的是不同审计视角，禁止相加或互相替代：

| 视角 | 当前值 | 用途 |
|---|---|---|
| exact validation matrix | 当前活动 22/22 validated、pending 0 | P2 已完成；旧 92 条用于验证退役处置证据 |
| runtime probe | 42 个 IR 中 41 ready、`convnextv2_multiclass` retired、0 failed | 只证明 IR 可执行性，不证明模型语义 |
| product scope | required-direct 26、required-transitive 12、inventory-unreachable 54 | 判断 UI/执行图的可达性 |
| consumer mapping | mapped 60、unmapped 32 | 发现缺消费者或缺映射记录 |
| source-map contract | model-specific 26、pending-model-specific 66 | source map 自己选择的 variant 视角 |
| required logical models | 22，pending=0、unresolved=0 | 冻结产品路径均可解析到活动模型 |

旧 source map 的 26/66 与旧 exact matrix 的 27/65 是不同审计视角。当前以活动 22/22、pending=0 和 70 条逐项退役证据为准，同时要求所有活动产品路径的 source-map gate 继续通过。

### 7.2 逐模型处置规则

每个 pending model 只能进入以下一种结论：

1. **Validated**：具备模型专用预处理、后处理、正/负/边界样本和真实调用 trace；
2. **Retired**：有静态来源、消费者和运行 trace 证据证明冻结的本地核心产品路径不可达，并从活动 registry、配置和执行图同时删除；
3. **Replaced**：主工件不可用，但活动 ONNX 替代工件完成相同语义合同；IR 仅作为已验证 fallback；
4. **Blocked**：证据不足，继续保持 exact gate 失败，不能用通用 smoke 标记完成。

按批次维护一个 92 行处置表，至少包含 artifact、wrapper、consumer、execution graph、runtime、contract、fixtures、trace、结论和证据路径。

### 7.3 批次 M0：活动产品路径和替代工件

先锁定 22 个 required logical model 及其 direct/transitive 变体，确认每个 UI 工具最终选择的实际 artifact、ONNX/IR 顺序和调用参数。所有活动替代工件必须有独立合同，不得借主工件的 validated 状态。

M0 准出：required logical models 仍为 pending=0、unresolved=0，且每条活动路径都能在 invocation report 中定位到实际工件。

### 7.4 批次 M1：当前失败效果的直接依赖

优先模型：

- `DepthAnythingV2SmallOpenVino`；
- `depth_map_i8` / `depth_map_i8_onnx`；
- `face_boxes_i8`；
- `face_landmarks_i8`；
- `eyes_detector_i8`；
- `IrisLandmarks`；
- `magic_lights_exp37_dataset123_1024`；
- sky/semantic segmentation 的活动替代模型。

必须补齐：

1. 输入尺寸、layout、dtype、RGB/BGR 和归一化；
2. letterbox/crop/pad 规则；
3. 输出 tensor 含义；
4. decode、NMS、坐标恢复、class map 或 depth 方向；
5. mask resize、threshold、feather；
6. 正样本、负样本、边界样本；
7. 真实产品调用 trace；
8. `BaseInference`/`InferenceResult` 输出语义、ONNX/IR 切换和资源释放测试；
9. `load_model()` 仅成功后设置 `_loaded=True`，`unload_model()` 释放 session/processor/tokenizer 并重置状态；
10. factory 动态导入子类校验、loader cache key/LRU/淘汰调用卸载，以及本地离线权重加载。

M1 准出：相关模型全部 `model-specific-validated`，且 `face_ai`、depth/sky/light 失败可以归因到效果层而非未知模型语义。

### 7.5 批次 M2：人像和分割族

覆盖：face part、skin、skin defect、hair、human、animal、transport、saliency、interactive segmentation。

共用验证集必须包含：

- 无人脸、单人脸、多人脸；
- 遮挡、侧脸、眼镜、暗光；
- 头发边缘、皮肤与背景相近颜色；
- 人体被裁切、衣物与背景粘连；
- 空 mask 和多目标 mask 负样本。

禁止为所有 segmentation 模型复用一个未经验证的 resize/threshold。

### 7.6 批次 M3：恢复和超分族

覆盖 12 个 super-resolution 以及 defocus、face restoration、RAW CFA/channel shift。

必须验证：

- x2/x4/x6 的实际倍率；
- tile size、overlap、padding、边缘融合；
- 输入/输出颜色范围；
- face enhancer 是否只作用 ROI；
- 奇数尺寸、小图、大图和透明通道；
- preview 与 export 的尺寸、profile 和像素一致性。

### 7.7 批次 M4：分类、embedding 和剩余工具模型

覆盖 image classification、text embedding、wire/dust/imperfection detection 等。

必须验证 tokenizer/label map、threshold、top-k、检测框坐标和空结果语义。未被本地核心功能调用的模型不能仅因文件存在而留在活动 registry。

### 7.8 批次 M5：IR fallback 审计

对 41 个 runtime-ready IR 逐一记录对应 ONNX 主工件、触发 fallback 的明确条件和同一 fixture 下的语义等价结果。`convnextv2_multiclass` 的非有限 IR 保持 retired，只允许合同通过的 ONNX 路径；禁止自动回退到输出形状相同但语义不同的模型。

### 7.9 修改入口

| 层 | 路径 | 职责 |
|---|---|---|
| 模型 wrapper | `ai/model/onnx/`、`ai/model/openvino/` | 模型专用预处理和后处理 |
| 基础合同 | `ai/model/model_contract.py`、`models/contracts/` | 结构和语义合同 |
| 加载/缓存 | `ai/model/loader.py`、`ai/model/factory.py` | runtime 选择和生命周期 |
| 调用 trace | `ai/pipeline/` | P2 只读取真实调用和中间产物；业务编排修改归 P3 |
| source map | `scripts/build_model_source_map.py` | 模型来源和消费者 |
| 验证矩阵 | `scripts/build_model_validation_matrix.py` | exact 状态汇总 |

### 7.10 每批验证

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . \
  --model-dir ai/model

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contract-audit-next.json

.venv/bin/python scripts/probe_openvino_ir.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/openvino-ir-runtime-probe-next.json

.venv/bin/python scripts/build_model_source_map.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --require-exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map-next.json

.venv/bin/python scripts/build_model_validation_matrix.py \
  --source-map test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map-next.json \
  --invocations test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations-next.json \
  --runtime-probe test_data/outputs/luminar-1.28.0-23071/diagnostics/openvino-ir-runtime-probe-next.json \
  --require-exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-validation-matrix-next.json
```

最终必须同时满足：92 个活动注册项全部 validated，或不可达项已凭证据从活动清单删除；exact matrix pending=0；source-map pending_required_models=0、unresolved=0；所有活动 fallback 通过相同模型语义合同。建议最终报告直接由 exact gate 生成，避免手工拼接错误输入。

## 8. P3：主效果 40/40

### 8.1 当前 7 个失败

| capability | MAE | SSIM | 首要排查层 |
|---|---:|---:|---|
| `magic_lights` | 0.005906 | 0.979915 | 局部结构/光晕核，SSIM 仅略低于门限 |
| `face_ai` | 0.030175 | 0.984125 | ROI、landmark、肤色保护，MAE 仅略高于门限 |
| `sky_replace` | 0.039682 | 0.973711 | sky/horizon mask、重光和素材几何 |
| `sunrays` | 0.053714 | 0.956221 | 光源位置、遮挡、衰减 |
| `depth_volume` | 0.069188 | 0.960300 | depth 方向、尺度、曲线和合成 |
| `fog` | 0.113488 | 0.903759 | depth/sky mask、透射率和颜色 |
| `blue_hour` | 0.039456 | 0.975336 | 共享天空分割及局部色调映射 |

`new_neon_light` 和 `lut_mapping` 在 v4 主报告中已经通过，作为回归锚点保留，不再列入失败簇。先修共享中间产物，再修单个效果参数；禁止对最终 RGB 图做补偿曲线来掩盖错误 mask/depth。

### 8.2 根因簇和执行顺序

| 顺序 | 根因簇 | 当前失败 | 依赖与策略 |
|---:|---|---|---|
| E0 | 接近门限 | `magic_lights`、`face_ai` | 先增加 holdout，确认不是单 fixture 过拟合，再做窄校准 |
| E1 | 深度合同 | `depth_volume` | M1 depth 模型；先锁 depth map，再调合成 |
| E2 | 天空/大气共享链 | `blue_hour`、`fog`、`sky_replace`、`sunrays` | M1 segmentation/depth；共享 mask 先于单效果参数 |
| E3 | 已通过锚点 | `new_neon_light`、`lut_mapping` | 每个批次必须保持通过，发现回退立即停止 |

### 8.3 E0-A：`face_ai`

验证顺序：face boxes → landmark 坐标 → 眼睛/嘴/皮肤 ROI → 参数强度 → 色彩保护 → 多人脸排序。

验收：主 fixture 通过，至少一张多人脸和一张无人脸 holdout 不回退，其他人像工具不受影响。

### 8.4 E0-B：`magic_lights`

1. 保存 Native 与候选的亮点位置、局部梯度和 glow 半径对比；
2. 区分检测区域正确但卷积核不一致，还是检测漏点/误点；
3. 验证颜色、衰减、blend space 和高光保护；
4. 使用无灯光、单灯和多灯 holdout，不能只优化 `night-lights.png`。

`new_neon_light` 不共享未经证明的检测合同；其当前通过结果只作为不回退锚点。

### 8.5 E1：`depth_volume`

1. 固定模型输入和原始 depth tensor，验证近/远方向、归一化和 resize；
2. 保存候选的归一化 depth map 与分位数，定位全局亮度偏差来自 depth 还是 tone curve；
3. 分离 depth 权重、局部对比和最终 opacity；
4. 用近景主体、远景风景、低纹理画面和非天空负样本验证。

### 8.6 E2：天空和大气簇

1. 冻结同一 depth map 输出，验证近/远方向；
2. 对比 sky/foreground/horizon mask；
3. 验证 mask feather 和缩放；
4. 分别校准蓝调、雾透射率、天空合成和太阳遮挡；
5. 用非天空负样本确认不会全图套用。

### 8.7 修改入口

- `ai/pipeline/image_effect_pipelines.py`；
- `image_ops/effects/basic.py`；
- `image_ops/effects/graph.py`；
- `image_ops/effects/luminar_preset.py`；
- `configs/capabilities/execution-graphs.json`；
- `configs/capabilities/parameter-schema.json`；
- `configs/capabilities/material-mappings.json`。

### 8.8 单效果循环

执行前把 `CAPABILITY_ID` 替换为待校准能力 ID。

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability CAPABILITY_ID \
  --force \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-next \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-generation-next.json

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability CAPABILITY_ID \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-next \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-CAPABILITY_ID-next.json
```

每关闭一个失败后重跑全量 40 case，防止共享 pipeline 回退。单 case 只有 calibration 和至少一个独立 holdout 同时通过才允许关闭；不得把 reference、case ID、输入 hash 或失败能力列表带入运行时算法。

## 9. P4：扩展 Exact 69/69

主效果未达到 40/40 前，不对当前 28 个扩展失败逐个做局部特判。最新正式 run 已通过 41/69、失败 28、pending 0，候选生成 69/69 且 failed=0。

### 9.1 当前失败簇

| case 数 | capability |
|---:|---|
| 2 | `default_effects`、`face_ai`、`grain`、`vignette` |
| 1 | `ai_enhance`、`blue_hour`、`bokeh_ai`、`color_adjustments`、`color_enhancer`、`color_toning`、`denoise`、`denoise_laplacian`、`depth_volume`、`face_enhancer`、`fade`、`fog`、`high_key`、`landscape_enhancer`、`magic_lights`、`pro_contrast`、`radiance`、`slim_people`、`structure_ai`、`sunrays` |

这些计数用于聚类和回归，不得据此在 capability 内新增 case 分支。

### 9.2 工作方式

1. 重跑 69 case；
2. 按 capability、模型、中间产物和参数区间聚类；
3. 区分主 fixture 已修复但 holdout 失败、连续参数失败、素材变体失败；
4. 每个根因只改一个共享实现；
5. 记录受益和回退 case 列表。
6. 对低/中/高参数、不同素材类型和 preview/export 建立参数曲线，不只检查主参数点；
7. 每个修复重跑 69 case 和 40 个主效果，发现主效果回退立即撤回当前批次。

### 9.3 准出条件

- case_count=69；
- passed=69；
- failed=0；
- pending=0；
- 没有新增 capability-specific threshold；
- 40 个主效果继续全通过。

## 10. P5：交互实现 10/10

根据 P1 Browser dry-run 修复行为，但暂不发布正式 evidence。

当前 10 个 v2 合同中，Native 8/10、Browser 8/10。最新 `interaction-execution` 有 6 个 issue：`viewport-contract-mismatch`、`stale-frontend-build`，以及 Preset、Multi-image 各自缺 Native observation 和 Browser execution。P5 先补齐两个真实行为缺口；已有 8 条在 frontend 冻结后由 P7 全量重录，不把旧证据补字段后复用。

### 10.1 修复顺序

1. Catalog：右键子菜单、folder collection、滚动和 trash restore；
2. Editor 基础：工具展开、crop、照片切换、history、compare/zoom/pan；
3. Preset、layer、mask 生命周期；
4. 三类多图；
5. export 唯一输出和元数据。

### 10.2 关键入口

- `frontend/src/App.tsx`；
- `frontend/src/components/CatalogWorkspace.tsx`；
- `frontend/src/components/ToolPanel.tsx`；
- `frontend/src/components/PreviewPanel.tsx`；
- `frontend/src/components/PresetBrowser.tsx`；
- `frontend/src/components/LayersPanel.tsx`；
- `frontend/src/components/WorkflowWorkspace.tsx`；
- `frontend/src/components/ExportDialog.tsx`；
- `frontend/src/api.ts`；
- `api/http/router.py`；
- `services/editor/service.py`；
- `storage/catalogs/luminar_sqlite.py`。

### 10.3 准出条件

- 10 个 Browser dry-run 均完成全部 events；
- 可见断言和 API 断言全部通过；
- 不使用 fixed sleep；
- 项目、catalog、layer、mask 和 history 持久化可在刷新后恢复；
- 功能修复的单元/集成测试已加入全量回归。
- 10 个合同 ID、事件序列和断言均来自当前 v2 contract，不存在 v1 ID 映射或旧 observation 复用。

## 11. P6：UI 像素 16/16

当前源码的 UI execution evidence 已达到 16/16、issue=0，且截图是 `1440x900` logical viewport、DPR 2、`2880x1800` physical PNG；当前 UI pixel 为 0/16。正式顺序是：**保留当前 evidence 作为差异基线 → 按共享布局/字体/颜色根因修复 → 每次 frontend hash 变化后重新全录 16 个状态 → pixel 16/16 后冻结 frontend hash**。

固定状态集合：`catalog`、`presets`、`edit`、`layer-stack`、`layer-library`、`tool-expanded`、`edit-history`、`more-panel`、`info-panel`、`edit-collapsed`、`black-white-before-conversion`、`black-white-after-conversion`、`denoise-level-selected`、`export-dialog`、`multi-image`、`multi-image-complete`。不得删除失败状态来提高通过率。

### 11.1 校准批次

| 批次 | 状态 | 优先修复 |
|---|---|---|
| U1 | 全部状态 | header、rail、左右栏、canvas、filmstrip、背景色 |
| U2 | `catalog`、`multi-image*` | sidebar、计数、网格、workflow 列表和完成态 |
| U3 | `edit`、`tool-expanded`、黑白、降噪 | 面板宽度、accordion、slider、radio、crop overlay |
| U4 | `layer-*`、`edit-history` | layer row、素材库、历史条目和选中态 |
| U5 | `presets`、`more-panel`、`info-panel` | 内容顺序、封面、卡片、EXIF 行 |
| U6 | `edit-collapsed`、`export-dialog` | 收起布局、dialog 尺寸、表单和遮罩层 |

### 11.2 每批顺序

1. 几何：宽高、位置、padding、gap；
2. 排版：字体、字号、行高、字重；
3. 图标和资源：尺寸、颜色、缩略图、裁切；
4. 边框、圆角、阴影和分隔线；
5. selected/hover/disabled/expanded/busy 状态；
6. Retina 和色彩管理差异。

### 11.3 修改入口

- `frontend/src/styles.css`；
- `frontend/src/components/`；
- `frontend/src/App.tsx`；
- `configs/ui/`；
- `assets/`。

### 11.4 验证规则

每次 frontend hash 改变后必须重录全部 16 个状态，不能拼接新旧截图。每个状态保存 logical screenshot、physical candidate、DOM、AX、fixture hash、build hash 和 diff。

校准必须使用绑定 `1440x900` logical viewport、DPR 2、`2880x1800` physical viewport 的 canonical reference。人工浏览只用于定位差异；没有完整 screenshot/DOM/AX/hash 链的状态不能算通过。

正式 evidence 构建和复算使用当前 Browser 的真实版本号。先在两个独立终端启动隔离的当前源码服务：

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8001

VITE_API_TARGET=http://127.0.0.1:8001 \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port 5175
```

然后从项目根目录执行原生 DPR 2 采集。`ACTUAL_BROWSER_VERSION` 必须取自生成的 `capture-run.json`，禁止填写猜测值：

```bash
node frontend/scripts/capture-ui-dpr2.mjs \
  --plan test_data/parity/ui-browser-capture-plan.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-dpr2-next \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-next

.venv/bin/python scripts/build_ui_browser_execution.py \
  --source-captures test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-capture-raw-dpr2-next \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-next \
  --browser-version ACTUAL_BROWSER_VERSION \
  --capture-engine chrome-cdp-page-capture-screenshot \
  --logical-width 1440 \
  --logical-height 900 \
  --device-scale-factor 2 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution-next.json

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --execution test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution-next.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-next.json

.venv/bin/python scripts/validate_ui_references.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --candidates test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates-next \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-next.json
```

准出：evidence 16/16、pixel 16/16，所有状态 `MAE <= 0.03` 且 changed pixel ratio `<= 0.02`。

## 12. P7：正式 Browser/Native 10/10

P6 通过后冻结 frontend hash，再生成正式 Browser evidence。

### 12.1 正式执行

1. 校验 P1 Native observation 仍与活动 v2 合同一致；
2. 若合同未变，不重复 Native 采样；若事件或最终状态变化，必须在 Luminar 全屏重新采样受影响合同；
3. 每个 Browser 合同从独立 fixture reset 开始；
4. 保存 final screenshot、DOM、AX、execution trace、network trace、console log；
5. 绑定 Native observation hash 和 frontend build hash；
6. Browser 执行前再次做本地服务和浏览器版本预检；允许使用已验证的独立 headless Chrome runner 避免占用用户外设，但必须保存 raw trace，且不得降低安全策略或人工补写结果；
7. 使用 builder 从显式 raw trace 发布 execution，再用 validator 复算。

### 12.2 构建和复算

```bash
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw-next.json \
  --evidence-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-next \
  --native-root test_data/outputs/luminar-1.28.0-23071/observations/interactions \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution-next.json

.venv/bin/python scripts/validate_interaction_execution.py \
  --execution test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution-next.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-validation-next.json
```

### 12.3 验收

- contract_count=10；
- executed=10；
- passed=10；
- issue_count=0；
- Native/Browser 事件、等待和最终状态一致；
- console error 和 failed network request 为 0。

## 13. P8：真实 Native catalog 单轨替换

当前 `storage/catalogs/luminar_sqlite.py` 和 `library/catalog.luminarneo` 的 schema 155 只证明项目已经使用 SQLite 单轨；它不是已观察到的 Luminar Native 私有 schema，不能作为严格对齐准出证据。最终发布前按以下顺序执行：

1. 在不修改原文件的前提下找到本机真实 Luminar catalog，复制到只读证据目录；`profiles/crop.db` 是相机裁切库、`profiles/data.mlcdb` 不是 SQLite，均不得误作 catalog；
2. 记录 SQLite header、`PRAGMA user_version`、表、列、索引、触发器、外键和初始 hash；
3. 在 Luminar 全屏环境分别执行新建 catalog、导入、编辑、收藏/评级、删除/恢复和导出，逐步复制数据库并计算 schema/data diff；
4. 根据观察结果一次性重写 `storage/catalogs/luminar_sqlite.py` 及其调用者，让项目只写真实 Native schema；
5. 删除 schema 155 的建表逻辑、测试 fixture 和旧项目数据库；验证数据重新创建，不提供 schema 155→Native 的运行时迁移；
6. 当前仓库已不存在 `scripts/migrate_catalog_to_luminar_sqlite.py`，持续用静态搜索确保 JSON→SQLite 迁移、双写、schema auto-upgrade 和 storage fallback 不被重新引入；
7. 删除旧 contract parser、ID 映射和 current evidence 中的 v1 记录；历史 run/reference 只保留审计用途，不能被 current pointer 或运行时读取；
8. 经 model-specific contract 验证的 OpenVINO runtime fallback 与 catalog 兼容层无关，可以继续保留。

准出：已获得真实 Native schema 和状态变化证据；项目可以完成 catalog round-trip；`api/`、`services/`、`storage/`、`frontend/src/` 中只有一条 Native schema 路径；不存在项目旧 schema、JSON catalog、迁移器、双写、auto-upgrade、fallback 或 v1 contract 兼容逻辑。真实 schema 未获得时，本阶段保持 blocked，不能用 schema 155 替代。

## 14. P9：连续两轮 exact 发布门禁

### 14.1 冻结

冻结以下输入：

- source；
- model artifact 和 contract；
- validation cases/input/reference；
- UI fixture 和 Native observation；
- environment、viewport、locale、timezone；
- comparator 和阈值。

### 14.2 执行

执行前把 `SOURCE_SHORT_HASH` 替换为冻结 source fingerprint 的唯一短前缀；A/B 使用相同前缀和不同 run ID。

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id release-exact-a-SOURCE_SHORT_HASH \
  --runs-root test_data/outputs/luminar-1.28.0-23071/diagnostics/runs \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-a.json

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id release-exact-b-SOURCE_SHORT_HASH \
  --runs-root test_data/outputs/luminar-1.28.0-23071/diagnostics/runs \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-b.json

.venv/bin/python scripts/compare_exact_runs.py \
  --first test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-a.json \
  --second test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-b.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-run-comparison-release.json
```

只有单轮预检已经达到 required failure=0 后才执行 A/B。两轮之间不得修改或重新生成任何输入；两轮都必须是完整独立执行，不能复制报告或复用 candidate 目录。任一 required gate 失败或 fingerprint 不同均停止发布，不执行“部分对齐”声明。

## 15. 测试分层和回归频率

| 频率 | 验证 | 触发条件 |
|---|---|---|
| 每次修改 | 目标单元测试、目标 capability parity | 所有代码修改 |
| 每个模型合同 | wrapper contract、正负样本、真实调用 trace | 模型批次 |
| 每个效果根因 | calibration + holdout + 40-case 回归 | 效果修改 |
| 每个 UI 批次 | 16-state evidence + pixel comparator | frontend hash 变化 |
| 每个交互批次 | 10 contract dry-run | 行为修改 |
| 每阶段 | Python、Frontend、build、Ruff | 阶段准出 |
| 发布前 | exact A/B + fingerprint compare | 所有域清零 |

基础回归：

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

## 16. 排期和任务拆分

以下是单人全职、相似模型可以按族复用验证夹具时的建议范围，不是降低验收标准的期限承诺：

| 阶段 | 建议工期 | 关键输出 |
|---|---:|---|
| P0 | 0.5–1 天 | 冻结 manifest 和任务看板 |
| P1 | 1–2 周 | Native 10 observation、Browser gap 列表 |
| P2 | 已完成 | 活动模型 22/22 validated；70 个不可达工件证据化退役 |
| P3 | 2–4 周 | 主效果 40/40 |
| P4 | 2–3 周 | 扩展 Exact 69/69 |
| P5 | 2–3 周 | Browser dry-run 10/10 |
| P6 | 2–4 周 | 当前 build evidence 16/16、UI pixel 16/16 |
| P7 | 3–5 天 | 正式 Native/Browser 10/10 |
| P8 | Native schema 获取前 blocked；获取后 3–7 天 | 真实 schema 单轨替换和无兼容层审计 |
| P9 | 1–2 天 | exact A/B 和发布结论 |

从当前状态起，剩余工作建议预留约 8–16 周。主要不确定性来自 Native 中间产物可观察性、剩余效果族的内容感知语义，以及 UI 字体/色彩栅格差异。若 Native fixture 无法获得或 Browser 安全策略持续阻断，工期应按实际证据增加；不用统一 wrapper、人工观感或阈值放宽缩短。

## 17. 缺陷记录模板

每个失败使用同一模板：

| 字段 | 内容 |
|---|---|
| ID | 域-能力-序号 |
| Native 前置 | app/build/fullscreen/fixture/hash |
| 复现事件 | 与合同一致的事件列表 |
| 期望 | Native 可见、AX、API 或像素结果 |
| 实际 | Browser/候选结果 |
| 指标 | MAE、SSIM、changed ratio、hash 或状态差异 |
| 根因层 | 模型/中间产物/效果/UI/持久化/证据 |
| 修改入口 | 真实文件和函数 |
| calibration | 用例和结果 |
| holdout | 用例和结果 |
| 回归 | 受益、无变化、回退 case |
| 证据 | run-scoped artifact 路径 |
| 状态 | open/fixed/verified/blocked |

## 18. 最终验收清单

- [ ] 本机 Luminar Neo 版本、build、bundle id、语言和全屏状态已绑定；
- [ ] 排除功能未进入 required scope；
- [x] 活动模型 22/22 validated，pending=0；70 个不可达工件已证据化退役；
- [ ] 活动模型都有真实调用 trace 和 model-specific contract；
- [ ] 主效果 40/40；
- [ ] 扩展 Exact 69/69；
- [ ] 多图 3/3；
- [ ] UI evidence 16/16；
- [ ] UI evidence、DOM、AX、截图和 frontend hash 属于同一当前 build；
- [ ] UI pixel 16/16；
- [ ] Native 10/10；
- [ ] Browser 10/10；
- [ ] 真实 Native catalog schema、状态变化和 round-trip 已验证；
- [ ] 只有真实 Native schema 单轨；没有 JSON catalog、迁移脚本、项目旧 schema、双写或 v1 contract 兼容逻辑；
- [ ] Python、Frontend、build、Ruff 全通过；
- [ ] exact A/B required failure 均为 0；
- [ ] A/B fingerprint 完全一致；
- [ ] 最终声明明确限定为冻结的本地核心合同。
