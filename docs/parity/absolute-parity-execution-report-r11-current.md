# Luminar Neo 绝对对齐 R11 执行报告

更新时间：2026-08-29  
对齐目标：本机 Luminar Neo `1.28.0 (23071)`  
产品范围：免费、本地、可执行的照片编辑、目录、预设、图层、遮罩、多图工作流和导出。付费、商店、账户、云服务、教程、帮助、推广与授权购买不在范围内。

## 1. 最终结论

R11 已完成现有证据、隔离条件和不允许伪造 reference 的约束下可以安全完成的实现与验证，但仍不能
声明绝对对齐。单轮 exact 为 **30/36 通过、6 项失败**；其中 35 项与 R10 同口径，仍为
30/35，新增第 36 项是 `absolute-scope-coverage` 严格覆盖门禁。由于 required failure 不为 0，
没有运行 release A/B。

失败门禁：

1. `absolute-scope-coverage`：59 个范围缺口；
2. `output-parity`：主效果 35/40；
3. `exact-incremental-parity`：扩展效果 61/69；
4. `ui-execution-evidence`：当前 frontend build 正式证据 0/16；
5. `ui-parity`：16 个状态全部未达到像素阈值；
6. `interaction-execution`：正式 Browser 8/10，Native 9/10，且 Browser 环境不满足 DPR/物理视口合同。

权威报告：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r11-single-final-20260829.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r11-single-final-20260829/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-scope-coverage-r11-p0.json`；
- `docs/parity/in-scope-feature-matrix.md`。

## 2. 执行前后对比

| 项目 | 执行前 R10 | 执行后 R11 | 结论 |
|---|---:|---:|---|
| exact required gate | 30/35 | 30/36 | 新增严格覆盖门禁；原 35 项仍为 30/35 |
| 主效果 | 35/40 | 35/40 | 无回归；5 个空间/语义效果未安全改动 |
| exact incremental | 61/69 | 61/69 | 无回归；8 个 full-range 失败未安全改动 |
| 严格范围缺口 | 未设置 gate | 59 | 10 个锚点、40 个 holdout、6 个裁切参数、1 Native、2 Browser |
| 模型 contract | 22/22，0 pending | 22/22，0 pending | 通过 |
| 活动模型调用 | 18/18 | 18/18 | 16 个实际调用模型，0 active pending |
| Native interaction | 9/10 | 9/10 | 仍缺真实 preset collection import |
| Browser interaction | 8/10 | 8/10 正式；clean fixture 功能路径通过 | 正式证据仍缺 2 项且环境不合格 |
| UI execution | 0/16 current-build | 0/16 current-build | R11 hash 已变化，旧证据继续 fail closed |
| UI pixel | 0/16 | 0/16 | 尚未校准；最低状态 MAE 0.031498，最高 0.186925 |
| clean UI fixture | 无正式 seeder | 两个独立 data root 均 46/46 唯一 | semantic fixture fingerprint 完全相同 |
| 前端产品范围 | 仍可能暴露未分组工具 | 只显示显式 40 项与三类本地合并工作流 | 排除项不再自动进入工具侧栏/更多面板 |
| Python tests | 378 passed | 382 passed | 增加 4 个严格门禁/夹具测试 |
| frontend tests | 42 passed | 43 passed | 全部通过 |
| SQLite | passed | passed | schema 155、26 表、无兼容层 |

R11 的主要进展不是用单张 reference 把数值调绿，而是把“最低分母通过”和“范围完整”拆开：过去
40/69/16/10 的最小集合无法证明每个参数和语义输入都被覆盖；现在这些缺口会直接阻塞 exact。

## 3. 已完成的实现

### 3.1 严格范围门禁

新增 `scripts/validate_absolute_scope_coverage.py` 并接入 exact gate。它联合检查 40 个显式工具、参数
schema、主效果、exact queue、UI 状态、Native reference、Browser execution 和 10 个交互合同，禁止以下
情况继续隐藏：

- 工具有主用例但没有足够 amount 锚点；
- 只有 canonical、没有两个不同输入 holdout；
- schema 参数从未出现在任何用例；
- UI 状态集合只在某一个 manifest 中存在；
- Native 或 Browser 交互缺项。

当前机器报告为 59 个问题：10 个工具缺完整 exact amount 锚点，全部 40 个工具少于 3 个不同输入，
`crop_ai` 缺 6 个几何参数用例，Native 缺 1 项，Browser 缺 2 项。

### 3.2 干净、可重复的 UI 证据夹具

新增 `scripts/prepare_ui_evidence_fixture.py`：

- 只接受位于测试输出目录下的全新、空 data root；
- 通过公开 application service 导入冻结的 46 张 canonical 照片，不直接写 SQLite；
- 拒绝重复 content、错误数量和重复运行到非空 root；
- 记录 source hash、asset/project id、SQLite 文件与 schema；
- 输出不受随机 project id 和根目录影响的 semantic fixture fingerprint。

两个独立 data root 均得到 46 条记录、46 个唯一 source hash，fingerprint 都是
`c642001438c18634e41c56d798c2ca83f634b5b9ca371ecd21941e58d9e68799`；
SQLite schema hash 均为 `7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79`，
`compatibility_layers=[]`。

### 3.3 UI capture 计划去污染

`test_data/parity/ui-browser-capture-plan.json` 已改为：

- 不含机器绝对路径；
- 不在每个状态重复导入同一图片；
- 从 clean catalog 双击固定照片进入编辑器；
- 不用固定 sleep 作为正确性条件；
- 多图只使用相对 canonical fixture，并保留独立 workflow reset。

目录照片现在支持双击进入编辑器。内置浏览器实际验证了 clean catalog 为 46 张、指定照片可双击进入
编辑器、更多面板只有 HDR/焦点堆叠/全景拼接。该验证是功能证据，不冒充 DPR2 正式像素证据。

### 3.4 产品范围收口

- “更多”面板移除提升分辨率、修复等排除项，只保留三类本地多图工作流；
- 工具侧栏不再把所有未分组 backend capability 自动暴露为“更多工具”；
- 当前 UI 只渲染 `configs/ui/editor.json` 显式配置的 40 个 in-scope 工具；
- backend 代码没有为了 UI 隐藏而增加历史兼容分支。

### 3.5 模型与 SQLite 守护

- model module 静态检查：0 blocking findings；
- 22/22 model-specific contract 通过，0 pending；
- 活动候选调用 18/18 通过，涉及 16 个实际调用模型；
- `luminar_effect_parity` 保持独立 pending/像素门禁，不把 contract 通过误报成效果通过；
- SQLite schema 155、29 objects、26 tables，结构 hash 未变，`compatibility_layers=[]`；
- 没有 JSON catalog、JSON/SQLite 双写、旧 schema fallback 或伪 `.lnpc`。

## 4. 未实施的危险方向与原因

对 Structure、AI Enhance、Landscape 的高区间做过只读标量外推诊断，最优 MAE 仍分别约为
0.03713、0.05970、0.03186，不能稳定过阈值；Face、Depth、Blue Hour、Sky Replace 和 Sunrays
的失败也具有明确空间/语义特征。当前又缺少每项 canonical + 两个 holdout 的 Native reference。

因此 R11 没有：

- 用单一 amount 系数拟合 canonical；
- 增加 filename、case id、input hash 或 fixture 特判；
- 降低 MAE/SSIM/UI 阈值；
- 把内置预设应用证据改名成预设集合导入证据；
- 构造 Luminar 未验证的 `.lnpc`；
- 在未证明隔离的会话中控制本机 Luminar 或用户鼠标键盘。

## 5. 最终验证结果

- Ruff：通过；
- Python：382 passed，1 个 Starlette/httpx 弃用警告；
- 前端：43 passed；
- frontend production build：通过；
- frontend build hash：`7e6bda45870069d758e8e8e7662606fe5ee70bf8fe5da2ee25233d76f4f29216`；
- exact：30/36，blocked；
- release fingerprint：`a33c467548251b7f6c7dc145f5a68ffd75c3ce7fe3c5a502f4f9987165eced72`；
- source fingerprint：`10d57adc6e2d6988b4692d86e7e8978aa184584607007d8177f67bfd4c53cca0`；
- model fingerprint：`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`；
- validation fingerprint：`fbabacff11e25c3e14a6dfd2c9b39bad345bd5f7bc9f7574e5b0eb9b838eb8a7`；
- environment fingerprint：`d59fdf4f82c9ffc2adcb409f9dbb2dd73cab69f2c4c5f0ac6ffcf94132a391d8`。

## 6. 当前明确遗漏

### 6.1 效果像素

主效果仍失败 5 项：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。
Exact 增量仍失败 8 项：Face 1.0/0.5、Sunrays 1.0、Structure 1.0、AI Enhance 1.0、
Depth 1.0、Blue Hour 1.0、Landscape 1.0。数值与 R10 一致，证明 R11 UI/证据改造未使效果回归。

### 6.2 范围完整性

- 缺 exact amount 锚点：Clone、Color Transfer、Complex Bleach、Crop、Deblur、Dodge & Burn、
  Erase、LUT、Skin Smooth、Sky Replace；
- 40 个工具全部尚未达到 3 个不同输入；
- Crop 缺 crop box、ratio、rotation、straighten、flip x/y 的正式效果用例；
- 当前 40/69 是最小回归集合，不是“每个工具每个参数已绝对覆盖”。

### 6.3 UI 与交互

- 当前 build 的 UI 正式 execution 为 0/16；旧 16 条因 build hash stale 被正确拒绝；
- 现有 16 个候选与 Native reference 均未达到像素阈值；
- Browser 环境缺完整字段，DPR=1 而合同要求 2，physical viewport 也不匹配；
- Browser 正式记录缺 preset import 和三类多图工作流；
- Native 缺 `preset-import-preview-apply`；现有 `.lnp` 目录不能被伪装成 Luminar 可导入的 `.lnpc` 集合；
- 当前没有证明可与用户外设隔离的虚拟显示/虚拟鼠标，所以没有触发 Native UI 控制。

## 7. 下一步严格优化顺序

1. **先解决隔离环境，不先改效果。** 准备独立 macOS 登录会话、VM 或独立远程桌面；验证虚拟显示和
   鼠标不会影响用户外设，Luminar 全屏、版本 1.28.0 (23071)、locale zh-Hans 后才允许采样。
2. **生成完整 effect reference 矩阵。** 对 40 个工具分别补到 canonical + 两个语义 holdout；连续
   amount 使用 0/0.25/0.4/0.5/0.75/1，支持负值时增加 -1/-0.5；补齐 10 个缺锚点工具与 Crop
   六个几何参数。每条都保存 source reset、preview/export、输出 hash 和重复导出一致性。
3. **补真实 preset collection。** 只使用由 Luminar 生成或原生接受、provenance 完整的 `.lnpc`；补录
   Native 全屏 import/preview/apply/restart persistence，再生成 Browser 对应正式 record。
4. **按共享视觉根因校准。** 先 Sky Replace + Blue Hour 的 sky/foreground/horizon/edge/relight；再
   Sunrays 的遮挡与 falloff；Depth 的近中远重照明；Face 的区域/背景保护；最后
   Structure/AI Enhance/Landscape 的多频 full-range 响应。每次要求 canonical 改善且两个 holdout
   不回归。
5. **重录当前 build UI 16/16。** 使用 clean fixture，在能同时固定 logical 1440×900、DPR2、
   physical 2880×1800 的浏览器中生成截图、DOM、AX、network、console、fixture 和 build hash；然后按
   shell → catalog/preset → canvas/crop → layer/tool/workflow 的顺序校准像素。
6. **完成 Browser 10/10。** 特别补 preset import 与三类多图，所有记录都必须链接同 id Native
   observation，事件、API readback、最终截图和持久化完整。
7. **再跑单轮 exact。** 目标是新增覆盖门禁在内 36/36；在此之前不运行 A/B。
8. **最后跑同指纹 A/B。** 两轮 source/model/reference/fixture/environment 完全一致且 required failure
   都为 0，才允许在本文限定范围内声明绝对对齐。

## 8. 停止条件

- 不降低任何像素阈值；
- 不增加 case/hash/文件名特判；
- 不创建伪 `.lnpc`；
- 不增加 JSON catalog、双写或历史 schema fallback；
- 不复用 stale frontend evidence；
- 不在共享输入设备上运行 Native Computer Use；
- 不在单轮 36/36 前运行 A/B 或声明绝对对齐。
