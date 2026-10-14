# Luminar Neo 核心严格对齐 R15 执行报告

## 结论

R15 已完成一轮真实 Native 采样、天空合同收敛、代码实现、全量回归和最新源码 exact 实跑。当前不能声明与本机 Luminar Neo 绝对对齐。

最终 exact 结果为 **29/37 passed、8/37 failed**。主效果仍为 **35/40 passed、5/40 failed**；增量 exact 仍为 **61/69 passed、8/69 failed**。本轮的实质改进是把天空从推测合同切换为本机 Luminar Neo 1.28.0 (23071) 的真实 18 控件合同，并消除旧天空参数导致的候选生成 422；没有降低 MAE/SSIM 阈值，也没有增加历史兼容层。

机器摘要见 `test_data/outputs/luminar-1.28.0-23071/diagnostics/alignment-r15-execution-summary.json`，最终门禁见 `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r15-final.json`。

## 本轮实际采集

采集使用本机全屏 Luminar Neo，逻辑窗口 1440×900，正式预检物理截图 2880×1800。系统中没有找到能证明显示与输入都隔离的虚拟屏幕方案，因此在用户明确允许 `--allow-ui-control` 后使用当前桌面；采集期间会占用前台和鼠标。付费、升级、商店、账户、云、教程、帮助、推广和许可流程均未进入范围。

实际完成：

1. 展开 Sky AI 及天空方向、蒙板细调、场景改光、反射、天空调整五个子区。
2. 对 16 个数值控件执行上下界钳位探测，并读取 1 个布尔控件和 1 个资产选择器，冻结 18 项 Native 合同。
3. 精确选择并回读 `Blue Sky 1`，没有用低置信度缩略图匹配替代。
4. 在同一输入 `008_e45cd3c34a.jpg` 上设置并回读 `SkyGlobal=100`，导出 1080×1440、sRGB、8-bit PNG。导出 SHA-256 为 `6b88b47fd6e5644cdb3528180e25d2aa549f88ec15c38a153286ce1d62eb990e`。
5. 恢复并回读 Native 默认 `SkyGlobal=30`，保存全屏 UI 锚点。默认值导出时 macOS 存储面板未启用“存储”，因此没有伪造默认导出成功。
6. 最终再次确认 `SkyGlobal=30`，没有把应用留在 100。

证据：

- 控件合同：`test_data/outputs/luminar-1.28.0-23071/observations/sky-r15-fullscreen/native-control-contract.json`
- 100 原生效果样本：`test_data/outputs/luminar-1.28.0-23071/observations/sky-r15-fullscreen/native-effect-sample-sky-global-100.json`
- 30 UI 锚点：`test_data/outputs/luminar-1.28.0-23071/observations/sky-r15-fullscreen/native-ui-anchor-sky-global-30.json`
- 100 原生导出：`test_data/outputs/luminar-1.28.0-23071/native-exports/r15-sky-global-100.png`

## 已实现内容

### 天空 UI 与参数合同

- 将天空公开 UI 收敛为本机 Native 的 18 项：资产、地平线、垂直、水平、翻转、修复细节、全局、消除间隙、三项场景改光、两项反射和五项天空调整。
- 删除 Native UI 中不存在的公开 `sky_scale`、`horizon_blending`、`rotation`、`contrast`、`saturation` 和主 amount 控件。
- 前端保留 Native 数值范围和默认值，通过单一转换函数映射到当前合成器的内部归一化参数。转换函数明确标记为待原生曲线标定，不冒充效果精确。
- `parameter-schema.json` 区分 18 项公开 Native 合同和 `amount / opacity / asset_path` 内部参数；内部参数由通用校验器按声明验证，而不是作为历史兼容字段硬塞回公开 UI。
- 更新主天空 case，只使用当前 Native 合同。单 case 候选生成从 HTTP 422 变为 1/1 成功。

### 天空效果与采样器

- 修复前景改光：旧实现用前景区域的 `result - base` 计算色差，该差值恒为零；新实现从替换天空区域估计颜色偏移，再按前景/人物遮罩应用。
- 为 16 个天空数值参数增加 purpose sampler 精确绑定和 readback 基础设施。
- 删除“资产索引 0 等于首个可见缩略图”的不可靠快捷路径。该路径在真实应用中选到了 `Sunset 1`；现在自动采样继续严格失败闭合。
- 采样队列支持显式 `parameter_binding`，但在其完成稳定的资产语义识别和三锚点回归前不登记为正式 passed。

### UI、交互和发布责任矩阵

- 新增并生成完整核心 UI 定义矩阵：40 个能力、210 个状态，其中 16 个旧状态、80 个 collapsed/expanded 状态、114 个参数状态。
- 新增并生成完整核心交互定义矩阵：124 个合同，其中 10 个旧合同、114 个参数合同。
- 两个定义 validator 均为 passed；execution gate 均保持 pending，禁止把“定义完整”写成“实测完成”。
- 两个矩阵进入 release fingerprint 验证根。

## 验证结果

### 代码验证

- Python：398 passed，1 个第三方弃用 warning。
- 前端：43 passed；生产构建通过。
- 定向天空、采样器、矩阵测试：60 passed。
- Ruff：全部通过。
- UI 定义矩阵：210/210 definition passed，execution pending。
- 交互定义矩阵：124/124 definition passed，execution pending。

### 模型合同

- 当前 required 逻辑模型为 22 个，22/22 model-specific validated，pending 0。
- 当前激活的模型调用 case 为 18 个，18/18 passed。
- runtime policy 为 ONNX Runtime 主路径、OpenVINO fallback，CoreML reference 0。
- 模型 pipeline audit 仍显示 8 ready、4 blocked；因此模型合同通过不应被扩展解释为所有上层效果均 exact。

### 最新 exact 门禁

release fingerprint：`be312f1cdfad1e6563d19619779a42b7d2a2720efa0b782222ece90ef6f6b9ad`。

失败的 8 个 required gate：

1. `absolute-scope-coverage`：58 个问题。
2. `luminar-reference-captures`：39 ready、1 invalid；天空旧 reference 与新参数合同发生 `metadata-parameters-mismatch`。
3. `output-parity`：35/40 passed、5 failed。
4. `exact-incremental-parity`：61/69 passed、8 failed。
5. `ui-execution-evidence`：16/16 executed，但当前源码/build hash 下 0 passed，原因为 stale frontend build evidence。
6. `ui-parity`：0/16 pixel passed。
7. `interaction-execution`：8/10 passed，并存在 viewport/DPR/build 环境问题。
8. `native-persistence-roundtrip`：缺少七类 Native roundtrip manifest。

## 执行前后对比

| 指标 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| 主效果 | 35/40 | 35/40 | 效果分数未提高；天空从旧合同改为真实合同后仍严格失败 |
| 增量 exact | 61/69 | 61/69 | 未变化 |
| 顶层 exact | 37 个 required | 29/37 passed | 仍 blocked |
| scope issue | 59 | 58 | 减少 1；unrepresented parameter 从 16 降到 6 |
| 当前 build 交互旧子集 | 5/10 | 8/10 | 增加 3，但仍缺 2 个执行且环境合同不完整 |
| UI 像素旧子集 | 0/16 | 0/16 | 未变化，必须重录当前 build |
| 完整 UI 定义责任 | 无完整分母 | 210/210 definition | 新增完整分母，执行仍 pending |
| 完整交互定义责任 | 无完整分母 | 124/124 definition | 新增完整分母，执行仍 pending |
| 天空真实控件合同 | 未冻结 | 18/18 | 已完成 |
| 天空真实效果锚点 | 0 | 1 个原生导出 + 1 个 UI 锚点 | 仍不足以拟合曲线 |
| Python 回归 | 392 | 398 | +6，全部通过 |
| 前端回归 | 43 | 43 | 全部通过 |

## 仍有遗漏

### 效果

- 主效果失败：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。
- exact 失败：`face_ai` 两例，以及 `sunrays`、`structure_ai`、`ai_enhance`、`depth_volume`、`blue_hour`、`landscape_enhancer`。
- 天空新合同没有匹配的 canonical Native reference。已有旧导出虽然能计算指标，但元数据不匹配，不能作为新合同正式 reference。
- `SkyGlobal` 只有 100 的原生导出；4 和 30 的原生导出、第二输入 holdout 和其余 17 参数的单变量曲线尚未完成。

### 范围、UI 与交互

- 58 个 scope 问题：40 个能力缺 holdout，9 个能力缺 exact amount anchor，6 个 crop 参数未被 case 表达，1 个 Native 交互和 2 个 Browser 交互缺失。
- 210 个 UI 状态和 124 个交互合同只有定义分母，没有逐项执行证据。
- 当前 16 个旧 UI 状态需要绑定最新 source/build hash、1440×900 CSS viewport、DPR 2、2880×1800 物理截图、DOM/AX snapshot 后重录。
- 交互仍缺 `preset-import-preview-apply` 和 `multi-image-three-workflows`，并要修复 DPR、物理 viewport、browser environment 和 stale build 证据。

### Persistence

- 没有找到本机 Luminar catalog 的真实 SQLite schema。
- 不能编造 schema，也不能以 JSON/SQLite 双写掩盖缺失。
- 当前 exact 仍缺 project、edit-history、layer、mask、workflow、preset、preview-export 七类 Native roundtrip manifest。

## 下一步可执行顺序

1. **先关闭天空 reference 身份问题。** 在全屏 Luminar 中用新 Native 默认合同重新采集 canonical：`Blue Sky 1`、18 控件默认值、同一输入/导出设置；保存 AX、截图、参数 readback、输入/资产/输出 hash。旧天空 reference 保留为旧证据，不改标签。
2. **完成天空单变量曲线。** 先采 `SkyGlobal=4/30/100` 的 canonical 与 holdout 原生导出；再按 17 个其余参数的 Native min/default/max 或语义锚点生成队列。每次只改一个参数，资产和所有其他参数固定。
3. **以原生曲线替换临时映射。** 对每个参数拟合单调或分段响应，加入 canonical + holdout 回归；不降低阈值。天空主 case 和相关 exact anchors 全绿后才标记 sky effect exact。
4. **关闭其余 4 个主效果和 8 个 exact case。** 优先按误差规模处理 `depth_volume / sunrays / blue_hour`，再处理 `face_ai` 和 exact-only `structure_ai / ai_enhance / landscape_enhancer`。每项固定 reference、阈值和输入 hash。
5. **把 scope 58 降到 0。** 为 40 个能力各补至少一个 holdout；补 9 个 amount anchor；补 crop 的 6 个参数 case；补 3 个交互证据。
6. **重录 UI。** 先使旧 16/16 在当前 build 下恢复 pixel passed，再按 210 状态矩阵逐工具、逐参数、逐弹层扩展；共享组件修复可以复用代码，但不能复用最终截图结论。
7. **完成 124 个交互执行。** 优先关闭旧 10 个正式合同，再补右键/子菜单、滚动、工具展开、历史、图层/遮罩、多图、导出等参数合同；每条绑定 Browser/Native 双证据。
8. **Persistence 只走真实单轨。** 找到本机真实 Luminar catalog schema 后，一次性迁移并删除 JSON primary、投影、旧 reader 和双写；再生成七类 restart roundtrip manifest。
9. **最后运行同指纹双轮 exact。** 只有单轮 37/37 后才冻结源码、模型、素材、reference、环境五类指纹；连续 A/B 两轮都必须 37/37、required failure=0，才能声明绝对对齐。

## 声明边界

本轮完成的是合同真实性、一个真实天空效果锚点、实现修正和最新门禁审计，不是核心功能完全收敛。所有尚无匹配 Native reference、当前 build UI 像素证据、完整交互执行或真实 persistence schema 的领域继续保持 blocked。
