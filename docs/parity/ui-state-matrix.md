# UI 状态矩阵

官方视觉方向和工作区参考见 `docs/parity/ui-reference-skylum.md`。Skylum 官网图片用于
风格与信息架构；本轮像素和行为验收基线固定为本机 Luminar Neo 1.28.0 build 23071。

每个编辑工具必须覆盖以下用户可见状态；截图和事件序列来自授权的 Luminar
黑盒采集后，写入当前 reference profile 的 `captures/luminar_ui/<case_id>/`，candidate
写入对应版本的 diagnostics 目录。

| 状态 | 需要验证的行为 |
|---|---|
| empty | 未上传图片时保留画布尺寸，并提示下一步动作 |
| ready | 工具可选、参数显示默认值、应用按钮可用性正确 |
| selected | 当前工具和功能分组有明确选中态 |
| loading | 处理期间按钮、滑块、导出和历史操作稳定禁用 |
| preview-ready | 新预览不会被旧请求覆盖，结果尺寸稳定 |
| error | 错误可读，并提供重试或重新打开图片动作 |
| blocked | 缺模型、未配置生成 provider 或缺素材时明确说明原因 |
| before-after | 原图与结果切换不改变项目编辑栈 |
| undo-redo | 撤销/重做后预览、编辑栈和导出结果一致 |
| export | 导出处理中、完成和失败状态清晰 |

验收优先断言文本、禁用状态、选中状态、图片 URL 和事件序列；不要只断言颜色或阴影。
