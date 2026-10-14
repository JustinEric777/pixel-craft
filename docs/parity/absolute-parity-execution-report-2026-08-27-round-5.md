# Luminar Neo 绝对对齐第五轮执行报告

## 1. 结论

本轮已完成用户优先要求的 UI、图层交互、素材和初始选择态修复，并完成两轮 Exact 综合门禁。当前项目的工程可用性与证据完整性明显提升，但尚不能声明“与 Luminar Neo 绝对对齐”。

已闭合的关键项：

- 当前 frontend build 的 16 个 UI 状态执行证据由 `0/16` 提升为 `16/16`，环境、fixture、截图和 build hash 均通过 fail-closed 校验。
- 初始“添加照片”空状态从顶部错位改为在画布可用区域内居中。
- 工具页左侧错误竖线已确认并消除：画布左右边框和右侧工具面板左边框均为 `0`。
- 图层从“宽列表与失控素材图”收敛为 Neo 式 76 px 缩略图轨道、204 px 三列素材库和右侧层属性卡。
- 图层新增、选中、50% 不透明度、显隐和真实指针拖拽重排均已在本地浏览器和隔离项目中验证；重排结果已持久化到项目 JSON。
- 本地 macOS Luminar Neo 1.28.0 build 23071 的天空、图层素材、LUT 和预设 artwork gate 全通过。
- 用户指定 Windows Portable 目录中的 43 个天空文件、234 个图层素材与项目逐文件 SHA-256 一致；41 个 LUT 仅有 CRLF/LF 换行差异，规范化后内容 41/41 一致。
- Python `305/305`、Frontend `24/24`、Ruff、TypeScript 和生产构建全部通过。
- Exact 综合门禁连续两轮结果一致：`22/28` gate 通过，5 个 required gate 仍阻塞。

尚未闭合的核心项：UI 像素等价 `0/16`、浏览器交互正式证据 `1/10`、主效果 `29/40`、Exact `38/69`、Panorama `0/1`、模型专用合同 `26/92`。因此本轮结果应表述为“重点 UI 与图层可用性修复完成，绝对对齐仍在收敛中”。

## 2. 固定参考与输入

### 2.1 主参考

- 应用：`/Applications/Luminar Neo.app`
- 版本：`1.28.0`
- build：`23071`
- locale：`zh-Hans`
- timezone：`Asia/Shanghai`
- UI logical viewport：`1440×900`
- UI physical viewport：`2880×1800`
- DPR：`2`

### 2.2 用户指定 Portable 资产源

- 根目录：`/Users/iknow/Downloads/LuminarNeo-1.28.0.17626-x64-Portable/Luminar Neo/App`
- 天空：43/43 文件与项目逐路径、逐 SHA-256 一致。
- Overlay：234/234 文件与项目逐路径、逐 SHA-256 一致。
- LUT：路径 41/41 对齐；Windows 文件使用 CRLF，项目使用 LF，换行规范化后内容 41/41 一致。
- PresetPacks：Portable 含 2965 个内部包文件，项目当前保留 168 个运行与 artwork 所需文件，其中 167 个与 Portable 逐 SHA-256 一致；不能把其余 2798 个文件未经语义映射直接复制进运行目录。

主资产 gate 记录为：天空 `43/43`、Overlay `234/234`、LUT `41/41`、preset artwork `123/123`、分类 `22`，全部通过。

### 2.3 采样输入

当前队列不是旧文档中的 246 条，而是 `255/255 ready`：UI 16、effect 40、preset 123、sky 35、overlay 38、workflow 3。该统计漂移属于文档遗漏，不是采样缺失。

## 3. 已实施修改

### 3.1 图层状态与面板职责

- [LayersPanel.tsx](../../frontend/src/components/LayersPanel.tsx) 改为由 App 控制选中图层，左侧只负责图层栈和素材库。
- [ToolPanel.tsx](../../frontend/src/components/ToolPanel.tsx) 在右侧工具区域渲染选中图层的属性卡。
- [App.tsx](../../frontend/src/App.tsx) 在新增、删除、切换项目后保持选中图层有效，并统一转发更新与重排。

该结构与 Neo 的“左侧层轨道 + 中央画布 + 右侧层属性/工具”一致，避免属性控件挤进左侧窄栏。

### 3.2 图层轨道与素材库

[LayersPanel.tsx](../../frontend/src/components/LayersPanel.tsx) 与 [styles.css](../../frontend/src/styles.css) 已实现：

- 76 px 左侧层轨道。
- 52×52 px 层缩略图。
- 选中黄框、悬停显隐与删除按钮、隐藏态透明度反馈。
- 204 px 素材库。
- “加载图像”、分组标题、“查看全部”、“获取更多资产”。
- 3 列首屏素材，每张约 52×44 px。
- 首屏素材取消 lazy loading，防止真实浏览器证据中出现未加载黑块。
- 星尘散景、漏光、烟火、耀斑使用本地 Neo 原始素材预览。

### 3.3 Neo 风格层属性卡

[LayersPanel.tsx](../../frontend/src/components/LayersPanel.tsx) 的属性卡已收敛为：

- `层属性 PRO` 标题。
- `摘要资讯 / 遮罩` 标签。
- 不透明度数值与滑杆。
- 混合模式。
- 水平/垂直翻转。
- 图像映射：适合、填充、拉伸。

此前额外暴露的缩放、旋转、水平位置和垂直位置滑杆已从默认摘要卡移除，避免与本地 Neo 当前状态不一致。

### 3.4 图层真实拖拽

原实现只有 HTML5 `drag/drop`，在真实浏览器指针拖动中没有触发持久化。当前在保留 HTML5 路径的同时增加 `pointerdown/pointerup` 重排路径。

实测流程：

1. 添加 `Champagne`。
2. 设置不透明度为 `0.5`。
3. 添加 `Fiesta`。
4. 从顶部缩略图拖到第二层。
5. 浏览器层顺序反转。
6. 只读 API 项目 JSON 确认顺序和 `opacity: 0.5` 已持久化。

### 3.5 初始选择态与边界

[styles.css](../../frontend/src/styles.css) 已将 `.canvas > .empty` 设置为占满画布可用区域并居中布局。修复前空状态仅占 300 px 高并贴近顶部；修复后整个提示组在画布区域内居中。

同文件已明确：

- `.workspace-edit > .canvas-panel { border-left: 0; border-right: 0; }`
- `.workspace-edit > .tool-panel { border-left: 0; }`

因此用户指出的工具页左侧竖线已确认不应存在，并已按本地 Neo 去除。

## 4. 浏览器执行证据

本轮通过 Codex in-app Browser 在 `1440×900` 下采集并发布 16 个状态：

- catalog
- multi-image
- multi-image-complete
- presets
- edit
- layer-stack
- layer-library
- tool-expanded
- edit-history
- more-panel
- info-panel
- edit-collapsed
- black-white-before-conversion
- black-white-after-conversion
- denoise-level-selected
- export-dialog

HDR 状态使用三张 `1080×1440` 测试照片，真实完成选择、合并和预览，未使用占位图。

执行证据：

- `ui-execution-evidence-round-5-after.json`：`16/16 passed`、issue `0`。
- `ui-parity-round-5-after.json`：`0/16 passed`，仍阻塞。

这两个结果并不矛盾：前者证明截图属于当前 build 和固定 fixture；后者证明当前视觉仍未达到像素阈值。

## 5. 前后对比

| 项目 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| UI 当前构建执行证据 | 0/16，5 issues | 16/16，0 issue | 已闭合 |
| Exact 综合 gate | 21/28 | 22/28 | UI evidence gate 转绿 |
| Frontend tests | 22 | 24 | 新增层属性与指针重排覆盖 |
| Python tests | 305 | 305 | 无回归 |
| 图层素材缩略图 | 失控大图/黑块/纵向溢出 | 3 列 52×44、首屏立即加载 | 已修复主要混乱 |
| 图层属性 | 左侧/额外变换滑杆 | Neo 式右侧摘要卡 | 结构对齐 |
| 图层拖拽 | 真实指针拖动不持久化 | 浏览器实测持久化 | 已修复 |
| 初始添加照片 | 提示组贴近顶部 | 画布可用区居中 | 已修复 |
| 工具页左边竖线 | 存在风险 | computed border 为 0 | 已确认并修复 |
| 主效果 | 29/40 | 29/40 | 本轮未收敛 |
| Exact | 38/69 | 38/69 | 本轮未收敛 |
| Multi-image | 2/3 | 2/3 | Panorama 仍失败 |
| 正式 Browser 合同 | 1/10 | 1/10 | 实测能力增加，但证据未发布 |
| UI 像素 parity | 0/16 | 0/16 | 仍是主要阻塞 |

## 6. 最终门禁

两轮 Exact 门禁均为：

- gate count：28
- passed：22
- required failed：5
- optional failed：1
- status：blocked

5 个 required 失败：

1. `multi-image`
2. `output-parity`
3. `exact-incremental-parity`
4. `ui-parity`
5. `interaction-execution`

optional 失败：`model-contract-inventory`。

领域明细：

| 领域 | 结果 |
|---|---:|
| output parity | 29/40，11 failed |
| exact parity | 38/69，31 failed |
| UI parity | 0/16，16 failed |
| UI execution | 16/16，0 issue |
| interaction execution | 1/10，9 missing |
| multi-image | 2/3，Panorama failed |
| model contracts | 92 valid；26 validated；66 model-specific-pending |

Panorama 当前 shape 已匹配，但指标为 MAE `0.0819413`、SSIM `0.8155414`。把最终 resize 改成对称 crop 的诊断试验反而退化到 MAE `0.0890742`、SSIM `0.7844877`，所以本轮没有提交无证据的几何改动。

## 7. 完整遗漏确认

### P0：UI 像素级状态仍未对齐

16 个状态都是真实当前构建证据，但仍全部未达到 UI parity 阈值。问题不是截图缺失，而是同一状态下的几何、字号、图标、照片缩放、filmstrip、对话框尺寸和部分状态内容仍有差异。

### P0：交互证据链未闭合

正式报告仍缺 9 个合同。图层新增、透明度、显隐与重排已经实测，但 `layer-add-reorder-opacity-delete` 要求最后删除图层；浏览器删除属于不可逆操作，需要在动作发生时获得用户确认，因此本轮没有伪造 passed raw trace。

### P0：主效果与 Exact 未收敛

- 主效果仍有 11 个失败。
- Exact 仍有 31 个失败。
- 失败覆盖人像、颗粒、光效、默认效果、结构、增强、晕影、雾、去噪等不同算法族，不能用一个全局调色参数解决。

### P0：Panorama 缺少原生几何语义

当前仍是 overlap translation + feather，缺少特征匹配、稳健单应/投影、局部 warp、曝光补偿、seam 和有效边界裁切。最终尺寸相同不代表内容等价。

### P1：模型专用合同未完成

模型模块静态契约 0 阻塞，92 个注册记录结构有效；但只有 26 个完成 model-specific validation，66 个仍 pending，runtime-ready 为 0。下一步应只激活实际调用的模型，不应为 66 个未调用模型制造伪调用。

### P1：Portable preset 不是简单复制问题

Portable PresetPacks 比项目多 2798 个内部文件。当前 UI artwork 已 123/123 对齐；剩余文件需要建立 pack/collection/preset/preview 的语义映射后再决定是否导入，不能直接把整个目录复制进项目。

### P1：第五轮 before 源码 manifest 缺失

代码修改开始前没有生成 `source-manifest-round-5-before.sha256`，因此无法在无 Git 元数据的工作区中可信重建“修改前源码 hash”。本报告明确记录该证据缺口，未用修改后的 hash 冒充 before。

### P2：统计文档过期

计划写的是 246 条队列，实际稳定队列为 255 条。相关计划、README 和验收表需要统一改为从报告动态读取 `record_count`，避免再次手写漂移。

## 8. 下一步可执行建议

### 8.1 第一优先：按区域收敛 UI 16 状态

不要同时改 16 张整图。按固定区域建立 cohort：

1. app chrome：Logo、breadcrumb、导出按钮、右 rail。
2. editor geometry：左轨、canvas、右 panel、filmstrip、底栏。
3. layer states：stack、library、inspector。
4. tool states：工具列表、展开态、黑白、降噪。
5. dialogs/workflows：导出、HDR 选择、HDR 完成。

每次只改一个 cohort，生成区域 diff 与全图 diff；要求该 cohort 的 MAE 和 changed-pixel ratio 同时下降，避免局部变好、全局退化。

### 8.2 第二优先：完成 10 个 Browser 合同

为每个合同建立独立 disposable workspace、raw trace、API readback、console/network 和最终截图。图层删除只在隔离项目中执行，并在动作时单独确认。完成后再用 `build_interaction_browser_execution.py` 发布，不能把本轮人工实测描述直接写成 passed evidence。

### 8.3 第三优先：先收敛主效果 11 个失败

按算法族聚类失败，而不是按 case id 分支：

- tone/color：high key、fade、landscape、default effects。
- local detail：details、structure、denoise/deblur。
- portrait geometry/mask：face、bokeh、slim。
- synthetic light/atmosphere：sunrays、fog、magic/neon。
- stochastic：grain 使用统计比较器独立调参。

每个算法族先通过 40-case 主门禁，再进入 69-case Exact；禁止降低阈值、替换 reference 或在运行代码读取 case id。

### 8.4 第四优先：重写 Panorama 几何核心

建议引入或实现可离线运行的特征匹配与稳健几何管线：

1. ORB/SIFT 等关键点与描述子。
2. ratio test + RANSAC。
3. homography/cylindrical projection。
4. canvas bounds 与有效 mask。
5. 曝光补偿和 seam selection。
6. multiband/feather blend。
7. 从有效 mask 推导 crop，禁止最终强制 resize。

先以 geometry tests 固定重叠、尺寸和有效边界，再跑 workflow smoke。当前环境没有 `cv2`，若选择 OpenCV，需要先做依赖与体积评估，不应临时联网下载。

### 8.5 第五优先：只闭合实际模型调用

对候选输出报告中实际出现的模型逐个补齐：注册记录、专用合同、invocation、terminal result、输入输出 hash 和 unload 证据。已验证 26 个保持冻结；66 个未激活模型继续 optional，直到真实效果路径调用它们。

### 8.6 第六优先：Portable preset 语义索引

新增只读索引器解析 Portable `PresetPacks`：pack、collection、preset、icon、preview、LUT 和配置引用。输出 missing/extra/different 语义报告，再按 API 真正消费的资源导入。图片/天空/Overlay/LUT 当前无需重复复制。

## 9. 下一轮验收条件

下一轮不得以“代码测试通过”替代“绝对对齐”。至少满足：

- UI execution 16/16 保持通过。
- UI parity 按 cohort 单调改进，最终 16/16。
- Browser interaction 10/10。
- output parity 40/40。
- exact parity 69/69。
- multi-image 3/3。
- 实际调用模型专用合同 100%。
- Exact gate 连续两轮 required failure 为 0，核心候选 hash 稳定。

## 10. 关键产物

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence-round-5-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-round-5-after.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/asset-alignment-round-5-before.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-evidence.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-5-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-round-5-run-2.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-baseline-round-5-final.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/convergence-failures-round-5-final.json`

