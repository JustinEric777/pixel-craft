# Luminar 自动化采样

> 本文说明如何使用 macOS Accessibility 对本机 Luminar Neo 1.28.0 执行可恢复采样，以及如何判断面板探测、效果采样和严格参考输出。

## 目录

- [1. 能力边界](#1-能力边界)
- [2. 代码与配置](#2-代码与配置)
- [3. 运行方式](#3-运行方式)
- [4. 状态与证据](#4-状态与证据)
- [5. 排障](#5-排障)
- [6. 严格对齐关闭条件](#6-严格对齐关闭条件)

## 1. 能力边界

自动采样器通过 Luminar 暴露的 `AXIdentifier` 切换工作区、展开工具、读取参数控件、设置
主滑杆或打开素材选择器，并在预览稳定后保存窗口截图和 Accessibility 快照。它不使用固定
屏幕坐标定位工具。

采样队列固定按“目录 → 预置 → 编辑”执行；每页的区域、卡片和工具按屏幕视觉顺序从左到右、
从上到下排列。队列中的每条记录都有 `page`、`section` 和连续 `scan_order`，不能按 case ID
或文件名字典序替代视觉顺序。

`effect-sampled` 只表示自动化确实执行了滑杆或素材动作；`panel-probed` 只表示工具面板已
展开。两者都不是严格参考输出。只有 Luminar 原版 `preview/export`、输入哈希、参数、素材、
版本和 UI sidecar 全部通过校验后，案例才能进入 `ready`。

## 2. 代码与配置

| 路径 | 职责 |
| --- | --- |
| `configs/luminar_sampling.yaml` | 活动版本、超时、重试、视口和逐工具语义定位配方。 |
| `scripts/luminar_capture/attempt_store.py` | 每次尝试的事件与不可变终态。 |
| `scripts/luminar_capture/native_helper.swift` | 原生 macOS Accessibility、窗口状态与真实鼠标事件边界。 |
| `scripts/luminar_capture/accessibility_driver.py` | 类型化 AX 节点、硬超时和动作接口。 |
| `scripts/luminar_capture/auto_sampler.py` | 整案例重试、工作区恢复、控件发现和稳定帧判断。 |
| `scripts/luminar_capture/sampling_queue.py` | 六类队列记录校验、哈希校验和稳定 capture ID。 |
| `scripts/luminar_capture/queue_runner.py` | 六类处理器分派、失败隔离和断点续跑。 |
| `scripts/run_luminar_sampling_queue.py` | 251 项统一命令行入口。 |
| `scripts/reconcile_sampling_queue_state.py` | 不操作 Luminar，按当前 queue fingerprint 重建对账报告。 |
| `scripts/validate_sampling_data_chain.py` | queue、canonical、原生导出和任务制品一致性门禁。 |
| `scripts/validate_sampling_queue_captures.py` | 全队列原版证据完整性门禁。 |
| `scripts/audit_sampling_effect_changes.py` | 拒绝仅由 JPEG 重编码产生差异的伪效果导出。 |
| `scripts/seed_ui_validation_catalog.py` | 用当前验证集初始化隔离的 46 图 UI 回归目录。 |

采样配方必须给出工具 `locator_id` 和 `strategy`。素材型工具还必须给出
`effective.picker_locator_id`；缺失时案例失败，不会退化为伪效果。

## 3. 运行方式

前置条件：

1. 本机安装版本必须与 `configs/reference.yaml` 的活动参考完全一致。
2. Luminar 已导入验证照片，且主目录窗口可正常打开。
3. 执行终端已获得 macOS“辅助功能”和“屏幕录制”权限。
4. 真正的 Luminar 采样必须使用独立的 macOS 登录会话、虚拟机、第二台 Mac，或用户明确
   预留的前台采样时段。Luminar 的自定义控件需要真实鼠标事件，同一桌面会与日常操作冲突。

当前验证数据根为 `test_data/夏日户外拍照`。先递归刷新验证清单并重绑活动版本用例：

```bash
.venv/bin/python scripts/build_validation_manifest.py \
  --source-dir test_data/夏日户外拍照 \
  --snapshot-dir test_data/parity/inputs/summer-outdoor
.venv/bin/python scripts/rebind_reference_inputs.py
.venv/bin/python scripts/build_parity_cases.py
.venv/bin/python scripts/build_luminar_sampling_queue.py
.venv/bin/python scripts/validate_dataset_freshness.py
```

活动数据集当前为 46 张有效 JPEG。语义样本绑定、案例和队列都携带同一数据集指纹；清理测试
图片后必须重新执行以上四个命令，禁止复用旧输入路径或按剩余文件顺序猜测替代图片。

执行前置检查会激活并读取 Luminar 窗口，因此也必须在独立 GUI 会话或预留的前台时段显式授权：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --limit 1 --preflight --allow-ui-control
```

先查看任务，不操作应用：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --kind sky --limit 1 --dry-run
```

在启动整队列前，先各选一条 `ui/effect/preset/sky/overlay/workflow` 记录做六类冒烟。该选择按
每类第一条视觉扫描记录产生，不会被队列前部的 UI 记录占满：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --one-per-kind --dry-run
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --one-per-kind --allow-ui-control
```

再执行一个案例：

```bash
.venv/bin/python scripts/run_luminar_sampling_queue.py \
  --kind sky --limit 1 --allow-ui-control
```

使用多个 `--record-id`、`--page` 或 `--kind` 可限制范围，`--start-order` 和 `--limit` 可按
扫描顺序切片；默认启用断点续跑。已处于 `ready` 的案例会跳过。预检和实际采样没有显式传入
`--allow-ui-control` 时，命令会以
`foreground-ui-control-not-authorized` 拒绝执行，不会激活 Luminar 或移动鼠标。

生成完整的顺序化队列不需要操作桌面：

```bash
.venv/bin/python scripts/build_luminar_sampling_queue.py
.venv/bin/python scripts/run_luminar_sampling_queue.py --dry-run
.venv/bin/python scripts/validate_sampling_queue_captures.py
```

队列和全部采样、候选、评估产物统一写入：

```text
test_data/outputs/luminar-1.28.0-23071/
```

## 4. 状态与证据

采样器把每次状态变化写入
`test_data/outputs/luminar-1.28.0-23071/captures/`：

```text
captures/
├── staging/<case-id>/
│   ├── before.png
│   ├── before.ax.txt
│   ├── after.png
│   ├── after.ax.txt
│   └── auto-probe.json
├── luminar_outputs/<case-id>/
│   ├── native-export.<ext>
│   ├── export.png
│   └── preview.png
├── attempts/<case-id>/
│   ├── <attempt-id>.json
│   └── <attempt-id>.jsonl
├── state/<case-id>.json
└── logs/<case-id>.jsonl
```

| 状态 | 含义 | 是否可用于严格输出对比 |
| --- | --- | --- |
| `panel-probed` | 工具已展开并完成稳定截图。 | 否 |
| `effect-sampled` | 已设置主参数或选择素材并完成稳定截图。 | 否 |
| `failed` attempt | 本次窗口、定位、参数、素材或稳定性条件未满足；不会覆盖旧 canonical。 | 否 |
| `ready` canonical | 原版预览、导出和元数据已由捕获协议完整校验。 | 是 |

顶层 `state/<case-id>.json` 是投影，不保存无限增长的 history。`canonical` 指向可用于严格比较的成功 attempt；`last_attempt` 记录最近一次运行。默认 resume 只根据 canonical ready 跳过，因此一次辅助功能失败不会让已采样案例重新进入队列。

Luminar 原生导出写入 `capture.native_export_root`，文件名包含 case ID 与 attempt ID。监听器只等待该精确文件，不扫描共享目录，也不会出现覆盖确认。归一化 `export.png` 只用于像素比较，不能替代 `native-export.<ext>` 的原始字节证据。

当前统一队列可执行 45 个效果、123 个免费预置、35 个天空素材、38 个叠加素材、7 个 UI 状态
和 3 个多图工作流，共 251 项。`catalog/presets/edit`、`layer-stack/layer-library/tool-expanded`、
`multi-image` 均使用 1.28.0 上验证过的定位或确定性页面状态；天空和叠加素材按素材 ID 唯一匹配，
找不到或匹配到多项时直接失败。

最终数量以 `diagnostics/sampling-effect-change-audit.json` 和
`diagnostics/sampling-queue-validation.json` 为准。候选输出、网页截图、AX dry-run，以及只达到
`panel-probed` 的记录都不能替代原版 `ready` 证据。原版采样仍需要 Luminar 全屏前台 GUI 控制；
ONNX 推理、候选生成和指标计算才可以在后台运行。

## 5. 排障

### 5.1 `Luminar Neo has no accessibility window`

这表示进程存在但没有主窗口。采样器会按 `automation.retries` 重做整次案例，避免复用旧
AX 索引。如果重试仍失败，手动打开 Luminar 的目录主窗口并保持在前台，再重跑单案例。
采样器不会自动终止应用，因为终止可能丢失未保存编辑。

### 5.2 `snapshot exceeded ...`

原生 Swift helper 通常能在数秒内读取编辑页 AX 树。CLI 仍使用硬超时防止 Luminar 自身
窗口重建或控件查询无限挂起；若持续超时，应先确认 Luminar UI 是否仍响应。

### 5.3 点击工作区后窗口消失

Luminar 1.25 可能暴露重复的工作区 `AXIdentifier`，且 `AXPress` 会返回成功但不切页。
helper 会优先选取启用、有状态和有效边界的节点，并对屏幕内控件发送真实鼠标事件。若窗口
仍从 AX 树消失，单案例应保持 `failed`，不要继续批量采样；重新打开照片并先运行
`--preflight`。该状态属于原应用窗口生命周期问题，不得把已有 staging 截图提升为参考输出。

### 5.4 预检看到窗口，但实际快照为空

Luminar 使用非标准窗口时，CGWindow/AX 可能报告一个 1440×900 窗口，而窗口的 AX 子树暂时
为空。采样器统一采用原生 AX/CGWindow 状态，不再使用 AppleScript 的窗口数量做判定；但空树
仍必须作为失败处理。先在 Luminar 中手动打开“目录”，选中已导入照片并进入“编辑”，确认
终端同时具备辅助功能和屏幕录制权限，再重跑单案例。禁止根据窗口边界存在就写入参考截图。

### 5.5 `uv run` 在 macOS 沙箱中异常退出

工程仍由 uv 管理依赖，但部分受限 macOS 环境中的 `uv run` 会在系统配置初始化阶段 panic。
这种情况下使用已由 uv 同步出的 `.venv/bin/python`、`.venv/bin/pytest` 和
`.venv/bin/ruff` 执行，不改变锁文件或依赖来源。

### 5.6 面板展开但没有效果

检查 `auto-probe.json` 的 `capture_level`。`panel` 表示只完成面板采样；素材工具必须成功
打开选择器并选中缩略图，滑杆工具必须找到可写控件，才能成为 `effect`。

### 5.7 导出成功但被判为原图

Luminar 会重新编码 JPEG，即使没有应用效果也可能产生约 `0.003` 的全局 MAE。采样器同时要求
归一化 MAE 和局部强变化像素占比达到阈值；仅有压缩噪声的结果会记录为
`invalid-unchanged-export`。多滑块工具必须在配方中使用可写的精确 `control_locator_id`，不能依赖
AX 返回顺序。AI 工具还必须等待预览稳定后再导出。

## 6. 严格对齐关闭条件

自动面板采样完成后仍需：

1. 对仍失败的 AI 工具选择能触发其语义效果的验证图；不能通过降低原图差异阈值关闭失败。
2. 对每个多滑块工具记录精确可写控件 ID、默认值、采样值和稳定帧数。
3. 自动完成 Luminar 导出，并校验导出文件稳定性、尺寸、色彩配置、输入哈希和强变化像素。
4. 把固定视口、显示缩放、语言和面板展开状态写入 UI sidecar。
5. 运行参考导入、SSIM/MAE、UI 像素差和逐模型语义门禁；全部通过后才能声明严格等价。

模型推理、候选输出生成、指标计算、测试、构建和报告可以在当前会话后台运行。Luminar 页面
切换、工具展开、参数设置、素材选择和原版导出属于前台 GUI 采样，不能宣称为同桌面无冲突
后台任务。
