# 模型配置与替换

## 唯一配置入口

`configs/model.yaml` 是模型运行时的唯一注册源。当前登记 22 个活动 ONNX 工件，
均使用 ONNX Runtime。每个工件都对应一个独立 Python wrapper 和一个
`models/contracts/<model-id>.json`，便于单独替换、验证和回滚。

记录必须包含唯一 `id`、稳定 `logical_id`、任务、格式、权重路径、wrapper 导入路径、
状态和资源预算。注册器拒绝未知字段、重复 ID、重复 wrapper 和直接注册公共 runtime 类。

当前效果参考是本机 Luminar Neo 1.28.1 build 23487。只读安装清单位于
`test_data/outputs/luminar-1.28.1-23487/inventory/install-manifest.json`：26 个模型变体
展开为 52 个 XML/BIN 文件，并已在项目模型目录中找到同名、同格式且 SHA-256 相同的文件。
来源和哈希审计属于诊断信息，不写入强类型运行配置。
这只证明工件一致，不代表模型预处理、后处理或 Luminar 最终效果已经等价。

## 模块边界

```text
ai/model/
├── base_inference.py       生命周期与 InferenceResult
├── registry.py             model.yaml 解析与后端候选选择
├── factory.py              wrapper 动态实例化和类型校验
├── loader.py               懒加载、LRU、租约与释放
├── runtime/                ONNX Runtime/OpenVINO 执行适配
├── onnx/<task>/<model>.py  一个 ONNX 工件一个 wrapper
└── openvino/<task>/<model>.py
                            一个 IR 工件一个 wrapper

ai/pipeline/                多模型调用、任务后处理和图像效果编排
configs/model.yaml          唯一模型配置
models/onnx/                ONNX 权重
models/openvino/            XML/BIN 权重
models/contracts/           输入、归一化、输出、后处理契约
models/metadata/            运行时确实使用的 tokenizer 等附属数据
```

模型私有 resize、颜色空间、归一化、张量布局和输出解析必须放在自己的 wrapper 或对应
pipeline，不能写入通用 runtime，也不能由 API 层硬编码。

## 当前运行策略

- ONNX Runtime 是首选后端；逻辑模型会优先解析到已验证的 `_onnx` 派生项。
- OpenVINO 是无法可靠转换时的备用。每个 IR 必须通过编译、真实 forward 和有限值检查；
  不会把文件存在或仅能编译误判成运行时可用。
- 已转换并真实 forward 的关键派生模型包括天空分割、地平线、水面天空、动物分割、
  DepthAnythingV2 Small、skin detector、人脸框/关键点、人体衣物分割、显著性、魔法光线、
  深度图和多种皮肤分割模型。
- CoreML 不属于项目运行时。

## 替换流程

1. 将权重放入 `models/onnx/` 或 `models/openvino/`。
2. 修改 `configs/model.yaml` 中对应记录的路径、哈希、格式、任务和 wrapper。
3. 只修改 `ai/model/<backend>/<task>/<model>.py` 中该模型自己的预处理和后处理。
4. 更新 `models/contracts/<model-id>.json`，明确颜色空间、尺寸、归一化、量化、输出语义和
   后处理验证状态。
5. 运行结构校验、真实 forward、任务 pipeline 和固定样图测试。
6. 若替换会改变最终效果，必须重新跑 Luminar 黑盒对齐，不能沿用旧的 parity 状态。

## 验证命令

```bash
.venv/bin/python .agents/skills/ai-model-inference/scripts/validate_model_module.py --project-root .
.venv/bin/python scripts/check_model_contracts.py \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/model-contract-audit.json
.venv/bin/python scripts/build_model_source_map.py
.venv/bin/python scripts/audit_model_pipelines.py \
  --output test_data/outputs/luminar-1.28.1-23487/diagnostics/model-pipeline-audit.json
.venv/bin/python scripts/run_validation_suite.py
.venv/bin/python scripts/run_sky_e2e_validation.py
.venv/bin/pytest -q
```

当前注册工件、wrapper 和 model-specific contract 均为 22/22；模型专项检查为 0 条阻塞发现。
这只证明运行契约完整，不代表 Luminar 黑盒输出已经等价。

## 不得混淆的三个状态

1. **文件已登记**：权重、wrapper 和 contract 存在。
2. **运行时可用**：真实输入可以完成 forward，pipeline 消费了模型输出。
3. **Luminar 等价**：预处理、后处理、参数响应和最终像素通过当前 1.28.1 build 23487 黄金样本。

只有第三种状态才能标记为 `parity-passed`。当前项目已经覆盖前两种状态中的主要功能，
但 1.28.1 的完整 Native 黑盒输出对齐仍待完成。
