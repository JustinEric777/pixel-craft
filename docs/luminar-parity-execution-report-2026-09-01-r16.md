# Luminar Neo 对齐执行报告（R16）

## 1. 结论

本轮已按“先冻结验收分母、再执行、最后统一门禁”的顺序完成可安全执行的工作，但当前不能判定为与本地 Luminar Neo 绝对对齐。

最终 exact 质量门禁共 37 项，通过 28 项，失败 9 项，状态为 `blocked`。阻塞集中在四类事实差距：Native 参考证据不足、效果误差仍超阈值、124 个交互没有完整的双端证据、原生 History 状态编解码和重启往返尚未完成。

本轮没有增加历史兼容分支，也没有使用兼容性回退掩盖缺证据状态。交互矩阵中的 `source_contract_id` 是冻结矩阵显式声明的源契约映射，不是旧 ID 猜测或兼容回退。

## 2. 已执行范围

### 2.1 冻结验收分母

- UI 状态矩阵：210 项，定义校验通过。
- 交互矩阵：124 项，定义校验通过。
- UI 矩阵指纹：`71ff41351bd8c997fbe7f18368f439bd922a129630064c245c40e0c4975f5134`。
- 交互矩阵指纹：`c9d5ff6085567b9ce83f0e64004e4f8447cdd7697639f78a18763d1b859b87db`。
- Sky AI 已扩展为 18 个精确控件；当前效果矩阵共 290 个 case。
- exact 增量队列为 98 项，其中 42 项缺 Native 参考。

### 2.2 本地浏览器 UI 实测

- 40 个工具全部执行折叠、展开、再次折叠，80/80 工具面板状态通过逻辑检查。
- 16 个工作区状态全部执行并留存截图及 DOM：目录、编辑、预设、编辑历史、更多、信息、工具展开、编辑栏折叠、图层栈、图层库、黑白转换前后、降噪等级、导出弹窗、多图导入、多图 HDR 完成。
- HDR 使用三张规范输入，实际完成“3 张图片已完成 HDR 合并”，并确认导出可用。
- 首次审计发现 114 个参数状态中存在 66 个参数表面，缺失 48 个。本轮随后实现并逐项复测这 48 项，结果为存在 48/48、修改 48/48、恢复 48/48。
- 已增加裁剪旋转可读状态；结合首次执行记录，当前 114/114 参数表面均可断言。
- 合并两次浏览器执行记录后，210/210 个 UI 逻辑状态均具备可断言表面。
- 旧的 16 个工作区观察可通过矩阵显式 `source_state_id` 映射到当前状态，但它们没有当前矩阵指纹下的双端截图与像素差；因此官方 UI execution 为 0/210、UI exact 为 0/210。浏览器逻辑通过不能替代像素级对齐。

已补齐的 48 个参数表面：

- 39 个工具的 `opacity`。
- `crop_ai`、`denoise`、`deblur` 的 `amount`。
- `new_neon_light` 的笔刷输入，以及 `neon_spread`、`atmosphere`、`hue`、`whiteness`。
- `bokeh_ai` 的 `radius`。

同时修正 Sky AI 表面：严格保留矩阵规定的 18 项，移除不属于 `sky_replace` 参数契约的通用 amount 和 opacity。

### 2.3 交互证据

- 修正交互矩阵 ID 与 Native 源观察目录的解析方式：验证器现在严格读取矩阵中的 `source_contract_id`。
- 修正前错误统计为 0/124 的问题后，确认 Native 有效观察为 9/124。
- 旧的 Native 观察中仅 `preset-import-preview-apply` 缺失；其余缺口来自新增的 114 个逐参数交互。
- 绝对范围审计可识别 8 个当前 workflow 的浏览器源观察，但官方浏览器交互门禁仍为 0/124：现有审计没有同时覆盖每项契约要求的 API 状态、撤销、重做、重置、导出结果与 Native 观察链接，不能冒充完整契约证据。

### 2.4 效果和模型链路

- 主效果矩阵维持 35/40，通过率未用单图特调虚增。
- 仍失败的 5 个主效果：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。
- exact 增量矩阵：98 项中 50 项通过、6 项失败、42 项缺 Native 参考。
- 6 个 exact 失败 case：
  - `exact-face_ai-1fad50972277`
  - `exact-structure_ai-50a826858cbd`
  - `exact-depth_volume-8bf32569889d`
  - `exact-blue_hour-a28cc5ae5e2b`
  - `exact-landscape_enhancer-e258e246b99f`
  - `exact-face_ai-501ddff4b40f`
- 上一轮原始失败数为 8，本轮为 6；但两轮有效参考分母不同，不能据此宣称效果质量净提升，也不能把 50/98 解读为完整效果通过率。
- 首次最终门禁另发现 3 个 New Neon Light case 因默认空 `strokes` 覆盖 Native 定位笔画而无法生成。本轮已修正 case builder 的参数优先级并增加回归约束；最终候选生成 98/98，失败 0。
- Sky 端到端 48/48、Overlay 38/38、多图 smoke 3/3、模型候选调用 18/18、40 个免费能力覆盖均通过。

### 2.5 Native 采样与持久化

- Native 采样前置检查已改为 fail-closed。
- 未显式授权前台 UI 控制时，采样会以 `foreground-ui-control-not-authorized` 阻断。
- 显式允许 UI 控制后，仍因缺少已验证的显示与输入隔离信息而在 isolation gate 阻断；本轮没有在不安全状态下生成伪 Native 参考。
- 已确认本地 Luminar Neo catalog schema 为 v155，共 26 张表。
- 已确认真实编辑状态位于 catalog 的 `History/<guid>` 文件，内容包括 `layers_array`、裁剪等状态；数据库 `img_history_states.data_wide_ch` 不能被简单的 `edit_count` JSON 代替。
- 当前工程仍使用 JSON project repository，原生 40 个工具 ID、参数映射、图层/蒙版状态和 undo 游标尚未形成可验证的 Native codec。
- 因未产生 `native-persistence-roundtrip-manifest.json`，7 次重启往返验收未开始，持久化门禁阻断。

## 3. 执行前后对比

| 维度 | 执行前 | 执行后 | 结论 |
| --- | ---: | ---: | --- |
| 主效果 | 35/40 | 35/40 | 未退化；5 个核心差距仍在 |
| exact 已有/当前矩阵 | 61/69，通过 61、失败 8 | 98 项：通过 50、失败 6、缺参考 42 | 已有参考失败数减少 2；新分母不可直接同比 |
| UI 验收分母 | 历史 16 个粗粒度状态 | 210 个冻结状态 | 分母已细化并可追踪 |
| UI 浏览器逻辑执行 | 未按 210 项执行 | 210/210 可断言 | 48 个缺表面与裁剪旋转状态已补齐 |
| UI exact 像素对齐 | 无当前证据 | 0/210 | Native 截图链仍缺失 |
| 交互验收分母 | 历史粗粒度观察 | 124 个冻结契约 | 分母已细化并可追踪 |
| Native 交互证据 | 因 ID 路径问题误报 0/124 | 9/124 | 修正统计，不代表新增了 9 项功能 |
| 浏览器交互源观察 / 完整契约 | 无当前证据 | 8/124 源观察；0/124 完整契约 | 需要逐项补齐 undo/redo/reset/export/API 证据 |
| absolute scope 口径 | 旧 16 UI / 10 interaction 粗分母，58 条问题 | 当前 210/124 分母，684 条记录级问题 | 数量变大来自分母纠正，不是功能倒退 |
| exact 候选生成 | 95/98，3 个 Neon case 无效 | 98/98 | 空笔画夹具遗漏已修复 |
| exact 质量门禁 | 27/37（含无效候选） | 28/37 | 当前状态明确为 blocked |
| 自动回归 | 旧基线 | Python 405、前端 46 全通过 | 本轮改动未引入已知回归 |

## 4. 明确遗漏

1. 40 个可见工具都没有满足至少 2 个额外 holdout 输入的绝对覆盖要求。
2. 9 个能力缺 amount anchor：`clone`、`color_transfer`、`complex_bleach`、`crop_ai`、`deblur`、`dodge_burn`、`erase`、`lut_mapping`、`skin_smooth`。
3. 6 个裁剪参数未进入效果 exact 覆盖：`crop_box`、`crop_ratio`、`crop_rotation`、`flip_x`、`flip_y`、`straighten`。
4. 42 个 exact case 缺 Native 参考，其中 28 个是 Sky AI 组合。
5. 210 个 UI 状态中，16 项只有可映射的旧工作区源观察；仍缺 194 项 Native reference 和 194 项正式 browser execution，且 210 项均没有当前矩阵下的有效像素差结论。
6. 124 个交互契约中，Native 仅有 9 项当前观察、缺 115 项；浏览器有 8 项当前源观察、缺 116 项，且没有一项具备完整契约证据链。
7. `preset-import-preview-apply` 缺 Native 观察。
8. 5 个主效果和 6 个 exact case 仍超阈值。
9. 原生 History codec、图层/蒙版/undo 状态和 7 次重启往返清单缺失。
10. 10 条旧 Native 交互证据不属于当前契约 ID，已被标记为 unexpected；不会加入兼容映射。

当前 absolute scope 的 684 条记录级问题由以下项目组成：40 个 holdout、9 个 amount anchor、6 个裁切参数、194 个 UI Native reference、194 个正式 UI execution、115 个 Native interaction、116 个 browser interaction，以及 10 条 unexpected Native interaction。类别存在交叉含义，但验证器按缺失记录逐条计数。

## 5. 下一阶段可执行计划

### P0：先建立可信 Native 采样通道

1. 在专用显示会话中配置并验证 provider、session、`verified_at`、虚拟显示隔离和输入隔离。
2. 先用 3 个探针验证截图坐标、色彩空间、缩放比例和前台焦点，再解锁批量采样。
3. 采集 42 个缺失 exact reference、210 个 UI Native 截图和 115 个缺失 Native 交互观察。
4. 每个证据记录 Luminar build、输入哈希、资产 ID、控件值、截图哈希、裁剪区域和采集时间；不允许手工补状态。

完成标准：42 个 pending-reference 清零；Native UI 210/210 有效；Native interaction 124/124 有效；数据链指纹与当前矩阵一致。

### 已完成：补全当前产品表面，不保留兼容路径

1. 已为 39 个工具增加真实 `opacity` 控件，并接入效果合成和导出参数。
2. 已增加 `crop_ai`、`denoise`、`deblur` 的 `amount`。
3. 已实现 New Neon Light 的笔刷、扩散、氛围、色相、白度。
4. 已增加 Bokeh AI `radius` 并接入推理响应。
5. 已暴露裁剪旋转的可读状态。
6. 已将 Sky AI 收紧为 18 项当前契约，不增加旧字段或兼容分支。

结果：参数表面 114/114 存在且可操作；Browser logical UI 210/210 可断言；未增加 compatibility layer。Native 像素级门禁仍需 P0 采样通道完成后验证。

### P1：闭合 124 个交互契约

每项交互统一执行：初始状态 → 用户操作 → API 状态 → 视觉状态 → undo → redo → reset → export → 重开项目，并链接对应 Native 观察。

优先顺序：

1. 补 `preset-import-preview-apply` Native 观察。
2. 先完成 66 个已有浏览器表面的完整证据链。
3. 基于已经补齐的 48 个参数表面，完成剩余逐参数契约的完整证据链。
4. 最后执行多图三工作流和导出重开的一致性检查。

完成标准：Browser 124/124、Native 124/124，所有契约的 end state、undo、redo、reset 和 export 与 Native 一致。

### P1：效果对齐采用多图约束

1. 为 40 个工具各补至少 2 个 holdout，覆盖人像、天空/风景、低光/高动态三类输入。
2. 补 9 个 amount anchor 和 6 个 crop exact 参数 case。
3. 对 5 个主失败效果和 6 个 exact 失败 case 做因果诊断；先确认输入归一化、mask、模型权重、参数曲线和混合顺序，再修改算法。
4. `depth_volume` 当前方向与 Native 相反，必须先确认深度图极性和混合公式，禁止继续做单图亮度补偿。
5. `face_ai` 先验证人脸检测/分割输入和区域 mask；`sky_replace`/`sunrays` 先验证天空 mask、资产坐标与遮挡；`blue_hour`/`landscape_enhancer`/`structure_ai` 先验证色彩空间和局部结构尺度。

完成标准：主效果 40/40；exact 失败为 0；每个工具的 holdout 和 anchor 都达到绝对覆盖门禁。

### P1：单轨 Native 持久化

1. 用真实 Luminar 新建项目生成最小状态对照，逐字段确认 catalog 与 `History/<guid>` 的写入责任。
2. 建立 v155 当前 schema 的单一 codec：40 个工具、参数、资产 ID、图层顺序、图层 opacity、蒙版、裁剪和 undo cursor。
3. API project repository 直接切换为单轨 Native repository；删除 JSON repository 和任何双写、迁移、旧字段适配逻辑。
4. 禁止向 `img_history_states.data_wide_ch` 写入推测性 JSON；只有在本地 Luminar 实证使用该字段后才能写入。
5. 执行 7 次往返：创建、编辑、关闭服务、重启、读取、继续编辑、导出，并同时用本地 Luminar Neo 打开验证。

完成标准：生成并通过 `native-persistence-roundtrip-manifest.json`；7/7 重启往返通过；Luminar 和本项目双向打开后状态、图层、历史、导出一致。

### P2：最终绝对验收

1. 在冻结 build、固定 DPR=2、1440×900 逻辑视口下重跑 210 UI exact A/B。
2. 重跑 124 interaction、40 主效果、98+ exact、40×2 holdout、9 anchors、6 crop 参数和 7 persistence roundtrip。
3. 仅当 37/37 exact 质量门禁通过、所有 pending/failed 为 0、且无 compatibility layer 时，才允许结论为“与本地 Luminar Neo 当前版本对齐”。

## 6. 验证命令与结果

- `.venv/bin/python -m pytest -q`：405 passed，1 个第三方 Starlette deprecation warning。
- `npm test -- --run`：11 个测试文件、46 项测试通过。
- `npm run build`：通过。
- `ruff check`：通过。
- `scripts/run_quality_gates.py --level exact --run-id r16-current-matrix-final`：37 个门禁，28 通过、9 失败，状态 blocked；exact 候选生成 98/98，效果结果为主矩阵 35/40、增量矩阵 50 passed / 6 failed / 42 pending。

## 7. 关键证据

- `configs/parity/core-ui-state-matrix.json`
- `configs/parity/core-interaction-matrix.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/browser-surface-audit-r16/audit.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/browser-surface-audit-r16-after-ui-completion.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-validation-r16.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-validation-r16.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r16-current-matrix-final/quality-gates-exact.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r16-current-matrix-final/exact-incremental-candidate-generation.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r16-current-matrix-final/exact-incremental-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r16-current-matrix-final/absolute-scope-coverage.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r16-current-matrix-final/native-persistence-roundtrip.json`
