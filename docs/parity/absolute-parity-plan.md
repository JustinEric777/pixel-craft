# Luminar Neo 1.28.0 严格对齐执行计划

> 本文描述当前真实基线、已完成的数据链改造，以及剩余效果、UI、交互校准的严格验收顺序。活动参考固定为 Luminar Neo 1.28.0 build 23071、`zh-Hans`。已经拥有完整 canonical 证据的案例不得重复采样。

## 目录

- [1. 当前结论](#1-当前结论)
- [2. 数据链边界](#2-数据链边界)
- [3. 已完成阶段](#3-已完成阶段)
- [4. 剩余执行阶段](#4-剩余执行阶段)
- [5. 严格完成定义](#5-严格完成定义)
- [6. 验证命令](#6-验证命令)

## 1. 当前结论

当前采样队列是 smoke 基线，不是参数全矩阵。队列包含 251 条记录：45 个效果、123 个预置、35 个天空、38 个叠加、7 个 UI 状态和 3 个多图工作流。

| 项目 | 当前结果 | 结论 |
|---|---:|---|
| 队列 canonical 证据 | 251/251 | 数据链通过，不重复采样 |
| 效果参考 | 45/45 | 参考证据完整 |
| 当前候选效果像素对比 | 15/45 | 30 个效果仍需校准 |
| UI 像素对比 | 0/7 | UI 仍需系统校准 |
| 模型静态结构 | 0 阻塞 | 模块结构通过 |
| 模型专用语义契约 | 10/90 | 80 个待关闭 |
| exact 参数矩阵 | 366 个效果锚点、10 个交互锚点 | 已生成，尚未成为参考队列 |

因此，当前可以声明“采样数据链完整且可恢复”，不能声明“效果、UI、交互已经完全等价”。任何 exact 模式都必须继续 fail closed。

## 2. 数据链边界

```text
sampling-queue.json（不可变计划 + fingerprint）
  │
  ├── state/<case>.json（canonical 投影）
  │     ├── canonical：最后一次已发布成功证据
  │     └── last_attempt：最近一次尝试，可失败但不能覆盖 canonical
  ├── attempts/<case>/<attempt>.json（不可变终态）
  ├── attempts/<case>/<attempt>.jsonl（逐事件记录）
  ├── luminar_outputs/<case>/native-export.<ext>（原生导出字节）
  ├── luminar_outputs/<case>/export.png（归一化比较图）
  ├── metadata/<case>.json（输入、应用版本、哈希和来源）
  └── sampling-runs/<run>.json（不可变运行/对账报告）
```

运行时不读取 v1 历史状态，也不提供历史兼容分支。旧数据只通过一次性迁移脚本转换，原文件归档在 `captures/state-v1-archive/`。

推理任务独立于模型 wrapper：

```text
POST analysis-jobs
  → data/jobs/inference/<job>.json
  → worker 逐模型执行
  → 每个模型完成后保存 checkpoint 和完整 npy/npz 制品
  → 全部模型结束后一次性合并项目 metadata
```

`ai/model` 仍只负责加载、预处理、前向、后处理和释放；租约、任务恢复和项目合并位于 `services/jobs` 与 `storage/jobs`。

## 3. 已完成阶段

### 3.1 M0：基线审计

- `scripts/audit_sampling_storage.py` 生成容量、物理重复、状态 schema 和队列对齐报告。
- 执行前/后报告分别为 `diagnostics/pre-migration-audit.json` 和 `diagnostics/post-migration-audit.json`。

### 3.2 M1：canonical/attempt 状态真源

- `CaptureJournal` 使用 schema v2。
- 成功案例再次执行失败时，失败只进入 `last_attempt`，不会覆盖 canonical。
- 251 个旧状态已迁移；旧状态保留在 `state-v1-archive`。
- `scripts/reconcile_sampling_queue_state.py` 为当前 queue fingerprint 生成不可变对账报告。

### 3.3 M2：导出、暂存和重复文件

- 导出文件名包含 case 与 attempt ID，不再触发覆盖确认。
- 导出监听只轮询本次精确目标文件，不再扫描共享目录。
- 保存面板已经位于正确目录时跳过“前往文件夹”。
- `finalize_case` 不再重复等待；原生导出与归一化 PNG 分开保存。
- 稳定帧使用环形窗口；成功后删除临时图，失败保留最近三组。
- 历史稳定帧已清理；capture 与全输出树共 763 个精确重复副本已转换为硬链接，路径与字节不变。

### 3.4 M3：队列指纹和历史对齐

- queue v2 携带 `profile`、`queue_revision` 和 `queue_fingerprint`。
- `semantic_key` 不依赖扫描顺序和本机文件路径。
- `scripts/compare_sampling_queues.py` 输出语义、record ID 和逻辑库存对齐。
- 1.25 与 1.28 的 record ID 共有 199 条；逻辑库存共有 246 项，1.28 删除 12 项、没有新增逻辑项。旧版本输出不参与 1.28 exact 证据。

### 3.5 M4：可恢复完整推理任务

- `POST /api/v1/projects/{project_id}/analysis-jobs` 返回 202；支持查询结果和取消。
- `scripts/run_inference_worker.py` 使用租约领取任务，进程中断后从未完成模型继续。
- 每个模型完成立即 checkpoint；原始 tensor 保存为 `.npy` 或 `.npz`，记录 SHA-256 和大小。
- 取消、心跳和终态发布采用同一文件锁与 lease owner 条件更新，stale worker 不能复活已取消任务或覆盖接管状态。
- 相同 project、source hash、models、idempotency key 不会创建重复任务。
- 模型加载器先驱逐 LRU 再加载，超预算或无可驱逐模型时明确失败。

### 3.6 M5-M8：矩阵与门禁基础设施

- `scripts/analyze_luminar_repeatability.py` 可测量 Luminar 自身波动。
- `scripts/build_exact_sampling_matrix.py` 已生成 366 个参数锚点和 10 个交互锚点。
- `scripts/validate_sampling_data_chain.py` 校验 queue、canonical attempt、UI/原生导出、运行报告和推理制品。
- exact 质量门禁已增加 `sampling-data-chain`。

## 4. 剩余执行阶段

### 4.1 P0：关闭当前 30 个效果差异

不重新采集已有 45 个参考，按以下顺序校准：

1. 修复结构错误：`crop_ai` 当前输出尺寸与 Luminar 不同。
2. 校准确定性全局效果：颜色、色调、LUT、渐隐、颗粒、晕影、细节、对比和高调。
3. 校准深度/天空效果：雾、景深、天空替换、太阳光线、风景增强。
4. 校准人像与模型效果：人脸、瘦身、背景虚化、AI Enhance。

每次只修改一个能力或一个共享模型，运行该能力单案例和共享回归集。不得通过放宽 `configs/parity.yaml` 关闭差异。

### 4.2 P1：关闭 7 个 UI 系统差异

当前 UI MAE 约为 0.10–0.16、变化像素比例超过 95%，属于布局/主题级差异。先固定视口、缩放、字体和窗口装饰，再对齐工作区骨架、侧栏、顶栏、画布、工具行、图标、文字、滑杆和动态状态。

### 4.3 P2：关闭交互状态机

以 10 个交互锚点验证导入选择、预置预览/应用、滑杆拖动、工具折叠、图层增删排序、撤销重做、前后对比、缩放平移、导出和多图工作流。事件顺序、加载/禁用状态和最终输出必须同时一致。

### 4.4 P3：关闭 80 个模型专用契约

只处理本地免费能力可达模型；不可达模型保留可达图证据。每个模型补齐颜色空间、尺寸变换、归一化、输出类别、阈值、插值、后处理和释放语义。

### 4.5 P4：增量 exact 采样

当前 251 条 canonical 全部跳过。把 366 锚点与当前队列按 semantic key 做差，只采集新增参数/交互记录。重复性测量使用独立 `repeatability` profile，不污染 canonical smoke/exact 队列。

## 5. 严格完成定义

- 数据链 0 issue，所有报告 fingerprint 与活动队列一致。
- 已有 canonical 不重复采样；新增案例只有 semantic diff。
- 45 个 smoke 效果和增量 exact 参数锚点全部通过尺寸、色彩和像素门禁。
- 7 个 UI 状态与 10 个交互锚点全部通过行为和视觉门禁。
- 123 个预置、35 个天空、38 个叠加和 3 个多图工作流通过。
- 所有可达模型为 model-specific validated，完整任务制品可恢复、可校验。
- exact required 门禁全绿，0 pending、0 invalid、0 failed、0 stale。

## 6. 验证命令

```bash
# 必须显示 ready_filtered=251、record_count=0
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run

.venv/bin/python scripts/reconcile_sampling_queue_state.py
.venv/bin/python scripts/validate_sampling_data_chain.py
.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/validate_reference_captures.py
.venv/bin/python scripts/run_parity_suite.py
.venv/bin/python scripts/validate_ui_references.py
.venv/bin/python scripts/check_model_contracts.py

.venv/bin/ruff check .
.venv/bin/pytest -q
cd frontend && npm test -- --run && npm run build
```
