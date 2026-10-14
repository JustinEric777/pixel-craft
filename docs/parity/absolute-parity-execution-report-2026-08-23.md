# Luminar Neo 1.28 绝对对齐计划执行报告（2026-08-23）

## 1. 结论

本轮已经完成当前环境内可安全执行的代码、数据链、队列、模型、采样性能、长任务、内容链和回归工作，但项目仍不能声明与本机 Luminar Neo 1.28 在效果、UI、交互上完全对齐。

最终机器结论是：

- smoke 效果：`36/45`，仍有 9 个失败案例。
- UI：`0/7`，应用内 Browser 当前无可发现实例，且已有候选不是 current build 证据。
- interaction：定义 `10/10`，原生 observation 与候选 execution 均为 `0/10`。
- exact：`1/96` 已通过，增量队列剩余 `95`；未启动重复或越级采样。
- exact quality gate：两次连续运行均为 `17/26 passed`、`8 required failed`、`1 optional failed`。
- 代码回归：Python `231/231`、前端 `11/11`、Ruff、前端 build、模型模块验证全部通过。

因此本轮没有更新发布 manifest，也没有把 blocked 项改写成 passed。

## 2. 已执行的实现

### 2.1 采样恢复与重复执行

1. 对主采样队列执行 `--resume --dry-run`，结果为 `ready_filtered=251`、`record_count=0`，确认已有 canonical 不会重复启动 Luminar。
2. 修复 exact 增量队列只扫描 smoke state、没有识别已 ready exact capture 的问题。
3. 修复后重建 exact 队列：从错误的 `96` 条恢复为 `95` 条；已通过的 `exact-details-0054c53f89cf` 不再回队。
4. exact 队列 dry-run 为 `record_count=95`、`ready_filtered=0`、`failed_filtered=0`，未实际启动新原生采样。
5. capture 审计共有 269 个 state：267 ready、2 deterministic failed；没有 staging/attempt 目录缺失对应 state。
6. 两个 failed 是 LUT 与 Magic Lights 校准语义的原生 unchanged-source 结果，保持 terminal failed，不自动重试。

### 2.2 模型产品范围与活动合同

1. 模型 source map 不再把 90 个 inventory wrapper 全部当作当前产品 required。
2. 当前分类：52 个 `inventory-unreachable`、26 个 `required-direct`、12 个 `required-transitive`。
3. source file `95/95 exact`、artifact `90/90 exact`、wrapper `90/90 present`。
4. source map 现在使用本机真实 runtime policy；macOS 当前 `openvino_enabled=false`，原因是 `macos-requires-explicit-compatible-runtime`，不再强制按 OpenVINO 可用选择变体。
5. 活动候选调用 `22/22` 通过，覆盖 19 个 capability、16 个实际模型，活动合同 `16/16` 通过。
6. 仍有 4 个当前可选择的 transitive ONNX 模型合同未完成：
   - `eyes_detector_i8_onnx`
   - `face_detector_retinaface`
   - `face_landmarks_i8_onnx`
   - `segmentator_i8_onnx`
7. 另有 4 个 transitive logical model 在当前 macOS runtime 不可解析：
   - `HumanLandmarks`
   - `IrisLandmarks`
   - `crop_decoder_i8`
   - `crop_encoder_i8`

### 2.3 活动模型后处理修复

`salient_object_improve_exp19_it150k` 的 wrapper 已返回规范化二维 mask，但 analysis pipeline 再次按四维 logits 索引，导致真实推理报 `IndexError`。本轮修复 pipeline 对 `[H,W]` 规范化 mask 与 `[N,C,H,W]` class output 的显式分支，并增加单元测试。

修复前性能 smoke：

- cold `4208.61 ms`
- warm `3967.23 ms`
- `salient_mask=failed`
- gate blocked

修复后：

- cold `4103.67 ms`
- warm `4027.87 ms`
- 三个模型输出均 ready
- gate passed

warm 时间没有显著下降，说明 session cache 之外的模型计算仍是主要成本；本轮优先保证输出合同正确。

### 2.4 原生采样阶段计时与文件发布

新增的机器字段包括：

- state transition 的 `stage_duration_ms`、`attempt_duration_ms`
- `export_dialog_seconds`
- `file_stable_seconds`
- canonical publish 的 preview convert、native copy、export convert、evidence copy、metadata write 分段计时

历史 251 条主采样日志的阶段统计：

| 阶段 | 样本数 | p50 | p95 | 最大值 |
|---|---:|---:|---:|---:|
| prepare → baseline | 256 | 9.852s | 54.685s | 133.159s |
| baseline → effect applied | 255 | 0.913s | 3.965s | 4.167s |
| effect applied → preview stable | 255 | 7.744s | 10.155s | 19.294s |
| preview stable → native export | 259 | 47.488s | 106.096s | 111.633s |
| native export → canonical ready | 260 | 1.623s | 1.668s | 1.729s |
| total | 267 | 75.123s | 123.794s | 160.186s |

结论：用户观察到的“重命名/替换等待”主要实际发生在 Luminar 原生 export，不在本地 replace。canonical publish 只占约 1.6 秒。

本轮仍为已验证 RGB PNG 增加直接复制快路径，避免 preview 等文件被无意义地解码和重新编码；非 PNG、带 alpha 或需要规范化的输入继续转换，native export 继续复制以防原导出路径后续覆盖硬链接证据。

### 2.5 LUT menu choice readback

采样器现会记录并验证：

- menu 点击前 native value/title
- 唯一 choice 定位
- choice 点击后 value/title
- slider 提交值
- 控件持久 readback

readback 不一致会抛出 terminal `NonRetryableCaptureError`。已有 failed semantic 没有重采；只有未来真实改变控制策略或输入/资产语义时才能生成新 semantic key。

### 2.6 长模型任务与断开重连

后端原有 job 已具备：source hash、request key、queued/running/succeeded/completed/failed/cancelled、租约、逐模型 checkpoint、artifact hash、终态 project merge 和取消/过期 worker 防覆盖。

本轮补齐：

- repository 按 project 查询 latest job
- `GET /api/v1/projects/{project_id}/analysis-jobs/latest`
- 前端 mount/project 恢复时重新发现 latest job
- running job 自动恢复轮询
- terminal job 拉取完整 result 后再刷新 project
- 页面卸载只停止 timer，不取消服务器任务
- generation token 继续阻止旧项目晚响应覆盖当前项目

新增断开重连测试后，前端 job 测试由 4 增至 5。

### 2.7 UI 运行时样式

删除了 `frontend/src/styles.css` 中第 391 行以后整段运行时生效的 Luminar Neo 1.25.1 workspace shell 覆盖；样式文件由 932 行收敛为 389 行，1.28 token 与 geometry 成为唯一当前样式源。

前端单测和生产 build 均通过。但应用内 Browser discovery 返回空列表，无法生成 current-build 的 7 张候选截图，所以不能评价视觉指标是否改善，也不能把 stale candidate 当作本轮证据。

### 2.8 内容链

- Preset：123 项、22 类全部 ready，全部产生有效变化。
- Sky E2E：46 项全部 ready，0 failed。
- Workflow：原脚本只验证本地 workflow 能运行，并把 `reference_parity` 固定写成 pending，导致 quality gate 假绿。本轮接入 3 个已有 Luminar canonical、校验 frame hash、保存候选并执行冻结视觉阈值。

真实 workflow 结果：

| Workflow | 结果 | MAE | SSIM | 尺寸 |
|---|---|---:|---:|---|
| HDR merge | failed | 0.103737 | 0.944482 | 一致 |
| Focus stacking | failed | 0.030116 | 0.979591 | 一致 |
| Panorama stitching | failed | 0.081787 | 0.816140 | reference 1070×1410，candidate 1078×1440 |

这使 exact required gate 新增 `multi-image` 阻塞。它是门禁纠偏，不是效果回退。

## 3. 执行前后对比

| 指标 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Python 测试 | 224 passed | 231 passed | +7，全部通过 |
| 前端测试 | 10 passed | 11 passed | +1，全部通过 |
| Ruff / build / model validator | passed | passed | 无回退 |
| smoke 效果 | 36/45 | 36/45 | 9 项仍阻塞，未对单样本过拟合 |
| UI | 0/7 | 0/7 | 旧 CSS 已删除，但无 current-build Browser evidence |
| interaction | 0/10 | 0/10 | 定义完整，双边执行证据为空 |
| exact | 1 passed + 95 pending | 1 passed + 95 pending | 未越级采样 |
| exact queue rebuild | 错误回队 96 | 正确剩余 95 | 已过滤 ready exact |
| 主队列恢复 | 251 ready | 251 ready，0 待跑 | 无重复采样 |
| 活动模型合同 | 16/16 | 16/16 | 保持通过 |
| source map blocker | 8 个 selected pending，错误假定 OV 可用 | 4 个 selected pending + 4 个 runtime unavailable | 更精确、与本机 runtime 一致 |
| 性能 smoke | blocked | passed | 修复 salient mask 合同 |
| workflow gate | passed（只验本地可运行） | failed 3/3（真实 Luminar parity） | 去除假绿 |
| exact quality gate | 18 pass / 7 required fail | 17 pass / 8 required fail | 新增真实 multi-image 阻塞 |
| exact 连续性 | 未执行最终双跑 | 两次 17/26，阻塞集合相同 | 结论稳定但未达发布条件 |

## 4. 当前遗漏与阻塞

### 4.1 效果

剩余 9 个失败案例：`face_ai`、`slim_people`、`depth_volume`、`lut_mapping`、`blue_hour`、`fog`、`sky_replace`、2 个 `sunrays`。

其中人像、深度、天空多数只有单个 smoke reference，没有独立 holdout；继续按单图调系数会产生不可证明的过拟合。`blue_hour` 的两条 calibration 能被简单模型解释，但原 general hard holdout 仍不能通过，证明存在内容/空间相关响应。LUT 旧 reference 的原生 apply/readback 可信度不足，必须保持 blocked。

### 4.2 模型

4 个 transitive ONNX contract 未完成，4 个 transitive logical model 在当前 macOS runtime 不可用。未完成 RetinaFace decode/NMS、landmark/eye/scene label 语义前，不能声明人像和前景保护链绝对对齐。

### 4.3 UI 与交互

- 应用内 Browser 可用实例为 `[]`。
- 7 个 current-build UI execution record 缺失。
- 原生 7 张 UI reference 是 legacy-import state，state 中有截图/AX/viewport，但没有独立 metadata 文件证明 app build/fixture/font/theme 完整环境。
- 10 个 interaction 的原生 observation 和候选 execution 均缺失。
- 现有 7 张 candidate 属于 stale build；不能用于本轮验收。

### 4.4 Exact 与内容

- exact 增量 95 项因 smoke/UI/interaction/model 前置门禁未通过而没有启动。
- workflow 3 项真实输出未过。
- overlay 最终 Luminar comparator 尚未形成与 preset/sky/workflow 同等级的独立机器报告。

### 4.5 数据卫生

- 没有 staging-without-state 或 attempts-without-state。
- 7 个 UI ready state 没有普通效果 metadata；它们是 UI reference evidence，需要独立 UI manifest，而不能假装成效果 metadata。
- 两个 deterministic failed calibration state 应保留审计，不删除、不重试。

## 5. 下一步建议

下一轮不应启动 95 条 exact 批量采样。建议严格按以下顺序：

1. 恢复应用内 Browser 会话，冻结 build hash、2880×1800、DPR、locale、timezone、font、fixture 与动效等待；先生成 7 个 current-build execution record。
2. 用已有原生 UI reference 建立独立 reference manifest；无法证明 1.28 build/fixture 的状态标 invalid，只补缺失语义，不重复已可信采样。
3. 实现 10 条原生 interaction observation 驱动和候选 Browser execution；先 catalog/preset，再 slider/undo/compare，再 layer/zoom，最后 export/multi-image。
4. 完成 4 个 transitive ONNX contract，并明确 4 个 macOS 不可用 logical model 的产品决策：提供 ONNX 变体或从当前执行图移除，不保留“配置声明可用但运行时不可达”。
5. 按共享合同关闭效果域：face/body ROI → depth field → sky/horizon/foreground → sun position/ray geometry → blue-hour semantic mask → LUT readback。
6. 每个单样本域先增加独立 holdout；已有 reference 不重复采样，只为缺少的多人/空目标/触边/near-far/太阳位置等新语义补证据。
7. 修复 3 个 workflow：HDR tone/ghost、focus measure/融合、panorama crop/投影；全部绑定现有 frame hash 和 canonical，不重新采原生输出。
8. 建立 overlay 38 项的真实最终合成 parity 报告。
9. 只有 smoke 45/45、UI 7/7、interaction 10/10、model source map 通过后，才按 capability anchor 启动 exact 95；每批通过后重建队列。
10. 最终再次执行两次 exact；只有两次 required gate 全过才更新 manifest。

## 6. 关键机器证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-execution-before.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-1.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-exact-final-2.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/model-source-map.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/performance-report-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/preset-validation-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/validation-sky-e2e-report.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-workflow-smoke-current.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-execution-evidence.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity.json`
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution.json`
