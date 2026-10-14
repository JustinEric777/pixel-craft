# 性能基准

使用明确的本地输入运行冷启动和 warm-cache 分析：

```bash
.venv/bin/python scripts/run_performance_suite.py \
  --image data/audit-artifacts/audit-source.png
```

`test_data/夏日户外拍照` 中的验证图片可读后，可以对清单中的每张样本循环运行同一命令，或先使用
`scripts/run_validation_suite.py` 生成批量分析报告。当前报告记录冷/热耗时、模型
缓存状态和每个分析项的状态，但不把当前机器耗时宣称为 Luminar Neo 的性能等价；
性能门槛必须在目标 Windows/Linux 运行环境和相同硬件上建立。
