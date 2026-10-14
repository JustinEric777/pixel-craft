# Luminar Neo 1.28 全链路对齐执行报告（2026-08-26，第二轮）

> 参考对象固定为本机 Luminar Neo 1.28.0（build 23071，macOS，zh-Hans）。本报告只记录本轮真实执行结果；未通过的门禁保持 blocked，不以截图存在、按钮可点击或测试通过替代像素/效果/交互对齐结论。

## 1. 执行结论

本轮完成了前端右侧工作区重构、图标补齐、Portable 素材授权审计、应用内 Browser 真实交互验证、七状态当前构建证据刷新、效果/多图/模型复验、定向无变化采样试运行、数据清理和两轮 Exact 全门禁。

项目仍未达到“与本机 Luminar Neo 绝对对齐”。两轮 Exact 结果完全一致：28 项中 22 项通过，5 个必需门禁失败，1 个可选门禁失败。

必需失败项：

1. `multi-image`
2. `output-parity`
3. `exact-incremental-parity`
4. `ui-parity`
5. `interaction-execution`

可选失败项为 `model-contract-inventory`。

UI 当前构建证据、完整 Python/前端测试、Ruff、生产构建、数据链、采样队列、实际模型调用契约均通过。结论是“工程闭环继续增强，但绝对等价仍被可测量差异阻断”。

## 2. 本轮完成的实现

### 2.1 编辑器右侧工作区

将原先混在单一 `mode` 中的页面状态拆为：

- 页面工作区：目录、单图编辑、多图工作流；
- 编辑器面板：预设、工具、编辑、更多、信息；
- 面板展开/收起状态。

新增并接入：

- `EditHistoryPanel`：读取真实项目编辑栈，支持删除编辑；
- `MorePanel`：展示生成式、增强和合并工具；HDR、焦点堆叠、全景拼接进入真实工作流；
- `InfoPanel`：只显示项目实际具备的尺寸、编辑、图层和元数据，不虚构 EXIF；
- `WorkspaceRail`：预设、工具、编辑、更多、信息均可切换，重复点击当前入口可收起/恢复面板。

Browser 验证中发现并修复三项跨工作区缺陷：

1. `更多 -> 提升分辨率` 只切换工具面板但不展开详情；现由显式 inspection request 打开目标检查器。
2. 进入 HDR 等多图工作流后，顶部仍显示单图文件名和单图导出；现显示工作流标题并隐藏单图导出。
3. 编辑页顶部“目录”只是文字，无法返回目录；现为真实导航按钮。

### 2.2 图标和视觉素材

扩展了代码内 SVG 图标系统，覆盖历史、更多、信息、帮助、升级、删除、锁定、修复、生成式工具、目录、网格、最近、教程、排序、工作流导航等入口。前端 TSX 中已清除本轮识别出的功能性 Unicode 图标占位；图层素材返回按钮也改为 SVG。

本轮没有直接复制 Portable 安装包素材。新增只读审计脚本 `scripts/audit_external_luminar_assets.py`，结果为：

- 用户提供目录实际声明版本为 Windows x64 `1.27.1.17225`，并非目录名所示的目标构建；
- 共识别 1,757 个候选记录；
- 206 个哈希已与项目 manifest 中现有记录匹配；
- 1,138 个属于付费或推广候选；
- 619 个仍需授权判定；
- 与目标 macOS 1.28.0 build 23071 不匹配；
- `copy_performed=false`。

因此该目录可用于只读结构/哈希研究，不能作为目标版本像素素材的直接来源，也不能绕过现有 `local-research-only-until-authorized` 许可策略。

### 2.3 Browser 当前构建证据

使用 Codex In-app Browser 26.818.22352 在 `1440×900` 逻辑视口建立并验证以下状态：

- 目录；
- 预设；
- 编辑；
- 图层栈；
- 图层素材库；
- 工具展开；
- HDR 多图工作区；
- 编辑历史、更多、信息、面板折叠、增强工具跳转。

七张逻辑候选按既有合同使用 Lanczos 派生为 `2880×1800`，重新绑定当前 frontend build hash。`validate_ui_execution_evidence.py` 最终为 `7/7`、issue `0`。Browser 控制台错误为 0。

### 2.4 黑白、降噪与无变化导出

现有前端仍保留“黑白必须先转换为黑白，之后亮度/饱和度和应用才可用”的交互门禁；测试覆盖继续通过。采样配置中的降噪仍要求选择明确等级，所有效果采样仍需从原始状态开始。

无变化审计结果保持：251 条记录中 230 ready、11 not-applicable、10 条 `invalid-unchanged-export`。本轮没有重跑其余 241 条。

对其中一条降噪无效记录进行了精确 dry-run 和单条实机试运行。队列只选中 scan order 173 的目标记录，但本机 Luminar 进程没有可用窗口边界，试运行在调整效果或导出之前失败。为避免制造额外失败尝试，其余 9 条未继续。Canonical 记录未被覆盖，复验仍为 251/251 ready、issue 0。

## 3. 执行前后对比

| 验收域 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| Exact 全门禁 | 22/28 | 两轮均 22/28 | 结果稳定，仍 blocked |
| 编辑/更多/信息 | 入口禁用或无独立行为 | 三个独立可用面板 | 真实 Browser 验证通过 |
| 更多 -> 增强工具 | 切换后不展开详情 | 自动进入目标工具检查器 | 修复 |
| 多图顶部状态 | 残留单图文件名/导出 | 工作流标题、无单图导出 | 修复 |
| 编辑 -> 目录 | 无返回入口 | 顶部目录按钮可返回 | 修复 |
| 功能性字符图标占位 | 仍有多处 | 本轮扫描为 0 | 已替换为 SVG |
| UI 当前构建证据 | 7/7 | 7/7，重新绑定当前 build | 保持可信 |
| UI 像素门禁 | 0/7 | 0/7 | 未达到绝对对齐 |
| edit UI MAE | 0.030773 | 0.031230 | 轻微回退，仍高于 0.03 |
| catalog UI MAE | 0.150737 | 0.168233 | 当前目录数据仅 21 图，差异扩大 |
| presets UI MAE | 0.092873 | 0.099465 | 预设数据结构仍不一致 |
| multi-image UI MAE | 0.072490 | 0.072674 | 基本持平，仍为空态证据 |
| 原生交互 | 8/10 | 8/10 | 缺图层和多图观察 |
| 正式 Browser 合同 | 1/10 | 1/10 | 本轮面板验证尚未形成其余 9 条 raw contract trace |
| 主效果 | 36/45 | 36/45 | 9 项失败未伪造提升 |
| Exact 效果 | 38/69 | 38/69 | 31 项失败未伪造提升 |
| 多图 | 2/3 | 2/3 | 全景仍失败 |
| Python | 290 passed | 291 passed | 新增外部素材审计测试 |
| 前端 | 13 passed | 19 passed（8 files） | 新增面板、导航和跨面板回归测试 |
| Ruff / build | 通过 | 通过 | 无回退 |
| 采样数据链 | 251/251 | 251/251，issue 0 | 未重复有效采样 |
| 安全清理 postcheck | 0 path / 0 byte | 0 path / 0 byte | 两轮门禁后重新归零 |

## 4. 当前门禁明细

### 4.1 UI

| 状态 | MAE | Changed pixel ratio | 结果 |
|---|---:|---:|---|
| catalog | 0.168233 | 0.769718 | failed |
| presets | 0.099465 | 0.507364 | failed |
| edit | 0.031230 | 0.310445 | failed |
| layer-stack | 0.031230 | 0.310445 | failed |
| layer-library | 0.053699 | 0.447256 | failed |
| tool-expanded | 0.038464 | 0.352930 | failed |
| multi-image | 0.072674 | 0.737393 | failed |

阈值仍为 MAE 不高于 0.03、changed pixel ratio 不高于 0.02。所有状态均为真实失败。

### 4.2 效果、多图和模型

- 主效果：45 条中 36 通过、9 失败。
- Exact：69 条中 38 通过、31 失败、0 pending。
- 多图：HDR 和焦点堆叠通过；全景失败。
- 实际模型调用：22/22 active model-backed cases 通过，16/16 被调用逻辑模型契约通过。
- 模型库存：92 条基础契约有效，26 条有模型专用验证，66 条 pending；因此可选 exact inventory 门禁失败。
- `ai/model` 静态 validator：0 阻塞。

### 4.3 交互

原生 10 条合同通过 8 条，缺：

1. `layer-add-reorder-opacity-delete`
2. `multi-image-workflow`

完整 interaction execution 仍只有 1/10 正式 Browser 记录，issue 11。当前界面的面板交互已实测，但还不能替代合同要求的原生 observation、API assertion、截图 hash 和 raw event trace。

## 5. 数据整理与删除结果

`test_data` 顶层当前仅保留：

- `multi_image`：确定性多图输入；
- `outputs/luminar-1.28.0-23071`：唯一目标版本输出根；
- `parity`：验证输入、reference 和 schema；
- `夏日户外拍照`：源数据集。

`outputs` 根目录没有散落图片，`test_data/luminar_1_26` 不存在。

本轮两次 Exact 验证会重新生成 overlay 工作区；两次清理合计删除约 234,173,200 字节的可重建 workspace，另移除本次失败试运行产生的 391 字节 transient staging。最终：

- cleanup dry-run：0 path / 0 byte；
- redundant native export：0；
- transient path：0；
- 采样数据链：251/251、issue 0。

存储审计仍发现 195 个相同字节组、425 个额外物理副本，理论重复约 435,961,313 字节。这些主要是不同记录的 before、export/native-export、日志和 attempt 证据。安全删除器认定可删 canonical export 为 0，因此没有按哈希盲删。另有 100 个 orphan state（Exact/校准历史）仍被现有报告链使用，未执行 495 路径的 stale prune。

## 6. 完整遗漏确认

仍阻断绝对对齐的事项：

1. UI 像素门禁 0/7；catalog、presets 的数据结构与原生差异最大。
2. 编辑状态 MAE 已接近阈值，但 changed pixel ratio 仍远高于阈值，不能只微调一个颜色 token。
3. 右侧“帮助”和“升级”目前只有视觉入口，没有 Neo 等价业务闭环。
4. 生成式工具在当前免费产品范围中显示为锁定，未实现本机 Neo 的云端生成式服务。
5. 正式 Browser interaction contract 仍缺 9 条；原生 interaction 缺 2 条。
6. 10 条无变化旧导出仍未被有效替代；本机 Neo 无窗口使定向修复暂停。
7. 主效果 9 项、Exact 31 项仍失败。
8. Panorama stitching 仍未通过。
9. 66 个未启用模型缺模型专用契约。
10. 100 个历史 orphan state 尚未进入显式 archive manifest。
11. 两轮 Exact 虽稳定，但均 blocked，不能声明 release 或绝对对齐。

## 7. 下一步建议

### P0：先关闭前端数据和正式交互合同

1. 以本机 1.28 的真实目录观察为准，为 catalog 增加 folder/album/import-order/relative-path 数据模型；当前 21 图扁平目录不是 CSS 问题。
2. 将 preset inventory 调整为本机 1.28 的推荐、购买、基本功能、新品结构；继续复用真实 preview API，不放静态假图。
3. 为“编辑、更多、信息、目录返回、工作流顶部状态”补 Browser raw trace 构建器；随后完成剩余 10 条合同，而不是把人工 DOM 检查算作合同通过。
4. 给帮助、升级定义明确产品范围：要么实现本地帮助/许可页，要么显示可审计的 unavailable 状态；不能保留无行为按钮。

### P1：恢复本机 Neo 后只修 10 条无效记录

1. 在 Luminar Neo 中手动打开目录窗口并确认 Accessibility/屏幕录制权限；不要只保留后台进程。
2. 先运行 `--preflight`，确认窗口边界、版本、截图和 AX tree 可用。
3. 逐条运行 10 个 invalid record：每条开始前恢复原图；黑白先转换；降噪选择明确等级；导出前验证预览变化；导出后验证存在恢复原图状态。
4. 新结果通过 source-change、preview/export 一致性和文件名回读后，再使旧记录失效；其余 241 条不重采。

### P2：效果与多图按共享根因处理

1. 先修主效果的 face/portrait ROI、LUT 颜色空间和插值，再处理天空/光照、fog/depth。
2. 每个能力只生成当前 candidate，不修改 reference；同时跑 anchor、holdout 和中性输入。
3. 全景先保存特征对应、局部位移场和有效边界，确定投影/warp 后再处理 seam、曝光和裁切。

### P3：像素收敛和最终发布

1. catalog/presets 数据模型对齐后重新建立七状态当前 build 证据。
2. edit/layer/tool 使用同一共享壳层调整字体、重采样、底栏和面板密度，禁止逐截图补丁。
3. 达到 Native 10/10、Browser 10/10、UI 7/7、主效果 45/45、Exact 69/69、Multi-image 3/3 后，再执行两轮 Exact。
4. 两轮之间不得修改代码、配置、输入、reference、素材、视口或环境；只有两轮必需失败均为 0 才可声明绝对对齐。

## 8. 关键证据

- 第一轮：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-current-round-1.json`
- 第二轮：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-current-round-2.json`
- UI 当前构建：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution.json`
- UI 像素：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-parity-current-final.json`
- 原生交互：`test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-native-current-final.json`
- 完整交互：`test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-execution-current-final.json`
- 主效果：`test_data/outputs/luminar-1.28.0-23071/diagnostics/parity-report-current-final.json`
- Exact：`test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-incremental-parity-current-final.json`
- 多图：`test_data/outputs/luminar-1.28.0-23071/diagnostics/multi-image-current-final.json`
- 外部素材审计：`data/diagnostics/external-luminar-assets.json`
- 存储审计：`test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-storage-current-final.json`

