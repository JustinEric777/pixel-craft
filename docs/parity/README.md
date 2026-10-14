# Luminar Neo 当前对齐资料

> 仓库当前活动配置已切换到 Luminar Neo `1.28.1 (23487)` 中文版。R20 的独立 profile、矩阵和诊断根已建立，但 Native screenshot、AX、preview、export 和 observation 尚未完成重采；旧 1.28.0 证据仅作历史只读参考，禁止混入 1.28.1 准出。

## 当前入口

- [R20 执行报告、前后对比与下一步](luminar-neo-r20-execution-report-2026-09-17.md)
- [R20 Luminar Neo 1.28.1 核心完全对齐可执行优化计划](luminar-neo-1.28.1-core-alignment-plan-r20.md)
- [R19 执行报告、前后对比与下一步](luminar-neo-r19-execution-report-2026-09-17.md)
- [R19 当前代码完全对齐可执行优化计划](luminar-neo-absolute-alignment-plan-r19-current.md)
- [R18 Current-only 绝对对齐可执行优化计划](absolute-parity-optimization-plan-r18-current-only.md)
- [R17 Current-only 执行报告、遗漏审计与下一轮计划](absolute-parity-execution-report-r17-current-only-2026-09-01.md)
- [核心 UI 状态矩阵说明](ui-state-matrix.md)
- [参考捕获协议](reference-capture-protocol.md)
- [自动化采样说明](automated-sampling.md)
- [模型契约](model-contracts.md)
- [验证集说明](validation-set.md)
- [范围矩阵](in-scope-feature-matrix.md)

## 唯一活动基线

| 项目 | 入口 |
|---|---|
| Reference profile | `configs/reference.yaml` |
| UI matrix | `configs/parity/core-ui-state-matrix.json` |
| Interaction matrix | `configs/parity/core-interaction-matrix.json` |
| Parameter schema | `configs/capabilities/parameter-schema.json` |
| Native capture environment | `configs/parity/native-capture-environment.json` |
| Reference cases | `test_data/parity/references/luminar-1.28.1-23487/cases.json` |
| UI reference manifest | `test_data/outputs/luminar-1.28.1-23487/ui/reference-manifest.json`（待 Native 重采） |
| Diagnostics | `test_data/outputs/luminar-1.28.1-23487/diagnostics/` |

当前矩阵规模为 170 个 UI 状态、84 条交互契约和 40 个可见核心能力；当前 `configs/model.yaml` 注册 22 个 active model。当前完成度必须从 R18 sampling 报告及最新 diagnostics 读取，不能用旧的 210 UI、124 interaction 或仅 10 条 workflow 子集代表完整范围。

## Current-only 证据规则

1. UI evidence 必须绑定 current `matrix_state_id` 和 UI matrix fingerprint。
2. Interaction evidence 必须绑定 current contract ID 和 interaction matrix fingerprint。
3. Native evidence 必须证明固定应用窗口或声明的比较区域、专用显示、隔离输入、版本/build、fixture 和 artifact hashes；OS-owned surface 使用 semantic 证据。
4. Browser evidence 必须绑定一条有效 Native observation，并保存 build、DOM、AX、trace、log 与截图。
5. Native persistence 必须由 Luminar 重开验证；禁止推测式 History 写入。
6. `runtime-ready`、单元测试通过或旧截图都不能替代 `parity-passed`。

## 常用命令

```bash
.venv/bin/python scripts/validate_sampling_queue_captures.py
.venv/bin/python scripts/validate_absolute_scope_coverage.py
.venv/bin/python scripts/run_quality_gates.py --level exact \
  --reference-id luminar-neo-macos-1.28.1-23487 \
  --run-id <new-current-run-id>
```

R20 exact gate 共 37 项，其中 36 项属于核心必需门禁，Native persistence 是独立 optional diagnostic。新矩阵把 170 个 UI 状态拆为 169 个 app-owned pixel state 和 1 个 OS-owned semantic state；旧 UI evidence 因版本与 fingerprint 变化已按规则失效。在 1.28.1 效果输出、UI、84 interaction 和 exact/holdout 证据缺口关闭前，不得声明与 Luminar Neo 完全对齐。
