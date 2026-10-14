# Luminar Neo 1.28 严格对齐执行报告（2026-08-29）

> 本报告记录较早的 `execution-plan-after-20260829` 阶段，已由
> `absolute-parity-execution-report-2026-08-29-r8.md` 取代。当前状态和后续执行
> 必须以 R8 报告为准，不得继续引用本文中的旧通过率、旧交互缺口或旧 SQLite 结论。

## 1. 结论

本轮已经按活动计划依次完成模型合同收敛、全屏 Native 观察、Browser 交互重录、部分效果校准、真正 DPR 2 的当前源码 UI 重录、SQLite 单轨核验、全量回归和 exact 单轮预检。最新正式 run 仍为 `29/34`；其中 `python-lint` 是本轮新增测试的 import 顺序问题，已在 run 后修复并由 `ruff check .` 复验通过。因此当前代码还剩 4 个已确认产品门禁失败，但在重新执行完整 exact 前不把汇总手工改写为 `30/34`。**不能声明与本机 Luminar Neo 绝对对齐，也不能启动连续 A/B 发布轮**。

最新不可覆盖预检为 `execution-plan-after-20260829`：

- exact quality gate：`29/34`，run 内 failure `5`；run 后已关闭 lint，产品 failure 为 `4`；
- 活跃模型：`22/22 validated`，pending `0`，model exact gate passed；
- 主效果：`33/40`，失败 `7`；
- 扩展 Exact：`41/69`，失败 `28`；
- UI 当前源码执行证据：`16/16`，原生 DPR 2，issue `0`；
- UI 像素：`0/16`；
- Native/Browser 交互合同：`8/10`；
- 本轮相关 Python：`31/31`，全仓 Ruff 通过；
- Frontend：`41/41`，生产构建通过；
- SQLite：schema `155` 单轨通过，无 JSON 双写和迁移兼容入口。

范围仍只包含免费、离线、可重复验证的本地核心能力。付费、升级、教程、帮助、账号、商店、云生成和商业内容不实现、不采样，也不进入 required gate。

## 2. 执行前后对比

### 2.1 同一活动门禁口径

| 域 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Exact gate | 27/34 | 正式 run 29/34 | run 后已修复 lint；剩余 4 项是效果、UI pixel、交互真实差距 |
| 活跃模型合同 | 27/92，pending 65 | 22/22，pending 0 | 70 个非活动 artifact 已按消费者和产品路径证据退役；未删除仍在调用的模型 |
| 主效果 | 33/40 | 33/40 | 总通过数不变；Slim People、Depth zero、Blue Hour 显著改善，当前失败集合收敛为 7 项 |
| 扩展 Exact | 39/69 | 41/69 | Depth zero 和 Face Enhancer zero 各新增 1 个通过；仍有 28 个失败 |
| UI current-build evidence | 0/16，stale build | 16/16，原生 DPR 2 | screenshot、DOMSnapshot、AX、步骤和当前 build hash 全部通过 |
| UI pixel | 0/16 | 0/16 | 页面可运行不等于像素一致 |
| Native/Browser v2 | 0/10 | 8/10 | 8 项具备全屏 Native + Browser 正式证据 |
| Python | 339 | 本轮相关 31 + Ruff | 全部通过；完整 exact 的 lint 失败已在 run 后修复 |
| Frontend | 34 | 41 | 全部通过且 production build 通过 |

用户最初提供的主效果数据是 `36/45`。当前活动集合为 `40` 项：旧集合中有已移除/重分类用例，LUT 还被登记为 confirmed-invalid reference，因此不能把 `36/45` 与 `33/40` 当作同分母升降比较。当前可信发布分母只能使用最新 run 中冻结的 `40` 项。

### 2.2 最新 exact fingerprint

| 指纹 | SHA-256 |
|---|---|
| release | `e5b6fb17242a9696b27a097c877873ff02f6f1c5907ae1c89af381fb57ff7d92` |
| source | `2eafd0265c2fd9703139d18b6bf45f0707253b09edd56d11d63c8057d2fc30f2` |
| models | `84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237` |
| validation | `817fc869898366bc835a44104d400c62f71a074175391a63a5197f5634930e5d` |
| environment | `0d9a382a7300760678148745cd651dead352a0adbddf3c110ae9692cab70e49a` |

任何源码、模型、fixture、reference、比较器或交互证据变化后，都必须生成新 fingerprint 和新 run。

## 3. 已完成的实现

### 3.1 模型 contract

原 `92` 个模型结构记录被重新按真实消费者和产品调用路径审计：`22` 个保留为活动模型，`70` 个没有活动调用路径的 artifact 以证据退役。活动矩阵结果为：

- `22/22` model-specific contract validated；
- pending `0`；
- `16` 个为 `inference-validated`，`6` 个为 `ort-smoke-passed`；
- model presence gate 和 exact gate 均 passed；
- ONNX 仍是主路径，OpenVINO IR 仅作为通过同语义合同的 fallback；
- 不可用且已排除范围的超分辨率路径 fail closed，不返回伪结果。

### 3.2 项目持久化与交互稳定性

Browser 连续图层、遮罩和历史操作曾暴露项目 JSON 偶发多出 `}` 的真实并发写入问题。项目保存现已改为同目录临时文件加原子 `replace`，并新增回归测试，避免读取半写入 JSON。

交互 evidence CLI 还修复了 `frontend_root` 未传入验证器的问题；现在 stale frontend hash 会被 CLI 正确拦截。

### 3.3 效果校准

- Face Enhancer：`amount=0` 现在严格返回原图且不执行 GFPGAN；扩展用例从 `MAE 0.042702 / SSIM 0.975313` 改善为 `MAE 0.003583 / SSIM 0.999955` 并通过。
- Slim People：人体 mask 覆盖异常时 fail closed，主效果通过；扩展强度用例仍因 SSIM 不足失败。
- Depth Volume：`amount=0` 改为严格身份插值，扩展 zero 用例通过；full-strength 仍需重建深度映射。
- Blue Hour：改为可解释的逐通道单调曲线，主用例从约 `MAE 0.133` 改善到 `0.039456`；仍未达到 `MAE <= 0.03` 和 `SSIM >= 0.98`。
- 没有降低 MAE、SSIM 或 UI changed-pixel-ratio 阈值，也没有按 case id/reference hash 特判。

### 3.4 Native 与 Browser 合同

已完成 8 项：

1. 目录照片右键子菜单；
2. 目录文件夹上下文和滚动；
3. 工具展开与裁切；
4. 照片切换和独立历史；
5. 图层生命周期；
6. 遮罩生命周期；
7. 前后对比、缩放和平移；
8. 导出对话框和文件。

所有 Native 新采样均以 Luminar Neo macOS 全屏为前提。当前没有独立虚拟 macOS 桌面/虚拟鼠标能力；Browser CUA 是隔离指针，但 Computer Use 操作本机应用仍会使用共享桌面。按用户补充要求，在没有新隔离能力时保持现状，不伪称虚拟外设隔离。

尚未完成的 2 项：

- preset import/preview/apply：发现真实 app 生成的 `.lnp` 目录，但没有真实 collection/package；合成 `.lnpc` 已被原生应用拒绝，不能伪造通过。
- multi-image-three-workflows：Native HDR 和 Focus Stacking 通过；Panorama 处理超过 420 秒仍停在 spinner，Continue 不可用。Browser 受控文件选择器又不允许本地文件注入，因此正式完成态也未生成。

### 3.5 UI 16 状态

已新增基于 Chrome DevTools Protocol 的零依赖 DPR 2 采集器。它使用独立 headless Chrome profile、`1440x900` 逻辑 viewport 和 `deviceScaleFactor=2`，由 `Page.captureScreenshot` 直接生成 `2880x1800` PNG，不占用本机鼠标或键盘，也不做 Lanczos 或其他后处理放大。

当前源码已完整录制 16 个状态，包括此前缺失的 `multi-image-complete`。每项都有原始 PNG、候选 PNG、DOMSnapshot、完整 AX 树、实际步骤、浏览器版本和 capture method。`ui-execution-evidence` 结果为 `expected=16 / executed=16 / passed=16 / issue=0`。

真实像素结果仍为 `0/16`。MAE 范围约 `0.031498–0.186935`；`edit-collapsed` 最接近，`multi-image-complete` 差异最大。该结果证明执行证据缺口已关闭，但布局、字体、颜色、内容选择和栅格仍未达到 Luminar reference，不能把“可运行”表述成像素对齐。

### 3.6 SQLite 单轨

- 运行时路径：`library/catalog.luminarneo`；
- 实现：`storage/catalogs/luminar_sqlite.py`；
- `PRAGMA user_version=155`；
- catalog/API round-trip 32 项测试通过；
- JSON→SQLite 一次性迁移脚本和迁移测试已移除；
- 遗留迁移脚本 `.pyc` 已删除；
- 没有 JSON catalog、双写、旧 schema fallback 或历史兼容层。

本实现只声称使用当前已验证的 schema 155 合同，不声称虚构出了尚未取得的 Luminar 原生 catalog 私有表结构。若将来取得真实本机 schema，应一次性替换当前 schema，并删除旧实现，不增加兼容层。

## 4. 当前 4 个产品 required failure

最新正式 run 额外包含一个已在 run 后修复的 `python-lint` 失败；以下只列仍存在的产品门禁。

### 4.1 主效果 `output-parity`

`33/40`，剩余 7 项：

| 效果 | MAE | SSIM | 主要方向 |
|---|---:|---:|---|
| Face AI | 0.030175 | 0.984125 | 人脸区域强度/肤色映射，MAE 刚超过阈值 |
| Depth Volume | 0.069188 | 0.960300 | 深度分层、局部对比和 foreground protection |
| Magic Lights | 0.005906 | 0.979915 | SSIM 仅低于阈值，检查光斑结构而非放宽阈值 |
| Blue Hour | 0.039456 | 0.975336 | 天空/前景分离和局部冷暖映射 |
| Fog | 0.113488 | 0.903759 | 深度雾、地平线与主体保护 |
| Sky Replace | 0.039682 | 0.973711 | mask、horizon、颜色匹配和融合 |
| Sunrays | 0.053714 | 0.956221 | 光源定位、遮挡、射线衰减与 bloom |

LUT reference 已登记为 confirmed-invalid，不再混入主效果通过率；仍必须在本机全屏重新观察真实 LUT 输出后才能恢复该合同。

### 4.2 扩展 Exact `exact-incremental-parity`

`41/69`，剩余 28 项。Face Enhancer zero 已关闭；重复失败仍主要集中在 Face AI、Face Enhancer full、Vignette、Grain、Default Effects，以及 AI Enhance、Blue Hour、Bokeh、Color、Denoise、Depth、Fade、Fog、High Key、Landscape、Magic Lights、Pro Contrast、Radiance、Slim People、Structure 和 Sunrays。

扩展 exact 必须在主效果族根因修复后按参数梯度和独立 holdout 校准，不能逐 case 打补丁。

### 4.3 UI pixel `0/16`

真实 DPR 2 采集能力已经完成；接下来只允许依据 16 份物理像素 diff 校准布局、字体、颜色、图标、间距和内容状态。不得通过放宽阈值或恢复派生截图关闭该门禁。

### 4.4 交互 `8/10`

除 preset 与三类多图工作流外，还存在全局 `viewport-contract-mismatch`：Browser 真实 viewport 为 `1440x900`，合同物理 viewport 为 `2880x1800`。必须补真实 DPR 2 browser execution，或把合同明确拆成逻辑事件 viewport 与物理 UI screenshot viewport；不能把两者混写。

## 5. 下一步严格执行顺序

### P0：补齐真实采样能力和两项交互证据

1. 在不污染冻结输入集的位置制作/取得真实 Luminar preset collection/package，先由全屏 Native 导入、预览、应用和导出回读，再执行 Browser 同事件。
2. 对 Native Panorama 单独建立最小 2/3 图 fixture，记录 CPU/GPU、spinner、按钮 AX、日志和超时；先判断输入不满足、算法卡死还是应用 bug，再决定实现校准。
3. 为 Browser 提供真实本地文件注入或 catalog→workflow 选择路径，完成 `multi-image-complete`，同时覆盖 HDR、Focus、Panorama 和导出。
4. 优先使用可隔离的虚拟显示/虚拟指针；若本机仍无此能力，只在 Luminar 全屏时使用共享 Computer Use，并保持用户当前外设状态不变。

验收：Native 10/10、Browser 10/10、interaction viewport issue 0。UI evidence 16/16 已完成。

### P1：建立真实 DPR 2 UI 采集并校准 UI

1. 保持现有真正 `deviceScaleFactor=2` 的 `2880x1800` 采集链；禁止重新引入后处理放大。
2. 先修公共 shell：字体、panel 宽度、顶部栏、底部 rail、canvas fit、背景和边框。
3. 再按当前 MAE 从大到小处理：multi-image-complete、catalog、denoise、presets、export、multi-image、BW、more/layer/tool/history、edit/info/collapsed。
4. 每次公共 CSS 变更后重录全部 16 项，不复用旧 screenshot/DOM/AX。

验收：UI execution 16/16 且 UI pixel 16/16，阈值保持不变。

### P2：关闭 7 个主效果

1. 先补 full-screen Native 中间证据：mask、depth、horizon、foreground、light source、color statistics。
2. 先处理结构性误差最大的 Fog、Depth、Sunrays、Sky Replace/Blue Hour；再处理 Face AI；最后关闭接近阈值的 Magic Lights。
3. 每个根因至少包含 calibration + 不同照片 holdout + zero/mid/full 参数梯度。
4. 重新观察 confirmed-invalid LUT reference，再决定恢复或继续阻塞。

验收：主效果 40/40。

### P3：按效果族关闭 29 个扩展 Exact

复用 P2 的算法根因修复，逐族覆盖参数曲线、zero identity、强度单调性、区域保护和 preview/export 一致性。任何只让一个 case 通过、却使 holdout 回退的修改必须撤销。

验收：69/69。

### P4：连续两轮发布门禁

只有单轮 exact 已达到 `34/34`、required failure `0` 后才执行 A/B。两轮必须使用完全相同的 source/model/validation/environment/reference fingerprint，候选目录独立，不能复制报告或复用 candidate。

验收：A、B 两轮 required failure 都为 0，fingerprint 完全一致，`compare_exact_runs.py` passed。

## 6. 遗漏审计

本轮没有发现新的活动模型 pending、JSON catalog 兼容入口或回归测试失败。仍未闭合的全部已知项是：

1. 主效果 7 项；
2. 扩展 Exact 29 项；
3. UI pixel 16 项；
4. preset 正式交互；
5. Panorama 正式交互；
6. Browser interaction 真实 DPR 2 / viewport contract（UI screenshot viewport 已完成）；
7. confirmed-invalid LUT reference 重观察；
8. 单轮 34/34；
9. 连续 A/B 两轮。

此外，Luminar 当前仍可能停留在 Panorama 模态流程。未经用户明确授权，不强制结束应用，避免丢失未保存状态；若要继续 Native LUT/Preset/Panorama 采样，需要用户明确授权强制重启，或由用户自行正常退出该模态页。

这些项目全部保持 fail closed，没有用人工检查、功能可运行、旧 hash、派生截图或阈值放宽替代。

## 7. 权威证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/execution-plan-after-20260829/quality-gates-exact.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/execution-plan-after-20260829/`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-validation-matrix-active22-20260829.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-current-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/dataset-freshness-current-final.json`
