# Luminar Neo 1.28 UI、交互、模型、效果与 Catalog 绝对对齐执行计划（第八轮）

> 本文面向当前项目维护者，给出从现有阻塞状态收敛到本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans` 唯一基线的执行顺序、修改入口、证据产物和硬验收条件。本文只规划当前活动实现，不保留旧 UI、旧 contract、旧 catalog 或旧运行时的兼容分支。

## 目录

- [1. 目标、边界与声明口径](#1-目标边界与声明口径)
- [2. 当前权威基线](#2-当前权威基线)
- [3. 不可破坏规则](#3-不可破坏规则)
- [4. 总体依赖和交付节奏](#4-总体依赖和交付节奏)
- [5. P0：让 exact gate 本身可信](#5-p0让-exact-gate-本身可信)
- [6. P1：重录当前 build 的 UI 16/16](#6-p1重录当前-build-的-ui-1616)
- [7. P2：重建并完成 Browser 10/10](#7-p2重建并完成-browser-1010)
- [8. P3：闭合 65 个 model-specific contract](#8-p3闭合-65-个-model-specific-contract)
- [9. P4：逐工具校准主效果与扩展 Exact](#9-p4逐工具校准主效果与扩展-exact)
- [10. P5：按真实 Luminar schema 一次性切换 SQLite](#10-p5按真实-luminar-schema-一次性切换-sqlite)
- [11. P6：集成回归与非像素合同](#11-p6集成回归与非像素合同)
- [12. P7：连续两轮不可变 exact 发布门禁](#12-p7连续两轮不可变-exact-发布门禁)
- [13. 批次模板、缺陷优先级与停止条件](#13-批次模板缺陷优先级与停止条件)
- [14. 完成定义](#14-完成定义)

---

## 1. 目标、边界与声明口径

### 1.1 唯一目标

最终活动产品必须在同一组冻结素材、参数、模型、环境和 Luminar canonical reference 上同时满足：

1. UI 16/16 当前 build 像素门禁通过；
2. Browser 10/10 和 Native 10/10 交互合同通过；
3. 40 个可见工具全部有真实功能路径、参数合同、预览和导出证据；
4. 主效果 canonical 报告全部通过，当前 9 个失败归零；
5. 69 个扩展 Exact case 全部通过，当前 31 个失败归零；
6. 92 个注册模型全部完成 model-specific contract，当前 65 个 pending 归零；
7. HDR、Focus Stacking、Panorama 继续保持 3/3；
8. Catalog 使用经本机真实 Luminar schema 证据确认的 SQLite 实现，运行时不存在 JSON catalog；
9. 两轮独立 exact run 的 required failure 都为 0，且全部输入指纹一致。

### 1.2 “绝对对齐”的允许口径

项目内的“绝对对齐”只表示冻结的 exact gate 全部通过，不表示仅凭人工观感、页面可操作、单元测试通过或模型能够 forward。现有效果合同的最低阈值保持 `SSIM >= 0.98`、`MAE <= 0.03`，UI 保持 `MAE <= 0.03`、`changed_pixel_ratio <= 0.02`；不得降低阈值。

如果要对外使用“逐像素完全相同”或“二进制完全相同”，还必须额外满足解码后像素 hash 或导出文件 hash 相同。MAE/SSIM 通过本身不能支持比 exact gate 更强的字面声明。

### 1.3 固定范围

| 项目 | 唯一值 |
|---|---|
| 原生参考 | Luminar Neo `1.28.0 (23071)` |
| Bundle ID | `com.skylum.luminarneo` |
| 平台 | macOS |
| 语言 | `zh-Hans` |
| 时区 | `Asia/Shanghai` |
| UI 物理 viewport | `2880x1800` |
| Browser 逻辑 viewport | `1440x900`，DPR `2` |
| 主运行时 | ONNX Runtime |
| 兜底运行时 | 经真实验证的 OpenVINO IR |
| 参考配置 | `configs/reference.yaml` |
| 对齐配置 | `configs/parity.yaml` |

Portable 安装只可用于权重、素材、配置和包结构旁证，不可替代本机 macOS Luminar 的 UI、交互、效果或 catalog schema 证据。

### 1.4 明确非目标

- 不支持 Luminar 1.25、1.26 或其他历史版本；
- 不保留旧 UI state、旧交互 contract ID、旧 API 字段或旧存储格式适配器；
- 不实现 JSON/SQLite 双写、JSON fallback、schema version 猜测或运行时自动迁移；
- 不通过删 case、改 reference、放宽 comparator、最终 resize 或 fixture 特判制造通过；
- 不把注册、signature valid、finite output 或 smoke passed 计作 model-specific validated；
- 不直接修改本机 Luminar 自己的 catalog 数据库。

## 2. 当前权威基线

### 2.1 统计基线

| 验收域 | 当前状态 | 目标状态 | 当前证据 |
|---|---:|---:|---|
| 模型结构 | 92/92 valid | 保持全量有效 | `model-contract-audit.json` |
| 模型专用合同 | 27/92 | 92/92 或经原生证据证明的非独立 backend 记录从活动注册表删除 | `model-contract-audit.json` |
| 模型 pending | 65 | 0 | `model-contract-audit.json` |
| 当前 runtime-ready | 41 | 所有活动路径可真实运行 | `model-contract-audit.json` |
| 主效果 | 36/45 | 45/45 | `parity-report-current-final.json` |
| 扩展 Exact | 38/69 | 69/69 | `exact-incremental-parity-current-final.json` |
| UI 原生 reference | 16/16 verified | 保持 | `ui/reference-manifest.json` |
| 当前源码 UI Browser evidence | 未完整重录 | 16/16 | 待生成新的 run-scoped evidence |
| Browser 交互 | 未重录 10/10 | 10/10 | 待生成 contract v2 evidence |
| Native 交互 | 已有旧合同证据 | 新合同 10/10 | 需要按 contract v2 补录 |
| 多图 | 3/3 | 保持 3/3 | 最新第七轮执行报告 |
| Catalog | JSON 单一活动存储 | 真实 schema SQLite 单一活动存储 | `services/editor/service.py`、`storage/projects/json_repository.py` |

统计必须从同一 run 重新生成。旧报告中出现的 26/66、7 个 UI state、40/45 主效果等数字不得混入新的完成声明。

### 2.2 当前 9 个主效果失败

| capability | 当前 MAE | 当前 SSIM | 首要定位方向 |
|---|---:|---:|---|
| `face_ai` | 0.030197 | 0.984212 | 人脸 ROI、landmark、局部强度与肤色保护 |
| `slim_people` | 0.053105 | 0.896961 | 人体分割、形变场、边界固定与重采样 |
| `depth_volume` | 0.068934 | 0.946598 | 深度归一化、近远景曲线与遮罩 feather |
| `lut_mapping` | 0.035247 | 0.999137 | LUT 色彩空间、插值、强度和 profile |
| `blue_hour` | 0.133379 | 0.914102 | 天空/前景分离、亮度曲线和冷暖映射 |
| `fog` | 0.113488 | 0.903759 | 深度引导透射率、雾色和空间衰减 |
| `sky_replace` | 0.064346 | 0.946903 | 天空 mask、地平线、前景保护和色彩匹配 |
| `sunrays`（sky fixture） | 0.070206 | 0.942800 | 光源定位、遮挡、径向衰减和合成 |
| `sunrays`（sunrays fixture） | 0.053714 | 0.956221 | 同一算法的 holdout 泛化 |

`face_ai` 只是略超 MAE 阈值，但仍必须按相同标准修复；不得通过小数截断或报告格式掩盖失败。

### 2.3 当前基础设施缺口

1. `scripts/run_quality_gates.py` 当前把 `model-contract-inventory` 设为 optional；exact 模式必须改为 required，并调用 `--require-exact` 的模型矩阵。
2. `scripts/build_source_manifest.py` 的默认 roots 缺少 `core/`，也没有绑定前端锁文件、模型二进制和运行环境。
3. 多个 gate 写固定 `current.json` 或默认诊断路径，连续两轮会覆盖证据，无法证明两轮独立完成。
4. UI evidence 当前只强制截图、fixture 和 frontend build hash，尚未强制 DOM snapshot 与 Browser AX tree。
5. 现有 10 个 Browser 合同没有完整覆盖新增的右键子菜单、目录滚动、照片切换历史、预设导入和遮罩闭环，需要一次性替换为 contract v2。
6. Catalog 读写仍位于 `EditorService` 私有 JSON 方法中，存储边界未形成独立 port。

## 3. 不可破坏规则

1. canonical reference 默认只读；候选失败不是重采 Luminar 的理由。
2. 只有 reference 缺证据、原生导出不稳定或输入/hash 错误时才允许重采，并必须先登记原因。
3. 不修改 `configs/parity.yaml` 的 MAE、SSIM、UI changed-pixel-ratio 阈值。
4. 不让运行时代码读取 case ID、reference 路径、reference hash、失败名单或 fixture 文件名选择算法。
5. 每次校准至少包含 calibration fixture、独立 holdout 和全量回归；只对单图有效的修复不得合并。
6. ONNX 可用时不得无理由加载 IR；IR 只有在 ONNX 不可用且自身 contract、forward、postprocess 和资源释放全部通过后才能接管。
7. `retired-invalid-source`、空输出、全零 mask、原图回退和启发式 fallback 不能计作 exact 成功。
8. 活动 native-used 模型不得为缩小统计而删除；只有证据证明是同一 logical model 的冗余 backend 记录时才可从活动注册表移除。
9. UI 或 frontend build hash 一旦变化，整套 UI 16 和 Browser 10 evidence 全部失效并重录。
10. SQLite 切换必须是单次破坏性 schema cutover：迁移成功后同一变更删除 JSON 读写、迁移器和旧测试。
11. 回滚通过源码版本和迁移前数据库备份完成，不在产品中保留兼容代码。
12. 任一阶段发现 source、model、input、reference、asset 或环境 fingerprint 漂移，立即停止该 run。

## 4. 总体依赖和交付节奏

```text
P0 门禁可信化与冻结基线
 │
 ▼
P1 UI 16/16 当前 build
 │
 ▼
P2 Browser/Native contract v2 10/10
 │
 ▼
P3 65 个 model-specific contract
 │
 ▼
P4 9 个主效果 → 31 个扩展 Exact → 40 工具全参数回归
 │
 ▼
P5 真实 Luminar schema 取证 → SQLite 一次性切换
 │
 ▼
P6 全链路集成回归
 │
 ▼
P7 两轮同 fingerprint exact gate
```

UI 必须先完成，因为当前 UI 改动会使 Browser evidence 失效；模型必须早于最终效果校准，因为 mask、depth、landmark 或 restoration contract 改动会直接改变候选输出；SQLite 放在效果稳定后，避免存储重构和图像算法调试交叉。

建议单人全职按 8–14 周规划，其中 P3 和 P4 占主要时间。若 65 个模型的语义无法从本机调用、配置或原生中间产物恢复，工期必须按证据缺口调整，不能用统一 wrapper 缩短。

## 5. P0：让 exact gate 本身可信

### 5.1 修改入口

- `scripts/run_quality_gates.py`
- `scripts/build_source_manifest.py`
- `scripts/build_model_validation_matrix.py`
- `scripts/check_model_contracts.py`
- `scripts/validate_ui_execution_evidence.py`
- `scripts/build_ui_browser_execution.py`
- `scripts/build_interaction_browser_execution.py`
- `scripts/validate_interaction_execution.py`
- `configs/parity.yaml`
- `tests/test_source_manifest.py`
- 对应 gate 测试

### 5.2 实施步骤

1. 将 exact 模式的模型门禁改为 required：
   - `check_model_contracts.py` 必须以 `exact_gate` 决定退出码；
   - `build_model_validation_matrix.py --require-exact` 必须执行；
   - 任何 pending、missing、format mismatch 或活动 backend runtime failure 都阻断 exact。
2. 扩展 source manifest：
   - 加入 `core/`、`frontend/package.json`、锁文件、Vite/TypeScript 配置；
   - 单独生成 model artifact manifest，记录 ONNX、XML、BIN、tokenizer 和 contract hash；
   - 单独生成 validation manifest，记录 cases、inputs、references、素材 manifest 和 comparator 配置；
   - 生成 environment manifest，记录 macOS、CPU 架构、Python、NumPy、Pillow、ORT、OpenVINO、Browser 版本、locale、timezone、viewport、DPR 和 motion。
3. 把 gate 输出改为不可变 run 目录：
   - `diagnostics/runs/<run-id>/...`；
   - 子 gate 不再覆盖另一 run 的报告；
   - 失败 run 保留完整 stdout、stderr、截图、网络、console 和 trace；
   - 只有整轮通过后才生成只读 release summary，不复制或改写 canonical。
4. 新增 exact-run 汇总器，必须检查所有子报告的 `run_id`、`reference_id` 和四类 fingerprint 一致。
5. 新增双轮比较器，比较 run-1 和 run-2 的 source/model/validation/environment fingerprint、gate 列表、阈值和 required failure。
6. 给 UI evidence 增加 DOM snapshot 与 Browser AX tree 路径和 SHA-256；缺任意一项即失败。
7. 给 interaction evidence 增加 frontend build hash、DOM/AX、每一步截图或 trace hash，以及 API request/response 摘要 hash。
8. 先执行 dry-run，确认 exact gate 列表包含所有 required 项且没有 optional exact 阻断项。

### 5.3 当前可执行检查

```bash
.venv/bin/python scripts/build_source_manifest.py \
  --project-root . \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/source-manifest-p0.json

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --dry-run \
  --run-id p0-exact-plan \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-plan-p0.json
```

### 5.4 准出条件

- exact dry-run 中模型 contract 和模型矩阵均为 required；
- source manifest 确实包含 `core/`；
- 两个不同 run-id 不覆盖彼此产物；
- 人为删除任一 UI DOM/AX、模型 contract 或 reference artifact 时，exact gate 必须失败；
- P0 只修门禁和证据链，不修改 UI 或图像算法。

## 6. P1：重录当前 build 的 UI 16/16

### 6.1 16 个固定状态

状态名沿用 `configs/parity.yaml`，但 evidence 必须属于当前 frontend build：

| 状态 | 固定 fixture / 操作 | 主要可见断言 |
|---|---|---|
| `catalog` | 已导入固定目录 fixture，默认“所有照片” | 目录侧栏、计数、网格、检查器和滚动容器 |
| `presets` | 固定单图，预设首页 | 分类顺序、封面、添加入口、无商店/升级入口 |
| `edit` | 固定单图，无展开工具 | 顶栏、画布、工作区 rail、工具栏和 filmstrip |
| `layer-stack` | 固定图层 fixture | 原图层、素材层、顺序、显隐、属性栏 |
| `layer-library` | 打开本地素材库 | 分组、缩略图、本地导入入口 |
| `tool-expanded` | 展开固定工具和参数 | 手风琴、参数顺序、slider/value、画布状态 |
| `edit-history` | 固定两步 edit stack | 历史顺序、当前项、开关和删除入口 |
| `more-panel` | 打开更多 | 提升分辨率、修复、HDR、Focus、Panorama 卡片 |
| `info-panel` | 固定带 EXIF 图片 | 文件、相机、镜头、尺寸、曝光字段 |
| `edit-collapsed` | 收起编辑面板 | 画布扩展、rail 状态、无布局跳变 |
| `black-white-before-conversion` | 黑白工具未转换 | 原图和转换入口 |
| `black-white-after-conversion` | 应用固定黑白参数 | 通道参数与画布输出 |
| `denoise-level-selected` | 选择固定降噪档位 | 档位状态、参数和 busy 完成态 |
| `export-dialog` | 打开导出 | 文件名、格式、尺寸、profile、取消/导出 |
| `multi-image` | 固定多图输入未完成 | 文件列表、工作流类型、预览按钮 |
| `multi-image-complete` | 固定工作流生成完成 | 预览、完成状态和导出可用 |

### 6.2 录制环境

1. 构建并启动后端和前端；固定 Browser 为 `1440x900`、DPR 2、`zh-Hans`、`Asia/Shanghai`、reduced motion。
2. 从空白 fixture root 初始化 catalog、projects、local presets 和 workflow，禁止复用开发者日常数据。
3. 每个状态按固定 seed 脚本建立；不得通过手工拖拽到“看起来差不多”的位置。
4. 每个状态保存：
   - 逻辑 viewport 原始截图；
   - 物理 viewport candidate；
   - DOM snapshot；
   - Browser AX tree；
   - fixture JSON 和 fixture hash；
   - frontend build hash；
   - Browser/environment manifest；
   - console error 和 failed network request 摘要。
5. 使用 `scripts/build_ui_browser_execution.py` 发布 evidence，再依次执行 evidence validator 和 UI comparator。

### 6.3 实施中需要补强的工具

- `build_ui_browser_execution.py`：加入 DOM/AX artifact 及 hash；
- `validate_ui_execution_evidence.py`：强制 16 个状态、DOM/AX、build/environment 一致；
- UI fixture seed：为 16 个状态提供幂等初始化和状态断言；
- UI comparator：失败时输出 reference、candidate、diff heatmap 和几何区域摘要。

### 6.4 校准顺序

1. 先修全局 frame：viewport、header、rail、左右栏、canvas；
2. 再修组件几何：宽高、padding、gap、字体、icon、border；
3. 再修内容：文案、排序、计数、默认选中；
4. 最后修状态：hover、selected、disabled、expanded、dialog；
5. 每次 frontend hash 改变后重新录制全部 16 状态，不拼接新旧截图。

### 6.5 准出条件

- `ui-execution-evidence`：expected=16、executed=16、passed=16；
- `ui-parity`：case_count=16、passed=16、failed=0、pending=0；
- 16 个记录共享同一个 frontend build hash 和 environment fingerprint；
- DOM/AX、截图和 fixture hash 全部存在且 validator 可复算；
- console error 和 failed request 为 0。

## 7. P2：重建并完成 Browser 10/10

### 7.1 一次性替换 contract v2

现有 `configs/parity/interaction-contracts.json` 直接替换为下列 10 个当前合同；不保留旧 ID 映射或 v1 解析器：

| 合同 ID | 必须覆盖的操作 | 必须证明的持久状态 |
|---|---|---|
| `catalog-photo-context-submenu` | 照片右键、标记/评分子菜单、旋转、移至回收站/恢复 | catalog record、preview rotation、计数变化 |
| `catalog-folder-context-scroll` | 文件夹右键、导入到当前文件夹、长目录滚动到底并返回 | 记录归属、滚动位置、选择保持 |
| `edit-tool-expand-crop` | 工具展开/收起、slider、裁切比例、拖框、旋转、应用 | edit stack、裁切几何、输出尺寸 |
| `photo-switch-history` | A 图编辑、切 B、编辑 B、返回 A、undo/redo | 两张照片历史隔离且恢复一致 |
| `preset-import-preview-apply` | 导入 `.lnp`、显示本地预设、预览、应用 | preset 索引、graph 顺序、只应用一次 |
| `layer-lifecycle` | 导入层、重排、显隐、opacity、blend、transform、删除 | layer stack 与 preview/export 一致 |
| `mask-lifecycle` | 新建/导入、画笔或 AI mask、反转、密度、羽化、undo/redo、删除 | mask 数据、历史和合成结果 |
| `compare-zoom-pan` | 前后对比、200% zoom、pan、fit | 项目不变，视图状态正确恢复 |
| `multi-image-three-workflows` | HDR、Focus、Panorama 三个分支各完成预览和导出 | 输入 hash、顺序、结果 hash、3/3 |
| `export-dialog-file` | 打开导出、文件名、格式、尺寸、profile、取消后再导出 | 单一输出、元数据和像素 hash |

### 7.2 Native 观察

1. 对 10 个 v2 合同逐个在 Luminar 原生应用执行；
2. 记录 before/after、AX tree、每一步语义定位、菜单层级、等待条件和最终状态；
3. 右键子菜单必须记录父菜单和子菜单，不把单层模拟当成通过；
4. 多图合同的三个分支分别保留 native observation，再由一个合同汇总；
5. 禁止 fixed sleep，所有等待都绑定可见状态、AX 状态、网络完成或 API 状态。

### 7.3 Browser 执行

1. 使用与 P1 完全相同的 frontend build 和 fixture root；
2. 每个合同从独立 fixture 重置开始，禁止依赖上一个合同留下的状态；
3. raw trace 必须包含合同原始 events、实际 target、开始/结束时间、等待条件、可见断言、API 断言和失败产物；
4. 使用 `scripts/build_interaction_browser_execution.py` 将 raw trace 与 native observation 绑定；
5. 使用 `scripts/validate_interaction_contracts.py` 和 `scripts/validate_interaction_execution.py` 验收。

### 7.4 必须增加的自动断言

- 右键操作必须产生预期 API mutation，关闭菜单后可重新读取；
- 目录滚动必须证明最后一行可见，不能只检查 `scrollHeight > clientHeight`；
- 照片切换后 edit ID、顺序、参数和 preview hash 都与原照片一致；
- 预设导入后重启 API 仍可读取；
- layer/mask 的 preview 与 export 使用同一 state hash；
- 多图三个分支都执行，不能用一个 HDR 成功代表 3/3；
- export 只能生成一个目标文件，取消不得生成文件。

### 7.5 准出条件

- contract definition：10/10 defined；
- Native：10/10 具有当前合同 observation；
- Browser：10/10 executed、10/10 passed；
- 每个合同 events、visible assertions、API assertions、DOM/AX、截图和 trace hash 完整；
- frontend build hash 与 P1 相同；
- fixed sleep、漏断言、缺 native observation 和缺 failure artifact 均为 0。

## 8. P3：闭合 65 个 model-specific contract

### 8.1 65 个 pending 的真实组成

| 模型族 | 数量 | 核心输出语义 |
|---|---:|---|
| 分割与 mask | 27 | semantic/instance/skin/hair/wire/dust/transport 等 mask |
| 超分辨率 | 12 | x2/x4/x6 restored image、tile 与 seam |
| 检测、landmark、depth 与分析 | 18 | boxes、keypoints、depth、class、light map |
| 恢复与 portrait bokeh | 4 | restored image、defocus map 或 alpha |
| RAW | 2 | CFA 与 channel-shift 图像 |
| 文本 embedding | 1 | normalized embedding |
| 未知分析模型 | 1 | 必须先恢复真实语义，不允许猜测 |
| 合计 | 65 | pending 必须归零 |

### 8.2 每个 contract 的最低字段

每个 `models/contracts/<model-id>.json` 必须通过真实代码和实测补齐：

- artifact/weights SHA-256、format、backend、logical model；
- input/output name、shape、dynamic axis、dtype、layout；
- source color space、channel order、range、normalization；
- resize、crop、letterbox、padding、tile、batch 规则；
- postprocess：activation、threshold、NMS、resize-back、坐标系、class mapping；
- output semantic type、finite/range/shape assertions；
- canonical 正样本、负样本、边界样本和选择理由；
- runtime raw output hash、postprocess result hash、重复运行一致性；
- loader/factory/cache/lease/unload 证据；
- consumers、capability invocation trace 和最终 effect/workflow evidence；
- ONNX/IR 双 backend 差异，或 IR 兜底不可用的明确阻断证据。

### 8.3 每模型固定验证顺序

```text
文件与 hash
  → runtime signature
  → preprocess golden
  → 真实 forward
  → raw tensor 语义
  → postprocess golden
  → 正/负/边界样本
  → 重复运行
  → unload/reload
  → backend pair
  → 产品 consumer invocation
  → Luminar 中间产物或最终效果
```

任何一步失败，状态保持 pending/blocked，不得跳过到 validated。

### 8.4 批次顺序

#### M0：修模型 exact gate

- exact runner 强制 `check_model_contracts.py` 和 `build_model_validation_matrix.py --require-exact`；
- `TERMINAL` 不再把 `retired-invalid-source` 计作活动 exact 成功；
- `runtime_ready` 的定义统一为真实 backend load + forward + postprocess + unload 通过。

#### M1：9 个主效果依赖模型

优先处理 face/landmark/skin/human segmentation、depth、sky/saliency、light detection、portrait bokeh。每个模型输出保存灰度 mask、彩色 overlay、分布统计和边界指标，先证明中间产物，再调最终效果。

#### M2：当前 UI 可触达工具与工作流模型

覆盖 crop、erase/clone、denoise/deblur、upscale、repair、layer/mask、HDR/Focus/Panorama 的真实调用路径。要求 UI 操作 → API → pipeline → wrapper → runtime → result → preview/export trace 连续。

#### M3：38 个 signature-inspected runtime pending

在当前 arm64 环境逐个执行 OpenVINO compile、forward、postprocess 和 unload；优先寻找可靠 ONNX 转换。只有转换的 ONNX checker、ORT forward、wrapper 和消费者全部通过后才能成为 primary。

#### M4：17 个 ORT smoke pending

补真实 normalization、postprocess 和语义样本；`finite + shape` 不足以通过。超分、mask、embedding 和 detection 分别使用专用比较器。

#### M5：10 个 inference-validated 但 contract pending

补消费者、正负样本、backend/effect parity 和生命周期证据，禁止因已有 inference 状态直接批量改 status。

#### M6：未知语义和无消费者记录

通过原生配置、模型 I/O、调用字符串、邻接 pipeline 和输入输出实验恢复语义。若证据证明只是同一 logical model 的冗余 backend 记录，可在一个破坏性清理变更中从活动注册表、contract 和 source map 删除；不得保留 alias 或把删除计作“已验证”。原生实际使用的模型不得删除。

### 8.5 ONNX 优先、IR 兜底的最终规则

1. 同一 logical model 的 ONNX 和 IR 使用同一任务语义和 postprocess contract；
2. ONNX 通过完整验证后优先级为 0；
3. IR 仅在 ONNX artifact 不存在、加载失败或平台不支持时尝试；
4. IR 自身必须已验证，不能在请求时临时探测；
5. primary 失败和 fallback 原因写入 trace；
6. 两 backend 输出在同一 fixture 上生成差异报告；
7. 非有限 IR 且已有可靠 ONNX 时，IR 从活动 fallback 列表移除，不保留 retired 兼容状态。

### 8.6 准出条件

- 92/92 contract 结构有效；
- model-specific validated=92、pending=0；如果活动注册表经证据清理，分母必须等于清理后的真实 native scope，且不得减少 native-used logical model；
- 所有活动模型 runtime forward/postprocess 可复现；
- 所有 UI 可触达模型都有 invocation trace；
- exact model matrix、source map、runtime policy、pipeline audit 和 invocation audit 全部通过；
- 不存在统一空壳 wrapper、全零结果或静默原图 fallback。

## 9. P4：逐工具校准主效果与扩展 Exact

### 9.1 总体策略

先修当前 9 个主效果失败，再处理 69-case 集合中的剩余扩展失败。每次只处理一个根因族，不按报告顺序盲调参数。相同 capability 的主 case、exact case 和 holdout 必须一起看。

### 9.2 9 个主失败的执行批次

| 批次 | 范围 | 必须先看的中间证据 | 允许修改的位置 |
|---|---|---|---|
| E1 | `face_ai`、`slim_people` | face box、landmark、human mask、warp grid、边界固定 | 对应 model wrapper、portrait pipeline、warp/compositor |
| E2 | `depth_volume`、`fog` | raw depth、normalized depth、透射率、feather mask | depth pipeline、curve、spatial compositor |
| E3 | `sky_replace`、`blue_hour` | sky mask、horizon、foreground protection、color stats | sky pipeline、mask refine、color match、blend |
| E4 | 两个 `sunrays` | light map、origin、occlusion、radial field | sunrays pipeline/compositor |
| E5 | `lut_mapping` | input/output color profile、3D LUT coordinates、interpolation | LUT loader、color transform、strength mix |

每个批次执行：before → 中间产物对比 → 最小根因修复 → calibration → holdout → 主 45 → Exact 69 → 性能与非回归。

### 9.3 40 个可见工具的完整回归矩阵

| 工具族 | capability | 必须验证的特性 |
|---|---|---|
| 人像/几何 | `bokeh_ai`、`face_ai`、`face_enhancer`、`skin_smooth`、`slim_people`、`crop_ai` | ROI、landmark/mask、形变、边缘、多人/无人负样本 |
| AI/场景 | `ai_enhance`、`depth_volume`、`structure_ai`、`landscape_enhancer`、`water_enhancer` | 中间 map、局部强度、场景负样本 |
| 天空/光效 | `blue_hour`、`fog`、`sky_replace`、`sunrays`、`magic_lights`、`new_neon_light` | mask、光源、地平线、遮挡、合成和素材 |
| 降噪/锐化/空间 | `denoise`、`denoise_laplacian`、`deblur`、`details`、`blur` | 档位、tile seam、halo、细节保留、preview/export |
| 色彩/色调 | `bw_channels`、`color_adjustments`、`color_enhancer`、`color_toning`、`color_transfer`、`lut_mapping` | 色彩空间、profile、通道、插值、强度 |
| 风格/基础效果 | `complex_bleach`、`default_effects`、`fade`、`glow_orton`、`grain`、`high_key`、`pro_contrast`、`radiance`、`vignette` | 参数曲线、混合顺序、随机性、局部/全局统计 |
| 画笔/修复 | `clone`、`dodge_burn`、`erase` | 坐标、笔刷半径、羽化、stroke 顺序、undo/redo |

每个 capability 不能只验默认 `amount=0.4`。至少增加零值、低/中/高、边界值、开关组合、素材选择或 brush stroke，以及 portrait/general/sky/negative 中适用的 holdout。新增参数点属于验证扩展，不可替换现有 canonical case。

### 9.4 31 个扩展 Exact 失败的根因队列

按当前报告先分为：

1. 高误差结构性失败：`fog`、`blue_hour`、`default_effects`、`grain`、`vignette`、`sunrays`、`depth_volume`；
2. 人像/AI 局部失败：`face_ai`、`face_enhancer`、`bokeh_ai`、`slim_people`；
3. 色调曲线失败：`color_toning`、`radiance`、`landscape_enhancer`、`fade`、`high_key`、`pro_contrast`、`color_adjustments`、`color_enhancer`；
4. 细节/噪声失败：`denoise`、`denoise_laplacian`、`structure_ai`；
5. 特殊 comparator 失败：`magic_lights`、`new_neon_light` 和 grain-statistical case。

主 case 已通过但 exact holdout 失败时，不允许以主 case 为依据结束；必须修泛化或回退该批修改。

### 9.5 预览、导出与非破坏编辑合同

每个工具还必须满足：

- 相同 ProjectState 的 preview 与 export 使用相同 effect graph；
- preview 只允许分辨率差异，不允许算法、参数或 mask 语义差异；
- edit 顺序、enable、opacity、mask 和 blend 可序列化并重载；
- undo/redo 恢复相同 edit ID、参数、model artifact hash 和输出 hash；
- 无适用对象时明确不可用或输出合同定义的 no-op，不伪造 AI 效果；
- 导出尺寸、orientation、ICC/profile 和 alpha 处理与 reference 合同一致。

### 9.6 准出条件

- 主效果 45/45；
- Exact 69/69；
- 40 个可见工具全部有参数、负样本、preview/export 和 history 证据；
- 9 个主失败和 31 个扩展失败为 0；
- 阈值、reference、input hash 和 comparator 未变化；
- performance gate 不出现不可接受回归，所有模型资源可释放。

## 10. P5：按真实 Luminar schema 一次性切换 SQLite

### 10.1 启动前置条件

本阶段只有在找到本机 Luminar 实际 catalog 数据库后才能开始。`crop.db` 和 `data.mlcdb` 不能作为 catalog schema。没有真实 schema 时，P5 保持 blocked，不创建推测表。

原生数据库只读复制后分析，禁止让项目进程连接或写入 Luminar 自己的活动数据库。

### 10.2 只读取证

阶段中新增 `scripts/inspect_luminar_catalog_schema.py`，对用户确认的只读副本输出：

- 文件 SHA-256、SQLite header、`application_id`、`user_version`、page size；
- tables、columns、types、null/default/PK；
- indexes、unique constraints、foreign keys、triggers、views；
- WAL/journal 模式；
- 与照片、文件夹、编辑、评分、标记、旋转、回收站、预设相关的表关系；
- 去隐私化的值类型和枚举，不复制用户私人路径或照片内容；
- canonical schema SQL 和 schema fingerprint。

只有关系、约束和状态语义都能解释当前 catalog 功能后，schema evidence gate 才通过。

### 10.3 目标架构

```text
API / EditorService
        │
        ▼
CatalogRepository port
        │
        ▼
SQLiteCatalogRepository
        │
        ▼
项目自有 catalog.db（真实 schema 的已验证活动子集/关系）
```

不要直接让 `EditorService` 拼 SQL。先从 `services/editor/service.py` 提取 catalog port，再在 `storage/` 实现单一 SQLite adapter；`api/app.py` 只组装 SQLite 实现。

### 10.4 一次性迁移步骤

1. 冻结写入并备份当前 `catalog.json`；备份只用于迁移失败回滚，不进入运行时读取路径。
2. 使用真实 schema 创建临时 `catalog.db`，开启 foreign keys 并按证据设置 journal。
3. 用阶段内临时迁移器把现有记录写入一个事务；字段无真实落点时停止，不塞入通用 JSON blob。
4. 校验 row count、asset/project 关联、rating、favorite、rejected、rotation、deleted、folder、edit count 和时间字段。
5. 启动 API，在隔离 fixture 上跑导入、查询、更新、删除/恢复、切图、历史、预设、重启持久化和 Browser 合同。
6. 原子替换正式 `catalog.db`。
7. 同一提交删除：
   - `catalog.json`；
   - `EditorService._read_catalog/_write_catalog`；
   - `JsonProjectRepository.catalog_path` 耦合；
   - JSON catalog 测试和 fixture；
   - 临时迁移器；
   - 所有 JSON fallback、dual-write、schema adapter 和版本判断。
8. 搜索 `catalog.json`、`_read_catalog`、`_write_catalog`、`catalog_path`，结果必须为 0。

项目 edit-state JSON 与 catalog 是不同边界。是否迁移 project state 必须由真实 Luminar schema 证据决定；不得为了“全 SQLite”口号猜测原生表，也不得保留 catalog JSON 作为 project state 的兼容入口。

### 10.5 数据一致性和并发

- 每个写操作使用显式事务；
- foreign keys 开启并测试；
- 导入以 asset content hash 保证幂等；
- rating/favorite/rotation/trash 更新后同一事务可读；
- API 重启后结果一致；
- 不允许 DB 锁错误被吞掉后返回成功；
- migration 和 runtime 不访问 Luminar 原始数据库。

### 10.6 准出条件

- 有真实 schema evidence、schema fingerprint 和关系说明；
- 项目仅连接自有 `catalog.db`；
- JSON catalog 文件、读写代码、fallback、dual-write 和旧测试全部删除；
- 数据迁移 row/hash/relationship 审计通过；
- P1 UI 16、P2 Browser 10、40 工具和 3 个多图工作流在 SQLite 上全量复跑通过；
- 进程重启和异常事务测试通过。

## 11. P6：集成回归与非像素合同

### 11.1 后端与前端

```bash
.venv/bin/python -m compileall -q ai api configs core services image_ops storage scripts tests
.venv/bin/ruff check ai api configs core services image_ops storage scripts tests
.venv/bin/pytest -q
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py --project-root .

cd frontend
npm test -- --run
npm run build
```

### 11.2 专项门禁

```bash
.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contract-audit-release.json

.venv/bin/python scripts/build_model_validation_matrix.py \
  --require-exact \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-validation-matrix-release.json

.venv/bin/python scripts/run_sky_e2e_validation.py
.venv/bin/python scripts/run_preset_validation.py
.venv/bin/python scripts/run_overlay_e2e_validation.py
.venv/bin/python scripts/run_multi_image_workflow_smoke.py
.venv/bin/python scripts/run_performance_suite.py
```

### 11.3 必须保持的横向合同

- 素材：天空、overlay、LUT、预设封面/图标 hash 不漂移；
- 三多图：HDR、Focus、Panorama 3/3，输入顺序和导出稳定；
- 目录：评分、标记、旋转、回收站、folder 和照片计数一致；
- 编辑：每照片历史隔离、preview/export 同 graph；
- 图层/遮罩：顺序、transform、blend、mask、history 和导出一致；
- 性能：没有 session 泄漏、无界缓存或重复模型加载；
- 失败行为：缺模型、坏输入、坏 schema 或写事务失败时 fail-closed。

### 11.4 准出条件

- 后端、前端、lint、build 全通过；
- 模型、效果、UI、交互、素材、多图、性能、SQLite 全部单域通过；
- 不存在 console error、未处理 promise、500 或静默 fallback；
- source/model/validation/environment manifest 已冻结，进入 P7 后禁止修改任何活动文件。

## 12. P7：连续两轮不可变 exact 发布门禁

### 12.1 冻结内容

进入 P7 前生成 release fingerprint，至少包含：

- 源码与配置；
- 前端 build；
- 92 个模型 artifact、weights 和 contracts；
- 40 个可见工具、45 个主 case、69 个 Exact case、输入和 canonical reference；
- 素材 manifests；
- catalog schema 和固定测试 fixture DB；
- Python/Node/ORT/OpenVINO/Browser/macOS 环境；
- viewport、DPR、locale、timezone、motion；
- comparator 和阈值。

### 12.2 两轮执行

阶段 P0 完成 run-scoped 改造后执行：

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --run-id release-exact-1 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/release-exact-1/quality-gates.json

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --run-id release-exact-2 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/release-exact-2/quality-gates.json
```

两轮之间允许清理进程、runtime cache 和临时 candidate，不允许改源码、配置、模型、fixture、reference、素材、DB schema、依赖或环境。

### 12.3 双轮比较

阶段中新增的双轮比较器必须检查：

- 两轮四类 fingerprint 完全相同；
- gate ID、required 属性和阈值相同；
- 每轮 required failure=0；
- 每轮 UI 16/16、Browser 10/10、Native 10/10；
- 每轮 model pending=0；
- 每轮主效果全通过、Exact 69/69、多图 3/3；
- 每轮没有 pending-reference、optional exact blocker、stale build 或被覆盖产物；
- 候选输出差异在合同允许范围内；确定性能力应输出相同 hash。

### 12.4 失败处理

- 任一轮失败：发布状态 blocked；
- fingerprint 不同：两轮全部作废，从修复后的新 fingerprint 重新执行两轮；
- 只修报告脚本也属于 source 变化，必须重新执行两轮；
- 不允许只补跑失败 gate 后与上一轮拼接成“完整通过”。

## 13. 批次模板、缺陷优先级与停止条件

### 13.1 每个实现批次模板

| 字段 | 必填内容 |
|---|---|
| Scope | 一个根因族、涉及 capability/model/UI state/contract |
| Before | 报告路径、case、MAE/SSIM 或合同 issue |
| Assumption | 预计根因及可证伪条件 |
| Files | 计划修改的最小文件集合 |
| Intermediate evidence | mask/depth/landmark/tensor/DOM/AX/SQL 等 |
| Calibration | 用于定位的 fixture |
| Holdout | 不参与调参的 fixture |
| Verification | 窄测试、域 gate、全量 gate |
| Regression | 已通过 case、性能、资源释放和历史 |
| Rollback | 代码版本或迁移前备份，不含兼容分支 |

### 13.2 优先级

| 优先级 | 条件 | 处理规则 |
|---|---|---|
| P0 | 证据链可伪造、gate 漏项、reference/hash 漂移 | 立即停止其他工作 |
| P1 | UI/Browser 当前 build 缺证据、主效果或模型 exact blocked | 按本文阶段顺序处理 |
| P2 | 已通过功能的性能、资源或边界回归 | 不得进入发布双轮 |
| P3 | 文档、诊断可读性，不影响判定 | 域 gate 稳定后处理 |

### 13.3 必须停止并重新判断的情况

- 找不到真实 catalog SQLite；
- Luminar 同一输入重复导出的原生方差超过现有阈值；
- 模型语义只有猜测，没有调用、配置或输出证据；
- 参考截图、AX tree、fixture 或源码 hash 无法绑定；
- 修复只能依赖 case ID、fixture 文件名或 reference 统计；
- 某 capability 的主 case 通过但 holdout 明显退化；
- IR 在当前运行时产生非有限输出且没有可靠 ONNX；
- 双轮之间任何 fingerprint 变化。

## 14. 完成定义

只有以下清单全部满足，才可把项目状态从 blocked 改为“与本机 Luminar Neo 1.28.0 (23071) 的冻结 exact contract 对齐”：

- [ ] exact gate 中不存在 optional 的 exact 阻断项；
- [ ] source/model/validation/environment manifest 完整；
- [ ] UI 当前 build 16/16；
- [ ] Native contract v2 10/10；
- [ ] Browser contract v2 10/10；
- [ ] 92 个活动模型 model-specific validated，pending=0；
- [ ] ONNX primary / validated IR fallback 策略真实生效；
- [ ] 40 个可见工具的 UI、参数、功能、preview/export、history 和效果合同完成；
- [ ] 主效果 45/45；
- [ ] 扩展 Exact 69/69；
- [ ] HDR、Focus、Panorama 3/3；
- [ ] 真实 catalog schema evidence 完成；
- [ ] SQLite 单写，JSON catalog 和迁移兼容逻辑为 0；
- [ ] 后端、前端、lint、build、性能和资源释放通过；
- [ ] 两轮相同 fingerprint 的 exact run required failure 都为 0；
- [ ] 两轮报告和失败产物可独立复算，没有互相覆盖。

未满足任一项时，允许声明对应子域“功能可用”或“域门禁通过”，不允许声明全产品绝对对齐。
