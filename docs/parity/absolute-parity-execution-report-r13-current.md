# Luminar Neo 本地核心严格对齐执行报告（R13）

执行日期：2026-08-31  
目标应用：本机 Luminar Neo `1.28.0 (23071)`  
执行 run：`alignment-r13-final-20260831`  
实施计划：`docs/parity/absolute-parity-optimization-plan-current.md`  
范围：免费、本地、可执行的目录、预设、编辑工具、图层、遮罩、多图工作流和导出  
排除：付费、商店、账户、云服务、教程、帮助、推广和授权购买流程

## 1. 最终结论

R13 已按计划顺序执行到所有安全准出边界，并完成遗漏复核。当前仍不能声明与 Luminar Neo 绝对对齐：
最终 exact 为 `31/36`，5 个 required gate 失败；scope 仍有 59 项，主效果 `35/40`，Exact 增量
`61/69`，UI pixel `0/16`，canonical Browser interaction `8/10`。

本轮的确定性改进有三项：

1. 找到本机真实 Native catalog，以只读 immutable 模式验证后，一次性把项目 SQLite schema 从旧的
   自验证结构替换为真实 Native 结构；没有迁移层、旧 reader、JSON catalog 或双写。
2. 为 UI exact 增加 Native AX 锚定的 region 合同并重新录制当前源码 16/16 正式证据；region manifest
   路径和 SHA-256 现已进入 evidence gate，不能事后移动裁剪范围。
3. 新增 DPR 2 的正式 headless interaction recorder，并完成 HDR/Focus/Panorama 三工作流的 current-build
   独立合同 `1/1`；旧 8 项没有被冒充为当前 build，所以 canonical 10 项总门禁仍如实 blocked。

Native Computer Use 没有执行。预检仍无法证明独立虚拟屏幕、独立虚拟鼠标/键盘和输入路由；按用户要求，
没有启动、聚焦或控制 Luminar，也没有影响用户外设。P2/P3 因此没有获得新的 Native holdout，效果算法
没有被针对单张 reference 继续过拟合，MAE/SSIM 阈值也没有降低。

P9 同指纹 A/B 两轮没有执行，因为 P8 第一轮 exact 仍有 5 个 required failure。这是既定停止条件，
不是被遗漏的验收步骤。

## 2. 执行前后对比

| 维度 | R13 执行前 | R13 执行后 | 结论 |
|---|---:|---:|---|
| exact required gate | 31/36 | 31/36 | 仍有 5 个 required failure |
| scope coverage | 59 issues | 59 issues | 无隔离 Native reference，未伪造关闭 |
| 机器 worklist | 95 项 | 95 项 | 主阻塞项数量不变 |
| 主效果 | 35/40 | 35/40 | 5 项仍失败 |
| Exact 增量 | 61/69 | 61/69 | 8 项仍失败 |
| model contract | 22/22 | 22/22，0 pending | 保持通过 |
| model-backed 调用 | 18/18 | 18/18 | 保持通过 |
| Native interaction | 9/10 | 9/10 | 缺真实 preset collection observation |
| canonical Browser interaction | 8/10 | 8/10 | preset、多图 current-build 尚未合并为 10 项全套 |
| 新增 Browser 多图合同 | 无 | 1/1 current-build | HDR/Focus/Panorama 正式证据完成 |
| UI execution evidence | 16/16 | 16/16 | 重录且新增 region manifest 绑定 |
| UI pixel | 0/16 | 0/16 | 没有以裁剪隐藏核心差异 |
| UI 平均 full-screen MAE | 0.0700274096 | 0.0700275069 | 实质不变，属重录浮动 |
| UI 平均 in-scope MAE | 无固定 region 合同 | 0.0689772790 | 仍远未达到 exact |
| SQLite catalog | 项目自验证结构 | 真实 Native 结构完全一致 | 本轮最重要的 contract 修正 |
| Python tests | 384 passed | 389 passed | 新增 UI region/SQLite 证据测试 |
| Frontend tests | 43 passed | 43 passed | 无回归 |

## 3. 分阶段执行结果

### P0：冻结基线和工作清单

- 基线 scope：59 issues；
- 基线与最终 worklist：均为 95 项；
- exact dry-run：36 个 gate；
- 基线 release fingerprint：
  `821bbd3680b1388c0aad0417c6b9f9f8f5f7fc3931e228b5c3a05db382d058d4`。

### P1：Native 全屏和外设隔离

只读预检没有发现可验证的虚拟显示或独立输入路由，CoreGraphics active display count 为 0，未发现可用的
BetterDisplay/DisplayLink 隔离链。sampling queue 只生成 6 类 dry-run；interaction 选择 10 项，其中
9 项可由当前 Native sampler 描述，preset import 因无可信 `.lnpc` 保持 unsupported。

没有传入 `--allow-ui-control`，没有调用 Computer Use，没有启动或切换 Luminar，没有调用系统文件选择器。

### P2/P3：范围、Native reference 和效果

59 项缺口保持原状态：

- 10 个工具缺 amount anchor：Clone、Color Transfer、Complex Bleach、Crop AI、Deblur、Dodge & Burn、
  Erase、LUT Mapping、Skin Smooth、Sky Replace；
- 40 个主工具都缺两个不同 source hash 的 holdout；
- Crop 缺 crop box、ratio、rotation、flip X/Y、straighten 六个参数合同；
- Native 缺 preset import；Browser canonical 缺 preset import 和正式多图合并证据。

主效果仍失败 5 项：Face AI、Depth Volume、Blue Hour、Sky Replace、Sunrays。Exact 增量仍失败 8 项：
Face AI 两档，以及 Sunrays、Structure AI、AI Enhance、Depth Volume、Blue Hour、Landscape Enhancer。

由于没有新的 Native holdout，本轮没有修改效果实现、增加图片特判或降低阈值。

### P4：模型合同

- `ai/model` 静态 validator：0 finding；
- 22/22 contract valid 且 model-specific，0 pending；
- 18/18 runtime case、16 个逻辑模型均实际 invocation，0 failed；
- 维持 ONNX primary、已验证的同逻辑 OpenVINO IR fallback，没有新增 wrapper fallback。

模型 gate 已关闭，但不替代效果像素 gate。

### P5：Browser 正式交互

新增 `frontend/scripts/capture-interaction-dpr2.mjs`。该 recorder 固定 1440×900 logical、DPR 2、
2880×1800 physical、zh-Hans、Asia/Shanghai，并记录 screenshot、DOM、AX、network、console、trace、
API readback、preview/export hash 和 build hash。文件输入通过 DOM/CDP 注入，不占用系统鼠标键盘。

当前只完整实现 `multi-image-three-workflows`，独立 validator 为 `1/1 passed`；三条 smoke 也为 `3/3`。
其余 9 个合同会 fail closed，而不是沿用或重标旧证据。canonical exact 仍读取原 10 项汇总，所以仍为
`8/10`、7 issues：旧 Browser 环境/DPR/physical/build 绑定不完整，Native/Browser preset 缺失，旧汇总
尚缺 current-build multi。没有可信 `.lnpc`，因此没有伪造 preset 容器或双格式解析。

### P6：UI 正式证据和像素合同

新增 `configs/parity/ui-regions.json` 和 region validator。include 由 Native 全屏 AX 边界锚定，仅排除已明确
不在范围内的帮助、教程、已购预设标题/推广块、导出 iCloud 行；region content hash 为
`7ecfe74b7d371e7c39800a0f0b2a1a30a77ef81ae8d76cfba6dc0f98285f509a`。

R13-02 fixture 为 46/46 unique，fingerprint
`c642001438c18634e41c56d798c2ca83f634b5b9ca371ecd21941e58d9e68799`。16 个状态全部使用 Chrome
151.0.7922.174、1440×900、DPR 2、2880×1800 重录；screenshot、DOM、AX、fixture/build/region hash
证据 `16/16 passed`。像素仍是 `0/16`；mean in-scope MAE `0.0689772790`，mean full-screen MAE
`0.0700275069`。region gate 通过只说明比较合同可信，不说明 UI 已对齐。

### P7：真实 Native SQLite 和持久化

只读发现的 Native catalog：

`/Users/iknow/Library/Group Containers/RTW788AXG3.com.skylum.luminarneo/Space/4413758/4413758.luminarneo`

- 读取方式：SQLite URI `mode=ro&immutable=1`；
- Native 文件 SHA-256：
  `bc6b5467e97a7e2ed925dc19a4039360c0c7a6620d5b81d265fbe8096eb3ce92`；
- schema 155、29 objects、26 tables；
- 真实结构 SHA-256：
  `af8a747826542f67922bab359d4c9567fee7739fc5aaf430e8bb1132dc96c86b`。

项目旧结构与 Native 的唯一结构差异是 `image_exiv_attributes` 列顺序：Native 的
`date_time_tz_offset_min` 紧跟 `date_time_int_64`。实现已一次性改为 Native 顺序，旧结构 hash
`7f754d...` 不再是运行合同。R13-02 项目 catalog 现在与 Native 结构完全一致，catalog JSON 为 0，
dual write 为 false，`compatibility_layers=[]`。

非 catalog 持久化仍 blocked：46 个 project JSON、4 个 workflow session JSON 和本地 preset index 还没有
Native 语义映射；project/layer/mask/history 的 JSON primary 与 SQLite history projection 仍形成两种表示。
在解码并 roundtrip `img_history_states.data_wide_ch` 和资源关系前，没有猜测性删除这些数据，也没有增加
迁移、旧 reader 或 fallback。

### P8/P9：全量回归、exact 和 A/B

- Ruff：passed；
- Python：389 passed，1 个 Starlette deprecation warning；
- Frontend：11 files、43 tests passed；
- Frontend production build：passed；
- model、SQLite、sampling、export 等非失败 gate 保持通过。

最终 run `alignment-r13-final-20260831` 为 `31/36`。失败 gate：

1. `absolute-scope-coverage`：59 issues；
2. `output-parity`：35/40；
3. `exact-incremental-parity`：61/69；
4. `ui-parity`：0/16；
5. `interaction-execution`：8/10、7 issues。

最终 release fingerprint：
`50fe4dd570ffb8e034a8d94d327c51e0473cee0f11faea61a2067a88a94ab2e3`；source：
`49fb87e1595b89a0d108d3c9d8c40c81aa9362a13aada094e241ba0698e3d76d`；models：
`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`；validation：
`fbabacff11e25c3e14a6dfd2c9b39bad345bd5f7bc9f7574e5b0eb9b838eb8a7`；environment：
`01612603825253f7dc03632cfde74c91df2dbff028da10a441838b13835ae850`。

required failure 非零，P9 两轮同指纹 exact 按停止条件未启动。

## 4. 最新遗漏审计

| 审计项 | 状态 | 剩余工作 |
|---|---|---|
| 主工具 backend 映射 | 已覆盖 | 40 个主能力均有活动 case |
| amount/几何参数 | 未完成 | 10 个 anchor、6 个 Crop 参数 |
| canonical + 两个 holdout | 未完成 | 40/40 工具不足三个不同 source |
| 主效果 exact | 未完成 | 5/40 失败 |
| Exact 增量 | 未完成 | 8/69 失败 |
| model-specific contract | 已完成 | 22/22，0 pending |
| model runtime invocation | 已完成 | 18/18 |
| current-build UI evidence | 已完成 | 16/16，含 region hash |
| UI pixel | 未完成 | 0/16 |
| Native interaction | 未完成 | 9/10，缺 preset |
| Browser interaction | 未完成 | canonical 8/10；仅 multi 有新 1/1 |
| 真实 SQLite catalog schema | 已完成 | 与 Native 结构一致、无兼容层 |
| 非 catalog persistence | 证据不足 | history/layer/mask/workflow/preset 未完成 Native roundtrip |
| 隔离虚拟屏幕/输入 | 未具备 | 因此未调用 Computer Use |
| 同指纹 A/B 两轮 | 未执行 | 单轮 exact 尚非 36/36 |

## 5. 下一步严格优化顺序

1. 先建立真正独立的 macOS VM、独立登录会话或可证明路由隔离的虚拟显示与虚拟输入；Luminar 全屏后才
   允许 Computer Use。无法证明隔离时继续保持现状。
2. 在隔离环境一次性补 40 个工具的 holdout A/B、10 个 amount anchor、6 个 Crop 参数以及 Native preset
   observation；所有输入、参数、AX、截图、preview/export 和 hash 同批绑定。
3. 取得来源可信的真实 `.lnpc` 后，只实现当前唯一格式；完成 Native 和 Browser preset 10/10，不保留
   `.lnp/.lnpc` 历史双格式。
4. 把新的 DPR2 recorder 扩展到其余 9 个 Browser 合同；每项都记录 event、API/project readback、DOM/AX、
   screenshot、network、console、trace 和 export hash，最终生成同一 build 的 10/10 汇总。
5. 有两个 Native holdout 后，按 Sky Replace/Blue Hour → Sunrays → Depth Volume → Face AI →
   Structure/AI Enhance/Landscape 顺序校准。每次只改一个共享根因，并依次跑 canonical、holdout A/B、
   40 主 case、69 Exact；阈值保持不变。
6. 以 16 状态 diff 聚类修复 UI 共享根因：字体与图标、catalog/preset 密度、工具内容布局、dialog、
   HDR/Focus/Panorama 完成页。任何 frontend hash 变化都重录 16/16 evidence 和 pixel。
7. 在 Native disposable catalog 中创建可识别 layer/mask/history/workflow/preset 状态，只读对比数据库变更，
   解码 `img_history_states.data_wide_ch` 并做 roundtrip。证据确认后一次性删除对应 JSON primary 和重复
   history projection；不引入迁移兼容层或双写。
8. 只有 scope 0、主效果 40/40、Exact 69/69、UI 16/16、Native/Browser 10/10、持久化 roundtrip 全绿，
   才运行 exact 36/36；第一轮全绿后再执行两个独立 run 目录的同指纹 A/B。两轮 required failure 均为 0
   才能声明本报告范围内的绝对对齐。

## 6. 权威 artifact

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r13-final-20260831/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/native-isolation-preflight-r13.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-r13.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-runtime-audit-r13.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-r13-multi-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-r13-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/luminar-catalog-schema-r13.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/persistence-storage-audit-r13.json`。
