# Luminar Neo R19 执行报告、前后对比与下一步

> 执行日期：2026-09-17  
> 冻结参考：Luminar Neo macOS `1.28.0 (23071)`，`zh-Hans`  
> 最终代码预检：`r19-final-preflight`  
> Release fingerprint：`ecca34ff4295a3d30f6eb587b369e1164467967968d79f9a2f218d4a645f8ce2`

## 1. 执行结论

R19 已完成验收模型、参数域、Native 参数执行基础设施、UI 比较口径和工程回归的首轮落地，但**尚未达到效果、UI、交互完全对齐**。最终 exact 门禁为 `29/37 passed`、8 个 required gate 失败；主效果仍为 `35/40`，exact cohort 仍有 8 failed、75 pending，Native interaction 正式证据仍为 `0/84`。

执行期间本机 Luminar 从冻结的 `1.28.0 (23071)` 更新为 `1.28.1 (23487)`。采集器按 fail-closed 规则停止写入 1.28.0 证据，避免跨版本污染。因此 WP3、WP4、WP5 视觉收敛、WP6 和 WP7 不能被诚实标记为完成。

## 2. 已执行修改

### 2.1 范围与验收语义

- UI matrix 增加 `surface_owner` 和 `comparison_mode`；169 个应用自有状态走 pixel comparator，macOS Save Panel 走 semantic interaction gate。
- UI region manifest 重建为 169 条像素区域；reference manifest 仍保留全部 170 个状态。
- Release fingerprint 纳入 parameter schema、Native bindings、capture environment、UI regions，并自动输出 `170 UI / 84 interaction / 40 capability / 22 active model`，连续两次生成一致。

### 2.2 参数域与 exact queue

- 为 35 个 amount 控件加入能力级 Native 范围；仅 8 个真正 signed 工具保留负值锚点。
- exact matrix 仍为 206 个语义 case，`invalid=0`；带 Native binding 的 case 从 28 增至 106。
- 新增量 worklist 为 112 条，`duplicate=0`、`invalid=0`；剩余 36 条明确分为 17 条 missing contract 和 19 条 not automated。
- `native-negative-amount-unrepresentable` 已归零。

### 2.3 Native interaction runner

- 74 条参数契约已接入数据驱动 dispatcher；覆盖 slider、button、menu-choice、asset-picker、stroke、crop-box。
- 修复全屏进入顺序、真实指针滑杆输入、crop drag 字段不一致和 crop ratio 默认值假变更。
- 参数 contract 现在必须验证 before/after、undo、redo、reset，并实际导出 PNG 后才报告 `export-completed`。
- dry-run 为 `84/84 supported`；这只证明代码有执行路径，不等于 Native 实机 `84/84 passed`。

### 2.4 UI comparator 与工程质量

- OS-owned state 不再参与浏览器全屏像素分数，而是委托给 interaction execution。
- 多视口计数、semantic delegation 和 pixel-only region 均增加测试。
- Ruff 全通过；后端 `440 passed`；前端 `46 passed`；前端 production build 通过；`ai/model` 专项校验 0 条发现。

## 3. 执行前后对比

| 指标 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| UI 验收类型 | 170 个均隐式 pixel | 169 pixel + 1 semantic | 修正系统表面口径 |
| amount 负值锚点 | 34 | 8 | 仅保留真实 signed 控件 |
| exact Native binding records | 28 | 106 | 参数映射显著补齐 |
| exact diff | 58 existing / 75 added / 73 blocked | 58 existing / 112 worklist / 36 blocked | 伪阻塞归零，真实缺口显式化 |
| Native 参数 binding audit | 部分支持 | 74/74 supported | 静态与 dry-run 通过 |
| Native runner dry-run | 10 workflow | 84/84 supported | 执行入口补齐 |
| Native 正式交互证据 | 0/84 | 0/84 | 被版本不一致阻塞 |
| 主效果输出 | 35/40 | 35/40 | 尚未进入可信算法校准 |
| Exact cohort | 50 pass / 8 fail / 75 pending | 不变 | 需匹配版本 Native 重采样 |
| UI pixel gate | 0/170 | 0/169，1 semantic 尚未取证 | 比较口径正确，视觉未收敛 |
| Exact quality gates | 30/37 | 29/37 | 新 UI fingerprint 主动使旧证据失效，并非能力退化 |
| 后端测试 | 433 | 440 | 新增回归覆盖且全部通过 |

最终失败门禁：`absolute-scope-coverage`、`exact-incremental-data-chain`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`、`native-persistence-roundtrip`。

## 4. 遗漏审计

以下工作未完成，不能用 dry-run、静态 binding 或旧证据替代：

1. **版本决策**：冻结基线是 1.28.0，本机仅有 1.28.1。必须选择恢复 1.28.0，或正式迁移 reference ID 并全量重采。
2. **Exact 数据**：75 条缺少 Native state，另有 2 条 cohort run evidence 缺失；40 个能力均未达到每项两个 holdout。
3. **效果**：`face_ai`、`depth_volume`、`blue_hour`、`sky_replace`、`sunrays` 主 case 未通过；exact 另涉及 `structure_ai`、`landscape_enhancer`、`color_enhancer`、`complex_bleach`。
4. **UI**：旧 Native/browser manifest 与新 matrix fingerprint 不匹配；169 个 app-owned 状态仍需重新采集并做共享布局、字体、图标和画布几何收敛。
5. **交互**：Native 与 Browser 正式 execution 都需按新 fingerprint 重跑；runner 的 84/84 只是 dry-run 支持度。
6. **参数自动化**：36 个 exact case 仍缺 enum、stroke、crop 或契约级自动化，必须逐条关闭或从产品范围中正式移除。
7. **Persistence**：7 类 Native roundtrip manifest 不存在；需确认它是否属于“效果/UI/交互完全对齐”的发布范围。
8. **最终发布**：尚未满足两次独立 `37/37` exact run；当前仅完成一次最终 preflight，状态 blocked。

## 5. 版本分叉建议

对 1.28.1 的只读 inventory/delta 审计显示：26/26 共享模型 hash 相同，7 个工具组、41 个工具 ID 和 18 个天空参数 ID 均与 1.28.0 相同；1.28.1 本地包含 22 个预设集合、123 个预设、35 个天空纹理和 38 个免费叠加纹理。因此结构性迁移风险较低，但截图、AX、输出和交互证据仍必须全量重采。

如果目标是“与当前本地 Luminar Neo 对齐”，建议正式迁移到 `1.28.1 (23487)`，冻结自动更新后创建新 reference profile；如果目标是复用既有 1.28.0 证据，则必须先恢复完全一致的 1.28.0 应用。禁止把两版 evidence 合并。

## 6. 立即执行顺序

1. 冻结目标版本和应用副本，生成新的 reference ID/fingerprint。
2. 先跑 1 个 slider、1 个 menu、1 个 asset、1 个 stroke、1 个 crop 的 Native canary；验证真实导出、undo/redo/reset 后再放大到 84 条。
3. 重采 170 个 Native UI、84 个 Native interaction，再重跑 Browser UI/interaction，消除 stale fingerprint。
4. 执行 112 条合法 worklist，关闭 75 pending；并为 40 个能力各补两个 holdout。
5. 按 `depth → sky/sunrays → color → face → detail` 顺序修 5 个主效果和 exact 失败，不调整阈值掩盖误差。
6. 从 shell geometry、字体、图标和共享控件族开始收敛 169 个 app-owned UI 状态。
7. 对 persistence 做明确范围决策；保留则在隔离 catalog 上实现 7/7，移除则留下产品决策记录。
8. 完成后连续执行 `r19-final-a`、`r19-final-b`，要求相同 fingerprint 且全部 required gate 通过。

## 7. 真正完全对齐后的下一步

完成效果、UI、交互闭环后，不应立刻扩展功能范围。建议依次进入：

1. **发布固化**：签名 golden evidence、锁定模型/素材/字体/依赖、生成可复现安装包和 SBOM。
2. **性能与资源**：建立冷启动、首帧、warm preview、export、峰值内存和模型 cache 的 p50/p95 基线；优化后强制重跑输出 parity。
3. **可靠性**：长时间编辑、批量多图、异常退出恢复、磁盘不足、损坏项目、模型加载失败和取消操作测试。
4. **真实世界验证**：在 canonical 之外扩大盲测图集和设备矩阵，持续监测 Native 自身方差与候选漂移。
5. **版本差分认证**：把 Luminar 小版本升级变成 inventory → canary → affected-scope recapture → full gate 的标准流程，禁止自动沿用旧证据。
6. **范围扩展**：最后再评估工程互操作、更多工具、平台适配或付费/云能力；每次扩展先更新产品范围和门禁。

## 8. 证据入口

- R19 matrix/queue/fingerprint：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r19-preflight/`
- 最终 exact preflight：`test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/r19-final-preflight/quality-gates-exact.json`
- UI regions：`configs/parity/ui-regions.json`
- Native parameter audit：`configs/parity/native-parameter-bindings.json`
- R19 原计划：`docs/parity/luminar-neo-absolute-alignment-plan-r19-current.md`
