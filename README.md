# pixel-craft

> pixel-craft 是一个本地优先的照片管理、非破坏编辑与 AI 推理项目，包含 Python/FastAPI 后端和 React/TypeScript 前端。

## 目录

- [1. 项目定位](#1-项目定位)
- [2. 目录结构](#2-目录结构)
- [3. 快速开始](#3-快速开始)
- [4. 配置入口](#4-配置入口)
- [5. 验证命令](#5-验证命令)
- [6. 文档导航](#6-文档导航)

## 1. 项目定位

pixel-craft 面向本地图片工作流，当前包含以下部分：

- 本地图片、项目和素材管理。
- 非破坏编辑、确定性图像处理和多图工作流。
- 基于 ONNX Runtime 的模型推理，以及可选的 OpenVINO 运行时。
- 由 FastAPI 提供的后端接口和由 Vite 驱动的 Web 客户端。
- 模型契约、能力配置和验证脚本，用于约束推理输入输出及功能状态。

项目默认在本机运行，运行数据和缓存写入 `data/`，模型与素材分别由 `models/` 和 `assets/` 管理。

## 2. 目录结构

```text
ai/                 模型封装、运行时和推理 pipeline
api/                FastAPI 应用、路由、DTO 和日志
configs/            模型、运行时、能力、预置和 UI 配置
core/               项目状态、工作流规则、执行策略和业务错误
services/           编辑、多图服务及其依赖端口
image_ops/          图像效果、渲染和多图合并算法
storage/            项目、素材、图片、模型清单和缓存适配器
frontend/           React/TypeScript Web 客户端
models/             模型权重、元数据和模型契约
assets/             图片素材、元数据和素材清单
data/               library、workspace、cache 和 diagnostics 运行数据
test_data/          验证图片、输出结果和测试夹具
scripts/            检查、转换、验证和基准脚本
docs/               工程文档
tests/              后端自动化测试
```

## 3. 快速开始

### 环境要求

- Python 3.11 或更高版本。
- `uv`，项目使用 `.tools/uv` 管理 Python 依赖。
- Node.js 和 npm。

### 安装依赖

在项目根目录执行：

```bash
.tools/uv sync --group dev
cd frontend
npm install
cd ..
```

### 启动开发环境

```bash
./run-local.sh
```

启动后访问：

- 前端：`http://127.0.0.1:5173/`
- 后端状态：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`

脚本会同时启动后端和前端，按 `Ctrl+C` 停止服务。若只需单独启动某一端，可分别运行：

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

## 4. 配置入口

| 路径 | 用途 |
|---|---|
| `configs/model.yaml` | 模型注册信息和模型级配置 |
| `configs/runtime.json` | 推理运行时和后端选择 |
| `configs/capabilities/` | 功能能力及可用状态 |
| `configs/presets/` | 预置和编辑参数 |
| `configs/ui/` | 前端界面配置 |
| `models/contracts/` | 模型输入输出契约 |
| `assets/manifests/` | 素材清单和索引 |

修改配置后，应根据影响范围运行对应的后端测试、模型检查或前端构建验证。

## 5. 验证命令

### 后端

```bash
.venv/bin/ruff check ai api configs core services image_ops storage scripts tests
.venv/bin/pytest -q
```

### 前端

```bash
cd frontend
npm test
npm run build
```

### 功能验证

```bash
.venv/bin/python scripts/run_validation_suite.py
.venv/bin/python scripts/run_sky_e2e_validation.py
.venv/bin/python scripts/run_preset_validation.py
.venv/bin/python scripts/run_multi_image_workflow_smoke.py
```

## 6. 文档导航

- [架构说明](docs/architecture.md)：系统边界、分层职责和核心数据流。
- [模型配置与替换](docs/model-configuration.md)：模型注册、契约和运行时配置。
- [本地参考样本约定](docs/reference-samples.md)：验证样本和参考数据的组织方式。
- [文档索引](docs/index.md)：完整工程文档列表。
