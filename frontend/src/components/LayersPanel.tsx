import { useEffect, useMemo, useState, type ChangeEvent, type DragEvent, type KeyboardEvent, type PointerEvent } from "react";
import {
  layerMaterialPreviewUrl,
  maskPreviewUrl,
  layerPreviewUrl,
  type Layer,
  type LayerMaterialGroup,
  type LayerUpdate,
  type MaskArtifact,
  type MaskBrushSettings,
  type MaskUpdate,
  type Project,
} from "../api";
import { Icon } from "./Icon";
import { ContextMenu } from "./ContextMenu";

type LayersPanelProps = {
  busy: boolean;
  groups: LayerMaterialGroup[];
  project?: Project;
  projectId?: string;
  selectedLayerId?: string;
  sourceUrl?: string;
  onAddLayer: (file?: File) => void;
  onAddMaterial: (materialId: string) => void;
  onDeleteLayer: (layerId: string) => void;
  onReorderLayers: (layerIds: string[]) => void;
  onSelectLayer: (layerId?: string) => void;
  onUpdateLayer: (layerId: string, changes: LayerUpdate) => void;
};

type PanelView = "stack" | "library" | "group";

const BLEND_MODES = [
  ["normal", "正常"],
  ["screen", "滤色"],
  ["multiply", "正片叠底"],
  ["overlay", "叠加"],
  ["soft_light", "柔光"],
  ["lighten", "变亮"],
  ["darken", "变暗"],
] as const;

export function LayersPanel({
  busy,
  groups,
  project,
  projectId,
  selectedLayerId,
  sourceUrl,
  onAddLayer,
  onAddMaterial,
  onDeleteLayer,
  onReorderLayers,
  onSelectLayer,
  onUpdateLayer,
}: LayersPanelProps) {
  const [view, setView] = useState<PanelView>("stack");
  const [activeGroupId, setActiveGroupId] = useState<string>();
  const [draggedLayerId, setDraggedLayerId] = useState<string>();
  const layers = project?.layers ?? [];
  const displayLayers = useMemo(() => [...layers].reverse(), [layers]);
  const selectedLayer = layers.find((layer) => layer.id === selectedLayerId);
  const activeGroup = groups.find((group) => group.id === activeGroupId);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onAddLayer(event.target.files?.[0]);
    event.target.value = "";
    setView("stack");
  }

  function addMaterial(materialId: string) {
    onAddMaterial(materialId);
    setView("stack");
  }

  function showGroup(groupId: string) {
    setActiveGroupId(groupId);
    setView("group");
  }

  function reorderLayer(targetId: string) {
    if (!draggedLayerId || draggedLayerId === targetId) return;
    const next = [...displayLayers];
    const sourceIndex = next.findIndex((layer) => layer.id === draggedLayerId);
    const targetIndex = next.findIndex((layer) => layer.id === targetId);
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    onReorderLayers(next.reverse().map((layer) => layer.id));
    setDraggedLayerId(undefined);
  }

  function dropLayer(event: DragEvent, targetId: string) {
    event.preventDefault();
    reorderLayer(targetId);
  }

  if (view === "library" || view === "group") {
    const visibleGroups = view === "group" && activeGroup ? [activeGroup] : groups;
    return (
      <aside className="layers-panel layer-library" aria-label="图层素材">
        <header className="layer-library-header">
          <button type="button" aria-label="返回图层" onClick={() => setView(view === "group" ? "library" : "stack")}>
            <Icon name="back" size={17} />
          </button>
          <h2>{view === "group" && activeGroup ? activeGroup.label : "层"}</h2>
        </header>
        {view === "library" && (
          <label className={`layer-load-image${busy ? " is-disabled" : ""}`}>
            加载图像
            <input type="file" accept="image/*" disabled={busy} onChange={handleFileChange} />
          </label>
        )}
        <div className="layer-library-scroll">
          {visibleGroups.map((group) => {
            const items = view === "group" ? group.items : group.items.slice(0, group.preview_limit);
            return (
              <section className="layer-material-section" key={group.id}>
                <div className="layer-material-heading">
                  <h3>{group.label}</h3>
                  {view === "library" && group.count > group.preview_limit && (
                    <button type="button" onClick={() => showGroup(group.id)}>查看全部</button>
                  )}
                </div>
                <div className="layer-material-grid">
                  {items.map((material) => (
                    <button
                      type="button"
                      key={material.id}
                      title={material.name}
                      disabled={busy || !projectId}
                      onClick={() => addMaterial(material.id)}
                    >
                      <img src={layerMaterialPreviewUrl(material.id)} alt={material.name} />
                    </button>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
        {view === "library" && (
          <label className={`layer-more-assets${busy ? " is-disabled" : ""}`}>
            添加本地素材
            <input type="file" accept="image/*" disabled={busy} onChange={handleFileChange} />
          </label>
        )}
      </aside>
    );
  }

  return (
    <aside className="layers-panel layer-stack" aria-label="图层">
      <div className="layer-stack-heading">
        <h2>层</h2>
        <button type="button" className="add-layer" disabled={busy || !projectId} aria-label="添加图层" onClick={() => setView("library")}>
          <Icon name="add" size={24} />
        </button>
      </div>
      <div className="layer-stack-scroll">
        {displayLayers.map((layer) => (
          <LayerRow
            busy={busy}
            key={layer.id}
            layer={layer}
            previewUrl={projectId ? layerPreviewUrl(projectId, layer.id) : ""}
            selected={selectedLayerId === layer.id}
            onDelete={() => onDeleteLayer(layer.id)}
            onPointerDown={() => setDraggedLayerId(layer.id)}
            onPointerUp={() => reorderLayer(layer.id)}
            onDragStart={() => setDraggedLayerId(layer.id)}
            onDrop={(event) => dropLayer(event, layer.id)}
            onSelect={() => onSelectLayer(layer.id)}
            onToggle={() => onUpdateLayer(layer.id, { visible: !layer.visible })}
          />
        ))}
        {sourceUrl && (
          <button className={`layer-stack-row source${selectedLayer ? "" : " selected"}`} type="button" onClick={() => onSelectLayer(undefined)}>
            <img src={sourceUrl} alt="原始图像" />
            <span><strong>原始图像</strong><small>背景</small></span>
          </button>
        )}
      </div>
    </aside>
  );
}

function LayerRow({
  busy,
  layer,
  previewUrl,
  selected,
  onDelete,
  onDragStart,
  onDrop,
  onPointerDown,
  onPointerUp,
  onSelect,
  onToggle,
}: {
  busy: boolean;
  layer: Layer;
  previewUrl: string;
  selected: boolean;
  onDelete: () => void;
  onDragStart: () => void;
  onDrop: (event: DragEvent) => void;
  onPointerDown: () => void;
  onPointerUp: () => void;
  onSelect: () => void;
  onToggle: () => void;
}) {
  const [context, setContext] = useState<{ x: number; y: number }>();
  return (
    <div
      className={`layer-stack-row${selected ? " selected" : ""}${layer.visible ? "" : " hidden"}`}
      draggable={!busy}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onDragStart={onDragStart}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
      onContextMenu={(event) => {
        event.preventDefault();
        event.stopPropagation();
        setContext({ x: event.clientX, y: event.clientY });
      }}
    >
      <button className="layer-visibility" type="button" disabled={busy} aria-label={layer.visible ? "隐藏图层" : "显示图层"} onClick={onToggle}>
        <Icon name="eye" size={15} />
      </button>
      <button className="layer-row-main" type="button" onClick={onSelect}>
        <img src={previewUrl} alt="" />
        <span><strong>{layer.name}</strong><small>{layer.source_kind === "library" ? "内置素材" : "图像图层"}</small></span>
      </button>
      <button className="layer-delete" type="button" disabled={busy} aria-label={`删除${layer.name}`} onClick={onDelete}>×</button>
      {context && <ContextMenu
        x={context.x}
        y={context.y}
        label={`${layer.name} 图层操作`}
        items={[
          { label: layer.visible ? "Hide Layer" : "Show Layer", disabled: busy, action: onToggle },
          { divider: true },
          { label: "移除图层", danger: true, disabled: busy, action: onDelete },
        ]}
        onClose={() => setContext(undefined)}
      />}
    </div>
  );
}

type LayerInspectorProps = {
  busy: boolean;
  layer: Layer;
  mask?: MaskArtifact;
  projectId?: string;
  onDeleteMask?: (maskId: string) => void;
  onUpdate: (changes: LayerUpdate) => void;
  onUpdateMask?: (maskId: string, changes: MaskUpdate) => void;
  onUploadMask?: (file: File) => void;
  maskBrushActive?: boolean;
  maskBrushSettings?: MaskBrushSettings;
  onMaskBrushActiveChange?: (active: boolean) => void;
  onMaskBrushSettingsChange?: (settings: MaskBrushSettings) => void;
};

export function LayerInspector({
  busy,
  layer,
  mask,
  projectId,
  onDeleteMask,
  onUpdate,
  onUpdateMask,
  onUploadMask,
  maskBrushActive = false,
  maskBrushSettings = { size: 80, softness: 24, strength: 70 },
  onMaskBrushActiveChange,
  onMaskBrushSettingsChange,
}: LayerInspectorProps) {
  const [activeTab, setActiveTab] = useState<"summary" | "mask">("summary");
  const [opacityDraft, setOpacityDraft] = useState(layer.opacity);

  useEffect(() => setOpacityDraft(layer.opacity), [layer.id, layer.opacity]);

  function commitOpacity(event: PointerEvent<HTMLInputElement>) {
    onUpdate({ opacity: Number(event.currentTarget.value) });
  }

  function commitOpacityKeyboard(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key.startsWith("Arrow") || event.key === "Home" || event.key === "End") {
      onUpdate({ opacity: Number(event.currentTarget.value) });
    }
  }

  return (
    <section className="layer-inspector" aria-label="图层属性">
      <div className="layer-inspector-heading"><strong>层属性 <sup>PRO</sup></strong><span aria-hidden="true">↶ &nbsp; ⓘ</span></div>
      <div className="layer-inspector-tabs" role="tablist" aria-label="图层属性视图">
        <button type="button" role="tab" aria-selected={activeTab === "summary"} onClick={() => setActiveTab("summary")}>摘要资讯</button>
        <button type="button" role="tab" aria-selected={activeTab === "mask"} onClick={() => setActiveTab("mask")}>遮罩</button>
      </div>
      {activeTab === "summary" ? <>
        <label className="layer-opacity">不透明度 <output>{Math.round(layer.opacity * 100)}</output>
          <input type="range" min="0" max="1" step="0.01" value={opacityDraft} disabled={busy} onChange={(event) => setOpacityDraft(Number(event.target.value))} onPointerUp={commitOpacity} onKeyUp={commitOpacityKeyboard} />
        </label>
        <label className="layer-blend">
          <span className="sr-only">混合模式</span>
          <select aria-label="混合模式" value={layer.blend_mode} disabled={busy} onChange={(event) => onUpdate({ blend_mode: event.target.value })}>
            {BLEND_MODES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </label>
        <div className="layer-flip-actions">
          <button type="button" disabled={busy} className={layer.flip_x ? "selected" : ""} onClick={() => onUpdate({ flip_x: !layer.flip_x })}>水平翻转</button>
          <button type="button" disabled={busy} className={layer.flip_y ? "selected" : ""} onClick={() => onUpdate({ flip_y: !layer.flip_y })}>垂直翻转</button>
        </div>
        <div className="layer-image-mapping">
          <strong>图像映射</strong>
          <div>
            <button type="button" disabled={busy} onClick={() => onUpdate({ scale: 1, offset_x: 0, offset_y: 0 })}>适合</button>
            <button type="button" disabled={busy} onClick={() => onUpdate({ scale: 1.15, offset_x: 0, offset_y: 0 })}>填充</button>
            <button type="button" disabled={busy} onClick={() => onUpdate({ scale: 1, offset_x: 0, offset_y: 0, rotation: 0 })}>拉伸</button>
          </div>
        </div>
      </> : <div className="layer-mask-editor">
        <div className="mask-brush-controls">
          <button type="button" className={maskBrushActive ? "selected" : ""} aria-pressed={maskBrushActive} disabled={busy} onClick={() => onMaskBrushActiveChange?.(!maskBrushActive)}>画笔</button>
          <label>画笔大小 <output>{maskBrushSettings.size}</output>
            <input aria-label="画笔大小" type="range" min="1" max="500" step="1" value={maskBrushSettings.size} disabled={busy} onChange={(event) => onMaskBrushSettingsChange?.({ ...maskBrushSettings, size: Number(event.target.value) })} />
          </label>
          <label>画笔柔和度 <output>{maskBrushSettings.softness}</output>
            <input aria-label="画笔柔和度" type="range" min="0" max="100" step="1" value={maskBrushSettings.softness} disabled={busy} onChange={(event) => onMaskBrushSettingsChange?.({ ...maskBrushSettings, softness: Number(event.target.value) })} />
          </label>
          <label>画笔强度 <output>{maskBrushSettings.strength}</output>
            <input aria-label="画笔强度" type="range" min="1" max="100" step="1" value={maskBrushSettings.strength} disabled={busy} onChange={(event) => onMaskBrushSettingsChange?.({ ...maskBrushSettings, strength: Number(event.target.value) })} />
          </label>
          <button type="button" disabled={busy || !mask} onClick={() => mask && onDeleteMask?.(mask.id)}>重置工具遮罩</button>
        </div>
        {mask && projectId ? <>
          <img className="layer-mask-preview" src={maskPreviewUrl(projectId, mask.id)} alt="当前图层遮罩" />
          <label className="layer-mask-toggle"><input type="checkbox" checked={mask.inverted} disabled={busy} onChange={() => onUpdateMask?.(mask.id, { inverted: !mask.inverted })} />反转遮罩</label>
          <label>密度 <output>{Math.round(mask.density * 100)}</output>
            <input type="range" min="0" max="1" step="0.01" value={mask.density} disabled={busy} onChange={(event) => onUpdateMask?.(mask.id, { density: Number(event.target.value) })} />
          </label>
          <label>羽化 <output>{Math.round(mask.feather)}</output>
            <input type="range" min="0" max="100" step="1" value={mask.feather} disabled={busy} onChange={(event) => onUpdateMask?.(mask.id, { feather: Number(event.target.value) })} />
          </label>
          <div className="layer-mask-actions">
            <label className={busy ? "is-disabled" : ""}>替换遮罩<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUploadMask?.(file);
              event.target.value = "";
            }} /></label>
            <button type="button" disabled={busy} onClick={() => onDeleteMask?.(mask.id)}>删除遮罩</button>
          </div>
        </> : <div className="layer-mask-empty">
          <span aria-hidden="true">◐</span>
          <strong>添加图层遮罩</strong>
          <p>导入灰度图；白色显示图层，黑色隐藏图层。</p>
          <label className={busy || !projectId ? "is-disabled" : ""}>加载遮罩<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy || !projectId} onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUploadMask?.(file);
            event.target.value = "";
          }} /></label>
        </div>}
      </div>}
    </section>
  );
}
