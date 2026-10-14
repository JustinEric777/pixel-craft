# Luminar Neo 1.28 严格对齐执行报告：R9

## 1. 结论

R9 已按当前源码重新执行完整 exact gate。权威结果仍为 `31/35`，4 个 required gate
失败：`output-parity`、`exact-incremental-parity`、`ui-parity` 和
`interaction-execution`。因此当前实现不能声明与本机 Luminar Neo `1.28.0 (23071)`
绝对对齐，也不具备 release A/B 两轮准入条件。

本轮没有降低 `MAE <= 0.03`、`SSIM >= 0.98`、shape match 或 Grain statistical
阈值，没有根据 case id、文件名或 reference hash 增加运行时特判，也没有增加历史
catalog、JSON 双写、旧 schema fallback 或迁移兼容层。

范围继续只包含本地、免费、可重复验证的核心编辑、目录与导出能力。付费、订阅、账号、
商店、教程、帮助、云生成和商业内容不进入 required gate。

权威运行信息：

- run id：`alignment-execution-r9-final-20260829`；
- exact：`31/35`；
- source fingerprint：`c3bcf6a09ebb68baae7ea6aaa349b4bdda2e06d4d4ed0c7e92b678079fbcf7e4`；
- model fingerprint：`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`；
- validation fingerprint：`04b22b3f27cade19cfa3003405c7bacb3cd7d639541342d4f53ee9fc6f47710f`；
- environment fingerprint：`d59fdf4f82c9ffc2adcb409f9dbb2dd73cab69f2c4c5f0ac6ffcf94132a391d8`；
- release fingerprint：`c7bb8c34366413245bc05b0fddb9ea6efb1697e06914d08316ba6542bdba7b36`。

## 2. R8 到 R9 对比

| 域 | R8 | R9 | 变化 |
|---|---:|---:|---:|
| Exact required gate | 31/35 | 31/35 | 失败门数量不变，门内用例继续收敛 |
| 主效果 | 34/40 | 35/40 | Fog 通过，失败 6→5 |
| 扩展 Exact | 51/69 | 56/69 | Grain、Bokeh、Face Enhancer、Fog、Slim People full 通过，失败 18→13 |
| 活动模型合同 | 22/22 | 22/22 | model-specific pending 保持 0 |
| UI current-build execution | 16/16 | 16/16 | 当前 build 采集链完整 |
| UI pixel | 0/16 | 0/16 | 16 个状态仍全部未达到像素阈值 |
| 正式 Browser interaction | 8/10 | 8/10 | Preset 与 Multi-image 正式执行仍缺；旧 8 条存在 viewport/build 问题 |
| Native catalog schema | passed | passed | schema 155 单轨保持精确通过 |
| Python tests | 367 passed | 374 passed | 新增 7 项回归覆盖 |
| Frontend tests | 41 passed | 41 passed | 无回归，production build 通过 |

`31/35` 不代表本轮没有进展。gate 是按域计数，只要一个域仍有任一 required failure，整个
域仍记为失败；主效果和扩展效果的内部通过数分别增加了 1 和 5。

## 3. 本轮实现

### 3.1 Fog

旧实现主要按深度图混合固定雾色，无法表达 Native 的上半帧大气层与主体保护。本轮改为：

- 使用垂直大气 envelope；
- 对人物前景增加保护；
- 对大气 mask 做与画幅相关的平滑；
- 使用 Native 锚点支持的非线性强度响应。

主效果 Fog 和扩展 full Fog 均通过。Depth Volume 没有复用该拟合：现有 depth 输出与 Native
Depth Volume 响应相关性不足，强行套用垂直位置函数只会对当前 fixture 过拟合。

### 3.2 Bokeh AI、Face Enhancer、Slim People

同图 Native `0.4` 与 `1.0` 锚点表明三项能力在 `0.4` 后基本饱和。本轮将实际效果强度限制在
该饱和点，同时保留 `amount=0` identity。新增测试覆盖 zero、smoke、full 关系，三项 full
exact 均通过。

### 3.3 Grain

保留 `0.4` 已通过锚点；对 `0.4→1.0` 上段校准噪声方差和轻微通道偏置。full comparator
重新达到原有 statistical 阈值，没有修改比较器阈值，也没有使用随机 fixture 特判。

### 3.4 拒绝的不安全修改

以下尝试没有进入代码：

- Depth Volume 的仅位置拟合：现有深度图与 Native response 相关性不足；
- Blue Hour 的 sky-fraction 修正：改善 sky-rich 当前图时会使两张非天空 holdout 回归；
- Face AI 的单 mask 参数扫描：无法跨锚点稳定改善；
- Structure AI、Landscape Enhancer 的单一 direction/amount 缩放：全尺寸仍不能通过。

这些拒绝项体现了当前边界：不能为关闭某一个红色 case 破坏独立 holdout。

## 4. 当前精确遗漏

### 4.1 主效果：35/40

| Capability | MAE | SSIM | 下一结构动作 |
|---|---:|---:|---|
| Face AI | 0.030175 | 0.984125 | 重建 face/skin/eye 局部 mask 与颜色响应，MAE 仅超 0.000175 |
| Depth Volume | 0.069188 | 0.960300 | 获得 Native 深度分层真值，替换当前错误的 depth-response 映射 |
| Blue Hour | 0.039456 | 0.975336 | 将天空、前景、亮部保护拆分，并用跨照片锚点拟合 |
| Sky Replace | 0.039682 | 0.973711 | 联合校准 sky mask、horizon、edge、relight 和颜色匹配 |
| Sunrays | 0.053714 | 0.956221 | 重建光源定位、遮挡、径向衰减和 bloom |

Fog 已从 R8 的 `MAE=0.113488 / SSIM=0.903759` 转为通过。

### 4.2 扩展 Exact：56/69

剩余 13 个失败，涉及 11 个 capability：

| Capability / anchor | MAE | SSIM |
|---|---:|---:|
| Default Effects `+1.0` | 0.201182 | 0.643019 |
| Default Effects `-1.0` | 0.043264 | 0.018253 |
| Face AI `1.0` | 0.039460 | 0.968162 |
| Face AI `0.5` | 0.048759 | 0.963466 |
| Sunrays `1.0` | 0.133299 | 0.798667 |
| Structure AI `1.0` | 0.039660 | 0.980043 |
| AI Enhance `1.0` | 0.061526 | 0.951811 |
| Vignette `+1.0` | 0.122094 | 0.818667 |
| Vignette `-1.0` | 0.141082 | 0.777095 |
| Depth Volume `1.0` | 0.140078 | 0.841479 |
| Blue Hour `1.0` | 0.072455 | 0.848761 |
| Radiance `1.0` | 0.057293 | 0.984737 |
| Landscape Enhancer `1.0` | 0.046846 | 0.986967 |

其中 Structure、Radiance、Landscape 的 SSIM 已过线但 MAE 未过线；仍必须修实现，不能只选
更宽松的指标。Default Effects negative 的候选为黑色而 Native 不是 identity/纯黑，是优先级很高的
参数语义缺陷。

### 4.3 模型合同

活动 registry 当前为 `22/22 validated`、pending `0`，模型 exact contract gate 通过：

- validation matrix：16 个 `inference-validated`，6 个 `ort-smoke-passed`；
- role：16 个 `active-invoked`，6 个 `configured-not-covered`；
- contract audit：22 个 normalization/postprocess 均 model-specific validated；
- 20 个模型不需要 source-backend parity，Human/Iris Landmarks 仍标记
  `pending-compatible-openvino-runtime`；
- 22 个模型的 `luminar_effect_parity` 仍为 `pending-reference`。

因此“65 个 model-specific pending”的旧阻塞已经关闭，但模型合同通过不能替代最终效果像素通过。
ONNX 仍为首选，只有存在兼容 IR 与可验证运行时时才使用 OpenVINO 兜底。

### 4.4 UI：执行证据通过，像素 0/16

当前 build 已具备 16/16 screenshot、DOM、AX、步骤和 build hash 绑定，执行证据 gate 通过；
但 16 个状态与 Native 参考全部未达像素阈值，MAE 范围为 `0.031498→0.186925`。问题最高的
状态为 multi-image-complete、catalog 和 denoise-level-selected。

后续必须先校准共享 shell、字体、颜色、主画布和面板几何，再逐状态校准内容。不能再次把
“候选采集成功”表述为“UI 对齐成功”。

### 4.5 交互：8/10

正式验证器报告 5 个问题：

1. `viewport-contract-mismatch`；
2. `stale-frontend-build`；
3. Preset 缺 Native observation；
4. Preset 缺 Browser execution；
5. Multi-image 缺正式 Browser execution。

仓库与本机已检查范围内没有真实、可由 Luminar 导入的 `.lnp/.lnpc` collection 可用于正式
Preset 合同；不生成伪包。UI 尚需大量修改，所以旧 8 条现在重录也会在前端冻结后再次过期。
正式 Browser 10/10 必须在最终 frontend hash 下统一重录。

### 4.6 Native 采样环境

Computer Use 使用共享 macOS 桌面和输入设备，当前没有可靠的隔离虚拟显示器/鼠标。按用户约束，
本轮没有操作共享指针，也没有重新采集 Native。未来只有在 Luminar 全屏且输入隔离得到确认时才允许
采样；否则保持证据状态不变。

### 4.7 SQLite catalog

真实 Luminar catalog schema exact gate 继续通过：schema version `155`、29 个 schema objects、
26 张表，结构 SHA-256 为
`7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79`。
运行时保持 SQLite 单轨，`compatibility_layers=[]`，没有 JSON/SQLite 双写或历史兼容逻辑。

## 5. 下一步严格执行顺序

1. **效果真值补全**：在满足全屏与隔离输入条件后，优先采集 Default Effects、Depth Volume、
   Sunrays、Vignette 的同图 zero/0.25/0.5/0.75/1.0、负向端点及跨照片 holdout；同时保存语义
   mask、光源、horizon 或 depth 的可推导观察证据。
2. **主效果结构闭环**：依次处理 Face AI、Depth Volume、Blue Hour、Sky Replace、Sunrays；每项先跑
   targeted，再跑 40-case 回归。任何 holdout 回归均回退该修改。
3. **扩展效果闭环**：先修 Default Effects 与 Vignette 的参数语义，再处理 Structure、AI Enhance、
   Radiance、Landscape；每项必须覆盖 zero/mid/full 和至少一张独立图片。
4. **UI 公共层校准**：先共享 shell、字体、颜色 token、panel geometry、canvas crop，再按
   multi-image-complete→catalog→denoise→其余状态修复；每批重跑完整 16 状态。
5. **真实 Preset 证据**：取得由本机 Luminar 真实导出/可导入的 collection 后，才执行 Native
   full-screen observation；没有真实包时保持 blocked。
6. **最终交互重录**：前端冻结后，以统一的 logical viewport、DPR 和 physical viewport 重录
   Browser 10/10，保存截图、DOM/AX、network、console、API readback 和 export hash。
7. **单轮 exact**：只有主效果 40/40、扩展 69/69、UI 16/16、交互 10/10 时，exact 才可能
   达到 35/35。
8. **双轮发布门禁**：在 source/model/validation/environment/reference fingerprint 完全相同的
   条件下独立执行 A/B 两轮；两轮 required failure 都为 0 后才允许声明绝对对齐。

## 6. 验证结果

- `.venv/bin/ruff check .`：passed；
- `.venv/bin/pytest -q`：374 passed，1 个第三方 deprecation warning；
- `npm test -- --run`：41 passed；
- `npm run build`：passed；
- exact gate：31/35，blocked。

## 7. 权威证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r9-final-20260829.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/parity-report.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/exact-incremental-parity.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/ui-parity.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/interaction-execution.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/model-validation-matrix.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/model-contract-audit.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r9-final-20260829/luminar-catalog-schema.json`。
