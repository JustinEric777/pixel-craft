# Luminar Neo 1.28 绝对对齐执行结果与最终收敛计划（第九轮）

> 本文是 2026-08-28 最终源码和证据状态的权威说明。目标仅覆盖本机 Luminar Neo `1.28.0 (23071)`、macOS、`zh-Hans`、冻结素材和冻结参数下的本地核心编辑合同。付费、升级、教程、帮助、账号、商店、云服务和商业内容不属于 required 功能范围。项目不保留历史版本、旧交互合同、JSON catalog、旧 schema、双写或 fallback 兼容逻辑。

## 1. 结论

本轮完成了门禁可信化、当前源码 UI 16 状态正式录制、交互合同 v2 定义、导出闭环、真实 Luminar schema SQLite cutover、主效果最新候选重算和全量工程回归。

项目仍不能声明“与 Luminar Neo 绝对对齐”。最终 exact run 为：

| 项目 | 最终结果 |
|---|---|
| run id | `final-v2-evidence-20260828` |
| exact gate | 31 项中 25 通过、6 失败，`blocked` |
| source fingerprint | `5cfb4001c5107dfca039af0d74e61caf37242c4ea611c01adf46b53cca47bcfe` |
| release fingerprint | `2cb0346bb24f8960df4c224249b05b76d49183996a4be42896ee284820559098` |
| Python | 333 passed，1 个第三方 deprecation warning |
| Frontend | 31 passed；TypeScript/Vite production build passed |
| Ruff | passed |
| UI 证据完整性 | 16/16 passed |
| UI 像素 | 0/16 passed |
| Browser/Native v2 | 0/10 executed |
| 主效果 | 31/40 passed，9 failed |
| 扩展 Exact | 38/69 passed，31 failed |
| 模型结构 | 92/92 valid |
| model-specific | 27/92 validated，65 pending |
| runtime-ready | 41 |
| OpenVINO IR | 42 个中 41 ready、1 retired、0 failed |

最终 6 个 required 失败域为：

1. `model-contract-inventory`；
2. `model-validation-matrix`；
3. `output-parity`；
4. `exact-incremental-parity`；
5. `ui-parity`；
6. `interaction-execution`。

## 2. 本轮已经实现的内容

### 2.1 Exact gate 和证据链

- exact 模式下模型合同和模型矩阵均为 required；
- 每个 run 使用不可覆盖目录 `diagnostics/runs/<run-id>`；
- source manifest 已覆盖 `core/`、前端源码和锁文件、模型合同、脚本、服务、存储和测试；
- release fingerprint 分离 source、model、validation 和 environment 输入；
- UI evidence 强制包含物理截图、逻辑截图、DOM snapshot、Browser AX tree、fixture hash 和 frontend build hash；
- 新增双 run fingerprint 比较入口；只有两轮全部 required 失败为 0 才允许发布对齐声明。

### 2.2 UI 当前源码正式证据

以 `1440x900` 逻辑 viewport、DPR 2、`2880x1800` 物理 viewport 重录了以下 16 个状态：

`catalog`、`presets`、`edit`、`layer-stack`、`layer-library`、`tool-expanded`、`edit-history`、`more-panel`、`info-panel`、`edit-collapsed`、`black-white-before-conversion`、`black-white-after-conversion`、`denoise-level-selected`、`export-dialog`、`multi-image`、`multi-image-complete`。

HDR 完成态使用三个真实文件通过浏览器 `filechooser` 输入，并真实执行后端合并；最终状态显示“3 张图片已完成 HDR 合并预览”且导出可用。

证据完整性 16/16 通过不代表像素一致。像素报告 16/16 失败，MAE 范围约为 `0.07155` 至 `0.28398`，changed pixel ratio 范围约为 `0.33177` 至 `0.99129`。

### 2.3 Browser 交互合同 v2

活动合同已经一次性替换为 10 个 v2 合同：

1. 照片右键子菜单、评分、旋转、回收站和恢复；
2. 文件夹右键导入和长目录滚动；
3. 工具展开与裁切；
4. 照片切换和隔离历史；
5. 本地预设导入、预览和应用；
6. 图层全生命周期；
7. 遮罩全生命周期；
8. 前后对比、缩放和平移；
9. HDR、Focus、Panorama 三工作流；
10. 导出文件、格式、尺寸、颜色配置和唯一输出。

合同定义本身通过，但 v2 的 Native observation 和 Browser execution 尚未生成，因此最终结果为 0/10，不能使用旧 v1 evidence 代替。

### 2.4 导出和目录功能

- 导出支持 PNG、JPEG、TIFF；
- 支持明确输出宽度和 sRGB profile；
- HTTP 返回宽高、profile 和内容 hash；
- 默认 PNG 原尺寸仍保持 preview/export 一致性；
- 前端导出对话框的格式、宽度和颜色配置均可交互；
- 文件夹导入会持久化真实 collection 归属；
- 上传路径保留原始文件名，不再用 hash 伪装文件扩展名。

### 2.5 真实 Luminar SQLite cutover

通过正在运行的 Luminar Neo 进程定位到真实 catalog：

`/Users/iknow/Library/Group Containers/RTW788AXG3.com.skylum.luminarneo/Space/4413758/4413758.luminarneo`

确认其 SQLite `user_version=155`，并核验 `images`、`paths`、`paths_images`、`image_user_attributes`、`img_history_states`、`image_history_state_proxy` 等真实表及关系。

当前项目已经：

- 使用 `storage/catalogs/luminar_sqlite.py` 作为唯一 catalog repository；
- 生成 `library/catalog.luminarneo`；
- 删除运行时 JSON catalog 读取、写入、fallback 和双写；
- 完成主数据和 UI 隔离数据的一次性迁移；
- 删除迁移后的 `catalog.json`；
- 对错误既有 schema fail closed；
- 保留项目编辑图的 JSON repository，它不是 catalog 兼容层。

迁移工具仅用于一次性离线 cutover，不在运行时自动执行。

## 3. 仍未闭合的精确差距

### 3.1 65 个 model-specific contract

92 个结构合同全部有效，但只有 27 个具备模型专用输入语义、预处理、输出 decode、后处理、正负样本和真实调用 trace。其余 65 个不得因 signature valid、finite output、ORT smoke 或 IR smoke 被标记为 validated。

优先按真实调用依赖分批：

| 批次 | 模型角色 | 必须产物 |
|---|---|---|
| M1 | 人脸、landmark、眼睛、人像分割 | ROI 规则、坐标 decode、NMS、mask resize、正负样本和人像效果 holdout |
| M2 | sky、depth、semantic segmentation | 输入色彩空间、letterbox、类别映射、深度方向和 feather 证据 |
| M3 | denoise、deblur、restoration、upscale | tile/overlap、归一化、颜色恢复、边缘拼接和多尺寸 holdout |
| M4 | relight、LUT、embedding、classification | tensor 含义、label/tokenizer、色彩 profile 和阈值 |
| M5 | OpenVINO-only fallback | ONNX 不可用证据、IR 等价输出、资源释放和独立负样本 |

每个批次完成后必须执行模型合同检查、模型矩阵、对应工具候选和全量回归。ONNX 可用时继续优先 ONNX；OpenVINO 只作为经同一合同验证的兜底。

### 3.2 主效果 9 个失败

旧的 45-case 报告同时包含 `ai_enhance`、`bw_channels`、`default_effects`、`denoise` 和 `sunrays` 各两条重复 capability。当前活动 `cases.json` 是 40 个唯一 capability 的 canonical 集；其中 4 个 case 使用了新的专用 fixture ID。当前 40 个 case ID 已全部用最新源码重新生成，不是通过删除失败 capability 得到 31/40。

阈值保持不变。当前失败为：

| capability | MAE | SSIM | 下一步定位 |
|---|---:|---:|---|
| `face_ai` | 0.030197 | 0.984212 | 人脸 ROI、landmark、肤色保护和局部强度 |
| `depth_volume` | 0.068934 | 0.946598 | 深度方向、归一化、近远景曲线和 feather |
| `lut_mapping` | 0.052734 | 0.996945 | LUT 色彩空间、插值、profile 和 amount blend |
| `magic_lights` | 0.005946 | 0.952913 | 发光区域形态、局部结构和合成顺序 |
| `new_neon_light` | 0.033333 | 0.329152 | 光源 mask、色调映射、衰减和背景保持 |
| `blue_hour` | 0.133379 | 0.914102 | sky/foreground 分离、冷暖映射和亮度曲线 |
| `fog` | 0.113488 | 0.903759 | 深度引导透射率、雾色和空间衰减 |
| `sky_replace` | 0.039682 | 0.973711 | 地平线、sky mask、前景保护和色彩匹配 |
| `sunrays` | 0.053714 | 0.956221 | 光源位置、遮挡、径向衰减和合成 |

校准顺序固定为：先修共享模型/遮罩语义，再修颜色和合成，最后修局部参数。每次修改必须同时运行 calibration fixture、独立 holdout 和全量 40 case；禁止 case ID 分支、reference 读取、最终 resize 或阈值放宽。

### 3.3 扩展 Exact 31 个失败

扩展 Exact 当前 38/69。先把 9 个主效果清零，再按失败的共享根因聚类，避免对 31 个 case 做 31 份特判。每个主效果修复后立即重跑 69 case，记录修复、回退和不受影响的 case 集。

### 3.4 UI 16 个像素失败

校准顺序：

1. 全局 frame：顶栏、左右 rail、面板宽度、canvas 和 filmstrip；
2. 组件几何：padding、gap、字体、行高、图标、圆角和分隔线；
3. 内容合同：文案、顺序、计数、默认选择和素材缩略图；
4. 状态合同：展开、选中、disabled、dialog、busy 和完成态；
5. 色彩管理和 Retina 字体栅格差异；
6. 每次 frontend hash 改变后整套重录 16 个状态。

每批最多修改一个共享壳层或一个组件族，并输出 reference、candidate、diff heatmap 和区域指标。目标保持 `MAE <= 0.03` 且 `changed_pixel_ratio <= 0.02`，不降低阈值。

### 3.5 Native/Browser 10/10

Native 采样必须先确认 Luminar Neo 处于 macOS 全屏；窗口化、系统对话框遮挡或其他应用截图不得进入证据。付费、教程、帮助、升级、账号和商店事件不录制为 required。

执行顺序：

1. 全屏核验 app、版本、build、locale、viewport；
2. 对每个 v2 contract 录制 native before/steps/after、AX、等待条件和最终断言；
3. 在同一 frontend hash 下从独立 fixture 重置执行 Browser 事件；
4. 记录每一步 target、截图、DOM/AX、网络摘要和 API 持久化断言；
5. 10 个合同全部完成后统一发布 execution；旧 v1 的 `edit-toggle-collapse` 记录应从活动 current evidence 删除，不做兼容映射。

## 4. 后续执行批次

### P1：交互证据闭环

- 输入：v2 合同、最终 frontend build、SQLite 隔离目录；
- 工作：Native 全屏 10 个 observation，Browser 10 个 execution；
- 验收：contract_count=10、executed=10、passed=10、issue_count=0；
- 停止条件：任一 native 状态不可稳定复现或 AX 无法定位时保留 blocked。

### P2：模型合同 M1/M2

- 优先关闭人脸、天空和深度依赖；
- 验收：相关模型 model-specific validated、真实候选 trace 指向该模型、9 个主效果至少关闭 `face_ai`、`depth_volume`、`blue_hour`、`fog`、`sky_replace`；
- 不接受统一 wrapper smoke 作为通过。

### P3：模型合同 M3/M4/M5

- 完成 restoration、upscale、relight、LUT、embedding 和 IR fallback；
- 验收：92/92 model-specific validated 或有原生证据证明并非独立活动模型后从注册表删除；pending=0。

### P4：效果收敛

- 主效果 40/40；
- 扩展 Exact 69/69；
- preset、sky、overlay、多图 3/3 不回退；
- preview/export hash 和尺寸合同全部通过。

### P5：UI 像素收敛

- 先全局框架，后组件族，最后状态；
- 当前源码重新录制的 16/16 evidence 与 16/16 pixel gate 同时通过；
- Browser 10/10 evidence 必须绑定相同 frontend build hash。

### P6：最终冻结

1. 冻结 source、model、validation、environment 和 reference fingerprint；
2. 运行 exact run A；
3. 不修改任何输入，运行 exact run B；
4. 用 `scripts/compare_exact_runs.py` 比较两轮；
5. 仅当两轮都是 required failure=0、fingerprint 全等、UI 16/16、交互 10/10、主效果 40/40、扩展 69/69、模型 pending=0 时，才允许声明“冻结的本地核心合同绝对对齐”。

## 5. 当前验证命令

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
cd frontend && npm test -- --run && npm run build

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id <unique-run-id> \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/<summary>.json
```

最终权威证据位于：

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-final-v2-evidence.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/final-v2-evidence-20260828/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-final.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-final-latest-source.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-current-final-latest-source.json`。

## 6. 完成定义

实现和迁移工作已完成不等于产品对齐完成。当前可以准确声明：工程回归通过、SQLite cutover 完成、当前 UI 证据完整、exact 阻塞已被量化；不能声明 UI、交互、模型或效果已经与 Luminar Neo 绝对一致。

只有 P1 至 P6 的硬验收全部满足，且连续两轮 identical-fingerprint exact run required failure 都为 0，本项目才达到本计划定义的完成状态。
