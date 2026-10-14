# Luminar Neo 1.28 核心功能域完全收敛优化计划（R15，天空替换优先）

更新时间：2026-08-31  
目标应用：本机 Luminar Neo 1.28.0 (23071)  
执行基线：R14 最终证据与 alignment-r13-final-20260831 效果报告  
当前状态：计划已冻结，尚未执行 R15 实现与 Native 新采样

> 本计划只覆盖免费、本地且直接影响修图结果的核心能力：目录、40 个编辑工具、预设、图层、遮罩、
> history/compare/zoom/pan、多图工作流、持久化与导出。付费内容、商店、账户、云服务、教程、帮助、
> 推广和购买/授权流程明确排除。计划不保留历史兼容逻辑，不建立旧 schema/model/preset reader，
> 不允许 JSON/SQLite 双写，也不允许按 case id、文件名、输入 hash 或 reference hash 选择实现。

## 目录

- [1. 目标和完成定义](#1-目标和完成定义)
- [2. 已核实基线](#2-已核实基线)
- [3. 核心域收敛策略](#3-核心域收敛策略)
- [4. 硬约束与执行原则](#4-硬约束与执行原则)
- [5. 阶段依赖与里程碑](#5-阶段依赖与里程碑)
- [6. P0：冻结 R15 基线](#6-p0冻结-r15-基线)
- [7. P1：隔离全屏 Native 环境](#7-p1隔离全屏-native-环境)
- [8. P2：天空替换 Native 合同采样](#8-p2天空替换-native-合同采样)
- [9. P3：天空模型与效果管线收敛](#9-p3天空模型与效果管线收敛)
- [10. P4：天空 UI、交互与持久化](#10-p4天空-ui交互与持久化)
- [11. P5：天空域退出门禁](#11-p5天空域退出门禁)
- [12. P6：场景、天空与深度相邻域](#12-p6场景天空与深度相邻域)
- [13. P7：人像与全局增强失败域](#13-p7人像与全局增强失败域)
- [14. P8：其余 40 工具覆盖](#14-p8其余-40-工具覆盖)
- [15. P9：横向工作流、UI 与持久化](#15-p9横向工作流ui-与持久化)
- [16. P10：单轮 exact 与同指纹 A/B](#16-p10单轮-exact-与同指纹-ab)
- [17. 修改与验证矩阵](#17-修改与验证矩阵)
- [18. 停止、回退和阻塞规则](#18-停止回退和阻塞规则)
- [19. 最终遗漏审计](#19-最终遗漏审计)
- [20. 交付物](#20-交付物)

---

## 1. 目标和完成定义

### 1.1 总目标

以本机 Luminar Neo 1.28.0 (23071) 为唯一 Native 真值，在固定源码、模型、素材、reference、viewport、
locale 和环境指纹下，使本项目的核心 UI、核心交互和核心效果三条主线完全一致。模型、持久化和证据链是
实现并证明这三条主线一致所需的底层门禁，不作为降低 UI、交互或效果要求的替代结论。

“核心功能完全收敛”不是“按钮存在”或“模型能执行”，而是每个功能域同时满足以下八项：

| 域门禁 | 必须证明的事实 |
|---|---|
| Native 合同 | 控件、默认值、范围、状态转换、preview/export 均来自本机全屏 Native 证据 |
| 模型合同 | 输入颜色/尺寸/归一化、输出语义、后处理和 runtime 均 model-specific validated |
| 真实调用 | required/conditional 模型按真实编辑路径执行，trace 可审计且无静默 fallback |
| 效果 exact | canonical、两个不同 source holdout、参数 anchor 均过冻结的 MAE/SSIM/shape 门禁 |
| UI exact | 相关 UI 绑定当前源码 hash、DOM/AX、viewport、DPR、截图并过 pixel gate |
| 交互 exact | Native observation 与当前 frontend build 的正式合同都通过 |
| 持久化 | 重启后参数、素材、图层、遮罩、history 和导出结果按真实 Native 语义 roundtrip |
| 回归稳定性 | 窄测、全量测试、单轮 exact 和同指纹 A/B 两轮全部通过 |

任一项缺失，该功能域只能是 blocked 或 pending，不得声明“已完全收敛”。

### 1.2 三条同级 exact 主线

| 主线 | “完全一致”的含义 | 不能替代的弱证据 |
|---|---|---|
| 核心 UI | 核心页面、40 个工具面板、弹层/菜单、控件状态、字体、图标、颜色、间距、滚动、hover/focus/selected/disabled/loading/error 在冻结 viewport/DPR 下逐状态像素通过 | 只过当前 16 个代表状态、DOM 结构相似、人工截图检查 |
| 核心交互 | 鼠标/键盘/滚动/右键/拖拽的入口、状态转换、结果、undo/redo/reset、照片 history 隔离、layer/mask、preset、多图、compare/zoom/pan、export 与 Native 合同一致 | 只过当前 10 个横向合同、按钮可点击、API 返回成功 |
| 核心效果 | 40 个工具的默认、边界、参数曲线、素材、canonical、两个 holdout、preview/export 和保护场景均过 exact | 模型能跑、单张图相似、内部 E2E ready |

当前 16 个 UI 状态和 10 个 interaction contract 只是已经存在的基线子集。P0 必须从
inventory/ui-contract.json、configs/ui/editor.json、40 个 capability schema 和 Native observation 构建：

- core-ui-state-matrix-r15.json：去重后的全部核心 UI required states，分母记为 N；
- core-interaction-matrix-r15.json：去重后的全部核心交互 required contracts，分母记为 M。

N 和 M 必须在任何 UI/交互实现修改前冻结，后续不得删除失败项。它们分别并入现有 ui-parity 和
interaction-execution required gate，因此 exact required gate 总数仍为 37；改变的是两个 gate 内部的完整
case 分母，不是通过增加顶层 gate 稀释失败。

### 1.3 全局最终门禁

| 指标 | 最终要求 |
|---|---:|
| exact required gate | 37/37，连续两轮 required failure = 0 |
| absolute scope issue | 0 |
| 主效果 | 40/40 |
| Exact 增量 | 69/69 |
| holdout | 40/40 工具，每个至少 canonical + 两个不同 source |
| 参数覆盖 | 10 个缺失 amount anchor 和 6 个 Crop 参数全部关闭 |
| 核心 UI execution / pixel | N/N / N/N；现有 16/16 必须作为子集全过 |
| Native / Browser interaction | M/M / M/M；现有 10/10 必须作为子集全过 |
| 模型合同 / active invocation | 22/22 / 18/18 |
| persistence | 第 37 个 native-persistence-roundtrip gate 通过 |
| worklist | 0 |

现有效果阈值保持不变：默认效果 SSIM >= 0.98、MAE <= 0.03、shape 必须一致；UI 为
MAE <= 0.03 且 changed pixel ratio <= 0.02。不得为关闭失败降低阈值、缩小失败 region、替换 reference
或改变分母。Grain 继续使用已冻结的统计比较合同。

## 2. 已核实基线

权威现状来自：

- docs/parity/absolute-parity-core-convergence-execution-r14-2026-08-31.md；
- diagnostics/runs/alignment-r13-final-20260831/；
- diagnostics/scope-coverage-r14-final.json；
- diagnostics/interaction-execution-r14-final.json；
- diagnostics/ui-parity-r14-final.json；
- diagnostics/release-fingerprint-r14-final.json。

### 2.1 当前总览

| 维度 | 当前结果 | 结论 |
|---|---:|---|
| 主效果 | 35/40 | 5 个失败 |
| Exact 增量 | 61/69 | 8 个失败 |
| UI execution evidence | 16/16 | 完整，但不能替代 pixel exact |
| UI pixel | 0/16 | blocked |
| Browser 正式交互 | 5/10 | 当前 build 缺 5 项 |
| 模型合同 / active invocation | 22/22 / 18/18 | 必须持续守绿 |
| absolute scope issue | 59 | blocked |
| worklist | 94 | blocked |
| persistence | 缺 Native manifest | 第 37 个 gate blocked |
| Python / frontend | 392 / 43 passed | R14 回归基线 |

59 个 scope issue 已机器化：40 个工具缺两个不同 source holdout、10 个工具缺 Exact amount anchor、Crop 缺
6 个正式参数证据、Native preset interaction 缺 1 项、Browser scope 缺 2 项。R14 当前-build 交互报告另缺
photo-switch-history、preset-import-preview-apply、layer-lifecycle、mask-lifecycle 和 compare-zoom-pan。

### 2.2 当前效果失败

主效果 5 个失败：

| capability | MAE | SSIM |
|---|---:|---:|
| face_ai | 0.030175 | 0.984125 |
| depth_volume | 0.069188 | 0.960301 |
| blue_hour | 0.039456 | 0.975336 |
| sky_replace | 0.039682 | 0.973711 |
| sunrays | 0.053714 | 0.956221 |

Exact 8 个失败为 face_ai 两条、sunrays、structure_ai、ai_enhance、depth_volume、blue_hour 和
landscape_enhancer。这决定 R15 先关闭天空/场景/深度，再关闭人像和全局增强，最后守护其余已通过工具。

### 2.3 天空替换当前事实

1. canonical sky_replace 已有真实 reference，但 MAE 0.039682 / SSIM 0.973711，未过阈值；
2. run_sky_e2e_validation.py 当前 48/48 ready，其中 29 张 replaceable sky、19 张 no-detected-sky；
3. 该报告的 luminar_blackbox_parity 明确为 pending-reference-outputs，只证明内部管线可运行；
4. required 模型为 improved_sky_segmentator_v462_i8、horizon_align_i8；
5. conditional 模型为 skyinwater_v16_i8、human_clothes_exp13_v2、salient_object_improve_exp19_it150k；
6. 当前实现含 sky mask、地平线、前景保护、水面 mask、几何、边缘、反射、重光和天空调整，但未逐段闭环；
7. 原版安装 UI 合同列出 18 个正式控制项，所有 range/default 仍 pending-black-box-calibration；
8. SkyControls.tsx、configs/ui/editor.json 和 parameter-schema.json 的字段/default 当前不一致；
9. 候选公开了 sky_scale、horizon_blending 等原版 UI 合同未列出的控件，schema 又漏登多项已出现 UI 字段。

这些是天空域无法 exact 的正式阻断项，不是文档小问题。

## 3. 核心域收敛策略

| 优先级 | 功能域 | 直接关闭的当前失败 | 退出结果 |
|---|---|---|---|
| D1 | 天空替换 | sky_replace 主效果和天空合同缺口 | 冻结天空垂直切片 |
| D2 | 场景/天空/深度 | blue_hour、sunrays、depth_volume、landscape_enhancer | 冻结场景域 |
| D3 | 人像 | face_ai 主效果和两条 Exact | 冻结人像域 |
| D4 | 全局增强 | ai_enhance、structure_ai Exact | 冻结增强域 |
| D5 | 其余工具 | 40 holdout、10 anchor、6 Crop 参数 | 冻结 40/40 工具矩阵 |
| H1 | 横向产品链 | UI、交互、持久化、预设、图层、遮罩、多图、导出 | 进入 release exact |

每个域只在八项门禁全绿后冻结。后续修改共享基础算子时必须重跑所有已冻结域；若发生回归，本批次立即回退
或同步修复，不得把失败推迟到最终 exact。

~~~text
Native 全屏单变量采样
  └─ 控件/状态/preview/export/持久化真值
       └─ 合同与 case matrix 冻结
            ├─ 模型输入输出与 invocation trace
            ├─ 候选中间诊断
            └─ UI/交互状态
                 └─ 最小实现修正
                      ├─ 窄测
                      ├─ canonical + holdout + anchor exact
                      └─ preview/export/restart roundtrip
                           └─ 域退出门禁 → 冻结 → 下一域
~~~

## 4. 硬约束与执行原则

### 4.1 Native 采样

- Luminar 必须在目标显示器全屏、前台、固定 locale 和 disposable workspace；
- 只有 virtual_display、input_isolated、fullscreen、ui_control_allowed 均有证据时才允许 Computer Use；
- 虚拟屏幕但输入仍共享不满足准入；Computer Use 本身不能证明隔离；
- 没有独立显示与独立输入路由时，保持用户应用、窗口、鼠标和键盘不变，记录 blocked-no-isolated-input；
- 每次动作后重新读取最新 app state/AX，不复用旧 element index；
- 不进入付费、商店、账户、教程、帮助或推广页面。

### 4.2 实现

- 以真实调用路径和可见输出定位根因，不先重写图像引擎；
- 模型 ONNX 优先，OpenVINO IR 只作已验证兜底；required 模型失败必须 fail closed；
- runtime 不下载模型/素材，不硬编码机器路径；
- 不以 reference、case id、文件名、输入 hash 选择算法或参数；
- Native 未公开 mask 时，不把 candidate mask 冒充真值；
- 不建立历史兼容层。真实 persistence 证据完整后一次性切换，并删除 JSON primary、重复 projection、旧 reader；
- 每批改动必须映射到失败 case、缺失合同或证据缺口。

### 4.3 证据

每条 case 至少绑定 reference build、source/asset SHA-256、全部参数、preview/export、截图、viewport/DPR、
source/model/reference/environment hash、执行 trace 和指标。缺任一字段即 pending。R15 使用新 run 目录，
不覆盖 R13/R14。

## 5. 阶段依赖与里程碑

~~~text
P0 冻结基线
  ├─ Browser-safe：schema/UI 测试准备、诊断器、候选窄测
  └─ P1 隔离全屏环境
       └─ P2 天空 Native 合同
            ├─ P3 天空模型/效果
            └─ P4 天空 UI/交互/持久化
                 └─ P5 天空域退出
                      ├─ P6 场景/天空/深度
                      ├─ P7 人像/全局增强
                      └─ P8 其余 40 工具
                           └─ P9 横向工作流/UI/持久化
                                └─ P10 exact 37/37 + A/B 两轮
~~~

里程碑：

- M1：天空 Native 控件和参数真值冻结；
- M2：天空 canonical + holdout + anchor 全绿；
- M3：5 个主效果和 8 个 Exact 失败全部关闭；
- M4：40 工具范围缺口归零；
- M5：核心 UI N/N、核心交互 M/M（分别包含原 16/16、10/10 子集）、persistence 全绿；
- M6：同指纹 exact A/B 两轮 37/37。

## 6. P0：冻结 R15 基线

### 操作

1. 生成 R15 dry-run，冻结 37 个 required gate；
2. 冻结 40 主效果、69 Exact、现有 16 UI state、10 interaction contract、59 scope issue；
3. 保存 R14 权威报告 hash，不修改旧 artifact；
4. 从当前报告生成按 D1-D5/H1 分组的机器 worklist；
5. 新增 scripts/build_core_ui_state_matrix.py 和 scripts/build_core_interaction_matrix.py：只读取 Native UI
   inventory、editor config、capability schema 和现有合同，生成去重的完整 N/M required matrix；
6. 新增 validate_core_ui_state_matrix.py 和 validate_core_interaction_matrix.py，检查每个核心页面、40 个工具、
   唯一控件类型、横向工作流和状态变体都有责任项；
7. 冻结 N、M 和每条 responsibility；建立天空新 case namespace，Native 样本完成前不写 passed；
8. 审计 threshold、UI region、interaction contract 和顶层 37 gate 分母无漂移。

~~~bash
.venv/bin/python scripts/run_quality_gates.py --level exact --dry-run \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id alignment-r15-plan-baseline-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r15-plan-baseline.json

.venv/bin/python scripts/validate_absolute_scope_coverage.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/scope-coverage-r15-baseline.json
~~~

### 准出

R15 baseline 如实 blocked；顶层 37、效果 40/69 分母不变；N/M 完整矩阵已在实现前冻结，原 16/10 全部保留
为 required 子集；59 issue 和 94 worklist 全可追溯；每个失败已分配到唯一责任域；没有修改阈值、region、
reference 或旧 artifact。

## 7. P1：隔离全屏 Native 环境

### 允许方案

按优先级选择独立 macOS VM、独立登录会话 + 独立远程桌面、能证明显示和输入均独立路由的虚拟显示方案。
仅有虚拟屏幕或虚拟鼠标名称不算证据，必须证明它们不影响用户当前会话。

### 预检字段

native-isolation-preflight-r15.json 必须包含 session id、display id/bounds、scale、虚拟显示实现、输入实现/路由、
input_isolated、Luminar version/build、bundle id、locale、workspace、foreground、fullscreen、
ui_control_allowed、采集前后 screenshot hash 和用户主屏未变化证据。

~~~bash
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run --preflight
.venv/bin/python scripts/run_luminar_interaction_observations.py --dry-run
~~~

### Computer Use 纪律

1. 先读取 com.skylum.luminarneo 最新 app state 和截图；
2. 核对全屏、目标照片、目标工具和参数；
3. 优先 AX element；每次动作后重读 state；
4. AX 缺失时才用目标虚拟显示内坐标；
5. 退出全屏、丢前台、bounds 改变或隔离失效时，当前 attempt 立即 invalid；
6. 不改变用户主显示器、鼠标、键盘、剪贴板或常用 workspace。

### 准出

一条无副作用 observation 在独立环境成功，前后 display/input/fullscreen 指纹一致，用户当前会话无变化。
否则 P2、P4 Native、P9 persistence blocked，只继续 Browser-safe 工作。

## 8. P2：天空替换 Native 合同采样

### 8.1 冻结 18 个 Native 控件映射

| Native source id | 候选目标字段 | 必须标定 |
|---|---|---|
| Texture | asset_id | 默认空态、选择、切换 |
| Horizon | horizon_offset | 默认、范围、方向、几何响应 |
| Sky Vertical Offset | vertical_offset | 范围、单位、裁切 |
| Sky Horizontal Offset | horizontal_offset | 范围、单位、边界 |
| SkyFlip | sky_flip | 是否只翻转纹理 |
| SkyGlobal | sky_global | mask/global 语义 |
| FixGaps | fix_gaps | gap close 方向和结构 |
| Sigma | edge_refinement | Fix Details 实际响应 |
| Relighting | foreground_relight | 前景亮度/色彩响应 |
| Relighting Saturation | relight_saturation | 作用区和曲线 |
| Relight Human | relight_human | 人物专用权重 |
| Water | reflection_amount | 水面触发、方向、强度 |
| WaterBlur | reflection_blur | reflection-only 模糊 |
| SkyBlur | sky_blur | 天空 defocus |
| Sky Grain | sky_grain | 统计分布和重复性 |
| White | atmospheric_haze | haze 色彩/亮度 |
| Temperature | temperature | 暖冷方向和通道曲线 |
| SkyExposure | brightness | 曝光曲线和 clipping |

sky_scale、horizon_blending、rotation、contrast、saturation 当前没有对应的 Native UI 合同。P2 必须证明它们
是自动内部量、其他真实字段或候选自有字段；没有证据则从公开 UI/schema 删除或转成私有自动中间量。

### 8.2 source 场景

至少冻结十类不同 hash：开阔天空/地平线、树枝发丝电线、建筑硬边、天空前人像、水面、低对比雾天、
逆光高光、小面积天空、无天空室内、高天空占比且无明确地平线。canonical、holdout A、holdout B 必须不同，
另留两个从未参与调优的保护集。

### 8.3 素材

从本机合法 SkyTextures 选择至少四个不同 hash：蓝天、云层、日落暖色、强纹理天空。先用一个固定 asset
完成参数曲线，再以其他三个验证不依赖单一纹理。记录 asset id、相对路径、hash、尺寸和色彩空间。

### 8.4 单变量矩阵

连续控件采集 min / 25% / default / 75% / max；方向控件覆盖负端；checkbox 覆盖 off/on；Texture 覆盖
无选择、首次选择、切换、重新选择。每次只改一个控件，保存 before/after 全屏截图和 AX、显示值、preview、
export、undo/redo/reset、restart、全部 hash。同一 default 至少重复导出三次识别自然方差，但不放宽阈值。

### 8.5 可见 ROI

Native 未公开内部 mask 时不虚构真值。生成只读诊断 ROI：sky core、边界 3/8/16 px、foreground、human、
water/reflection、no-sky protection。ROI 只定位 mask、几何、重光、反射或色彩根因；release 仍以全图 exact
为硬门禁。新增 ROI hard gate 时，阈值须在看 candidate 前用 Native 重复方差冻结。

### 准出

18 控件 default/range/direction/disable/reset/undo/redo 不再 pending；source/asset/parameter/repeat 完整；
preview/export/restart 证据完整；候选自有 public 参数已证实、内部化或删除；无人工 passed。

## 9. P3：天空模型与效果管线收敛

### 9.1 逐段诊断

扩展 diagnose_sky_composite.py 和 run_sky_e2e_validation.py，为每条 case 输出：原图/纹理、raw sky 输出摘要、
restored mask、horizon、foreground/human、reflection mask、fitted texture、refined alpha、sky-only、
reflection-only、relight-only、final preview/export、model invocation trace。中间图仅用于候选诊断。

### 9.2 模型合同

| 模型 | 责任 | 核心验证 |
|---|---|---|
| improved_sky_segmentator_v462_i8 | sky probability | RGB/BGR、513 resize/pad、归一化、channel、restore |
| horizon_align_i8 | horizon angle | 224 输入、角度单位/方向、旋转中心、无地平线 |
| skyinwater_v16_i8 | reflection mask | channel 语义、无水面保护 |
| human_clothes_exp13_v2 | human protection | 五类合并、restore transform |
| salient_object_improve_exp19_it150k | foreground | mask 语义、与 human 的组合 |

wrapper 保持 load/preprocess/predict/postprocess/unload 分层；完整加载后才设置 loaded；cache 淘汰必须 unload。
required 模型失败抛诊断错误；conditional 模型只有在对应场景/控件启用时才影响输出。

~~~bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
~~~

### 9.3 根因顺序

1. 输入/色彩：EXIF orientation、RGB、gamma/linear、resize、preview/export 色彩空间；
2. sky mask：channel、restore、soft alpha、no-sky；
3. 几何：horizon、vertical/horizontal、flip、自动 scale/rotation、边界延拓；
4. refinement：Global、Close Gaps、Fix Details；
5. sky adjustments：blur、grain、haze、temperature、exposure；
6. relight：foreground/human strength/saturation；
7. reflection：地平线、映射、amount、blur、水面边界；
8. 最终合成：alpha、rounding、preview/export 编码。

当前 _foreground_relight 以 result - base 作为前景 delta，而 sky mask 外通常 result == base，实际前景重光可能
接近零。必须用 Native 单变量结果和 foreground ROI 证实后最小修正，不能凭函数名假定正确。

### 9.4 参数单一合同

P2 后以 parameter-schema.json 为公共字段/range/default 权威来源；editor.json 只保留布局；SkyControls 不再
维护冲突默认；API edit node、preview、export、preset、persistence 使用同字段/单位；增加 schema ↔ frontend
↔ service 一致性测试。无需建立通用代码生成框架。

### 9.5 窄测

~~~bash
.venv/bin/pytest -q tests/test_sky_compositor.py \
  tests/test_ai_effect_pipeline_helpers.py tests/test_execution_graphs.py \
  tests/test_api.py -k 'sky or horizon'

.venv/bin/python scripts/run_sky_e2e_validation.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/r15-sky-e2e.json

.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 --capability sky_replace --force \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/r15-sky-candidates \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/r15-sky-generation.json

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 --capability sky_replace \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/r15-sky-candidates \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/r15-sky-parity.json
~~~

每次改动只接受失败下降、根因变明确或回退。无指标收益的复杂化不保留。

## 10. P4：天空 UI、交互与持久化

### 10.1 UI

对齐工具组位置、图标/AI badge、折叠、Texture picker、Native section 顺序/标题、enable/disable、显示值、
范围/步长、reset、loading、错误态。只有 P2 证实的控件可公开。天空工具折叠/展开、picker、各 section、参数
状态、disabled/loading/error 均进入 P0 冻结的 N-state matrix；不得因它们比现有 16 个状态更难而降为诊断项。

### 10.2 正式交互

覆盖打开工具/picker、选择/切换/翻转、各 section 代表参数、reset/undo/redo、照片切换 history、layer/mask、
compare/zoom/pan、导出回读、restart 恢复、无天空/无模型/无素材 fail closed。所有合同进入 P0 冻结的
M-contract matrix。Browser 证据绑定同一 frontend hash；Native observation 绑定同一 build 和隔离环境。

### 10.3 preview/export

两者必须使用同一 effect graph 和参数合同；只允许显示缩放/编码差异。保存 preview/export pixel hash 和
去编码比较；PNG/JPEG 分别验证颜色空间、尺寸、metadata；Global=0、reset、undo 必须匹配 Native 语义。

### 10.4 persistence

在 disposable Native workspace 对 sky asset、18 参数、layer、mask、history、preview/export 做单变量
before/after snapshot 和 restart roundtrip。用 capture_native_persistence_delta.py 只读比较。字段映射完整后
一次性切换 active repository，并删除 JSON primary、projection、双写、旧 reader/migration。证据不完整时
保持 blocked，不猜 schema。

## 11. P5：天空域退出门禁

| 项目 | 准出 |
|---|---|
| Native 控件 | 18/18 default/range/state/单变量证据完整 |
| 模型 | 2 required + 3 conditional 合同和 invocation 正确 |
| canonical | MAE <= 0.03、SSIM >= 0.98、shape match |
| holdout | 两个不同 source 全绿，未调优保护集无回归 |
| asset | 四个不同 asset hash，不依赖单一纹理 |
| 参数 | 全部 public 控件的边界/default/方向 anchor 通过 |
| protection | 细边缘、人物、水面、小天空、无天空符合 Native |
| preview/export | 去编码后像素合同通过 |
| UI/interaction | 天空相关 N/M responsibility 全过，current-build + Native observation 全绿 |
| persistence | restart 后 asset/参数/layer/mask/history/export roundtrip |
| regression | 天空窄测、model validator、全量测试无回归 |

全部通过才标记 D1 frozen-passed。48/48 内部 E2E、单张 canonical 或人工观感不能单独准出。

## 12. P6：场景、天空与深度相邻域

按 D1 模板处理：

1. blue_hour：Native 默认/amount 曲线，分离天空、前景和全局冷暖；
2. sunrays：太阳位置、方向、遮挡、强度、无天空/无亮源保护；
3. depth_volume：depth 方向、归一化、前中后景曲线、无深度结构保护；
4. landscape_enhancer：校准 Exact anchor，确认不是通用 saturation/contrast 的粗替代；
5. 同时守护 sky_replace、fog、water_enhancer。

每工具 canonical + 两 holdout + min/default/max anchor；model-backed 必须有 invocation。准出时关闭相关 4 个
主效果失败和 4 个 Exact 失败，天空域无回归。

## 13. P7：人像与全局增强失败域

### 人像

face_ai 使用单人正脸、多人、侧脸、无脸 source，确认 detection box restore、作用区、amount 曲线、五官/皮肤
保护和 no-face identity；关闭 1 个主效果和两条 Exact。共享 human mask 修改后重跑天空人物保护。

### 全局增强

ai_enhance、structure_ai 先确认模型是语义分析还是实际增强，所有曲线来自 Native 单变量证据；用低纹理、
高纹理、人物皮肤、天空 source 校准，关闭两条 Exact。禁止 canonical 特判。

### 准出

主效果 40/40、Exact 69/69；D1/D2 无回归；人像/增强各有两个不同 holdout；模型合同/invocation 全绿。

## 14. P8：其余 40 工具覆盖

1. 40 工具每个新增两个不同 source holdout；
2. 为 clone、color_transfer、complex_bleach、crop_ai、deblur、dodge_burn、erase、lut_mapping、
   skin_smooth、sky_replace 补 amount anchor；
3. Crop 补 crop_box、crop_ratio、crop_rotation、straighten、flip_x、flip_y；
4. brush 工具验证坐标、radius、softness、strength、undo/redo、preview/export；
5. asset 工具至少两个不同合法 asset hash；
6. stochastic 工具用统计合同；
7. 每工具增加 amount=0/reset/negative（若支持）保护合同。

顺序为 model-backed → geometry/brush → asset/preset → tone/color → stochastic。每完成一个工具立即冻结。
准出时 40 holdout + 10 anchor + 6 Crop 共 56 个 effect scope 缺口归零。

## 15. P9：横向工作流、UI 与持久化

### 15.1 核心 interaction M/M

同一 frontend build 补齐 photo-switch-history、preset-import-preview-apply、layer-lifecycle、mask-lifecycle、
compare-zoom-pan。Preset 必须用真实 .lnpc Native observation；compare pan 必须产生可信非零 panX/panY。
之后重录现有 10 项并作为 required 子集；同时完成 P0 冻结的全部 M 项：

- 40 个工具各自的打开、代表参数修改、apply/reset/undo/redo、照片切换和导出；
- slider、toggle、select、asset picker、brush、crop canvas、context menu、drag-sort 等每种唯一控件语义；
- catalog、preset、layer、mask、history、compare、zoom/pan、multi-image、export 横向工作流；
- success、disabled、empty、loading、error 和 fail-closed 状态转换。

每条都要求 Native observation 与 Browser execution 成对，不能只重录现有 10 项，不拼接旧 build。

### 15.2 核心 UI N/N

按风险顺序：先 export-dialog/catalog/multi-image/multi-image-complete；再 presets/denoise；再 layer/more/BW；
最后低 MAE 的 edit-collapsed/info/edit/history/tool-expanded，集中修字体、图标、1-2 px 几何和颜色 token。
现有 16 状态必须全部重录并通过；同时完成 P0 冻结的全部 N 项：

- catalog、edit、preset、info、export、multi-image 等核心 workspace；
- 40 个工具各自的 collapsed、expanded、default、有修改、disabled/error，以及真实存在的 section/picker；
- hover、focus、selected、active、disabled、loading、empty、error 等可见状态；
- 右键菜单、子菜单、popover、dialog、tooltip、滚动顶部/中部/底部；
- layer、mask、history、compare、zoom/pan 的可见状态。

每次共享 token 修改后从全新 fixture 重录 N/N，绑定同一 build，不改 region/阈值。共享控件可以复用实现修复，
但每个工具面板的最终截图不能用“控件同类”推定通过。

### 15.3 persistence 单轨

补 project、edit history、layer、mask、workflow、preset、preview/export 七类 delta 和 restart roundtrip。
字段完整后一次性 repository 切换并删除 JSON primary/投影/双写/旧 reader。运行
validate_native_persistence_roundtrip.py，第 37 gate 必须 passed。

### 准出

Native/Browser M/M（含原 10/10）；UI execution/pixel N/N（含原 16/16）；scope 0；persistence passed；
worklist 0；无兼容层残留。

## 16. P10：单轮 exact 与同指纹 A/B

P5-P9 全绿后才运行单轮：

~~~bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id alignment-r15-release-candidate-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r15-single.json
~~~

单轮必须 37/37。失败只回责任域，不重跑到偶然通过。单轮通过后冻结五类指纹，运行 A/B：

~~~bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id alignment-r15-release-a-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r15-a.json

.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id alignment-r15-release-b-20260831 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r15-b.json
~~~

两轮要求 37/37、required failure=0、source/model/reference/fixture/environment 指纹一致、case 数一致、无 stale
artifact、无人工覆盖。任一轮失败仍为 blocked。

## 17. 修改与验证矩阵

| 目标 | 主要修改入口 | 窄验证 | 最终验证 |
|---|---|---|---|
| 天空模型 | ai/model/onnx/sky_segmentation、horizon_alignment、OpenVINO wrapper | model validator/wrapper tests | contract/invocation |
| 天空编排 | ai/pipeline/image_effect_pipelines.py、execution-graphs.json | pipeline/helper tests | sky E2E/parity |
| 天空合成 | image_ops/effects/sky_compositor.py | test_sky_compositor.py | exact matrix |
| 天空参数 | parameter-schema.json、editor.json | consistency tests | Native 18-control |
| 天空 UI | SkyControls.tsx、ToolPanel.tsx、CSS | component tests/build | UI/interaction |
| API/edit graph | services/editor/service.py、api/http/router.py | API/edit tests | preview/export/persistence |
| 其他效果域 | 对应 pipeline/model/effect | capability 窄测 | 主效果/Exact |
| 证据 | sky diagnostics、sampling/parity scripts | fixture/schema | quality gates |
| 持久化 | 真实 schema 确定后的 active repository | roundtrip tests | 第 37 gate |

全量守护：

~~~bash
.venv/bin/ruff check .
.venv/bin/pytest -q
cd frontend && npm test -- --run
cd frontend && npm run build
~~~

## 18. 停止、回退和阻塞规则

### 立即停止 Native UI

Luminar 退出全屏/前台、display/input isolation 为 false/unknown、用户会话受影响、版本/locale/workspace 不匹配、
进入排除范围或可能修改用户真实 catalog。停止后保持现状，attempt 标记 invalid/blocked。

### 立即回退实现

冻结域新增失败；required 模型静默 fallback；preview/export 用不同合同；需降阈值/缩 region/换 reference；
增加 case/hash/filename 特判；新增 JSON/SQLite 双写/旧 reader/兼容迁移；改动无法由单变量证据解释。

### 合法 blocked

无隔离输入、Native range/default 未采样、真实 persistence mapping 不完整、真实 .lnpc observation 缺失。
blocked 必须写缺证据和下一动作，不能伪完成。

## 19. 最终遗漏审计

- [ ] 40 工具均有 canonical + 两个不同 source holdout；
- [ ] 10 amount anchor 和 6 Crop 参数关闭；
- [ ] 天空 18 控件无 pending range/default；
- [ ] 天空 public 字段与 Native 一致，无多余候选控件；
- [ ] 天空 required/conditional invocation 正确；
- [ ] 5 主效果和 8 Exact 失败全部关闭；
- [ ] preview/export 去编码合同通过；
- [ ] Native/Browser interaction M/M，且原 10/10 子集全过；
- [ ] UI execution/pixel N/N，且原 16/16 子集全过；
- [ ] preset/layer/mask/history/compare/multi/export 全闭环；
- [ ] persistence 七类 delta/restart 完整；
- [ ] 无 JSON primary、双写、旧 reader 或历史迁移；
- [ ] scope=0、worklist=0；
- [ ] exact 单轮和同指纹 A/B 均 37/37；
- [ ] 排除范围未进入分母；
- [ ] 文档数字、路径、命令与最终 artifact 一致。

任一项未勾选，最终结论必须写“尚未绝对对齐”。

## 20. 交付物

1. Native isolation preflight；
2. 天空 source/asset/parameter/repeat Native manifest；
3. 天空 18 控件合同；
4. 天空逐段诊断和 invocation trace；
5. 天空 canonical/holdout/anchor parity；
6. 场景、人像、全局增强域退出报告；
7. 40 工具 holdout/anchor/Crop 矩阵；
8. 当前 build Native/Browser M/M 和原 10/10 子集报告；
9. 当前源码 UI execution/pixel N/N 和原 16/16 子集报告；
10. Native persistence delta/roundtrip 和单轨审计；
11. scope 0、worklist 0；
12. exact single/A/B 报告与一致指纹；
13. R15 执行前后对比、最终遗漏和下一步建议。

最终声明必须列出 build、范围、37/37 A/B、40/40、69/69、UI N/N（含 16/16）、interaction M/M
（含 10/10）、scope/worklist 0、模型 22/22 和 18/18、persistence passed、完整 fingerprint。缺任一字段
不使用“核心 UI、交互、效果完全一致”或“绝对对齐”。
