# Luminar Neo 1.28.0 完全对齐可执行优化计划（R19）

> 基线日期：2026-09-17
>
> 参考对象：Luminar Neo for macOS `1.28.0 (23071)`，`zh-Hans`
>
> 参考 ID：`luminar-neo-macos-1.28.0-23071`
>
> 适用范围：本仓库当前定义的 40 个本地免费核心能力、当前 UI/交互矩阵和相关本地工作流。

## 1. 结论先行

当前工程已经具备较完整的对齐基础设施，但尚不能声明“与 Luminar APP 完全对齐”。主要问题不是单点缺陷，而是六条链路同时未闭环：

1. 验收定义仍混合了应用自有 UI 与 macOS 系统 UI，存在技术上不可比较的用例。
2. 精确采样矩阵按全局 `amount=-1..1` 生成锚点，制造了 23 个 Luminar 原生滑杆无法表达的伪阻塞。
3. 浏览器侧已能覆盖 84 条交互契约，原生采集器只实现了 10 条工作流处理器，74 条参数交互没有执行证据。
4. 40 个主效果中仍有 5 个未达标；精确 cohort 有 8 个失败、75 个缺少参考结果。
5. 170 个 UI 状态均已有浏览器证据，但像素门禁为 `0/170`；差异以全局布局、字体、图像视口和复用控件为主，不适合逐截图打补丁。
6. Native persistence 仅有门禁和 delta 工具，没有可验证的 Luminar 工程/history 编解码实现。

因此，正确顺序必须是：先修验收模型和证据链，再收敛算法/UI，最后切换持久化与发布。直接继续调 CSS、滤镜常量或放宽阈值，只会把错误口径固化到实现中。

## 2. “完全对齐”的可验收定义

### 2.1 固定范围

R19 只验收以下范围：

- 当前 `configs/parity.yaml` 定义的 40 个可见核心能力；
- `configs/parity/core-ui-state-matrix.json` 中的 170 个当前 UI 状态；
- `configs/parity/core-interaction-matrix.json` 中的 84 条当前交互契约；
- 当前 3 条多图工作流、预设、天空素材、叠加素材、预览和导出；
- `configs/model.yaml` 当前注册的 22 个逻辑模型，而不是 `models/contracts/` 中全部 92 个历史/库存契约。

付费、云端、商店、教程、账户及未在产品范围清单中的隐藏能力不自动进入 R19。新增范围必须先更新产品范围、矩阵和门禁，再进入实现。

### 2.2 四种对齐级别

| 维度 | 验收定义 | 证据 |
|---|---|---|
| 功能 | 同一操作可完成，错误状态和边界行为一致 | API/服务测试、工作流 trace |
| 交互 | 控件类型、范围、步长、默认值、状态转换、撤销/重做一致 | Native + Browser observation |
| 输出 | 同一输入、参数、素材和版本下达到冻结的图像指标 | preview/export、参数和模型指纹 |
| 视觉 | 应用自有区域在固定显示环境下达到 UI 指标 | 截图、区域 mask、DOM/AX、字体与资产指纹 |

只有四类证据都通过，才允许对该能力标记 `parity-passed`。`runtime-ready`、单元测试通过、人工“看起来相似”或仅主参数通过均不能替代精确门禁。

### 2.3 必须先做的平台决策

当前 `workspace:export-dialog` 的 Native 参考是 macOS 系统 Save Panel，而候选端是浏览器自绘弹窗。两者无法实现全屏像素相等。

R19 推荐规则：

- Luminar 自有界面：要求区域级像素对齐；
- macOS 系统窗口、文件选择器和系统菜单：要求字段、行为、键盘操作、可访问性和最终输出语义对齐，不做浏览器像素门禁；
- 若产品要求连系统窗口也逐像素一致，则必须把交付形态改为原生 macOS 宿主，并将其作为独立架构项目，不应继续在当前 Web UI 上调样式。

此规则落地前，UI 分数不能作为有效的最终发布结论。

## 3. 当前代码与数据流

```text
React/Vite frontend
  -> FastAPI routes (api/)
  -> editor orchestration (services/editor/service.py)
  -> capability / workflow pipelines
       -> ai/pipeline/*
       -> image_ops/effects/*
       -> ai/model factory + loader + wrappers
  -> project/catalog adapters (storage/)
  -> preview/export artifacts

Luminar Native capture
  -> sampling/interaction runners (scripts/)
  -> versioned reference artifacts (test_data/outputs/...)
  -> parity reports
  -> 37 exact quality gates
```

当前最明显的维护热点是 `services/editor/service.py`、`ai/pipeline/image_effect_pipelines.py`、`image_ops/effects/basic.py`、`frontend/src/App.tsx` 和 `frontend/src/styles.css`。R19 不建议先做大范围重构；只有在某个对齐差异已被证据定位后，才做最小、可回归的边界拆分。

## 4. 已验证基线

以下数字来自当前矩阵、R18 最终证据和本地验证，不使用旧 R17/R18 文档中的 210 UI / 124 interaction 数字。

| 项目 | 当前状态 | 结论 |
|---|---:|---|
| Canonical 采样队列 | `409/409 ready` | 基础采样链完整 |
| UI 矩阵 | 170：16 workspace、80 panel、74 parameter | 当前实际范围 |
| Browser UI 执行 | `170/170 passed` | 仅证明候选截图完整 |
| UI 像素门禁 | `0/170 passed` | 全部仍需收敛或纠正 ROI |
| 交互矩阵 | 84：10 workflow、74 parameter | 当前实际范围 |
| Browser 交互 dry-run | `84 supported` | 候选侧契约可执行 |
| Native 交互执行 | `0/84` 正式执行；runner 仅支持 10 workflow | 当前关键阻塞 |
| 主效果输出 | `35/40 passed` | 5 个主效果失败 |
| Exact 活动 cohort | 133：50 pass、8 fail、75 pending reference | 数据链未闭环 |
| Exact semantic matrix | 206：58 existing、75 added、73 blocked | 其中 23 个为错误参数域 |
| 绝对范围问题 | 217 | 包含 holdout、参数和交互缺口 |
| 模型配置 | 22 个 active，22/22 contract validated | 模型结构不是首要阻塞 |
| Exact quality gates | `30/37 passed` | 7 个门禁失败 |
| 后端测试 | `433 passed` | 2026-09-17 本地运行 |
| 前端测试 | `46 passed` | 2026-09-17 本地运行 |
| Ruff / frontend build | passed / passed | 工程健康基线正常 |

7 个失败门禁为：absolute scope coverage、exact incremental data chain、output parity、exact incremental parity、UI parity、interaction execution、native persistence roundtrip。

## 5. 根因分析

### 5.1 真相源与文档漂移

`docs/parity/README.md` 和旧计划仍写 210 个 UI 状态、124 条交互；README 中的 92 个逻辑模型也不是当前激活模型数。矩阵已变化，但说明文档、执行报告和某些固定数字没有从配置生成。

根因不是“文档没及时改”，而是同一事实存在多个手写来源。解决方向是让配置和不可变 run evidence 成为唯一真相源，文档只引用或生成摘要。

### 5.2 参数域错误导致伪阻塞

`configs/capabilities/parameter-schema.json` 把通用 `amount` 定义为 `[-1, 1]`，`scripts/build_exact_sampling_matrix.py` 对所有 float 生成 default/min/mid/max。很多 Luminar 工具的原生 amount 实际是正值范围，增量队列因此把负值锚点标为 `native-negative-amount-unrepresentable`。

73 个 blocked case 应拆为：

- 23 个错误负值锚点：修 schema/生成逻辑，不应实现自动化；
- 26 个缺少原生参数契约：clone、color transfer、crop、deblur、dodge & burn、erase、LUT；
- 24 个已有语义但未自动化：bokeh、denoise、new neon。

### 5.3 原生交互执行器没有覆盖参数契约

`scripts/run_luminar_interaction_observations.py` 目前通过 `HANDLERS` 只分发 10 个工作流函数；虽然 `configs/parity/native-parameter-bindings.json` 已有 74 条 supported binding，runner 仍会把这些 contract 判为 unsupported。

这不是证据不足，而是执行层缺少基于 binding kind 的统一 dispatcher。继续手写 74 个 handler 会重复状态恢复、readback、截图和错误处理，应实现 7 类原子操作并由 binding 数据驱动。

### 5.4 效果输出差异集中在共享管线

主矩阵失败项：

| 能力 | MAE | SSIM | 首要检查路径 |
|---|---:|---:|---|
| `face_ai` | 0.030175 | 0.9841 | face ROI、skin mask、前景保护 |
| `depth_volume` | 0.06919 | 0.9603 | depth polarity、归一化、局部映射 |
| `blue_hour` | 0.03946 | 0.9753 | tone curve、色域与混合次序 |
| `sky_replace` | 0.031238 | 0.98047 | horizon、mask、反射、前景保护 |
| `sunrays` | 0.05371 | 0.95622 | 光源中心、射线几何、sky mask |

Exact 另有 `structure_ai`、`landscape_enhancer`、`color_enhancer`、`complex_bleach` 等失败。`ai/pipeline/image_effect_pipelines.py` 自身已说明当前实现是兼容集成层，并不代表恢复了 Luminar 私有后处理。因此模型契约通过不能推出效果等价；必须在能力层做黑盒校准。

### 5.5 UI 是系统性偏差，不是 170 个独立问题

当前 UI MAE 范围约为 `0.02899–0.17016`，changed pixel ratio 为 `0.2815–0.99659`。即便最接近的状态也有约 28% 像素变化，说明问题位于共享层：

- 画布/侧栏/底部胶片条几何关系；
- 字体度量、字号、字重和抗锯齿；
- 图像 fit、缩放、背景和裁剪位置；
- 图标资产与控件高度；
- `styles.css` 前后两组规则的 cascade 覆盖；
- 系统窗口被错误纳入全屏比较。

最差状态包括 multi-image complete、denoise、deblur、catalog、presets 和 export dialog。应先校准共享布局 token，再处理 workspace 和工具族，不能逐状态追加 CSS override。

### 5.6 持久化门禁超前于实现

当前 `api/app.py` 仍组合 `JsonProjectRepository`；`storage/catalogs/luminar_sqlite.py` 主要操作 catalog metadata，并非 Luminar project/history 编解码器。`validate_native_persistence_roundtrip.py` 只验证 7 类 manifest 是否存在且可重开，当前缺少完整 manifest。

如果“完全对齐”包含“Luminar 可直接重开并继续编辑本项目”，就必须实现受控的 v155 codec/repository；如果只要求用户可见行为一致，则不应把私有工程格式互操作设为强制范围。R19 默认保留该门禁，但要求在隔离副本上完成，禁止写用户真实 catalog。

## 6. 执行原则与依赖关系

```text
WP0 冻结范围与验收语义
  -> WP1 修参数域与矩阵生成
       -> WP2 补 Native 参数交互执行器
       -> WP3 完成 reference / holdout / repeatability
            -> WP4 效果算法收敛
  -> WP5 UI 比较口径与共享视觉系统
       -> WP6 84 条双端交互闭环
  -> WP7 Native persistence（仅在范围确认后）

WP4 + WP5 + WP6 + WP7
  -> WP8 性能、资源和模型发布约束
       -> WP9 两轮不可变最终验收
```

并行边界：WP4 与 WP5 可在 WP1 基线冻结后并行；WP6 必须等待 WP2；WP7 可独立研究，但不能提前切换生产 repository；WP9 必须等待其余工作包完成。

## 7. 详细工作包

### WP0：建立唯一真相源并冻结 R19 范围

目标：所有人基于同一矩阵、同一版本、同一显示环境和同一验收语义工作。

修改入口：

- `configs/reference.yaml`
- `configs/parity.yaml`
- `configs/parity/core-ui-state-matrix.json`
- `configs/parity/core-interaction-matrix.json`
- `configs/parity/native-capture-environment.json`
- `scripts/build_release_fingerprint.py`
- `docs/parity/README.md`

执行步骤：

1. 冻结 reference ID、Luminar build、语言、逻辑/物理分辨率、DPR、fixture、素材和字体环境。
2. 为 UI state 增加 `surface_owner: app|os` 和 `comparison_mode: pixel|semantic`；系统 Save Panel 不再进入应用像素统计。
3. 由脚本输出 UI 数、interaction 数、active model 数和能力数，禁止在文档手写第二份计数。
4. 生成 R19 release fingerprint；任何矩阵/schema/素材变化必须产生新 fingerprint，并使旧证据 fail-closed。
5. 将 R18 evidence 保持只读，不覆盖旧 run；R19 使用新 run ID。

验收：

- 文档与配置均报告 170 UI、84 interaction、40 capability、22 active model；
- 系统表面与应用表面的门禁规则可机器校验；
- 同一输入连续两次生成相同 fingerprint；
- 旧 fingerprint 证据不能被 R19 gate 接受。

回滚：仅回滚新 schema 字段和生成脚本；不修改或删除任何 R18 evidence。

### WP1：修正参数契约与 exact matrix

目标：采样矩阵只生成 Luminar 能表达、候选端也有明确映射的参数值。

修改入口：

- `configs/capabilities/parameter-schema.json`
- `configs/parity/native-parameter-bindings.json`
- `scripts/parity_parameter_values.py`
- `scripts/build_exact_sampling_matrix.py`
- `scripts/build_incremental_sampling_queue.py`
- 对应 `tests/scripts/` 测试

执行步骤：

1. 为每个 capability/parameter 建立 `native_min`、`native_max`、`native_default`、`step`、`signed` 和候选值转换规则；通用 schema 只做类型默认，不再替代能力级范围。
2. 只对 Native 已观察为 signed 的控件生成负值锚点；其余 amount 使用 native min/default/mid/max。
3. 对 enum、boolean、asset、crop box 和 stroke 使用离散语义锚点，不套 float 规则。
4. matrix builder 遇到无法映射的锚点时直接报 schema 错误，不生成“等待自动化”的伪 case。
5. 补齐 26 个 missing contract 和 6 个未表示参数：crop box/ratio/flip、deblur face enhancer/sharp level。
6. 重新生成 exact matrix、incremental queue 和 fingerprint，并输出 old/new case diff。

新增测试至少覆盖：正值 amount、真正 signed 参数、步长量化、enum 全值、asset hash、crop box、schema 缺失时 fail-closed。

验收：

- `native-negative-amount-unrepresentable` 从 23 降为 0；
- 所有 case 都能回溯到 capability + parameter + native range；
- matrix 生成两次字节级稳定；
- 未映射参数使构建失败而不是静默跳过。

回滚：保留 R18 matrix 和 queue；R19 新文件未通过审核前不得替换 current pointer。

### WP2：实现数据驱动的 Native 参数交互执行器

目标：Native runner 对全部 84 条契约提供真实执行能力和可审计 readback。

修改入口：

- `scripts/run_luminar_interaction_observations.py`
- `scripts/luminar_capture/accessibility_driver.py`
- `scripts/luminar_capture/semantic_locator.py`
- `scripts/luminar_capture/state_machine.py`
- `configs/parity/native-parameter-bindings.json`

实现 7 类 dispatcher：

1. `slider`：聚焦、设置、键盘微调、读取显示值；
2. `button`：点击并读取 selected/enabled 状态；
3. `menu-choice`：打开、按语义选择、读取当前项；
4. `asset-picker`：按资产 ID/hash 选择并验证缩略图/标签；
5. `stroke`：固定画布坐标、笔刷配置和输入轨迹；
6. `crop-box`：固定坐标系下设置 box/ratio/flip；
7. `semantic-readback`：用于只能观察、不能直接赋值的原生状态。

每条执行必须遵循：恢复基线 → 定位控件 → 记录 before → 执行动作 → 稳定等待 → 记录 after/readback → 截图/AX/日志 → 撤销或重置 → 验证无状态泄漏。失败记录定位策略、候选节点和截图，禁止用坐标 fallback 冒充成功。

验收：

- dry-run 显示 `84/84 supported`；
- 正式执行 `84/84 executed`，每条包含 Native observation、前后状态、artifact hashes 和 reference fingerprint；
- 任一定位歧义、值未变化或 readback 不匹配均 fail-closed；
- 重新运行同一 contract 不依赖前一 contract 的残留状态。

回滚：保留当前 10 个 workflow handler；dispatcher 可通过单一入口禁用，但不得保留两套并行写证据逻辑。

### WP3：补齐参考、holdout 与重复性数据

目标：先让数据链完整，再判断实现差异，避免根据单张截图或单一输入过拟合。

执行顺序：

1. 先执行现有 75 个 `pending reference`，按 capability 分批并使用 `--resume`；天空替换 28 个 case 单独成批。
2. WP1 后执行新增/修正的合法参数锚点。
3. 为每个 40 核心能力加入至少 2 个非 canonical holdout，覆盖不同内容类别、分辨率和困难边界。
4. 在代表性能力上重复导出至少 3 次，量化 Native 自身方差；阈值必须高于噪声地板并保留安全裕量。
5. 固定 input、parameter、asset、model、preview、export 和环境 hash，完成 exact data chain。

执行命令示例：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --resume --preflight

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --resume --allow-ui-control

.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/validate_sampling_data_chain.py
```

验收：

- pending reference 为 0；
- 40/40 能力各有 canonical + 至少 2 个 holdout；
- 所有引用都绑定 R19 fingerprint，hash 和 provenance 完整；
- 重复性报告给出 MAE/SSIM 分布，`configs/parity.yaml` 阈值不再标记 provisional。

停止条件：Native 应用版本、语言、分辨率或 fixture 不一致时立即停止本批，不允许事后补 metadata。

### WP4：按共享根因收敛效果输出

目标：主矩阵、exact 参数锚点和 holdout 同时通过，不以放宽阈值或仅调 canonical 图为手段。

每个能力使用同一闭环：

1. 固定失败 case，保存 Native/candidate preview、export、参数、素材和模型 hash。
2. 输出必要中间量：mask/depth/face boxes、tone curve、blend weights、工作色域和 resize 信息。
3. 将差异分类为模型输入、模型输出解释、mask、色彩空间、混合顺序、参数映射或导出编码。
4. 先添加能重现根因的窄测试，再修改最小实现。
5. 运行当前能力的 main + exact + 两个 holdout，然后运行同共享管线的回归组。
6. 中间调试产物进入 run 目录，不在生产路径永久写盘。

建议批次：

| 批次 | 能力 | 原因 | 主要代码 |
|---|---|---|---|
| A | `depth_volume` | 当前误差最大且能校准 depth 语义 | `ai/pipeline/image_effect_pipelines.py` |
| B | `sky_replace`、`sunrays`、`landscape_enhancer` | 共享 sky/foreground mask | `ai/pipeline/*`、`image_ops/effects/sky_compositor.py` |
| C | `blue_hour`、`color_enhancer`、`complex_bleach` | 共享色彩/曲线/混合问题 | `image_ops/effects/basic.py`、pipeline |
| D | `face_ai` | 独立人像 ROI/skin mask | `ai/pipeline/image_effect_pipelines.py` |
| E | `structure_ai` 及新增 exact 失败 | 收尾局部细节算法 | pipeline/effect implementation |

算法修改约束：

- `ai/model/` 只负责模型契约、加载、推理和资源生命周期；Luminar 风格后处理留在 pipeline/effect 层；
- 不引入根据 fixture hash 或 case ID 分支的“答案表”；
- 不把输出 clip、resize 或色彩转换隐式塞进 model wrapper；
- 不以降低 SSIM、提高 MAE 或忽略大面积区域作为修复。

验收：

- 主效果 `40/40 passed`；
- 重建后的 exact cohort 全部通过；
- 每个能力的 2 个 holdout 通过；
- 同一模型/素材/输入重复运行结果满足确定性约束；
- 所有 model 层变更通过 `python scripts/validate_model.py` 和相关资源释放测试。

### WP5：重建 UI 测量口径并收敛共享视觉系统

目标：先消除系统性偏差，再逐工作区收尾，使 UI 门禁具有可解释性。

阶段一：比较器正确性

1. 按 `surface_owner` 选择 pixel 或 semantic comparator。
2. 为 app-owned 截图定义稳定 ROI，排除系统菜单栏、Save Panel 和非应用通知。
3. 对字体、DPR、浏览器缩放、视口、图像解码和截图色彩空间做 preflight。
4. 做 Native 重复截图，确认阈值覆盖采集噪声而不是覆盖实现误差。

阶段二：共享 token

从 Native 几何证据提取并冻结：顶栏、左/右栏、胶片条、画布 padding、控件行高、圆角、字号、字重、颜色、间距、图标 bounding box。把 token 放入单一 CSS 层，清理 `frontend/src/styles.css` 中重复且相互覆盖的布局规则。

阶段三：按层收敛

1. Shell：viewport、sidebars、canvas、filmstrip、bottom bar；
2. Typography/icons：字体度量、图标资产和基线；
3. 16 个 workspace，先处理 multi-image、denoise、deblur、catalog、presets；
4. 80 个 tool panel，按复用组件族一次修复；
5. 74 个 parameter modified state，验证控件值和视觉状态同步；
6. export dialog 按平台决策走 semantic 或 native-host 路线。

组件拆分只服务于可测边界：从 `frontend/src/App.tsx` 提取 workspace shell/state controller，从 `ToolPanel.tsx` 提取 slider/enum/boolean/asset/crop 等稳定控件族；不要在 R19 同时引入新的状态管理框架。

验收：

- comparator 自测能识别 1 px 位移、字体变化和错误 ROI；
- app-owned UI 状态全部通过冻结阈值；
- semantic OS states 的字段、焦点、键盘、取消/确认和输出均通过；
- 不存在仅为某个 matrix state ID 生效的 CSS 选择器；
- 170 个状态都保留 screenshot、DOM、AX、capture metadata 和 build hash。

### WP6：闭环 84 条双端交互

目标：把“控件看起来一样”升级为“同一操作产生同一状态与输出”。

执行步骤：

1. 使用 WP2 产生的 84 条 Native observations 作为唯一交互基线。
2. 冻结前端 build hash 后执行 84 条 Browser contracts。
3. 比较 before/after 值、显示文本、enabled/selected、preview 变化、撤销/重做、持久化和导出影响。
4. 对连续滑杆验证 min/default/mid/max、步长、键盘微调和 reset；对离散控件遍历全值；对 asset/crop/stroke 验证稳定 ID 和坐标系。
5. 一次修复一个共享控件族，同时回归该族全部 contract。

验收：

- Native `84/84 executed and passed`；
- Browser `84/84 executed and passed`；
- contract fingerprint、Native observation ID、Browser build hash 三者完整关联；
- undo/redo 与刷新/重开后的状态符合契约；
- 无 issue、missing observation、unsupported 或人工豁免。

### WP7：Native persistence 受控实现与切换

目标：仅在产品确实要求 Luminar 工程互操作时，实现 7 类状态的真实重开验证。

安全前置：

- 只操作 `test_data` 下从模板复制出的隔离 catalog；
- 每次写入前记录文件 hash、schema version、事务和备份路径；
- 禁止自动发现并写入用户真实 Luminar library；
- 未通过 Native 重开前，任何 codec 输出都视为实验产物。

执行步骤：

1. 用 `capture_native_persistence_delta.py` 对单一原子操作做 before/after delta：project、edit-history、layer、mask、workflow、preset、preview-export。
2. 区分 SQLite 元数据、sidecar/blob、资源引用和顺序字段，建立最小 schema 文档。
3. 新建明确版本化的 v155 codec 和 repository adapter；读取器严格校验 magic/version/foreign key/hash，写入使用事务和原子替换。
4. 每实现一类状态即由 Luminar 原生重开、继续编辑、撤销并再次导出验证。
5. 7/7 通过后才在 `api/app.py` 用配置切换 repository；不做双写。
6. 稳定一轮后再单独清理不再使用的 JSON adapter，避免在同一提交同时实现、切换、删除回滚路径。

验收：

- 7 类 manifest 全部存在、hash 完整并由 Luminar 重开通过；
- 写入失败不破坏模板，事务可回滚；
- project/history/layer/mask 的顺序与引用关系稳定；
- 候选端与 Luminar 互开后，preview/export 和编辑状态符合契约。

若产品最终不要求文件格式互操作，则从 exact 发布门禁中移除该项，并用候选自身的 reopen/undo/export 行为门禁替代；必须留下明确的范围决策记录。

### WP8：模型、性能与资源发布约束

目标：在正确性闭环后，保证本地运行稳定且不因优化改变输出。

执行步骤：

1. 当前只维护 `configs/model.yaml` 的 22 个 active model；92 个 contract 文件作为库存审计，不计入 active 完成度。
2. 对 16 个已调用模型保持输入 shape/dtype/color order、normalization、postprocess 和 backend metadata 契约；对 6 个 configured-not-covered 模型，只有进入当前产品范围才补调用证据。
3. `OnnxModelService` 的 exact/release 模式必须加载由门禁生成的 parity ledger；development 模式不得被误标为 exact。
4. 测量冷启动、首帧、warm preview、export、峰值内存、模型 cache 命中和 unload；以 Native 实测分布设目标。
5. 性能优化后重新跑输出 hash/指标；禁止用降低分辨率、跳过模型或改变色彩精度换速度。

验收：

- 22/22 model contract validated，0 blocker；
- 资源 lease、LRU eviction、异常释放和重复加载测试通过；
- 40 个能力的 invocation evidence 与配置一致；
- 性能报告包含 p50/p95、冷/热状态、硬件和 fingerprint；
- exact release 不接受 `pending-reference` 能力。

### WP9：最终门禁与发布

目标：用两次独立、不可变 run 证明完成，而不是用一次偶然通过的工作区状态宣布完成。

发布前执行：

```bash
.venv/bin/ruff check api core services storage image_ops ai scripts tests
.venv/bin/python -m pytest -q

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_absolute_scope_coverage.py
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id r19-final-a

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id r19-final-b
```

最终 DoD：

- 37/37 exact gates 通过，或在 WP0 正式修订门禁后，新全集 100% 通过；
- absolute scope issue 为 0；
- main effects 40/40，重建后的 exact cohort 和全部 holdout 100%；
- app-owned UI 100%，OS-owned semantic states 100%；
- Native/Browser interaction 84/84；
- persistence 7/7，若范围决策保留该要求；
- 两次 final run 使用相同代码/配置/素材/model fingerprint，结果一致；
- 任一 `pending`、`blocked`、人工豁免、旧版本证据或无法追溯的 artifact 都阻止发布。

## 8. 建议实施批次与工作量

以下是单团队相对估算，不是完成承诺；Native 私有格式和黑盒算法存在研究不确定性。

| 批次 | 工作包 | 建议角色 | 相对工作量 | 退出标准 |
|---|---|---|---:|---|
| 0 | WP0 | parity owner + tech lead | S | 口径/fingerprint 冻结 |
| 1 | WP1 | parity infra + backend | M | 伪阻塞归零，新矩阵稳定 |
| 2 | WP2、WP3 | macOS automation + QA | L | Native 84 条、reference/holdout 完整 |
| 3A | WP4 | image/ML engineer | XL | 所有效果与 holdout 通过 |
| 3B | WP5、WP6 | frontend + visual QA | XL | UI/交互双端通过 |
| 3C | WP7 | storage/reverse-engineering | XL/高不确定性 | 7/7 原生重开，或范围移除 |
| 4 | WP8、WP9 | performance + release owner | M | 两轮全部门禁通过 |

关键路径是 `WP0 → WP1 → WP2 → WP3 → WP4 → WP9`。UI 可从 WP0 后并行；持久化研究可并行，但不得阻塞其他证据链，也不得提前切换运行时。

## 9. 风险、停止条件与回滚

| 风险 | 早期信号 | 应对与停止条件 |
|---|---|---|
| 对错误矩阵做优化 | case 无原生可表达值 | 停止算法工作，回到 WP1 |
| Native UI 定位漂移 | AX 节点歧义或坐标 fallback | 本批 fail-closed，更新 semantic locator |
| 过拟合 canonical fixture | 主样本通过、holdout 退化 | 不合并；增加根因测试并撤回常量 |
| UI cascade 补丁化 | state-specific selector 增长 | 停止局部补丁，回到共享 token/组件族 |
| 阈值掩盖误差 | changed ratio 很高但判 pass | 恢复阈值，先测 Native 重复性 |
| 模型层职责膨胀 | wrapper 出现 UI/能力分支 | 将后处理移回 pipeline/effect 层 |
| 写坏 Luminar catalog | 原生重开失败、schema drift | 立即停止写入，用模板副本恢复并保留 delta |
| 证据污染 | fingerprint/version 缺失 | 废弃整批 run，不手工补写 provenance |
| 范围不断扩大 | 新能力绕过 product scope | 拒绝进入 R19；另建下一版 scope |

每个工作包都应以小提交交付：schema/测试、runner、单个能力修复、单个组件族、单类 persistence 分开提交。回滚单位必须与这些边界一致。

## 10. 首轮可直接领取的任务清单

1. 给 UI matrix 增加 `surface_owner/comparison_mode`，修正 export dialog 的验收模式。
2. 从配置生成 170/84/40/22 摘要，并替换文档手写旧数字。
3. 为 parameter schema 增加能力级 native range override。
4. 写 matrix builder 的正值 amount、signed amount 和 fail-closed 测试。
5. 重建 matrix，确认 23 个负值伪阻塞消失并审查 diff。
6. 为 Native runner 实现 `slider` dispatcher 和 readback，先跑 1 条真实 contract。
7. 依次加入 button/menu/asset/crop/stroke/semantic-readback，达到 dry-run 84/84。
8. 执行现有 75 个 pending reference，并同时建立每能力 2 个 holdout 清单。
9. 对 `depth_volume` 建立 intermediate diagnostic bundle，完成第一条算法闭环。
10. 校准 shell 几何和字体 preflight，重新测 16 个 workspace，验证 UI 差异是否整体下降。
11. 在隔离 catalog 上采集第一组 project/edit-history delta，决定 WP7 是否可行。
12. 生成 `r19-preflight` exact gate 报告，作为后续每批工作的统一 burn-down 基线。

## 11. 合并检查模板

每个对齐 PR 必须回答：

- 对应哪个 capability/state/contract 和哪条失败证据？
- 修改了哪个最小根因，为什么不是调整阈值？
- 新增了什么自动化测试或证据？
- canonical、exact、holdout 和共享回归组结果是什么？
- 是否改变 matrix/schema/fingerprint；旧证据是否已正确失效？
- 是否影响模型输入输出契约、资源生命周期或持久化格式？
- 回滚路径是什么？

只有“代码、契约、证据、门禁”四者同时闭环，任务才可标记完成。
