# 素材 provenance 与发布门禁

素材实际文件位于 `assets/`，模型仍位于 `models/`。`assets/manifests/registry.json` 记录
路径、尺寸和 hash；`assets/manifests/licenses.json` 记录每个 family 是否可以再分发。

执行：

```bash
.venv/bin/python scripts/build_asset_audit.py
```

当前素材许可状态是 `unknown`，因此 audit 只能用于本地研究，不能据此生成可再分发
的商业素材包。只有补齐逐素材或 family 级授权证据后，才允许把
`redistributable` 改为 `true`。
