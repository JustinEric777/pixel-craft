# 本地验证集

当前原始测试图片位于：

```text
/Users/iknow/Works/python/zpixel_edit/test_data/夏日户外拍照
```

冻结后的活动验证输入位于 `test_data/parity/inputs`，由 46 张夏日户外 JPEG 与
`exact-fixtures` 中 2 张只用于特定效果的固定输入组成。当前组合数据集指纹为：

```text
c016c6377a02098080e8254f81c725646c404a6724ad7c29a87139aa7f7ffd31
```

指纹由相对路径、文件大小和 SHA-256 共同计算。源目录发生增删改后，清单、固定输入、案例或
采样队列中的任一指纹不一致都会使质量门禁失败。

生成或刷新清单：

```bash
.venv/bin/python scripts/build_validation_manifest.py \
  --source-dir /Users/iknow/Works/python/zpixel_edit/test_data/parity/inputs
```

只校验源数据和固定快照，不写文件：

```bash
.venv/bin/python scripts/build_validation_manifest.py \
  --source-dir test_data/parity/inputs \
  --check
.venv/bin/python scripts/validate_dataset_freshness.py
```

`test_data/parity/inputs` 是严格验证使用的冻结组合输入，只包含输入素材，不包含 Luminar 或
zpixel 输出。若需要从原始素材重新生成 `summer-outdoor` 快照，应先单独刷新该子目录，再把
特定效果所需的 `exact-fixtures` 一并纳入组合清单；不要直接用原始素材覆盖组合根目录。

`configs/parity.yaml` 使用显式语义角色绑定验证图片，例如 `sky`、`portrait`、`denoise` 和
`sharpness`。重绑脚本不会再按文件顺序平均分配图片；角色缺失、重复或文件不存在时直接失败：

```bash
.venv/bin/python scripts/rebind_reference_inputs.py
.venv/bin/python scripts/build_parity_cases.py
.venv/bin/python scripts/build_luminar_sampling_queue.py
```

源数据清理后，先预览再删除活动参考版本中不再对应当前案例的候选、采样和诊断输出：

```bash
.venv/bin/python scripts/prune_stale_parity_outputs.py
.venv/bin/python scripts/prune_stale_parity_outputs.py --apply
```

该命令只处理活动参考版本的可重建目录，不删除固定输入和仍在清单中的证据。

当前环境的验证原则：

1. ONNX 模型使用 ONNX Runtime，并记录模型哈希、输入输出形状和执行证据；
2. OpenVINO IR 只有在兼容主机完成真实 `compile_model` 和样图推理后才能计为可运行；
3. Sky AI 当前通过天空分割、地平线和水面反射三个专用 ONNX 模型执行；
   `scripts/run_sky_e2e_validation.py` 会递归处理当前清单中的全部有效图片，并为每张记录三模型的
   ONNX Runtime 调用证据。该功能通过只代表候选链路可运行，不代表与 Luminar 输出等价；
4. 验证集通过只说明 zpixel_edit 候选链路稳定，不等于活动 Luminar 参考版本输出等价；
5. 对齐结论必须绑定同一原图、同一参数、同一素材和 Luminar 原版 preview/export。

当前可重建验证输出统一见 `test_data/outputs/luminar-1.28.0-23071/`，固定输入见
`test_data/parity/`。

统一执行入口：

```bash
.venv/bin/python scripts/run_quality_gates.py --level functional
.venv/bin/python scripts/run_quality_gates.py --level exact
```

`functional` 验证项目自身真实可运行；`exact` 额外要求 Luminar preview/export、固定视口
UI 参考和模型专用后处理证据。缺少原版证据时，`exact` 必须返回 blocked。
