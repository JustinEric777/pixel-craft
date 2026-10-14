# OpenVINO IR 运行策略

项目默认使用 ONNX Runtime。OpenVINO 只用于无法可靠转换为 ONNX、且在目标主机完成真实
编译和样图推理的 XML/BIN 模型，不作为静默降级或假成功路径。

当前 `.venv` 是 uv 管理的原生 arm64 CPython 3.11.16，已安装 OpenVINO 2025.4.1；但在
本机显式编译真实 IR 时仍出现底层运行时失败。因此 `configs/runtime.json` 将 OpenVINO
设置为 `auto`，能力解析优先选择已验证的 ONNX 派生模型。IR 文件存在不计为可用证据。

启用显式探针：

```bash
.tools/uv sync --extra runtime-openvino
ZPIXEL_ENABLE_OPENVINO=1 .venv/bin/python scripts/probe_openvino_ir.py
```

单个 IR 进入生产候选前必须完成：

1. XML/BIN 哈希和配对检查；
2. `read_model`、`compile_model` 和真实图片 forward；
3. 模型专用颜色空间、resize、归一化、量化和输出语义验证；
4. pipeline 确实消费模型结果，输出不是启发式占位；
5. 与活动参考 `configs/reference.yaml` 指向的 Luminar Neo 1.28.0 build 23071 做同参数
   对照；保留的 1.26 仅用于版本差异审计。

能转换的模型使用 `OpenVINO Frontend → ONNX` 路径。转换结果必须通过 ONNX checker、
ONNX Runtime forward、模型 contract 和功能 E2E；失败时保留 IR 并明确阻断对应能力，不
静默切换到基础滤镜。
