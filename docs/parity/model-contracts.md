# 模型 Contract 恢复与验证

执行：

```bash
.venv/bin/python scripts/model_probe.py
.venv/bin/python scripts/check_model_contracts.py
```

Contract 输出在 `models/contracts/`。活动版本的检查结果写入
`test_data/outputs/luminar-1.28.0-23071/diagnostics/`。

ONNX/ORT 模型会读取 ONNX Runtime 的真实输入输出签名，报告中的
`runtime-signature-only` 表示 I/O 已确认、任务语义和精确后处理仍待恢复。当前 90 个注册
模型均有格式匹配的 contract，其中 10 个完成模型专用验证、80 个仍为 pending。新增的
IR 转 ONNX 模型只有在 checker、ORT forward、wrapper 后处理和 contract 均通过后才进入
注册表；这仍不等同于已经通过 Luminar 黑盒输出校准。
OpenVINO XML/BIN 不会因为文件存在而自动标记为可用；在兼容主机可运行
`.venv/bin/python scripts/probe_openvino_ir.py` 逐个探测，再补齐颜色、量化、ROI、输出语义
和后处理字段。

模型来源、wrapper 和功能消费者映射可通过以下命令重建：

```bash
.venv/bin/python scripts/build_model_source_map.py
```

当前 95 个 Portable 模型文件均为同名同哈希，90 个注册模型均有独立 wrapper；60 个模型能
追踪到 pipeline 或能力图消费者，30 个尚未进入任何功能图。后者不能计为“功能已接入”。

候选输出的真实调用证据通过以下命令重建：

```bash
.venv/bin/python scripts/audit_candidate_model_invocations.py
```

该审计不读取“模型已注册”作为成功条件，而是逐案例检查 execution trace、`invoked=true`、
required model、结果内容哈希和实际导出。当前 130 个活动 model-backed 候选案例全部通过真实
调用校验，覆盖 20 个能力和 17 个实际模型文件。90 个注册项按证据分为：

- 16 个 `active-invoked`：当前候选输出确实执行过。
- 11 个 `active-alternate`：上述逻辑模型的 OpenVINO/ONNX 备用变体，本轮未选中。
- 33 个 `configured-not-covered`：已有执行图或代码消费者，但当前候选案例没有覆盖。
- 30 个 `inventory-unmapped`：只有模型库存和 wrapper，尚无功能消费者证据。

17 个实际调用模型中，目前 6 个完成模型专用 normalization/postprocess 验证，11 个仍为
`model-specific-pending`。因此“真实调用门禁”通过，但“活动模型语义契约门禁”和 Luminar
最终效果等价仍阻塞；两者不可互相替代。
