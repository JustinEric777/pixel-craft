# Luminar Neo 1.28 本地核心绝对对齐执行报告（R17，Current-only）

> 本文记录 R17 计划的实际执行结果、执行前后差异、未关闭项和下一轮唯一执行顺序。验收对象是本机 Luminar Neo `1.28.0 (23071)` 中文版与当前 zpixel 代码；不提供历史 schema、旧状态 ID、旧证据或旧项目格式的运行时兼容逻辑。

## 目录

- [1. 最终结论](#1-最终结论)
- [2. 本轮范围与验收口径](#2-本轮范围与验收口径)
- [3. 按顺序执行结果](#3-按顺序执行结果)
- [4. 执行前后对比](#4-执行前后对比)
- [5. 最终遗漏审计](#5-最终遗漏审计)
- [6. 下一轮可执行计划](#6-下一轮可执行计划)
- [7. 验证命令与证据入口](#7-验证命令与证据入口)

---

## 1. 最终结论

R17 已完成当前契约收敛、210 状态 UI 队列接入、124 条交互契约接入、证据防伪收紧、真实 Native 持久化只读审计、模型层静态审计和完整回归验证。代码侧不再使用旧 UI 状态别名、旧交互来源映射或推测式 Native History 写入。

R17 **没有达到“与本地 Luminar Neo APP 完全绝对对齐”**。当前 exact 质量门禁为 `26/37 passed`、`11/37 failed`，状态 `blocked`。主要原因不是测试失败，而是官方 Native 证据、Browser 重放证据、完整 Native 持久化 codec 和足够的效果标定样本尚未获得。

当前可确认的工程状态：

| 维度 | 当前结果 | 结论 |
|---|---:|---|
| Python 回归 | `405 passed` | 通过 |
| Python 静态检查 | `ruff passed` | 通过 |
| Frontend 测试 | `46 passed` | 通过 |
| Frontend build | 通过 | 通过 |
| 主效果 | `35/40 passed` | 未收敛 |
| Exact 扩展效果 | `50 passed / 6 failed / 42 pending`，共 98 | 未收敛 |
| UI Native 参考 | `0/210 verified` | 阻塞 |
| UI Browser 执行 | `0/210 passed` | 阻塞 |
| Native 交互 | `0/124 passed` | 阻塞 |
| Browser 交互 | `0/124 passed` | 阻塞 |
| Native persistence roundtrip | 7 类必需状态无 manifest | 阻塞 |
| Exact required gates | `26/37 passed` | 阻塞 |

## 2. 本轮范围与验收口径

### 2.1 唯一活动参考

| 项目 | 值 |
|---|---|
| Reference ID | `luminar-neo-macos-1.28.0-23071` |
| App | Luminar Neo `1.28.0 (23071)` |
| Bundle ID | `com.skylum.luminarneo` |
| Locale | `zh-Hans` |
| UI matrix fingerprint | `9c23735db6cae91827056f2dea1d88edab0458fbd8938c3c615909d9121549fe` |
| Interaction matrix fingerprint | `e9d5cf0c0c68d670c882d58c2c3c0f385ab6892b6aed0636e4c19421b4edf37f` |

### 2.2 Current-only 规则

1. UI 证据只能使用 `matrix_state_id` 和当前 UI matrix fingerprint。
2. 交互证据只能使用当前 124 条 contract ID 和当前 interaction fingerprint。
3. Native 证据必须包含版本、build、bundle、fixture hash、全屏环境、隔离显示、隔离输入、截图和 accessibility artifact 的哈希。
4. Browser 证据必须与同一条有效 Native 观察绑定，并记录 build hash、DOM、accessibility tree、执行 trace、network trace、console log 和最终截图。
5. 缺证据时保持 `pending` 或 `blocked`；不得以运行成功、旧截图或来源别名替代 parity pass。
6. Native 项目写入不得猜测字段。未完成真实 v155 roundtrip 前，不能把 JSON workspace repository 宣称为 Luminar 原生项目兼容。

## 3. 按顺序执行结果

### 3.1 WP0：冻结当前契约与清理旧映射

状态：**完成**。

- UI 和交互矩阵均使用当前 canonical ID 与 fingerprint。
- 移除了采样、UI manifest、UI Browser 执行和 interaction capture 中的旧状态别名、旧 source key 和 fallback。
- 旧 evidence 已移出活动路径；活动门禁不会读取归档证据。
- 删除推测式 Native History 写入，避免生成表面可写但无法被 Luminar 正确恢复的项目。

验收结果：当前 UI/interaction evidence validator 会拒绝旧字段、旧 fingerprint 和非 canonical 状态。

### 3.2 WP1：构建完整采样队列

状态：**完成**。

`sampling-queue.json` 当前包含 449 条记录：

| Kind | 数量 |
|---|---:|
| effect | 40 |
| overlay | 38 |
| preset | 123 |
| sky | 35 |
| ui | 210 |
| workflow | 3 |
| 合计 | 449 |

采样证据审计为 `239 ready / 210 pending`。210 条 pending 全部是新增的 current-only UI 状态，不再只采集旧的 16 状态子集。

### 3.3 WP2：收紧 UI 与交互证据链

状态：**完成**。

- UI reference manifest 升级为 version `2.0`，精确列出 210 个 matrix state。
- UI manifest 必须绑定当前 fingerprint；每条记录必须绑定同一 canonical state。
- UI Browser execution 不再接受 `state` 或来源别名。
- Native interaction runner 只注册 10 个已明确实现的工作流 handler；114 个参数交互不会使用猜测坐标或通用 fallback。
- Native interaction validator 要求隔离显示与隔离输入证明。
- 绝对范围统计只计算通过完整 Native observation 校验的 contract，目录名或空壳文件不再算覆盖。

### 3.4 WP3：采集 210 UI 与 124 交互证据

状态：**已执行准入与采集尝试，证据产出阻塞**。

阻塞事实：

1. 本机处于锁屏状态，自动解锁失败，无法合法读取或操作 Luminar Neo 界面。
2. `configs/parity/native-capture-environment.json` 中 `virtual_display_verified=false`、`isolated_input_verified=false`，provider、session ID 和验证时间为空。
3. 124 条交互中只有 10 条工作流存在明确 Native handler；114 条参数交互尚未基于真实 accessibility locator 绑定。
4. 严格 preflight 在上述条件不满足时 fail closed，因此没有绕过隔离门禁生成伪 Native 证据。

结果：

| 证据 | 当前状态 |
|---|---:|
| UI reference manifest | `0 verified / 210 invalid-evidence` |
| UI Browser execution | `0/210 executed` |
| UI parity | `0 passed / 210 pending` |
| Native interaction | `0/124 passed` |
| Browser interaction | `0/124 executed` |

### 3.5 WP4：Native 项目持久化

状态：**完成只读审计；可写 codec 与 roundtrip 未完成**。

已验证本地 catalog：

- 项目：`/Users/iknow/Works/luminarneo/未命名/未命名.luminarneo`
- History：`/Users/iknow/Works/luminarneo/未命名/History`
- catalog schema version：`155`
- History 文件为 JSON，已观察到 canvas、layers、edits、effect parameters、mask、blend、opacity、transformation 等结构。

仍缺少 40 个工具的字段映射、默认值语义、undo/redo、资源引用、mask 编解码和保存后由 Luminar 重开验证。当前 `native-persistence-roundtrip` 因缺少 7 类必需状态 manifest 而 blocked：`project`、`edit-history`、`layer`、`mask`、`workflow`、`preset`、`preview-export`。

本轮没有用局部样本推测完整 codec，也没有把 API 切换到一个不可验证的 Native writer。

### 3.6 WP5：模型与效果收敛

状态：**模型层静态契约通过；像素效果未完全收敛**。

- `ai/model` 专项验证通过，`0 findings`。
- 主效果仍为 `35/40 passed`；失败项：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。
- Exact 扩展为 `50 passed / 6 failed / 42 pending`。
- Exact 的 6 个失败 case 涉及 `face_ai` 两条、`structure_ai`、`depth_volume`、`blue_hour`、`landscape_enhancer`。

本轮未在缺少新 Native holdout 的情况下继续微调单图系数。当前仍缺 9 个 amount anchors、40 个能力的足量 holdout，以及 6 个未覆盖参数。

### 3.7 WP6：完整验证

状态：**完成**。

- Python：`405 passed`，仅 1 条第三方 Starlette deprecation warning。
- Ruff：通过。
- Frontend：11 个 test files、46 个 tests 全部通过。
- Frontend build：通过。
- Exact gate run：`r17-current-only-final`，37 个 required gates 中 26 pass、11 fail。

失败的 required gates：

1. `absolute-scope-coverage`
2. `sampling-data-chain`
3. `exact-incremental-data-chain`
4. `sampling-queue-evidence`
5. `luminar-reference-captures`
6. `output-parity`
7. `exact-incremental-parity`
8. `ui-execution-evidence`
9. `ui-parity`
10. `interaction-execution`
11. `native-persistence-roundtrip`

## 4. 执行前后对比

| 维度 | 执行前（R16） | 执行后（R17） | 结论 |
|---|---:|---:|---|
| Exact gates | `28/37 pass` | `26/37 pass` | 数字下降来自门禁收紧，不代表功能回退 |
| UI 活动参考 | 旧 manifest `16/16 verified` | current matrix `0/210 verified` | 移除以 16 状态代表 210 状态的假完成 |
| UI sampling scope | 16 个来源状态 | 210 个 canonical 状态 | 范围完整化 |
| Native interaction | 旧来源记录可被计入 | `0/124` current-valid | 清除旧来源与无效证据计数 |
| Browser interaction | 旧来源记录可被计入 | `0/124` current-valid | 必须绑定当前 Native contract |
| Absolute scope issues | 684 | 933 | 新口径暴露完整缺口；不是新增 249 个功能回归 |
| 主效果 | `35/40` | `35/40` | 无新 holdout，未做不可验证微调 |
| Python tests | 405 | 405 | 稳定 |
| Frontend tests | 46 | 46 | 稳定 |
| Native writer | 存在推测式 History 写入风险 | 推测式写入移除 | 安全性提高，roundtrip 仍未完成 |

`933` 是诊断条目总数，不是互斥功能数。其中 210 个 UI 状态同时出现在“缺少已验证参考”和“manifest 记录无效”两类诊断中，存在有意的记录级重叠。

## 5. 最终遗漏审计

### 5.1 绝对范围缺口

| 缺口 | 数量 |
|---|---:|
| 缺少 exact amount anchors | 9 |
| holdout 输入不足 | 40 |
| 参数未被样本表示 | 6 |
| 缺少有效 UI Native reference | 210 |
| 缺少 UI Browser execution | 210 |
| 当前 UI reference 记录无效 | 210 |
| 缺少 Native interaction | 124 |
| 缺少 Browser interaction | 124 |

### 5.2 不能宣布完成的事项

1. 210 个 UI 状态的视觉、布局、文字、展开态、滑杆态和素材选择态尚无当前 Native 截图真值。
2. 114 个参数交互缺少 Native accessibility locator 与显式 handler。
3. 124 条交互缺少 Native before/after、AX snapshot 和完整 Browser 重放链。
4. 5 个主效果失败，6 个 Exact case 失败，42 个 Exact case 缺参考。
5. 40 个能力仍缺足量跨图片 holdout，9 个 amount anchor 和 6 个参数覆盖未完成。
6. v155 Native persistence codec 与 7 类 roundtrip 未完成。
7. 专用显示、隔离输入和解锁状态未满足，因此不能进行可审计的官方 Native 采集。

## 6. 下一轮可执行计划

### 6.1 P0：恢复 Native 采集准入

前置条件：用户手动解锁 Mac，并保持 Luminar Neo 可操作。

执行步骤：

1. 建立专用采集 display/session，记录 provider 与 session ID。
2. 验证物理/逻辑 viewport 为 `2880×1800 / 1440×900`、locale 为 `zh-Hans`。
3. 验证输入隔离，禁止用户鼠标键盘与自动化事件混用。
4. 更新 `configs/parity/native-capture-environment.json` 的两项 verified、provider、session ID、verified_at。
5. 运行 strict preflight；不通过时停止后续采集。

完成定义：preflight 通过，且环境记录可被 Native interaction validator 接受。

### 6.2 P1：先做 3 个探针，再完成 210 UI Native 参考

执行步骤：

1. 选择 workspace、tool-panel、parameter 各 1 个探针。
2. 验证 screenshot、AX snapshot、fixture hash、state ID、matrix fingerprint 和环境哈希。
3. 探针通过后按 matrix 顺序批量采集 210 状态。
4. 每批结束运行 `build_ui_reference_manifest.py` 与 `validate_ui_references.py`。
5. 任一状态无法稳定到达时记录 blocked reason，不复制相邻状态截图。

完成定义：`210/210 verified`，无 missing、invalid、duplicate 或 stale fingerprint。

### 6.3 P2：补齐 114 个参数 Native handler

执行步骤：

1. 从 Native AX tree 为每个参数记录 tool、section、control role、label/value locator。
2. 为 slider、toggle、selector、asset picker、crop geometry 分别实现显式操作函数。
3. 每个 contract 执行 source reset、事件序列、允许的稳定等待和最终状态断言。
4. 禁止通用坐标 fallback、固定 sleep 和旧 ID fallback。
5. 先验证 10 个已有工作流，再按 capability 顺序补齐 114 个参数 contract。

完成定义：Native dry-run 不再出现 `unsupported contract`，124 条均存在明确 handler。

### 6.4 P3：完成 124 Native 与 Browser 交互链

执行步骤：

1. 先采集 Native before/after、AX snapshot、fixture、环境和 artifact hashes。
2. 只有 Native contract 通过后才执行同 ID 的 Browser 重放。
3. Browser 保存 DOM、AX tree、execution/network trace、console log、最终截图和 build hash。
4. 每条 Browser record 绑定 Native observation path 与 SHA-256。
5. 逐条运行 interaction validator，最后运行完整 124 contract gate。

完成定义：Native `124/124`、Browser `124/124`、issue count 为 0。

### 6.5 P4：以 controlled delta 逆向 v155 persistence

执行步骤：

1. 每次只在 Luminar 改一个变量，保存前后 catalog/History 副本和哈希。
2. 分别覆盖 project、edit-history、layer、mask、workflow、preset、preview-export。
3. 建立 40 个工具 ID、parameter name、默认值、范围和资源引用的显式映射。
4. 实现单一 current v155 codec，不加入旧 schema 分支。
5. 写入临时项目，由 Luminar 重开并验证 UI 状态、导出结果和 undo/redo。
6. 7 类 roundtrip 全部通过后，才把 API repository 切换到 Native repository。

完成定义：`native-persistence-roundtrip` 7 类全过，且 Luminar 可重开、继续编辑与导出。

### 6.6 P5：效果样本与算法收敛

执行步骤：

1. 为 40 个能力各补至少 2 个新的 Native holdout，使每能力 distinct input 达到门禁要求。
2. 补齐 9 个 amount anchors、6 个未表示参数和 42 个 pending Exact reference。
3. 按失败能力分别诊断，不进行跨能力大改。
4. 每次只修改能被新 Native 样本证明的公式、模型 wrapper 或 compositing 阶段。
5. 先跑单能力 main/exact/holdout，再跑 40 主效果和 98 Exact 全量。

完成定义：主效果 `40/40`、Exact `98/98`，holdout 与参数覆盖门禁均通过。

### 6.7 P6：最终验收顺序

1. Python、Ruff、Frontend tests、Frontend build。
2. UI reference、UI execution、UI parity。
3. Native interaction、Browser interaction。
4. Native persistence roundtrip。
5. Main output parity、Exact incremental parity、absolute scope coverage。
6. 最后运行一次新的 exact run ID；不得复用旧 run 的成功文件。

完成定义：37 个 required gates 全部通过、absolute scope issue count 为 0、所有 evidence fingerprint 为当前值。

## 7. 验证命令与证据入口

### 7.1 当前证据

- Exact gate summary：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/quality-gates-exact.json`
- Absolute scope：`test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-scope-coverage.json`
- Main parity：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/parity-report.json`
- Exact parity：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/exact-incremental-parity.json`
- UI manifest：`test_data/outputs/luminar-1.28.0-23071/ui/reference-manifest.json`
- UI execution：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/ui-execution-evidence.json`
- Interaction execution：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/interaction-execution.json`
- Native persistence：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r17-current-only-final/native-persistence-roundtrip.json`

### 7.2 回归与门禁

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python scripts/validate_absolute_scope_coverage.py
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id <new-current-run-id>
```

若 P0 的锁屏、专用显示或隔离输入条件未满足，应停止在 preflight，不得继续生成官方 Native evidence。
