# Luminar Neo 1.28 核心绝对对齐执行报告（R14，2026-08-31）

## 结论

R14 已完成所有不依赖新 Native 隔离采样的实现、证据刷新和回归工作，但尚未达到“与本机 Luminar Neo
绝对对齐”。当前 release、source、model、validation 和 environment 指纹以本轮最终生成的
`diagnostics/release-fingerprint-r14-final.json` 为准，避免文档内容参与 source hash 后形成自引用。

阻塞项仍然是 UI pixel 0/16、当前 build 正式交互 5/10、主效果 35/40、Exact 61/69、scope 59、
worklist 94，以及缺少 Native persistence roundtrip manifest。P8 单轮 exact 和 P9 A/B 两轮按停止规则未运行。

## 本轮完成内容

1. 冻结 R14 基线，并确认 Luminar Neo `1.28.0 (23071)`、bundle id
   `com.skylum.luminarneo` 和 reference 分母没有漂移。
2. 完成隔离预检。系统没有可验证的独立虚拟显示和独立输入路由，因此没有调用 Computer Use 控制 Luminar，
   没有启动、聚焦或接管 Luminar，也没有触碰共享鼠标键盘。
3. 扩展 Browser DPR2 交互录制器，新增目录照片右键子菜单、目录文件夹菜单与滚动、裁切、对比缩放平移、
   导出文件和多图三工作流执行路径；所有断言都绑定 DOM、API 或文件哈希，不以固定 sleep 判定完成。
4. 修复导出文件名未传到后端 `Content-Disposition` 的缺陷。导出设置现在实际控制下载文件名，非法文件名字符
   在服务端统一替换，PNG 宽度和文件 SHA-256 已由真实下载文件回读。
5. 在全新一次性 workspace 上重录当前 frontend hash 的 UI 16 个状态。screenshot、DOM、AX、region、fixture、
   viewport、DPR 和 build hash 证据为 16/16；像素结果仍为 0/16，未降低阈值或修改 region。
6. 当前 build 已正式录制并验证 5 个 Browser 合同：目录照片、目录文件夹、裁切、导出、多图三工作流。
   内置隔离浏览器另行实测 200% 平移得到 `panX=55`、`panY=30`，证明产品平移有效；无头录制器仍不能稳定
   生成非零 pan，因此 compare 合同没有被写成正式 passed。
7. 新增只读 `capture_native_persistence_delta.py`，可比较两个冻结 snapshot 的文件、SHA-256、SQLite schema、
   table row count 和新增/删除 row hash；SQLite 使用 `mode=ro&immutable=1`，不写 Native 数据。
8. 新增 fail-closed `native-persistence-roundtrip`，并注册为第 37 个 exact required gate。缺少 Native manifest
   时明确 blocked；没有建立猜测 schema、JSON/SQLite 双写、旧 reader 或 runtime migration。
9. 完成模型和全量回归：模型模块 validator 0 阻塞，model contract 22/22，active invocation 18/18，
   Python 392/392，前端 43/43，ruff 和 production build 全部通过。

## 执行前后对比

| 指标 | R14 执行前 | R14 当前 | 说明 |
|---|---:|---:|---|
| exact gate 分母 | 36 | 37 | 新增 Native persistence required gate |
| 主效果 | 35/40 | 35/40 | 本轮无可用新 Native canonical effect 样本，不做无依据校准 |
| Exact 效果 | 61/69 | 61/69 | 同上 |
| UI 正式证据 | 16/16 | 16/16 | 当前 frontend hash 已全量重录 |
| UI 像素 | 0/16 | 0/16 | 所有阈值和 region 保持不变 |
| Browser 正式交互 | 8/10（旧 build） | 5/10（当前 build） | 当前 build 重新从空目录录制；不拼接旧 hash |
| 模型 contract | 22/22 | 22/22 | 0 pending |
| active model invocation | 18/18 | 18/18 | 真实调用审计通过 |
| scope issues | 59 | 59 | Native/UI/effect 阻塞尚未消除 |
| worklist | 95 | 94 | 已关闭一个可追踪责任项 |
| Python tests | 旧基线 | 392/392 | 全量通过 |
| Frontend tests | 旧基线 | 43/43 | 全量通过 |

Browser 的 8/10 → 5/10 不是功能回归，而是证据口径收紧：旧 build 的记录没有和当前 frontend hash 混合。
当前 5 项均为重新录制，另外 5 项保持 missing/blocked。

## 当前明确遗漏

1. UI 16 个状态全部未过 pixel gate。结构性优先级仍是 export dialog、catalog、multi-image 和
   multi-image-complete；低 MAE 的 edit/info/collapsed 应从字体、图标和 1–2 px 几何入手。
2. Browser 缺 `photo-switch-history`、`preset-import-preview-apply`、`layer-lifecycle`、`mask-lifecycle` 和
   `compare-zoom-pan` 的正式 current-build 证据；preset 同时缺真实可信 `.lnpc` Native observation。
3. 主效果仍有 5 个失败，Exact 仍有 8 个失败。缺少新的隔离全屏 Native canonical 输出时不能继续盲调。
4. Native persistence 缺 project/edit-history/layer/mask/workflow/preset/preview-export 七类单变量 delta 和 restart
   roundtrip，故第 37 个 gate 按设计 blocked。
5. 仍未证明独立虚拟显示与独立输入路由。Computer Use 不能单独证明隔离，因此 Native 新采样未执行。
6. 单轮 exact 37/37 和同指纹 A/B 两轮没有准入条件，不能执行或声明通过。

## 下一步唯一合理顺序

1. 在独立 macOS VM，或独立登录会话加独立远程桌面中证明 display/input isolation；Luminar 必须全屏，
   采集前后记录 bounds、scale、版本、locale、workspace 和 screenshot hash。
2. 用真实 `.lnpc` 和单变量操作补齐 Native 10/10 observation，随后在冻结 frontend hash 上补齐 Browser 5 项；
   compare 录制器需改用与内置浏览器等价的可信拖动输入，不接受手写 passed。
3. 先处理 UI 结构性四项，再处理共享字体/图标/几何根因；每次修改后从全新 fixture 重录 16/16。
4. 只用新增 Native canonical/holdout 证据校准主效果 5 项和 Exact 8 项，保持原 MAE/SSIM 阈值。
5. 用只读 delta 工具建立七类 Native persistence 字段映射；证据完整后一次性切换 active repository，并删除
   JSON primary 和重复 projection，不保留历史兼容层。
6. scope、worklist、UI、interaction、effect 和第 37 个 gate 全部为零失败后，运行单轮 exact 37/37；只有单轮
   通过才冻结指纹并运行 A/B 两轮。

## 主要证据

- `diagnostics/ui-execution-evidence-r14-final.json`：UI 执行证据 16/16 passed。
- `diagnostics/ui-parity-r14-final.json`：UI pixel 0/16、gate blocked。
- `diagnostics/interaction-execution-r14-final.json`：当前 build 5/10、gate blocked。
- `diagnostics/native-persistence-roundtrip-r14.json`：第 37 个 gate blocked，缺 manifest。
- `diagnostics/scope-coverage-r14-final.json`：59 个 scope issue。
- `diagnostics/absolute-alignment-worklist-r14-final.json`：94 项 worklist。
- `diagnostics/release-fingerprint-r14-final.json`：当前 release/source/model/validation/environment 指纹。
