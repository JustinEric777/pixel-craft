import { useMemo, useState } from "react";
import type { AssetRecord, Capability, Layer, LayerUpdate, MaskBrushSettings, MaskUpdate, Project, ToolGroup } from "../api";
import { AssetPicker } from "./AssetPicker";
import { Icon, type IconName } from "./Icon";
import { LayerInspector } from "./LayersPanel";
import { SkyControls, type SkySettings } from "./SkyControls";

export type CropSettings = {
  box: [number, number, number, number];
  ratio: "original" | "free" | "1:1" | "4:3" | "3:2" | "16:9";
  rotation: number;
  straighten: number;
  flipX: boolean;
  flipY: boolean;
};

export type BokehShape = "circle" | "filled_circle" | "oval" | "hexagon" | "heart" | "star";

type ToolPanelProps = {
  amount: number;
  assetId: string;
  skySettings: SkySettings;
  busy: boolean;
  groups: ToolGroup[];
  visuals: Record<string, { icon: string; ai_badge: boolean }>;
  items: Capability[];
  onAmountChange: (value: number) => void;
  onAmountCommit?: (value: number) => void;
  denoiseLevel?: "low" | "middle" | "high";
  onDenoiseLevelChange: (value: "low" | "middle" | "high") => void;
  denoiseSettings?: { luminosity: number; details: number; sharpness: number };
  onDenoiseSettingChange?: (key: "luminosity" | "details" | "sharpness", value: number) => void;
  sharpLevel?: "low" | "middle" | "high";
  sharpType?: "universal";
  sharpFaceEnhancer?: boolean;
  onSharpLevelChange?: (value: "low" | "middle" | "high") => void;
  onSharpFaceEnhancerChange?: (value: boolean) => void;
  onApply: () => void;
  onAssetChange: (value: string) => void;
  onSkySettingChange: (key: keyof SkySettings, value: number | boolean) => void;
  onSelect: (value: string) => void;
  project?: Project;
  selected: string;
  colorAssets: AssetRecord[];
  colorAssetId: string;
  onColorAssetChange: (value: string) => void;
  strokesCount: number;
  brushRadius: number;
  onBrushRadiusChange: (value: number) => void;
  onClearStrokes: () => void;
  bokehShape?: BokehShape;
  onBokehShapeChange?: (value: BokehShape) => void;
  neonSettings?: { spread: number; atmosphere: number; hue: number; whiteness: number };
  onNeonSettingChange?: (key: "spread" | "atmosphere" | "hue" | "whiteness", value: number) => void;
  lutAssets: AssetRecord[];
  lutAssetId: string;
  onLutAssetChange: (value: string) => void;
  skyAssets: AssetRecord[];
  selectedLayer?: Layer;
  projectId?: string;
  onDeleteMask?: (maskId: string) => void;
  onUpdateLayer?: (layerId: string, changes: LayerUpdate) => void;
  onUpdateMask?: (maskId: string, changes: MaskUpdate) => void;
  onUploadLayerMask?: (layerId: string, file: File) => void;
  cropSettings: CropSettings;
  onCropSettingsChange: (changes: Partial<CropSettings>) => void;
  straightenActive?: boolean;
  onStraightenActiveChange?: (active: boolean) => void;
  onExpandedChange?: (capabilityId?: string) => void;
  maskBrushActive?: boolean;
  maskBrushSettings?: MaskBrushSettings;
  onMaskBrushActiveChange?: (active: boolean) => void;
  onMaskBrushSettingsChange?: (settings: MaskBrushSettings) => void;
};

const CATALOG_WORKFLOW_CAPABILITIES = new Set([
  "hdr_merge",
  "focus_stacking",
  "panorama_stitching",
]);

const CAPABILITIES_WITHOUT_NATIVE_AMOUNT = new Set([
  "sky_replace",
  "crop_ai",
  "deblur",
  "erase",
  "clone",
]);

export function ToolPanel({
  amount,
  assetId,
  skySettings,
  busy,
  groups,
  visuals,
  items,
  onAmountChange,
  onAmountCommit,
  denoiseLevel,
  onDenoiseLevelChange,
  denoiseSettings = { luminosity: 1, details: 0.5, sharpness: 0.5 },
  onDenoiseSettingChange,
  sharpLevel = "middle",
  sharpType = "universal",
  sharpFaceEnhancer = false,
  onSharpLevelChange,
  onSharpFaceEnhancerChange,
  onApply,
  onAssetChange,
  onSkySettingChange,
  onSelect,
  project,
  selected,
  colorAssets,
  colorAssetId,
  onColorAssetChange,
  strokesCount,
  brushRadius,
  onBrushRadiusChange,
  onClearStrokes,
  bokehShape = "circle",
  onBokehShapeChange,
  neonSettings = { spread: 0.6, atmosphere: 0.05, hue: 270, whiteness: 0.3 },
  onNeonSettingChange,
  lutAssets,
  lutAssetId,
  onLutAssetChange,
  skyAssets,
  selectedLayer,
  projectId,
  onDeleteMask,
  onUpdateLayer,
  onUpdateMask,
  onUploadLayerMask,
  cropSettings,
  onCropSettingsChange,
  straightenActive = false,
  onStraightenActiveChange,
  onExpandedChange,
  maskBrushActive,
  maskBrushSettings,
  onMaskBrushActiveChange,
  onMaskBrushSettingsChange,
}: ToolPanelProps) {
  const [expandedCapability, setExpandedCapability] = useState<string>();
  const [blackWhiteConverted, setBlackWhiteConverted] = useState(false);
  const [blackWhiteMode, setBlackWhiteMode] = useState<"luminance" | "saturation">("luminance");
  const needsSkyAsset = selected === "sky_replace" || selected === "augmented_sky";
  const needsLutAsset = selected === "lut_mapping";
  const needsColorAsset = selected === "color_transfer";
  const needsBrush = selected === "erase" || selected === "dodge_burn" || selected === "clone" || selected === "new_neon_light";
  const isBlackWhite = selected === "bw_channels";
  const isDenoise = selected === "denoise";
  const isSupersharp = selected === "deblur";
  const isCrop = selected === "crop_ai";
  const isBokeh = selected === "bokeh_ai";
  const isNeon = selected === "new_neon_light";
  const hasAmount = !CAPABILITIES_WITHOUT_NATIVE_AMOUNT.has(selected);
  const effectiveDenoiseLevel = denoiseLevel ?? "middle";
  const selectedItem = items.find((item) => item.id === selected);
  const selectedStatus = selectedItem?.readiness?.status;
  const runnable = selectedStatus === "parity-passed" || selectedStatus === "runtime-ready";
  const canApply = Boolean(project) && !busy && runnable
    && (!needsSkyAsset || Boolean(assetId))
    && (!needsLutAsset || Boolean(lutAssetId))
    && (!needsColorAsset || Boolean(colorAssetId))
    && (!needsBrush || strokesCount > 0)
    && (!isBlackWhite || blackWhiteConverted)
    && (!isDenoise || Boolean(effectiveDenoiseLevel));
  const commitsAmountDirectly = canApply
    && !needsSkyAsset
    && !needsLutAsset
    && !needsColorAsset
    && !needsBrush
    && !isBlackWhite
    && !isDenoise
    && !isSupersharp
    && !isCrop;
  const groupedItems = useMemo(() => {
    return groups.map((group) => ({
      ...group,
      items: group.capabilities
        .map((capabilityId) => items.find((item) => item.id === capabilityId))
        .filter(
          (item): item is Capability =>
            item !== undefined && !CATALOG_WORKFLOW_CAPABILITIES.has(item.id),
        ),
    })).filter((section) => section.items.length);
  }, [groups, items]);

  function chooseCapability(item: Capability) {
    if (expandedCapability === item.id) {
      setExpandedCapability(undefined);
      onExpandedChange?.(undefined);
      return;
    }
    onSelect(item.id);
    if (item.id === "bw_channels") {
      setBlackWhiteConverted(false);
      setBlackWhiteMode("luminance");
    }
    setExpandedCapability(item.id);
    onExpandedChange?.(item.id);
  }

  const inlineInspector = selectedItem ? (
    <div className="tool-inline-inspector" aria-label={`${selectedItem.title}参数`}>
      {needsSkyAsset && <div data-parameter-id="asset_id"><AssetPicker assets={skyAssets} disabled={busy} selectedId={assetId} onChange={onAssetChange} /></div>}
      {needsLutAsset && <div data-parameter-id="asset_id"><AssetPicker assets={lutAssets} disabled={busy} label="内置情绪 LUT" preview={false} selectedId={lutAssetId} onChange={onLutAssetChange} /></div>}
      {needsColorAsset && <div data-parameter-id="asset_id"><AssetPicker assets={colorAssets} disabled={busy} label="颜色参考" selectedId={colorAssetId} onChange={onColorAssetChange} /></div>}
      {needsBrush && <div className="brush-controls" data-parameter-id="strokes">
        <p>{selected === "clone" ? "先点按取样位置，再点按目标位置；可重复添加。" : "直接在照片上拖动绘制处理区域。"}</p>
        <label htmlFor="brush-radius">画笔大小 <output>{Math.round(brushRadius * 200)}%</output></label>
        <input id="brush-radius" aria-label="画笔大小" type="range" min="0.01" max="0.15" step="0.005" value={brushRadius} disabled={busy} onChange={(event) => onBrushRadiusChange(Number(event.target.value))} />
        <button type="button" disabled={!strokesCount || busy} onClick={onClearStrokes}>清除笔触（{strokesCount}）</button>
      </div>}
      {needsSkyAsset && <SkyControls disabled={busy} settings={skySettings} onChange={onSkySettingChange} />}
      {isBlackWhite && <div className="black-white-conversion">
        <button
          className={blackWhiteConverted ? "converted" : ""}
          type="button"
          aria-pressed={blackWhiteConverted}
          disabled={busy}
          onClick={() => setBlackWhiteConverted(true)}
        >{blackWhiteConverted ? "已转换为黑白" : "转换为黑白"}</button>
        <div className="black-white-modes" role="tablist" aria-label="黑白通道模式">
          <button type="button" role="tab" aria-selected={blackWhiteMode === "luminance"} disabled={!blackWhiteConverted || busy} onClick={() => setBlackWhiteMode("luminance")}>亮度</button>
          <button type="button" role="tab" aria-selected={blackWhiteMode === "saturation"} disabled={!blackWhiteConverted || busy} onClick={() => setBlackWhiteMode("saturation")}>饱和度</button>
        </div>
      </div>}
      {isDenoise && <div className="denoise-levels" role="radiogroup" aria-label="降噪等级" data-parameter-id="denoise_level">
        <p>建议：对此图像使用 中等调整</p>
        {(["low", "middle", "high"] as const).map((level) => (
          <button
            type="button"
            role="radio"
            aria-checked={effectiveDenoiseLevel === level}
            disabled={busy}
            key={level}
            onClick={() => onDenoiseLevelChange(level)}
          >{{ low: "低", middle: "中等", high: "高" }[level]}</button>
        ))}
        {([
          ["luminosity", "光度降噪"],
          ["details", "详细信息"],
          ["sharpness", "锐度"],
        ] as const).map(([key, label]) => <label className="denoise-native-control" key={key}>{label} <output>{Math.round(denoiseSettings[key] * 100)}</output>
          <input aria-label={label} data-parameter-id={key} type="range" min="0" max="1" step="0.01" value={denoiseSettings[key]} disabled={busy} onChange={(event) => onDenoiseSettingChange?.(key, Number(event.target.value))} />
        </label>)}
      </div>}
      {isSupersharp && <div className="supersharp-controls">
        <button className="supersharp-type" type="button" disabled={busy} aria-label="超锐类型">{sharpType === "universal" ? "通用" : sharpType}</button>
        <div role="radiogroup" aria-label="超锐等级" data-parameter-id="sharp_level">
          {(["low", "middle", "high"] as const).map((level) => <button type="button" role="radio" aria-checked={sharpLevel === level} disabled={busy} key={level} onClick={() => onSharpLevelChange?.(level)}>{{ low: "低", middle: "中等", high: "高" }[level]}</button>)}
        </div>
        <label><input type="checkbox" data-parameter-id="face_enhancer_enabled" checked={sharpFaceEnhancer} disabled={busy} onChange={(event) => onSharpFaceEnhancerChange?.(event.target.checked)} />面部增强器<sup>AI</sup></label>
      </div>}
      {isCrop && <div className="crop-controls" data-parameter-id="crop_box">
        <label>比例：<select aria-label="裁切比例" data-parameter-id="crop_ratio" value={cropSettings.ratio} disabled={busy} onChange={(event) => onCropSettingsChange({ ratio: event.target.value as CropSettings["ratio"] })}>
          <option value="original">原始</option><option value="free">自由</option><option value="1:1">1:1</option><option value="4:3">4:3</option><option value="3:2">3:2</option><option value="16:9">16:9</option>
        </select></label>
        <button className="crop-compose" type="button" disabled={busy} onClick={() => onCropSettingsChange({ box: [0.06, 0.06, 0.94, 0.94] })}>构图 <sup>AI</sup></button>
        <div className="crop-straighten-control"><button type="button" className={straightenActive ? "selected" : ""} aria-pressed={straightenActive} disabled={busy} onClick={() => onStraightenActiveChange?.(!straightenActive)}>水平对齐</button></div>
        <span>旋转和翻转 <output aria-label="裁切旋转角度">{cropSettings.rotation.toFixed(0)}°</output></span>
        <div className="crop-transform-buttons">
          <button type="button" disabled={busy} aria-label="向左旋转" onClick={() => onCropSettingsChange({ rotation: cropSettings.rotation <= -90 ? 180 : cropSettings.rotation - 90 })}>↶</button>
          <button type="button" data-parameter-id="flip_x" className={cropSettings.flipX ? "selected" : ""} disabled={busy} aria-label="水平翻转" aria-pressed={cropSettings.flipX} onClick={() => onCropSettingsChange({ flipX: !cropSettings.flipX })}>◁▷</button>
          <button type="button" data-parameter-id="flip_y" className={cropSettings.flipY ? "selected" : ""} disabled={busy} aria-label="垂直翻转" aria-pressed={cropSettings.flipY} onClick={() => onCropSettingsChange({ flipY: !cropSettings.flipY })}>▽△</button>
        </div>
      </div>}
      {isBokeh && <div className="parameter-controls" aria-label="散景参数">
        <span>虚化形状调整</span>
        <div className="bokeh-shape-controls" role="radiogroup" aria-label="虚化形状" data-parameter-id="bokeh_shape">
          {([
            ["circle", "圆环", "○"],
            ["filled_circle", "实心圆", "●"],
            ["oval", "椭圆", "⬭"],
            ["hexagon", "六边形", "⬡"],
            ["heart", "心形", "♥"],
            ["star", "星形", "★"],
          ] as const).map(([value, label, glyph]) => <button
            aria-checked={bokehShape === value}
            aria-label={label}
            className={bokehShape === value ? "selected" : ""}
            disabled={busy}
            key={value}
            onClick={() => onBokehShapeChange?.(value)}
            role="radio"
            type="button"
          >{glyph}</button>)}
        </div>
      </div>}
      {isNeon && <div className="parameter-controls" aria-label="霓虹灯参数">
        {([
          ["spread", "扩散", 0, 1, 0.01],
          ["atmosphere", "氛围", 0, 1, 0.01],
          ["hue", "色相", 0, 360, 1],
          ["whiteness", "白度", 0, 1, 0.01],
        ] as const).map(([key, label, min, max, step]) => <label key={key}>{label} <output>{key === "hue" ? `${Math.round(neonSettings[key])}°` : Math.round(neonSettings[key] * 100)}</output>
          <input aria-label={label} data-parameter-id={`neon_${key}`} type="range" min={min} max={max} step={step} value={neonSettings[key]} disabled={busy} onChange={(event) => onNeonSettingChange?.(key, Number(event.target.value))} />
        </label>)}
      </div>}
      {hasAmount && <div className="control tool-global-controls">
        <>
          <label htmlFor="amount">{isBlackWhite ? (blackWhiteMode === "luminance" ? "红色亮度" : "红色饱和度") : "强度"} <output>{Math.round(amount * 100)}</output></label>
          <input
            id="amount"
            data-parameter-id="amount"
            aria-label={isBlackWhite ? (blackWhiteMode === "luminance" ? "红色亮度" : "红色饱和度") : "强度"}
            type="range"
            min="-1"
            max="1"
            step="0.01"
            value={amount}
            disabled={busy || (isBlackWhite && !blackWhiteConverted)}
            onChange={(event) => onAmountChange(Number(event.target.value))}
            onPointerUp={(event) => {
              if (commitsAmountDirectly) onAmountCommit?.(Number(event.currentTarget.value));
            }}
            onKeyUp={(event) => {
              if (
                commitsAmountDirectly
                && (event.key.startsWith("Arrow") || event.key === "Home" || event.key === "End")
              ) onAmountCommit?.(Number(event.currentTarget.value));
            }}
          />
        </>
      </div>}
      <button className="apply native-ai-apply" disabled={!canApply} onClick={() => {
        onApply();
        if (isCrop) {
          setExpandedCapability(undefined);
          onExpandedChange?.(undefined);
          onStraightenActiveChange?.(false);
        }
      }}>{busy ? "应用中…" : "应用"}</button>
      {!runnable && <p className="tool-gate">该工具的完整执行管线尚不可用。</p>}
    </div>
  ) : null;

  return (
    <aside className="tool-panel">
      <div className="tool-panel-heading">
        <h2>工具</h2>
      </div>
      {selectedLayer && onUpdateLayer && (
        <LayerInspector
          busy={busy}
          layer={selectedLayer}
          mask={selectedLayer.mask_artifact ? project?.masks?.[selectedLayer.mask_artifact] : undefined}
          projectId={projectId}
          onDeleteMask={onDeleteMask}
          onUpdate={(changes) => onUpdateLayer(selectedLayer.id, changes)}
          onUpdateMask={onUpdateMask}
          onUploadMask={(file) => onUploadLayerMask?.(selectedLayer.id, file)}
          maskBrushActive={maskBrushActive}
          maskBrushSettings={maskBrushSettings}
          onMaskBrushActiveChange={onMaskBrushActiveChange}
          onMaskBrushSettingsChange={onMaskBrushSettingsChange}
        />
      )}
      <div className="tool-groups">
        {groupedItems.length ? groupedItems.map((section) => (
          <section className={`tool-section tone-${section.tone}`} key={section.id}>
            <h3>{section.label}</h3>
            {section.items.map((item) => {
              const status = item.readiness?.status;
              const available = status === "parity-passed" || status === "runtime-ready";
              const visual = visuals[item.id];
              return (
                <div data-capability-id={item.id} className={`tool-accordion-item${expandedCapability === item.id ? " expanded" : ""}`} key={item.id}>
                  <button
                    className={`tool${selected === item.id ? " selected" : ""}`}
                    type="button"
                    aria-expanded={expandedCapability === item.id}
                    disabled={busy || !available}
                    title={available ? item.title : `尚未通过完整执行门禁：${item.readiness?.reason || "运行管线不可用"}`}
                    onClick={() => chooseCapability(item)}
                  >
                    <span className="tool-icon" aria-hidden="true"><Icon name={(visual?.icon || "adjust") as IconName} size={17} /></span>
                    <span className="tool-label">{item.title.replace(/\s*AI$/, "")}{visual?.ai_badge ? <sup>AI</sup> : null}</span>
                    <Icon name="chevronDown" size={13} />
                  </button>
                  {expandedCapability === item.id && selected === item.id && inlineInspector}
                </div>
              );
            })}
          </section>
        )) : <div className="panel-empty">正在读取工具列表…</div>}
      </div>
    </aside>
  );
}
