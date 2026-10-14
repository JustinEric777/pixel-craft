# Luminar Neo 黑盒参考采集协议

本协议把“复刻”从静态模型盘点变成可重复的输入、参数、输出和 UI 状态证据。
它不复制 Luminar Neo 的私有模型、DLL、图标或受版权保护素材，只记录在拥有合法
使用权的环境中观察到的行为结果。

## 采集环境

- 当前冻结基线为本机 macOS 原生 Luminar Neo 1.28.0 build 23071。记录软件版本、
  系统版本、GPU、显示缩放、语言、
  窗口尺寸和色彩配置。
- 每次采集先关闭已有编辑，导入同一份源图片，等待缩略图和预览完全稳定。
- 预览和最终导出必须分别保存；不能用屏幕截图代替导出文件。
- 每次采集保存操作事件序列，至少包括工具打开、参数修改、应用、撤销、重做和导出。

UI 截图必须同时保存 sidecar 元数据，至少包含：参考版本 ID、应用或前端构建标识、物理
截图宽高、CSS viewport 宽高、device pixel ratio、系统显示缩放、语言、页面状态和展开
面板。仅 PNG 像素尺寸一致不代表视口一致；例如 DPR=2 时 1440×900 图片可能来自
720×450 的逻辑视口并错误触发响应式断点。缺少这些字段的截图只能作为诊断候选，不能
进入严格 UI 门禁。

## 用例目录

`test_data/parity/references/luminar-1.28.0-23071/cases.json` 是当前机器可读用例清单。
每个用例包含：

- `sample_id`、源图片 hash 和相对路径；
- `capability_id`；
- 默认值、最小值、最大值和 25/50/75% 参数锚点；
- 使用的素材 id 及素材 hash；
- 原版 preview/export/mask/UI capture 路径；
- zpixel_edit candidate 路径；
- 比较状态和失败原因。

## 文件命名

在授权的黑盒采集机上，将结果放到项目外部的 parity 数据目录，再通过 manifest
导入，不把原安装包复制进源代码仓库：

```text
test_data/outputs/luminar-1.28.0-23071/captures/
├── staging/<case_id>/before.png
├── staging/<case_id>/after.png
├── luminar_outputs/<case_id>/preview.png
├── luminar_outputs/<case_id>/export.png
├── luminar_outputs/<case_id>/mask.png
├── luminar_ui/<case_id>/before.png
├── luminar_ui/<case_id>/after.png
└── metadata/<case_id>.json
```

项目提供可恢复的半自动采集器。Luminar 的主工作区没有稳定暴露完整的 macOS
辅助功能控件，因此采集器负责案例选择、APP 启动、窗口截图、导出稳定性检查、哈希和
元数据；工具选择与参数设置仍需采集人员在 Luminar 内确认，不能用坐标猜测后直接标记完成。

```bash
# 列出 Sky AI 案例
.venv/bin/python scripts/luminar_capture/run_capture.py list \
  --capability-id sky_replace

# 准备一个案例并记录待导入原图/参数
.venv/bin/python scripts/luminar_capture/run_capture.py prepare \
  --case-id <case_id>

# 在 Luminar 中完成导入、设参、预览和导出后采集证据
.venv/bin/python scripts/luminar_capture/run_capture.py capture-before \
  --case-id <case_id>
.venv/bin/python scripts/luminar_capture/run_capture.py capture-after \
  --case-id <case_id>
.venv/bin/python scripts/luminar_capture/run_capture.py finalize \
  --case-id <case_id> \
  --preview-source <preview_image> \
  --export-source <export_image>
```

`finalize` 只有在 preview/export 都存在且导出文件停止变化后才会生成 metadata 和
`ready` 状态。`capture-before` 和 `capture-after` 先写入 `staging/`；只有成功
`finalize` 后才提升到正式 `luminar_ui/`。未验证截图不会进入等价门禁，也不会把窗口
截图当作最终导出文件。

`metadata/<case_id>.json` 最少包含：

```json
{
  "case_id": "sky_tutorial__sky_replace__amount_0_5",
  "reference_build": "luminar-neo-macos-1.28.0-23071",
  "app_version": "1.28.0",
  "app_build": "23071",
  "platform": "macOS",
  "window": {"width": 1920, "height": 1200, "scale": 1.0},
  "parameters": {"amount": 0.5},
  "asset_id": "sky_001",
  "input_sha256": "...",
  "preview_sha256": "...",
  "export_sha256": "...",
  "events": ["open_tool", "set_parameters", "apply", "export"]
}
```

## 等价门禁

只有以下条件同时满足，case 才能从 `pending` 变为 `passed`：

1. 原版和 candidate 的输入 hash、尺寸、方向、色彩空间一致；
2. 参数和素材 hash 一致；
3. preview/export 都存在；
4. mask、bbox、landmark 等中间证据（适用时）存在；
5. 自动指标和关键区域人工检查通过；
6. UI 状态截图和事件序列可回放。

当前工程没有原版黑盒输出时，工具必须显示 `pending-reference`，不能自动判定通过。
采集器会先核对 App 的版本、build 和 bundle id；不同版本的截图、导出或 metadata 不得
挂接到当前 1.25 用例。旧 1.26 证据保留在其原有版本目录中。
