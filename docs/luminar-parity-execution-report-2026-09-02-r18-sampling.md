# Luminar Neo 绝对对齐执行报告（R18 current-only）

日期：2026-09-02  
Native 基准：Luminar Neo macOS 1.28.0 (23071)，zh-Hans，2880×1800 物理像素  
结论：采样主队列与 current UI 证据链已经完整；产品像素、部分效果算法、完整交互和 Native 持久化仍未达到绝对对齐，不能宣称全量完成。

## 1. 本轮实际完成

### 1.1 主采样与恢复

- 主采样队列：409/409 canonical ready，0 pending。
- 分类：UI 170/170、effect 40/40、preset 123/123、sky 35/35、overlay 38/38、workflow 3/3。
- 直接调用 Luminar 原生 `reset-all-edits`；最终返回 `ok=true`、`enabled=false`、`performed=false`。
- 独立状态复核仍为 `enabled=false`。含义是当前图片已经处于原始状态，菜单项不可点击，而不是自动化遗漏点击。

### 1.2 采样性能与导出正确性

- 导出菜单动作改为受控的 Luminar 进程级点击，并在动作后恢复光标位置。
- 导出文件按产品、能力、输入、参数、attempt 生成可读且抗冲突的名称。
- 导出完成判断改为按唯一 stem 查找 Luminar 实际生成的后缀；当前 Native 实际导出 PNG 时不再错误等待 `.jpeg`。
- 导出保存面板会恢复为原图方向和尺寸。Bokeh 验证从错误的 843×1440/1080×1440 收口到 1080×1845。
- Bokeh 重采样总耗时由 49.2 秒降到 23.1 秒，约降低 53%；最近一次导出阶段为 6.37 秒。

### 1.3 Bokeh 当前合同

- 删除并拒绝虚假的 `radius` 参数。
- 增加真实的 `bokeh_shape`：circle、filled_circle、oval、hexagon、heart、star。
- Browser 已验证 change → API → preview → undo → redo → reset → export 全链路。
- Native 参数绑定审计维持 74 个支持项；UI 状态矩阵为 170，交互合同矩阵为 84。

### 1.4 UI current-only 证据链

- 新增 `scripts/build_ui_regions.py`，从当前 170 个已验证 Native 状态生成区域合同。
- `configs/parity/ui-regions.json` 已从 16 个旧 ID 更新为 170 个 current ID；无旧 ID 映射或兼容分支。
- 仅保留明确排除项：教程、帮助、商店/推广和 iCloud 行；区域仍由 Native AX selector 与冻结哈希约束。
- Native reference manifest：170/170 verified。
- Browser execution evidence：170/170 executed、170/170 passed、0 issue。
- Region manifest gate：passed，0 issue。
- 实际 UI 像素对比：0/170 passed、170 failed。MAE 0.02899～0.17016，changed-pixel ratio 0.28152～0.99659。现在的失败均为真实视觉差异，不再是旧 ID、缺图或缺区域造成的结构性假失败。

### 1.5 历史精确采样复用

- exact matrix：206 个 current 语义记录。
- 对历史 exact evidence 重新执行 current schema 复验：状态必须 ready，输入/导出文件必须存在，导出哈希必须匹配，输出尺寸必须与输入一致，参数必须仍属于当前能力合同。
- 只允许删除“当前未声明、但属于公共参数且值等于当前默认值”的中性字段；不会吞掉非默认未知参数。
- 58 条历史 Native evidence 被合法复用。
- 2 条包含旧 `radius=8.0` 的 Bokeh evidence 被明确拒绝。
- current active cohort：133 条，其中 58 ready、75 missing；另有 73 个 exact matrix 锚点因为没有 Native 参数自动化绑定而保持 blocked。
- current exact candidate：133/133 生成成功；对已有 Native 对照的结果为 50 passed、8 failed，另有 75 pending-reference。

### 1.6 代码验证

- Ruff：passed。
- Python：433 passed，1 个第三方 Starlette/httpx deprecation warning。
- Frontend：11 files、46 tests passed。
- Frontend production build：passed。
- 最终 exact 总门禁 `r18-current-final`：37 项中 30 passed、7 failed；上一轮为 28 passed、9 failed。

## 2. 执行前后对比

| 项目 | 执行前 | 执行后 |
|---|---:|---:|
| 主采样 canonical ready | 402/409，随后 408/409 | 409/409 |
| Native UI references | current 状态不完整/未统一发布 | 170/170 verified |
| Browser UI evidence | current matrix 下不完整 | 170/170 passed，0 issue |
| UI region contract | 16 个旧状态 ID | 170 个 current 状态 ID，0 issue |
| UI pixel gate | 被旧 region manifest 阻断 | region gate 通过；真实结果 0/170 |
| 主候选生成 | schema 变更后一度 1/40 | 40/40 generated |
| 主效果 parity | 无法形成完整 current 结果 | 35/40 passed，5 failed |
| Bokeh 参数 | 虚假 `radius` | 真实 `bokeh_shape` 六枚举 |
| Bokeh 导出尺寸 | 843×1440/1080×1440 | 1080×1845 |
| Bokeh 单次重采样 | 49.2 秒 | 23.1 秒 |
| exact 历史复用 | 旧 semantic key 导致 0 条命中 | 58 条 current 合法复用，2 条旧 radius 拒绝 |
| exact candidate | 旧队列 96/98，2 条 radius 失败 | current 133/133 generated |
| absolute-scope issues | 222 | 217 |
| exact 总门禁 | 28/37 passed | 30/37 passed |
| Python tests | 427 passed | 433 passed |

## 3. 最终确认的剩余遗漏

### P0：效果输出差异

主效果仍有 5 个失败：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays`。这五项已经排除候选缺失和尺寸错误，应按 Native reference 的指标差异修正算法，不应放宽阈值。

current exact 的 58 个可比用例中 8 个失败：两个 `face_ai`，以及 `structure_ai`、`depth_volume`、`blue_hour`、`landscape_enhancer`、`color_enhancer`、`complex_bleach`。其中与主效果失败重叠的能力优先级最高。

### P0：current exact Native evidence

- 75 条已有可执行 Native binding、但尚未产生 current canonical evidence。
- 73 个 matrix 锚点尚无 Native 控件绑定，不能执行。
- exact data-chain 因 75 个 missing state 和 current cohort run evidence 缺失而 blocked。

### P0：UI 像素对齐

- 结构证据已全部完成，但 170/170 像素比较失败。
- 最优状态 MAE 已接近 0.03，但 changed-pixel ratio 仍至少 0.2815，说明不是单个图标或抗锯齿问题，而是全局布局、字体、图像 viewport/裁切和组件样式仍有系统性差异。

### P1：交互执行

- 84/84 Native observations 缺失。
- 84/84 Browser formal executions 缺失。
- 现有 Browser 原始证据的 matrix fingerprint、viewport、DPR、locale、timezone 和 build hash 仍是旧合同；单独完成的 Bokeh shape 流程不能替代 84 条正式记录。

### P1：Native 持久化

- 缺少 `native-persistence-roundtrip-manifest.json`。
- 需要证明保存、关闭、重开后参数、图层顺序、可见性、混合模式、资源绑定及导出 hash 一致。

### P1：绝对范围

217 个问题包括：3 个能力缺 exact amount anchors、40 个能力缺第二输入 holdout、6 个参数未被 exact matrix 表示、84 个 Native interaction 缺失、84 个 Browser interaction 缺失。

剩余 3 个 amount anchors：`color_transfer`、`dodge_burn`、`lut_mapping`。  
剩余 6 个未表示参数：`crop_ai.crop_box/crop_ratio/flip_x/flip_y`、`deblur.face_enhancer_enabled/sharp_level`。

## 4. 下一步可执行顺序

1. 先采 75 条 current exact pending queue。每条先检查 state；ready 直接跳过。按 capability 分组并保持单次导入，使用已优化导出和原图尺寸恢复。完成后重建 active cohort 和 run evidence。
2. 为 73 个 blocked anchor 实现通用 Native 参数执行器。输入直接使用 74 项 binding audit，支持 slider、toggle、enum、asset picker、geometry；每次必须写入、回读并记录 control identifier/value space。
3. 修复 5 个主效果算法。顺序建议：`face_ai` → `depth_volume` → `blue_hour` → `sky_replace` → `sunrays`；每项同时跑主 case、已有 exact anchors 和新增 holdout，防止只拟合单图。
4. 对 UI 做系统性基线归因：先对齐 viewport/canvas crop、主图尺寸和全局字体，再处理导航、侧栏、工具面板和状态细节。每批修改后只重跑受影响 state，最后再跑 170 全量。
5. 基于 current 84-contract matrix 同步采集 Native 与 Browser interaction。先实现参数型通用 runner，再补 10 个工作流；禁止继续复用旧 fingerprint 的 formal evidence。
6. 完成 Native persistence roundtrip 7/7，并生成不可变 manifest。
7. 补 40 个 holdout 输入、3 个 amount anchors 和 6 个未表示参数，最后运行 37 项 exact gate。验收条件是 37/37 passed、absolute-scope issue_count=0，且 Luminar 最终 `reset-all-edits-status.enabled=false`。

## 5. 关键证据

- 主采样：`test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-evidence-r18-final.json`
- current UI Browser：`test_data/outputs/luminar-1.28.0-23071/diagnostics/ui-browser-execution.json`
- current UI pixel：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r18-current-final/ui-parity.json`
- current exact diff：`test_data/outputs/luminar-1.28.0-23071/diagnostics/exact-semantic-diff-r18-current.json`
- current exact cohort：`test_data/outputs/luminar-1.28.0-23071/diagnostics/sampling-queue-exact-incremental.json`
- current exact parity：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r18-current-final/exact-incremental-parity.json`
- absolute scope：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r18-current-final/absolute-scope-coverage.json`
- 最终 37 gates：`test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r18-current-final.json`

