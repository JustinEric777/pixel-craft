# Luminar Neo 1.28.1 R20 执行报告、前后对比与下一步

> 执行日期：2026-09-17  
> 目标参考：Luminar Neo macOS `1.28.1 (23487)`，`zh-Hans`  
> 最终 exact run：`r20-final-latest-2026-09-17`  
> 当前 release fingerprint：`16c3dd28bcad1bea528594d97acb29007a5df258d328028a8d1e99d54673f648`（blocked）

## 1. 执行结论

R20 已完成版本迁移、范围重建、安装盘点、模型与素材核验、质量门禁修复，以及 Browser UI/交互原始证据采集；代码回归全部通过。**当前仍不能声明在效果、UI、交互层面与 Luminar Neo 完全对齐**：执行环境无法启动 Luminar Neo 进程，1.28.1 的 Native preview/export、UI manifest、AX 和 interaction observation 均未生成。所有正式 builder 和 gate 均保持 fail-closed，没有复用 1.28.0 证据或伪造通过状态。

最终 exact 门禁为 `23/36 required passed`，另有 1 项 optional persistence 失败；总计 `23 passed / 14 failed / 37`。13 个 required failure 主要是同一 Native 证据缺口及其数据链级联，而非 13 个互不相关的代码回归。

## 2. 分阶段执行结果

| 工作包 | 状态 | 可验证结果 |
|---|---|---|
| WP0 范围与门禁 | 完成 | 36 required + 1 optional；persistence 不再阻塞核心范围 |
| WP1 唯一真相源 | 完成 | active reference 切换到 1.28.1；cases、matrix、captures、UI、observations、diagnostics 独立分根 |
| WP2 inventory/binding/canary | 部分完成 | 版本与 inventory 完成；Native runner dry-run 可用；实机 canary 被进程不可用阻塞 |
| WP3 全量重采 | 部分完成 | 409 条 Native queue 已建立但均为 pending；Browser UI 170/170、Browser interaction 84/84 原始采集完成 |
| WP4 效果收敛 | 阻塞 | 缺少 1.28.1 Native 输出，禁止调算法或阈值 |
| WP5 UI 参考系统 | 部分完成 | 170 状态矩阵和 Browser DOM/AX/截图齐全；Native reference manifest 缺失 |
| WP6 UI 视觉收敛 | 阻塞 | 无同版本 Native screenshot，无法计算可信 pixel parity |
| WP7 交互闭环 | 部分完成 | Browser 84/84 原始 trace 完成；Native observation 0/84，正式 execution 为 0/84 |
| WP8 holdout/重复性 | 阻塞 | 依赖 Native 输出与正式执行证据 |
| WP9 最终发布 | 阻塞 | release fingerprint 缺两类 Native 根；未满足两次独立全绿 exact run |

## 3. 本轮落地内容

- 新建并激活 `luminar-neo-macos-1.28.1-23487` profile；旧 1.28.0 profile 仅作历史只读参考。
- 盘点本地安装：26 个模型变体/52 个 XML、BIN 文件，22 个 active logical model；52/52 源文件 hash 精确匹配，wrapper、consumer 和 model-specific contract 均已映射。
- 盘点 22 个预设集合、123 个可见预设、35 个天空素材、38 个免费叠加素材；预设图标 123/123、分类 22/22，sky/LUT/overlay 素材校验均通过。
- 重建 170 个 UI 状态（169 pixel + 1 OS semantic）、84 条交互契约、206 个 exact case、170 条合法 exact incremental queue；无重复或非法 case。
- 重建 409 条 Native sampling queue：40 effect、38 overlay、123 preset、35 sky、170 UI、3 workflow。
- 修复质量门禁依赖顺序、动态 reference root、可选 persistence 语义、模型 source map 和多处 1.28.0 硬编码；将 `frontend/scripts` 纳入 release source fingerprint，保证采集器变化会使证据失效。
- 强化 Chrome 采集：进程退出拒绝 pending call、唯一导航 URL、文件路径解析、恢复校验、图片 decode 等待和可访问名称点击。本轮发现并修复纯 `aria-label` 图标按钮无法点击的问题。
- Browser UI 产物为 170 个唯一 ID、680 个原始文件和 170 个候选截图；零缺失、零错误尺寸，全部为 `2880×1800`、runner `1.1.0`。目录、编辑和天空面板抽检无黑图或未解码素材。
- Browser interaction 原始证据为 84/84，每条均保存 screenshot、DOM、AX、execution/network/console trace；正式 builder 因 Native observation 缺失而拒绝发布。

## 4. 执行前后对比

| 指标 | R20 执行前 | R20 执行后 | 说明 |
|---|---:|---:|---|
| 活动参考 | 1.28.0 (23071) | 1.28.1 (23487) | 新证据根完全隔离 |
| 模型安装核验 | 旧版/口径不一致 | 26 变体、52/52 文件、22 logical | source/wrapper/contract 全链通过 |
| UI Browser 原始证据 | 0/170 current | 170/170 | 尚未绑定 Native manifest，不等于 UI parity |
| Interaction Browser 原始证据 | 0/84 current | 84/84 | 尚未绑定 Native observation，不等于交互 parity |
| Native sampling queue | 未建立 1.28.1 队列 | 409/409 明确 pending | 缺口可执行且不再隐式继承 |
| 正式 Native UI | 0/170 | 0/170 | 执行环境阻塞，无虚假增长 |
| 正式 Native interaction | 0/84 | 0/84 | dry-run/Browser trace 不能替代 Native 实测 |
| 主效果 | 旧版 35/40 | 1.28.1 为 0/40 已取证 | 迁移后主动失效，待重采 |
| exact gate | R19 29/37 | 23/36 required；1 optional failed | 下降来自同版本证据清零；首轮 20/37，修复后净增 3 |
| 后端测试 | 440 passed | 443 passed | 1 条第三方弃用警告 |
| 前端测试/构建 | 46 passed / pass | 46 passed / pass | 无回归 |

最终 required failures：`release-fingerprint`、`absolute-scope-coverage`、`overlay-e2e`、`multi-image`、`sampling-data-chain`、`exact-incremental-data-chain`、`sampling-queue-evidence`、`luminar-reference-captures`、`output-parity`、`exact-incremental-parity`、`ui-execution-evidence`、`ui-parity`、`interaction-execution`。Optional failure：`native-persistence-roundtrip`。

## 5. 阻塞与遗漏审计

Native canary 两次停止于：`native-preflight-failed: Luminar accessibility activate failed: process is not running`。直接启动应用后仍无法在当前执行上下文获得可访问进程。因此以下项目是明确的未完成项：

1. 409 条 Native queue 的 preview/export/UI/workflow 采集全部 pending；效果 40/40 尚无 1.28.1 基准。
2. 170 个 Native UI screenshot/AX、84 个 Native interaction observation 和 7 类 optional persistence roundtrip 均缺失。
3. `configs/parity/native-parameter-bindings.json` 与 `ui-regions.json` 仍保留已验证的旧版事实，必须在新 Native evidence 后重建，不能机械改版本号。
4. 效果参数校准、UI pixel comparator、84 条正式 Browser execution、holdout、重复性和两次发布门禁均依赖上述 Native 输入。
5. 当前 fingerprint 唯一缺失根为 `observations/interactions` 与 `ui/reference-manifest.json`；状态保持 blocked 是正确结果。

非遗漏项：`AGENTS.md` 在执行前已存在，按要求未覆盖或修改；旧 1.28.0 参考保留用于审计；Native persistence 已明确为 optional，不再被误算为核心发布范围。

## 6. 立即下一步：关闭 Native 证据链

1. 在真实登录的 macOS GUI 会话中启动冻结的 1.28.1 副本，授予 Terminal/Python 辅助功能与屏幕录制权限；锁定自动更新、显示缩放、色彩配置、语言和窗口几何。
2. 先执行 6 个 Native canary：slider、menu、asset picker、stroke、crop、multi-image workflow。每个必须验证 before/after、undo/redo/reset、preview 与 export hash。
3. Canary 全绿后顺序执行 409 条 Native queue、170 个 UI reference、84 个 interaction observation；失败必须可恢复且不得跳过。
4. 重建 Native binding、UI regions、reference manifest，再发布正式 Browser UI/interaction execution。要求所有证据绑定相同 reference ID、matrix fingerprint、fixture hash 和环境指纹。
5. 先按 `depth → sky/sunrays → color → face → detail` 校准效果，再按 shell geometry → 字体/图标 → 共享控件 → 单工具状态收敛 UI；禁止放宽阈值掩盖误差。
6. 为 40 个能力各补至少两个 holdout，验证重复性和 Native 自身方差；随后执行两次独立 required `36/36` exact run，fingerprint 必须一致。

## 7. 真正完全对齐后的建议

完成效果、UI、交互闭环后，建议暂缓扩展功能，依次进入：

1. **发布固化**：签名 golden evidence，锁定模型、素材、字体和依赖，产出可复现安装包与 SBOM。
2. **性能基线**：记录冷启动、首帧、warm preview、export、批处理、峰值内存和模型 cache 的 p50/p95；任何优化都重跑 parity。
3. **可靠性与恢复**：覆盖长会话、异常退出、磁盘不足、损坏工程、模型加载失败、取消与恢复、并发导出。
4. **盲测与设备矩阵**：扩大非 canonical 图像集，并验证不同 Apple Silicon、系统版本、显示缩放和色彩配置。
5. **版本差分认证**：固定执行 inventory → canary → affected-scope recapture → full gate，禁止小版本自动继承旧 evidence。
6. **最后扩展范围**：再评估更多工具、工程互操作、平台和云能力；每次扩展先更新 scope、矩阵与准出门禁。

## 8. 证据入口

- [R20 可执行计划](luminar-neo-1.28.1-core-alignment-plan-r20.md)
- `test_data/outputs/luminar-1.28.1-23487/diagnostics/runs/r20-final-latest-2026-09-17/quality-gates-exact.json`
- `test_data/outputs/luminar-1.28.1-23487/diagnostics/ui-capture-raw/capture-run.json`
- `test_data/outputs/luminar-1.28.1-23487/diagnostics/interaction-browser-raw.json`
- `test_data/outputs/luminar-1.28.1-23487/diagnostics/release-fingerprint-r20-current.json`
- `test_data/outputs/luminar-1.28.1-23487/inventory/install-manifest.json`
