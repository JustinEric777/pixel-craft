# Luminar Neo 1.28 绝对对齐优化计划（2026-08-25）

> 本计划面向后续直接执行。目标是在本机 Luminar Neo `1.28.0 (23071)`、`zh-Hans`、固定合法免费素材、固定输入和固定 `2880×1800` UI 视口下，使效果、UI、交互和工作流的全部 required gate 连续两次通过。有限黑盒样本不能证明所有图片和连续参数空间的数学全等，因此本文的“绝对对齐”只指上述冻结合同范围内可重复、可审计、可证伪的等价。

## 目录

- [1. 当前基线](#1-当前基线)
- [2. 总体原则](#2-总体原则)
- [3. 执行依赖和总流程](#3-执行依赖和总流程)
- [4. P0：冻结证据和恢复 Browser](#4-p0冻结证据和恢复-browser)
- [5. P1：关闭 9 条不可信 exact 证据](#5-p1关闭-9-条不可信-exact-证据)
- [6. P2：效果算法闭环](#6-p2效果算法闭环)
- [7. P3：Overlay 和多图工作流](#7-p3overlay-和多图工作流)
- [8. P4：UI 像素对齐](#8-p4ui-像素对齐)
- [9. P5：交互对齐](#9-p5交互对齐)
- [10. P6：模型推理行为合同](#10-p6模型推理行为合同)
- [11. P7：全链路收口和发布](#11-p7全链路收口和发布)
- [12. 批次、停止条件和回滚](#12-批次停止条件和回滚)
- [13. 完成定义](#13-完成定义)

## 1. 当前基线

| 域 | 当前结果 | 目标 |
|---|---:|---:|
| exact 综合门禁 | 18/28 passed | required 全部通过，连续双跑 |
| 基础效果 | 36/45 | 45/45 |
| exact 增量 | 41 pass / 26 fail / 2 pending | 合法 case 全部通过 |
| exact 数据链 | 60/69 canonical-ready | 合法 case 全部 canonical-ready |
| Overlay | 37/38 | 38/38 |
| Multi-image | 1/3 | 3/3 |
| UI current build | 0/7 | 7/7 |
| Interaction execution | 0/10 | 10/10 |
| required model source | 22/22 | 保持 22/22 |
| Python / Frontend | 259 / 12 passed | 不回退 |

当前机器事实来自：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-execution-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-incremental-data-chain.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-incremental-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution.json`

## 2. 总体原则

1. 不降低 `configs/parity.yaml` 的默认门限：`SSIM >= 0.98`、`MAE <= 0.03`、尺寸一致；UI 保持 `MAE <= 0.03`、变化像素比例 `<= 0.02`。
2. 不用单张 reference 调通用系数。每个共享语义至少用目标 case、同域另一输入和中性 anchor 验证。
3. 已可信 canonical 不重复采样。只有 `failed`、`invalid-evidence`、reference 被确认损坏或合同改变后才重建对应 semantic key。
4. 不保留 1.25/1.26 兼容分支，不新增“旧数据回退”。活动版本只有 1.28。
5. 原生 preview、原生 export、candidate preview/export、AX、Browser、API 状态必须属于同一个 fixture 和 build hash。
6. 控件读回不等于效果成功；非零效果必须通过最终导出变化和 parity。
7. 一个批次只解决一个共享根因。失败先诊断，不继续同域大批量采样。
8. UI 以 Luminar 原生截图和 AX 为唯一设计源，不引入新的视觉语言。
9. 模型层只负责加载、预处理、前向、后处理和释放；效果组合留在 pipeline，任务租约留在 job service。
10. optional 的 66 个 inventory-unreachable 模型不阻塞当前可见产品范围，不为追求数字实现不可达模型。

## 3. 执行依赖和总流程

```text
恢复 Browser + 冻结本机参考
            │
            ▼
修正非法/不可信采样合同 ──► exact 数据链可信
            │
            ├────────► 效果算法 45/45 + exact
            ├────────► Overlay / HDR / Panorama
            └────────► UI 7 状态 + 10 交互
                              │
                              ▼
                    required gate 连续双跑
```

阶段依赖：

- P0 是 UI/交互的硬前置，但不阻塞纯效果和工作流算法调试。
- P1 是 exact 参数拟合的硬前置；证据不可信时禁止修改候选算法去拟合它。
- P2、P3、P4 可在证据完成后按独立小批推进。
- P5 必须在 UI 主结构稳定后执行，避免 selector 和截图频繁失效。
- P6 只在 P2 证明误差来自模型语义时启动。
- P7 只做收口，不再引入新功能。

## 4. P0：冻结证据和恢复 Browser

### 4.1 目标

- in-app Browser 可见并可控制当前前端；
- 7 个 UI state 产生当前 build、固定视口截图；
- 10 个 interaction contract 同时具有 Luminar native observation 和 Browser execution；
- 所有 evidence 写入 validator 约定路径。

### 4.2 操作

1. 从项目根目录运行 `codex app .`，在 Codex App 新会话确认 Browser 实例不是空列表。
2. 启动当前前端和后端，固定 locale `zh-Hans`、timezone `Asia/Shanghai`、viewport `2880×1800`。
3. 用 `scripts/seed_ui_validation_catalog.py` 建立固定 catalog/project fixture；记录 fixture id/hash。
4. 依次建立 `catalog`、`presets`、`edit`、`layer-stack`、`layer-library`、`tool-expanded`、`multi-image`。
5. Browser 截图严格写入 `diagnostics/ui-candidates/2880x1800/<state>.png`。
6. 生成 `diagnostics/ui-browser-execution.json`，必须包含 browser、browser_version、viewport、locale、timezone、frontend build hash 和 7 条记录。
7. 按 `configs/parity/interaction-contracts.json` 在 Luminar 原版逐条执行 10 个合同，保存 before/after/AX/observation.json 到 `observations/interactions/<contract>/`。
8. 在 Web 端逐条执行相同事件，保存截图、console、network、API assertion、wait conditions 和 native observation hash 到 `diagnostics/interaction-browser-execution.json`。

### 4.3 验证

```bash
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

准入：UI execution `7/7` 且 interaction evidence schema `10/10` 完整。此阶段只证明证据完整，不要求像素和行为已经通过。

停止条件：Browser 仍无实例、build hash 不一致、fixture hash 不一致或原生 observation 缺失时停止 UI/交互判定；不得使用 Playwright、单测或旧截图替代。

## 5. P1：关闭 9 条不可信 exact 证据

### 5.1 先修合同，不先重采

| 能力 | 当前问题 | 第一修改入口 | 决策 |
|---|---|---|---|
| Face AI | `-1` 无法映射到原生 `0..100` | `scripts/build_incremental_sampling_queue.py`、native range evidence | 从合法原生矩阵删除负值，不伪造 -100 |
| Color Enhancer | preview/export 不一致 | sampler comparison、color profile metadata | 先判定色彩管理或产品延迟，再决定重采 |
| Magic Lights | 非零但原生导出不变 | `configs/luminar_sampling.yaml`、工具 AX | 确认是否需要光源检测/素材/二次 Apply |
| New Neon Light | 非零但原生导出不变 | 同上 | 确认是否需要画布定位或光源选择 |
| Skin Smooth | 人像输入仍无变化 | subject readiness/AX | 增加人物分析完成信号，不用固定 sleep |
| Slim People | 两个方向无变化 | subject readiness、slider semantic | 确认人形检测完成和正负方向语义 |
| Denoise | 当前绑定 Details | recipe control id | 验证 Luminosity/Amount 是否才是主强度 |
| Denoise Laplacian | 非零无变化 | recipe control id | 验证主滑杆与辅助滑杆绑定 |

### 5.2 完成信号

对 AI/人物工具优先寻找以下可观察信号，按顺序选择最小可行项：

1. AX 中 loading/progress 元素消失；
2. 主 preview 像素发生变化并在完整静默窗口内稳定；
3. 目标 slider 从 disabled 变 enabled；
4. 原生 export 与 source 达到变化门限。

禁止仅增加一个盲目的 30/60 秒 sleep。若 Luminar 没有可观察信号，可配置“最小等待 + 稳定窗口 + 最终 export 变化”三重条件，但只能用于确认需要长推理的具体 recipe。

### 5.3 状态修复

1. 修正参数矩阵或 recipe。
2. 重建 incremental queue；确认合法 case 数变化有明确 diff。
3. `--dry-run` 必须只列出合同变化或 invalid/failed case。
4. 每次只重试一个 capability，成功后立即审计。

```bash
.venv/bin/python scripts/build_exact_sampling_matrix.py
.venv/bin/python scripts/build_incremental_sampling_queue.py
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --resume --dry-run
.venv/bin/python scripts/audit_sampling_effect_changes.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json
.venv/bin/python scripts/validate_sampling_data_chain.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json
```

验收：合法 exact 记录全部 canonical-ready，审计中 `invalid-unchanged-export=0`、`missing-evidence=0`。非法产品参数不计入合法队列，不保留兼容假 case。

## 6. P2：效果算法闭环

### 6.1 公共执行方式

每个能力使用同一闭环：

1. 读取 reference/source/candidate/diff heatmap 和区域统计。
2. 判断误差类型：全局色调、局部 mask、几何、素材、位置、噪声统计或编码。
3. 写一个能复现共享根因的窄测试。
4. 只修改一个 pipeline/helper/contract。
5. 只强制生成目标 capability candidate。
6. 运行目标 capability parity。
7. 运行同域 holdout 和中性 anchor。
8. 通过后再进入下一能力。

```bash
.venv/bin/python scripts/generate_candidate_outputs.py --capability <capability> --force
.venv/bin/python scripts/run_parity_suite.py --capability <capability>
.venv/bin/pytest -q tests/test_ai_effect_pipeline_helpers.py tests/test_api.py
```

### 6.2 批次 A：光照/大气/深度

顺序：`blue_hour` → `fog` → `depth_volume` → `sunrays`。

修改入口：`ai/pipeline/image_effect_pipelines.py`。

- Blue Hour：先对齐曝光、白平衡、蓝/品红分离，不用单一蓝色 overlay。
- Fog：校验 depth 方向、远近衰减、雾色和对比压缩；用 depth 分位统计而非硬编码样本像素。
- Depth Volume：与 Fog 共享 depth normalization，但保留独立 tone curve。
- Sunrays：把光源位置纳入正式参数合同；原生 position 需要从 UI/采样 metadata 进入 pipeline，禁止从单张天空 mask 的中位数猜位置。

批次验收：基础相关 case 全过；exact 的 `-1/0/+1` 合法锚点全过；其他 depth/light 能力不回退。

### 6.3 批次 B：天空和素材

顺序：`sky_replace` → `lut_mapping`。

- Sky Replace：保持已通过的 46 个 Sky E2E，不改素材映射；只对齐 horizon mask、边缘去色、反射/relight 和构图。
- LUT：先证明 Luminar reference 真的应用了所记录 LUT；若 reference 接近 source，检查 asset id/hash 和 Amount，不拟合错误素材。

验收：Sky E2E 保持 46/46；LUT、Sky 基础 parity 通过；素材 hash 和 metadata 一致。

### 6.4 批次 C：人像几何和人物效果

顺序：`face_ai` 尾差 → `slim_people` → `face_enhancer`/`bokeh_ai` exact failures。

- Face AI：基于前景 mask 的现有实现微调亮度、模糊和 mask feather；必须在至少两个 portrait fixture 验证。
- Slim People：以人体 mask + 几何形变域为核心，修正中心、保护脸/背景直线、边界 blend；不能用整图水平缩放。
- Face Enhancer/Bokeh：先判断 exact 失败来自 mask、强度曲线还是模型输出，不共享未经验证的 Face AI 系数。

验收：人像基础和 exact 全过；背景直线/边缘 holdout 不出现明显弯曲；`amount=0` byte/像素语义保持 no-op。

### 6.5 批次 D：其余 exact 参数曲线

处理 `default_effects`、`grain`、`high_key`、`pro_contrast`、`structure_ai`、`vignette`、`color_toning`、`radiance`、`fade` 等 exact 失败。

规则：

- 先按 capability 汇总三个 anchor 的误差方向；
- 单调效果拟合单调曲线，不为正负值建立互不相关分支；
- Grain 使用 `grain-statistical` comparator，不追逐随机像素；
- 尺寸或 reference 失真优先修数据链，不进入算法。

P2 完成标准：`output-parity 45/45`，合法 exact effect 全过，preset 123/123 和 sky 46/46 不回退。

## 7. P3：Overlay 和多图工作流

### 7.1 Overlay 38/38

唯一失败项先根据 `configs/parity/invalid-references.json` 和最近邻素材诊断确认：

- 若 reference 素材错配：只重建该 Overlay 原生 reference 和 metadata；
- 若素材正确：修改 layer blend/stretch/opacity/composite；
- 不为单条错误 reference 修改通用 stretch 规则。

```bash
.venv/bin/python scripts/run_overlay_e2e_validation.py
```

验收：38/38，且其他 37 条 hash/metrics 不回退。

### 7.2 HDR

修改入口：`image_ops/merge/hdr.py`。

当前 candidate 平均亮度比 reference 高约 0.09–0.10。执行顺序：

1. 先验证 frame 顺序、尺寸、色彩空间；
2. 分离 exposure fusion 与 tone mapping 的误差；
3. 对齐 luminance weight 和全局/局部 tone curve；
4. 检查高光保护、阴影抬升和颜色饱和度；
5. 使用固定输入的区域统计验证，不只看整图 MAE。

验收：尺寸一致、MAE/SSIM 门限通过，preview/export hash 稳定。

### 7.3 Panorama

修改入口：`image_ops/merge/panorama.py`。

当前 candidate `1078×1440`，reference `1070×1410`。执行顺序：

1. 先关闭尺寸：特征对齐、投影模型、有效像素边界和最终 crop；
2. 再关闭内容：曝光补偿、seam path、feather；
3. 不用最终强制 resize 掩盖投影/crop 错误；
4. 对 overlap、输出边界和接缝增加单元测试。

```bash
.venv/bin/python scripts/run_multi_image_workflow_smoke.py
.venv/bin/pytest -q tests/test_workflows.py tests/test_multi_image_validation_data.py
```

验收：HDR、Focus、Panorama 3/3；Focus 当前通过结果保持。

## 8. P4：UI 像素对齐

### 8.1 视觉方向

唯一主方向是“复刻 Luminar 1.28 精密编辑工作台”。预览画布保持最高优先级，侧栏和工具栏服从原版截图；不引入营销式卡片、大面积渐变或额外装饰。

主要修改入口：

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/components/CatalogWorkspace.tsx`
- `frontend/src/components/PresetBrowser.tsx`
- `frontend/src/components/PreviewPanel.tsx`
- `frontend/src/components/ToolPanel.tsx`
- `frontend/src/components/LayersPanel.tsx`
- `frontend/src/components/WorkflowWorkspace.tsx`

### 8.2 对齐顺序

1. 全局壳：窗口背景、顶部栏高度、三栏宽度、滚动所有权、画布尺寸。
2. 全局令牌：背景/表面/文字/强调色/边框/圆角/间距；令牌只由 Luminar screenshot 反推。
3. Typography：字体栈、字号、字重、行高、数字对齐。
4. 共享组件：按钮、tab、slider、tool row、panel heading、空态和 loading。
5. 状态页面：catalog → presets → edit → tool-expanded → layer-stack → layer-library → multi-image。
6. 状态完整性：hover、focus-visible、selected、disabled、loading、empty、error。
7. 窄屏仅保证可用性，不作为 2880×1800 像素门禁的一部分。

### 8.3 每状态闭环

1. 对原版和当前截图生成绝对差、分区 MAE、变化像素热力图。
2. 先修最大面积结构误差，再修颜色/字体/细节。
3. 一次只改共享壳或一个 state，避免 7 张截图同时漂移。
4. Browser 重拍当前 build screenshot。
5. 运行证据校验和 UI parity。

```bash
cd frontend && npm test -- --run && npm run build
cd ..
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

验收：7/7；每张 shape match，`MAE <= 0.03`，changed pixel ratio `<= 0.02`；build hash、fixture hash、viewport 全匹配。

## 9. P5：交互对齐

按依赖顺序执行 10 个合同：

1. `catalog-import-select`
2. `preset-preview-apply`
3. `edit-slider-drag`
4. `edit-toggle-collapse`
5. `layer-add-reorder-opacity-delete`
6. `undo-redo`
7. `before-after-compare`
8. `zoom-pan`
9. `export-dialog`
10. `multi-image-workflow`

### 9.1 行为要求

- 事件顺序、可见状态、API mutation 次数和最终 project JSON 与合同一致；
- wait 只能使用合同中声明的条件，禁止 fixed sleep；
- 异步请求使用最新请求身份，旧响应不能覆盖当前项目/预览/错误；
- slider 拖动必须显示即时值，Apply 后只创建一个 edit；
- before/after、zoom/pan 不得改变 project state；
- undo/redo 恢复相同 edit id/parameters；
- export 只发一次请求，尺寸与项目一致；
- 长分析/多图任务支持进度、取消、错误、重试和完成结果，不在组件卸载后继续污染状态。

### 9.2 实现策略

- 先补语义 selector/ARIA label 和稳定 data 属性，只用于真实产品语义，不创建测试专用旁路；
- 修业务状态，再调动画和视觉；
- 每个合同补一个用户可见行为测试；
- Browser execution 必须链接对应 Luminar native observation。

验收：`scripts/validate_interaction_execution.py` 返回 `executed=10`、`passed=10`、`issue_count=0`。

## 10. P6：模型推理行为合同

只有 P2 的误差诊断证明根因在模型 wrapper/输出语义时才进入本阶段。

### 10.1 修改边界

- `ai/model`：BaseInference、wrapper、registry、factory、loader、preprocess/predict/postprocess/unload；
- `ai/pipeline`：模型输出如何组成效果；
- `services/jobs`：长任务编排、lease、checkpoint；
- 三层不交叉承担职责。

### 10.2 单模型接入/修复检查

1. 本地权重和 registry path/class 一致；不隐式联网。
2. `load_model()` 全部成功后才 `_loaded=True`。
3. preprocess 明确 RGB/BGR、尺寸和 normalization。
4. predict 只做前向，使用 eval/no-grad 或等价 runtime session。
5. postprocess 返回同 task 稳定字段和原图坐标/尺寸。
6. unload 释放 model/session/processor 并重置 loaded。
7. loader 淘汰时调用 unload；缓存键和 memory estimate 可解释。
8. 为活动 case 记录真实 invocation 和 contract result。

### 10.3 验证

```bash
python .agents/skills/ai-model-inference/scripts/validate_model_module.py --project-root .
.venv/bin/python scripts/build_model_source_map.py
.venv/bin/python scripts/check_model_contracts.py
.venv/bin/pytest -q tests/test_model_loader.py tests/test_model_outputs.py \
  tests/test_model_source_map.py tests/test_active_model_contracts.py \
  tests/test_candidate_model_invocations.py tests/test_ai_effect_pipeline_helpers.py
```

验收：required source map 保持 22/22；活动调用 22/22；没有新增 pending required model。optional unreachable inventory 不扩 scope。

## 11. P7：全链路收口和发布

### 11.1 回归顺序

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
cd frontend && npm test -- --run && npm run build
cd ..
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-run-1.json
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-run-2.json
```

两次运行之间不得修改代码、配置、reference、candidate 或 fixture。两份报告必须具有相同 dataset/build fingerprint，required failure set 都为空。

### 11.2 发布动作

只有双跑通过后：

1. 更新 1.28 manifest 的 dataset/build/candidate fingerprint；
2. 生成最终前后对比和门禁摘要；
3. 运行一次安全 cleanup dry-run，只删除可重建 workspace/stale stability frame；
4. 不删除发布 canonical、current Browser evidence、interaction observation 和最后失败诊断；
5. 将声明限定为冻结范围内等价，不扩展到付费、生成式、未采样参数或其他 Luminar 版本。

## 12. 批次、停止条件和回滚

### 12.1 单批上限

- 原生采样：一个 capability 或最多 5 条记录；
- 效果实现：一个共享语义；
- UI：一个共享壳改动或一个 state；
- Interaction：一个 contract；
- Workflow：一种 merge；
- 模型：一个 wrapper/contract。

### 12.2 立即停止条件

- reference hash、fixture hash、build hash 不一致；
- preview/export 不一致；
- non-zero export 与 source 无变化；
- 同域 holdout 回退；
- 需要降低阈值才能通过；
- Browser/AX 当前不可用；
- Luminar UI 运行态退化，如主 preview AXImage 消失；
- 同一结构性错误连续两条出现。

### 12.3 回滚原则

- 代码：只回滚当前小批修改，不回滚其他已通过域；
- reference：不覆盖旧 canonical，先 invalidation，再以新 attempt 发布；
- candidate：只 `--force` 目标 capability/case；
- UI evidence：build hash 变化后旧截图自动失效，不复制为新 build；
- 数据：清理只使用 `scripts/cleanup_test_data.py` dry-run → review → apply。

## 13. 完成定义

以下条件必须全部满足：

- 基础效果 45/45；
- 合法 exact case 全部 canonical-ready 且 parity 全过；
- Preset 123/123；
- Sky E2E 46/46；
- Overlay 38/38；
- Multi-image 3/3；
- UI current build 7/7；
- Interaction 10/10；
- required model source/behavior/candidate invocation 全过；
- Python、Frontend、build、lint 全过；
- invalid registry 中 confirmed/suspected 项已关闭或被可信重建，但登记不能豁免 gate；
- exact required gates 连续两次失败集合为空；
- 没有阈值放宽、旧版本回退、固定 sleep 伪稳定、错误 reference 拟合或已完成样本重复采样。

达到这些条件后，才允许发布“在本机 Luminar Neo 1.28 冻结合同范围内，效果、UI、交互完全对齐”的结论。
