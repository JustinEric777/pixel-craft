# Luminar 采样数据链执行报告

> 本报告记录 2026-08-21 对 Luminar Neo 1.28.0 采样、导出和长耗时推理链的实际改造结果、数据迁移、验证结论与剩余阻塞项。

## 1. 执行前后对比

| 指标 | 执行前 | 执行后 |
|---|---:|---:|
| capture 文件逻辑字节 | 3,821,415,750 | 2,642,899,028 |
| 当前物理唯一 inode 字节 | 未建立去重基线 | 2,065,314,730 |
| 稳定轮询临时图 | 616 个待清理 | 0 个待清理 |
| 物理重复副本 | 1,028 个额外副本 | 0 个 |
| 状态 schema | 251 个 legacy | 251 个 v2 |
| 顶层状态 | 241 ready / 10 failed | 251 ready |
| canonical ready | 0 | 251 |
| 队列待执行 | 10 个表面 failed | 0 |
| 原生导出证据 | 分散在共享根目录 | 244/244 归档到 case 目录 |
| 原生导出来源 | 未标注 | 235 原始 JPEG，9 normalized fallback |
| 数据链问题 | 多真源冲突 | 0 issue |

全 `test_data/outputs` 的最终物理占用从 2,464,236 KiB 降到 2,225,028 KiB；逻辑路径和文件字节不变。

执行前/后精确报告位于 `test_data/outputs/luminar-1.28.0-23071/diagnostics/pre-migration-audit.json` 和 `post-migration-audit.json`。

## 2. 为什么没有重复采样

迁移从旧 history 中恢复曾经成功且制品仍存在的 canonical 记录。10 个最后状态为 failed 的案例都保留了先前 ready 证据，辅助功能权限失败只记录为最后一次尝试。

`.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run` 当前结果为 `ready_filtered=251`、`record_count=0`。只有 queue semantic key 新增或 canonical 制品损坏时才需要采样。

## 3. 数据清理

- 删除 616 个成功案例的稳定轮询图，回收 1,309,413,215 字节。
- capture 内将 461 个精确重复文件替换为硬链接，减少 577,584,298 字节物理占用。
- 全输出树遗漏审计再处理 302 个精确重复副本，减少 244,396,068 字节；合计 763 个、821,980,366 字节。
- 未删除 preview、export、native export、metadata、UI/AX、state、attempt 或全局日志。
- v1 状态保存在 `captures/state-v1-archive/`，运行时不读取。

## 4. 长耗时推理

创建任务：

```http
POST /api/v1/projects/{project_id}/analysis-jobs
Content-Type: application/json

{"models":["SemanticSearchImage"],"idempotency_key":"project-analysis-v1"}
```

启动 worker：

```bash
.venv/bin/python scripts/run_inference_worker.py
```

查询接口为 `GET /api/v1/analysis-jobs/{job_id}` 和 `GET /api/v1/analysis-jobs/{job_id}/result`，取消使用 `DELETE /api/v1/analysis-jobs/{job_id}`。worker 每完成一个模型就更新 checkpoint 和 artifact cache；单 tensor 保存 `.npy`，多 tensor 保存 `.npz`。取消、心跳和终态发布使用同一文件锁与 lease owner 条件检查，旧 worker 不能覆盖取消或新 worker 的状态。任务终态前只把合并结果一次写入项目；部分模型失败时明确写入 `completed-with-errors`。

## 5. 当前门禁

| 门禁 | 结果 |
|---|---|
| sampling data chain | passed：251/251，0 issue |
| sampling queue evidence | passed：251/251 |
| reference captures | passed：45/45 |
| effect output parity | blocked：25/45，20 failed |
| UI parity | blocked：0/7 |
| model module static validation | passed：0 findings |
| model-specific contracts | blocked：10/90 validated |

数据链完成不等于产品完全对齐。剩余问题已经收敛为效果算法、UI 布局、交互状态和模型语义校准，不能用阈值放宽或旧报告规避。最新执行细节和下一阶段门禁见 `optimization-execution-report.md`。

## 6. 回滚与排障

- 状态异常：从 `captures/state-v1-archive/<case>.json` 人工恢复后重新执行迁移；运行时不自动回退。
- 原生导出哈希失败：检查 `metadata/<case>.json` 的 `native_export`，不得用 candidate 替代。
- worker 中断：等待一小时租约过期后重新启动；已完成模型不会重复执行，旧 worker 不能覆盖接管后的状态。
- capture 中断：下次运行会先把未完成 attempt 封存为 failed，再在同一轮启动新 attempt；canonical ready 仍直接跳过。
- queue fingerprint 变化：先做历史/当前语义 diff，只运行 added 项，再重新对账。
- exact 门禁阻塞：读取真实失败项，不修改阈值绕过。
