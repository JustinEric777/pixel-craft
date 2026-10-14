# Luminar Neo 绝对对齐 R10 执行报告

更新时间：2026-08-29  
对齐目标：本机 Luminar Neo 1.28.0 (23071)  
产品范围：免费、本地、可执行的照片编辑、目录、预设、图层、遮罩、多图工作流和导出。付费、商店、账户、云服务、教程与帮助不在范围内。

## 1. 最终结论

本轮完成了所有在现有证据和输入隔离约束下可以安全完成的实现、回归和门禁执行，但仍不能声明“绝对对齐”。修正后的单轮 exact gate 为 35 项中 30 项通过、5 项失败；因此没有执行 release A/B 两轮。

最终失败门禁：

1. `output-parity`：主效果 40 项中 35 项通过、5 项失败；
2. `exact-incremental-parity`：增量效果 69 项中 61 项通过、8 项失败；
3. `ui-execution-evidence`：现有 16 项证据的 frontend hash 已过期；
4. `ui-parity`：现有候选 16 项中 0 项达到像素阈值；
5. `interaction-execution`：正式 Browser 仍为 8/10，且缺少 1 项 Native observation。

权威报告：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r10-single-final-corrected.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r10-single-final-corrected-20260829/parity-report.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r10-single-final-corrected-20260829/exact-incremental-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r10-single-final-corrected-20260829/ui-execution-evidence.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-r10-single-final-corrected-20260829/interaction-execution.json`

## 2. 执行前后对比

| 项目 | 执行前 R9 | 执行后 R10 | 结论 |
|---|---:|---:|---|
| exact required gate | 31/35 | 30/35 | frontend 发生有效修改，旧 UI build evidence 被正确判 stale，因此总门禁暂降 1；不是将旧证据冒充为当前证据 |
| 主效果 | 35/40 | 35/40 | 无回归；尚未关闭 5 个结构性效果 |
| exact incremental | 56/69 | 61/69 | 净关闭 5 个失败 |
| 活动模型 contract | 22/22 | 22/22 | 0 pending，exact gate passed |
| 模型调用审计 | 17/17 | 18/18 | 当前主集 18 个 model-backed case 全部实际调用通过 |
| Native interaction | 9/10 | 9/10 | 仍缺 preset import 的全屏 Native observation |
| 正式 Browser interaction | 8/10 | 8/10 | 当前构建已实测 preset 和三类多图工作流，但尚未生成满足 DPR/build/全 artifact 约束的新正式 execution |
| UI execution | 16/16 | 0/16 current-build | 旧证据被 frontend hash 正确失效 |
| UI pixel | 0/16 | 0/16 | 未达到 MAE/changed-pixel 门禁 |
| SQLite schema | passed | passed | schema 155、29 objects、26 tables、结构 hash 不变，兼容层为空 |

本轮关闭的 5 个增量失败：

- `default_effects` amount `+1`；
- `default_effects` amount `-1`；
- `vignette` amount `+1`；
- `vignette` amount `-1`；
- `radiance` amount `1`。

## 3. 已完成的实现

### 3.1 确定性效果

- Default Effects 改为按负值、低正值和高正值分段的连续明度/对比度响应；
- Vignette 增加正负方向不同的 feather、指数和明暗合成响应；
- Radiance 保持现有 `0.4` canonical 响应，在高值区间使用颜色矩阵连续插值；
- 未加入 filename、case id、输入 hash 或 reference 特判；
- 未放宽 MAE/SSIM 阈值。

### 3.2 预设合同

- 浏览器使用真实 Luminar `.lnp` 目录中的 `template.lmps`，不构造伪 `.lnpc`；
- 增加“选择预设 → preview endpoint → 显式应用预设 → 编辑历史”的真实路径；
- 已验证本地预设在 API 进程重启后仍可见；
- interaction fixture 名称从错误的 `canonical-lnpc` 改为 `canonical-lnp-package`。

### 3.3 多图工作流

- HDR 合并、焦点堆叠、全景拼接均使用各自标准三图 fixture 完成 preview 和 export；
- 修复三条工作流之间复用旧 session、preview、status 和 export 状态的问题；
- 切换工作流现在统一通过父级 reset，旧结果不会泄漏到下一条工作流。

### 3.4 Browser viewport 合同

- 正式合同明确拆分为 logical `1440×900`、DPR `2`、physical `2880×1800`；
- builder 和 validator 不再接受含义不清的单一 `viewport` fallback；
- 旧 Browser evidence 会因 DPR、physical viewport 或 frontend hash 不一致而 fail closed。

### 3.5 Catalog 和证据隔离

- 已确认旧 UI capture 的 catalog 含 44 个重复照片项目，不能用于视觉校准；
- 本轮通过独立 `ZPIXEL_DATA_ROOT` 创建干净 catalog，并真实导入 46 张不同照片；
- 曾尝试在产品层复用同一路径项目，但 exact gate 发现它会让批处理 case 编辑栈串案；该实现已完整回退；
- 后续必须通过“每轮独立数据根目录 + 一次性 fixture seed”解决 UI 证据污染，不改变项目创建语义。

## 4. 验证结果

- Ruff：通过，0 findings；
- Python：378 passed，只有 Starlette/httpx 弃用警告；
- 前端：42 passed；
- 前端 production build：通过；
- AI model module static validation：0 blocking findings；
- model contract：22 valid、22 model-specific validated、0 pending；13 个 `ort-smoke-passed`、9 个 `inference-validated`；
- 当前主集 model invocation：18/18 passed、18 capabilities、16 logical models、0 active contract pending；
- SQLite：schema 155、29 objects、26 tables、结构 hash `7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79`、`compatibility_layers=[]`；
- corrected exact fingerprint：release `cb08e4429f04de0e74fcf9993aed4d4ae41b00c5af70afd68e6f8c2efd1ef606`、source `225080c4e41241ab1cf81526bebb240bfa39e6f1c73235e28af7e4a07cf5023b`、models `84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`、validation `fbabacff11e25c3e14a6dfd2c9b39bad345bd5f7bc9f7574e5b0eb9b838eb8a7`、environment `d59fdf4f82c9ffc2adcb409f9dbb2dd73cab69f2c4c5f0ac6ffcf94132a391d8`。

## 5. 当前明确遗漏

### 5.1 主效果 5 项

| capability | amount | MAE | SSIM |
|---|---:|---:|---:|
| `face_ai` | 0.4 | 0.030175 | 0.984125 |
| `depth_volume` | 0.4 | 0.069188 | 0.960300 |
| `blue_hour` | 0.4 | 0.039456 | 0.975336 |
| `sky_replace` | 0.4 | 0.039682 | 0.973711 |
| `sunrays` | 0.4 | 0.053714 | 0.956221 |

### 5.2 增量效果 8 项

| capability | amount | MAE | SSIM |
|---|---:|---:|---:|
| `face_ai` | 1.0 | 0.039460 | 0.968162 |
| `sunrays` | 1.0 | 0.133299 | 0.798667 |
| `structure_ai` | 1.0 | 0.039660 | 0.980043 |
| `ai_enhance` | 1.0 | 0.061526 | 0.951811 |
| `depth_volume` | 1.0 | 0.140078 | 0.841479 |
| `blue_hour` | 1.0 | 0.072455 | 0.848761 |
| `landscape_enhancer` | 1.0 | 0.046846 | 0.986967 |
| `face_ai` | 0.5 | 0.048759 | 0.963466 |

这些失败不能通过单一 amount scalar 安全关闭。Sky/Blue Hour 需要 sky/foreground segmentation；Sunrays 需要遮挡和体积光；Depth Volume 需要深度分区重照明；Face AI 需要面部区域契约；Structure、AI Enhance、Landscape 需要 full-range model-specific response 和 holdout。

### 5.3 UI 与交互证据

- 当前 in-app 隔离浏览器默认 DPR 2 时逻辑视口为 `1280×720`；强制 `1440×900` 后 DPR 变为 1，无法同时满足正式合同；
- 没有证明可与用户外设完全隔离的 Native Computer Use 会话，因此没有重新控制 Luminar Neo；
- 用户要求 Native 采样时 Luminar 必须全屏，当前仍严格保留该前提；
- 当前 frontend build hash 为 `26f7428fe4b0282bc4771855fa24dc51e3d69aa36cdfcc7012c3924c9948a487`，旧 16/16 UI execution 因 stale build 正确失效；
- 正式 Native interaction 仍缺 `preset-import-preview-apply`；
- 正式 Browser execution 仍缺当前 build 的 preset 与 multi-image 两条完整 artifact record。

## 6. 下一步严格执行顺序

1. 准备真正隔离的 macOS 会话：独立登录会话、VM 或独立远程桌面；确认虚拟显示器与鼠标不会影响用户外设。将 Luminar Neo 全屏后补录 preset Native observation，并只重录合同变化项。
2. 为 UI capture 增加显式 fixture seed：每个 run 使用全新 `ZPIXEL_DATA_ROOT`，一次导入 46 张 canonical 照片，验证 count、唯一 source hash 和 collection 后才允许截图。
3. 在能同时固定 logical 1440×900、DPR 2、physical 2880×1800 的隔离 Browser 中重录当前源码的 16 项 screenshot/DOM/AX/build evidence；不得复用旧截图。
4. 以 clean fixture 的 16 项差异重新分组修 UI：先全局 shell/三栏宽度/字号与间距，再 canvas fit/crop，再 catalog/preset/workflow/layer/tool 状态；每次 frontend hash 变化后重录全部 16 项。
5. 生成当前 build 的 Browser 10/10 正式 execution；本轮已实测的 preset 和三类多图流程仍需补 final screenshot、DOM、AX、network、console、API readback 和 Native link。
6. 效果校准顺序：Sky Replace + Blue Hour 共用 sky mask；Sunrays；Depth Volume；Face AI；最后 Structure/AI Enhance/Landscape full-range。每项至少 canonical + 两个 holdout，ONNX 优先、OpenVINO IR 仅作已验证 fallback。
7. 主效果达到 40/40、增量达到 69/69、UI 达到 16/16、Native/Browser 达到 10/10 后，重新运行单轮 exact 35/35。
8. 只有单轮 exact required failure 为 0，才冻结全部 fingerprint 并执行 release A/B 两轮；两轮都为 35/35 后才能声明绝对对齐。

## 7. 停止条件

- 不降低 MAE/SSIM 或 UI 阈值；
- 不增加 filename、case id、fixture hash 特判；
- 不创建伪 `.lnpc`；
- 不增加 JSON catalog 或 JSON/SQLite 双写；
- 不复用 stale frontend evidence；
- 不在共享输入设备上运行 Native Computer Use；
- 不在单轮 35/35 前运行 A/B 或发布绝对对齐声明。
