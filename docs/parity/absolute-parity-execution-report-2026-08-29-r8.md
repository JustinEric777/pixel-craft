# Luminar Neo 1.28 严格对齐执行报告：R8

## 1. 当前结论

R8 已完成当前源码下的独立 exact 预检。结果为 `31/35`，required failure 仍有
4 个：主效果、扩展效果、UI 像素和正式交互证据。因此当前代码仍不能声明与本机
Luminar Neo `1.28.0 (23071)` 绝对对齐，也不能启动 release A/B 两轮。

本轮范围只包含免费、离线、可重复验证的本地核心能力。付费、升级、订阅、账号、
商店、教程、帮助、云生成和商业内容继续排除，不进入 required gate。

权威 run：

- run id：`alignment-execution-r8-20260829`；
- exact：`31/35`；
- source fingerprint：`19bc7187122cedd677161afc87444d5fba8837b809bce8d73e0d0798f1140ad4`；
- model fingerprint：`84eac62c7d459e64b37fecf20bd65b19becac514786d69ba81ada3e337228237`；
- validation fingerprint：`04b22b3f27cade19cfa3003405c7bacb3cd7d639541342d4f53ee9fc6f47710f`；
- environment fingerprint：`d59fdf4f82c9ffc2adcb409f9dbb2dd73cab69f2c4c5f0ac6ffcf94132a391d8`；
- release fingerprint：`a68dea90c1f19543cdc436b0c45ff598ece5846f3ea30cdab926418d35fe0c38`。

## 2. 执行前后对比

| 域 | 本轮起点 | R8 | 变化 |
|---|---:|---:|---:|
| Exact required gate | 30/34 | 31/35 | 新增真实 Native catalog schema required gate 并通过；产品失败仍为 4 项 |
| 活动模型合同 | 22/22 | 22/22 | 保持全部验证，pending 0 |
| 主效果 | 33/40 | 34/40 | Magic Lights 关闭 1 个失败 |
| 扩展 Exact | 41/69 | 51/69 | 新增 10 个通过，失败由 28 降至 18 |
| UI current-build execution | 16/16 | 16/16 | 保持通过 |
| UI pixel | 0/16 | 0/16 | 没有用功能通过替代像素结论 |
| Native 交互 | 8/10 | 9/10 | 多图三工作流已形成 source-reset 后的正式 Native observation |
| Browser 正式 current-build | 旧 8 条 stale/viewport mismatch | multi-image 1/1 current-build partial | 多图已按 2880×1800 完成；旧 8 条仍须全量重录，不能直接改写 hash |
| Native catalog schema | 未取得真实 schema | schema 155、29 objects、26 tables 精确通过 | 已删除“私有 schema 未知”的旧结论 |
| Python | 363 passed | 367 passed | 新增校准、catalog 和比较器回归测试 |
| Frontend | 41 passed | 41 passed | production build 通过 |

`35` 个 gate 中通过 `31` 个，失败项固定为：

1. `output-parity`；
2. `exact-incremental-parity`；
3. `ui-parity`；
4. `interaction-execution`。

## 3. 已完成的实现

### 3.1 真实 Native catalog schema 单轨

通过只读方式定位并检查了本机 Luminar catalog：

- `/Users/iknow/Works/luminarneo/未命名/未命名.luminarneo`；
- `/Users/iknow/Library/Group Containers/RTW788AXG3.com.skylum.luminarneo/Space/4413758/4413758.luminarneo`。

两者均为 SQLite `user_version=155`，结构为 29 个 schema objects、26 张表。项目实现已按
真实结构修正列顺序、外键、显式索引、两个 filter trigger、`last_synced_at` 初始行、
sentinel volume 和 `NotifyFilterRefUpdate` UDF。冻结结构 hash 为：

`7f754d62d041eda3cd0a04e0fef2471c0ebca0c454f0db13fb9647ea04817b79`

`luminar-catalog-schema` 已加入 required gate 并在 R8 通过。运行时只有 SQLite 单轨，
`compatibility_layers=[]`；没有 JSON catalog、双写、旧 schema fallback、自动升级或迁移兼容层。

### 3.2 主效果与扩展效果

本轮没有降低 `MAE <= 0.03`、`SSIM >= 0.98`、shape match 或 Grain statistical
阈值，也没有按 case id、文件名、reference hash 写运行时特判。

已关闭的扩展失败：

- Magic Lights：补充 Native 锚点支持的 effect-wide toe/color response；主效果和 zero/full
  exact 均通过；
- High Key：用 0.4/1.0 Native 锚点拟合单调逐通道 tone curve；
- Pro Contrast：保留 0.4 已验证响应，并补齐 0.4→1.0 的上段强度曲线；
- Color Adjustments：正负端点采用全局 RGB matrix，zero 保持 identity；
- Color Enhancer：正端点采用全局 RGB matrix，zero 保持 identity；
- Color Toning：Native 0.4 与 1.0 为像素等价 full response，按真实 anchor 饱和；
- Denoise：amount-only full endpoint 映射到已验证的 Native middle profile；显式
  low/middle/high profile 不变；
- Denoise Laplacian：0.4 smoke 与独立 noisy-image 1.0 锚点映射到同一 full response；
- Fade：以 zero/0.4/1.0 锚点替换旧的经验 warm blend。

Grain `amount=0` 的 comparator 也已修正：zero 是 identity contract，走 pixel-structural；
非零 Grain 仍使用原 statistical 阈值。该修正没有降低阈值，只避免把 Native 导出编码残差
误判为已应用颗粒。

### 3.3 多图交互

Native `multi-image-three-workflows` 已在每个分支前验证 source reset，并完成 HDR、Focus
Stacking、Panorama 的正式 observation。Browser 在全新隔离数据根上，以物理 viewport
`2880×1800` 重跑三条工作流：

- 只创建 3 个 workflow；
- 9 张输入的文件名、顺序和 SHA-256 全部持久化；
- 3 个 analysis 均为 `ready`；
- 3 个 workflow 均为 `exported`；
- 3 组 export SHA-256 均与 preview SHA-256 相同。

当前源码下的 Browser partial evidence 通过 `1/1`，不存在 viewport mismatch 或 stale build。
它不能与旧 8 条不同 build 的证据拼成 9/10，因此正式 interaction pointer 仍保持 blocked。

### 3.4 测试与构建

- `.venv/bin/ruff check .`：passed；
- `.venv/bin/pytest -q`：367 passed，1 个第三方 deprecation warning；
- `npm --prefix frontend test -- --run`：41 passed；
- `npm --prefix frontend run build`：passed。

## 4. 当前确切遗漏

### 4.1 主效果：34/40

| Capability | MAE | SSIM | 根因分类 |
|---|---:|---:|---|
| Face AI | 0.030175 | 0.984125 | 区域/肤色响应；MAE 刚超阈值 |
| Depth Volume | 0.069188 | 0.960300 | 当前深度方向和 Native 分层响应不一致 |
| Blue Hour | 0.039456 | 0.975336 | 缺 content-aware sky/foreground 冷暖映射 |
| Fog | 0.113488 | 0.903759 | 缺全局 atmospheric component、地平线和主体保护 |
| Sky Replace | 0.039682 | 0.973711 | mask、horizon、颜色匹配和融合仍不同 |
| Sunrays | 0.053714 | 0.956221 | 光源定位、遮挡、衰减和 bloom 结构不同 |

方向扫描已经证明 Face、Depth、Blue Hour、Fog 和 Sunrays 不能靠单一 amount 缩放过线；
继续改强度只会过拟合，必须补 full-screen Native 中间真值并重建结构算法。

### 4.2 扩展 Exact：51/69

仍有 18 个失败：

- Grain full；
- Default Effects positive/negative；
- Face AI 两个 full/mid anchor；
- Sunrays；
- Bokeh AI；
- Structure AI；
- AI Enhance；
- Vignette positive/negative；
- Depth Volume；
- Face Enhancer full；
- Blue Hour；
- Radiance；
- Landscape Enhancer；
- Fog；
- Slim People full。

这些失败包含两类：一类是主效果共享的结构根因；另一类出现 Native anchor 非单调或不同照片
响应不一致。后一类必须先补同图 zero/mid/full 和不同照片 holdout，不能用非单调 lookup 关闭。

### 4.3 UI：execution 16/16，pixel 0/16

UI screenshot、DOM、AX、步骤、DPR 2 和 frontend build hash 的执行证据全部通过，但 16 个
状态的像素门禁全部失败。尚未完成公共 shell、字体、panel 几何、canvas、颜色、图标、间距和
各状态内容的逐像素校准。

### 4.4 交互

- Native：9/10；只缺真实 `.lnpc` collection 的 preset import/preview/apply；
- Browser current-build：multi-image partial 1/1；其余旧 8 条必须在最终 frontend hash 下、
  `2880×1800` viewport 全量重录；
- 正式 combined gate 当前仍显示旧执行的 8/10，并正确报告 viewport mismatch、stale build、
  preset missing 和 multi-image missing；不能人工覆盖；
- 本机没有可靠的独立虚拟 macOS 显示器/鼠标。Computer Use 仍使用共享桌面；按用户要求，
  没有隔离能力时保持现状，不继续抢占外设。

真实 app 生成的 `.lnp` 单 preset 已保存，但 `.lnpc` 是 collection/package。测试的合成包已被
Luminar 拒绝，因此不能用 `.lnp` 或伪造 archive 替代 `.lnpc` 正式合同。

### 4.5 发布轮

required failure 仍为 4，故没有执行 release A/B。只有单轮 `35/35` 后才允许冻结完全相同的
source/model/validation/environment/reference fingerprint，执行两轮独立候选生成。

## 5. 下一步可执行顺序

1. 先补算法真值：仅在 Luminar 全屏、且不与用户外设冲突时，采集 Face、Depth、Blue Hour、
   Fog、Sky Replace、Sunrays 的同图 zero/mid/full、中间 mask/depth/horizon/light-source 证据；
   没有虚拟输入能力时保持 blocked。
2. 以不同照片 holdout 重建 6 个主效果；每关闭一个根因，立即跑目标用例和 40-case 主回归。
3. 复用主效果根因关闭扩展 18 项；对 Grain、Default、Bokeh、Vignette、Face Enhancer、
   Radiance、Landscape、Slim People 单独补一致的参数梯度，拒绝非单调特判。
4. 冻结 frontend 后按公共 shell→高 MAE 状态→其余状态的顺序校准 UI；每批重录全部 16 项，
   直到 UI pixel 16/16。
5. 取得真实、可由本机 Luminar 导入的 `.lnpc`，完成 Native preset observation；没有真实包时
   合同持续 blocked。
6. 在最终 frontend hash 下重录 Browser 10/10，统一使用 `2880×1800` 正式 viewport；不得复用
   旧截图或直接改写 build hash。
7. 单轮 exact 达到 35/35 后执行 release A/B；两轮 required failure 都为 0 且 fingerprint
   完全相同，才允许声明严格对齐。

## 6. 权威证据

- `test_data/outputs/luminar-1.28.0-23071/diagnostics/quality-gates-r8-20260829.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/runs/alignment-execution-r8-20260829/`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-execution-r5-multi-20260829.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-validation-r5-multi-20260829.json`；
- `test_data/outputs/luminar-1.28.0-23071/diagnostics/interaction-browser-evidence-current-20260829/multi-image-three-workflows/`；
- `test_data/outputs/luminar-1.28.0-23071/observations/interactions/multi-image-three-workflows/observation.json`；
- `scripts/validate_luminar_catalog_schema.py`；
- `storage/catalogs/luminar_sqlite.py`。
