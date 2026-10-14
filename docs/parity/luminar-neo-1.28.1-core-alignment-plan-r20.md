# Luminar Neo 1.28.1 核心完全对齐可执行优化计划（R20）

> 目标对象：Luminar Neo for macOS `1.28.1 (23487)`，`zh-Hans`，dark theme  
> 目标 reference ID：`luminar-neo-macos-1.28.1-23487`  
> 核心范围：40 个本地免费效果能力、170 个 UI 状态、84 条交互契约，以及这些能力依赖的本地预设、天空、叠加和多图工作流  
> 非目标：付费、云端、商店、账户、教程，以及 Luminar 私有工程/history 格式互操作  
> 当前活动配置仍指向 1.28.0；只有完成 WP0–WP2 的迁移和 canary 后才允许切换。

## 1. 结论与执行策略

本轮不能从“继续调 1.28.0 的 5 个失败效果”开始。正确顺序是：

1. 将所有活动真相源迁移到 `1.28.1 (23487)`，消除运行代码中的 1.28.0 路径和版本默认值；
2. 对本机应用、模型、素材、预设、UI contract 和显示环境建立新的不可变 fingerprint；
3. 用小规模 Native canary 验证采集器在 1.28.1 上仍能真实操作、读取、撤销、重做、重置和导出；
4. 全量重采 1.28.1 参考，不复制任何 1.28.0 screenshot、AX、preview、export 或 observation；
5. 基于新的失败集分别收敛效果、UI 和交互；
6. 用两个独立、不可变的 final run 证明完成。

已验证 1.28.1 与 1.28.0 共享 26 个模型变体且 hash 全部一致，7 个工具组、41 个工具 ID 和 18 个天空参数 ID 也一致。因此 locator 和算法问题大概率可局部迁移，但这只能降低迁移风险，不能替代 1.28.1 原生证据。

## 2. 可验收的“完全对齐”定义

R20 的“完全对齐”是基于冻结环境和黑盒阈值的工程定义，不表示恢复 Luminar 私有源码或逐位生成完全相同的文件字节。

| 维度 | 完成条件 | 必需证据 |
|---|---|---|
| 效果 | 同一输入、参数、素材和输出设置下，40 个 main、全部 exact 和至少 80 个 holdout 达到冻结指标 | Native preview/export、candidate、参数、素材、模型、环境和指标 hash |
| UI | 169 个 app-owned 状态通过 pixel comparator；1 个 OS-owned Save Panel 通过 semantic comparator | Native/browser screenshot、AX/DOM、ROI、环境和 build fingerprint |
| 交互 | Native 和 Browser 的 84 条契约全部执行并通过 | before/after、readback、undo/redo/reset、export、trace、AX/DOM、artifact hash |
| 证据 | 不存在旧版本、stale fingerprint、pending、unsupported、人工豁免或无法追溯产物 | 两次独立 exact-core run |

Native persistence 不属于本轮效果/UI/交互核心范围。现有 validator 保留为 optional diagnostic，但不得再作为 core alignment 的 required blocker。若以后要求 Luminar 工程文件互开，应另建独立项目，不与 R20 同批实施。

## 3. 已验证基线与迁移约束

### 3.1 本机 1.28.1 inventory

| 项目 | 1.28.1 结果 |
|---|---:|
| 安装版本 | `1.28.1 (23487)` |
| Bundle ID | `com.skylum.luminarneo` |
| 模型变体 | 26 OpenVINO IR |
| 当前候选 active model | 22，来自 `configs/model.yaml` |
| 预设集合 / 可见预设 | 22 / 123 |
| 天空集合 / 纹理 | 8 / 35 |
| 免费叠加集合 / 纹理 | 4 / 38 |
| UI 工具组 / 工具 | 7 / 41 |
| 天空参数 | 18 |

### 3.2 当前 1.28.0 方向性基线

以下数据只能用于估算风险，切换 1.28.1 后必须重新计算：

- main effects：`35/40 passed`；
- exact cohort：50 passed、8 failed、75 pending；
- UI：169 个 pixel state 尚未通过，1 个 semantic state 尚未正式取证；
- interaction：runner dry-run `84/84 supported`，正式 Native/Browser 证据 `0/84`；
- 最新工程回归：Ruff passed、backend `440 passed`、frontend `46 passed`、frontend build passed；
- R19 exact gate：`29/37 passed`，旧 UI evidence 已因新 fingerprint 正确失效。

### 3.3 当前代码风险

1. `configs/reference.yaml`、`configs/parity.yaml`、`configs/luminar_sampling.yaml` 和多个生成脚本仍固定 1.28.0。
2. `scripts/build_release_fingerprint.py` 的 validation roots 仍包含 1.28.0 路径，会导致新 reference fingerprint 不完整。
3. `services/editor/service.py` 和素材校验脚本仍硬编码 `1.28.0/23071`。
4. Browser UI/interaction recorder 只读取 `common_parameters`，没有合并 capability `parameter_overrides`，会重新引入错误 amount 值。
5. `configs/parity/native-parameter-bindings.json` 的 AX evidence 全部来自 1.28.0，不能直接提升为 1.28.1 supported evidence。
6. `frontend/src/App.tsx` 约 880 行、`styles.css` 约 820 行、`ToolPanel.tsx` 约 394 行；UI 偏差仍集中在共享 shell、CSS cascade 和复用控件族。
7. 旧采样文档引用已不存在的 `scripts/rebind_reference_inputs.py`，迁移命令必须同步修正。

## 4. 依赖关系与工作流

```text
WP0 冻结 R20 范围和 core gate policy
  │
  ▼
WP1 创建 1.28.1 profile、去版本硬编码、初始化 pending baseline
  │
  ▼
WP2 1.28.1 inventory、panel probes、binding audit、六类 canary
  │
  ├──────────────┐
  ▼              ▼
WP3 全量 Native 参考与数据链    WP5 Native UI 基线/测量口径
  │              │
  ▼              ▼
WP4 效果收敛                WP6 UI 视觉收敛
  │              │
  └──────┬───────┘
         ▼
WP7 Native + Browser 84 条交互闭环
         │
         ▼
WP8 holdout、重复性、跨维度回归
         │
         ▼
WP9 两次不可变 final run 与发布
```

禁止提前并行的部分：没有完成 WP2 canary 时不得全量前台采集；没有完成 WP3 新参考时不得调效果阈值或算法；没有冻结 Native interaction observation 时不得把 Browser interaction 标记为通过。

## 5. WP0：冻结范围、门禁和版本策略

### 5.1 目标

让“完成”只代表 1.28.1 的效果、UI 和交互闭环，同时保留 persistence 诊断但不扩大本轮范围。

### 5.2 修改入口

- `configs/reference.yaml`
- `configs/parity.yaml`
- `scripts/run_quality_gates.py`
- `scripts/build_release_fingerprint.py`
- `docs/parity/README.md`

### 5.3 执行步骤

1. 在 `configs/parity.yaml` 增加机器可读的 scope policy，例如 `native_persistence_required: false`；不要删除 persistence validator。
2. `run_quality_gates.py` 根据 scope policy 设置 `Gate.required`，报告同时列出 required 和 optional 结果。
3. exact-core release 只在效果、UI、交互相关 required gates 全部通过时放行；optional persistence 失败必须可见，但不改变 core 状态。
4. 固定 40 capability、170 UI、84 interaction、22 active model 的生成式 scope summary。
5. 规定任何 app version/build、matrix、schema、binding、素材、模型、字体或 capture environment 变化都产生新 fingerprint。

### 5.4 测试与验收

- 测试 core policy 下 persistence 失败不阻塞 core release，其他 required gate 失败仍阻塞。
- quality-gate dry-run 输出完整命令和 required/optional 分类。
- 文档不得再用旧的 `37/37` 作为唯一完成表述；以“全部 required passed，optional 单列”为准。

### 5.5 回滚

回滚 scope policy 即恢复 persistence required；不删除任何 validator 或历史报告。

## 6. WP1：创建 1.28.1 唯一真相源

### 6.1 目标

新增独立 1.28.1 profile 和数据根，保留 1.28.0 为历史只读参考，不复制旧输出证据。

### 6.2 目标目录

```text
test_data/parity/references/luminar-1.28.1-23487/
├── cases.json
├── manifest.json
└── reference-matrix.json

test_data/outputs/luminar-1.28.1-23487/
├── inventory/
├── captures/
├── ui/
├── observations/
├── native-exports/
└── diagnostics/runs/
```

### 6.3 配置迁移

1. 在 `configs/reference.yaml` 添加 `luminar-neo-macos-1.28.1-23487` profile，初始 `exact_gate_enabled: false`。
2. 先不切换 `active_reference`；使用显式 `--reference-id` 初始化和验证。
3. 运行现有初始化器，只复用输入和 case 计划，不复制 captures：

```bash
.venv/bin/python scripts/initialize_reference_baseline.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --seed-reference-id luminar-neo-macos-1.28.0-23071
```

4. 更新或重建以下活动契约的 reference ID：
   - `configs/ui/editor.json`
   - `configs/capabilities/registry.json`
   - `configs/parity/core-workspace-states.json`
   - `configs/parity/interaction-contracts.json`
   - `configs/parity/invalid-references.json`
   - `configs/luminar_sampling.yaml`
5. `configs/presets/free.json` 的 provenance 必须由 1.28.1 inventory/采集生成，禁止全文件盲替换版本字符串。
6. `native-capture-environment.json` 新版本初始状态必须是 pending；完成本机显示/权限验证后再标记 verified。

### 6.4 去版本硬编码

优先将以下运行路径改为通过 `ReferenceProfile` 解析，而不是把 1.28.0 字面量机械替换成 1.28.1：

- `scripts/build_release_fingerprint.py`
- `scripts/build_model_validation_matrix.py`
- `scripts/build_core_ui_state_matrix.py`
- `scripts/build_core_interaction_matrix.py`
- `scripts/build_native_parameter_binding_audit.py`
- `scripts/build_ui_regions.py`
- `scripts/build_exact_parity_cases.py`
- `scripts/validate_absolute_scope_coverage.py`
- `scripts/validate_product_scope.py`
- `scripts/validate_luminar_asset_alignment.py`
- `scripts/import_luminar_preset_artwork.py`
- `services/editor/service.py`

历史文档、旧 run、旧 preset provenance 和 `storage/catalogs/luminar_sqlite.py` 中真实描述 1.28.0 来源的内容保持不变，除非新的 schema audit 证明应更新。

### 6.5 参数定义统一解析

为 Python builder 和 Browser recorder 建立同一条规则：

```text
effective_definition = common_parameters[parameter]
                     + capabilities[capability_id].parameter_overrides[parameter]
```

至少修复：

- `scripts/build_ui_browser_capture_plan.py`
- `frontend/scripts/capture-interaction-dpr2.mjs`

新增正值 amount、signed amount、enum、boolean、asset、crop box 和 stroke 的跨端一致性测试，确保 UI capture、Browser interaction、exact matrix 和 Native binding 使用相同 canonical value。

### 6.6 验收

- 显式指定 1.28.1 时，所有生成产物只写入 1.28.1 root。
- 1.28.0 目录 hash 不变化。
- runtime/config/scripts 的活动默认路径不再固定 1.28.0；历史 provenance 例外必须列入 allowlist。
- 新 profile 的 cases 全部是 `pending-reference`，没有旧 preview/export 路径。
- reference/profile 测试覆盖两个版本和 active switch。

## 7. WP2：安装冻结、inventory、binding 和 canary

### 7.1 安装与环境冻结

每个 Native 批次开始和结束都运行：

```bash
.venv/bin/python scripts/inspect_luminar_install.py \
  --app "/Applications/Luminar Neo.app" \
  --output-dir test_data/outputs/luminar-1.28.1-23487/inventory
```

增强 local lock，使其至少包含：bundle ID、version、build、Info.plist hash、主 executable hash、资源根摘要和 26 个模型 hash。若批次前后 lock 不同，整批证据废弃。

冻结环境：

- logical viewport `1440x900`；
- physical viewport `2880x1800`；
- DPR `2`；
- locale `zh-Hans`；
- dark theme；
- 本地物理显示、屏幕录制和辅助功能权限；
- 独立 GUI 会话或明确预留的前台采集时段。

### 7.2 版本 delta

```bash
.venv/bin/python scripts/compare_luminar_references.py \
  --baseline-manifest test_data/outputs/luminar-1.28.0-23071/inventory/install-manifest.json \
  --candidate-manifest test_data/outputs/luminar-1.28.1-23487/inventory/install-manifest.json \
  --baseline-ui test_data/outputs/luminar-1.28.0-23071/inventory/ui-contract.json \
  --candidate-ui test_data/outputs/luminar-1.28.1-23487/inventory/ui-contract.json \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/reference-delta.json
```

补齐 preset inventory 后再次比较 preset ID 和 edit graph；不能以当前仅模型/UI 的 delta 代替 preset 审计。

### 7.3 生成矩阵

```bash
.venv/bin/python scripts/build_core_ui_state_matrix.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --inventory test_data/outputs/luminar-1.28.1-23487/inventory/ui-contract.json \
  --output configs/parity/core-ui-state-matrix.json

.venv/bin/python scripts/build_core_interaction_matrix.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --output configs/parity/core-interaction-matrix.json
```

矩阵期望仍为 170 UI 和 84 interaction；如果 1.28.1 inventory 产生差异，应先审查 scope，不得修改固定断言让未知状态静默进入或退出。

### 7.4 解决 binding audit 的证据顺序

1. 先构建 409 条 pending sampling queue。
2. 只执行 `tool-panel-state`，采集 40 个工具的 expanded AX 证据。
3. 用新的 1.28.1 UI root 重建 `native-parameter-bindings.json`。
4. 审查 58 slider、7 button、1 menu-choice、3 asset-picker、4 stroke、1 crop-box 是否仍成立。
5. 再生成包含 parameter state 的正式 queue/fingerprint。

旧 1.28.0 locator 可以作为候选定位提示，但只有 1.28.1 AX snapshot/hash 才能产生 `supported` 状态。

### 7.5 Native canary

先做六类队列 canary：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --one-per-kind --dry-run

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --one-per-kind --allow-ui-control
```

再做参数操作 canary：

- slider：`tool:details:parameter:amount`；
- button：`tool:crop_ai:parameter:flip_x`；
- menu：`tool:crop_ai:parameter:crop_ratio`；
- asset：`tool:sky_replace:parameter:asset_id`；
- stroke：`tool:erase:parameter:strokes`；
- crop：`tool:crop_ai:parameter:crop_box`。

每条必须真实完成 before/after、readback、undo、redo、reset、PNG export 和 source cleanup。任一 canary 失败时停止同类全量执行，先修 dispatcher 或 locator。

### 7.6 准出条件

- app/version/display/permission preflight 通过；
- inventory 和 local lock 稳定；
- UI/interaction matrix definition gate 通过；
- parameter binding audit `74/74 supported`；
- 六类 sampling canary 和六类 parameter canary 全部通过；
- 无坐标 fallback 冒充 semantic locator 成功。

## 8. WP3：全量重采 1.28.1 参考与数据链

### 8.1 基础队列

重新生成：

```bash
.venv/bin/python scripts/build_parity_cases.py \
  --reference-id luminar-neo-macos-1.28.1-23487

.venv/bin/python scripts/build_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.1-23487
```

期望队列结构在 scope 不变时为：40 effect、123 preset、35 sky、38 overlay、170 UI、3 workflow，共 409 条。实际数字以新 builder 输出为准。

### 8.2 推荐批次

1. 16 个 workspace UI；
2. 80 个 tool panel；
3. 74 个 parameter UI；
4. 40 个 main effect；
5. 123 preset；
6. 35 sky；
7. 38 overlay；
8. 3 multi-image workflow。

每批 5–20 条，执行前 dry-run，执行后立即校验并记录 app lock。不要连续跑完全队列后才发现版本或状态漂移。

### 8.3 Exact matrix

```bash
.venv/bin/python scripts/build_exact_sampling_matrix.py \
  --cases test_data/parity/references/luminar-1.28.1-23487/cases.json \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/exact-sampling-matrix.json

.venv/bin/python scripts/build_incremental_sampling_queue.py \
  --matrix test_data/outputs/luminar-1.28.1-23487/diagnostics/exact-sampling-matrix.json \
  --smoke-queue test_data/outputs/luminar-1.28.1-23487/diagnostics/sampling-queue.json \
  --capture-root test_data/outputs/luminar-1.28.1-23487/captures \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/sampling-queue-exact-incremental.json \
  --diff-output test_data/outputs/luminar-1.28.1-23487/diagnostics/exact-semantic-diff.json
```

R19 的 112 条 worklist/36 条 blocked 只是迁移估算。R20 必须把 36 条缺少 enum、stroke、crop 或 Native automation 的记录逐条关闭；最终 blocked、invalid、duplicate 均为 0。

### 8.4 数据链校验

```bash
.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --reference-id luminar-neo-macos-1.28.1-23487

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --reference-id luminar-neo-macos-1.28.1-23487
```

### 8.5 准出条件

- 409 条基础队列全部具备合法 canonical evidence；
- exact matrix 的合法 case 全部 ready；
- 每条记录绑定 input、parameter、asset、app、environment、preview、export 和 attempt hashes；
- 没有 1.28.0 路径或 fingerprint；
- failed attempt 不覆盖成功 canonical。

## 9. WP4：效果输出收敛

### 9.1 先建立 1.28.1 新基线

生成当前 candidate 并运行 main/exact parity。只有新报告中的失败才进入修复队列；R19 的 `face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays` 仅作为优先观察项。

### 9.2 单能力闭环

每个失败能力严格执行：

1. 固定一个 main 或 exact 失败 case；
2. 保存 Native/candidate preview、export、参数、素材和所有 hash；
3. 输出最小诊断：mask/depth/face box、tone curve、blend weight、工作色域、resize；
4. 将差异分类为模型输入、模型输出解释、mask、色彩空间、混合顺序、参数映射或编码；
5. 先添加根因测试；
6. 修改最小实现；
7. 运行当前 case、同能力 exact、两个 holdout 和共享 pipeline 回归组；
8. 指标退化或 holdout 不通过即回滚。

### 9.3 修改边界

| 根因 | 首选位置 | 禁止做法 |
|---|---|---|
| 模型输入 shape/dtype/color/normalization | `ai/model/`、`ai/pipeline/inference_executor.py` | 在 wrapper 中读取 UI/case ID |
| mask/depth/face 解释 | `ai/pipeline/image_effect_pipelines.py` | 按 fixture hash 返回答案 |
| 色彩、曲线、锐化、局部效果 | `image_ops/effects/basic.py`、`retouch.py` | 放宽全局阈值掩盖差异 |
| sky/foreground/reflection | `image_ops/effects/sky_compositor.py`、相关 pipeline | 忽略大面积前景 ROI |
| 参数映射 | parameter schema、service/pipeline 边界 | 在多个层重复缩放参数 |

模型 wrapper 只负责加载、推理契约、缓存和释放；Luminar 风格的能力后处理保留在 pipeline/effect 层。

### 9.4 建议批次

按 1.28.1 新失败报告排序；若失败集与 R19 类似，则顺序为：

1. depth family：`depth_volume`；
2. sky family：`sky_replace`、`sunrays`、`landscape_enhancer`；
3. color family：`blue_hour`、`color_enhancer`、`complex_bleach`；
4. portrait family：`face_ai`；
5. detail family：`structure_ai` 及剩余 exact failures。

### 9.5 阈值与重复性

- 先对每个 capability 做至少 3 次 Native 重复导出，记录 MAE/SSIM 方差；
- 阈值必须高于 Native 噪声地板，但不得因 candidate 失败临时放宽；
- 默认验收边界仍为 `SSIM >= 0.98`、`MAE <= 0.03`；特殊统计型效果必须有专用 comparator 和依据；
- preview 和 export 都必须验证，不能只让其中一个通过。

### 9.6 准出条件

- main `40/40`；
- 新 exact matrix 全部通过；
- 每个能力至少两个不同输入 holdout，共至少 80 个，全部通过；
- 重复运行满足确定性/噪声约束；
- 0 pending reference、0 fallback backend、0 fixture-specific branch。

## 10. WP5：重建 1.28.1 UI 参考与测量系统

### 10.1 Native UI reference

1. 用 1.28.1 queue 采集 170 个截图和 AX tree；
2. 构建新的 `reference-manifest.json`；
3. 用 169 个 pixel state 重建 `configs/parity/ui-regions.json`；
4. Save Panel 保持 `surface_owner=os`、`comparison_mode=semantic`；
5. 对 edit、catalog、presets、multi-image、代表性 panel 连续截图，确认采集噪声。

### 10.2 Browser UI 证据

```bash
.venv/bin/python scripts/prepare_ui_evidence_fixture.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --data-root test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-evidence-fixture \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-evidence-fixture.json

.venv/bin/python scripts/build_ui_browser_capture_plan.py \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-browser-capture-plan.json

cd frontend
npm run capture:ui:dpr2 -- \
  --plan ../test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-browser-capture-plan.json \
  --output-root ../test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-capture-raw \
  --candidate-root ../test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-candidates \
  --resume true \
  --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

正式 capture 前先使用 `--dry-run true` 验证 170/170 recipe 和 locator。

### 10.3 比较器自测

必须证明 comparator 能识别：

- 1 px 全局或局部位移；
- 字号/字重变化；
- 错误 DPR、viewport 和缩放；
- candidate/reference 交换；
- region hash 或 AX evidence 失配；
- semantic state 被错误纳入 pixel 统计。

### 10.4 准出条件

- Native manifest 与 UI matrix fingerprint 一致；
- region manifest 恰好 169 条；
- Browser capture 170/170 完整；
- UI evidence validator 不存在 stale build、fixture、region 或 matrix issue；
- 只有在这些条件满足后，UI pixel 分数才可用于优化。

## 11. WP6：UI 视觉收敛

### 11.1 修复顺序

1. **Shell geometry**：viewport、top bar、左右栏、canvas、filmstrip、bottom bar；
2. **Typography/icons**：字体文件、font metrics、字号、字重、行高、图标 bounding box；
3. **16 workspace**：优先 catalog、presets、multi-image、denoise、deblur；
4. **80 tool panels**：按复用组件族修复；
5. **74 modified states**：确保值、控件状态和视觉同步；
6. **亚像素收尾**：只处理剩余 1 px、baseline 和 border 差异。

### 11.2 代码入口

- `frontend/src/styles.css`：先提取并冻结共享 token，再删除被新 token 完全替代的重复规则；
- `frontend/src/App.tsx`：只在 shell/state 边界需要独立测试时拆分；
- `frontend/src/components/ToolPanel.tsx`：按 slider/enum/boolean/asset/crop/brush 复用族收敛；
- `PreviewPanel.tsx`、`CatalogWorkspace.tsx`、`PresetBrowser.tsx`、`ExportDialog.tsx`：处理各 workspace 的结构差异。

不在 R20 引入新的状态管理框架，不为某个 matrix state ID 编写 CSS 特例，不进行无证据的大规模组件重写。

### 11.3 单次优化循环

1. 从 heatmap、DOM、AX 和几何数据选择一个共享根因；
2. 写一个组件或 comparator 回归测试；
3. 修改最小 token/component；
4. 重录受影响组件族；
5. 再重录全部 16 workspace，检查系统性回归；
6. 保存 before/after metrics 和 screenshot；
7. 任何已通过状态退化则回滚该批。

### 11.4 准出条件

- 169/169 app-owned pixel states 通过冻结阈值；
- Save Panel 的字段、焦点、键盘、取消、确认和最终输出通过 semantic contract；
- 无 state-specific CSS hack；
- 每个状态都有 screenshot、DOM、AX、fixture、browser build 和 region hash。

## 12. WP7：闭环 Native 与 Browser 84 条交互

### 12.1 Native observations

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --dry-run

.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --resume --allow-ui-control
```

每条 contract 必须：恢复基线 → 定位 → before → action → readback → after → undo → redo → reset → export → cleanup。失败必须保留 blocked observation、候选节点和截图，不能用人工说明提升为 passed。

### 12.2 Browser execution

1. 修复 capability override 解析后先 dry-run `84/84 supported`；
2. 冻结 frontend build hash 和 fixture fingerprint；
3. 执行 `frontend/scripts/capture-interaction-dpr2.mjs`；
4. 使用 `build_interaction_browser_execution.py` 将 raw trace 与 Native observation hash-link；
5. 运行 `validate_interaction_execution.py`。

Browser 证据至少包含 screenshot、DOM/AX、console、network、project state、download/export、事件计数和 API assertions。

### 12.3 组件族验收

| 类型 | 必测内容 |
|---|---|
| slider | min/default/mid/max、step、键盘微调、reset、undo/redo |
| button/boolean | selected/enabled、重复点击、撤销和导出影响 |
| menu/enum | 全值、当前项 readback、键盘路径 |
| asset | 稳定 ID/hash、缩略图/标签、预览和导出 |
| stroke | 固定归一化坐标、笔刷配置、清除、撤销/重做 |
| crop | box、ratio、flip、apply/cancel、坐标系和导出尺寸 |
| workflow | catalog、preset、layer、mask、compare、multi-image、export 完整状态转换 |

### 12.4 准出条件

- Native `84/84 executed and passed`；
- Browser `84/84 executed and passed`；
- interaction matrix、Native observation、Browser build、fixture 和 export hashes 完整关联；
- 无 missing observation、unsupported、fixed sleep、undeclared wait 或 stale build；
- 每条执行后 source state 可恢复，不污染下一条 contract。

## 13. WP8：holdout、重复性与跨维度回归

### 13.1 Holdout 设计

每个 40 核心能力至少两个非 canonical 输入，覆盖：

- portrait / non-portrait；
- day / night；
- sky / no-sky；
- high-frequency / low-frequency detail；
- 不同方向、分辨率、色调和困难边界。

Holdout 在算法调整前冻结，不允许因失败替换输入。素材型能力还要覆盖至少两个 asset，局部工具覆盖至少两个固定 stroke/crop geometry。

### 13.2 跨维度检查

每个 capability 完成时同时验证：

- 输出指标通过；
- UI 控件显示与实际参数一致；
- Native/Browser interaction readback 一致；
- undo/redo/reset 后 preview 和 export 一致；
- 模型、素材和配置 fingerprint 未变化。

### 13.3 性能底线

记录 Native 与 candidate 的 slider preview、工具首次打开和 export 延迟分布。性能不是替代正确性的门槛，但任何优化不得降低分辨率、跳过模型、改变色彩精度或复用错误缓存。

### 13.4 准出条件

- 80+ holdout 全部通过；
- 每个能力至少 3 次重复运行；
- 无 canonical 通过而 holdout 退化；
- preview/export、UI state 和 interaction state 不存在跨维度矛盾。

## 14. WP9：最终门禁与发布

### 14.1 提交前工程验证

```bash
.venv/bin/ruff check api core services storage image_ops ai scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

### 14.2 两次不可变 final run

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --run-id r20-final-a

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --run-id r20-final-b
```

### 14.3 最终 DoD

- 所有 core required gates 在 A/B 两轮均通过；
- main effects `40/40`；
- exact 全量通过，0 pending/blocked/invalid/duplicate；
- holdout 至少 `80/80`；
- app-owned UI `169/169`，OS semantic `1/1`；
- Native interaction `84/84`，Browser interaction `84/84`；
- A/B 使用相同 source、model、validation 和 environment fingerprint；
- A/B 指标差异处于 Native 重复性范围；
- optional persistence 单独报告，不得被描述为已完成；
- 不存在人工豁免、旧版本 evidence、未追溯 artifact 或自动更新后的混合批次。

## 15. 实施批次与退出标准

| 批次 | 工作包 | 相对工作量 | 退出标准 |
|---|---|---:|---|
| 0 | WP0–WP1 | M | 新 profile、core policy、去硬编码和参数解析通过 |
| 1 | WP2 | M | inventory 稳定、74 bindings、12 个 canary 通过 |
| 2 | WP3 | L | 409 基础队列和 exact 数据链闭环 |
| 3A | WP4 | XL | 40 main、exact、holdout 全通过 |
| 3B | WP5–WP6 | XL | 169 pixel + 1 semantic UI 全通过 |
| 3C | WP7 | L | Native/Browser 84/84 |
| 4 | WP8–WP9 | M | 重复性、跨维度和 final A/B 通过 |

每个批次只合并一个可回滚边界：profile/脚本、binding、单个效果族、单个 UI 组件族、单个 interaction 类型或 final evidence。不要把版本迁移、算法调整和 UI 重写放在同一提交。

## 16. 风险、停止条件与回滚

| 风险 | 停止信号 | 处理与回滚 |
|---|---|---|
| Luminar 再次自动更新 | version/build/app hash 变化 | 废弃整批，恢复冻结 app 或新建 reference |
| 跨版本证据污染 | artifact 路径或 reference ID 指向 1.28.0 | gate fail；删除新批次 pointer，不删除历史证据 |
| AX locator 漂移 | 0 或多节点匹配 | 停止该类型，更新 locator 和测试 |
| 参数值空间错误 | Browser/Native canonical 不同 | 回到 effective definition resolver，不调效果算法 |
| Native 自身非确定性 | 重复导出方差超过阈值 | 扩大重复样本，冻结噪声模型后再比较 |
| 算法过拟合 | canonical 通过、holdout 退化 | 回滚常量，按共享根因重新诊断 |
| UI 补丁化 | state-specific selector 增长 | 停止局部修补，回到 token/组件族 |
| 状态泄漏 | 下一 contract 的 before 非默认 | 阻塞整批，修 reset/cleanup |
| 阈值漂移 | 为单个失败提高 MAE/降低 SSIM | 拒绝修改；只有 Native 方差报告可触发阈值评审 |
| 长任务证据不完整 | 进程中断、run summary 缺失 | 保留 attempt，resume；不得手工补 metadata |

回滚原则：切换失败时将 `active_reference` 指回 1.28.0 即可恢复旧工作流；1.28.1 新目录保持 pending/blocked，不覆盖也不删除 1.28.0 immutable evidence。

## 17. 首轮可直接领取的任务

1. 添加 1.28.1 reference profile，运行 `initialize_reference_baseline.py`。
2. 将 `build_release_fingerprint.py` 的 versioned validation roots 改为从 profile 解析。
3. 消除 service、asset validators 和 builder defaults 中的活动 1.28.0 硬编码。
4. 为 Python/Browser 实现统一 effective parameter definition resolver。
5. 修复自动采样文档中的失效 `rebind_reference_inputs.py` 命令。
6. 写入 1.28.1 install inventory、UI contract 和 local lock。
7. 重建 170 UI / 84 interaction matrix，并执行 definition validators。
8. 采集 40 个 expanded panel AX，重建 74 条 binding audit。
9. 执行六类 sampling canary 和六类 interaction canary。
10. 生成 `r20-baseline` exact-core dry-run，确认所有命令和输出根均指向 1.28.1。

## 18. 合并检查模板

每个 R20 PR 必须回答：

- 对应哪个 1.28.1 capability/state/contract？
- 使用哪条 Native 1.28.1 evidence 定位根因？
- 是否改变 reference、schema、matrix、binding、素材或 fingerprint？
- 修改的是 model contract、pipeline/effect、UI token/component，还是 interaction dispatcher？
- main、exact、两个 holdout、共享回归组结果是什么？
- 是否重跑了受影响的 UI/interaction 组件族？
- 是否出现旧版本路径、stale build、人工豁免或阈值变化？
- 回滚单位是什么？

只有代码、契约、1.28.1 原生证据和门禁四者同时闭环，任务才可标记完成。
