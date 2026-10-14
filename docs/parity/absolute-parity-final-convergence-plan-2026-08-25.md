# Luminar Neo 1.28 效果、UI、交互绝对对齐最终收敛计划

> 日期：2026-08-25  
> 活动基线：本机 Luminar Neo `1.28.0 (23071)` / macOS / `zh-Hans`  
> 目标：在冻结、合法、可重复的本机合同范围内，使本项目与 Luminar Neo 在效果、UI、交互、内容和工作流层面形成可审计等价。

## 1. 结论和执行主线

当前项目已有可用的采样、候选生成、差异比较、状态持久化和质量门禁骨架，但还不能声明“绝对对齐”。最新两次 exact 门禁稳定为 required `18 passed / 9 failed`，说明剩余问题已经收敛为明确的 9 个门禁，不是随机失败。

本轮停止横向扩展，按以下主线收口：

```text
冻结本机合同和证据指纹
          │
          ├── 恢复 Browser，建立当前 build 的 UI/交互证据通道
          │
          ▼
拆分 exact active cohort / pending worklist
          │
          ▼
只重观察 invalid、failed、损坏或合同变化项
          │
          ├── 效果 45/45 + 合法 exact 全过
          ├── Overlay 38/38 + Multi-image 3/3
          └── UI 7/7 + Interaction 10/10
                              │
                              ▼
                  required exact 连续双跑零失败
                              │
                              ▼
                    清理可重建数据并冻结发布
```

本文的“绝对对齐”只指第 2 节冻结合同内可重复、可审计、可证伪的等价，不代表对所有未知图片、所有连续参数、付费内容或未来 Luminar 版本的数学全等。

## 2. 冻结范围和不做事项

### 2.1 冻结范围

| 维度 | 冻结值 |
|---|---|
| 产品 | Luminar Neo `1.28.0 (23071)` |
| Bundle | `com.skylum.luminarneo` |
| 平台/语言/时区 | 本机 macOS / `zh-Hans` / `Asia/Shanghai` |
| UI | `2880×1800`，同时记录 DPR、字体、主题和 motion |
| 输入 | `test_data/parity/inputs/` 中冻结输入及 SHA-256 |
| 参考 | `test_data/parity/references/luminar-1.28.0-23071/` |
| 原生证据 | `test_data/outputs/luminar-1.28.0-23071/{captures,ui,observations}/` |
| 诊断 | `test_data/outputs/luminar-1.28.0-23071/diagnostics/` |
| 内容 | 本地可合法使用的免费 Preset、Sky、Overlay、LUT |
| 功能 | required 效果、7 个 UI 状态、10 个交互合同、3 个多图工作流 |

### 2.2 明确不做

- 不恢复 1.25/1.26 profile，不写历史 payload、样式或证据兼容逻辑。
- 不把付费、未安装、生成式或当前产品界面不可达能力纳入 required。
- 不降低 MAE、SSIM、尺寸或 UI changed-pixel 门限。
- 不以人工观感、单测、模型加载成功或 `runtime-ready` 替代 parity。
- 不对单张 reference 硬编码坐标、裁切、颜色常数或 case 分支。
- 不重复采样 `ready` 且合同 hash 未变化的 canonical。
- 不按 hash 直接删除证据；相同内容可能承担不同审计角色。
- 不为 optional 的 66 个产品不可达模型扩展实现。

## 3. 最新基线和差距

| 域 | 当前 | 目标 | 结论 |
|---|---:|---:|---|
| required exact | 18 passed / 9 failed | 连续两次 failure=0 | 稳定阻断 |
| 基础效果 | 36/45 | 45/45 | 9 条像素差异 |
| exact parity | 41 pass / 26 fail / 2 pending | 合法 cohort 全过 | 数据与算法均未闭环 |
| exact 数据链 | 60/69 ready | 合法 cohort 全 ready | 7 invalid、2 failed |
| 主队列逐文件证据 | 248/251 | 251/251 | 3 条 AX 被历史硬链接覆盖 |
| Preset / Sky | 123/123、46/46 | 保持 | 已通过 |
| Overlay | 37/38 | 38/38 | 1 条疑似素材错配 |
| Multi-image | 2/3 | 3/3 | HDR、Focus 过；Panorama 失败 |
| UI current build | 0/7 | 7/7 | Browser 无实例 |
| Interaction | 0/10 | 10/10 | 缺联合执行证据 |
| required model | 22/22 | 保持 | 已通过 |
| Python / Frontend / Ruff | 265 / 12+build / pass | 不回退 | 已通过 |

当前 required 失败门禁：`overlay-e2e`、`multi-image`、`exact-incremental-data-chain`、`sampling-queue-evidence`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`。

optional `model-contract-inventory` 的 66 个产品不可达模型不影响 required 22/22，也不进入关键路径。

## 4. 硬性执行规则

### 4.1 真值优先级

1. 同一 build/fixture 的 Luminar preview/export、UI screenshot、AX 和 observation。
2. 原生素材 id/path/hash、control id/range/readback 和导出 metadata。
3. 本项目同一 build hash 的 candidate、Browser execution、API/project 状态。
4. 自动 comparator 和质量门禁。
5. 人工观察只提出假设，不判定通过。

### 4.2 采样选择

只有以下记录允许进入 pending worklist：

- `failed` 或 `invalid-evidence`；
- artifact 缺失/hash 损坏；
- contract、fixture、recipe 或原生 build 改变；
- 新增合法 required semantic key。

canonical 为 `ready`，且 semantic key、contract hash、fixture hash、reference build 未变化时，禁止重采。单批最多一个 capability 或 5 个 case；出现系统性 unchanged、错误素材、错误控件或 native preview/export 不一致时立即停止该 capability。

### 4.3 算法修改

每个共享算法改动同时验证目标 fixture、同域 holdout、中性 anchor、已通过同域能力和双跑 hash。一次批次只解决一个根因，不把 UI、模型、迁移和算法大改混在一起。

## 5. 目标数据链：active cohort 与 pending worklist

### 5.1 必须拆分的原因

现有 `build_incremental_sampling_queue.py` 只生成“缺 canonical 的语义”。若用它覆盖现有 69 条队列，会把 60 条成功记录从验证全集移除；若保留旧队列，又会包含已确认非法的 Face AI 负值。

因此建立两个产物：

| 产物 | 职责 | 包含 ready | 直接执行 |
|---|---|---:|---:|
| exact active cohort | 当前 1.28 全部合法 required exact 合同，是发布验证全集 | 是 | 否 |
| exact pending worklist | cohort 中需要新证据的动态视图 | 否 | 是 |

active cohort 至少包含 cohort/reference/matrix fingerprint、semantic key、capability/case、参数/value-space、native control/range/readback、fixture/recipe hash、canonical pointer、evidence status 和 contract hash。

pending 只选择 `missing`、`failed`、`invalid-evidence`、`artifact-corrupt`、`contract-changed`、`fixture-changed`。Face AI 非法 `-1` 进入 diff 的 `excluded-illegal-native-range`，不进入 cohort 或 worklist。

### 5.2 修改入口

- `scripts/build_exact_sampling_matrix.py`
- `scripts/build_incremental_sampling_queue.py`
- `scripts/build_exact_parity_cases.py`
- `scripts/validate_sampling_data_chain.py`
- `scripts/validate_sampling_queue_captures.py`
- `tests/test_exact_sampling_matrix.py`
- `tests/test_incremental_sampling_queue.py`
- `tests/test_sampling_data_chain.py`

优先扩展现有最小路径，不增加通用编排框架。新实现直接使用当前 schema；旧 JSON 仅作为 diagnostics 归档，不保留运行时兼容分支。

## 6. 阶段依赖

| 阶段 | 目标 | 前置 | 准出 |
|---|---|---|---|
| P0 | 冻结基线、恢复 Browser | 当前代码可启动 | Browser 可见；基线指纹落盘 |
| P1 | 拆 cohort/worklist | 冻结 reference | cohort 完整，worklist 只含需采项 |
| P2 | 修 fixture/recipe、定向重观察 | P1 | 无非法合同、无已知错误真值 |
| P3 | 关闭效果 | 对应 P2 真值可信 | 45/45；合法 exact effect 全过 |
| P4 | Overlay/Multi-image | 对应 P2 真值可信 | 38/38；3/3 |
| P5 | UI 像素对齐 | Browser/reference | 7/7 |
| P6 | 交互对齐 | UI 共享组件稳定 | 10/10 |
| P7 | 模型/长任务 | 仅诊断触发 | required 保持；完整恢复 |
| P8 | 回归、双跑、清理、发布 | P1–P7 | required 双跑零失败 |

P3、P4、P5 可在各自证据可信后交错推进，但每个执行记录仍是独立批次。P6 在 UI 主结构稳定后开始。

## 7. P0：冻结基线并恢复 Browser

### 7.1 Baseline manifest

记录 reference/build/bundle、配置和 cases/matrix/fixture/素材 hash、代码 fingerprint、Python/Node/browser 版本、viewport/DPR/locale/timezone/font/motion、两次 gate 报告、cohort/worklist fingerprint。没有 Git 时，对明确的源文件清单计算 hash。

fixture、合同或 reference 变化时生成新 revision，不覆盖旧 manifest。每批开始/结束都写 baseline id。

### 7.2 Codex CLI 操作

```bash
cd /Users/iknow/Works/python/zpixel_edit
codex app .
```

在 Codex App 新任务确认 Browser 实例存在。当前 CLI 会话 runtime 可加载但实例列表为 `[]`，不能伪造 UI/交互证据。

后端：

```bash
cd /Users/iknow/Works/python/zpixel_edit
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd /Users/iknow/Works/python/zpixel_edit/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Browser 打开 `http://127.0.0.1:5173`，不是后端 8000。

准出：能打开当前 Vite build，API 正确，无阻断 console error；固定 UI 环境；一个 UI state 和一个 interaction contract 都能生成 execution JSON、截图、network/API assertion 和 hash。若仍无 Browser，P5/P6 保持 blocked，禁止用独立 Playwright、旧截图或测试快照替代。

## 8. P1：实现 cohort/worklist

1. Face AI 使用能力级 `amount 0..100`，不继承 signed 全局范围。
2. 生成完整 matrix，并将非法语义写入 diff。
3. 用 matrix + 当前 canonical state 构建 active cohort。
4. 从 cohort 派生 pending worklist。
5. 迁移 60 条 ready 指针，不复制、不重采、不改 artifact hash。
6. 7 条 invalid 与 Color Enhancer failed 进入 worklist。
7. Face AI `-1` 排除并记录原因。
8. data-chain validator 检查 cohort；queue validator 检查 worklist。
9. exact parity case builder 读取 cohort，不读取 pending queue 作为全集。
10. 添加确定性、唯一性、ready 排除、单合同变化选择测试。

完整 matrix 当前有效命令：

```bash
.venv/bin/python scripts/build_exact_sampling_matrix.py \
  --cases test_data/parity/references/luminar-1.28.0-23071/cases.json \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-sampling-matrix.json
```

改造完成前，旧 builder 仅 dry-run 到临时文件，不覆盖冻结 69 条队列：

```bash
.venv/bin/python scripts/build_incremental_sampling_queue.py \
  --matrix test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-sampling-matrix.json \
  --smoke-queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue.json \
  --capture-root test_data/outputs/luminar-1.28.0-23071/captures \
  --output /tmp/zpixel-exact-worklist-dry-run.json \
  --diff-output /tmp/zpixel-exact-worklist-diff-dry-run.json
```

验收：60 条 ready hash 不变；非法 Face 不在 cohort/worklist；worklist 只含需采项；semantic key 唯一；两个产物各有 fingerprint；缺 artifact、错 hash、孤立 canonical 和错 contract hash 均 fail closed。

```bash
.venv/bin/pytest -q \
  tests/test_exact_sampling_matrix.py \
  tests/test_incremental_sampling_queue.py \
  tests/test_sampling_data_chain.py
```

## 9. P2：fixture/recipe 和定向重观察

### 9.1 invalid-evidence 修复矩阵

| 能力 | 根因 | 新 fixture/recipe | 完成信号 |
|---|---|---|---|
| Magic Lights `+1` | 无明确灯源 | 夜景、多个离散灯具、不过曝 | 检测完成；preview 稳定；export 变化 |
| Slim People `±1` | 半身输入不适用 | 冻结数据中的全身输入，背景直线可见 | 人体识别；局部形变；背景可检查 |
| New Neon Light `+1` | 缺画布放置/绘制 | position/draw/Apply recipe | 控制点提交；效果层出现；export 变化 |
| Skin Smooth `+1` | 人脸遮挡/分析未完成 | 无遮挡正面人像 | 工具 enabled；皮肤 ROI 变化 |
| Denoise `+1` | 噪声不足、曾绑 Details | fixed-seed 亮度/色度噪声，真实主控件 | readback；噪声统计下降 |
| Denoise Laplacian `+1` | 主/辅助语义不明 | 同噪声输入，核对 Luminosity/Color/Boost | metadata/control 一致 |

噪声 fixture 保存 seed、生成算法、源 hash 和噪声统计；它直接属于当前 1.28 验证集，不需要历史兼容代码。

### 9.2 定向重观察

- 主队列 AX：`queue-overlay-4c5931833a03`、`queue-overlay-bdbba755f19c`、`queue-overlay-66c244f43ca2` 的 `before.ax.txt` 已被历史硬链接覆盖。只重观察这 3 条的 AX/before/after/metadata，并验证新文件不是硬链接共享 inode；其他 248 条不重采。
- Anaheim LUT：source/reference MAE `0.003743`、SSIM `0.999938`，确认基本未生效。核对 asset hash、Amount、readback 后只重观察该 case。
- Color Enhancer：native preview/export `rgb_mae=0.030780`。先查 color profile、稳定窗口和导出完成条件。
- Overlay `queue-overlay-e977d0dc815c`：重新核对素材 thumbnail、id/path/hash、AX 与 export。

invalid registry 不能豁免 required。新 attempt 验证通过后发布新 canonical；旧 canonical 保留撤销审计，不原地覆盖。

### 9.3 黑白与长推理

- 黑白工具先点击“转换为黑白”，状态完成后再调亮度/饱和度。
- 控件 readback 后仍检查 preview 稳定与 export 变化，避免效果未应用就导出。
- AI 工具等 loading 消失、slider enabled、preview 稳定、export 变化；不只追加固定 sleep。
- 单模型推理期间持续续租 lease，旧 worker 不覆盖新 worker/cancel/terminal。

### 9.4 导出耗时和卡页优化

当前保存面板核心路径已由约 `70.517s` 降到约 `1.715s`，后续不能再把所有等待归因于“重命名”。每次必须分别记录：效果/模型稳定、打开导出面板、确认导出、文件出现、文件 size/mtime 稳定、图片 verify、canonical publish。只有同机同 fixture 的分段 p50/p95 才能用于判断瓶颈。

- 每个 attempt 使用唯一 export stem 和唯一 staging 目标，禁止触发覆盖/替换确认框。
- 重试创建新 attempt，不覆盖旧文件；成功后再以原子 publish 更新 canonical pointer。
- 文件出现后等待 size/mtime 稳定并执行图片解码校验，不能只看到文件名就继续。
- 以面板消失、目标文件稳定、preview/export 变化等语义条件替代全局固定 sleep。
- 若 UI 卡在导出页，先保存 screenshot、AX、当前 focus、目标路径和阶段计时，再恢复/重试；不进行无证据的重复点击。
- 性能优化只借用本来就必须采的 pending case 测量，不重采 ready canonical。

先 dry-run 确认只选目标记录；改造后的计划产物名为 `sampling-queue-exact-pending.json`：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-pending.json \
  --resume --retry-failed --dry-run
```

真实 GUI 每次一条：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-pending.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --allow-ui-control
```

每条后立即跑 effect-change audit、data-chain validator 和 parity。验收要求 `invalid-unchanged-export=0`，同 attempt 的 preview/export/metadata 完整，旧 ready canonical hash/mtime 不变。

## 10. P3：效果算法收敛

### 10.1 单能力闭环

1. 读取 source、native/candidate preview/export。
2. 生成 RGB/Luma MAE、SSIM、shape、区域统计和热力图。
3. 分类为 tone、mask、geometry、asset、position、random-statistics 或 color-management。
4. 写复现共享根因的窄测试。
5. 只改一个 pipeline/helper/contract。
6. 只 force 目标 candidate。
7. 跑目标、holdout、中性 anchor 和同域回归。
8. 记录 before/after 与双跑 hash。

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id>
```

### 10.2 批次顺序

1. 先关闭 LUT、Color Enhancer、Sky/Overlay 素材真值；真值不可信时禁止拟合。
2. `blue_hour` → `fog` → `depth_volume`：固定 depth 方向、值域、resize；共享最小 normalization，不共享未经验证的 tone curve；检查边缘 halo。
3. Sunrays：把太阳 position/坐标空间/readback 纳入合同；不从单图 sky mask 或固定中心猜位置；对齐遮挡、衰减、暖色和前景保护。
4. Sky Replace：保持 Sky 46/46，只处理 horizon、边缘去色、reflection/relight、曝光/白平衡和人物细枝保护。
5. Face AI 尾差 → Slim People：Face 当前 MAE `0.030197`，只处理 mask feather/局部 tone；Slim 使用人体 ROI 局部 warp，保护脸和背景直线，禁止整图横向缩放。
6. 其余 exact：按 capability 汇总 `-1/0/+1`；单调语义用单调曲线；Grain 用统计 comparator；shape/reference 错误回数据链；0 保持 no-op。

P3 准出：基础 45/45，合法 exact effect 全过，Preset 123/123、Sky 46/46 不回退，shape 一致，默认 `MAE<=0.03`、`SSIM>=0.98`，双跑稳定，无 case-id/像素坐标特判。

## 11. P4：Overlay 和 Multi-image

### 11.1 Overlay

只处理唯一失败：先重观察 asset id/path/hash。若 reference 错配，只发布该项新 canonical；若素材正确，再分析 stretch、blend、opacity、色彩空间和 alpha。其他 37 条保持通过与 hash 稳定。

```bash
.venv/bin/python scripts/run_overlay_e2e_validation.py
```

### 11.2 HDR 与 Focus

HDR 当前 MAE `0.025352`、SSIM `0.992789` 已通过；保留相同帧 no-op、真实 bracket tone curve、shape/color/hash 回归。Focus 已通过，只补边界/噪声 holdout。除非回归失败，两者不再改造。

### 11.3 Panorama

当前 candidate `1080×1440`，原生 `1070×1410`，MAE `0.081580`、SSIM `0.816616`。依次处理：

1. 保留已修正的 exhaustive overlap，验证 feature/overlap。
2. 建立原生投影模型，不以平移拼接作为最终实现。
3. 计算 warp 有效像素 mask 和 canvas bounds。
4. 复刻非对称 auto-crop，解释宽 10px、高 30px 的差异。
5. shape 对齐后处理 exposure compensation、seam path、feather。
6. 增加背景直线、移动物体、曝光差 holdout。

入口：`image_ops/merge/panorama.py`。禁止最终强制 resize 或硬编码 `1070×1410` crop。

```bash
.venv/bin/pytest -q \
  tests/test_panorama_merge.py \
  tests/test_workflows.py \
  tests/test_multi_image_validation_data.py

.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke-current.json
```

P4 准出：Overlay 38/38，Multi-image 3/3，shape 一致，双跑稳定。

## 12. P5：UI 7 状态像素对齐

视觉方向唯一采用 Luminar 1.28 精密编辑工作台：预览画布优先、暗色层级克制、右栏紧凑。原生截图/AX 是设计源，不新增卡片、渐变、圆角或营销式层级。

主要入口：`frontend/src/App.tsx`、`frontend/src/styles.css`、`CatalogWorkspace.tsx`、`PresetBrowser.tsx`、`PreviewPanel.tsx`、`ToolPanel.tsx`、`LayersPanel.tsx`、`WorkflowWorkspace.tsx`。

实现顺序：

1. shell：背景、top bar、三栏宽度、canvas、滚动所有权；
2. tokens：surface/text/accent/border/radius/spacing；
3. typography：字体、字号、字重、行高、数字；
4. 共享控件：button/tab/slider/tool-row/panel/tooltip；
5. `catalog` → `presets` → `edit` → `tool-expanded` → `layer-stack` → `layer-library` → `multi-image`；
6. hover/focus/selected/disabled/loading/empty/error。

每个 state 单独做同尺寸截图、区域 MAE/changed-pixel/heatmap；先修最大面积几何，再修字体和颜色；Browser 重拍当前 build；通过后锁定，共享 token 变化回归已锁状态。

```bash
cd /Users/iknow/Works/python/zpixel_edit/frontend
npm test
npm run build

cd /Users/iknow/Works/python/zpixel_edit
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

准出：7/7；fixture/build/viewport/DPR/locale/hash 一致；shape exact；每张 MAE `<=0.03`、changed ratio `<=0.02`；无双滚动、布局跳动、加载覆盖；focus/disabled 语义一致。

## 13. P6：10 个交互合同

顺序：`catalog-import-select`、`preset-preview-apply`、`edit-slider-drag`、`edit-toggle-collapse`、`layer-add-reorder-opacity-delete`、`undo-redo`、`before-after-compare`、`zoom-pan`、`export-dialog`、`multi-image-workflow`。

每条保存 native before/after、AX/observation、事件顺序；candidate before/after、browser events、network/console、API mutation、最终 project/workflow JSON、wait condition、native/fixture/build hash。

硬约束：

- import 只创建一个 asset/project；preset preview 不落 edit，Apply 一次提交；
- slider 实时预览，commit 只建一条语义 edit；collapse 只改视图；
- layer id/order/opacity/delete 在 UI 和 project JSON 同步；
- undo/redo 恢复相同 edit id、参数、layer 顺序和输出；
- before/after、zoom/pan 不修改项目/导出；
- export 只发一个请求，busy 正确解除，尺寸/content-type 正确；
- multi-image 有 progress/cancel/error/retry/result，ready 前不可导出；
- newest-request-wins，旧响应不覆盖新项目/预览/error；
- 卸载时清 poller，不取消仍需完成的服务端长任务；
- 使用语义 wait，不用 fixed sleep。

```bash
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py
```

准出：native+candidate 10/10，issue 0，fixed sleep 0，artifact/hash 完整，无重复 mutation、过期覆盖或 poller 泄漏。

## 14. P7：模型推理和长任务

required 模型已 22/22。只有 wrapper 的输入色彩/resize/normalization、tensor shape/dtype、输出解释、cache/lifecycle 或模型原始 ROI/mask/depth 被证实错误时才修改 `ai/model`。若差异来自 mask 后处理、强度曲线、composite、tone mapping 或业务选择，修改 `ai/pipeline`/`image_ops`。

边界：

```text
ai/model       load → preprocess → predict → postprocess → unload
ai/pipeline    组合模型输出和效果语义
services/jobs  enqueue → lease → checkpoint → cancel/retry → result
frontend       poll/restore → 完整结果合并 → 展示
```

长任务故障注入：第 N 个模型后重启不重跑 checkpoint；单模型持续 lease；stale worker 不覆盖；刷新/切项目恢复正确 latest job；terminal 后完整拉取并验 hash 再 merge；cancel/fail 保留错误和 checkpoint；loader 淘汰调用 `unload_model()`，active lease 不淘汰。

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py --project-root .
.venv/bin/python scripts/build_model_source_map.py
.venv/bin/pytest -q \
  tests/test_active_model_contracts.py \
  tests/test_candidate_model_invocations.py \
  tests/test_model_loader.py \
  tests/test_model_outputs.py \
  tests/test_model_source_map.py \
  tests/test_inference_job_lease.py \
  tests/test_inference_job_repository.py
```

optional inventory 不通过实现 66 个不可达模型消除，继续作为非阻断审计项。

## 15. P8：回归、双跑、清理和发布

### 15.1 全量回归

```bash
cd /Users/iknow/Works/python/zpixel_edit
.venv/bin/python -m pytest -q
.venv/bin/ruff check .

cd /Users/iknow/Works/python/zpixel_edit/frontend
npm test
npm run build
```

### 15.2 required exact 双跑

```bash
cd /Users/iknow/Works/python/zpixel_edit
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-run-1.json
```

中间不改代码、配置、fixture、reference、candidate 或 canonical，直接第二轮：

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-release-run-2.json
```

两轮 required failed 均为 0；gate 集合、dataset/cohort/reference/fixture/build fingerprint、candidate 和关键报告 hash 一致。optional 单独报告。

### 15.3 test_data 清理

发布双跑通过前只 dry-run：

```bash
.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/test-data-cleanup-release-dry-run.json
```

逐项确认只有可重建 workspace/transient 后 apply：

```bash
.venv/bin/python scripts/cleanup_test_data.py \
  --apply \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/test-data-cleanup-release.json
```

当前约 233,951,310 bytes Overlay workspace 在 required blocked 时先保留。canonical、当前 candidate、失败诊断、最后 attempt、state/log/metadata 不因内容重复而删除。

发布产物包括 baseline/release manifest、active cohort、空 pending worklist、双跑报告、各域结果、UI/interaction evidence、model source/call 报告、cleanup 报告和冻结范围声明。

## 16. 失败路由、停止和回滚

| 现象 | 修改域 | 禁止动作 | 准出 |
|---|---|---|---|
| native export≈source | fixture/recipe/sampler | 拟合 unchanged reference | 新证据有效 |
| native preview/export 不一致 | export/color contract | 任取一张当真值 | 同 attempt 一致 |
| shape 不一致 | geometry/workflow | 最终 resize | 原生 shape 可解释 |
| 大面积 tone 差 | pipeline/image_ops | 单 case RGB 常数 | target+holdout+neutral 过 |
| 局部 halo | mask/resize/feather | 全图模糊 | ROI/边缘过 |
| UI changed ratio 高 | shell/tokens | 随机 CSS 微调 | 几何先闭环 |
| 交互偶发回退 | state machine | fixed sleep | newest-request-wins |
| 模型不稳定 | ai/model contract/lifecycle | pipeline 隐藏随机性 | tensor/result 双跑稳定 |
| ready 又入队 | cohort/worklist builder | 手改 JSON | 选择测试通过 |
| 磁盘重复 | cleanup/artifact role | 按 hash 批删 | dry-run 无证据丢失 |

每批记录 batch id、单根因假设、输入/reference/candidate/contract/build hash、修改文件、目标+holdout、before/after、是否改变真值、回滚点和下一批准入。

出现 Browser/build/fixture hash 不符、真值无效、control/range 不明、系统性 unchanged、holdout 回退、双跑不确定、需要降门限/强制 resize/case 特判、cleanup 目标仍被引用时，立即停止当前域。

代码按单根因回滚；reference/canonical 不原地覆盖；fixture/contract 变化生成新 revision；frontend build 变化使相关 Browser evidence 失效；candidate `--force` 只选目标 case；回滚后重跑同域 holdout 和 exact anchor。

## 17. 最终完成定义

- [ ] 只有活动 1.28 reference，无历史运行时兼容分支；
- [ ] active cohort 只含合法可表达合同，pending worklist 为空；
- [ ] ready canonical artifact/hash/metadata 完整；
- [ ] 效果 45/45，合法 exact 全过；
- [ ] Preset 123/123、Sky 46/46、Overlay 38/38；
- [ ] HDR/Focus/Panorama 3/3；
- [ ] UI 7/7，Interaction 10/10；
- [ ] required model source/call/contract 通过；
- [ ] Python/Ruff/Frontend test+build 通过；
- [ ] invalid registry 无未关闭 required 项；
- [ ] 无 ready/unchanged 重采；
- [ ] 长任务恢复完整结果，无 stale overwrite；
- [ ] required exact 连续两次失败集合为空；
- [ ] 两轮 fingerprint 和关键 hash 一致；
- [ ] cleanup apply 后 manifest/data-chain 不变；
- [ ] 发布声明严格限定冻结范围。

## 18. 下一轮严格执行顺序

1. `codex app .` 恢复 Browser。
2. 拆 active cohort/pending worklist，先迁移非法 Face 负值且保留 60 条成功证据。
3. 建 Slim/Magic/Denoise/Skin/Neon 的适用 fixture/recipe。
4. 定向重观察 LUT、Color Enhancer、唯一 Overlay 错配，不重采成功项。
5. 关闭大气/深度、Sunrays、Sky、人像及其余 exact。
6. 关闭 Panorama，保持 HDR/Focus。
7. Browser 逐状态关闭 UI 7/7。
8. UI 稳定后关闭 interaction 10/10。
9. 仅证据触发时修模型 wrapper，并完成长任务故障注入。
10. 全量回归、required 双跑、cleanup dry-run/apply、发布冻结声明。

该顺序先修“真值是否可信”和“验证全集是否正确”，再修候选像素，避免重复采样成功证据和对错误 reference 过拟合。
