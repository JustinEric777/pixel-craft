# 架构与模块边界

## 依赖方向

```text
frontend → api → services → core
                    │
                    ├─→ ai/pipeline → ai/model → ONNX Runtime
                    │                         └→ OpenVINO（可选）
                    ├─→ image_ops
                    └─→ ports ← storage
```

`api/app.py` 是唯一 composition root：配置在这里加载一次，仓储、素材目录、模型 pipeline、renderer 和用例服务在这里组装。环境变量只允许由 `configs/store.py` 读取。

## 根级模块

| 模块 | 负责 | 不负责 |
|---|---|---|
| `core/` | 项目聚合、编辑节点、工作流实体、执行图值对象 | HTTP、Pillow、模型 Session、文件系统 |
| `services/` | 编辑、预置、目录和多图用例编排；定义 ports | 解析 HTTP、创建推理后端、实现像素算法 |
| `ai/model/` | `BaseInference`、显式 model wrapper、注册、懒加载、LRU、资源释放 | 项目状态、页面状态、素材选择 |
| `ai/pipeline/` | 模型调用编排、输出语义和模型效果流程 | 文件仓储和 HTTP |
| `image_ops/` | 确定性效果、天空合成、edit graph、多图合并算法 | 模型发现、项目持久化 |
| `storage/` | 项目、图片、素材、manifest 和 artifact cache | 业务规则 |
| `api/` | FastAPI 路由、DTO、日志和依赖组装 | 图像算法和模型后处理 |
| `configs/` | 路径、运行时、执行图、能力策略、免费预置和公开 UI 配置 | 图像数学实现 |

旧 `application/`、`imaging/`、`infrastructure/`、`server/` 不保留兼容包，启动入口固定为 `api.app:app`。

## 模型层

`configs/model.yaml` 是唯一模型注册源，每条记录必须包含唯一的 `inference_class`。`ai/model/onnx/<task>/<model>.py` 和 `ai/model/openvino/<task>/<model>.py` 每个文件只对应一个模型工件；`runtime/` 只封装执行后端，不能被生产配置直接注册。缺少显式 wrapper、文件、契约或后处理时直接阻断。

```text
models/
├── onnx/          默认生产模型
├── openvino/      无法可靠转换的 XML/BIN
├── contracts/     输入、归一化、输出和后处理契约
└── metadata/      tokenizer 与模型附加元数据
```

模型替换只改三处：替换 `models/` 下权重、修改 `configs/model.yaml` 对应记录、调整该模型自己的 wrapper。注册解析、动态实例化和加载缓存分别固定在 `ai/model/registry.py`、`ai/model/factory.py` 和 `ai/model/loader.py`。

## 数据与证据

```text
data/
├── library/       图库索引、导入图片、缩略图
├── workspace/     项目、上传、导出和多图会话
├── cache/         可重建的模型中间产物
└── diagnostics/   可重建的验证、性能和对比输出

test_data/
├── parity/        固定用例、schema、验证样本和参考矩阵
├── 夏日户外拍照/ 当前用户验证图片
└── ...            用户提供的验证图片
```

`docs/` 只存 Markdown；机器生成结果不进入文档目录，也不建立 `reports/` 历史仓库。

## 等价门禁

“能加载模型”和“能生成图片”都不等于 Luminar 等价。能力只有同时满足以下条件才能标记为 `parity-passed`：

1. 本地权重完成真实推理，执行 trace 可证明调用了目标模型；
2. 颜色空间、缩放、归一化、输入输出语义和资源释放契约已验证；
3. 模型后处理、蒙版边缘、几何、融合和参数响应有自动测试；
4. 固定验证集存在活动 Luminar 参考版本的同参数 preview/export；
5. 像素指标、关键区域视觉审查和 UI 交互状态全部通过。
