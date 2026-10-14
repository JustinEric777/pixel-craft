# Luminar Neo 1.28 绝对对齐执行报告（2026-08-26）

> 本文记录 `absolute-parity-optimization-plan-2026-08-26.md` 的实际执行结果、代码改动、真实门禁、前后对比、遗漏审计和下一轮准入顺序。结论仅适用于本机 Luminar Neo `1.28.0 (23071)`、冻结输入/素材和当前项目代码；未通过的门禁保持 blocked。

## 目录

- [1. 执行结论](#1-执行结论)
- [2. 已完成改动](#2-已完成改动)
- [3. 分阶段结果](#3-分阶段结果)
- [4. 执行前后对比](#4-执行前后对比)
- [5. 遗漏审计](#5-遗漏审计)
- [6. 下一步建议](#6-下一步建议)
- [7. 验证记录](#7-验证记录)
- [8. 关键产物](#8-关键产物)

---

## 1. 执行结论

本轮完成了基线冻结、原生交互证据链最小实现、Browser 证据聚合、一个原生/Browser 双端交互闭环、折叠布局修复、导出不跳页与文件名修复、模型/长任务保护性回归和全量门禁审计。

本轮不能标记为“绝对对齐完成”。最终 exact 门禁为：

| 项目 | 结果 |
|---|---:|
| 总门禁 | `21 passed / 6 required failed / 1 optional failed` |
| 主效果 | `36/45` |
| Exact | `38/69`，failed `31`，pending `0` |
| Overlay | `38/38` |
| Multi-image | `2/3` |
| UI parity | `0/7` |
| UI current-build evidence | `0/7`，旧截图 build hash 已失效 |
| Interaction native | `1/10` |
| Interaction Browser | `1/10` |
| Python | `285 passed` |
| Frontend | `13 passed`，production build 通过 |
| 数据链 | `251/251`，issue `0` |
| 清理 | `0 path / 0 byte` |

required 失败项是 `multi-image`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity` 和 `interaction-execution`。`ui-execution-evidence` 是本轮新增的真实阻断：前端代码发生变化后，旧七状态截图不再属于当前 build，validator 正确拒绝复用。

## 2. 已完成改动

### 2.1 基线和失败注册表

新增：

- `scripts/build_convergence_baseline.py`；
- `tests/test_convergence_baseline.py`；
- `diagnostics/convergence-baseline-2026-08-26.json`；
- `diagnostics/convergence-failures-2026-08-26.json`。

基线固定了 28 项门禁、9 个主效果失败、31 个 exact 失败、7 个 UI 失败和 10 个交互缺失。采样队列 `251/251 ready`，没有重新采样已完成效果。

### 2.2 原生交互 observation

新增：

- `scripts/run_luminar_interaction_observations.py`；
- `tests/test_luminar_interaction_observations.py`。

修改：

- `scripts/validate_interaction_execution.py` 增加 `--native-only`；
- 原生 observation 和 Browser screenshot 的路径/hash 校验改为各自受限根目录；
- 最终 Browser screenshot 必须带 SHA-256。

`edit-toggle-collapse` 已生成真实 Luminar 证据并通过。双窗口场景不再依赖“第一个窗口标题”，而是从 AXWindow 标题和 `PreviewImage` 判断冻结图片是否已打开；面板恢复等待同时检查工具列表和画布几何，不使用固定 sleep。

`before-after-compare` 没有生成成功 observation。诊断证明普通 AXPress 只改变按钮区域，整窗归一化 MAE 约 `0.0000197`，没有证明原图实际显示。该控件需要实现 key-down/mouse-down 保持语义，不能把普通点击冒充通过。

### 2.3 Browser 交互证据链

新增：

- `scripts/build_interaction_browser_execution.py`；
- `tests/test_interaction_browser_execution_builder.py`；
- `diagnostics/interaction-browser-raw.json`；
- `diagnostics/interaction-browser-execution.json`；
- `diagnostics/interaction-browser-evidence/edit-toggle-collapse/final.png`。

聚合器只接受：合同 events 完全一致、visible/API assertions 完整、wait 已声明、`fixed_sleep=false`、最终截图存在且 hash 完整、原生 observation 存在且 hash 完整的记录。

### 2.4 折叠布局

`frontend/src/styles.css` 新增 `.workspace-edit-collapsed` 单列网格。修复前，折叠编辑面板后唯一画布子节点被放进 64px 图层列；修复后 Browser 实测：

| 状态 | 画布宽度 | 工具面板 | 图层面板 |
|---|---:|---:|---:|
| 展开前 | `828` | `1` | `1` |
| 折叠后 | `1172` | `0` | `0` |
| 恢复后 | `828` | `1` | `1` |

项目编辑栈在前后均为 `[]`，没有产生 mutation。`frontend/src/App.tsx` 同时把“新导入图片”和“从目录打开图片”的编辑面板初始状态改为打开，与交互合同和原生初始状态一致。

### 2.5 导出卡页和文件名

根因不是后端渲染。导出 API 一直能返回 `200`、`image/png`、`1080×1440` 和 attachment；问题是 `EditorHeader.tsx` 与 `PreviewPanel.tsx` 使用 `target="_blank"`，浏览器会进入独立导出页面。

修复后：

- 两个入口均使用同源 `download` 链接，不再打开新页；
- `api/http/router.py` 根据 `metadata.original_filename` 返回 `<source-stem>-edited.png`；
- 文件名去除路径分隔符和控制字符；
- POST/GET export 使用同一命名规则；
- Browser 实测下载到 `008_e45cd3c34a-edited.png`；已有同名文件时由浏览器自动追加 `(1)`；
- 下载后 URL 仍为 `http://127.0.0.1:5173/`。

`tests/test_api.py` 增加 `Content-Disposition` 回归断言。

### 2.6 模型和长任务

本轮遵守 `ai/model` 边界，没有修改模型 wrapper、注册、加载缓存或推理输出合同。结果：

- 模型模块 validator：0 阻塞；
- required 模型相关测试：`29 passed`；
- lease/repository/checkpoint：`6 passed`；
- `useAnalysisJob`：`5 passed`。

### 2.7 数据清理

Overlay 回归结束后，cleanup dry-run 识别到唯一可重建目录
`diagnostics/overlay-workspace/workspace`，大小 `156,041,498` bytes。已通过
`cleanup_test_data.py --apply` 删除；postcheck 为 `0 path / 0 byte`，随后数据链仍为
`251/251`、issue `0`。Canonical capture、native export、reference 和 current candidate
均未删除。

## 3. 分阶段结果

| 阶段 | 状态 | 真实结论 |
|---|---|---|
| P0 | 完成 | 基线和失败注册表可重建；未触发效果重采 |
| P1 | 部分完成、blocked | runner/validator 完成；native `1/10`，其余 9 条缺失 |
| P2 | 部分完成、blocked | 修复共享折叠几何；当前 build 的七状态证据尚未重采，parity `0/7` |
| P3 | 部分完成、blocked | Browser 聚合器完成；Browser `1/10`，aggregate issue `18` |
| P4 | 审计完成、门禁未关闭 | 主效果 `36/45`、exact `38/69`，没有重复采样或放宽阈值 |
| P5 | 诊断完成、门禁未关闭 | Panorama 仍失败；中心 crop 假设被否定，没有提交退化实现 |
| P6 | 完成 | 模型和长任务保护门禁通过 |
| P7 | 审计完成、发布 blocked | 全量回归通过；exact required failure 仍为 6，不执行发布双跑 |

## 4. 执行前后对比

| 维度 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Exact quality gates | `22 pass / 5 required fail / 1 optional fail` | `21 pass / 6 required fail / 1 optional fail` | 新增的 required fail 是旧 UI evidence 被当前 build hash 正确作废 |
| 主效果 | `36/45` | `36/45` | 无回退，无假提升 |
| Exact | `38/69` | `38/69` | 无回退，pending 仍为 0 |
| Multi-image | `2/3` | `2/3` | Panorama 仍失败 |
| Overlay | `38/38` | `38/38` | 保持 |
| Native interaction | `0/10` | `1/10` | 新增一条真实原生证据 |
| Browser interaction | `0/10` | `1/10` | 新增一条完整 Browser/API/hash 证据 |
| Interaction issues | `22` | `18` | 缺失项减少 4 |
| 折叠画布 | `64px` | `1172px` | 共享布局 bug 已修复 |
| 导出 | 新标签页/卡页，固定名 | 当前页下载，源文件名 `-edited.png` | 真实 Browser 验证通过 |
| Python | `277 passed` | `285 passed` | 新增证据链测试后全通过 |
| Frontend | `13 passed` | `13 passed` + build | 保持 |
| 数据链 | `251/251` | `251/251` | 保持，未重复采样 |
| Cleanup | `0/0` | `0/0` | 无脚本识别的冗余数据 |

## 5. 遗漏审计

### 5.1 必须关闭的遗漏

1. Native interaction 还缺 9 条：`catalog-import-select`、`preset-preview-apply`、`edit-slider-drag`、`layer-add-reorder-opacity-delete`、`undo-redo`、`before-after-compare`、`zoom-pan`、`export-dialog`、`multi-image-workflow`。
2. Browser interaction 对应缺 9 条，aggregate validator 当前 issue `18`。
3. UI 必须基于当前 frontend build 重新采集七状态；旧 screenshot 不得重新登记为 current-build。
4. UI parity 仍是 `0/7`，此前 MAE 约 `0.1091–0.2431`，不是微小 token 差异。
5. 主效果还缺 9 个，exact 还缺 31 个；算法失败不能通过重采 reference 解决。
6. Panorama 仍使用最终测量比例 resize。诊断中原始 `1080×1440` 的中心 crop 到 `1070×1410` 得到 `MAE 0.08908 / SSIM 0.78450`，差于当前 resize 的 `0.08194 / 0.81554`，因此没有提交中心 crop。
7. 当前 exact required failure 为 6，未达到发布双跑前置条件。

### 5.2 非遗漏

- 已采样的 251 条记录没有重复进入队列；
- exact pending 为 0；
- cleanup dry-run 为 `0 path / 0 byte`；
- 黑白转换和降噪等级既有实现没有回退；
- Overlay `38/38` 没有回退；
- required 模型和长任务没有回退。

## 6. 下一步建议

### 6.1 第一优先级：完成原生交互状态机

按以下顺序逐条 dry-run、单条实机执行、native-only 验证：

1. `before-after-compare`：给 native helper 增加 mouse-down/mouse-up 或按键按下/释放动作，按住期间保存 source screenshot，释放后验证 edited screenshot 恢复；
2. `zoom-pan`：读取原生 zoom button 标题，滚轮后验证百分比变化、pan 后验证 PreviewImage 几何、fit 后恢复；
3. `edit-slider-drag`：使用 `EditExpandButton_DetailsEnhancerAdjustmentLayer` 和可读 slider value；
4. `undo-redo`：先建立一条确定性编辑，再验证同一编辑 id/参数恢复；
5. import、preset、layer、export、multi-image：每条使用独立 fixture/project，完成后清理项目写入。

准出命令：

```bash
.venv/bin/python scripts/validate_interaction_execution.py --native-only
```

要求 `10/10`、issue `0` 后再扩 Browser 记录。

### 6.2 第二优先级：修正 UI capture viewport 合同

原生 `2880×1800` 是 `1440×900` logical viewport 的 Retina 输出。下一轮必须先证明 candidate capture 使用一致的 logical viewport 和 device scale，再做像素调优。当前 in-app Browser 会话不提供 viewport override，因此不能用当前 `1280×720` 截图替代冻结证据。

需要新增或恢复一个可审计的 current-build capture 入口，要求：

- logical viewport `1440×900`；
- device scale factor `2`；
- 输出 shape `2880×1800`；
- locale `zh-Hans`、timezone `Asia/Shanghai`；
- motion 关闭；
- 每个状态记录 frontend build hash、fixture hash 和 screenshot hash。

完成后先重采七张 candidate，不重采原生 reference，再运行：

```bash
.venv/bin/python scripts/validate_ui_execution_evidence.py
.venv/bin/python scripts/validate_ui_references.py
```

### 6.3 第三优先级：效果失败按共享根因收敛

不重采已有 valid reference。先做 `face_ai` 和 `lut_mapping` 两个低误差能力，分别验证 mask/ROI 边界与颜色空间/LUT 插值；每次只 force 单能力 candidate，并同时跑 exact anchor、holdout 和中性项。随后再进入 Denoise/Grain、人物深度、天空光照和组合效果。

### 6.4 第四优先级：Panorama 投影诊断

不要把当前 resize 换成固定 crop。下一轮应先保存输入到 reference 的特征对应、局部位移场和有效边界，证明是柱面投影、homography 还是局部 warp，再实现最小变换和 mask-derived auto-crop。只有 geometry 通过后才调整 seam、曝光和 multiband blending。

### 6.5 最终发布顺序

只有 native `10/10`、Browser `10/10`、UI `7/7`、主效果 `45/45`、exact `69/69`、Multi-image `3/3` 同时达到后，才执行两轮 exact quality gate。两轮之间不得修改代码、配置、输入、reference、素材、viewport 或环境。

## 7. 验证记录

本轮实际通过：

```text
Python full suite: 285 passed
Ruff: all checks passed
Frontend: 13 passed
Frontend production build: passed
API focused suite: 26 passed
Interaction focused suite: 11 passed
Model focused suite: 29 passed
Long-task/lease/checkpoint: 6 passed
useAnalysisJob: 5 passed
Sampling data chain: 251/251, issue 0
Sampling queue captures: 251/251 ready
Overlay: 38/38
Cleanup dry-run: 0 path / 0 byte
```

保持 blocked：

```text
Main output parity: 36/45
Exact incremental parity: 38/69
Multi-image: 2/3
UI current-build evidence: 0/7
UI parity: 0/7
Interaction execution: 1/10, issue 18
Exact quality gates: 21 passed / 6 required failed / 1 optional failed
```

## 8. 关键产物

- 计划：`docs/parity/absolute-parity-optimization-plan-2026-08-26.md`；
- 最终门禁：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-after-2026-08-26.json`；
- 主效果：`diagnostics/parity-report-after-2026-08-26.json`；
- exact：`diagnostics/parity-exact-after-2026-08-26.json`；
- Multi-image：`diagnostics/multi-image-after-2026-08-26.json`；
- Overlay：`diagnostics/overlay-after-2026-08-26.json`；
- Native interaction：`observations/interactions/edit-toggle-collapse/observation.json`；
- Browser interaction：`diagnostics/interaction-browser-execution.json`；
- Interaction 审计：`diagnostics/interaction-execution-after-2026-08-26.json`；
- Cleanup：`diagnostics/cleanup-after-2026-08-26-dry-run.json`。

项目文档规范影响了本报告的写法：所有完成/阻塞结论均对应真实路径、命令和门禁，不把计划目标写成已完成事实。
