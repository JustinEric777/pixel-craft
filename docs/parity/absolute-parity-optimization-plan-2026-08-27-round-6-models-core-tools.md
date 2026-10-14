# Luminar Neo 1.28 全模型与核心工具绝对对齐可执行优化计划（第六轮）

> 目标参考：本机 `/Applications/Luminar Neo.app`，版本 `1.28.0 (23071)`，`zh-Hans`，macOS。  
> 资产旁证：`/Users/iknow/Downloads/LuminarNeo-1.28.0.17626-x64-Portable/Luminar Neo/App`。  
> 本轮重点：全部 92 个模型、图层、遮罩、天空替换、降噪、锐化，以及 HDR Merge、Focus Stacking、Panorama Stitching 三类多文件合并；同时闭合 UI、交互和效果门禁。

## 1. 执行结论与总原则

当前项目已经具备可运行的前后端、完整本地素材、基础模型注册、图层栈、天空合成和三类多图工作流，但仍不能声明与 Luminar Neo 绝对对齐。第六轮不应继续做零散样式修补，而应把产品行为拆为六条可独立验证、最终汇合的闭环：

1. **92/92 模型闭环**：每个模型都必须有明确输入、预处理、推理、后处理、终态结果、资源释放和消费者；不再把 66 个 pending 留作长期可选项。
2. **遮罩成为一等编辑对象**：统一 AI 遮罩、画笔遮罩、工具遮罩、图层遮罩和天空遮罩的数据与合成语义。
3. **图层成为完整工作流**：素材、层栈、属性、变换、混合、遮罩、历史、导出和交互证据全部闭合。
4. **天空、降噪、锐化逐链路对齐**：分别校验模型中间产物和最终效果，避免只看最终图而无法定位误差。
5. **三类多图工作流分别验收**：HDR 和 Focus 保持通过并补齐真实交互；Panorama 重建几何核心，禁止用最终 resize 模拟原生投影。
6. **UI、交互、效果和模型统一发布门禁**：只有全部 required gate 连续两轮通过，才允许使用“绝对对齐”结论。

本计划是执行计划，不修改现有 reference、case、阈值或素材。所有实现工作都必须按“单批次、单根因、可回滚、可量化”推进。

## 2. 权威基线与已确认遗漏

### 2.1 第五轮权威基线

权威结果以以下产物为准：

- `docs/parity/absolute-parity-execution-report-2026-08-27-round-5.md`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-5-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-round-5-final.json`

| 验收域 | 当前结果 | 本轮终态 |
|---|---:|---:|
| Exact 综合门禁 | 22/28；5 个 required、1 个 optional 失败 | required 0 failure，optional 0 failure，连续两轮稳定 |
| 主效果 | 29/40 | 40/40 |
| Exact 效果 | 38/69 | 69/69 |
| UI 当前构建执行证据 | 16/16 | 保持 16/16、issue 0 |
| UI 像素对齐 | 0/16 | 16/16 |
| Browser 交互合同 | 1/10 | 10/10 |
| 多图工作流 | 2/3 | 3/3 |
| 模型专用合同 | 26/92 | 92/92 |
| Python / Frontend | 305 / 24 passed | 全部保持通过且新增测试通过 |

当前 required 阻断项为：`multi-image`、`output-parity`、`exact-incremental-parity`、`ui-parity`、`interaction-execution`。`model-contract-inventory` 当前虽标记 optional，但本轮完成标准中将升级为 required。

### 2.2 诊断产物命名漂移

`quality-gates-round-5-final.json` 的实际执行结果为主效果 `29/40`，而后生成的 `parity-report-current-final.json` 显示了另一组 `36/45` 统计。两者的 case 集和生成时点不同，不能混用。

第六轮 P0 必须先建立唯一 canonical 别名和 run id：

- 每次门禁生成不可覆盖的 `round-6-run-N` 产物；
- `*-current.json` 只能由已完成的同一 run 原子更新；
- convergence、candidate invocation、UI、interaction 和 multi-image 必须记录同一个 `run_id`；
- 报告统计只能从该 run 的质量门禁引用，禁止手写数字。

### 2.3 全模型真实状态

`configs/model.yaml` 当前注册 92 个模型：

- ONNX Runtime：50；
- OpenVINO：42；
- `inference-validated`：27；
- `ort-smoke-passed`：23；
- `ir-registered-runtime-pending`：41；
- `runtime-blocked-nonfinite`：1，模型为 `convnextv2_multiclass`。

按任务族统计：

| 任务族 | 数量 | 任务族 | 数量 |
|---|---:|---|---:|
| super_resolution | 12 | skin_segmentation | 7 |
| semantic_segmentation | 6 | human_analysis | 4 |
| depth_estimation | 4 | sky_segmentation | 4 |
| wire_segmentation | 4 | animal_segmentation | 3 |
| dust_detection | 3 | face_analysis | 3 |
| interactive_segmentation | 3 | face_detection | 2 |
| face_restoration | 2 | hair_segmentation | 2 |
| horizon_alignment | 2 | image_classification | 2 |
| iris_landmarks | 2 | light_detection | 2 |
| portrait_bokeh | 2 | saliency_segmentation | 2 |
| 其余 20 个单模型任务族 | 20 | 合计 | 92 |

现有 `candidate-model-invocations.json` 虽然 `19/19` 调用通过，但只覆盖 16 个逻辑模型；仍有 33 个 configured-not-covered、32 个 inventory-unmapped。它证明当前少量产品路径没有漏调用，不能证明 92 个模型均已正确推理。

### 2.4 图层和遮罩遗漏

图层当前已具备选中、显隐、不透明度、混合模式、翻转、映射、素材添加和拖拽重排，但仍缺：

- `LayerInspector` 的“遮罩”页签是禁用占位，没有实际遮罩 UI；
- 没有每层 mask 引用、mask thumbnail、显示/隐藏/反转/羽化/密度；
- 没有在画布上画笔增减、AI 选区、擦除、快捷键和 overlay 可视化；
- 没有统一 layer transform 的真实 Neo 语义和画布手柄；
- 图层删除、遮罩、undo/redo、导出结果尚未形成正式 Browser 合同；
- 素材图片已对齐文件，但分组顺序、命名、首屏可见范围和添加后默认 blend/transform 仍需原生逐状态确认。

后端 `EditNode.mask_artifact` 目前主要保存字符串引用；它还不是一个带版本、尺寸、来源、编辑操作和生命周期的可验证遮罩对象。

### 2.5 天空替换遗漏

现有链路已包含天空 mask、前景保护、天空纹理 fit、颜色调整、边缘、倒影和前景重光基础，但主效果 `sky_replace` 仍失败，当前误差为 MAE 约 `0.0643`、SSIM 约 `0.9469`。需要补齐或确认：

- `improved_sky_segmentator_v462_i8`、`horizon_align_i8`、`skyinwater_v16_i8`、人物/显著物体保护模型的实际调用与中间产物；
- 原生地平线几何、scale、vertical/horizontal offset、flip 和 rotation 的坐标语义；
- global、horizon blending、fix gaps、edge refinement 的 mask 运算顺序；
- foreground relight、saturation、human relight、reflection 的区域与强度；
- atmosphere、temperature、brightness、blur、grain 的色彩空间和处理顺序；
- 43 个本地天空素材的 UI 顺序、缩略图、默认项、asset id 和最终纹理文件映射。

### 2.6 降噪和锐化遗漏

降噪现状：

- UI 已要求用户选择低/中/高；
- 模型为 `model_luminocity_denoise`；
- pipeline 当前通过简单 level factor 调节 amount；
- 主效果和 Exact 均有失败，主效果 MAE 约 `0.0366`；
- 当前只明确了亮度去噪模型，尚未证明 Neo 对低/中/高的模型选择、噪声估计、色度处理、tile overlap、边缘 padding、细节恢复和混合曲线。

锐化现状：

- 产品能力名为 `deblur`，UI 名称为“超锐 AI”；
- 模型为 `srn_deblur_512`；
- 当前参数 schema 只有 `amount`、`opacity`，没有原生“低/中/高”和模糊类型选择合同；
- 需要确认本机 Neo 当前版本实际显示的档位、按钮、默认值、处理进度、preview/export 行为，再决定扩展参数，不能只把 deblur 模型输出按 amount 混合。

### 2.7 三类多文件合并遗漏

- HDR：当前 parity 通过，但算法只是平均融合、gamma 和固定增益；缺少排序、对齐、去鬼影、曝光权重、色调映射和原生选项合同。
- Focus Stacking：当前 parity 通过，但主要是梯度 winner-take-all；缺少帧对齐、focus map 平滑、遮挡和边缘 seam 合同。
- Panorama：当前失败，MAE `0.0819413`、SSIM `0.8155414`；当前只做 overlap 平移搜索、线性 feather 和最终 resize，缺少特征、RANSAC、投影、warp、曝光补偿、seam 和有效区域裁切。

## 3. 最终成功标准

### 3.1 全局硬门禁

1. `output-parity`：40/40。
2. `exact-incremental-parity`：69/69。
3. `ui-parity`：16/16；shape、MAE 和 changed-pixel-ratio 均满足现有阈值。
4. `interaction-execution`：10/10；每个合同均有原始事件、截图、API readback 和 console/network 状态。
5. `multi-image`：HDR、Focus、Panorama 3/3。
6. `model-contract-inventory`：92/92 model-specific validated，0 pending，0 blocked。
7. 所有模型有 deterministic terminal result：成功输出或经证据确认的不可运行阻断；发布目标要求最终 0 阻断。
8. Exact 综合 required gate 连续两轮 0 failure，关键候选输出 hash 稳定。

### 3.2 模型单体通过条件

每个模型同时满足以下条件才可从 pending 改为 validated：

- 注册 id、logical id、backend、模型文件和 SHA-256 一致；
- wrapper 是独立 `BaseInference` 子类，未使用通用占位 wrapper；
- 输入名、shape、dtype、dynamic axis、色彩空间、通道顺序和数值范围已验证；
- resize、crop、letterbox、padding、归一化和 batch 语义已版本化；
- 输出名、shape、dtype、数值范围、finite、坐标系和类别语义已验证；
- sigmoid/softmax、阈值、NMS、resize-back、mask class 和颜色反变换已验证；
- canonical fixture 上有实际 inference、结果摘要、输入/输出 hash 和重复运行一致性；
- load、lease、LRU、unload 和异常清理有测试证据；
- ONNX/OpenVINO 双后端变体在同一 logical id 下有差异报告；
- 直接消费模型的能力有中间产物与最终效果对齐；不直接产图的分析模型有独立语义标注验收。

### 3.3 核心功能通过条件

| 功能 | 必须通过的层面 |
|---|---|
| 图层 | UI 几何、素材、层栈顺序、显隐、opacity、blend、transform、mask、history、preview/export、Browser 合同 |
| 遮罩 | AI/brush/edit/layer/sky 统一 schema；画布编辑；合成；反转/羽化/密度；undo/redo；导出一致 |
| 天空替换 | 43 个素材映射；5 模型链；mask/地平线/倒影/前景保护；全部控件；preview/export parity |
| 降噪 | 低/中/高状态；模型输入输出；亮度/色度/细节；tile seam；UI/交互；主/Exact parity |
| 锐化 | 原生档位和类型；模型输入输出；边缘/halo；tile seam；UI/交互；主/Exact parity |
| HDR | 选帧、排序、对齐、去鬼影、融合、色调、预览、导出 |
| Focus | 选帧、排序、对齐、focus map、seam、预览、导出 |
| Panorama | 选帧、顺序、特征、RANSAC、投影、warp、曝光、seam、crop、预览、导出 |

## 4. 不可破坏规则

1. 唯一主参考为 `luminar-neo-macos-1.28.0-23071`；Portable 只用于本地素材和 Windows 包结构旁证。
2. 不降低 `configs/parity.yaml` 阈值，不替换 reference，不删除失败 case，不改变 comparator 以制造通过。
3. 运行时代码不得读取 case id、reference path、reference hash、失败列表或 fixture 名选择算法。
4. 不用最终强制 resize、硬编码某张图 crop、单 case LUT 或全局颜色偏移掩盖几何/模型错误。
5. 模型文件只从本地 `models/` 和已批准本地路径加载；不得隐式下载权重或依赖网络。
6. 不直接复制 Portable `PresetPacks` 的全部内部文件；必须先建立语义索引与许可边界。
7. UI build hash 变化后，旧 Browser screenshot 和 interaction execution 失效，必须重录。
8. 一个批次只解决一个根因族；每批都有 before、after、holdout、回归和回退点。
9. 修改 `ai/model` 仅用于 wrapper 的输入、输出、生命周期契约；组合与强度问题留在 pipeline/compositor。
10. 任一阶段出现 reference/input/hash 漂移时立即停止，不继续生成候选。

## 5. 阶段依赖与执行顺序

```text
P0 统一 run、冻结输入和源码 manifest
 │
 ├── P1 模型验证基础设施与 92 模型矩阵
 │     ├── P2 遮罩模型与统一遮罩平台
 │     │     ├── P3 图层 + 图层遮罩
 │     │     └── P4 天空替换完整链路
 │     ├── P5 降噪完整链路
 │     └── P6 锐化完整链路
 │
 ├── P7 HDR / Focus / Panorama
 │
 └── P8 其余模型族 92/92 闭环
       │
       ▼
P9 UI 16 状态 + Browser 10 合同
 │
P10 主效果 40/40 → Exact 69/69
 │
P11 全量回归、素材复核、双轮发布门禁
```

允许并行分析但不允许交叉提交的部分：P5、P6、P7 可在 P1 基础设施稳定后分别推进；P3 必须依赖 P2 的 mask schema；P4 必须复用 P2 的 mask 语义。

## 6. P0：统一基线、run id 与变更边界

### 6.1 修改目标

- 消除 `29/40` 与 `36/45` 等诊断统计漂移；
- 修复第五轮缺失 before source manifest 的证据链；
- 确保所有第六轮产物属于同一次运行。

### 6.2 实施步骤

1. 新增只读源码 manifest 脚本，覆盖 `ai/`、`api/`、`configs/`、`frontend/src/`、`image_ops/`、`services/`、`storage/`、`scripts/`、`tests/`、`models/contracts/`。
2. manifest 排除模型二进制、candidate 输出、build 和 cache，只记录路径、size、SHA-256。
3. 在 `run_quality_gates.py` 生成 `run_id`，传递或写入每个子报告。
4. 每个报告保留不可覆盖的 `round-6-run-01.json`；全部完成后再原子更新 `current.json`。
5. 生成 P0 before：源码 manifest、环境、素材、采样、模型目录、质量门禁、convergence failures。
6. 对 `255/255 ready` 队列和 `40 + 69 + 16 + 10 + 3` 验收集做 hash 固定。

### 6.3 入口文件

- `scripts/run_quality_gates.py`
- `scripts/build_convergence_baseline.py`
- `scripts/validate_sampling_data_chain.py`
- `configs/reference.yaml`
- 新增 `scripts/build_source_manifest.py`

### 6.4 准出条件

- 同一 run 的所有报告 `reference_id`、`run_id`、source manifest hash 一致；
- 权威主效果统计唯一为 40 case；Exact 唯一为 69 case；
- before manifest 可重建且执行后不会被误写；
- P0 不修改算法或 UI。

## 7. P1：全模型验证基础设施与 92 模型矩阵

### 7.1 先建立机器可读矩阵

新增 `model-validation-matrix.json`，每个模型至少包含：

- `id`、`logical_id`、task、backend、format；
- model/weights path 和 SHA-256；
- wrapper class；
- input/output signature；
- preprocess/postprocess version；
- canonical fixture id 与适用理由；
- runtime status、repeatability status、backend parity status；
- capability consumers；
- intermediate artifact type；
- Luminar reference 类型：mask、map、boxes、embedding、restored image、final effect；
- owner batch、blocked reason、validation evidence path。

同时把 `configured-not-covered` 和 `inventory-unmapped` 变成显式待处理队列。`inventory-unmapped` 不能自动删除：先判断是原生保留模型、替代 backend、未接入能力还是确实冗余。

### 7.2 增强统一模型合同

对 `BaseInference`、factory、registry、loader 只做必要增强：

- `InferenceResult.metadata` 记录 wrapper version、backend、input/output contract version、artifact hash；
- wrapper 统一声明 source color space 和 output semantic type；
- loader health 输出真实或实测峰值内存，不再只依赖统一 `512 MB` 估计；
- 明确同一 logical model 的 backend 选择和 fallback 原因；
- 加入 deterministic seed/context，只对有随机节点的模型生效；
- unload 后验证 session、compiled model 和缓存释放；
- 异常不得返回“ready”或静默 fallback 到占位结果。

### 7.3 模型验证批次

| 批次 | 范围 | 关键验收 |
|---|---|---|
| M1 | 27 个 inference-validated | 冻结合同，补 backend/effect reference，不回归 |
| M2 | 23 个 ORT smoke | 补真实 preprocess/postprocess 和语义输出，禁止只检查 finite/shape |
| M3 | 41 个 OpenVINO pending | 在本地 OpenVINO 真实 compile + inference + unload，补对应 ONNX 差异 |
| M4 | `convnextv2_multiclass` | 定位非有限输出发生在 preprocess、runtime 还是 postprocess；修复后与 ONNX 变体对比 |
| M5 | 32 个 inventory-unmapped | 建立消费者或明确“仅库存/后端变体”的合法状态，禁止无归属 |
| M6 | 33 个 configured-not-covered | 为真实产品能力建立 candidate case 和 invocation trace |

### 7.4 每个模型的验证顺序

1. 静态文件和 hash；
2. runtime signature；
3. 独立 preprocess golden；
4. 原始 runtime outputs；
5. postprocess golden；
6. repeat run；
7. unload/reload；
8. backend pair；
9. capability invocation；
10. Luminar 中间/最终 reference。

任何一步失败都保留 terminal failure artifact，不得以空数组、全零 mask 或原图回退冒充成功。

### 7.5 修改和测试入口

- `ai/model/base_inference.py`
- `ai/model/factory.py`
- `ai/model/loader.py`
- `ai/model/registry.py`
- 各 `ai/model/onnx/**`、`ai/model/openvino/**` wrapper
- `models/contracts/*.json`
- `configs/model.yaml`
- `tests/test_model_loader.py`
- `tests/test_model_outputs.py`
- `tests/test_active_model_contracts.py`
- `tests/test_candidate_model_invocations.py`
- `scripts/model_probe.py`
- `scripts/check_model_contracts.py`
- `scripts/audit_model_pipelines.py`

### 7.6 准出条件

- 92/92 wrapper 可动态实例化；
- 92/92 model-specific contract validated；
- 92/92 有 canonical terminal result、重复运行和 unload 证据；
- 42/42 OpenVINO 不再处于 `runtime-pending`；
- 0 非有限输出；
- 0 configured-not-covered、0 inventory-unmapped，或每项有经门禁认可的非产品库存状态；
- `model-contract-inventory` 从 optional 升为 exact required。

## 8. P2：统一遮罩平台

### 8.1 统一数据模型

将当前字符串式 `mask_artifact` 扩展为版本化对象，建议最小字段：

```text
MaskArtifact
  id, version, project_id
  owner_type: edit | layer | sky | workflow
  owner_id
  width, height, dtype=float32, range=[0,1]
  source: brush | ai | gradient | luminosity | imported
  model_id, preprocess_version, postprocess_version
  inverted, density, feather
  raster_path, preview_path, sha256
  operations[], created_at, updated_at
```

必须保持老项目可迁移：旧字符串引用读入后转换为默认 `version=1`，保存时写新 schema；不能破坏已有 edit history。

### 8.2 合成语义

统一 mask pipeline：

1. source mask 读取；
2. resize-back 到原图坐标，禁止多次缩放；
3. add/subtract/intersect；
4. refine edge；
5. feather；
6. density；
7. invert；
8. effect/layer alpha；
9. preview/export 使用同一 mask artifact 和同一运算顺序。

明确禁止：概率输出重复 softmax、uint8 多次量化、preview 与 export 各自重跑不确定模型、遮罩尺寸与画布尺寸隐式错配。

### 8.3 AI 遮罩能力

接入并分别验证：

- `SegmentAnything`：交互点/框输入和 decoder 输出；
- `MulticlassSegmentationV2`：天空、人物、建筑、植物、水等类别；
- salient/portrait/hair/skin/animal/transport/wire 系列模型；
- AI 结果必须显示为可编辑初始 mask，不是不可修改最终结果。

### 8.4 前端画布与面板

实现与 Neo 对齐的遮罩页：

- 画笔、擦除、AI 遮罩、渐变/径向入口以本机实际 UI 为准；
- 画笔 size、softness、strength；
- add/subtract 模式；
- overlay 颜色、开关和快捷键；
- invert、clear、copy/paste；
- feather/density；
- mask thumbnail 和计算中/失败状态；
- pointer capture、zoom/pan 下坐标转换；
- 每个 stroke 合并为一个 undo step，不能每个 pointermove 产生历史节点。

### 8.5 API 与存储入口

- `api/http/schemas.py`
- `api/http/router.py`
- `services/editor/service.py`
- `storage/` 的项目与 artifact 存储
- `image_ops/effects/graph.py`
- `frontend/src/api.ts`
- 新增 `frontend/src/components/MaskPanel.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`

### 8.6 测试与准出

- mask schema migration；
- add/subtract/intersect/invert/feather/density 数值 golden；
- 不同画布缩放下 stroke 坐标一致；
- preview/export mask hash 一致；
- layer mask 与 edit mask 分离；
- undo/redo、project reload、export 保持；
- AI mask 模型不可用时显示明确失败，不回退全图；
- Browser 完成“创建 AI mask → 画笔减去 → 反转 → undo/redo → 导出”合同。

## 9. P3：图层、图层素材和图层交互严格对齐

### 9.1 原生状态采集

先在本机 Neo 固定采集以下状态，不凭记忆改 UI：

1. 仅原图；
2. 打开层素材库；
3. 每个首屏素材分组；
4. 添加素材后的默认 transform、blend、opacity；
5. 两层和三层栈；
6. hover、selected、hidden、dragging；
7. 摘要资讯页；
8. 遮罩页；
9. 画布 transform 手柄；
10. 删除确认/直接删除行为；
11. undo/redo 后层栈；
12. reload 和 export 后状态。

### 9.2 素材语义对齐

现有 234/234 overlay 文件 SHA 一致，下一步验证：

- material id → 文件 → preview → full texture 一一映射；
- 分组顺序、分组名称、项目数、`preview_limit` 和首屏顺序；
- 透明通道、EXIF orientation、色彩 profile；
- 加入层后的默认 blend mode、stretch/fit、opacity；
- 不把 thumbnail 当成 render texture；
- 加载失败有错误状态，不出现黑块或无限大图片。

### 9.3 图层渲染与状态

扩展 layer schema：

- 保持 `visible`、`opacity`、`blend_mode`、flip、scale、rotation、offset；
- 增加明确的 mapping mode、anchor、mask artifact id；
- 确认层栈数据顺序与视觉顺序，只在一个边界做 reverse；
- blend 在正确色彩空间运算；
- alpha、透明 PNG、premultiplied alpha 行为一致；
- transform 在原图坐标完成，preview/export 共用；
- source/background 层不可被错误删除或重排。

### 9.4 UI 和交互

- 左侧保持无错误竖线；
- 76 px layer rail、52 px thumbnail、204 px library 作为当前起点，再按 native region diff 微调；
- pointer reorder 加入 drag threshold、capture、插入指示、取消和键盘可访问路径；
- opacity 拖动时实时 preview，pointer up 合并 history；
- blend、flip、mapping 每次产生可撤销 edit；
- “遮罩”页签不再 disabled，使用 P2 统一 MaskPanel；
- 删除在隔离测试项目执行并完成正式合同，不影响用户正常项目。

### 9.5 准出条件

- `layer-stack`、`layer-library` 和 layer inspector 对应 UI case 通过；
- `layer-add-reorder-opacity-delete` Browser 合同通过；
- 添加、重排、隐藏、opacity、blend、transform、mask、undo/redo、reload、export 全部有 API readback；
- 234 个素材可加载且缩略图/渲染源无错配；
- 图层专项测试覆盖所有 blend mode 和透明素材。

## 10. P4：天空替换完整链路

### 10.1 模型链拆分验收

按中间产物逐级保存和对比：

1. dedicated sky probability mask；
2. horizon position/angle；
3. sky-in-water reflection mask；
4. human/clothes/salient foreground protection mask；
5. refined composite alpha；
6. fitted sky texture；
7. relit foreground；
8. reflected water；
9. final preview/export。

每级记录 model id、pre/post version、shape、range、mean、histogram、artifact hash。最终误差必须能回溯到某一级，禁止直接对最终图做无依据参数搜索。

### 10.2 几何对齐

- 以模型 horizon 为基准，确认 UI 地平线参数是绝对值、相对 offset 还是 texture anchor；
- 统一 horizontal/vertical offset、scale、flip、rotation 的顺序；
- texture cover 与有效天空区域的 crop 规则需通过棋盘格和方向标记素材测试；
- reflection 使用地平线/水面几何翻转，不是整张 texture 的简单上下翻转；
- 禁止用 reference 尺寸常量或单张图 horizon 常量。

### 10.3 遮罩与融合

- sky global、fix gaps、edge refinement、horizon blending 分别建立合成单测；
- 细树枝、屋顶、电线、人物、头发、水面的区域 crop 单独比对；
- 保护 mask 的优先级和组合模式由本机原生状态确认；
- 避免 `MaxFilter + GaussianBlur` 作为所有图的固定近似，改为与控件对应的可解释算子。

### 10.4 色彩和重光

- brightness/temperature/saturation/contrast 在明确色彩空间执行；
- atmospheric haze、blur、grain 只作用于天空纹理；
- foreground relight 从天空统计或原生拟合关系推导，不用全局色偏；
- human relight 只在人物保护区域；
- preview 和 export 共享同一模型 artifact，避免两次推理差异。

### 10.5 素材和 UI

- 保持 43/43 天空原文件 hash 对齐；
- 建立固定 asset semantic index：类别、显示名、顺序、preview、texture；
- `SkyControls.tsx` 的五个 section、默认展开状态、slider 范围、步长、默认值全部从 native readback 固定；
- 添加 loading、失败、无天空、无遮挡、重算状态；
- 采集选择素材、调整地平线、mask refine、relight、reflection 的正式交互证据。

### 10.6 入口与准出

入口：

- `ai/pipeline/model_service.py`
- sky/horizon/water/foreground 对应 wrappers
- `image_ops/effects/sky_compositor.py`
- `image_ops/effects/graph.py`
- `services/editor/service.py`
- `frontend/src/components/SkyControls.tsx`
- 天空 asset registry 与 API
- `tests/test_sky_compositor.py`
- `scripts/diagnose_sky_composite.py`
- `scripts/run_sky_e2e_validation.py`

准出：sky E2E gate 通过、主 `sky_replace` 通过、相关 Exact case 通过、43 个素材映射全通过、模型 invocation trace 完整。

## 11. P5：降噪严格对齐

### 11.1 先确认原生产品合同

固定采集低/中/高三档：

- 按钮 identifier、显示文本、默认选择和 disabled 状态；
- 每档触发的模型/配置、处理时长和缓存行为；
- 0/25/50/75/100 amount；
- 不同 ISO、亮度噪声、色度噪声、纹理和暗部样本；
- before/after、preview/export、undo/redo、重开项目。

### 11.2 模型和 pipeline

验证 `model_luminocity_denoise`：

- 输入亮度通道来自 RGB、linear RGB、Lab 还是 YCbCr；
- 输入分辨率、tile size、padding、overlap 和 stitching；
- 模型输出是去噪亮度、残差还是权重；
- overshoot clip 位置；
- 色度降噪是否为独立确定性算子；
- 低/中/高是不同预处理、强度曲线还是不同模型；
- amount 和 opacity 的合成顺序。

重构目标是“级别 profile + 统一 tile runner + 色彩恢复 + amount blend”，不允许只用 `0.65/0.85/1.0` 之类未经原生证据确认的 factor。

### 11.3 质量比较

除全图 MAE/SSIM 外，增加只用于诊断、不替代正式门禁的指标：

- 平坦区域噪声标准差；
- 边缘保留率；
- 高频能量；
- chroma residual；
- tile seam 最大差；
- 暗部和肤色 ROI。

### 11.4 UI 和交互

- 保持进入工具后必须明确选档的原生行为；若 native 有默认档则按 native 修正；
- 档位切换、处理中、取消、失败和缓存命中状态；
- slider 实时/延迟执行时机；
- before/after、undo/redo、history 节点名称；
- UI `denoise-level-selected` 像素 case 和交互合同通过。

### 11.5 准出条件

- 低/中/高各自有独立 reference 和 holdout；
- 模型 contract validated，invocation trace 和 artifact hash 完整；
- 主 denoise case 与 Exact denoise case 均通过；
- 4K tile seam 为 0 或低于固定诊断阈值；
- preview/export 一致，无颜色漂移、边缘 halo 和纹理塑料化回归。

## 12. P6：锐化 / 超锐 AI 严格对齐

### 12.1 先解决产品命名和参数合同

本机原生采集确认：

- `Supersharp` 是否有低/中/高；
- 是否有 motion blur、defocus、universal 等类型；
- 默认项、按钮 identifier、处理时机和可取消行为；
- 原生 UI 与 API 内部能力名的映射。

在确认前不扩展 schema。确认后将 `deblur` 参数从笼统 `amount` 扩展为原生所需的最小字段，例如 `sharp_level`、`blur_type`，并保留旧项目迁移默认值。

### 12.2 模型和 pipeline

验证 `srn_deblur_512`：

- RGB/BGR、range、resize、tile、padding；
- 输出层选择、输出范围和反归一化；
- 大图 tile overlap 与 seam；
- 模型 restored image 与原图的 level/amount 混合曲线；
- halo、ringing、噪声放大和过冲抑制；
- 与 `defocus_exp35...`、`OUFV2_i8` 的职责边界，防止锐化和散焦修复误用同一能力。

### 12.3 诊断样本

- 文字/细线；
- 人像毛发；
- 低对比纹理；
- 运动模糊；
- 散焦模糊；
- 已锐利图像的 no-op；
- 高 ISO 图像与降噪前后组合顺序。

### 12.4 准出条件

- 原生档位和类型 UI 一致；
- wrapper/model contract validated；
- 每档有 reference、holdout 和实际 invocation；
- no-op 不产生明显 halo；
- preview/export、undo/redo、history 和缓存一致；
- 主/Exact 对应锐化 case 通过；若当前主集无有效 case，先按冻结采样流程新增一次原生 reference，再纳入 required。

## 13. P7：HDR、Focus Stacking、Panorama 三类多图

### 13.1 共享工作流合同

三类工作流统一验证：

- 允许的最小/最大帧数和格式；
- 添加、移除、排序和重复文件；
- EXIF orientation、尺寸不一致和色彩 profile；
- analyze、preview、export 的状态机；
- 进度、取消、错误恢复；
- workflow reload、临时文件清理；
- preview 与 export 使用同一 analysis；
- UI 选择态、完成态和导出；
- Browser `multi-image-workflow` 合同。

### 13.2 HDR Merge

在保持当前 parity 通过的前提下分阶段补齐：

1. 帧曝光排序和 EXIF/亮度估计；
2. 全局/局部对齐；
3. 饱和/欠曝/过曝权重；
4. 去鬼影 mask 与参考帧；
5. radiance fusion；
6. tone mapping；
7. 原生默认选项和 UI。

每一步先跑现有三帧 reference，任何回退立即停止；新增运动物体 holdout 只作回归，不替换现有 gate。

### 13.3 Focus Stacking

1. 帧全局对齐；
2. 多尺度 sharpness/focus map；
3. focus map 平滑与小区域去噪；
4. 遮挡和 parallax 边界处理；
5. seam blend；
6. 有效区域 crop；
7. 原生默认选项和 UI。

保留 winner-take-all 作为可对照 baseline，不在没有指标改善时引入复杂融合。

### 13.4 Panorama Stitching

按以下严格顺序重写，禁止直接从最终 resize 开始调：

1. 灰度/颜色预处理和相邻帧候选；
2. ORB 或本地可用 SIFT 特征；
3. descriptor ratio/cross check；
4. RANSAC homography 或适合当前 reference 的 transform；
5. 选择平面、柱面或球面投影；
6. 以中间帧为 anchor 累积 transform；
7. canvas bounds 和有效 mask；
8. 曝光/白平衡补偿；
9. seam selection；
10. multiband 或有证据的 feather blend；
11. 从有效 mask 推导 crop；
12. 保留原生输出尺寸，不做最终强制 resize。

依赖决策：先检测环境现有库。如果选择 OpenCV，必须通过独立依赖评审确认本地离线可安装、包体、许可证、平台兼容和性能；未经确认不得临时联网下载。若不引入 OpenCV，则对 feature、RANSAC、warp 分别实现最小可测试模块。

### 13.5 多图专项测试

- transform recovery synthetic tests；
- valid mask/canvas bounds；
- seam continuity；
- exposure invariance；
- reversed order；
- duplicate/insufficient frames；
- different sizes/orientation；
- deterministic output hash；
- preview/export dimensions；
- temp artifact cleanup。

### 13.6 准出条件

- HDR、Focus 当前 reference 保持 passed；
- Panorama 达到现有 MAE/SSIM/shape 门槛；
- 三类工作流各自有独立 UI 和 API E2E；
- Browser multi-image 合同包含至少一种完成流程和三种入口映射；
- 不存在强制 resize 或 reference-specific crop。

## 14. P8：其余模型族 92/92 闭环

核心工具完成后，按消费者优先级关闭剩余模型：

### 14.1 Mask / segmentation 族

semantic、interactive、salient、saliency、portrait、skin、hair、animal、transport、wire、imperfection、dust。验收重点为类别定义、概率/标签语义、resize-back、阈值、边界和空目标行为。

### 14.2 Portrait / face / human 族

face detection、landmark、iris、eyes、face part、human landmarks/clothes、bokeh、face restoration。验收重点为坐标系、NMS、landmark 顺序、多人选择、无人像 no-op 和 ROI 恢复融合。

### 14.3 Depth / light / sky 族

depth estimation、horizon、sky/water、magic light。验收重点为相对深度方向、归一化、horizon 角度、光点坐标和消费者的空间对齐。

### 14.4 Restore / resolution 族

denoise、deblur、defocus、6 个 ONNX upscale 与 6 个 OpenVINO upscale。验收重点为 scale、tile、padding、颜色、纹理、backend pair 和大图内存。

### 14.5 Search / classifier / RAW 族

image/text embedding、classifier、CFA、channel shift、unknown analysis。验收重点为 token/input contract、embedding 归一化、类别表、RAW 通道语义；`unknown_analysis` 必须查明消费者或移出产品注册，不能永久保持 unknown。

### 14.6 准出条件

最终报告不得出现：`pending-model-specific`、`ir-registered-runtime-pending`、`runtime-blocked-nonfinite`、`configured-not-covered`、`inventory-unmapped`。允许“非活动替代 backend”角色，但它仍需完成单体合同和与活动 backend 的 parity。

## 15. P9：UI 16 状态与 Browser 10 合同

### 15.1 UI 分 cohort 收敛

按区域而不是整图盲调：

1. app chrome：logo、breadcrumb、export、右 rail；
2. editor geometry：左轨、canvas、右 panel、filmstrip、底栏；
3. initial/canvas：初始图片选择居中、照片 fit、zoom/pan；
4. layer：stack、library、inspector、mask；
5. tool：expanded、黑白、降噪、锐化、天空；
6. side panels：history、more、info、collapsed；
7. workflow/dialog：multi-image、complete、export dialog。

每个 cohort 同时记录 region MAE、changed-pixel ratio 和全图指标；只有 region 和全图不退化才合入下一批。

工具页左侧竖线是明确禁止回归项：对 `.workspace-edit > .canvas-panel` 和 `.workspace-edit > .tool-panel` 增加 computed-style 或截图区域测试，确保 border-left/right 为 0。

### 15.2 10 个 Browser 合同

按 disposable workspace 分别执行：

1. catalog-import-select；
2. preset-preview-apply；
3. edit-slider-drag；
4. layer-add-reorder-opacity-delete；
5. undo-redo；
6. before-after-compare；
7. zoom-pan；
8. export-dialog；
9. multi-image-workflow；
10. 当前已通过合同保持原始名称，以 `interaction-contracts.json` 为唯一清单。

每个合同需：raw events、before/after screenshot、project/API readback、console error 0、unexpected network 0、build hash、fixture hash。删除类动作仅在隔离项目执行。

### 15.3 准出条件

- UI execution 16/16 保持；
- UI parity 16/16；
- interaction 10/10；
- 图层、遮罩、天空、降噪、锐化和三类 workflow 的关键状态均被现有或新增合同覆盖；
- frontend build 变化后证据已全量重录。

## 16. P10：主效果与 Exact 收敛

### 16.1 主效果优先

以 `quality-gates-round-5-final.json` 的 40 case 为唯一主集，当前 11 个失败按根因族处理：

- mask/portrait：face_ai；
- depth/atmosphere/sky：depth_volume、blue_hour、fog、sky_replace、sunrays；
- restore：denoise；
- color/LUT：bw_channels、lut_mapping；
- synthetic light：magic_lights、new_neon_light。

每个族必须先有 calibration + holdout，再改共享算法。不得按 case id 分支。

### 16.2 Exact 后收敛

主集 40/40 后再处理 31 个 Exact 失败。按算法族归并：

- global tone/color；
- local detail/restore；
- portrait/mask/geometry；
- depth/sky/atmosphere/light；
- stochastic grain。

颗粒等随机/统计效果可以增加统计诊断，但正式 69 case comparator 和阈值不得更换。若确认原生输出本身随机，先以三次原生重复证明，再提出独立可重复 reference 策略，不能单方面修改 gate。

### 16.3 准出条件

- 主效果 40/40；
- Exact 69/69；
- 模型 backed case 的 execution trace、model version、result hash 一致；
- 每个修改族 holdout 不退化；
- 没有 reference-specific 代码。

## 17. P11：素材复核、全量回归与双轮发布

### 17.1 素材复核

- sky 43/43 SHA；
- overlay 234/234 SHA；
- LUT 41/41 规范化内容；
- preset artwork 123/123；
- 22 categories；
- Portable preset semantic index 无未解释运行依赖；
- 运行时代码只消费索引中明确引用的资源。

### 17.2 全量测试命令

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .

cd frontend
npm test -- --run
npm run build
```

模型专项：

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py \
  --project-root . --model-dir ai/model

.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-contract-audit-round-6.json

.venv/bin/python scripts/audit_model_pipelines.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/model-pipeline-audit-round-6.json

.venv/bin/python scripts/audit_candidate_model_invocations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --require-active-contracts \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocations-round-6.json
```

核心功能：

```bash
.venv/bin/pytest -q \
  tests/test_layer_rendering.py \
  tests/test_sky_compositor.py \
  tests/test_active_model_contracts.py \
  tests/test_hdr_merge.py \
  tests/test_panorama_merge.py \
  tests/test_workflows.py

.venv/bin/python scripts/run_sky_e2e_validation.py \
  --reference-id luminar-neo-macos-1.28.0-23071

.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-round-6.json
```

最终门禁连续运行两轮：

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-6-run-1.json

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --output test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-6-run-2.json
```

实际执行前必须用各脚本 `--help` 再确认参数；若脚本当前没有文档中的 `--run-id` 或输出参数，应在 P0 实现并测试，而不是手工改报告。

### 17.3 最终产物

- `source-manifest-round-6-before.sha256`
- `source-manifest-round-6-after.sha256`
- `model-validation-matrix-round-6.json`
- `model-contract-audit-round-6.json`
- `candidate-model-invocations-round-6.json`
- `mask-platform-validation-round-6.json`
- `layer-e2e-round-6.json`
- `sky-e2e-round-6.json`
- `denoise-e2e-round-6.json`
- `supersharp-e2e-round-6.json`
- `multi-image-round-6.json`
- `ui-parity-round-6.json`
- `interaction-execution-round-6.json`
- `quality-gates-round-6-run-1.json`
- `quality-gates-round-6-run-2.json`
- `absolute-parity-execution-report-2026-08-27-round-6.md`

## 18. 文件级修改与验证矩阵

| 模块 | 主要入口 | 必须补的测试 |
|---|---|---|
| 模型基础设施 | `ai/model/base_inference.py`、`factory.py`、`loader.py`、`registry.py` | lifecycle、fallback、memory、repeatability、error terminal |
| 模型 wrappers | `ai/model/onnx/**`、`ai/model/openvino/**` | 92 个 model-specific pre/post golden |
| 模型配置/合同 | `configs/model.yaml`、`models/contracts/**` | schema、hash、logical backend pair、consumer coverage |
| 遮罩 | schemas/router/editor/storage/effect graph/MaskPanel | migration、mask ops、coordinate、history、export |
| 图层 | `LayersPanel.tsx`、App、layer service/render | material、stack、transform、blend、mask、reload、Browser |
| 天空 | model service、sky compositor、SkyControls、assets | intermediate artifacts、geometry、edge、relight、reflection、E2E |
| 降噪 | denoise wrapper、image effect pipeline、ToolPanel | level profiles、tile/color/detail、main/Exact/UI |
| 锐化 | deblur/defocus wrappers、pipeline、ToolPanel | level/type、tile/halo/no-op、main/Exact/UI |
| HDR | `image_ops/merge/hdr.py`、multi-image service/UI | align、ghost、fusion、tone、E2E |
| Focus | `image_ops/merge/focus.py` | align、focus map、seam、E2E |
| Panorama | `image_ops/merge/panorama.py` | feature、transform、projection、seam、crop、E2E |
| UI | App/components/styles | 16 current-build screenshots、region diff |
| Interaction | Browser evidence scripts | 10 raw contracts、API readback、console/network |
| Release | quality/convergence scripts | same-run linkage、double run、source manifest |

## 19. 单批次执行模板

每个实现批次严格使用以下模板：

1. **目标**：一句话描述唯一根因和成功指标。
2. **冻结输入**：列出 reference、case、fixture、source manifest hash。
3. **before**：记录当前指标、中间产物和失败截图。
4. **假设**：指出误差位于 UI、wrapper、pipeline、compositor、storage 或 comparator 哪一层。
5. **最小修改**：只改与假设直接相关文件。
6. **专项测试**：单测、契约、E2E。
7. **holdout**：至少一组未参与调参的样本。
8. **全局回归**：Python、Frontend、相关 parity cohort。
9. **after**：记录指标、hash、source diff。
10. **判定**：通过则冻结；不通过且假设被否定则回退该批，不叠加新补丁。

## 20. 风险、停止条件与回退策略

### 20.1 高风险项

- 42 个 OpenVINO 模型可能存在 runtime 版本、设备或 IR op 兼容问题；
- 92 个模型全量实际推理可能超出单次内存，必须按 task cohort 和 loader budget 执行；
- 遮罩 schema 会影响老项目兼容、history 和导出；
- Panorama 引入视觉库可能增加包体和平台依赖；
- UI 改动会使全部旧浏览器证据失效；
- 原生部分模型中间输出无法直接读取，只能通过可观察能力和替代诊断建立证据边界。

### 20.2 停止条件

遇到以下任一项立即停止当前批次：

- reference、input、asset 或 case hash 漂移；
- holdout 退化超过当前门限；
- 输出只在特定 case id 下改善；
- 模型输出非 finite 或 shape 不稳定；
- UI build 变化但没有重录证据；
- 需要联网下载、复制未知许可资源或引入未评审二进制依赖；
- 修改一个族导致另一个已通过 required gate 失败。

### 20.3 回退

- 每批次保留 before source manifest 和明确文件列表；
- 无 Git 元数据时不得使用破坏性 checkout/reset，应通过反向 `apply_patch` 回退该批文件；
- 旧项目 schema 在迁移前复制到隔离 fixture，迁移失败不覆盖原文件；
- 新模型合同或 backend 选择用 feature/config gate 切换，但发布前必须删除临时双路径；
- Panorama 旧实现可保留为测试 baseline，不允许在生产路径偷偷 fallback 并报告通过。

## 21. 逐批执行顺序与里程碑

### 里程碑 A：证据与模型底座

1. P0 same-run 和 source manifest；
2. P1 模型矩阵；
3. 修复 OpenVINO runtime probe 与 nonfinite；
4. 将模型合同 gate 升为 required；
5. 目标：92 模型都有明确 owner 和 terminal status。

### 里程碑 B：遮罩和图层

1. mask schema/migration；
2. mask compositor；
3. AI mask；
4. MaskPanel/Canvas overlay；
5. layer mask 和 layer transform；
6. 234 素材语义；
7. 图层 Browser 合同；
8. 目标：图层与遮罩端到端闭合。

### 里程碑 C：天空、降噪、锐化

1. 天空中间产物；
2. 天空几何/融合/重光/倒影；
3. 降噪三档；
4. 超锐档位/类型；
5. 对应 UI、interaction、主/Exact；
6. 目标：三个核心 AI 工具各自全链路通过。

### 里程碑 D：三类多图

1. 共享 workflow 状态机；
2. HDR 保持并补齐；
3. Focus 保持并补齐；
4. Panorama 几何重建；
5. multi-image Browser 合同；
6. 目标：3/3。

### 里程碑 E：其余模型、全 UI 和效果

1. 剩余模型族闭合至 92/92；
2. UI cohort 16/16；
3. Browser 10/10；
4. 主效果 40/40；
5. Exact 69/69。

### 里程碑 F：发布

1. 素材复核；
2. 全量测试；
3. source manifest after；
4. Exact gate run 1；
5. 清洁环境 Exact gate run 2；
6. 生成执行前后对比和遗漏复核报告。

## 22. 最终遗漏复核清单

执行结束前逐项回答“是/否”，任何“否”都不得声明完成：

- [ ] 权威 run 是否唯一，所有统计是否同一 run？
- [ ] 92 个模型是否全部有专用合同、实际终态、重复运行和 unload 证据？
- [ ] 42 个 OpenVINO 是否全部实际运行？
- [ ] `convnextv2_multiclass` 非有限输出是否关闭？
- [ ] 所有模型是否有消费者或合法库存角色？
- [ ] 遮罩是否覆盖 AI、画笔、edit、layer、sky，并统一 preview/export？
- [ ] 图层遮罩页是否真实可用而非占位？
- [ ] 234 个图层素材是否不仅文件一致，而且顺序、preview、默认合成也一致？
- [ ] 图层添加、重排、opacity、blend、transform、mask、delete、history、reload、export 是否全闭合？
- [ ] 工具页左侧是否仍无竖线？
- [ ] 初始图片选择是否仍在画布可用区正确居中？
- [ ] 天空 43 个素材和全部控件是否严格映射？
- [ ] 天空 mask、horizon、water、foreground、relight 中间产物是否可诊断？
- [ ] 降噪低/中/高是否都有独立原生合同和结果？
- [ ] 锐化档位、类型和模型职责是否与 Neo 一致？
- [ ] HDR 是否在补齐行为后仍通过？
- [ ] Focus 是否在补齐行为后仍通过？
- [ ] Panorama 是否没有最终强制 resize 和 reference-specific crop？
- [ ] 三类多图是否 3/3 且有真实 Browser 证据？
- [ ] UI 是否 16/16？
- [ ] Browser interaction 是否 10/10？
- [ ] 主效果是否 40/40？
- [ ] Exact 是否 69/69？
- [ ] 全量测试、lint、build 是否通过？
- [ ] Exact required gate 是否连续两轮 0 failure 且输出 hash 稳定？

## 23. 立即开始时的第一批任务

第一批只做 P0 + P1 基础设施，不改视觉算法：

1. 新增 source manifest 和 `run_id`；
2. 重新生成同一 run 的第五轮基线，消除统计命名漂移；
3. 生成 92 模型机器可读矩阵；
4. 为 41 个 OpenVINO pending 建立分批 runtime probe；
5. 单独定位 `convnextv2_multiclass` 非 finite；
6. 为遮罩、图层、天空、降噪、锐化和三类多图建立 owner batch；
7. P0/P1 通过后再进入遮罩 schema，避免在证据链不稳定时大改产品状态。

这个顺序能先把“我们实际改了什么、哪一个模型真的运行、结果属于哪次构建”固定下来，再推进高风险的遮罩、图层和模型效果，避免再次出现功能看似可用但无法证明严格对齐的情况。
