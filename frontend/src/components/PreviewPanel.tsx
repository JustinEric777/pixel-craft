import { useEffect, useRef, useState, type ChangeEvent, type PointerEvent, type WheelEvent } from "react";
import { previewUrl } from "../api";
import type { BrushStroke, CatalogRecord, ExecutionTrace, WorkflowKind } from "../api";
import { Icon } from "./Icon";
import { ContextMenu, type ContextMenuItem } from "./ContextMenu";

type PreviewPanelProps = {
  analysis?: string;
  analysisActive: boolean;
  analysisError?: string;
  busy: boolean;
  onAnalyze: () => void;
  onCancelAnalysis: () => void;
  onHistory: (action: "undo" | "redo") => void;
  onExport: () => void;
  onReset: () => void;
  onToggleBefore: () => void;
  onPreviewReady: () => void;
  onUpload: (file?: File) => void;
  previewNonce: number;
  previewOverrideUrl?: string;
  projectId?: string;
  showBefore: boolean;
  sourceUrl?: string;
  trace?: ExecutionTrace;
  filename?: string;
  mode: "presets" | "edit";
  interactiveTool?: string;
  strokes: BrushStroke[];
  brushRadius: number;
  onStrokesChange: (strokes: BrushStroke[]) => void;
  filmstrip?: Array<{ projectId: string; filename: string; url: string; selected: boolean }>;
  onSelectFilmstrip?: (projectId: string) => void;
  catalogRecord?: CatalogRecord;
  onCatalogUpdate?: (changes: Record<string, unknown>) => void;
  onOpenPanel?: (panel: "presets" | "tools" | "edits" | "info") => void;
  onOpenWorkflow?: (kind: WorkflowKind) => void;
  cropActive?: boolean;
  cropBox?: [number, number, number, number];
  onCropBoxChange?: (box: [number, number, number, number]) => void;
  straightenActive?: boolean;
  onStraightenComplete?: (angle: number) => void;
};

export function PreviewPanel({
  analysis,
  analysisActive,
  analysisError,
  busy,
  onAnalyze,
  onCancelAnalysis,
  onHistory,
  onExport,
  onReset,
  onToggleBefore,
  onPreviewReady,
  onUpload,
  previewNonce,
  previewOverrideUrl,
  projectId,
  showBefore,
  sourceUrl,
  trace,
  filename,
  mode,
  interactiveTool,
  strokes,
  brushRadius,
  onStrokesChange,
  filmstrip = [],
  onSelectFilmstrip = () => undefined,
  catalogRecord,
  onCatalogUpdate = () => undefined,
  onOpenPanel = () => undefined,
  onOpenWorkflow = () => undefined,
  cropActive = false,
  cropBox = [0, 0, 1, 1],
  onCropBoxChange = () => undefined,
  straightenActive = false,
  onStraightenComplete = () => undefined,
}: PreviewPanelProps) {
  const requestedImageUrl = showBefore && sourceUrl
    ? sourceUrl
    : previewOverrideUrl ?? (projectId ? previewUrl(projectId, previewNonce) : sourceUrl);
  const [displayImageUrl, setDisplayImageUrl] = useState(requestedImageUrl);
  const [imageState, setImageState] = useState<"empty" | "loading" | "ready" | "error">("empty");
  const [showingSourceFallback, setShowingSourceFallback] = useState(false);
  const [draftPoints, setDraftPoints] = useState<number[][]>([]);
  const draftPointsRef = useRef<number[][]>([]);
  const activeStrokePointerRef = useRef<number | undefined>(undefined);
  const [cloneSource, setCloneSource] = useState<number[]>();
  const [zoom, setZoom] = useState(1);
  const [zoomMenuOpen, setZoomMenuOpen] = useState(false);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panOrigin, setPanOrigin] = useState<{ clientX: number; clientY: number; x: number; y: number }>();
  const [context, setContext] = useState<{ x: number; y: number }>();
  const [comparePressed, setComparePressed] = useState(false);
  const [cropDrag, setCropDrag] = useState<{ handle: "nw" | "ne" | "sw" | "se" | "move"; pointerId: number; start: [number, number]; box: [number, number, number, number] }>();
  const [straightenStart, setStraightenStart] = useState<{ pointerId: number; x: number; y: number }>();

  useEffect(() => {
    setDisplayImageUrl(requestedImageUrl);
    setImageState(requestedImageUrl ? "loading" : "empty");
    setShowingSourceFallback(false);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [requestedImageUrl]);

  useEffect(() => {
    setDraftPoints([]);
    draftPointsRef.current = [];
    activeStrokePointerRef.current = undefined;
    setCloneSource(undefined);
  }, [interactiveTool]);

  function normalizedPoint(event: PointerEvent<HTMLImageElement>): number[] {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [
      Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
    ];
  }

  function beginStroke(event: PointerEvent<HTMLImageElement>) {
    if (busy || imageState !== "ready") return;
    if (cropActive && straightenActive) {
      event.currentTarget.setPointerCapture?.(event.pointerId);
      setStraightenStart({ pointerId: event.pointerId, x: event.clientX, y: event.clientY });
      return;
    }
    if (!interactiveTool) {
      if (zoom <= 1) return;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      setPanOrigin({ clientX: event.clientX, clientY: event.clientY, ...pan });
      return;
    }
    const point = normalizedPoint(event);
    if (interactiveTool === "clone" && !cloneSource) {
      setCloneSource(point);
      return;
    }
    event.currentTarget.setPointerCapture?.(event.pointerId);
    activeStrokePointerRef.current = event.pointerId;
    draftPointsRef.current = [point];
    setDraftPoints(draftPointsRef.current);
  }

  function extendStroke(event: PointerEvent<HTMLImageElement>) {
    if (panOrigin) {
      setPan({
        x: panOrigin.x + event.clientX - panOrigin.clientX,
        y: panOrigin.y + event.clientY - panOrigin.clientY,
      });
      return;
    }
    if (
      !draftPointsRef.current.length
      || activeStrokePointerRef.current !== event.pointerId
    ) return;
    const point = normalizedPoint(event);
    const previous = draftPointsRef.current[draftPointsRef.current.length - 1];
    if (Math.hypot(point[0] - previous[0], point[1] - previous[1]) > 0.003) {
      draftPointsRef.current = [...draftPointsRef.current, point];
      setDraftPoints(draftPointsRef.current);
    }
  }

  function finishStraighten(event: PointerEvent<HTMLElement>) {
    if (straightenStart?.pointerId !== event.pointerId) return false;
    const angle = Math.max(-45, Math.min(45, Math.atan2(event.clientY - straightenStart.y, event.clientX - straightenStart.x) * 180 / Math.PI));
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    setStraightenStart(undefined);
    onStraightenComplete(Number(angle.toFixed(1)));
    return true;
  }

  function finishStroke(event: PointerEvent<HTMLImageElement>) {
    if (finishStraighten(event)) return;
    if (panOrigin) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      setPanOrigin(undefined);
      return;
    }
    if (draftPointsRef.current.length < 2) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      draftPointsRef.current = [];
      activeStrokePointerRef.current = undefined;
      setDraftPoints([]);
      return;
    }
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    onStrokesChange([
      ...strokes,
      { points: draftPointsRef.current, radius: brushRadius, ...(cloneSource ? { source: cloneSource } : {}) },
    ]);
    draftPointsRef.current = [];
    activeStrokePointerRef.current = undefined;
    setDraftPoints([]);
    if (interactiveTool === "clone") setCloneSource(undefined);
  }

  function changeZoom(event: WheelEvent<HTMLDivElement>) {
    if (!projectId || busy || imageState !== "ready") return;
    event.preventDefault();
    const next = Math.max(0.25, Math.min(4, zoom + (event.deltaY < 0 ? 0.1 : -0.1)));
    setZoom(Number(next.toFixed(2)));
    if (next <= 1) setPan({ x: 0, y: 0 });
  }

  function fitToView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setZoomMenuOpen(false);
  }

  function selectZoom(next: number) {
    setZoom(next);
    if (next <= 1) setPan({ x: 0, y: 0 });
    setZoomMenuOpen(false);
  }

  function beginCompare() {
    if (showBefore || comparePressed) return;
    setComparePressed(true);
    onToggleBefore();
  }

  function endCompare() {
    if (!comparePressed) return;
    setComparePressed(false);
    onToggleBefore();
  }

  function handleImageError() {
    if (!showBefore && sourceUrl && displayImageUrl !== sourceUrl) {
      setDisplayImageUrl(sourceUrl);
      setImageState("loading");
      setShowingSourceFallback(true);
      return;
    }
    setImageState("error");
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onUpload(event.target.files?.[0]);
    event.target.value = "";
  }

  function beginCropDrag(event: PointerEvent<HTMLButtonElement | HTMLDivElement>, handle: "nw" | "ne" | "sw" | "se" | "move") {
    if (busy || straightenActive) return;
    event.preventDefault();
    event.stopPropagation();
    const overlay = event.currentTarget.closest(".crop-overlay") as HTMLElement | null;
    if (!overlay) return;
    const bounds = overlay.getBoundingClientRect();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setCropDrag({
      handle,
      pointerId: event.pointerId,
      start: [(event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height],
      box: [...cropBox],
    });
  }

  function moveCropDrag(event: PointerEvent<HTMLDivElement>) {
    if (!cropDrag || cropDrag.pointerId !== event.pointerId) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    const dx = x - cropDrag.start[0];
    const dy = y - cropDrag.start[1];
    let [left, top, right, bottom] = cropDrag.box;
    const minimum = 0.08;
    if (cropDrag.handle === "move") {
      const width = right - left;
      const height = bottom - top;
      left = Math.max(0, Math.min(1 - width, left + dx));
      top = Math.max(0, Math.min(1 - height, top + dy));
      right = left + width;
      bottom = top + height;
    } else {
      if (cropDrag.handle.includes("w")) left = Math.max(0, Math.min(right - minimum, left + dx));
      if (cropDrag.handle.includes("e")) right = Math.min(1, Math.max(left + minimum, right + dx));
      if (cropDrag.handle.includes("n")) top = Math.max(0, Math.min(bottom - minimum, top + dy));
      if (cropDrag.handle.includes("s")) bottom = Math.min(1, Math.max(top + minimum, bottom + dy));
    }
    onCropBoxChange([left, top, right, bottom]);
  }

  function finishCropDrag(event: PointerEvent<HTMLDivElement>) {
    if (finishStraighten(event)) return;
    if (!cropDrag || cropDrag.pointerId !== event.pointerId) return;
    setCropDrag(undefined);
  }

  function beginCropOverlayPointer(event: PointerEvent<HTMLDivElement>) {
    if (busy || !straightenActive) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setStraightenStart({ pointerId: event.pointerId, x: event.clientX, y: event.clientY });
  }

  const selectedFilmstripItem = filmstrip.find((item) => item.selected);
  const visibleFilmstrip = selectedFilmstripItem
    ? [...filmstrip.filter((item) => !item.selected).slice(0, 7), selectedFilmstripItem]
    : filmstrip.slice(0, 8);

  const contextItems: ContextMenuItem[] = [
    ...(catalogRecord ? [
      { label: "设置标记", submenu: [
        { label: "收藏", checked: Boolean(catalogRecord.favorite), action: () => onCatalogUpdate({ favorite: true, rejected: false }) },
        { label: "已拒绝", checked: Boolean(catalogRecord.rejected), action: () => onCatalogUpdate({ rejected: true, favorite: false }) },
        { label: "清除标记", checked: !catalogRecord.favorite && !catalogRecord.rejected, action: () => onCatalogUpdate({ favorite: false, rejected: false }) },
      ] },
      { label: "设置评分", submenu: [
        ...[1, 2, 3, 4, 5].map((rating) => ({ label: `${"★".repeat(rating)}${"☆".repeat(5 - rating)}`, checked: catalogRecord.rating === rating, action: () => onCatalogUpdate({ rating }) })),
        { divider: true },
        { label: "清除评分", checked: !catalogRecord.rating, action: () => onCatalogUpdate({ rating: 0 }) },
      ] },
    ] : []),
    { divider: true },
    { label: "旋转", submenu: [
      { label: "向左旋转 90°", disabled: !catalogRecord, action: () => onCatalogUpdate({ rotation_delta: -90 }) },
      { label: "向右旋转 90°", disabled: !catalogRecord, action: () => onCatalogUpdate({ rotation_delta: 90 }) },
    ] },
    { label: "浏览", submenu: [
      { label: "预设", action: () => onOpenPanel("presets") },
      { label: "工具", action: () => onOpenPanel("tools") },
      { label: "编辑", action: () => onOpenPanel("edits") },
      { label: "信息", action: () => onOpenPanel("info") },
    ] },
    { label: "合并", submenu: [
      { label: "HDR 合并", action: () => onOpenWorkflow("hdr_merge") },
      { label: "焦点堆叠", action: () => onOpenWorkflow("focus_stacking") },
      { label: "全景拼接", action: () => onOpenWorkflow("panorama_stitching") },
    ] },
    { label: "创建虚拟副本", shortcut: "⌘'", disabled: true },
    { label: "调整", submenu: [
      { label: "应用预设…", action: () => onOpenPanel("presets") },
      { label: "打开工具…", action: () => onOpenPanel("tools") },
    ] },
    { divider: true },
    { label: "导出…", shortcut: "⇧⌘E", action: onExport },
    { label: "移至 Luminar 回收站", danger: true, disabled: !catalogRecord, action: () => onCatalogUpdate({ deleted: true }) },
    { label: "在 Finder 中显示", shortcut: "⌘R", disabled: true },
    { label: "显示直方图", action: () => onOpenPanel("info") },
  ];

  return (
    <section className="canvas-panel">
      {analysis && <div className={`analysis-status${analysisError ? " is-error" : ""}`} role={analysisError ? "alert" : "status"}>
        <span className="status-dot" />
        <span title={analysisError}>{analysis}{analysisError ? ` · ${analysisError}` : ""}</span>
        {analysisActive
          ? <button type="button" onClick={onCancelAnalysis}>取消</button>
          : analysisError && <button type="button" onClick={onAnalyze}>重试</button>}
      </div>}
      <div className={`canvas canvas-${mode}${imageState === "loading" ? " is-loading" : ""}`} onWheel={changeZoom}>
        {displayImageUrl ? <>
          <div
            className={`image-stage${interactiveTool ? " brush-active" : zoom > 1 ? " pan-active" : ""}`}
            data-pan-x={Math.round(pan.x)}
            data-pan-y={Math.round(pan.y)}
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          >
            <img key={displayImageUrl} src={displayImageUrl} alt={showBefore || showingSourceFallback ? "原始图片" : "编辑预览"} onContextMenu={(event) => { event.preventDefault(); setContext({ x: event.clientX, y: event.clientY }); }} onLoad={() => { setImageState("ready"); if (!showBefore && !showingSourceFallback) onPreviewReady(); }} onError={handleImageError} onPointerDown={beginStroke} onPointerMove={extendStroke} onPointerUp={finishStroke} onPointerCancel={finishStroke} />
            {cropActive && imageState === "ready" && <div className={`crop-overlay${straightenActive ? " straighten-active" : ""}`} aria-label="裁切区域" onPointerDown={beginCropOverlayPointer} onPointerMove={moveCropDrag} onPointerUp={finishCropDrag} onPointerCancel={finishCropDrag}>
              <div className="crop-shade crop-shade-top" style={{ height: `${cropBox[1] * 100}%` }} />
              <div className="crop-shade crop-shade-left" style={{ top: `${cropBox[1] * 100}%`, width: `${cropBox[0] * 100}%`, height: `${(cropBox[3] - cropBox[1]) * 100}%` }} />
              <div className="crop-shade crop-shade-right" style={{ top: `${cropBox[1] * 100}%`, left: `${cropBox[2] * 100}%`, height: `${(cropBox[3] - cropBox[1]) * 100}%` }} />
              <div className="crop-shade crop-shade-bottom" style={{ top: `${cropBox[3] * 100}%` }} />
              <div className="crop-frame" style={{ left: `${cropBox[0] * 100}%`, top: `${cropBox[1] * 100}%`, width: `${(cropBox[2] - cropBox[0]) * 100}%`, height: `${(cropBox[3] - cropBox[1]) * 100}%` }} onPointerDown={(event) => beginCropDrag(event, "move")}>
                <i className="crop-grid-v crop-grid-v-one" /><i className="crop-grid-v crop-grid-v-two" /><i className="crop-grid-h crop-grid-h-one" /><i className="crop-grid-h crop-grid-h-two" />
                {(["nw", "ne", "sw", "se"] as const).map((handle) => <button key={handle} type="button" className={`crop-handle crop-handle-${handle}`} aria-label={`裁切控制点 ${handle}`} onPointerDown={(event) => beginCropDrag(event, handle)} />)}
              </div>
            </div>}
            {interactiveTool && <svg className="brush-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
              {strokes.map((stroke, index) => <polyline key={index} points={stroke.points.map((point) => point.join(",")).join(" ")} fill="none" stroke={interactiveTool === "clone" ? "#54b9ff" : "#f5aa00"} strokeWidth={stroke.radius * 2} strokeLinecap="round" strokeLinejoin="round" opacity="0.55" />)}
              {draftPoints.length > 0 && <polyline points={draftPoints.map((point) => point.join(",")).join(" ")} fill="none" stroke="#ffc13a" strokeWidth={brushRadius * 2} strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />}
              {cloneSource && <circle cx={cloneSource[0]} cy={cloneSource[1]} r={brushRadius} fill="none" stroke="#54b9ff" strokeWidth="0.006" />}
            </svg>}
          </div>
          {imageState === "loading" && <div className="preview-state" role="status"><span className="state-spinner" />正在生成预览…</div>}
          {imageState === "error" && <div className="preview-state preview-error" role="alert"><strong>预览加载失败</strong><span>原图也无法读取，请重新打开图片</span></div>}
          {showingSourceFallback && imageState === "ready" && <div className="preview-fallback-notice" role="alert"><strong>当前编辑无法生成预览</strong><span>正在显示原图。请在“编辑”中删除尚不可运行的编辑后重试。</span></div>}
        </> : <div className="empty">
          <label className={`empty-import${busy ? " is-disabled" : ""}`} aria-label="添加照片">
            <span className="empty-mark" aria-hidden="true"><Icon name="add" size={28} /></span>
            <strong>添加照片开始编辑</strong>
            <span>JPEG、PNG、WebP 或 TIFF</span>
            <input hidden type="file" accept="image/*" disabled={busy} onChange={handleFileChange} />
          </label>
        </div>}
      </div>
      <div className="filmstrip" aria-label="照片胶片栏">
        {visibleFilmstrip.map((item) => (
          <button
            key={item.projectId}
            type="button"
            className={item.selected ? "selected" : ""}
            disabled={busy}
            title={item.filename}
            onClick={() => onSelectFilmstrip(item.projectId)}
          >
            <img src={item.url} alt={item.filename} />
          </button>
        ))}
      </div>
      <footer className="canvas-footer">
        <div className="execution-state" aria-label="执行状态">{trace && <i className={trace.status === "ready" ? "trace-ready" : "trace-warning"} title={trace.status === "ready" ? "执行完成" : "执行失败"} />}</div>
        <strong title={filename}>{filename || "未选择照片"}</strong>
        <div className="preview-actions">
          <div className="zoom-selector">
            <button type="button" disabled={!projectId} onClick={() => setZoomMenuOpen((open) => !open)} title="适合视图" aria-label="适合视图">{Math.round(zoom * 100)}%</button>
            {zoomMenuOpen && <div className="zoom-menu" role="menu" aria-label="缩放比例">
              {[0.25, 0.5, 1, 2, 4].map((value) => <button key={value} type="button" role="menuitem" onClick={() => selectZoom(value)}>{Math.round(value * 100)}%</button>)}
              <button type="button" role="menuitem" onClick={fitToView}>适合屏幕</button>
            </div>}
          </div>
          <button type="button" disabled={!projectId || busy} onClick={() => onHistory("undo")} title="撤销"><Icon name="undo" size={17} /></button>
          <button type="button" disabled={!projectId || busy} onClick={() => onHistory("redo")} title="重做"><Icon name="redo" size={17} /></button>
          <button type="button" disabled={!projectId || busy} onClick={onReset} title="恢复到原始状态" aria-label="恢复到原始状态"><Icon name="restore" size={17} /></button>
          <button type="button" disabled={!projectId || busy || analysisActive} onClick={onAnalyze} title="运行 AI 分析"><Icon name="spark" size={17} /></button>
          <button className={showBefore ? "selected" : ""} type="button" disabled={!projectId || busy} onPointerDown={beginCompare} onPointerUp={endCompare} onPointerCancel={endCompare} onPointerLeave={endCompare} title="前后对比"><Icon name="compare" size={17} /></button>
          <button className={showBefore ? "selected" : ""} type="button" disabled={!projectId || busy} onClick={onToggleBefore} title="显示原图"><Icon name="eye" size={18} /></button>
          {projectId && <button type="button" onClick={onExport} disabled={busy} title="导出" aria-label="导出"><Icon name="export" size={17} /></button>}
        </div>
      </footer>
      {context && <ContextMenu x={context.x} y={context.y} label="照片操作" items={contextItems} onClose={() => setContext(undefined)} />}
    </section>
  );
}
