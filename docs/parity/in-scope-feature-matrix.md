# Luminar Neo 本地核心范围覆盖矩阵（R11）

更新时间：2026-08-29  
参考应用：Luminar Neo `1.28.0 (23071)`  
机器可读报告：`test_data/outputs/luminar-1.28.0-23071/diagnostics/absolute-scope-coverage-r11-p0.json`

## 1. 口径

本矩阵只覆盖免费、本地、可执行的照片编辑、目录、预设、图层、遮罩、多图工作流与导出。
付费内容、商店、账户、云服务、教程、帮助、推广和授权购买流程不在范围内。

每个工具的最终准出条件是：主用例存在；连续 `amount` 至少有三个 exact 锚点；canonical
以外至少有两个不同 source hash 的 holdout；参数 schema 中每个参数都有用例；Native 与 Browser
关键交互都有正式证据。未满足的单元格是采样/合同 worklist，不能被当前“功能可运行”替代。

## 2. 当前效果能力矩阵

| capability | 已覆盖参数 | amount 锚点 | 不同输入 | 当前缺口 |
|---|---|---:|---:|---|
| `ai_enhance` | amount, opacity | 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `blue_hour` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `blur` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `bokeh_ai` | amount, opacity, radius | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `bw_channels` | amount, opacity | -1, 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `clone` | amount, opacity, strokes | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `color_adjustments` | amount, opacity | -1, 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `color_enhancer` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `color_toning` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `color_transfer` | amount, opacity, asset_id | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `complex_bleach` | amount, opacity | 0, 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `crop_ai` | amount, opacity | 0.4 | 1 | 缺 crop/rotation/flip 参数、exact 锚点和 2 个 holdout |
| `deblur` | amount, opacity | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `default_effects` | amount, opacity | -1, 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `denoise` | amount, denoise_level, opacity | 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `denoise_laplacian` | amount, opacity | 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `depth_volume` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout；现有 exact 失败 |
| `details` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `dodge_burn` | amount, opacity, strokes | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `erase` | amount, opacity, strokes | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `face_ai` | amount, opacity | 0, 0.4, 0.5, 1 | 2 | 缺 1 个 holdout；现有 exact 失败 |
| `face_enhancer` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `fade` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `fog` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `glow_orton` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `grain` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `high_key` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `landscape_enhancer` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout；full-range exact 失败 |
| `lut_mapping` | amount, opacity, asset_id | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout |
| `magic_lights` | amount, opacity | 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `new_neon_light` | amount, opacity, strokes, spread/atmosphere/hue/whiteness | 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `pro_contrast` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `radiance` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `skin_smooth` | amount, opacity | 0.4, 1 | 2 | 缺 exact 锚点和 1 个 holdout |
| `sky_replace` | amount, opacity, asset_id, sky geometry/color/edge/relight | 0.4 | 1 | 缺 exact 锚点和 2 个 holdout；现有 exact 失败 |
| `slim_people` | amount, opacity | -1, 0, 0.4, 1 | 2 | 缺 1 个 holdout |
| `structure_ai` | amount, opacity | -1, 0, 0.4, 1 | 1 | 缺 2 个 holdout；full-range exact 失败 |
| `sunrays` | amount, opacity | 0, 0.4, 1 | 2 | 缺 1 个 holdout；现有 exact 失败 |
| `vignette` | amount, opacity | -1, 0, 0.4, 1 | 1 | 缺 2 个 holdout |
| `water_enhancer` | amount, opacity | 0, 0.4, 1 | 1 | 缺 2 个 holdout |

## 3. UI 与交互覆盖

- UI 配置、Native reference manifest 和 Browser execution manifest 的状态集合均为 16 个；这只证明
  结构完整，旧 frontend build 的截图不能证明当前 build 像素通过。
- Native 正式证据为 9/10；缺 `preset-import-preview-apply`。现有
  `preset-preview-apply` 仅证明内置预设，不得冒充导入集合。
- Browser 正式证据为 8/10；缺 `preset-import-preview-apply` 和
  `multi-image-three-workflows`，且现有环境不满足 DPR2/物理 viewport 合同。
- 当前 clean fixture 浏览器功能实测已证明：46 个唯一照片、目录双击进入编辑器、更多面板只保留三类
  本地合并工作流；该实测不是正式像素证据。

## 4. 模型与数据持久化

- 22/22 活动模型结构与 model-specific contract 通过，0 pending；候选调用审计 18/18 通过，
  覆盖 16 个实际调用模型。
- `luminar_effect_parity` 仍是独立维度；模型 contract 通过不等于 Luminar 像素效果通过。
- catalog 继续只使用 Native SQLite；禁止 JSON catalog、JSON/SQLite 双写、旧 schema fallback。

## 5. 当前严格结论

范围门禁为 blocked，共 59 个缺口：10 个工具缺完整 exact amount 锚点，40 个工具缺足够 holdout，
裁切缺 6 个几何参数用例，Native 缺 1 个交互证据，Browser 缺 2 个交互证据。只有这些缺口连同
现有像素失败全部归零，且相同指纹连续两轮 exact required failure 为 0，才允许在本文限定范围内
声明绝对对齐。
