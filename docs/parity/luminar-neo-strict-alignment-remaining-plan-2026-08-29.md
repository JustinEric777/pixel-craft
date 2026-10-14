# Luminar Neo 1.28 本地核心严格对齐剩余执行计划

> 状态：历史计划；当前执行基线和后续顺序已由
> `absolute-parity-execution-report-2026-08-29-r8.md` 取代  
> 基线：本机 Luminar Neo `1.28.0 (23071)` / macOS / `zh-Hans`  
> 起点：`execution-plan-current-final-preflight-2-20260829`，exact `29/34`  
> 目标：在不放宽阈值、不伪造证据、不增加历史兼容层的前提下，连续两轮 exact `34/34`

## 1. 目标、范围与声明边界

### 1.1 最终目标

本计划只在下列条件同时满足后，允许声明“与本机 Luminar Neo 本地核心严格对齐”：

| 对齐域 | 当前 | 发布目标 |
|---|---:|---:|
| 活动模型 contract | 22/22，pending 0 | 22/22，pending 0，且两轮 fingerprint 一致 |
| 主效果 | 33/40 | 40/40 |
| 扩展 Exact | 40/69 | 69/69 |
| 当前源码 UI execution | 15/16 | 16/16 |
| UI pixel | 0/16 | 16/16 |
| Native 交互合同 | 8/10 | 10/10 |
| Browser 交互合同 | 8/10 | 10/10 |
| Exact gate | 29/34 | 34/34，required failure 0 |
| 连续复现 | 未执行 | A/B 两轮均 34/34，且 fingerprint 完全相同 |

“功能可运行”“人工看起来接近”“已有旧截图”或“单轮偶然通过”都不构成严格对齐。

### 1.2 实现范围

只实现和验证本机、离线、免费、可重复的核心能力：

- Catalog、照片浏览、右键操作、滚动、照片切换和独立历史；
- Preset 导入、预览、应用；
- Edit 工具、图层、遮罩、裁切、前后对比、缩放、平移；
- 当前冻结集合中的主效果和扩展参数合同；
- HDR、Focus Stacking、Panorama 三类多图工作流；
- 本地导出；
- 当前单轨 catalog 持久化；
- 16 个冻结 UI 状态和 10 个交互合同。

明确排除：付费、升级、订阅、账号、商店、云生成、教程、帮助和商业内容。排除项不得进入 required gate，也不得为它们新增空壳页面。

### 1.3 不允许的收敛手段

- 不降低 `MAE <= 0.03`、`SSIM >= 0.98`、shape match 或 UI changed-pixel-ratio 阈值；
- 不按 case id、输入文件名、reference hash 写特判；
- 不把 Lanczos 放大图标记成真实 DPR 2 截图；
- 不手写 DOM、AX、截图、交互 trace 或成功报告；
- 不用 runtime-ready、结构有效或 smoke pass 替代 model-specific contract；
- 不复制旧 build 的证据到新源码 hash；
- 不对 Luminar 原生数据库执行写入；
- 不保留 JSON/SQLite 双写、旧 schema fallback、旧版本分支或迁移兼容层；
- 不把 Native 应用自身稳定复现的失败静默改为“通过”。

## 2. 当前阻塞项与依赖关系

当前 5 个 exact required failure 是：

1. 主效果 `output-parity`：7 个失败；
2. 扩展 `exact-incremental-parity`：29 个失败；
3. UI execution：缺 `multi-image-complete`；
4. UI pixel：0/16；
5. Interaction：Preset 与三类多图工作流未闭合，Native/Browser 均为 8/10。

除此之外还有两个必须显式处理的声明风险：

- Browser 当前只有 `1440x900` 逻辑截图，`2880x1800` 候选是派生图，不能支持 native DPR 2 声明；
- 尚未取得 Luminar 原生 catalog 私有 SQLite schema，当前 schema 155 只能声明为本项目单轨合同。

执行依赖固定如下：

```text
冻结基线与证据规则
        ↓
真实 DPR 2 / 本地文件 / 全屏 Native 采集能力
        ↓
Native 缺失行为重观察与有效 fixture
        ↓
主效果 40/40 → 扩展 Exact 69/69
        ↓
Preset / 多图交互实现完整
        ↓
UI 公共壳与 16 状态像素校准
        ↓
冻结最终源码 hash，正式重录 UI 16/16 + Native/Browser 10/10
        ↓
单轮 exact 34/34 → 相同 fingerprint 的 A/B 两轮
```

效果先于最终 UI 重录，是因为预览内容会进入 UI 截图；多图实现先于 UI 校准，是因为 `multi-image-complete` 本身属于 16 个冻结状态。这样可避免反复使正式证据失效。

## 3. 统一执行规则

### 3.1 每个批次必须具备的记录

每个改动批次必须记录：

- 唯一 run id；
- source、model、validation、reference、environment fingerprint；
- 修改前失败列表和指标；
- 修改的根因、代码路径和受影响合同；
- calibration 输入与独立 holdout 输入；
- preview/export 候选及其 SHA-256；
- 测试、门禁、失败原因和回滚条件；
- 新生成证据路径，禁止覆盖旧 run 目录。

### 3.2 小批次原则

- 一个效果批次只处理一个共享算法根因；
- 一个 UI 批次只处理一类公共变量或一组同构状态；
- 一个交互批次只关闭一个合同；
- 每批先运行定向测试，再运行域级门禁；
- 指标改善但未过线时继续保持 failed，不写“基本完成”；
- calibration 通过、holdout 回退时立即撤销该方案；
- 任何 fixture/reference 变化都必须生成新 hash 和新 run。

### 3.3 模型层不可回退约束

模型已完成 22/22，不再作为新增开发阶段，但每轮必须复验：

- 活动注册表只能包含真实消费者可达的模型；
- ONNX Runtime 为主路径，OpenVINO IR 仅在同语义 contract 通过时兜底；
- 不允许隐式下载或 CoreML 替代；
- 输入 dtype、shape、range、layout、输出语义、资源释放均必须保持 contract；
- 新增模型或更换 artifact 时，先更新 model-specific contract，再允许接入调用路径。

## 4. Phase 0：冻结起点并建立变更账本

### 4.1 输入

- 最新 exact 报告：`quality-gates-current-final-preflight-2-20260829.json`；
- 当前 40 个主效果、69 个扩展用例、16 个 UI 状态和 10 个交互合同；
- 当前模型矩阵、UI evidence、interaction execution 和 dataset freshness 报告。

### 4.2 执行动作

1. 将当前 5 个 required failure 展开为可追踪任务，每项绑定合同 ID、当前指标和证据路径。
2. 对所有活动 reference、fixture、模型、配置和比较器计算 hash。
3. 冻结 `configs/reference.yaml`、`configs/parity.yaml` 的验收阈值；阈值变化视为范围变化，必须重新立项，不能用于关闭本计划。
4. 建立“证据有效性”列：`current-build`、`native-fullscreen`、`real-dpr2`、`holdout-passed`、`preview-export-consistent`。
5. 标记 LUT 为 `confirmed-invalid-reference`，在重采样前不得计入通过。

### 4.3 验收与退出条件

- 起点 exact 仍可复现为 29/34；
- 模型仍为 22/22；
- 失败分母没有被删除或悄悄改成 optional；
- 任务账本中的每个失败都能反查到当前报告。

若起点不可复现，先修复环境或证据链，不进入算法开发。

## 5. Phase 1：补齐可信采集基础设施

### 5.1 Browser 真实 DPR 2

目标是同时记录逻辑事件空间和物理截图空间：

- logical viewport：`1440x900`；
- device scale factor：`2`；
- physical screenshot：`2880x1800`；
- 浏览器版本、字体、locale、timezone、缩放、颜色空间必须入 manifest。

执行：

1. 基于当前浏览器测试运行时增加独立截图 runner，启动时固定 `deviceScaleFactor=2`。
2. 截图后立即校验真实像素尺寸；尺寸不符直接失败。
3. 记录浏览器报告的 `window.devicePixelRatio`，要求等于 2。
4. 禁止 runner 调用 `prepare_ui_candidate.py` 进行上采样；该脚本只可保留为诊断工具，不能生成正式候选。
5. 更新 UI execution builder，使 logical viewport、DPR、physical viewport 分字段校验，消除 `viewport-contract-mismatch`。
6. 新增测试覆盖 DPR 缺失、DPR=1、截图尺寸不符、派生图冒充原图等失败路径。

退出条件：空白或最小状态的 Browser 原始截图本身就是 2880x1800，manifest 能证明它来自 DPR 2 会话，而非后处理。

### 5.2 Browser 本地文件与 catalog→workflow 路径

1. 使用产品真实 API/文件选择入口向受控 Browser 提供冻结 fixture；不通过 query 参数直接伪造完成态。
2. 文件被选中后必须经过项目实际导入、校验、任务创建、进度、完成和导出路径。
3. trace 必须包含用户可见动作、API 请求、任务状态和最终文件 hash。
4. 对非法扩展名、重复图片、缺图、任务失败增加 fail-closed 测试。

退出条件：Browser 可以从 Catalog 或真实文件输入进入 HDR、Focus、Panorama，并生成可验证输出。

### 5.3 Native Computer Use 采集约束

1. 每次采集前验证 Luminar Neo 位于前台且为 macOS 全屏；窗口化、被遮挡或版本不符立即中止。
2. 固定 locale、显示缩放、输入素材、初始 catalog 和工具状态。
3. 采集 screenshot、AX、窗口边界、操作时间、输入 hash 和导出 hash。
4. 当前没有可用的独立虚拟 macOS 指针/显示器时，保持共享桌面现状；分批采集并避免与用户同时操作。
5. 若后续获得可靠虚拟显示/虚拟鼠标，必须先用一个非正式合同验证坐标、Retina、全屏和导出行为，再替换正式采集环境。

退出条件：Native 新证据全部带有 full-screen preflight，且没有把虚拟隔离能力写成未经验证的事实。

## 6. Phase 2：补齐 Native 真值与有效 fixture

### 6.1 Preset import/preview/apply

1. 只接受由当前 Luminar Neo 正式导出或可验证来源的真实 collection/package。
2. 先在隔离目录保存其 hash、文件树、元数据和预览图，不修改冻结 reference。
3. 在全屏 Native 中依次执行导入、列表出现、悬停/点击预览、应用、强度变化、导出。
4. 对每一步记录 AX、截图、输入/输出 hash 和撤销历史。
5. 合成 `.lnpc` 已被 Native 拒绝，不再投入工程时间伪造包格式。

退出条件：取得一个真实可重复导入的包，并形成完整 Native observation。若始终没有真实包，合同保持 blocked，不得用 `.lnp` 目录替代 package 成功。

### 6.2 HDR、Focus、Panorama

HDR 和 Focus 已有 Native 成功证据，主要补 Panorama：

1. 准备最小 2 图和 3 图两组有足够重叠、曝光合理、EXIF 明确的 fixture。
2. 先在 Native 手工验证输入是否被识别，再运行自动采集。
3. 记录开始时间、CPU/GPU 活动、AX spinner、按钮 enabled 状态、应用日志和超时点。
4. 使用分级超时：启动、特征匹配、预览生成、Continue 可用、最终导出分别计时，避免只有一个 420 秒黑盒超时。
5. 若最小有效 fixture 成功，冻结该组输入并用于 Browser；若多组有效输入均稳定卡死，记录为 Native 1.28.0 可复现缺陷。
6. Native 自身缺陷不能由 zpixel 假装成功来关闭“与本机行为一致”的合同；应明确比较错误/超时行为，或由用户决定是否从产品范围中移除，不能静默改为 optional。

退出条件：三类工作流均拥有明确的 Native 行为真值；成功路径必须包含完成态和导出，失败路径必须有稳定可复现证据。

### 6.3 LUT 重观察

1. 重新选择一个真实 LUT 资产和一张能产生稳定变化的冻结输入。
2. 在 Native 中采集 zero/mid/full 三档、preview/export 和关闭工具后的 identity。
3. 执行变化审计，确认 reference 不是原图复制、空输出或错误资产。
4. 只有新 reference 通过完整证据校验后，才能恢复 LUT 合同；否则继续保持 invalid，而不是计入失败分母或通过分母。

## 7. Phase 3：主效果从 33/40 收敛到 40/40

### 7.1 固定处理顺序

按结构误差和共享依赖处理：

1. Fog；
2. Depth Volume；
3. Sky Replace 与 Blue Hour；
4. Sunrays；
5. Face AI；
6. Magic Lights。

共享 mask、depth、horizon 或 light field 的能力先修底层语义，再校准外观，避免多个效果各自复制一套近似算法。

### 7.2 各效果的可执行校准项

| 效果 | 当前指标 | 优先核验 | 实现方向 | 必须覆盖的 holdout |
|---|---|---|---|---|
| Fog | MAE 0.113488 / SSIM 0.903759 | 深度方向、地平线、主体保护 | 深度分层雾密度、颜色散射、远近衰减 | 有天际线、无天际线、近景主体 |
| Depth Volume | 0.069188 / 0.960300 | depth range、局部对比、foreground | 统一深度归一化、分段曲线、前景保护 | 人像、建筑、平坦场景 |
| Sky Replace | 0.039682 / 0.973711 | sky mask、horizon、edge halo | 天空分割、边缘 refinement、颜色/曝光匹配 | 树枝边缘、建筑边缘、无天空 |
| Blue Hour | 0.039456 / 0.975336 | 天空/前景冷暖分离 | 复用 sky/horizon，分区色调和亮度曲线 | 日落、阴天、低天空占比 |
| Sunrays | 0.053714 / 0.956221 | 光源、遮挡、射线衰减 | visibility field、ray spread、bloom 和主体遮挡 | 光源画内/画外、树木遮挡、无明显天空 |
| Face AI | 0.030175 / 0.984125 | 人脸区域、肤色、强度 | landmark/skin mask 精度与局部映射 | 单人、多人、无人脸、不同肤色/尺度 |
| Magic Lights | 0.005906 / 0.979915 | 小范围光斑结构 | 只校准核大小、位置、衰减和合成，不放宽 SSIM | 点光源、无点光源、不同分辨率 |

### 7.3 每个效果的批次模板

1. 用 Native reference 与当前 candidate 生成 diff、mask overlay、亮度/色彩统计。
2. 明确是检测、区域、曲线、合成还是导出颜色管理问题。
3. 只修改对应根因，新增单元测试或不变量测试。
4. 生成 calibration 的 zero/mid/full preview/export。
5. 生成至少两张不同语义 holdout。
6. 校验 zero identity、强度单调、区域外保护、preview/export 一致。
7. 运行当前效果族 parity；通过后再运行 40 项主效果全集。
8. 若共享组件导致已通过效果回退，批次失败并回滚。

### 7.4 Phase 3 退出条件

- 主效果 40/40；
- 每个新通过效果至少有 calibration + holdout；
- 40 项中没有 shape mismatch；
- 阈值、reference 和比较器未被放宽；
- preview 与 export 均通过，而非只通过一条输出路径。

## 8. Phase 4：扩展 Exact 从 40/69 收敛到 69/69

### 8.1 分组策略

按共享算法族处理 29 个失败，禁止按 29 个 case 分别打补丁：

| 批次 | 效果族 | 主要合同 |
|---|---|---|
| E1 | Face AI、Face Enhancer、Slim People | 区域检测、mask feather、多人独立性、强度曲线 |
| E2 | Fog、Depth、Bokeh、Sunrays、Magic Lights | depth/light field、遮挡、空间衰减 |
| E3 | Blue Hour、Sky、Landscape、Color、Radiance | 天空/前景分区、颜色空间、色调曲线 |
| E4 | Vignette、Grain、Fade、High Key | 坐标归一化、随机性固定、混合与边缘保护 |
| E5 | Denoise、Structure、AI Enhance、Pro Contrast | 频率分离、局部对比、噪声/纹理保护 |
| E6 | Default Effects 与其余单项 | 默认参数、关闭态 identity、序列化/反序列化 |

### 8.2 参数合同

每族至少覆盖：

- zero 为严格 identity；
- low/mid/high/full 的响应方向正确且单调；
- 超出 UI 合法范围的参数 fail closed 或被同样 clamp；
- 多人/多区域不相互污染；
- 随机效果使用固定 seed，并验证跨进程复现；
- 不同分辨率下使用归一化坐标，不写死像素半径；
- preview/export 使用相同核心参数语义；
- 序列化后重新加载得到相同结果。

### 8.3 退出条件

- 扩展 Exact 69/69；
- 主效果仍为 40/40；
- 新增 holdout 不低于各族 2 张；
- 相同输入连续生成的候选 hash 稳定；
- 未引入新的模型 contract pending。

## 9. Phase 5：关闭 Preset 与三类多图 Browser/Native 合同

### 9.1 `preset-import-preview-apply`

实现和验证顺序：

1. 导入 Phase 2 冻结的真实 package；
2. 验证 collection 和 preset 元数据在 UI 可见；
3. 预览不能提交历史；
4. 应用后产生一个可撤销历史节点；
5. 强度变化更新同一操作语义，不产生重复脏节点；
6. 切换照片后各自保持独立状态；
7. 导出像素与当前预览合同一致；
8. 重启项目后仍可读取，不保留旧格式 fallback。

Native 与 Browser 的可见断言、API 断言、截图和输出 hash 均齐全后，合同才能通过。

### 9.2 `multi-image-three-workflows`

对 HDR、Focus、Panorama 分别验证：

1. 从 Catalog/文件输入选中多张真实 fixture；
2. 校验数量和兼容性；
3. 创建任务并显示可验证进度；
4. 允许取消，取消后无残留项目和输出；
5. 完成后进入真实 `multi-image-complete`；
6. 结果回到 Catalog/Editor；
7. 导出存在、尺寸正确、hash 非输入复制；
8. 重复执行结果可复现。

若 Native Panorama 真值是稳定超时，则 Browser 必须匹配该合同定义，不能制造 Native 不存在的成功路径；是否取消此能力只能由明确的范围决策完成。

### 9.3 Phase 5 退出条件

- 定向合同 Native 2/2、Browser 2/2；
- 全部 Native 10/10；
- 全部 Browser 10/10；
- viewport issue 为 0；
- `multi-image-complete` 可由真实流程到达，不依赖 debug flag。

此阶段生成的证据仍属于开发证据；Phase 6 UI 修改完成后，Browser 正式证据必须按最终源码 hash 重录。

## 10. Phase 6：UI 16 状态像素收敛与最终证据重录

### 10.1 先修公共壳

先对 16 状态共同区域建立测量表：

- 字体文件、字号、字重、行高和抗锯齿；
- 顶栏、工作区 rail、左右 panel 的宽度和边界；
- canvas fit、缩放、平移原点和背景；
- 主色、次色、边框、阴影、圆角和透明度；
- 图标资源、viewBox、stroke、尺寸和基线；
- Retina 1 CSS px 到 2 physical px 的映射。

公共 shell 批次通过的标准不是“某张图变好”，而是 16 状态总体 MAE/changed-pixel-ratio 改善且没有明显回退。

### 10.2 再按状态族收敛

顺序固定为：

1. export dialog；
2. denoise、more、info、history；
3. black-white before/after；
4. catalog、presets、multi-image、multi-image-complete；
5. edit、layer-stack、layer-library、tool-expanded、edit-collapsed。

每个状态都必须比较：

- 物理尺寸 2880x1800；
- 全图 MAE、SSIM、changed-pixel-ratio；
- 公共 shell crop；
- 内容 canvas crop；
- panel/header/dialog crop；
- DOM/AX 中关键节点的边界和可见性。

### 10.3 最终 UI 与交互证据

所有 UI 代码冻结后：

1. 计算最终 frontend/source hash；
2. 使用 real DPR 2 runner 重走 16 个状态；
3. 每个状态生成原始 screenshot、DOM、AX、操作 trace 和 manifest；
4. 重走 Browser 10 个交互合同；
5. Native 只在证据受新真值或合同影响时重录，且必须全屏；
6. 运行 current-build validator，拒绝任何旧 hash；
7. 运行 UI pixel suite，不允许派生截图进入候选目录。

### 10.4 Phase 6 退出条件

- UI execution 16/16；
- UI pixel 16/16；
- Browser 10/10；
- Native 10/10；
- 每个证据都绑定最终源码 hash；
- logical 1440x900、DPR 2、physical 2880x1800 三者一致；
- 所有 UI 阈值保持原值。

## 11. Phase 7：SQLite 原生 schema 的严格处理

这是一条独立的产品一致性门禁，不应被当前 34 项 exact 聚合悄悄掩盖。

### 11.1 只读发现

1. 在用户授权的 Luminar Application Support/catalog 位置做定向只读查找，不进行全盘扫描。
2. 先检查文件头，再使用只读 SQLite URI 打开。
3. 采集 `PRAGMA user_version`、`application_id`、`sqlite_master`、索引、外键和触发器。
4. 对 schema 文本做规范化 hash；不复制用户照片路径、标题或个人元数据到仓库。
5. `data.mlcdb` 不是 SQLite，不再围绕它设计兼容表。

### 11.2 一次性替换

取得真实 schema 后：

1. 建立只包含结构和合成数据的 contract fixture；
2. 映射 Catalog、Photo、Edit、Export、Multi-image 的实际读写路径；
3. 一次性替换 `storage/catalogs/luminar_sqlite.py` 的当前 schema；
4. 同一改动中删除旧 schema、旧测试和所有转换代码；
5. 只保留一个 catalog 路径和一个 schema version；
6. 不提供 JSON 读取、双写、旧 schema fallback 或跨版本迁移。

退出条件：真实 schema fingerprint 有来源证据，项目 round-trip、并发、原子性和损坏恢复测试通过，源码中没有历史兼容入口。

若仍未取得真实数据库：保持当前 schema 155 单轨，不虚构 Native 私有兼容；最终声明必须明确写“原生 catalog 私有 schema 未验证”，因此不能做全应用数据格式绝对对齐声明。

## 12. Phase 8：完整回归、遗漏审计与单轮 exact

### 12.1 回归矩阵

必须全部执行：

- Python 全量测试；
- Frontend 全量测试、lint、production build；
- dataset freshness 和采样队列完整性；
- 活动模型 22/22 exact contract；
- 主效果 40/40；
- 扩展 Exact 69/69；
- UI execution/pixel 16/16；
- Native/Browser 10/10；
- 多图三流程 smoke；
- catalog/API round-trip、原子写、并发和单轨扫描；
- exact quality gate。

### 12.2 遗漏审计

在单轮 exact 前做一次独立清点：

1. 搜索 `pending`、`skipped`、`optional`、`invalid-reference`、`stale`、`derived`；
2. 检查是否仍有 JSON catalog、migration、legacy、fallback、dual-write 入口；
3. 检查每个 required 合同是否同时有 reference、candidate、manifest 和指标；
4. 检查所有证据是否属于当前 source hash；
5. 检查 Native 证据是否 full-screen；
6. 检查 UI 截图是否真实 DPR 2；
7. 检查 paid/tutorial/help/account/store/cloud 未进入范围；
8. 检查两个 holdout 是否因为实现变更回退；
9. 检查最新报告分母与配置冻结分母一致；
10. 检查没有人工修改生成报告。

### 12.3 单轮准入

只有上述审计为 0 遗漏，才运行正式单轮 exact。退出条件：

- exact 34/34；
- required failure 0；
- 无 warning 被降级为成功；
- 报告、candidate 和 manifest 位于新的 immutable run 目录。

## 13. Phase 9：连续 A/B 两轮发布证明

### 13.1 运行规则

1. 冻结源码、模型、validation、reference、配置、依赖锁和环境；
2. A、B 使用不同 run id 和独立 candidate 目录；
3. B 不复制 A 的图片、报告、缓存命中或中间产物；
4. 两轮均从同一冻结输入重新生成；
5. 比较 release/source/models/validation/environment/reference fingerprint；
6. 比较所有 required gate、case 指标、输出 hash 和证据数量。

### 13.2 最终退出条件

- A = 34/34，required failure 0；
- B = 34/34，required failure 0；
- `compare_exact_runs.py` passed；
- fingerprint 完全相同；
- 无 case 依赖重试次数、顺序或旧缓存；
- SQLite 私有 schema 的声明边界已明确；
- 发布报告列出范围内能力与排除项。

任何一轮失败都返回对应 Phase 修复；禁止只重跑到偶然成功。

## 14. 可直接执行的命令模板

以下命令均从项目根目录执行。`<run-id>`、`<path>` 必须替换为本批次唯一值；不得复用正式 run id。

### 14.1 定向候选与效果对比

```bash
.venv/bin/python scripts/generate_candidate_outputs.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability> \
  --force

.venv/bin/python scripts/run_parity_suite.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --capability <capability> \
  --scope in-scope-free \
  --output <path>
```

### 14.2 Native 交互观察

```bash
.venv/bin/python scripts/run_luminar_interaction_observations.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --contract-id <contract-id> \
  --allow-ui-control
```

该命令只在 Luminar Neo 已处于前台全屏、用户未同时操作共享桌面时执行。

### 14.3 Browser interaction 与 UI evidence

```bash
.venv/bin/python scripts/build_interaction_browser_execution.py \
  --raw <raw-trace.json> \
  --evidence-root <evidence-dir> \
  --native-root <native-evidence-dir> \
  --output <interaction-execution.json>

.venv/bin/python scripts/validate_interaction_execution.py \
  --execution <interaction-execution.json> \
  --output <interaction-validation.json>

.venv/bin/python scripts/build_ui_browser_execution.py \
  --browser <browser> \
  --browser-version <version> \
  --logical-width 1440 \
  --logical-height 900 \
  --device-scale-factor 2 \
  --source-captures <real-dpr2-capture-dir> \
  --output <ui-execution.json>

.venv/bin/python scripts/validate_ui_execution_evidence.py \
  --execution <ui-execution.json> \
  --output <ui-evidence-validation.json>
```

### 14.4 多图 smoke

```bash
.venv/bin/python scripts/run_multi_image_workflow_smoke.py \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --validation-root test_data/parity/inputs \
  --output <multi-image-smoke.json>
```

### 14.5 全量测试与构建

```bash
.venv/bin/pytest
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 14.6 正式 exact 与 A/B 比较

```bash
.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id <run-a>

.venv/bin/python scripts/run_quality_gates.py \
  --level exact \
  --reference-id luminar-neo-macos-1.28.0-23071 \
  --run-id <run-b>

.venv/bin/python scripts/compare_exact_runs.py \
  --first <run-a-report.json> \
  --second <run-b-report.json> \
  --output <comparison.json>
```

## 15. 执行批次与工作量控制

不以日期代替验收，使用以下最大批次控制风险：

| 阶段 | 建议批次数 | 单批上限 | 阶段结束产物 |
|---|---:|---|---|
| Phase 0 | 1 | 只读基线 | 冻结账本与 hash |
| Phase 1 | 3 | 一个采集能力 | DPR 2、文件输入、全屏 preflight |
| Phase 2 | 3 | 一个 Native 真值族 | Preset、Panorama、LUT 证据 |
| Phase 3 | 6 | 一个共享效果根因 | 主效果 40/40 |
| Phase 4 | 6 | 一个效果族 | 扩展 69/69 |
| Phase 5 | 2 | 一个交互合同 | Native/Browser 10/10 开发证据 |
| Phase 6 | 4–6 | 公共壳或一个状态族 | UI 16/16 正式证据 |
| Phase 7 | 1–3 | 发现、映射、替换分开 | SQLite 声明闭合或明确 blocked |
| Phase 8 | 1 | 全量回归 | 单轮 34/34 |
| Phase 9 | 2 | 每轮独立 | A/B 发布证明 |

任一阶段连续两批没有改善时，停止参数微调，回到 Native 真值、输入有效性或共享算法假设重新诊断。

## 16. 最终验收清单

- [ ] 活动模型 22/22，pending 0；
- [ ] 主效果 40/40；
- [ ] 扩展 Exact 69/69；
- [ ] Preset 使用真实 package 完成 Native/Browser 合同；
- [ ] HDR、Focus、Panorama 的 Native 真值和 Browser 行为完整；
- [ ] UI execution 16/16；
- [ ] UI pixel 16/16；
- [ ] UI 原始截图为 logical 1440x900 / DPR 2 / physical 2880x1800；
- [ ] Native 10/10 且新采样均为 Luminar 全屏；
- [ ] Browser 10/10 且无 debug shortcut；
- [ ] LUT reference 已重观察并通过有效性审计，或继续明确 invalid；
- [ ] SQLite 只有一个 schema、一个路径，无 JSON、migration、legacy、fallback、dual-write；
- [ ] 若未取得 Luminar 私有 schema，最终声明明确保留该限制；
- [ ] Python、Frontend、lint、build、多图和 catalog 回归全部通过；
- [ ] 单轮 exact 34/34，required failure 0；
- [ ] A/B 两轮独立生成且 fingerprint 完全相同；
- [ ] 没有阈值放宽、case 特判、旧 hash、派生 DPR 2 图或人工证据；
- [ ] 付费、教程、帮助、账号、商店、云能力仍明确排除。

只有清单全部关闭，且 SQLite 声明边界不被夸大时，才发布严格对齐结论。
