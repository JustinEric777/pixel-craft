# Luminar Neo 1.28 效果、UI、交互绝对对齐收敛计划（第二轮，2026-08-26）

> 本计划基于 `absolute-parity-execution-report-2026-08-26.md` 和最终 exact gate 的真实结果制定。目标是在本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`、冻结输入/素材和 `2880×1800` 物理截图范围内，关闭现有 6 个 required 失败门禁。计划只维护活动 1.28 合同，不增加历史版本兼容逻辑，不重复采样已经 ready 且证据可信的 reference。

## 目录

- [1. 当前结论与执行边界](#1-当前结论与执行边界)
- [2. 最终成功标准](#2-最终成功标准)
- [3. 不做什么](#3-不做什么)
- [4. 执行原则](#4-执行原则)
- [5. 阶段依赖与推荐顺序](#5-阶段依赖与推荐顺序)
- [6. P0：冻结第二轮基线](#6-p0冻结第二轮基线)
- [7. P1：补齐确定性证据基础设施](#7-p1补齐确定性证据基础设施)
- [8. P2：完成原生交互 observation](#8-p2完成原生交互-observation)
- [9. P3：UI 七状态结构与像素收敛](#9-p3ui-七状态结构与像素收敛)
- [10. P4：Browser 十条交互合同收敛](#10-p4browser-十条交互合同收敛)
- [11. P5：效果主线与 exact 收敛](#11-p5效果主线与-exact-收敛)
- [12. P6：Panorama 原生语义收敛](#12-p6panorama-原生语义收敛)
- [13. P7：模型推理与长任务保护](#13-p7模型推理与长任务保护)
- [14. P8：全量门禁、双跑、清理与交付](#14-p8全量门禁双跑清理与交付)
- [15. 修改入口与验证矩阵](#15-修改入口与验证矩阵)
- [16. 单批次执行模板](#16-单批次执行模板)
- [17. 停止条件、回退与风险控制](#17-停止条件回退与风险控制)
- [18. 最终验收清单](#18-最终验收清单)

---

## 1. 当前结论与执行边界

### 1.1 最新真实基线

基线来源：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-after-2026-08-26.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-2026-08-26.json`；
- `docs/parity/absolute-parity-execution-report-2026-08-26.md`。

| 域 | 当前结果 | 本轮目标 |
|---|---:|---:|
| Exact quality gates | `21 passed / 6 required failed / 1 optional failed` | required failure `0` |
| 主效果 | `36/45` | `45/45` |
| Exact | `38/69`，failed `31`，pending `0` | `69/69` |
| Overlay | `38/38` | 保持 |
| Multi-image | `2/3` | `3/3` |
| UI current-build evidence | `0/7` | `7/7` |
| UI parity | `0/7` | `7/7` |
| Native interaction | `1/10` | `10/10` |
| Browser interaction | `1/10` | `10/10` |
| Interaction issues | `18` | `0` |
| 采样队列 | `251/251 ready` | 保持，不重复采样 |
| Python / frontend | `285 / 13 passed`，frontend build 通过 | 不回退 |
| Cleanup postcheck | `0 path / 0 byte` | 每阶段保持 |

6 个 required 失败固定为：

1. `multi-image`；
2. `output-parity`；
3. `exact-incremental-parity`；
4. `ui-execution-evidence`；
5. `ui-parity`；
6. `interaction-execution`。

唯一 optional 失败为 `model-contract-inventory`：92 条记录都有效，但只有 26 条完成 model-specific validation，66 条为 optional pending。本轮不以扩展 optional 模型为主线，也不能让该 optional 项阻塞 required 对齐。

### 1.2 “绝对对齐”的可验证含义

本计划中的“绝对对齐”不是宣称覆盖 Luminar Neo 的全部商业能力，而是指以下冻结合同同时通过：

- 原生版本：Luminar Neo `1.28.0 (23071)`；
- bundle、语言、时区：活动 reference profile 中的 bundle，`zh-Hans`，`Asia/Shanghai`；
- 输入与素材：现有 frozen source、free preset、Sky、Overlay、多图 fixture；
- 参数：现有 main 45 条、exact 69 条 case 参数；
- UI：logical viewport `1440×900`、device scale factor `2`、物理截图 `2880×1800`；
- 交互：`configs/parity/interaction-contracts.json` 的 10 条合同；
- 像素门限：`configs/parity.yaml` 当前门限，不放宽、不增 case 例外；
- 结果必须可重跑、可追溯、hash 稳定、失败时 fail closed。

冻结范围外的未来版本、付费素材、不可达 optional 模型、未冻结输入和移动端布局不包含在“完成”声明内。

### 1.3 已完成能力不是本轮重做项

以下结果只做回归保护，不重新实现：

- 251 条采样记录全部 ready，已有可信 reference 不重复采样；
- 黑白工具先点击“转换为黑白”，再启用亮度/饱和度调节；
- 降噪必须先选择原生等级，再记录强度和导出；
- 无变化、无 Reset 证据、重复导出已经受数据链和清理规则约束；
- 导出在当前页下载，文件名为 `<source-stem>-edited.png`；
- 编辑面板折叠后画布展开、恢复后编辑栈不变；
- Overlay `38/38`；
- required 模型、lease/checkpoint、长任务结果恢复当前通过。

## 2. 最终成功标准

只有下表所有 required 条件同时成立，才允许把冻结范围标记为完成：

| 域 | 必须达到的准出标准 |
|---|---|
| 数据链 | `251/251 ready`；duplicate、invalid、pending 均为 0；ready 项未重新排队 |
| 主效果 | `45/45`，shape match，使用现有 MAE/SSIM 门限 |
| Exact | `69/69`，pending 0，不删除 required case |
| 内容回归 | Preset、Sky、Overlay 均不回退；Overlay 保持 `38/38` |
| Multi-image | HDR、Focus、Panorama `3/3` |
| UI evidence | 当前 frontend build 的 7 个状态均有有效环境、fixture、截图和 SHA-256 |
| UI parity | `7/7`；每项 shape match、`MAE <= 0.03`、changed pixel ratio `<= 0.02` |
| 原生交互 | observation `10/10`，app/fixture/artifact hash 完整，issue 0 |
| Browser 交互 | execution `10/10`，events/assertions/waits 完整，issue 0，`fixed_sleep=false` |
| 模型 | required logical model 与真实 invocation 门禁不回退；model loader/lifecycle 通过 |
| 长任务 | 慢模型可跨刷新、切项目、worker 重启拿到完整 terminal result/artifact |
| 工程回归 | Python、Ruff、frontend test/build 全通过 |
| 发布 | exact quality gate 连续两轮 required failure 为 0，关键候选/evidence hash 稳定 |

## 3. 不做什么

- 不全量重采已 ready 的效果、Preset、Sky、Overlay、UI 原生 reference 或 exact reference。
- 不把当前 build 之前的 Browser 截图重新登记为 current-build evidence。
- 不修改原生 reference 图片、manifest hash 或 required case 来制造通过。
- 不放宽 `configs/parity.yaml` 的 MAE、SSIM、changed-pixel 或 shape 门限。
- 不为单个 case id、单张输入、文件 hash 或固定输出尺寸写运行时特例。
- 不以固定 sleep、接口 `200`、按钮点击成功或“肉眼差不多”替代结果门禁。
- 不把 Panorama 的固定比例 resize 换成另一组固定 crop 常量。
- 不为 1.25/1.26 或旧 payload、旧样式、旧行为增加兼容分支。
- 不为了 optional 66 个模型合同打断 required 对齐主线。
- 不做移动端、响应式重设计或与原生桌面 UI 无关的视觉美化。
- 不在 `ai/model` 放入工具强度、mask 合成、业务编排或页面状态。

## 4. 执行原则

### 4.1 一个批次只关闭一个可解释根因

每个批次必须记录：

1. 目标 case/state/contract；
2. 当前指标和 artifact hash；
3. 一个可证伪的根因假设；
4. 修改文件和受影响通过项；
5. 窄测试、目标验证、同域回归；
6. 修改前后指标与 hash；
7. 通过、继续 blocked 或回退的决定。

只有真实逻辑第二次重复时才提取新抽象，不先建设通用自动化框架、通用效果 DSL 或新的设计系统。

### 4.2 Reference 默认只读

算法指标失败不是重采理由。只有以下证据之一成立，才允许把单条 reference 放入 targeted reobserve：

- app version/build、source hash、素材 hash 或参数 readback 与合同不一致；
- 非中性效果导出后 Reset/恢复原图能力不可用；
- preview 与 export 不一致；
- export 相对 source 没有可测变化，且原生交互证明效果应为非中性；
- 黑白没有先转换，或降噪没有先选择等级；
- 导出文件/hash 归属错误。

即使满足条件，也必须先登记 invalid/suspected record、dry-run 只选择一个 `record-id`，再 `--limit 1 --allow-ui-control` 定向重观察。已验证的其他记录不进入队列。

### 4.3 先合同，再结构，再像素

- UI：先建立确定性 capture 环境，再修壳层几何，再修组件状态，最后修 token/像素细节。
- 交互：先得到原生状态机，再在本项目执行相同状态转换。
- 效果：先核对输入、颜色、模型、mask、坐标和编辑图顺序，再调曲线或参数。
- Panorama：先确定投影、warp 和有效边界，再做 seam、曝光和 blending。
- 长任务：先确保 terminal result 完整和归属正确，再优化等待体验。

### 4.4 所有阶段 fail closed

缺少截图、hash、readback、模型输出、完整 result、native observation 或最终 export 时，状态必须保持 blocked。新 build 使旧 evidence 失效是正确行为，不能通过跳过 build hash 校验处理。

### 4.5 运行时与诊断严格分离

运行时代码不得读取历史 parity 报告、原生输出 hash 或失败注册表决定算法分支。诊断文件只用于开发期归因和门禁。

## 5. 阶段依赖与推荐顺序

```text
P0 冻结第二轮基线
  │
  ▼
P1 证据基础设施
  ├── UI: logical 1440×900 / DPR 2 确定性采集
  └── Native: mouse/key down-up、wheel、drag、状态等待
  │
  ├───────────────┐
  ▼               ▼
P2 Native 10/10   P5 效果 45/45 + exact 69/69
  │               │
  ▼               ▼
P3 UI 7/7         P6 Panorama 3/3
  │               │
  ▼               │
P4 Browser 10/10  │
  └───────┬───────┘
          ▼
P7 模型/长任务保护性回归
          │
          ▼
P8 exact 双跑、清理、交付
```

推荐严格按 P0 → P1 → P2 → P3 → P4 执行证据/UI/交互主线；P5、P6 的代码边界与前端不同，可以穿插，但每个批次仍单独提交和验收。P7、P8 不得提前标记完成。

## 6. P0：冻结第二轮基线

### 6.1 目标

把本轮入口固定为最新 `21/6/1`，避免继续引用旧计划的 `22/5/1`。不复制大图，只保存报告 hash、失败集合和环境合同。

### 6.2 工作项

1. 先给 `build_convergence_baseline.py` 增加显式报告输入参数：`--quality-gates`、`--output-parity`、`--exact-parity`、`--ui-parity`、`--ui-execution`、`--interaction`、`--multi-image`、`--cleanup`。当前脚本固定读取第一轮 canonical 文件名，直接运行会得到过期的 `22/5/1`，不能作为第二轮基线。
2. 默认值只指向活动 profile 的 canonical 文件；第二轮命令显式传入 `*-after-2026-08-26.json`。这不是历史兼容逻辑，而是让一次基线构建使用同一批真实报告。
3. 给显式输入、缺失报告、reference id 不一致和报告批次混用补窄测试；任一情况必须 fail closed。
4. failure registry 增加或确认字段：domain、case/state/contract、capability、metrics、reference/candidate hash、owner batch、root-cause hypothesis、status。
5. 记录当前 frontend build hash；现有 UI screenshot build hash 不一致，保持 invalid current-build evidence。
6. 记录 9 条缺失 native 和 9 条缺失 Browser contract。
7. 记录 Panorama 当前 `MAE 0.0819413 / SSIM 0.815541`、shape `1070×1410`。
8. 验证采样队列 `251/251 ready`、data-chain issue 0、cleanup 0。

建议产物：

- `diagnostics/convergence-baseline-round-2-2026-08-26.json`；
- `diagnostics/convergence-failures-round-2-2026-08-26.json`；
- `diagnostics/convergence-batches-round-2-2026-08-26.json`。

### 6.3 验证命令

```bash
.venv/bin/python scripts/build_convergence_baseline.py \
  --profile-root test_data/outputs/luminar-1.28.0-23071 \
  --quality-gates test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-after-2026-08-26.json \
  --output-parity test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-after-2026-08-26.json \
  --exact-parity test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-exact-after-2026-08-26.json \
  --ui-parity test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json \
  --ui-execution test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence.json \
  --interaction test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-after-2026-08-26.json \
  --multi-image test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-after-2026-08-26.json \
  --cleanup test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-final-2026-08-26-postcheck.json \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-baseline-round-2-2026-08-26.json \
  --failure-output test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-round-2-2026-08-26.json

.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-round-2-p0-dry-run.json
```

### 6.4 准出标准

- 能重建 `21 passed / 6 required failed / 1 optional failed`；
- 主效果失败 9、exact 失败 31、UI 失败 7、interaction issue 18；
- exact pending 0；
- 251 条 ready 没有进入新采样队列；
- cleanup 为 0；
- reference、输入、素材和阈值 hash 没有变化。

## 7. P1：补齐确定性证据基础设施

P1 只补当前门禁直接需要的能力，不扩展成通用浏览器或桌面自动化平台。

### 7.1 P1-A：UI 确定性采集合同

#### 当前根因

原生 UI reference 是 `2880×1800`；对应逻辑 viewport 应为 `1440×900`、DPR 2。当前 in-app Browser 会话是 `1280×720` 且没有暴露 viewport override，因此不能用于发布七状态 current-build evidence。旧七张截图的 frontend build hash 已失效。

#### 最小工作项

1. 先做依赖能力审计：确认现有 Node 依赖是否能直接启动可控 Chromium。当前 `frontend/package.json` 没有直接声明 Playwright；不得假设 lockfile 中的 optional peer 已可调用。
2. 若现有环境不可用，只增加一个明确的 dev-only capture 依赖和一个脚本，不引入 E2E 框架全家桶。
3. 建议新增 `frontend/scripts/capture-ui.mjs` 或等价最小入口，参数至少包括：
   - base URL；
   - state；
   - logical width/height；
   - DPR；
   - locale/timezone；
   - output path。
4. 启动上下文必须固定：`1440×900`、DPR 2、`zh-Hans`、`Asia/Shanghai`、reduced motion、固定字体和颜色方案。
5. 使用 `scripts/seed_ui_validation_catalog.py --reset` 建立隔离 fixture；不得读取开发者日常 catalog。
6. 每个状态只在确定条件达成后截图：请求结束、图片 decode 完成、字体 ready、动画关闭、布局连续两帧稳定；不使用固定 sleep。
7. 采集结果仍由现有 `scripts/build_ui_browser_execution.py` 发布，复用现有 build hash、fixture hash、screenshot hash 和 shape 校验，不再创造第二套 manifest。
8. `build_ui_browser_execution.py` 的 environment 应显式记录 logical viewport、physical viewport、DPR 和 capture engine；validator 对缺失或不匹配保持 blocked。

#### 窄测试

- logical `1440×900` + DPR 2 必须输出 `2880×1800`；
- 改 frontend 源码后旧 evidence 必须失败；
- fixture hash 不一致、重复 state、截图 hash 错、截图尺寸错必须失败；
- 页面仍在加载、字体未 ready 或 animation 未关闭时不得发布截图；
- 七状态顺序稳定，文件名为 `<state>.png`。

#### 验证

```bash
.venv/bin/python scripts/seed_ui_validation_catalog.py \
  --reference-id luminar-neo-macos-1.28.0-23071 --reset

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/build_ui_browser_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --browser-version <capture-engine-version>

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --reference-id luminar-neo-macos-1.28.0-23071
```

P1-A 的目标只是得到当前 build 的 `7/7` 有效 evidence；视觉 parity 仍可为 `0/7`，在 P3 关闭。

### 7.2 P1-B：原生 observer 动作语义

#### 当前根因

`edit-toggle-collapse` 已通过；`before-after-compare` 的普通 AXPress 只改变按钮区域，整窗归一化 MAE 约 `0.0000197`，没有证明 source image 显示。后续 zoom、slider、layer reorder 也需要真实按住、滚轮和拖动语义。

#### 最小工作项

在现有 `scripts/luminar_capture/` helper 中只补当前合同需要的动作：

- `mouse_down` / `mouse_up`；
- `key_down` / `key_up`；
- wheel with direction/delta；
- drag from resolved element geometry to normalized/value target；
- 等待 AX value、title、geometry、PreviewImage hash 或可见控件状态；
- finally 中保证所有按键和鼠标释放、窗口恢复、失败 artifact 保存。

不要新增通用录制器、脚本语言或任意坐标宏系统。优先使用 AX identifier/name/value；只有 AX 没有语义目标时才使用相对元素 geometry，并把几何证据写入 observation。

#### 窄测试

- down/up 成对，即使中途异常也释放；
- wheel/drag 目标不存在时 fail closed；
- before/after 必须证明 PreviewImage 区域变化，而不是只看按钮像素；
- wait 只能来自合同 `allowed_wait_conditions`；
- 不出现 fixed sleep；
- 失败 observation 不会覆盖已通过 observation。

### 7.3 P1 准出标准

- UI capture 能稳定生成当前 build 的 7 张 `2880×1800` candidate；
- UI execution evidence `7/7`；
- native helper 能表达 9 条剩余合同需要的动作和状态等待；
- 新基础设施有窄测试，Python/Ruff/frontend test/build 不回退；
- 没有重新采集原生 UI reference 或效果 reference。

## 8. P2：完成原生交互 observation

### 8.1 目标与顺序

当前 native 为 `1/10`，已通过 `edit-toggle-collapse`。剩余 9 条必须逐条执行，不能一次连跑：

1. `before-after-compare`；
2. `zoom-pan`；
3. `edit-slider-drag`；
4. `undo-redo`；
5. `catalog-import-select`；
6. `preset-preview-apply`；
7. `layer-add-reorder-opacity-delete`；
8. `export-dialog`；
9. `multi-image-workflow`。

顺序先处理只改 view state 的合同，再处理单编辑、项目写入、文件导出和多图长流程。

### 8.2 每条合同的真实断言

| 合同 | 原生 observation 必须证明的事实 |
|---|---|
| Before/after | 按住期间 PreviewImage 显示 source；释放后恢复 edited；项目状态不变 |
| Zoom/pan | zoom title/value 变化；pan 后图像几何变化；fit 后恢复；无 edit mutation |
| Slider | Details 工具展开；slider readback 为 `0.65`；应用后 preview 变化且编辑存在 |
| Undo/redo | 撤销移除确定编辑；重做恢复同一语义参数，不产生第二条等价编辑 |
| Catalog | 文件只导入一次；记录可见；选中后进入 Edit；source hash 正确 |
| Preset | focus/preview 不写 edit；apply 一次；busy 清除；顺序与原生一致 |
| Layer | 创建、排序到顶、opacity 50%、删除完整发生；每步 UI 状态可见 |
| Export | 原生导出完成；输出尺寸/类型/文件存在；有非中性编辑时 Reset/恢复原图仍可用 |
| Multi-image | 所有 frame 可见；preview ready；ready 前不可导出；输出和 workflow 状态完整 |

特别约束：

- 黑白 observation 必须先触发“转换为黑白”再移动亮度/饱和度；
- 降噪 observation 必须先选择对应等级再应用强度；
- 非中性效果导出后若原生没有 Reset/恢复选项，必须标记该 attempt 无效，不能写 canonical；
- 导出相对 source 无变化时，必须先判为无意义 attempt，不能以文件存在作为成功。

### 8.3 单合同执行模板

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --contract-id <contract-id> --dry-run

.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --contract-id <contract-id> --allow-ui-control

.venv/bin/python scripts/validate_interaction_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-round-2.json
```

每条成功后立即检查 observation JSON、before/after、AX snapshot 和 SHA-256，再执行下一条。`--resume` 只能跳过 app build 与 artifact hash 都完整的已通过 observation。

### 8.4 准出标准

- native observations `10/10`；
- native issue 0；
- events 与合同完全一致；
- app version/build/bundle 和 fixture hash 完整；
- wait 均来自合同且无 fixed sleep；
- 失败 attempt 保留诊断但不覆盖 canonical observation；
- 已通过的 `edit-toggle-collapse` 不回退。

## 9. P3：UI 七状态结构与像素收敛

### 9.1 唯一视觉方向

唯一方向是原生 Luminar Neo 1.28 的桌面精密编辑工作台：画布是视觉中心，顶栏和侧栏服务编辑任务，面板紧凑，层级清楚，装饰克制。不得引入与 reference 无关的渐变、玻璃拟态、漂浮卡片、营销布局或新的品牌视觉。

当前历史指标约为：

| 状态 | MAE | changed pixel ratio |
|---|---:|---:|
| catalog | `0.1780` | `0.9505` |
| presets | `0.2431` | `0.9682` |
| edit | `0.2241` | `0.9677` |
| layer-stack | `0.2197` | `0.9528` |
| layer-library | `0.2263` | `0.9530` |
| tool-expanded | `0.2164` | `0.9529` |
| multi-image | `0.1091` | `0.9598` |

这些是结构级差异，不应从颜色或阴影微调开始。

### 9.2 收敛层次

#### U1：应用壳、几何与滚动所有权

主要入口：

- `frontend/src/App.tsx`；
- `frontend/src/components/WorkspaceRail.tsx`；
- `frontend/src/components/EditorHeader.tsx`；
- `frontend/src/components/PreviewPanel.tsx`；
- `frontend/src/styles.css`。

工作项：

1. 以 reference 测量顶栏、左 rail、主画布、右工具栏、图层栏和底部资源区的边界。
2. 使用一套明确 grid/flex 几何；同一方向只保留一个主要滚动容器。
3. 需要伸缩的子项显式设置 `min-width: 0`、`min-height: 0`。
4. 图片加载、空态、错误态、busy 态必须保持画布和面板尺寸稳定。
5. 保持折叠后画布展开、恢复后回到相同布局，编辑栈不变。
6. 每改共享壳层必须重截七状态，不只看目标页面。

#### U2：组件密度与可见状态

主要入口：

- `CatalogWorkspace.tsx`；
- `PresetBrowser.tsx`；
- `ToolPanel.tsx`；
- `LayersPanel.tsx`；
- `AssetPicker.tsx`；
- `WorkflowWorkspace.tsx`。

逐项对齐：字体、行高、控件高度、内边距、分隔线、选中态、hover、focus-visible、disabled、expanded/collapsed、loading、empty、error。

行为不能因视觉调整回退：

- 黑白转换前亮度/饱和度控件 disabled；
- 降噪等级选择与强度是两个状态；
- preview ready 前 export disabled；
- 新请求清理依赖旧状态；
- 旧响应不得覆盖当前项目/预览；
- 图层和编辑操作不因面板折叠丢失。

#### U3：语义 token 和像素细节

只在相同值跨组件重复后收敛背景、表面、文字、边框、强调色、间距、圆角和短动效。页面只组合语义 token，不再创造第二套颜色体系。最后才调整文字基线、图标对齐、1px border、弱阴影和局部色差。

### 9.3 状态执行顺序

1. `catalog`：应用壳、资源网格和底部区域；
2. `edit`：顶栏、画布、右侧编辑栏和图层栏；
3. `presets`：预置资源密度、hover/selected；
4. `tool-expanded`：工具头、滑杆、值显示、应用状态；
5. `layer-stack`；
6. `layer-library`；
7. `multi-image`。

### 9.4 单状态循环

1. 确认 frontend build hash 和 fixture hash。
2. 使用 P1 capture runner 重截当前 build 的目标状态。
3. 运行 comparator，生成 reference/candidate/delta/heatmap。
4. 定位最大连续误差区域，分类为 geometry、typography、component-state、asset 或 token。
5. 只修一个层级。
6. 重截目标状态与一个共享壳状态。
7. 运行组件测试和 build。
8. 共享壳改动后重跑全部七状态。
9. 指标改善但未过时保持 failed，不登记“视觉完成”。

### 9.5 验证与准出

```bash
cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/validate_ui_references.py \
  --reference-id luminar-neo-macos-1.28.0-23071
```

准出要求：current-build evidence `7/7`；UI parity `7/7`；shape 全匹配；每项 `MAE <= 0.03`、changed pixel ratio `<= 0.02`；frontend tests/build 全通过；黑白、降噪、图层、面板、异步状态不回退。

## 10. P4：Browser 十条交互合同收敛

### 10.1 实现策略

以 P2 的 native observation 为状态真值，在本项目逐条重现。优先使用可访问名称和用户可见状态；只有目标不稳定时才补 `aria-*` 或 `data-testid`，且不能改变视觉布局。

Browser 原始记录继续写入现有 raw JSON 和 evidence root，再由 `scripts/build_interaction_browser_execution.py` 生成受校验的 execution manifest。不得在 raw JSON 中手写“passed”绕过真实截图、network、project JSON 或 export file。

### 10.2 合同级执行要求

| 合同 | Browser/API 必须对齐的状态 |
|---|---|
| Catalog import/select | asset/project 只创建一次；source hash 正确；选择后 Edit 和 preview ready |
| Preset preview/apply | focus 只 preview；apply 只写一次；编辑图顺序一致；busy 清除 |
| Slider drag | 显示值和 project 参数均为 `0.65`；只创建一条 Details edit |
| Panel collapse | 画布扩展、面板恢复、edit stack 不变；保留已通过证据 |
| Layer lifecycle | 创建、排序、opacity 0.5、删除在 UI/project 同步 |
| Undo/redo | redo 恢复相同 edit id/参数，不创建新 id |
| Before/after | 按住显示 source、释放恢复 preview；无 mutation request |
| Zoom/pan/fit | 只改 view state；indicator/pan/fit 均可见；项目不变 |
| Export | 一个 export request；下载完成；类型/尺寸/文件名正确；页面 URL 不跳转 |
| Multi-image | frame 名/hash 完整；preview ready 前不可导出；analysis/result hash 稳定 |

### 10.3 异步和长耗时约束

- 使用稳定 generation/project key，旧请求不得覆盖新选择。
- 页面卸载停止本地轮询，但不自动取消服务端模型任务。
- 轮询只在 terminal status 停止；`succeeded/completed` 后必须再取完整 result。
- result 的 artifact 缺失、hash 错或归属 project/job 错时保持失败。
- 多图和模型 preview 未 ready 前，导出按钮必须 disabled。
- 导出等待真实 download/network completion，不固定 sleep，也不通过重命名轮询猜测完成。

### 10.4 执行顺序与证据

先复验已通过的 `edit-toggle-collapse`，再按 P2 的剩余顺序执行。每条记录至少包含：events、visible assertions、API assertions、allowed waits、`fixed_sleep=false`、最终 screenshot、screenshot SHA-256、native observation link/hash，以及合同要求的 console/network/project/export/workflow artifact。

聚合与验证：

```bash
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --raw test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-raw.json \
  --evidence-root test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence

.venv/bin/python scripts/validate_interaction_contracts.py

.venv/bin/python scripts/validate_interaction_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-round-2.json
```

### 10.5 准出标准

- native `10/10`；Browser `10/10`；aggregate issue 0；
- 所有 waits 已声明，`fixed_sleep=false`；
- 导出只发一个请求、页面不跳转、文件可读且尺寸/类型正确；
- 模型/多图长流程得到完整 terminal result；
- console error、重复 mutation、stale response 和 artifact hash 错均为 0。

## 11. P5：效果主线与 exact 收敛

### 11.1 当前失败面

主效果 9 条失败：

- `face_ai`：MAE `0.030197`，SSIM `0.984212`；
- `slim_people`：MAE `0.053105`，SSIM `0.896961`；
- `depth_volume`：MAE `0.068934`，SSIM `0.946598`；
- `lut_mapping`：MAE `0.035247`，SSIM `0.999137`；
- `blue_hour`：MAE `0.133379`，SSIM `0.914102`；
- `fog`：MAE `0.113488`，SSIM `0.903759`；
- `sky_replace`：MAE `0.064346`，SSIM `0.946903`；
- `sunrays` 两条：`0.070206/0.942800` 与 `0.053714/0.956221`。

Exact 31 条失败覆盖人物、曲线、纹理/噪声、全局风格、天空/光照和降噪。以 `convergence-failures-round-2` 为机器可读清单，不在代码中硬编码这 31 个 case。

### 11.2 先诊断，后实现

每个失败 case 先生成：

- source/native/candidate 三联图；
- RGB、luma delta 和 heatmap；
- 边缘、人物、天空、背景和接缝 ROI；
- shape、MAE、SSIM、均值、方差、梯度、changed-pixel；
- candidate 连续两次输出 hash；
- 当前参数、模型 invocation、mask/depth/landmark 等中间 artifact 摘要。

根因分类只允许：input/parameter contract、color management、tone/curve、mask/ROI、geometry/coordinates、asset/compositing、noise/randomness、model preprocessing/output、edit graph/order。无法归类时不得盲目调参。

### 11.3 单能力闭环

每个 capability 选择：

1. 一个主失败 case；
2. 一个 exact anchor；
3. 一个未参与调参的 holdout；
4. 一个中性/no-op；
5. 至少一个同域已通过保护项。

执行：写窄测试 → 只改根因层 → force 目标候选 → 跑 main/exact/holdout/no-op → 跑同域保护门禁 → 双跑 hash。指标改善但未越过门限仍为 failed。

### 11.4 批次顺序

#### E1：低误差、颜色与值域合同

- `face_ai` 主 case：先查 mask feather/ROI 边界尾差；
- `lut_mapping`：工作色域、3D LUT 插值、alpha/opacity 和 clamp；
- exact 的 `pro_contrast`、`high_key`、`color_adjustments`、`color_enhancer`、`fade`。

E1 用来验证单能力闭环；不得因接近阈值而放宽门限。

#### E2：纹理、噪声和局部增强

- `denoise`、`denoise_laplacian`：等级和强度分开建模；已有 valid reference 不重采；
- `grain`：尺寸、强度、分布、色噪和确定性 seed；
- `structure_ai`、`ai_enhance`：局部结构 mask、halo 和高光保护；
- `radiance`：低频 glow、曝光保护和混合空间。

#### E3：人物、形变和深度

- `face_ai`、`face_enhancer`、`bokeh_ai`、`slim_people`、`depth_volume`；
- 统一 detector/landmark/person mask 的坐标、排序、padding、resize 和 feather；
- Slim People 只做人体局部 warp，保护背景直线；
- depth 固定 near/far、无效值、归一化和 resize 语义；
- 无脸/无人输入必须符合原生 no-op 语义。

只有模型 wrapper 的 preprocess/predict/postprocess 合同错误才修改 `ai/model`。效果强度、mask 合成、模型选择和业务顺序留在 `ai/pipeline` 或 `image_ops`。

#### E4：天空、雾和光源

- `blue_hour`、`fog`、`sky_replace`、`sunrays`；
- exact 的 `magic_lights`、`new_neon_light`、`landscape_enhancer`；
- 对齐 sky/horizon/reflection/foreground mask；
- Blue Hour 分离天空冷色、地面曝光和暖光；
- Fog 固定深度方向和边缘保护；
- Sunrays 固定太阳坐标、遮挡积分、衰减和 glow；
- Sky E2E 与 Overlay `38/38` 是硬回归门禁。

#### E5：全局风格和编辑图

- `default_effects`、`color_toning`、`vignette` 及剩余 exact；
- Default Effects 按真实编辑图顺序拆解，不用单个 tone curve 冒充复合效果；
- Vignette 对齐中心、半径、羽化、曝光曲线和高光保护；
- 中性、正值和负值方向必须同时正确。

### 11.5 定向生成与比较

主效果：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/work/<capability-id>-main.json
```

Exact：

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --output-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-exact-incremental \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --cases test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-cases-exact-incremental.json \
  --candidate-root test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-outputs-exact-incremental \
  --capability <capability-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/work/<capability-id>-exact.json
```

### 11.6 唯一允许的 targeted reobserve

只有 failure registry 先证明单条 reference 无效，才执行：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --dry-run

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --allow-ui-control
```

第二条只能在第一条输出明确只选择一个 record 后执行。成功 attempt 仍需通过 effect-change、Reset、preview/export、hash 和 data-chain 门禁；重复或无变化导出删除 attempt，不替换 canonical。

### 11.7 准出标准

- 主效果 `45/45`；Exact `69/69`；pending/invalid/duplicate 0；
- candidate 双跑 hash 稳定；
- Preset、Sky、Overlay、黑白锚点不回退；
- required 模型调用和 lifecycle 不回退；
- 没有新增 case/hash 特例、阈值例外或历史兼容逻辑。

## 12. P6：Panorama 原生语义收敛

### 12.1 当前根因与已否定假设

`image_ops/merge/panorama.py` 当前是 overlap translation + feather，末尾用 `1070/1080`、`1410/1440` 比例 resize。它匹配 shape，但不解释原生投影、局部 warp、接缝和有效边界。

中心 crop 已被诊断否定：`MAE 0.08908 / SSIM 0.78450`，差于当前 resize 的 `0.08194 / 0.81554`。因此下一轮不能提交固定 center crop。

### 12.2 G1：几何诊断

1. 保存每张输入到原生输出的稳定特征/边缘对应。
2. 估计局部位移场，检查是否存在旋转、透视、柱面投影或非刚性 warp。
3. 比较 translation、similarity、homography、cylindrical 的重投影误差。
4. 保存 inlier ratio、transform、canvas bounds、valid mask 和 reference crop 边界。
5. 在删除固定 resize 前先补几何、shape 和 valid-mask 回归。

如果当前依赖不能支持经证实的变换，只允许增加一个最小、离线可用、维护明确的配准依赖；不得先引入大型 CV 栈再寻找用途。

### 12.3 G2：最小几何实现

- 选用 G1 数据支持的最小投影；
- 进行特征匹配、异常值剔除、变换、canvas bounds 和 warp；
- 输出尺寸由 valid mask 和原生 crop 语义推导，不使用输入专属边距或固定比例；
- 空匹配、低 inlier 或退化矩阵必须明确失败或走有证据的稳定 fallback，不能静默 resize。

### 12.4 G3：曝光、seam 与 blending

1. 先对齐重叠区曝光和白平衡。
2. 根据局部误差选择 seam，保护结构线和主体。
3. 先验证 feather；只有 seam ROI 仍不通过且诊断证明收益时才增加 multiband。
4. 分别检查天空、建筑直线、人物和重叠区域。

### 12.5 验证

```bash
.venv/bin/python -m pytest \
  tests/test_panorama_merge.py \
  tests/test_multi_image_validation_data.py -q

.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-round-2.json
```

### 12.6 准出标准

- Panorama shape、MAE、SSIM 使用现有门限全部通过；
- seam ROI 无明显结构断裂；
- HDR、Focus 继续通过；
- 末端不存在固定比例 resize 或冻结输入专用 crop 常量；
- Multi-image `3/3`。

## 13. P7：模型推理与长任务保护

### 13.1 范围边界

当前 required 模型与长任务已通过，本阶段以回归保护为主。只有 P5 诊断证明 model wrapper 的输入/输出或生命周期合同错误，才修改 `ai/model`。

`ai/model` 只负责：

- 本地权重加载；
- preprocess、predict、postprocess；
- 稳定 `InferenceResult`；
- factory 实例化；
- loader 缓存、LRU、unload 和资源释放。

以下不进入 `ai/model`：工具强度、mask 合成、模型选择策略、编辑图顺序、HTTP 编排、任务队列、UI 状态。

### 13.2 模型门禁

- 只从本地权重加载，不在推理路径下载；
- `load_model()` 成功后才设置 loaded；
- 失败不写入缓存，不返回伪成功；
- 相同 task 输出字段兼容且可序列化；
- loader 淘汰、手动清理和全量清理都调用 `unload_model()`；
- candidate invocation 必须记录真实调用，不以“模型存在”替代“模型执行”。

### 13.3 长任务完整结果合同

- 第 N 个模型后 worker 重启，已完成 checkpoint 不重跑；
- lease 续租，旧 worker 不覆盖新 owner、cancel 或 terminal 状态；
- 页面卸载只停止 polling，不取消 server job；
- 刷新或切回项目后恢复正确 latest job；
- terminal 后读取完整 result 和 artifact 后才 merge 项目；
- artifact 路径、hash、project id、job id 不匹配时 fail closed；
- 失败/取消/超时有明确终态，轮询可停止；
- UI 显示的是当前 generation 的进度和结果。

### 13.4 验证

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root .

.venv/bin/python -m pytest \
  tests/test_active_model_contracts.py \
  tests/test_candidate_model_invocations.py \
  tests/test_model_loader.py \
  tests/test_model_outputs.py \
  tests/test_model_source_map.py \
  tests/test_inference_job_repository.py -q

cd frontend
npm test -- useAnalysisJob
cd ..
```

准出：required model、pipeline audit、candidate invocation 和生命周期门禁均通过；长任务跨恢复仍能拿到完整结果；不扩展 optional 66 条作为 required 前置。

## 14. P8：全量门禁、双跑、清理与交付

### 14.1 全量回归顺序

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/run_overlay_e2e_validation.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/validate_ui_references.py \
  --reference-id luminar-neo-macos-1.28.0-23071
.venv/bin/python scripts/validate_interaction_contracts.py
.venv/bin/python scripts/validate_interaction_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071
```

### 14.2 exact 连续双跑

只在所有窄门禁通过后执行第一次：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-2-release-1.json
```

在代码、配置、输入、reference、素材、viewport、build 和环境均不变化的情况下执行第二次：

```bash
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-2-release-2.json
```

比较两轮：gate id/status/case count、main/exact candidate tree hash、UI execution/parity hash、interaction execution hash、模型 source/invocation hash 和 Multi-image 输出 hash。任何 required failure 或非预期漂移都停止交付。

### 14.3 数据清理

先 dry-run：

```bash
.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-round-2-release-dry-run.json
```

只有清单全部属于脚本识别的可重建 workspace、临时文件或重复失败 attempt 时才允许 `--apply`。Canonical capture、native export、reference、当前 candidate、interaction observation、发布报告和用于前后对比的证据不得删除。

执行清理后：

1. 再次 dry-run，要求 path count 与 reclaimable bytes 为 0；
2. 重跑 sampling data-chain；
3. 重跑第二次 exact gate 或等价 post-clean gate；
4. 确认每个效果只保留一个有效、有意义 canonical export；重复和无变化 attempt 不计入 canonical。

### 14.4 最终交付物

- 第二轮 baseline/failure/batch registry；
- 两轮 exact quality gate 及 SHA-256；
- main/exact/UI/interaction/Multi-image 最终报告；
- source/reference/candidate/observation manifest；
- 清理 dry-run、apply 和 postcheck 报告；
- 执行前后对比报告；
- 遗漏审计，明确 required 与 optional；
- 结论只能写“冻结范围内可审计等价”，不能外推到未验证范围。

## 15. 修改入口与验证矩阵

| 目标 | 主要修改入口 | 窄验证 | 保护门禁 |
|---|---|---|---|
| UI capture | `frontend/scripts/`、`scripts/build_ui_browser_execution.py`、UI validators | capture runner tests、shape/build/fixture/hash | 原生 UI reference 只读 |
| Native actions | `scripts/run_luminar_interaction_observations.py`、`scripts/luminar_capture/` | observer/helper tests、单合同 dry-run | 已通过 observation 不覆盖 |
| UI 壳与状态 | `frontend/src/App.tsx`、`frontend/src/components/`、`frontend/src/styles.css` | component tests、build、七状态 comparator | 黑白/降噪/图层/异步行为 |
| Browser interaction | raw evidence、builder、interaction validators | 单合同 trace、builder tests | native observation hash |
| 效果语义 | `image_ops/effects/`、`ai/pipeline/` | capability main/exact/holdout/no-op | Preset/Sky/Overlay/已通过能力 |
| 模型 wrapper | `ai/model/`、`configs/model.yaml` | model validator、invocation、loader tests | 不含业务合成/编排 |
| Panorama | `image_ops/merge/panorama.py`、`services/multi_image/` | geometry tests、workflow smoke | HDR/Focus |
| 长任务 | job repository/worker/checkpoint、`frontend/src/useAnalysisJob.ts` | lease/restart/stale hook tests | 完整 terminal artifact |
| 采样合同 | `scripts/luminar_capture/`、queue runners | record dry-run、effect-change、Reset、data-chain | 禁止全量重采 |
| 发布门禁 | `scripts/run_quality_gates.py`、validators | 两轮 exact | 阈值/reference/hash 不漂移 |
| 数据治理 | `scripts/cleanup_test_data.py`、prune scripts | dry-run/apply/postcheck | canonical 与发布证据保留 |

## 16. 单批次执行模板

每个 UI state、interaction contract、effect capability 或 Panorama 子阶段都按同一闭环执行：

1. **登记**：目标、当前指标、artifact/hash、owner path、保护项。
2. **假设**：只写一个可证伪根因，并说明为何不是 reference 或环境漂移。
3. **窄测试**：选择或新增最小失败测试。
4. **最小实现**：只改根因所在层，不顺手重构邻接模块。
5. **目标生成**：只生成目标 candidate/screenshot/observation，不全量重采。
6. **目标比较**：记录修改前后 MAE/SSIM/changed-pixel/state/API/hash。
7. **同域保护**：跑 anchor、holdout、no-op、已通过同域项。
8. **跨域保护**：按修改范围跑 UI、模型、Sky、Overlay、HDR/Focus 或 interaction 门禁。
9. **稳定性**：目标双跑，检查 hash 和状态不漂移。
10. **决定**：过门禁则锁定；改善但未过则继续 blocked；保护项回退则回滚该最小批次。
11. **记录**：更新 failure/batch registry 和前后对比，不把计划目标写成已完成。

“代码已写完”不等于批次完成；只有目标门禁通过且保护门禁不回退才算完成。

## 17. 停止条件、回退与风险控制

### 17.1 立即停止条件

- 已 ready semantic key 再次进入效果采样队列；
- app build、source、素材、参数 readback、viewport 或 fixture hash 不一致；
- Browser screenshot 不属于当前 frontend build；
- 非中性原生导出无 Reset/恢复证据或相对 source 无变化；
- 黑白未转换、降噪未选择等级就导出；
- 需要放宽阈值、删除 required case、手改 hash、固定 resize/crop 才能通过；
- 单案例改善导致 holdout、已通过能力、Sky、Overlay、HDR/Focus 回退；
- interaction 使用未声明 wait、fixed sleep 或缺少最终 artifact；
- 模型返回 success 但 result/artifact 不完整；
- stale response 覆盖当前项目、preview 或 job；
- 同一根因批次中多数目标同方向恶化。

### 17.2 回退原则

- 只回退当前最小批次，不覆盖用户或其他无关改动；
- canonical、失败截图、observation、trace 和 comparator 报告不随代码回退删除；
- 算法、合同、素材、阈值和 reference 变更必须分开批次；
- 清理只删除脚本明确识别且可重建的数据；
- 不重新引入历史版本兼容逻辑作为回退方案；
- 若两种实现都未过门禁，保留更简单、保护项更稳定、根因更可解释的一种，并保持目标 blocked。

### 17.3 主要风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| UI capture 环境漂移 | 指标不可比较 | 固定 logical viewport/DPR/locale/timezone/font/motion/build/fixture hash |
| 原生 AX 控件无稳定动作 | observation 假通过 | element geometry + down/up + PreviewImage 区域变化 + failure artifacts |
| 效果对单 case 过拟合 | holdout 回退 | 每能力 main/exact/holdout/no-op/已通过保护项 |
| Panorama 依赖过重 | 维护成本和环境风险 | 先诊断投影，只引入一个经证实需要的离线依赖 |
| 模型任务耗时长 | 轮询超时或丢结果 | server job/checkpoint/lease/terminal result，不靠页面长连接 |
| 导出重复或无变化 | 污染 canonical 和磁盘 | 一次请求、effect-change/Reset/hash 门禁、attempt 与 canonical 分离 |
| 文档数字过期 | 错误决策 | 最新 diagnostics 为事实源，计划数字只作入口快照 |

## 18. 最终验收清单

- [ ] 第二轮 baseline 与最终 `21/6/1` 起点一致。
- [ ] 251 条 ready reference 没有全量或重复采样。
- [ ] targeted reobserve 仅限有证据的单条 invalid record。
- [ ] UI capture 使用 logical `1440×900`、DPR 2，输出 `2880×1800`。
- [ ] UI current-build evidence `7/7`。
- [ ] UI parity `7/7`，所有 shape、MAE、changed-pixel 通过。
- [ ] Native interaction `10/10`，issue 0。
- [ ] Browser interaction `10/10`，issue 0，fixed sleep 0。
- [ ] Before/after 是真实按住语义，zoom/pan/fit 只改 view state。
- [ ] 导出只发一个请求、当前页不跳转、文件名/类型/尺寸正确。
- [ ] 黑白必须先转换；降噪必须先选等级；无变化导出不进入 canonical。
- [ ] 主效果 `45/45`。
- [ ] Exact `69/69`，pending/invalid/duplicate 0。
- [ ] Preset、Sky、Overlay 保持通过，Overlay `38/38`。
- [ ] HDR、Focus、Panorama `3/3`。
- [ ] Panorama 没有固定比例 resize 或输入专属 crop。
- [ ] Required 模型、真实 invocation、loader/lifecycle 全通过。
- [ ] 长模型任务跨刷新、切项目、worker 重启仍返回完整 terminal result/artifact。
- [ ] Python、Ruff、frontend test/build 全通过。
- [ ] Cleanup postcheck 为 0，canonical/reference/current evidence 完整。
- [ ] Exact quality gate 连续两轮 required failure 0，关键 hash 稳定。
- [ ] 最终前后对比和遗漏审计已更新，optional 事项未伪装成 required 完成。

本计划受代码规划、UI、模型推理和项目文档规范约束：实现必须小步、可验证、不推测；UI 以原生 reference 为唯一方向；模型层保持纯推理边界；所有计划和结论均映射到真实路径、命令、报告和门禁。
