# Luminar Neo 1.28 本地核心严格对齐执行报告（R12）

执行日期：2026-08-30  
目标应用：本机 Luminar Neo `1.28.0 (23071)`  
执行 run：`alignment-r12-single-final-20260830`  
实施计划：`docs/parity/absolute-parity-optimization-plan-current.md`  
范围：免费、本地、可执行的目录、预设、编辑工具、图层、遮罩、多图工作流和导出  
排除：付费、商店、账户、云服务、教程、帮助、推广和授权购买流程

## 1. 结论

R12 已按计划的准入、停止和证据规则执行。单轮 exact 从 R11 的 `30/36` 提升到 `31/36`，
当前源码 UI 正式执行证据从 `0/16` 提升到 `16/16`；UI 平均 MAE 从 `0.0776026727` 降到
`0.0700274096`，16 个状态中 12 个改善、4 个不变、0 个回归。

仍不能声明与 Luminar Neo 绝对对齐。最终单轮 exact 为 `31/36`，5 个 required gate 失败；scope
仍有 59 项缺口，主效果仍为 `35/40`，Exact 增量仍为 `61/69`，UI pixel 为 `0/16`，正式交互为
`8/10`。由于单轮未达到 `36/36`，按计划没有执行 P9 的同指纹 A/B 两轮。

Native 采样未执行。机器预检没有发现独立虚拟显示，也没有独立虚拟键盘/鼠标或输入路由的证明。
Computer Use 本身不能证明外设隔离，因此未启动、切换或控制 Luminar Neo，现有 Native reference 和
用户外设保持不变。

## 2. 执行前后对比

| 维度 | R11 执行前 | R12 执行后 | 结论 |
|---|---:|---:|---|
| exact required gate | 30/36，6 failed | 31/36，5 failed | UI execution evidence 转为通过 |
| scope coverage | 59 issues | 59 issues | Native reference 前提未满足，未伪造证据 |
| 机器 worklist | 无统一逐项队列 | 95 项当前 worklist | 96 项基线中关闭 1 项 UI execution |
| 主效果 | 35/40 | 35/40 | 5 项仍失败 |
| Exact 增量 | 61/69 | 61/69 | 8 项仍失败 |
| 活动 model contract | 22/22 | 22/22，0 pending | 保持通过 |
| model-backed 实际调用 | 18/18 | 18/18 | 保持通过 |
| Native interaction | 9/10 | 9/10 | preset collection 缺真实 Native 证据 |
| Browser interaction | 8/10 | 8/10 | preset 和正式三工作流证据仍缺 |
| UI execution evidence | 0/16 current-build | 16/16 current-build | screenshot/DOM/AX/fixture/build hash 完整 |
| UI pixel | 0/16 | 0/16 | 全部状态仍超过 exact 阈值 |
| UI 平均 MAE | 0.0776026727 | 0.0700274096 | 下降约 9.76% |
| SQLite catalog | passed | passed | schema 155，29 objects，26 tables，无兼容层 |
| Python tests | 382 passed | 384 passed | 新增 evidence/worklist 测试 |
| Frontend tests | 43 passed | 43 passed | 无回归 |

用户最初提供的旧报告为主效果 `36/45`；R11 在 R12 开始前已冻结为当前活动矩阵 `35/40`。本报告的
“执行前后”使用紧邻本轮的 R11 权威基线，避免混合不同 case 总数。

## 3. 分阶段执行结果

### 3.1 P0：基线、worklist 和证据合同

- 新增 `scripts/build_absolute_alignment_worklist.py` 和单元测试；
- 生成 R12 基线 worklist：96 项；
- 最终 worklist：95 项；
- worklist 保存 scope、主效果、Exact、UI、交互各自的失败职责和输入文件 SHA-256；
- UI fixture 现在强校验真实 46/46 catalog、46 个唯一 source hash、collection、单图 source hash 和
  fixture fingerprint，并绑定到每个 UI 状态。

当前 worklist 构成：scope 59、主效果 5、Exact 增量 8、UI pixel 16、交互 7，共 95 项。

### 3.2 P1：Native 全屏隔离预检

只读预检结果：

- 当前 CoreGraphics active display count 为 0；
- 未发现可证明独立路由的虚拟显示；
- 未发现可证明独立路由的虚拟键盘/鼠标；
- Native UI 控制许可为 false；
- sampling queue 与 interaction observation 仅执行 dry-run/preflight；
- 未传入 `--allow-ui-control`，未调用 Computer Use。

状态为 `blocked-no-isolated-input`，符合“没有隔离就保持现状”的要求。

### 3.3 P2/P3：reference、范围和效果

59 项 scope 缺口未被人工关闭：

- 10 个工具缺 exact amount anchor；
- 40 个工具缺 canonical 之外的两个不同 source holdout；
- Crop 缺 6 个几何参数合同；
- Native 缺 preset import；
- Browser 缺 preset import 和正式三类多图 workflow。

本轮没有修改效果算法。P3 的硬前提要求先取得两个语义 holdout；当前 Native 隔离不成立时继续针对单张
canonical 调参会形成不可验证的过拟合，因此保持失败，不降低 MAE/SSIM，不增加
case/hash/filename 特判。

主效果剩余：

| 工具 | amount | MAE | SSIM |
|---|---:|---:|---:|
| Face AI | 0.4 | 0.0301750 | 0.984125 |
| Depth Volume | 0.4 | 0.0691883 | 0.960300 |
| Blue Hour | 0.4 | 0.0394560 | 0.975336 |
| Sky Replace | 0.4 | 0.0396822 | 0.973711 |
| Sunrays | 0.4 | 0.0537143 | 0.956221 |

Exact 增量剩余：Face AI 0.5/1.0、Sunrays 1.0、Structure AI 1.0、AI Enhance 1.0、Depth Volume
1.0、Blue Hour 1.0、Landscape Enhancer 1.0。

### 3.4 P4：模型合同和调用链

- `ai/model` validator：0 blocking findings；
- 活动 model contract：22/22 valid、22/22 model-specific、0 pending；
- 候选真实调用：18/18 case 通过；
- 16 个逻辑模型均有实际 invocation；
- 未做无证据 wrapper 重构，也未增加 backend fallback；
- 继续使用 ONNX primary、已验证的同逻辑 OpenVINO IR fallback。

模型 gate 已关闭，但它不能替代 Luminar 输出像素 gate。

### 3.5 P5：交互、预设和多图

Browser smoke 验证了 46 张 catalog 和 HDR/Focus/Panorama 三个入口；正式 UI 状态使用真实 HDR
`frame-1/2/3` fixture。in-app Browser 的文件选择器在 chooser event 前超时，没有改用系统文件选择器，
因此没有与用户鼠标键盘产生冲突。

正式 interaction 仍为 8/10，并有 7 个 issue：

- 当前 Browser interaction artifact 的环境字段不完整；
- DPR 和 physical viewport 不符合当前合同；
- frontend build hash 已过期；
- `preset-import-preview-apply` 缺 Native observation 和 Browser execution；
- `multi-image-three-workflows` 缺正式 Browser execution。

本机没有找到来源可信的原生 `.lnpc`。没有伪造容器，也没有实现 `.lnp/.lnpc` 双格式。

### 3.6 P6：current-build UI

完成新 workspace 和正式 16 状态采集：

- catalog：46/46，unique source hash：46/46；
- fixture fingerprint：`c642001438c18634e41c56d798c2ca83f634b5b9ca371ecd21941e58d9e68799`；
- logical viewport 1440×900，DPR 2，physical viewport 2880×1800；
- locale zh-Hans、timezone Asia/Shanghai、reduced motion；
- screenshot、DOM、AX、source capture 和各自 SHA-256 完整；
- frontend build hash：`66fa7257d0bcdd02308e90f73d3ecc3004eb490e76e90281965849f06a746d89`；
- UI execution evidence：16/16，0 issue。

Browser 实测暴露并修复两项 evidence 问题：fixture 只复制旧 id/hash、编辑页等待文本命中目录导航。
现在 builder 必须绑定真实 fixture manifest，capture plan 使用 `.workspace-edit` 可观察选择器。

共享 CSS 几何修改后，主编辑图像左边界由约 339px 调整到约 332px，与 Native 332px 对齐；工具栏宽度
调整到 307px，并为 collapsed/layer-library 保留状态级共享布局覆盖。最终 12 状态改善、4 状态不变、
0 状态回归。

像素 gate 仍为 0/16。阈值仍是 MAE ≤ 0.03 且 changed pixel ratio ≤ 0.02；没有降低阈值，也没有
事后裁剪失败区域。最接近的 edit 状态 MAE 为 0.0312671，但 changed pixel ratio 仍为 0.288085，
所以不能按观感判定通过。

### 3.7 P7：SQLite 单轨

- schema version 155；
- 29 个 schema object、26 张表；
- expected/actual structure hash 均为
  `7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79`；
- `compatibility_layers=[]`；
- UI workspace catalog 只有 `library/catalog.luminarneo`，没有 JSON catalog，也没有双写。

项目、workflow、job 和 manifest 当前仍有 JSON primary repository。这些不是 catalog 历史 fallback 或
双写，但其是否与 Native persistence 完全一致还缺权威 Native schema 证据。找到真实结构前不应把它们
猜测性塞入 catalog SQLite；若 Native 证据证明应合并，再一次性切换并删除 JSON primary path。

### 3.8 P8/P9：回归、exact 和 A/B

- Ruff：passed；
- Python：384 passed，1 个第三方 deprecation warning；
- Frontend：11 files、43 tests passed；
- Frontend production build：passed；
- SQLite schema、model contract/invocation：passed。

最终单轮 exact：31/36，5 个失败 gate：

1. `absolute-scope-coverage`：59 issues；
2. `output-parity`：35/40；
3. `exact-incremental-parity`：61/69；
4. `ui-parity`：0/16；
5. `interaction-execution`：8/10、7 issues。

`ui-execution-evidence` 已由 R11 的失败转为通过。因为 required failure 非零，P9 A/B 未执行。

本轮 fingerprint：release `821bbd3680b1388c0aad0417c6b9f9f8f5f7fc3931e228b5c3a05db382d058d4`，
source `92cc621f3fe27d9e5b97406b91e878a7ca67cb4a848442909158799842c67285`，models
`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`，validation
`fbabacff11e25c3e14a6dfd2c9b39bad345bd5f7bc9f7574e5b0eb9b838eb8a7`，environment
`74a0cef157fd581a280daec90a6df2f474bff03ecd2729092caf53ce41f0bb05`。

## 4. 最新遗漏审计

| 审计项 | 状态 | 说明 |
|---|---|---|
| in-scope 工具映射 backend | 已覆盖 | 40 个主能力均有 case |
| amount/参数范围 | 未完成 | 10 个 anchor、6 个 Crop 参数缺失 |
| canonical + 两个独立输入 | 未完成 | 40/40 工具不足 3 个 source hash |
| preview/export exact | 未完成 | 5 个主效果、8 个 Exact case 失败 |
| current-build UI artifact | 已完成 | 16/16 evidence，0 issue |
| current-build UI pixel | 未完成 | 0/16 |
| Native/Browser interaction | 未完成 | 9/10、8/10 |
| model-specific contract | 已完成 | 22/22，0 pending |
| model-backed invocation | 已完成 | 18/18 |
| SQLite catalog 单轨 | 已完成 | 无 JSON catalog/双写/兼容层 |
| Native project persistence 等价 | 证据不足 | JSON primary 是否偏离 Native 尚无权威 schema |
| P9 同指纹 A/B | 未执行 | 单轮 exact 非零失败 |
| 用户外设隔离 | 已遵守 | 未控制 Native、未操作系统文件选择器 |

## 5. 下一步严格顺序

1. 取得真正隔离的 macOS 会话/VM/远程桌面，证明独立虚拟显示与独立输入路由；Luminar 必须全屏。
2. 在该环境一次性采集 40 个工具的两个不同 source holdout、10 个 amount anchor、6 个 Crop 参数、
   preset Native interaction 和必要的真实 `.lnpc` provenance；无证据的项目继续 blocked。
3. 按 Sky/Blue Hour → Sunrays → Depth Volume → Face AI → Structure/AI Enhance/Landscape 的顺序，
   每项只做一类根因修改，并依次验证 canonical、holdout A/B、同域、40 主 case、69 Exact case。
4. 取得真实 preset collection 后一次性实现唯一格式；删除旧解析路径，不保留 `.lnp/.lnpc` 双格式。
5. 重录 current-build Browser interaction，补齐 preset 和 HDR/Focus/Panorama 三工作流的 events、API、
   project readback、DOM/AX、截图、网络、console 和 export hash，达到 Native/Browser 10/10。
6. 按共享 UI 根因继续校准字体/图标、catalog/preset、工具内容、对话框和多图完成页；每次 frontend hash
   变化都重录全部 16 状态，阈值保持不变。
7. 仅在取得 Native persistence schema 后决定 project/workflow/job 是否迁入 SQLite；需要迁移时一次性
   切换并删除 JSON primary repository，不增加 compatibility layer。
8. scope 0、40/40、69/69、UI 16/16、交互 10/10 后再跑 exact 36/36；单轮全绿后才执行两个不同
   run 目录的同指纹 A/B。两轮 required failure 都为 0 才能声明本报告范围内严格对齐。

## 6. 权威 artifact

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r12-single-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r12-single-final-20260830/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-alignment-worklist-r12-current.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/native-isolation-preflight-r12.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-r12-current.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-r12-current.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-r12.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-runtime-audit-r12.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/luminar-catalog-schema-r12.json`。
