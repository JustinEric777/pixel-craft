# Luminar Neo 1.28 效果、UI、交互对齐执行报告（2026-08-24）

> 基线：本机 Luminar Neo `1.28.0 (23071)`、`com.skylum.luminarneo`、macOS、`zh-Hans`。本报告只对冻结输入、合法本地素材和当前产品范围负责，不把“代码可运行”写成“与黑盒产品绝对等价”。

## 1. 最终结论

本轮已完成当前环境中可以安全验证和实现的计划项，并补上模型合同、Overlay 全链路、多图 Focus、前端 zoom/pan、采样文件发布、导出等待和 exact 队列范围验证。代码回归全部通过，候选双跑哈希一致。

项目仍不能声明与 Luminar Neo 完全对齐。当前机器门禁仍明确阻塞：

- smoke 效果 `36/45`，9 个失败；
- Overlay `37/38`，唯一失败 reference 高概率为素材选择错标，不能拟合；
- Multi-image `1/3`，Focus 通过，HDR 与 Panorama 失败；
- UI reference manifest `7/7` 可信，但 current-build 像素比较 `0/7`；
- interaction 合同定义 `10/10`，真实执行 `0/10`；
- required 模型选择合同 `22/22` 完成，但 crop encoder/decoder 条件链仍无可验证运行时；
- 主队列因 3 个历史 AX 文件被硬链接联动覆盖，真实证据为 `248/251`，不能再使用旧的 `251/251` current 报告；
- exact 新完成 3 个 canonical；队列校验后剩余 69 个可执行点，另有 163 个点被参数合同门禁阻断；
- 最新 exact 综合门禁为 `16/27 passed`、10 required failed、1 optional failed。required 失败为：`model-source-map`、`overlay-e2e`、`multi-image`、`exact-incremental-data-chain`、`sampling-queue-evidence`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`。

因此本轮没有更新发布 manifest，也没有放宽 `MAE <= 0.03`、`SSIM >= 0.98` 或尺寸一致门限。

## 2. 按计划执行结果

### 2.1 P0：证据、队列和存储基线

1. 主队列 `--resume --dry-run` 验证已有 251 个 canonical 不会重复启动 Luminar。
2. 重新执行主队列 data-chain：251/251 state/canonical 链通过。
3. 重新执行逐文件证据校验后发现 3 个 Overlay `ax_before` 哈希漂移，真实结果为 248 ready、3 pending。
4. 根因不是采样重复，而是旧去重脚本对可变目录创建硬链接：
   - `queue-overlay-4c5931833a03/before.ax.txt`
   - `queue-overlay-bdbba755f19c/before.ax.txt`
   - `queue-overlay-66c244f43ca2/before.ax.txt`
   - `ui/2880x1800/layer-stack.ax.json`
   曾共享一个 inode；重观察 layer-stack 时，原地写入同步改写了 3 份历史 AX。
5. 已解除整个 1.28 输出根下 274 组共享 inode：802 个路径中 528 个路径被拆成独立 inode；复查后 shared inode 为 0。
6. 去重工具改为“只审计重复 + 可选解除硬链接”，不再创建新硬链接；AX snapshot 和原生 screenshot 改为临时文件完成后原子替换。
7. 最终重复文件审计为 1104 个相同内容路径、约 1.751 GB 可回收逻辑容量，主要来源：
   - canonical/candidate 与 staging：359 个；
   - candidate workspace 与对外发布别名：194 个；
   - native export 历史归档：18 个；
   - 同字节 canonical：15 个；
   - 其余诊断、审计和中间产物别名：518 个。

这些路径中一部分是证据链的不同角色，并非“重复采样”；未经角色化清理不能直接删除或重新硬链接。已损坏的 3 份原始 AX 字节在现存数据中无副本，保持 pending，未篡改 metadata hash，未重采。

### 2.2 P1/P2/P5/P6：UI 和交互

1. 对 7 个 legacy UI state 做了定向原生重观察，只补 UI 证据，不重采 effect/preset/sky/overlay/workflow。
2. 新增 fail-closed UI reference manifest，绑定：reference id、app version/build/bundle、viewport、fixture id/hash、screenshot/AX 路径及 hash、attempt 与时间。
3. manifest 当前 `7 verified / 0 invalid`。
4. 前端 Preview 新增：
   - 鼠标滚轮缩放，范围 25%–400%；
   - zoom > 1 时拖拽平移；
   - Fit-to-view；
   - 切换图片重置纯视图状态，不污染笔刷/编辑参数。
5. 前端测试由 11 增至 12，production build 通过。
6. 应用内 Browser discovery 仍返回 `[]`，无法对 current build 执行 7 个 UI 截图和 10 个交互合同；UI 像素 `0/7`、interaction execution `0/10` 保持 blocked。

这里不能使用独立 Playwright、旧 candidate 或前端单测替代真实 Browser 证据。

### 2.3 P3：模型推理合同

1. 修复 RetinaFace 输出适配，统一 decode/NMS 后的检测合同。
2. 新增/完成 HumanLandmarks 与 IrisLandmarks ONNX wrapper、registry、合同和真实推理验证。
3. 修复 OpenVINO IR 转 ONNX 后 Resize `sizes` 的输出尺寸规范化；Human/Iris 均可被 ONNX Runtime 加载并完成实际推理。
4. required logical model 当前 24 个：
   - selected required contract `22 model-specific`；
   - pending required `0`；
   - unresolved logical 仅 `crop_encoder_i8`、`crop_decoder_i8`。
5. crop decoder 虽可单独转换，但其输入依赖 crop encoder feature；crop encoder 使用非标准 bilinear ROI Pooling，当前 macOS 无兼容 OpenVINO ground truth。未注册半条链，也未用近似算子伪装 exact。
6. 转换失败和半链 ONNX 已移到 diagnostics/model-conversion-artifacts，避免进入可用模型目录。
7. 活动模型候选调用 `22/22` 通过，覆盖 19 个 capability、16 个实际模型，16 个活动合同全部验证。

### 2.4 P4：效果候选

1. 45 个候选全部重新生成，缺失候选从 2 个降为 0。
2. Magic Lights 状态配置修正后，两个缺失候选可生成。
3. 当前 smoke 仍为 36/45；未针对单张 reference 调阈值或过拟合。
4. 9 个失败及 MAE/SSIM：

| 能力/案例 | MAE | SSIM |
|---|---:|---:|
| `slim_people` | 0.053105 | 0.896961 |
| `fog` | 0.113488 | 0.903759 |
| `blue_hour` | 0.133379 | 0.914102 |
| `face_ai` | 0.080715 | 0.929874 |
| `sunrays`（sky fixture） | 0.070206 | 0.942800 |
| `depth_volume` | 0.068934 | 0.946598 |
| `sky_replace` | 0.064346 | 0.946903 |
| `sunrays`（独立 fixture） | 0.053714 | 0.956221 |
| `lut_mapping` | 0.035247 | 0.999137 |

LUT 和 slim_people 的 Luminar 输出接近 source，而当前候选过度变换；单样本不足以决定通用系数，保持 blocked。

### 2.5 P7：Overlay 与 Multi-image

#### Overlay

1. 新增 public API E2E：上传冻结输入、按 material id 加层、导出、与 38 个 Luminar canonical 比较。
2. 初始为 21/38；定位到 Luminar 免费 library overlay 默认按画布拉伸，而当前实现使用 cover。
3. library layer 改为 stretch；用户上传 layer 保持 cover/aspect 行为。
4. 最终 37/38 通过。
5. 唯一失败 `queue-overlay-e977d0dc815c`：请求资产是 Night Rain，但 Luminar reference 视觉和最近邻指标均更接近另一张粉橙 light-leak。该 reference 标为疑似采样选择错标，不让代码拟合错误证据；用户要求不重复采样，因此此项继续 blocked。

#### Multi-image

1. Focus stacking 从 soft blend 改为逐像素清晰度 argmax，避免重新引入模糊。
2. Focus 从失败提升为通过：MAE `0.009250`、SSIM `0.994731`、尺寸一致。
3. HDR 仍失败：MAE `0.103737`、SSIM `0.944482`。
4. Panorama 仍失败：MAE `0.081787`、SSIM `0.816140`；candidate `1078×1440`，reference `1070×1410`。

### 2.6 P8：exact 增量

1. 先执行 1 个未采样 smoke，随后短批执行；共新增 3 个 ready canonical：
   - `exact-color_enhancer-0b137e9133a2`，amount -1 -> native -100；
   - `exact-complex_bleach-0c583dd9c244`，amount 1 -> native 100；
   - `exact-skin_smooth-0f35f87f0c22`，amount 0 -> native 0。
2. `water_enhancer` 的 -1 锚点被 Luminar `0..100` slider 拒绝，证明旧 exact 队列包含无效语义。
3. 立即停止剩余长批处理，没有继续数小时制造确定性失败。
4. exact 队列生成器现在读取现有 smoke AX 日志中的 primary slider range；负值在原生最小值 >= 0 时排队前阻断。
5. 重建结果：
   - canonical semantic 45；
   - matrix existing 41，其中包含新增 3 个 exact canonical；
   - 可执行队列 69；
   - blocked 163：负值不可表示 23、native parameter contract 缺失 73、非 amount 参数未自动化 67；
   - duplicate 0、invalid 0。
6. 新 69 条队列当前全部 pending；按计划必须等 smoke/UI/interaction/model/workflow 前置门禁通过后再执行。

### 2.7 P9：采样耗时和长模型任务

1. 历史 24 个 export event 的中位总耗时约 74.138 秒；旧事件没有可分离的 dialog/file/publish 完整计时，不能伪造优化后实测对比。
2. 当前优化：
   - 导出菜单不再固定 sleep 1 秒，改为可见条件等待；
   - 文件稳定窗口从 1.0 秒降到 0.4 秒，但增加 PIL 完整图片 verify，截断文件不会被接收；
   - 每个 attempt 使用唯一 export stem，避免覆盖/替换对话框；
   - canonical 发布保留原子替换和完整 hash。
3. 纯固定等待理论最多减少约 1.6 秒；实际总耗时仍主要受 Luminar 原生 UI 与 export 支配。本轮遵守“不重复已采样”，没有为性能数字重跑旧 24 项。
4. 长模型任务已经验证：幂等 enqueue、租约、逐模型持久 checkpoint、完整 results 查询、终态再 merge project、取消/过期 worker 防覆盖、重载后恢复 latest job。不会因耗时长只返回部分结果。
5. 三模型性能 smoke：cold `4737.40 ms`、warm `4479.32 ms`，三项 ready，gate passed。

### 2.8 P10：回归和确定性

1. Python：`243 passed`、1 条第三方 Starlette/httpx deprecation warning，无失败。
2. Ruff：全项目通过。
3. Frontend：5 个 test file、12 个测试通过；production build 通过。
4. 候选双跑哈希保持一致：
   - 45-case candidate tree：`78eb339de4ab32d0ca27582564bafe416717b4d82a4f27ee5275881bc8f8d384`；
   - 3 workflow candidates：`3a8d05018aa9c3a8adb5214808317db36a0333a25f881d542606d61d3ea2e8ce`；
   - 38 overlay candidates：`639a9704e1282df019f5078cfc220857ff50e5e3eb387c96209181f0a799f7f4`。
5. exact quality gate 已加入 Overlay E2E required gate，防止 37/38 被遗漏。

## 3. 执行前后对比

| 指标 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Python 测试 | 231 passed | 243 passed | +12，全部通过 |
| 前端测试 | 11 passed | 12 passed | zoom/pan/Fit 行为已覆盖 |
| 模型注册/wrapper | 90/90 | 92/92 | Human/Iris 接入 |
| selected required contracts | 16 validated + 4 pending | 22 model-specific，0 pending | crop 条件链仍 unresolved 2 |
| smoke 候选完整性 | 43/45 | 45/45 | 无缺失候选 |
| smoke parity | 36/45 | 36/45 | 9 个真实算法差异未关闭 |
| UI reference manifest | 无严格 manifest | 7/7 verified | reference 可信度关闭 |
| UI current-build parity | 0/7 | 0/7 | Browser 不可用，保持阻塞 |
| interaction | 0/10 execution | 0/10 execution | 定义 10/10，真实执行仍缺 |
| Overlay E2E | 无独立最终报告 | 37/38 | 拉伸规则修复，1 条疑似错标 |
| Multi-image | 0/3 | 1/3 | Focus 通过；HDR/Panorama 阻塞 |
| 主队列表面证据 | 251/251 | 248/251 | 揭露硬链接污染，去除假绿 |
| shared inode | 274 组 | 0 组 | 历史路径已解除共享 |
| exact 新 canonical | 0 | 3 | 都有参数 readback、完整导出和 hash |
| exact 可执行待办 | 95 | 69 | 23 个无效负值提前阻断，3 ready 排除 |
| exact 明确 blocked | 未分类 | 163 | 参数合同缺失/未自动化/不可表示 |
| Overlay required gate | 未接入 | 已接入 | exact gate 总数 26 -> 27 |
| 候选确定性 | 未形成三链哈希 | 三链双跑一致 | 当前环境可复现 |

## 4. 遗漏确认

### 4.1 外部环境阻塞

- 应用内 Browser 无可发现会话，导致 current-build 7 个 UI 状态和 10 个交互合同无法执行。
- crop encoder 的非标准 bilinear ROI Pooling 缺兼容 OpenVINO runtime/ground truth；不能用近似 ONNX 算子宣称 exact。

### 4.2 证据阻塞

- 3 个 Overlay `ax_before` 被旧硬链接机制污染且无原始字节副本；不改 hash、不重采时永久 pending。
- `queue-overlay-e977d0dc815c` 疑似选择错标；不重采时不能证明 38/38。
- UI 原生 reference 已可信，但 candidate/current Browser 证据为空。
- interaction 原生 observation 与 candidate execution 均为空。

### 4.3 算法阻塞

- 9 个 smoke 效果差异；集中在人像几何/曝光、深度场、天空遮挡、太阳光线、蓝调时刻、雾和 LUT。
- HDR 缺曝光对齐、去鬼影和 Luminar 风格 tone mapping。
- Panorama 缺投影模型、特征匹配、接缝、自动裁切和输出几何合同。

### 4.4 参数覆盖阻塞

- exact matrix 中 73 个语义没有 native parameter contract，67 个非 amount 参数未自动化。
- 69 个合法可执行点尚未放行；不能在前置门禁失败时批量消耗原生采样时间。

## 5. 下一步建议（严格优先级）

### P0：恢复真实 Browser 证据通道

1. 在应用设置中恢复 Computer use/Browser 会话发现。
2. 固定 2880×1800、DPR、locale、timezone、字体、主题、motion、build hash。
3. 先执行 7 个 UI state，再执行 10 个 interaction contract。
4. 只有 execution record 和截图 hash 完整后才改 CSS/交互；禁止盲调。

### P1：修复证据而不是拟合错误 reference

1. 将 3 个 AX hardlink 污染记录和 1 个疑似 Overlay 错标记录纳入 invalid-reference registry。
2. 在“不重复采样”约束不变时，它们只能保持 blocked。
3. 如果未来允许最小定向重观察，只重观察这 4 个 evidence，不触发其它 247 个主队列记录。

### P2：按共享语义关闭 9 个效果

1. face/body：统一人脸 ROI、多人策略、人体 warp 网格、背景保护和坐标合同。
2. depth/fog：冻结 near/far 方向、归一化、边缘引导和局部强度曲线。
3. sky/sunrays/blue-hour：统一天空/前景/反射遮挡、地平线、太阳坐标与射线几何。
4. LUT：先验证 native LUT choice/readback 和颜色管理，再调 3D LUT；不能只修 MAE 0.035 的单图。
5. 每个共享根因使用已有 calibration/holdout；已有 canonical 不重采。

### P3：关闭 crop 条件链

1. 在具有兼容 OpenVINO 的 Windows/Linux 机器运行 crop encoder/decoder ground-truth probe。
2. 找到与原非标准 ROI Pooling 完全一致的 ONNX 表达后再注册两模型。
3. encoder、decoder、feature shape、coordinate convention 和端到端 crop 输出必须同批通过；不注册半链。

### P4：完成 Multi-image

1. HDR：曝光估计、对齐、去鬼影、radiance merge、局部 tone curve。
2. Panorama：特征匹配、RANSAC、cylindrical/spherical projection、seam/blend、自动 crop 和精确尺寸。
3. 保持 Focus 当前 hard argmax 基线，增加边界/噪声 holdout，防回退。

### P5：参数合同后再放行 exact

1. 为 73 个缺合同项建立 native control id/range/value-space/readback。
2. 为 67 个非 amount 参数实现最小语义操作；不把它们映射到 amount。
3. 重建 incremental queue；只执行合法且未 ready 的 semantic key。
4. 每个 capability 小批放行、立即生成候选和比较；失败先修共享根因，不继续同域剩余采样。

### P6：最终发布门禁

当且仅当以下同时满足后连续双跑 exact：

- smoke 45/45；
- Overlay 38/38 且 reference 有效；
- Workflow 3/3；
- UI 7/7 current-build；
- interaction 10/10 双边执行；
- required model exact behavior gate passed；
- sampling evidence 251/251 或 invalid reference 被重新建立可信证据；
- exact 合法范围全部完成，blocked 参数语义均已关闭。

两次 required gate 失败集合均为空后，才更新 manifest 和“冻结范围内等价”声明。

## 6. 关键机器证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-evidence-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-storage-audit-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-storage-audit-after-detach.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/candidate-model-invocation-audit-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/overlay-e2e-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/performance-report-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json`
- `test_data/outputs/luminar-1.28.0-23071/ui/reference-manifest.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution.json`
