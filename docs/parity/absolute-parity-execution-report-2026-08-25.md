# Luminar Neo 1.28 绝对对齐执行报告（最终复核）

> 复核日期：2026-08-25  
> 原生基准：本机 Luminar Neo `1.28.0 (23071)` / `com.skylum.luminarneo` / macOS / `zh-Hans`  
> Reference ID：`luminar-neo-macos-1.28.0-23071`  
> 本文只描述当前有效实现和证据，不保留旧版本兼容结论。

## 1. 最终结论

本轮计划已按数据源、原生采样、候选生成、效果、UI、交互、模型、回归、清理和发布门禁逐项执行。采样与候选数据链已闭合，重复和无变化导出已清理，黑白与降噪的原生前置交互已纳入采样合同，应用内 Browser 已恢复并完成 7 个 current-build UI 状态采集，代码回归全部通过。

项目目前仍不能声明与本机 Luminar Neo 1.28 “绝对对齐”。最终 28 个质量门禁中 22 个通过、5 个 required 失败、1 个 optional 失败，发布状态为 `blocked`。剩余 required 阻塞是：

1. Multi-image：`2/3`，Panorama 未通过；
2. 主效果输出：`36/45`，9 条失败；
3. 精确锚点输出：`38/69`，31 条失败、0 条 pending；
4. UI 像素对齐：`0/7`；
5. 原生/本项目交互执行证据：`0/10`。

上述失败均保留真实门限和真实证据，没有通过放宽 MAE/SSIM、伪造交互记录、把 JPEG 重编码差异当作有效效果，或对单张 reference 增加特例来消除红灯。

## 2. 本轮完成内容

### 2.1 数据链、队列和“已采样不重复采样”

- 将 exact active cohort 与增量 worklist 的职责分离，队列按 source hash、能力、参数、素材和 recipe 形成稳定 semantic key；
- 原始数据集 snapshot/fingerprint 恢复一致，dataset freshness 通过；
- 主采样队列 `251/251`，exact 活动数据链 `69/69`，候选生成 `69/69`；
- resume 只选择缺失、作废或 reference hash 漂移的记录，已经 ready 且 hash 一致的记录不再采样；
- Overlay 仅重采 4 条确认无效/被覆盖的旧记录，其他已通过记录未重复采样，最终 `38/38`。

### 2.2 原生交互与有效效果判定

采样器现在以“控件提交成功 + 原生编辑状态成立 + 图像确实变化”为非中性效果的共同条件：

1. 参数写入后必须从 AX 控件读回；
2. 非中性效果导出前，Luminar 的 `ResetAllEdits` 必须存在且 enabled；
3. 导出与源图变化必须超过 recipe 对应门限；
4. preview/export 必须满足一致性约束；
5. 任一条件不成立时记录失败，不发布 canonical，也不进入成功去重集合。

这直接覆盖“看似导出了，但效果没有应用”和“导出后没有恢复原始状态选项”的问题。

特殊前置交互已经固化：

- 黑白：先点击 `转换为黑白`，再启用亮度/饱和度和通道滑杆；本项目 UI 同样在转换前禁用这些控件；
- 降噪：先选择原生降噪等级，本轮使用 `Noiseless.Mid`，再提交强度；不选择等级的无效果结果不再发布；
- Neon：包含工具激活和画布 stroke；
- Overlay：素材、源图、前后 AX 状态和最终导出 hash 都进入证据合同。

### 2.3 导出卡住与重命名耗时

保存面板不再为每个动作遍历完整 AX 树，而是优先通过稳定 identifier 执行 `read/set/press first`：

- 直接读取保存目录；
- 设置 `saveAsNameTextField`；
- 点击 `OKButton`；
- 每次使用唯一文件名，等待文件大小稳定后原子发布 canonical；
- 开始新任务前关闭遗留保存面板，避免上一次中断污染后续任务。

已验证样本中，保存面板定位、改名和确认由 `70.517 s` 降至 `1.715 s`，下降约 `97.6%`；完整导出约 `4.812 s`。文件稳定等待仍保留，因为取消它会读取未完成文件。

### 2.4 黑白效果实现

本项目已增加与原生一致的交互状态：

- 初始只显示可用的 `转换为黑白`；
- 转换前亮度、饱和度和应用按钮不可用；
- 转换后解锁分栏和 signed 通道参数；
- 后端默认黑白转换产生灰度输出，`converted=false` 才显式保留彩色源图；
- 红色亮度通道按 `-1 / 0 / +1` 原生锚点做连续分段映射，不查询 fixture、不硬编码单张图片。

三个 exact 黑白锚点全部通过：

| 锚点 | MAE | SSIM | 结果 |
|---:|---:|---:|---|
| `0` | 0.00600 | 0.99950 | passed |
| `-1` | 0.00934 | 0.99829 | passed |
| `+1` | 0.01031 | 0.99858 | passed |

### 2.5 Multi-image、Overlay 和效果

- Overlay：`37/38 → 38/38`；Night Rain 和另外 3 条 AX-before hash 被覆盖的旧样本仅做 targeted resample；
- HDR：通过；
- Focus：通过；
- Panorama：候选 shape 已统一到可比较输出，但原生仍包含不同投影、warp、接缝与非对称 auto-crop，当前 MAE 约 `0.0819`、SSIM 约 `0.8155`，保持失败；
- 主效果：`36/45`，失败能力为 Face AI、Slim People、Depth Volume、LUT Mapping、Blue Hour、Fog、Sky Replace、Sunrays（2 条）；
- exact：`38/69`，失败 31 条，主要集中在人物/深度、天空/光照、细节/噪声、颜色/色调和全局风格五类。

exact 失败按能力计数：

| 数量 | 能力 |
|---:|---|
| 2 | Vignette、Grain、Face Enhancer、Face AI、Depth Volume、Default Effects |
| 1 | Sunrays、Structure AI、Slim People、Radiance、Pro Contrast、New Neon Light、Magic Lights、Landscape Enhancer、High Key、Fog、Fade、Denoise Laplacian、Denoise、Color Toning、Color Enhancer、Color Adjustments、Bokeh AI、Blue Hour、AI Enhance |

### 2.6 UI 与交互证据

应用内 Browser 已恢复，使用固定 `2880×1800` viewport 实际运行本项目，并采集 Catalog、Presets、Edit、Layer Stack、Layer Library、Tool Expanded、Multi-image 共 7 个状态：

- current-build 执行证据：`7/7 passed`；
- 原生 UI reference manifest：有效；
- 像素门禁：`0/7`。

当前 MAE 为：Catalog `0.1780`、Presets `0.2431`、Edit `0.2241`、Layer Stack `0.2197`、Layer Library `0.2263`、Tool Expanded `0.2164`、Multi-image `0.1091`。这属于布局、组件层级、信息密度和状态呈现的结构性差异，不适合只调颜色 token。

10 个 interaction contract 的 schema 均有效，但 `interaction execution` 仍为 `0/10`：当前缺少 10 条原生 observation 和 10 条对应 Browser execution；验证器共报告 22 个问题（另含 browser environment/reference id 元数据问题）。本轮没有用单测替代产品交互证据。

### 2.7 模型和长耗时任务

- required logical model：`22/22` model-specific source/contract 通过；
- model source：95 个源文件、92 个注册模型，required pending 为 0；
- 模型 pipeline 审计：12 ready、0 blocked；
- exact candidate invocation：`22/22`，16 个实际调用合同全部验证；
- 长任务保留持久化 job、逐模型 checkpoint、lease heartbeat、幂等恢复和终态合并；长模型在执行期间不会因无阶段结果被其他 worker 错误回收；
- optional 全量库存仍为 26 个 model-specific、66 个待行为校准。66 个不可达/非 required 模型不是当前 required 发布阻塞，不应先于用户可达链路过度实现。

## 3. test_data 整理与重复导出清理

目录已收敛到当前 1.28 profile：

- 删除用户指定的 `test_data/luminar_1_26`；
- 删除 inactive 1.25/1.26 reference、旧 captures/observations、旧配置入口和空目录；
- `test_data/outputs` 根目录散落导出已迁入 `outputs/luminar-1.28.0-23071` 的合适目录；
- 原生导出按 semantic capture 保留一个 canonical，有效中性锚点和不同参数锚点仍分别保留，因为它们不是重复效果；
- 删除无变化、无 canonical 指针、被更新 reference 替代、重复尝试和可重建 workspace；
- 清理后原生 canonical export 为 91，重复 export 为 0，transient path 为 0；
- 最终 cleanup postcheck：0 个剩余路径、0 bytes 可回收。

已保存的 applied 报告累计回收 `3,048,394,319` bytes（约 3.05 GB），不含旧版本目录删除量。本轮最后一次定向清理额外回收 `715,755,906` bytes。

当前 `test_data` 约 4.3 GB：

- 约 3.0 GB 为 339 条 ready capture 的原生/canonical 审计证据；
- 约 1.0 GB 为当前主候选和 exact 候选；
- 原始数据、versioned reference、当前候选、失败诊断和关键 UI 截图均保留。

这些保留项直接参与当前门禁，不属于无意义历史。已清除的数据为直接删除，只能通过外部备份恢复。

## 4. 执行前后对比

| 域 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| required 门禁 | 18 passed / 9 failed | 22 passed / 5 failed | 明显收敛，仍 blocked |
| 主采样证据 | 248/251 | 251/251 | 闭环 |
| exact 数据链 | 60/69 | 69/69 | 闭环 |
| exact 候选 | 有 pending | 69/69，pending 0 | 闭环 |
| exact parity | 旧口径 41 pass / 26 fail / 2 pending | 38 pass / 31 fail / 0 pending | 全量可信 reference 后口径更严格，不直接按 pass 数比较 |
| Overlay | 37/38 | 38/38 | 闭环 |
| Multi-image | 2/3 | 2/3 | Panorama 未闭环 |
| 黑白 exact | 旧转换/控件合同不完整 | 3/3 | 效果与交互闭环 |
| UI current-build evidence | 0/7 | 7/7 | 采集闭环 |
| UI 像素 parity | 0/7 | 0/7 | 结构性未对齐 |
| Interaction execution | 0/10 | 0/10 | 原生 observation runner 缺失 |
| Required models | 22/22 | 22/22 | 保持通过 |
| Python 测试 | 265 passed | 277 passed | 通过 |
| Frontend 测试 | 12 passed | 13 passed | 通过 |
| 可清理重复/临时数据 | 多批历史与 workspace | 0 | 闭环，累计约 3.05 GB |

注意：exact pass 数从 41 变成 38 不是代码退化结论。执行前只有 60/69 reference 可信且还有 pending；执行后 69/69 均进入同一严格口径，失败集合变得完整、可行动。

## 5. 回归与最终门禁

代码回归：

- Python：`277 passed`，仅 1 个 Starlette 第三方弃用警告；
- Frontend：6 个 test files、`13 passed`；
- TypeScript/Vite production build：通过；
- Ruff：通过；
- 长任务 checkpoint/幂等/complete 专项：通过；
- Denoise 选择等级、黑白转换门控、无效果导出拒绝、质量门禁 candidate-root 路径均有回归覆盖。

最终质量门禁：`28` 总数，`22 passed`、`5 required failed`、`1 optional failed`，状态 `blocked`。

Required 失败：

1. `multi-image`：Panorama；
2. `output-parity`：36/45；
3. `exact-incremental-parity`：38/69；
4. `ui-parity`：0/7；
5. `interaction-execution`：0/10。

Optional 失败：`model-contract-inventory`，原因是 66 个非 required 模型尚未逐模型行为校准。

## 6. 遗漏确认

本轮实现、采样、清理和验证步骤已经执行完；“绝对对齐”目标本身仍有以下真实遗漏：

1. 缺少原生 interaction observation 自动采集器。文档中规划的 `scripts/run_luminar_interaction_observations.py` 当前不存在；这是 10/10 交互门禁的第一阻塞，不是 Browser 连接问题；
2. 31 个 exact 失败需要按能力簇校准处理语义。现有 reference 已完整，不需要再次全量采样；只有证明 reference 或交互前置错误时才 targeted reobserve；
3. 9 个主效果失败中，天空/深度/人物几何差异最大；LUT 只超 MAE，Face AI 只略超 MAE，但仍不得调阈值通过；
4. Panorama 缺少 Luminar 的投影模型、特征匹配、局部 warp、接缝优化和非对称 auto-crop；
5. 7 个 UI 状态均存在大面积结构差异；
6. optional 66 个模型没有全部行为校准，但它们不应抢占当前用户可达 required 链路的优先级。

## 7. 下一阶段可执行计划

### P0：先关闭交互证据（1 个迭代）

1. 实现原生 observation runner，只负责 10 个冻结 contract：Catalog 导入选择、Preset preview/apply、滑杆拖动、工具折叠、图层增删改序/透明度、Undo/Redo、Before/After、Zoom/Pan、Export Dialog、Multi-image；
2. 每条 observation 记录 before/after AX snapshot、关键控件 identifier/value/enabled、截图、输入 hash、版本和完成信号；
3. 在应用内 Browser 对本项目执行同一 contract，保存 DOM/state/screenshot/网络终态；
4. 由 validator 做逐步状态对比，不用“点击成功”代替结果状态；
5. 验收：interaction execution `10/10`，且 reference id/environment 元数据问题为 0。

### P1：按误差域校准 31 个 exact 和 9 个主效果（2–4 个迭代）

按共享处理语义分组，不按 case 写特例：

1. 人物/深度：Face AI、Face Enhancer、Slim People、Bokeh AI、Depth Volume；先统一人物 mask、深度图、边缘 feather、几何 warp；
2. 天空/光照：Blue Hour、Fog、Sunrays、Magic Lights、Neon、Landscape；统一 sky mask、horizon、散射、光源空间和局部遮挡；
3. 噪声/纹理：Denoise、Denoise Laplacian、Grain、Structure AI；把原生等级与强度分别建模，使用现有 sensor-noise fixture，不重采已 valid case；
4. 色彩/风格：Color Adjustments、Color Enhancer、Color Toning、Fade、High Key、Radiance、Pro Contrast、Vignette、Default Effects、AI Enhance；校准工作色域、tone curve、局部权重和参数非线性；
5. 每次只改变一个共享语义，先跑对应 exact anchors，再跑 smoke/holdout；任何 reference 重采必须先有 source/AX/effect-state 异常证据；
6. 验收：主效果 `45/45`，exact `69/69`，连续两次 required gate 失败集合一致为空。

### P2：实现 Panorama 原生语义（1–2 个迭代）

1. 估计 Luminar 的投影类型和有效视场，不使用最终 resize 掩盖尺寸；
2. 增加特征匹配 + RANSAC homography/局部 warp；
3. 对齐曝光补偿、seam mask 和 multiband blending；
4. 从有效像素边界推导非对称 auto-crop；
5. 用现有三张冻结输入验证 shape、MAE、SSIM 和接缝 ROI；
6. 验收：Multi-image `3/3`。

### P3：按原生状态重建 UI（2–3 个迭代）

1. 先处理结构：顶栏高度、左右栏宽、画布占比、底部胶片栏、工具分组与图层区域；
2. 再处理组件状态：selected/hover/disabled/expanded、滑杆轨道/数值、素材卡、弹窗、导出页；
3. 最后收敛 token：字体、字号、行高、间距、边框、阴影和颜色；
4. 每个状态独立 screenshot diff，并使用最大误差区域决定下一次修改；
5. 保持已通过的黑白门控与现有行为测试；
6. 验收：7 个固定状态全部通过 UI 门禁，并用 10 个 interaction contract 防止视觉修复破坏交互。

### P4：冻结与发布

只有同时满足以下条件才可更新“绝对对齐”声明：

- 数据链和采样证据全通过；
- 主效果 45/45、exact 69/69；
- Overlay 38/38、Multi-image 3/3；
- UI 7/7、interaction 10/10；
- required model 22/22；
- 连续两轮 28-gate required failure 为 0；
- 最终 cleanup dry-run 为 0，且 source/reference/candidate hash 冻结。

optional 66 个模型仅在产品 UI/API 变为可达或纳入发布范围时再进入 required inventory。

## 8. 关键证据

- 最终门禁：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final.json`
- 主效果：`test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report.json`
- exact：`test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-incremental-parity.json`
- exact 数据链：`test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-incremental-data-chain.json`
- Overlay：`test_data/outputs/luminar-1.28.0-23071/diagnostics/overlay-e2e.json`
- Multi-image：`test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke.json`
- UI 执行：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence.json`
- UI 对比：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json`
- Interaction：`test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution.json`
- 模型源：`test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map-current.json`
- 原生导出去重：`test_data/outputs/luminar-1.28.0-23071/diagnostics/native-export-prune-final-postcheck.json`
- test_data 清理：`test_data/outputs/luminar-1.28.0-23071/diagnostics/test-data-cleanup-final-postcheck.json`
- 黑白交互截图：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-candidates/2880x1800/black-white-conversion.png`
