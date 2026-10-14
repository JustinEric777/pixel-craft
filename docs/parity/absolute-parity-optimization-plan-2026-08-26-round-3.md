# Luminar Neo 1.28 UI、交互、效果绝对对齐可执行收敛计划（第三轮，2026-08-26）

> 本计划基于 `docs/luminar-parity-execution-report-2026-08-26-round-2.md`、两次
> `quality-gates-current-round-*.json` 和当前代码制定。目标不是继续堆功能，而是在冻结、合法、
> 可重复的合同内关闭现存差异。活动目标固定为本机 Luminar Neo `1.28.0 (23071)`、macOS、
> `zh-Hans`。已有可信采样不重复执行；不增加 1.25/1.26 或旧数据格式兼容逻辑。

## 目录

- [1. 当前结论](#1-当前结论)
- [2. “绝对对齐”的范围与声明规则](#2-绝对对齐的范围与声明规则)
- [3. 最新基线与最终验收标准](#3-最新基线与最终验收标准)
- [4. 硬性执行原则](#4-硬性执行原则)
- [5. 目标数据链与阶段依赖](#5-目标数据链与阶段依赖)
- [6. P0：冻结第三轮合同并恢复原生采集环境](#6-p0冻结第三轮合同并恢复原生采集环境)
- [7. P1：UI 优先收敛](#7-p1ui-优先收敛)
- [8. P2：原生与 Browser 交互合同收敛](#8-p2原生与-browser-交互合同收敛)
- [9. P3：只修复 10 条无变化采样](#9-p3只修复-10-条无变化采样)
- [10. P4：效果与 Exact 像素收敛](#10-p4效果与-exact-像素收敛)
- [11. P5：Panorama 收敛](#11-p5panorama-收敛)
- [12. P6：模型推理与长任务完整结果](#12-p6模型推理与长任务完整结果)
- [13. P7：数据整理、双跑和发布](#13-p7数据整理双跑和发布)
- [14. 修改入口与验证矩阵](#14-修改入口与验证矩阵)
- [15. 单批次执行模板](#15-单批次执行模板)
- [16. 风险、停止条件和回退](#16-风险停止条件和回退)
- [17. 完整执行清单](#17-完整执行清单)

---

## 1. 当前结论

当前项目已经具备完整的采样、候选生成、模型调用审计、UI 当前构建证据、交互合同、差异比较和
Exact 门禁骨架，但仍不能声明与 Luminar Neo 绝对对齐。最新两轮 Exact 结果一致：28 项中
22 项通过、5 个 required 门禁失败、1 个 optional 门禁失败。

5 个 required 阻断项固定为：

1. `multi-image`；
2. `output-parity`；
3. `exact-incremental-parity`；
4. `ui-parity`；
5. `interaction-execution`。

这意味着下一轮不应再横向增加面板或抽象层，而应关闭以下真实差异：

- UI 当前构建证据为 `7/7`，但像素对齐为 `0/7`；
- Native interaction 为 `8/10`，正式 Browser execution 为 `1/10`；
- 主效果为 `36/45`，Exact 为 `38/69`；
- 多图为 `2/3`，Panorama 仍失败；
- 251 条采样中仍有 10 条历史导出被判为 `invalid-unchanged-export`；
- 实际激活的模型调用和模型合同已通过，但完整模型库存仍有 66 条 optional pending；
- UI 的编辑、更多、信息面板已可用，但帮助、升级和生成式服务没有完整业务闭环；
- 现有 7 状态矩阵没有覆盖新面板、黑白转换前后、降噪等级、导出和多图完成态，不能代表完整 UI。

## 2. “绝对对齐”的范围与声明规则

### 2.1 三层范围

| 层级 | 范围 | 本轮要求 | 允许的最终声明 |
|---|---|---|---|
| A：本地核心 | 目录、预设、编辑、图层、本地效果、本地模型、多图、导出 | required，必须全部通过 | “冻结的本地核心合同绝对对齐” |
| B：受限入口 | 付费内容、升级、账号、当前不可用功能的锁定/提示 | required 对齐可见状态、点击结果和错误语义 | “受限入口状态对齐” |
| C：外部服务 | 生成式擦除/替换/扩展等依赖 Skylum 账号或云服务的真实输出 | 有合法凭据和接口才可 required；否则 blocked | 未验证前禁止声称全产品绝对对齐 |

“绝对对齐”必须附带 target manifest，不代表所有未知输入、未来版本、未安装商业内容或第三方服务的
数学全等。若用户要求包含 C 层，必须先取得合法授权、账号、网络契约和可重复测试条件；不能用本地假实现、
静态截图或 Windows 1.27 素材替代。

### 2.2 冻结合同

| 维度 | 冻结值 |
|---|---|
| 原生应用 | Luminar Neo `1.28.0 (23071)` |
| Bundle / 平台 | 当前活动 reference profile / macOS |
| 语言 / 时区 | `zh-Hans` / `Asia/Shanghai` |
| UI | logical `1440×900`、DPR 2、physical `2880×1800`、固定字体/主题/motion |
| 输入 | `test_data/parity/inputs/` 和 `test_data/multi_image/` 的 SHA-256 冻结输入 |
| 原生 reference | `test_data/parity/references/luminar-1.28.0-23071/` 与活动 captures |
| 阈值 | `configs/parity.yaml` 当前门限，不放宽、不加 case 特例 |
| 交互 | `configs/parity/interaction-contracts.json` 的状态转换和断言 |
| 素材 | provenance 已确认、目标版本匹配、许可允许的本地素材 |

### 2.3 明确不做

- 不增加 1.25/1.26、旧 schema、旧 payload、旧路径或旧视觉的运行时兼容分支。
- 不重复采样 241 条未被 effect-change audit 判为无效的记录。
- 不修改 reference、阈值、输入、case 或 comparator 来制造通过。
- 不对 case id、图片 hash、固定输出尺寸或单张截图写运行时特例。
- 不把 API `200`、按钮可点击、单元测试通过或“肉眼相似”当作 parity 通过。
- 不按重复 hash 直接删除 canonical 证据；不同文件可能承担不同审计角色。
- 不把 66 条当前产品路径未调用的 optional 模型合同放到 required 关键路径。
- 不直接复制 `/Users/iknow/Downloads/LuminarNeo-1.28.0.17626-x64-Portable` 的商业素材。该目录实际为
  Windows `1.27.1.17225`，版本不匹配且 619 项仍待授权确认。

## 3. 最新基线与最终验收标准

### 3.1 最新真实基线

| 域 | 当前 | 本轮最低准出 |
|---|---:|---:|
| Exact quality gates | `22/28`；required failed `5`；optional failed `1` | 两轮 required failed `0` |
| 主效果 | `36/45` | `45/45` |
| Exact | `38/69`，pending `0` | `69/69` |
| Multi-image | `2/3` | `3/3` |
| UI current-build evidence | `7/7` | 扩展矩阵全部 current-build |
| 现有 UI pixel parity | `0/7` | 扩展矩阵全部通过 |
| Native interaction | `8/10` | `10/10` |
| Browser interaction | `1/10` | `10/10` |
| 活动模型调用 | `22/22`；活动合同 `16/16` | 保持且长任务结果完整 |
| 采样数据链 | `251/251 ready`，issue `0` | 保持；无无效 canonical |
| 无变化历史导出 | `10` | `0` |
| Python / frontend | `291` / `19` passed | 不回退，新增窄测试通过 |
| 清理 postcheck | `0 path / 0 byte` | 每阶段完成后保持 |

### 3.2 UI 状态矩阵扩展

当前 7 个状态继续保留，但绝对 UI 对齐至少增加下列关键状态。最终 required 集合建议为 16 个：

| 类别 | 状态 | 需要证明 |
|---|---|---|
| 原有 | catalog、presets、edit、layer-stack、layer-library、tool-expanded、multi-image-empty | 保持当前合同 |
| 新增 | edits-panel | 历史列表、删除入口、空态与原生一致 |
| 新增 | more-panel | 生成式/增强/合并分组、锁定状态、图标、间距一致 |
| 新增 | info-panel | 文件、尺寸、元数据缺省展示一致，不虚构 EXIF |
| 新增 | editor-collapsed | 折叠后画布、rail、恢复状态一致 |
| 新增 | bw-before-convert | 亮度/饱和度/应用为原生禁用状态 |
| 新增 | bw-after-convert | 转换完成后控件启用和默认值一致 |
| 新增 | denoise-level-selected | 明确等级选中后强度控件和 busy 状态一致 |
| 新增 | export-dialog | 文件名、格式、保存位置、取消/确认状态一致 |
| 新增 | multi-image-ready | 全部帧、预览完成、导出可用状态一致 |

若原生 1.28 的可达 UI 还存在必需状态，只允许通过一次 target-manifest revision 增加；不能在实现阶段随意
删减状态。新增状态在获取可信原生截图之前保持 `pending`，不得用本项目截图自举 reference。

### 3.3 最终 release gate

只有以下条件同时成立才可声明完成：

1. target manifest、输入、reference、素材、阈值、视口和环境 hash 冻结；
2. 251 条数据链全部有效，10 条无变化记录已经被有效新 canonical 替代；
3. 主效果 `45/45`、Exact `69/69`、Multi-image `3/3`；
4. UI 扩展矩阵全部 current-build evidence 且全部像素门禁通过；
5. Native `10/10`、Browser `10/10`，issue `0`，无固定 sleep；
6. 本地模型真实 invocation、活动模型合同、资源释放和长任务 terminal result 全部通过；
7. Python、Ruff、frontend test/build 全通过；
8. 同一代码、配置、输入、reference、素材和环境下 Exact 门禁连续两次 required failure 为 0；
9. 两次运行之间不允许修改任何参与结果的文件；候选和证据 hash 稳定；
10. C 层外部服务若未验证，最终报告必须明确写为 blocked，不能使用“全产品绝对对齐”。

## 4. 硬性执行原则

### 4.1 真值优先级

1. 同 build、同 fixture 的 Luminar preview/export、UI screenshot、AX 和 observation；
2. 原生 control id、value/range/readback、素材 id/path/hash 和导出 metadata；
3. 本项目同一 build hash 的 Browser trace、API/project state 和 candidate；
4. 自动 comparator、effect-change audit 和 quality gate；
5. 人工观察只用于提出根因假设，不直接判定通过。

### 4.2 每次输入必须恢复原始状态

所有效果、预设、图层和导出采样都必须执行统一前置合同：

```text
定位目标图片
  -> 检查 source hash
  -> 恢复原图/删除全部编辑
  -> 验证 edit stack 为空且 preview 与 source 一致
  -> 选择目标工具或素材
  -> 等待效果/模型完成
  -> readback 参数与状态
  -> 验证 preview 发生预期变化
  -> 导出到唯一 attempt 路径
  -> 验证文件稳定、可解码、效果存在
  -> 成功后原子发布 canonical
```

如果原生界面没有“恢复图片原始状态”能力，或恢复后 source hash/preview 不一致，该 attempt 立即失败。
不能继续调参或导出。

### 4.3 只选择需要重做的记录

记录只有在以下任一条件成立时才进入 pending worklist：

- `invalid-unchanged-export`、failed 或 artifact/hash 损坏；
- app build、fixture、recipe、contract 或素材 hash 改变；
- 原生参数 readback 与合同不一致；
- preview/export 不一致；
- 非中性效果没有 Reset/恢复原图证据；
- 新增 required semantic key。

`ready` 且合同 hash 未变化的记录禁止排队。每个实机批次只执行一个 `record-id`；失败时先分析证据，
不得自动扫完剩余记录。

### 4.4 一批只解决一个根因

每个批次必须有：目标 case/state/contract、修改前指标、一个可证伪假设、最小修改、窄测试、目标验证、
同域 holdout/anchor 回归、修改后指标和继续/回退决定。只有逻辑第二次真实重复时才提取共享抽象。

### 4.5 Fail closed

缺少截图、AX、事件 trace、参数 readback、preview、export、文件 hash、模型结果、完整 terminal result 或
reference provenance 时必须保持 blocked。失败 attempt 不覆盖已通过 canonical。

## 5. 目标数据链与阶段依赖

### 5.1 单一数据链

```text
target manifest + frozen input + native reference
                    │
                    ▼
          active contract / active cohort
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
     UI/interaction       effect/workflow
     current evidence     candidate/model trace
          │                    │
          └─────────┬──────────┘
                    ▼
             comparator / audit
                    │
                    ▼
              exact quality gate
                    │
                    ▼
          archive manifest + release report
```

运行时代码不得读取历史 parity 报告、失败注册表或原生输出 hash 来选择算法；这些产物只参与开发期诊断。

### 5.2 推荐顺序

| 阶段 | 目标 | 前置 | 准出 |
|---|---|---|---|
| P0 | 冻结合同、恢复原生窗口与权限 | 当前代码可运行 | preflight 通过，第三轮 baseline 落盘 |
| P1 | UI 数据、素材、结构、像素 | P0 | 扩展 UI matrix 全 current-build 且全通过 |
| P2 | Native/Browser 交互 | P1 结构稳定 | `10/10 + 10/10` |
| P3 | 定向修复 10 条无变化记录 | P0 原生可控 | invalid `0`，其他 241 条不变 |
| P4 | 主效果与 Exact | 对应 reference 可信 | `45/45 + 69/69` |
| P5 | Panorama | P0 多图 reference 可信 | `3/3` |
| P6 | 模型与长任务 | P4/P5 触发的活动模型明确 | invocation、contract、terminal result 完整 |
| P7 | 清理、双跑、发布 | P1-P6 | required 连续两轮零失败 |

P3、P4、P5 可在 P1/P2 的独立代码边界上交错推进，但每个批次仍须单独验证和记录，不能把多个域混成
一次大改。

## 6. P0：冻结第三轮合同并恢复原生采集环境

### 6.1 目标

把 `22/5/1`、当前 build、当前输入和当前 reference 固定为唯一入口，并让本机 Luminar Neo 真正具备
可见窗口、AX、截图和前台控制能力。只检测到后台进程不算通过。

### 6.2 工作项

1. 创建第三轮 baseline manifest，记录两轮 gate 文件 hash、app version/build/bundle、代码 fingerprint、
   UI build hash、Python/Node/Browser 版本、viewport/DPR/locale/timezone/font/motion、输入/reference/素材/
   配置 hash。
2. 创建 failure registry，逐项登记：5 个 required gate、7 个现有 UI 状态、16 个目标 UI 状态、
   2 个 native 缺失、9 个 Browser execution 缺失、9 个主效果、31 个 Exact case、Panorama 和 10 条
   invalid record。
3. 在系统设置确认 Luminar Neo 与执行 Python/Codex 的辅助功能、屏幕录制权限；手动打开 Luminar 的目录页，
   确认不是只有后台进程。
4. 运行采样 `--preflight`，要求得到窗口 bounds、app build、前台 screenshot 和 AX tree。
5. preflight 未通过时只修环境，不执行任何效果、交互或导出采样。
6. 检查 `test_data` 顶层仍只有 `multi_image`、`outputs`、`parity`、`夏日户外拍照`，outputs 根无散图，
   `test_data/luminar_1_26` 不存在。

### 6.3 验证命令

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --preflight --dry-run

.venv/bin/python scripts/validate_sampling_queue_captures.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/cleanup_test_data.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/cleanup-round-3-p0-dry-run.json
```

### 6.4 准出标准

- baseline 能准确重建 `22 passed / 5 required failed / 1 optional failed`；
- Luminar window bounds、AX、screenshot、版本和 bundle 全部存在；
- 251/251 数据链 ready，issue 0；
- reference、输入、素材和门限未变化；
- cleanup dry-run 为 0；
- 241 条非目标记录没有进入 pending worklist。

## 7. P1：UI 优先收敛

### 7.1 P1-A：先对齐数据模型，不先调 CSS

catalog MAE `0.168233`、changed ratio `0.769718`，presets MAE `0.099465`、changed ratio
`0.507364`。这是信息架构和数据密度差异，不是一个颜色 token 能解决。

#### Catalog

在现有项目/目录接口上补齐活动 1.28 所需的最小字段：

- folder/album/collection identity；
- relative path 与 source hash；
- imported at 与稳定排序键；
- selected record、filmstrip order、thumbnail aspect/status；
- recently edited/added 等原生可见分组，仅实现 reference 中真实出现的分组。

修改入口优先为 `core/`、`services/`、`api/` 的现有 catalog/project 路径，以及
`frontend/src/components/CatalogWorkspace.tsx`。不新建第二套前端假数据模型。

#### Presets

将当前扁平列表整理为原生 1.28 reference 中出现的推荐、基本功能、购买/锁定、新品等真实分组；免费预设
继续读取真实 preview/API，购买项只对齐锁定态和点击语义，不放静态假效果图。修改入口为现有 preset 服务、
`frontend/src/components/PresetBrowser.tsx` 和相关 API 类型。

验收：结构、顺序、选中态和数据数量与冻结 reference 一致后，才进入几何和像素调整。

### 7.2 P1-B：素材与图标 provenance

1. 盘点目标 macOS 1.28 App 自身可合法读取的图标、缩略图、LUT、Sky、Overlay 元数据，只记录路径、hash、
   尺寸、版本和许可状态。
2. 复用已有 `assets/manifest.json`、素材 API 和代码内 SVG 图标体系；能由稳定 SVG 表达的 UI 图标继续使用
   `frontend/src/components/Icon.tsx`，不要把字符或文字占位当图标。
3. Windows 1.27 Portable 只用于只读 hash/结构对照；版本不匹配或授权未知的文件不进入 production assets。
4. 若原生像素必须依赖未授权商业位图，该 UI state 保持 `blocked-by-asset-license`，不能用近似素材后声明通过。
5. 对 Help/Upgrade 明确产品行为：至少实现与原生一致的本地说明/许可状态/外链确认或 unavailable 状态；按钮不能
   无响应。实际购买和账号流程属于外部服务范围。

### 7.3 P1-C：共享壳层和组件状态

按差异热力图顺序修改，不按截图逐个打补丁：

1. 顶栏高度、工作区列宽、右 rail 宽度、底部 filmstrip、高度和 canvas fit；
2. 字体 family/size/weight/line-height、图标 bounding box 和按钮 hit area；
3. panel heading、分组间距、列表密度、border/radius/shadow；
4. selected/hover/disabled/busy/locked/error/empty 状态；
5. 图片 fit、thumbnail crop、滚动位置和动画关闭；
6. 最后处理颜色、透明度和 1px 细节。

主要修改入口：

- `frontend/src/App.tsx`：workspace/panel 状态，不承载视觉常量；
- `frontend/src/components/EditorHeader.tsx`、`WorkspaceRail.tsx`：共享 shell；
- `CatalogWorkspace.tsx`、`PresetBrowser.tsx`、`ToolPanel.tsx`、`LayersPanel.tsx`；
- `EditHistoryPanel.tsx`、`MorePanel.tsx`、`InfoPanel.tsx`、`WorkflowWorkspace.tsx`；
- `frontend/src/styles.css`：共享 token 和布局，删除被新规则完全覆盖的重复声明时必须有截图回归证明。

### 7.4 P1-D：扩展 UI reference/evidence 合同

1. 在 `configs/parity.yaml` 和 `docs/parity/ui-state-matrix.md` 中登记 16 个 required 状态。
2. 对新增状态先从原生 1.28 获取 reference、AX、fixture hash 和环境元数据；每个状态只采一次可信 canonical。
3. 用当前 frontend build 生成对应 candidate，记录 build hash、fixture hash、screenshot hash 和 physical shape。
4. 所有状态必须 `shape_match`、`MAE <= 0.03`、changed pixel ratio `<= 0.02`。
5. 先跑单状态 comparator；同一共享组件影响的已有通过状态全部回归。

验证入口：

```bash
cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-round-3.json

.venv/bin/python scripts/validate_ui_references.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-round-3.json
```

### 7.5 P1 批次顺序与准出

推荐顺序：catalog → presets → edit shared shell → layer states → tool/B&W/denoise → edits/more/info → export →
multi-image empty/ready。

准出：16 个状态全部属于当前 build 和同一 frozen fixture，像素门禁全部通过；console/network issue 0；
Help/Upgrade/locked entries 不再是无行为按钮；没有复制未授权或错误版本素材。

## 8. P2：原生与 Browser 交互合同收敛

### 8.1 原生剩余 2 条

只执行当前缺失的：

1. `layer-add-reorder-opacity-delete`；
2. `multi-image-workflow`。

每条先 dry-run，确认 fixture、目标 AX、输出目录和事件序列；真实执行后立即验证 observation、before/after、
AX snapshot、事件 trace 和 SHA-256。已有 8 条不重跑，除非合同或 app build 改变。

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --contract-id <contract-id> --dry-run

.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --contract-id <contract-id> --allow-ui-control

.venv/bin/python scripts/validate_interaction_execution.py \
  --reference-id luminar-neo-macos-1.28.0-23071 --native-only \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-round-3.json
```

### 8.2 Browser 剩余 9 条

当前正式 execution 只有 `edit-toggle-collapse`。其余 9 条必须由现有合同驱动并生成 raw trace：

- `catalog-import-select`；
- `preset-preview-apply`；
- `edit-slider-drag`；
- `layer-add-reorder-opacity-delete`；
- `undo-redo`；
- `before-after-compare`；
- `zoom-pan`；
- `export-dialog`；
- `multi-image-workflow`。

临时人工 DOM 验证不能转记为合同通过。每条必须包含 events、visible assertions、API assertions、allowed waits、
final screenshot、console/network 和 project/workflow JSON。失败时保留 failure artifact，但不覆盖 canonical execution。

### 8.3 交互关键语义

| 合同 | 必须证明的状态转换 |
|---|---|
| Catalog | 记录不重复导入，选中后 project source hash 正确并进入编辑 |
| Preset | preview 不写 edit；Apply 只写一次；busy 清除；编辑顺序一致 |
| Slider | readback 与 API 参数一致；preview 完成；只创建一条目标 edit |
| Layer | 添加、置顶、opacity 50%、删除每一步均可见且持久化 |
| Undo/redo | 撤销移除目标 edit，重做恢复同一语义参数，不制造重复 edit |
| Compare | source/edited 真正切换，项目无 mutation；原生若为 press-and-hold，Browser 行为也必须一致 |
| Zoom/pan | 只改 view state；fit 后恢复；项目无 edit mutation |
| Export | 文件名回读正确；取消不落文件；确认只创建一个文件并退出导出态 |
| Multi-image | 全部 frame hash 落盘；ready 前不可导出；terminal result/hash 完整 |

### 8.4 导出卡页与重命名专项

将导出等待拆分并分别记录 `opened_at`、`filename_readback_at`、`confirmed_at`、`file_created_at`、
`file_stable_at`、`decoded_at`、`canonical_published_at`。优化规则：

- 每个 attempt 使用唯一 stem 和 staging path，避免覆盖/替换确认框；
- fill 后必须 readback 完整文件名，不能只发送按键；
- 点击确认后等待“面板关闭或完成状态 + 目标文件出现”，不是固定 sleep；
- 文件 size/mtime 连续稳定并可解码后才发布 canonical；
- 若仍停在导出页，保存 screenshot、AX、focus、目标路径和阶段耗时后取消并结束 attempt；
- 不在同一状态重复点击确认，不自动覆盖已有文件；
- 性能只在本来需要执行的 pending case 上测量，不重跑 ready case。

### 8.5 P2 准出

- Native `10/10`，Browser `10/10`，issue 0；
- 合同 events 和断言完整，`fixed_sleep=false`；
- B&W、denoise、export 和 multi-image 状态机全部有正式 trace；
- 当前已通过的 UI 状态和项目数据不回退。

## 9. P3：只修复 10 条无变化采样

### 9.1 唯一允许重做的记录

| 能力 | 记录数 | 必须修正的前置交互 |
|---|---:|---|
| `denoise` | 2 | 恢复原图后选择明确 Low/Mid/High 等级，再调目标强度 |
| `bw_channels` | 2 | 先点击“转换为黑白”，确认控件启用，再调亮度/饱和度 |
| `denoise_laplacian` | 1 | 核对真实工具/主控件和非中性值，不复用错误 Denoise locator |
| `magic_lights` | 1 | 等待灯光检测完成并确认目标输入存在有效灯源 |
| `lut_mapping` | 1 | 核对 LUT asset hash、Amount 和 preview readback |
| `new_neon_light` | 1 | 完成放置/绘制/Apply 状态，不只打开面板 |
| `skin_smooth` | 1 | 等待人脸分析与 slider enabled，确认皮肤 ROI 变化 |
| `slim_people` | 1 | 使用合同内合适全身 fixture，确认人体检测和局部形变 |

### 9.2 单条流程

1. 从 audit 读取一个 record id；
2. `--dry-run --record-id ... --limit 1`，确认只选中该条；
3. 打开原图并执行恢复原始状态合同；
4. 按能力执行 B&W conversion、denoise level、模型完成或 Apply 等前置步骤；
5. 参数 readback；
6. preview 变化门禁通过；
7. 导出到唯一 attempt path；
8. 文件稳定、可解码、source/export 变化和 preview/export 一致性通过；
9. 导出后原生仍能恢复原图；
10. 新 attempt 通过全部检查后才更新 canonical pointer；旧 attempt 进入归档，不原地覆盖。

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-pending.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --dry-run

.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --queue test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-pending.json \
  --record-id <record-id> --resume --retry-failed --limit 1 --allow-ui-control

.venv/bin/python scripts/audit_sampling_effect_changes.py \
  --reference-id luminar-neo-macos-1.28.0-23071
```

### 9.3 停止条件与准出

同一能力连续两次出现 unchanged、错误控件、错误素材、无 Reset、preview/export 不一致或导出卡页时，停止该
能力并修 recipe/fixture，不继续点击或换 record。准出要求 invalid 数为 0，251 条 active canonical 均有效，
其余 241 条 hash/mtime 不变。

## 10. P4：效果与 Exact 像素收敛

### 10.1 先验证真值，再修改算法

10 条 invalid reference 中包含 `slim_people`、`lut_mapping` 等主效果失败能力，也包含多个 Exact 失败能力。
P3 未给对应 record 建立可信 reference 前，不允许拟合这些 case。可信 reference 只读；算法失败不是重采理由。

### 10.2 主效果 9 项分组

| 批次 | 能力 | 当前线索 | 首要检查 |
|---|---|---|---|
| E1 | `lut_mapping` | MAE `0.035247`，SSIM 很高 | LUT 颜色空间、插值、强度混合、asset hash |
| E2 | `face_ai`、`slim_people` | ROI/几何差异 | 模型输出坐标、mask resize、landmarks、局部 warp |
| E3 | `depth_volume`、`fog`、`blue_hour` | 深度/天空区域差异大 | depth 方向/范围、resize、mask feather、合成顺序 |
| E4 | `sky_replace`、`sunrays`×2 | 素材、位置、光照和边缘 | sky mask、horizon、asset crop、光源坐标、色彩匹配 |

主要入口为 `ai/pipeline/image_effect_pipelines.py` 和已有共享 image operations。模型 wrapper 只在输入输出合同确实
错误时修改；业务强度、mask 合成和效果顺序不写入 `ai/model`。

### 10.3 Exact 31 项按根因处理

不要逐 case 调常数。建议分为：

- 颜色/全局 tone：high_key、pro_contrast、color_toning、color_adjustments、color_enhancer、radiance、fade、
  landscape_enhancer、default_effects、ai_enhance；
- 随机/纹理：grain；
- 人像/几何：face_enhancer、face_ai、bokeh_ai、slim_people；
- 深度/天空/光照：depth_volume、blue_hour、fog、sunrays；
- 局部 AI/工具：structure_ai、denoise、denoise_laplacian、magic_lights、new_neon_light；
- 几何遮罩：vignette。

每个能力用同一流程：

1. 对 source/native/candidate 生成 RGB/Luma MAE、SSIM、shape、区域统计、边缘/梯度和 heatmap；
2. 分类为 color-management、tone curve、mask、geometry、asset、position、random statistics 或 sampling error；
3. 写一个能复现共享根因的窄测试；
4. 只修改一个 pipeline/helper/contract；
5. 只重生成目标 candidate；
6. 跑目标 case、同能力其他 anchor、holdout、中性输入和已通过同域能力；
7. 记录 before/after 指标和双跑 hash；
8. 指标回退或只对单张 reference 有效时立即回退该批次。

`grain` 必须使用配置中的 statistical comparator，不追求随机像素逐点相等；其他能力继续使用当前 shape/MAE/SSIM
合同。不能为了关闭 31 条而修改门限。

### 10.4 验证入口

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-<capability-id>-round-3.json
```

### 10.5 P4 准出

主效果 `45/45`，Exact `69/69`，pending 0；reference hash 未改；每个修复有 holdout/anchor；活动模型 invocation
仍真实发生；不出现 case/hash 特例。

## 11. P5：Panorama 收敛

### 11.1 当前差异

Panorama shape 已一致为 `1070×1410`，但 MAE `0.0819413`、SSIM `0.815541`。这说明问题不再是简单输出
尺寸，而是几何映射、有效边界、seam、曝光或裁切策略。

### 11.2 实施顺序

修改入口为 `image_ops/merge/panorama.py`，服务调用保持在 `services/multi_image/service.py`：

1. 保存每对 frame 的特征/相关性候选和匹配置信度；
2. 估计并记录局部位移/变换，而不是继续使用固定 offset/crop；
3. 对比 translation、affine、homography/圆柱投影假设，选择能解释 reference 的最小模型；
4. 先对齐 warp 和有效边界，再确定原生裁切矩形；
5. 最后处理 exposure compensation、seam path 和 feather/multiband blending；
6. 加入反序、重叠变化、亮度变化和无足够重叠的窄测试；
7. 确保失败输入返回可诊断错误，不输出伪成功图。

不得直接写固定 `1070×1410` crop 或针对当前三帧 hash 的位移常数。

```bash
.venv/bin/pytest -q tests/test_panorama_merge.py tests/test_workflows.py

.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-round-3.json
```

准出：HDR、Focus、Panorama `3/3`；Panorama shape/MAE/SSIM 全部通过；HDR/Focus 指标不回退；相同输入
双跑 hash 稳定。

## 12. P6：模型推理与长任务完整结果

### 12.1 边界

活动模型当前已通过 `22/22` invocation 和 `16/16` model-specific contract。本阶段只保护实际产品路径，
不为了 optional inventory 扩建 66 个未调用 wrapper。

`ai/model` 只负责：注册、动态实例化、离线本地加载、preprocess、predict、postprocess、稳定
`InferenceResult` 和资源释放。页面状态、任务编排、工具参数、mask 合成、重试和导出不进入该目录。

### 12.2 长任务完整结果合同

每个模型/多图长任务必须持久化：

- job id、project id、requested models/capability、input hash；
- queued/running/terminal 状态与阶段时间；
- 每个已完成模型的结构化结果、artifact path/hash、duration 和 metadata；
- 部分失败列表与可诊断错误；
- lease owner/expiry、checkpoint、cancel reason；
- terminal result 必须可在页面刷新、切换项目和 worker 重启后恢复。

轮询使用现有 `frontend/src/useAnalysisJob.ts` 的 terminal-state 语义，不用固定长 sleep。前端只有在后端 terminal
且结果读取成功后显示完成；HTTP 超时不等于任务失败，刷新后必须按 project/job 恢复。

### 12.3 验证

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root .

.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-invocations-round-3.json

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contracts-round-3.json

.venv/bin/pytest -q \
  tests/test_model_loader.py \
  tests/test_model_outputs.py \
  tests/test_active_model_contracts.py \
  tests/test_candidate_model_invocations.py

cd frontend
npm test -- --run src/useAnalysisJob.test.tsx
```

准出：活动 invocation/contract 不回退；模型只从本地权重加载；load/unload 状态正确；长任务刷新/切项目/worker
重启后能得到完整 terminal result；失败不伪装成功。optional inventory 可以继续报告 pending，但不得影响 A 层发布。

## 13. P7：数据整理、双跑和发布

### 13.1 数据整理

1. 生成 active reference graph：case、queue record、canonical state、attempt、报告、截图和模型 artifact 的引用关系。
2. 为 100 个 orphan state 生成显式 archive manifest，记录来源、最后引用报告、hash、保留/删除原因。
3. 只有无活动引用、可重建、非 canonical、非失败诊断的派生产物才能进入 prune dry-run。
4. 先执行 `cleanup_test_data.py` dry-run；审查路径后再 `--apply`；apply 后再次 dry-run 必须为 0。
5. 195 个重复 hash 组和 425 个额外物理副本不能按 hash 盲删；只有 safe pruner 明确认定 redundant canonical 为
   0 以外的项目才可处理。
6. outputs 根继续不放散图；活动文件统一位于 `outputs/luminar-1.28.0-23071` 的职责目录。

### 13.2 完整回归

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
cd ..

.venv/bin/python scripts/validate_sampling_data_chain.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-3-run-1.json

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-3-run-2.json
```

两次 Exact 之间不得修改代码、配置、input、reference、素材、环境或 UI build。两轮都 required failure 0 后，
再生成执行报告，必须包含执行前后表、失败清零证明、hash 稳定性、已删除数据、可恢复性和仍在范围外的 C 层能力。

## 14. 修改入口与验证矩阵

| 目标 | 主要修改入口 | 窄验证 | 最终门禁 |
|---|---|---|---|
| Catalog 数据 | 现有 `core/`、`services/`、`api/` catalog/project 路径；`CatalogWorkspace.tsx` | API + component tests | UI states + interaction |
| Preset 数据 | 现有 preset service/API；`PresetBrowser.tsx` | preset import/apply tests | preset UI + apply contract |
| UI shell | `App.tsx`、`EditorHeader.tsx`、`WorkspaceRail.tsx`、`styles.css` | frontend component tests | UI matrix |
| 编辑/更多/信息 | 对应 panel 组件 | `EditorSidePanels.test.tsx` | 新 UI states + Browser trace |
| 黑白/降噪 | `ToolPanel.tsx`、`configs/luminar_sampling.yaml`、queue handler | tool + sampling tests | UI + effect-change |
| 导出 | export UI/API、`scripts/luminar_capture/` watcher/handler | export watcher tests | export interaction |
| 原生交互 | `scripts/run_luminar_interaction_observations.py`、capture helpers | interaction observation tests | Native 10/10 |
| Browser 交互 | `scripts/build_interaction_browser_execution.py`、合同执行层 | browser execution builder tests | Browser 10/10 |
| 效果 | `ai/pipeline/image_effect_pipelines.py`、已有 `image_ops/` | 目标能力 + anchor/holdout | 45/45、69/69 |
| Panorama | `image_ops/merge/panorama.py` | panorama/workflow tests | Multi 3/3 |
| 模型 wrapper | `ai/model/`，仅合同确实错误时 | model validator/tests | active invocation/contract |
| 数据清理 | cleanup/prune/archive scripts | dry-run + postcheck | data-chain + cleanup 0 |

## 15. 单批次执行模板

每次实际修改使用同一记录模板：

```text
批次 ID：
域 / target：
冻结 baseline ID：
修改前证据与指标：
根因假设：
允许修改的文件：
明确不修改的文件：
最小实现：
窄测试：
目标验证：
holdout / anchor / 已通过回归：
修改后指标与 artifact hash：
reference/input/config hash 是否不变：
决定：accept / continue-blocked / revert
遗留项：
```

只有 target 指标改善、同域已通过项不回退、测试通过、证据完整时才 accept。若假设被证伪，记录结果并结束批次，
不要继续在同一批次叠加第二个不相关修改。

## 16. 风险、停止条件和回退

| 风险 | 检测信号 | 处理 |
|---|---|---|
| 原生窗口不可控 | 无 bounds/AX/screenshot | 停止所有 GUI 采样，只修权限和窗口 |
| 错误 reference | source/asset/readback/Reset 不一致 | 单条 invalid，定向重观察，不全量重采 |
| 导出卡页 | filename 未回读、面板不消失、文件不稳定 | 保存诊断、取消 attempt、修等待条件 |
| UI 过拟合 | 单状态改善、共享状态回退 | 回退截图特例，改共享 shell/data model |
| 效果过拟合 | 目标过、holdout/anchor 失败 | 回退 case 常数，重新分类根因 |
| 模型伪成功 | wrapper loaded 但无真实 invocation/result | fail closed，修 active contract/调用链 |
| 商业素材不合法 | provenance unknown/version mismatch | blocked-by-license，不复制、不发布 |
| 清理误删风险 | 文件仍被 case/report 引用 | 不 apply，先补 archive/reference graph |

全局停止条件：同一根因连续两个批次无可测改善；需要修改 reference/阈值才能通过；需要未授权素材或云服务；
或修复导致已通过同域指标明显回退。此时必须保留 blocked 结论并重新制定假设，不能扩大改动范围掩盖问题。

回退以单批次文件修改为单位，不使用破坏性 Git 命令，不删除用户其他修改；数据 canonical 通过 pointer/manifest 回退，
失败 attempt 保留审计。

## 17. 完整执行清单

### P0

- [ ] 第三轮 baseline/failure registry 指向 `22/5/1`。
- [ ] Luminar 可见窗口、版本、bounds、AX、screenshot 全通过。
- [ ] 251/251 数据链和 cleanup 0 保持。
- [ ] 仅 10 条 invalid 进入 pending worklist。

### P1 UI

- [ ] Catalog folder/album/order/selection/filmstrip 数据与原生一致。
- [ ] Preset 分组、锁定态、preview/apply 语义与原生一致。
- [ ] 目标 macOS 1.28 素材 provenance 完整；未授权素材未复制。
- [ ] Help/Upgrade/locked entry 有明确可审计行为。
- [ ] 16 个 UI 状态已冻结并具备原生 reference。
- [ ] 16 个 current-build evidence 有效。
- [ ] 16 个 UI pixel parity 全通过。

### P2 交互

- [ ] Native layer 合同通过。
- [ ] Native multi-image 合同通过。
- [ ] 9 条缺失 Browser raw execution 补齐。
- [ ] Native 10/10、Browser 10/10、issue 0。
- [ ] 导出命名、完成、退出页面和唯一文件得到正式证明。

### P3 采样

- [ ] 所有 case 开始前恢复原图并验证 source 状态。
- [ ] B&W 两条先转换再调参数。
- [ ] Denoise 两条先选择等级再调强度。
- [ ] 其余 6 条完成各自 apply/analysis/asset 前置步骤。
- [ ] 10 条新 canonical 均有 preview/export/reset/change/readback 证据。
- [ ] invalid-unchanged-export 为 0，其他 241 条未重采。

### P4/P5 效果与多图

- [ ] 主效果 9 条按 E1-E4 共享根因关闭。
- [ ] Exact 31 条按六类根因关闭。
- [ ] 每个能力都有 anchor/holdout/中性输入回归。
- [ ] 主效果 45/45、Exact 69/69。
- [ ] Panorama 投影/warp/crop/seam/exposure 根因明确。
- [ ] Multi-image 3/3，双跑 hash 稳定。

### P6/P7 模型、清理、发布

- [ ] 活动模型 invocation 22/22 和活动合同 16/16 不回退。
- [ ] 长任务刷新、切项目、worker 重启后结果完整可恢复。
- [ ] 100 个 orphan state 已进入 archive manifest 后再决定 prune。
- [ ] 全量 Python/Ruff/frontend test/build 通过。
- [ ] cleanup apply 后 postcheck 为 0。
- [ ] Exact 连续两轮 required failure 0，证据 hash 稳定。
- [ ] 最终报告明确 A/B/C 层完成或 blocked 状态，不扩大声明范围。

