import { useRef, useState, type ChangeEvent, type InputHTMLAttributes, type MouseEvent } from "react";
import type { CatalogRecord, Project, WorkflowKind } from "../api";
import { Icon } from "./Icon";
import { ContextMenu, type ContextMenuItem } from "./ContextMenu";

type CatalogWorkspaceProps = {
  collectionName: string;
  project?: Project;
  records: CatalogRecord[];
  busy: boolean;
  onUpload: (file?: File | File[], collection?: string) => void;
  onOpen: (record: CatalogRecord) => void;
  onOpenPanel: (record: CatalogRecord, panel: "presets" | "tools" | "edits" | "info") => void;
  onOpenWorkflow: (kind: WorkflowKind) => void;
  onUpdateRecord: (record: CatalogRecord, changes: Record<string, unknown>) => void;
  onExportRecord: (record: CatalogRecord) => void;
};

type CatalogView = "collection" | "all" | "recent" | "edited" | "trash";

function basename(path?: string): string {
  return path?.split(/[\\/]/).pop() || "未选择照片";
}

function projectFilename(project?: Project): string {
  const originalFilename = project?.metadata?.original_filename;
  return typeof originalFilename === "string"
    ? originalFilename
    : basename(project?.source.path);
}

export function CatalogWorkspace({
  collectionName,
  project,
  records,
  busy,
  onUpload,
  onOpen,
  onOpenPanel,
  onOpenWorkflow,
  onUpdateRecord,
  onExportRecord,
}: CatalogWorkspaceProps) {
  const [view, setView] = useState<CatalogView>("all");
  const [query, setQuery] = useState("");
  const [context, setContext] = useState<{ x: number; y: number; record?: CatalogRecord; folder?: WorkflowKind | "collection" }>();
  const folderInputRef = useRef<HTMLInputElement>(null);
  const folderCollectionRef = useRef<string | undefined>(undefined);

  function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    onUpload(event.target.files ? Array.from(event.target.files) : undefined);
    event.target.value = "";
  }

  function handleFolderUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : [];
    const relativeRoot = files[0]?.webkitRelativePath?.split("/")[0];
    onUpload(files, folderCollectionRef.current || relativeRoot || collectionName);
    folderCollectionRef.current = undefined;
    event.target.value = "";
  }

  const folderInputProps = {
    type: "file",
    accept: "image/*",
    multiple: true,
    disabled: busy,
    onChange: handleFolderUpload,
    webkitdirectory: "",
    directory: "",
  } as unknown as InputHTMLAttributes<HTMLInputElement>;

  const visible = records.filter((record) => {
    if (view === "trash") return Boolean(record.deleted_at);
    if (record.deleted_at) return false;
    if (view === "recent") return true;
    if (view === "edited") return record.edit_count > 0;
    return true;
  }).filter((record) => record.filename.toLowerCase().includes(query.toLowerCase()));

  const count = (filter: (record: CatalogRecord) => boolean) => records.filter(filter).length;

  function showPhotoMenu(event: MouseEvent, record: CatalogRecord) {
    event.preventDefault();
    event.stopPropagation();
    setContext({ x: event.clientX, y: event.clientY, record });
  }

  function showFolderMenu(event: MouseEvent, folder: WorkflowKind | "collection") {
    event.preventDefault();
    setContext({ x: event.clientX, y: event.clientY, folder });
  }

  function photoMenuItems(record: CatalogRecord): ContextMenuItem[] {
    const openPanel = (panel: "presets" | "tools" | "edits" | "info") => () => onOpenPanel(record, panel);
    return [
      { label: "设置标记", submenu: [
        { label: "收藏", checked: Boolean(record.favorite), action: () => onUpdateRecord(record, { favorite: true, rejected: false }) },
        { label: "已拒绝", checked: Boolean(record.rejected), action: () => onUpdateRecord(record, { rejected: true, favorite: false }) },
        { label: "清除标记", checked: !record.favorite && !record.rejected, action: () => onUpdateRecord(record, { favorite: false, rejected: false }) },
      ] },
      { label: "设置评分", submenu: [
        ...[1, 2, 3, 4, 5].map((rating) => ({ label: `${"★".repeat(rating)}${"☆".repeat(5 - rating)}`, checked: record.rating === rating, action: () => onUpdateRecord(record, { rating }) })),
        { divider: true },
        { label: "清除评分", checked: !record.rating, action: () => onUpdateRecord(record, { rating: 0 }) },
      ] },
      { divider: true },
      { label: "旋转", submenu: [
        { label: "向左旋转 90°", action: () => onUpdateRecord(record, { rotation_delta: -90 }) },
        { label: "向右旋转 90°", action: () => onUpdateRecord(record, { rotation_delta: 90 }) },
      ] },
      { label: "浏览", submenu: [
        { label: "预设", action: openPanel("presets") },
        { label: "工具", action: openPanel("tools") },
        { label: "编辑", action: openPanel("edits") },
        { label: "信息", action: openPanel("info") },
      ] },
      { label: "合并", submenu: [
        { label: "HDR 合并", action: () => onOpenWorkflow("hdr_merge") },
        { label: "焦点堆叠", action: () => onOpenWorkflow("focus_stacking") },
        { label: "全景拼接", action: () => onOpenWorkflow("panorama_stitching") },
      ] },
      { label: "创建虚拟副本", shortcut: "⌘'", disabled: true },
      { label: "调整", submenu: [
        { label: "应用预设…", action: openPanel("presets") },
        { label: "打开工具…", action: openPanel("tools") },
      ] },
      { divider: true },
      { label: "导出…", shortcut: "⇧⌘E", action: () => onExportRecord(record) },
      { label: "打开在", submenu: [
        { label: "预设", action: openPanel("presets") },
        { label: "工具", action: openPanel("tools") },
      ] },
      { label: "转到", submenu: [
        { label: collectionName, action: () => setView("collection") },
      ] },
      { label: record.deleted_at ? "从回收站恢复" : "移至 Luminar 回收站", danger: !record.deleted_at, action: () => onUpdateRecord(record, { deleted: !record.deleted_at }) },
      { label: "在 Finder 中显示", shortcut: "⌘R", disabled: true },
      { label: "显示直方图", action: openPanel("info") },
    ];
  }

  function folderMenuItems(folder: WorkflowKind | "collection"): ContextMenuItem[] {
    return [
      { label: "打开", action: () => folder === "collection" ? setView("collection") : onOpenWorkflow(folder) },
      { label: "导入图片到该文件夹…", action: () => {
        folderCollectionRef.current = folder === "collection" ? collectionName : folder;
        folderInputRef.current?.click();
      } },
      { divider: true },
      { label: "新的子文件夹…", disabled: true },
      { label: "在 Finder 中显示", disabled: true },
      { divider: true },
      { label: "重新命名…", disabled: true },
      { label: "从目录中删除", disabled: true },
      { label: "永久删除", danger: true, disabled: true },
      { divider: true },
      { label: "添加至快捷方式", disabled: true },
    ];
  }

  return (
    <section className="catalog-workspace">
      <aside className="catalog-sidebar">
        <h2>目录</h2>
        <label className="catalog-search"><Icon name="search" size={17} /><input aria-label="搜索照片" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索…" /></label>
        <details className="catalog-import-menu">
          <summary className={`catalog-add${busy ? " is-disabled" : ""}`}>添加照片</summary>
          <div className="catalog-import-options">
            <label><span>添加文件</span><input type="file" accept="image/*" multiple disabled={busy} onChange={handleUpload} /></label>
            <label><span>添加文件夹</span><input ref={folderInputRef} {...folderInputProps} /></label>
          </div>
        </details>
        <nav aria-label="照片目录">
          <button className={view === "all" ? "selected" : ""} type="button" onClick={() => setView("all")}><Icon name="folder" size={16} /><span>所有照片</span><b>{count((record) => !record.deleted_at)}</b></button>
          <button type="button"><Icon name="grid" size={16} /><span>单个图像编辑</span><b>{count((record) => !record.deleted_at)}</b></button>
          <button className={view === "recent" ? "selected" : ""} type="button" onClick={() => setView("recent")}><Icon name="recent" size={16} /><span>最近添加的</span><b>{count((record) => !record.deleted_at)}</b></button>
          <button className={view === "edited" ? "selected" : ""} type="button" onClick={() => setView("edited")}><Icon name="history" size={16} /><span>最近编辑的</span><b>{count((record) => !record.deleted_at && record.edit_count > 0)}</b></button>
          <button type="button"><Icon name="missing" size={16} /><span>丢失的编辑修改</span><b>0</b></button>
          <button className={view === "trash" ? "selected" : ""} type="button" onClick={() => setView("trash")}><Icon name="trash" size={16} /><span>回收站</span><b>{count((record) => Boolean(record.deleted_at))}</b></button>
        </nav>
        <section className="catalog-workflows" aria-label="合并工具">
          <h3>文件夹</h3>
          <button type="button" onContextMenu={(event) => showFolderMenu(event, "hdr_merge")} onClick={() => onOpenWorkflow("hdr_merge")}><Icon name="hdr" /><span>HDR Merge</span></button>
          <button type="button" onContextMenu={(event) => showFolderMenu(event, "focus_stacking")} onClick={() => onOpenWorkflow("focus_stacking")}><Icon name="focus" /><span>Focus Stacking</span></button>
          <button type="button" onContextMenu={(event) => showFolderMenu(event, "panorama_stitching")} onClick={() => onOpenWorkflow("panorama_stitching")}><Icon name="panorama" /><span>Panorama Stitching</span></button>
          <button className={view === "collection" ? "selected" : ""} type="button" onContextMenu={(event) => showFolderMenu(event, "collection")} onClick={() => setView("collection")}><Icon name="folder" /><span>{collectionName}</span><b>{count((record) => !record.deleted_at)}</b></button>
        </section>
      </aside>
      <div className="catalog-content">
        <header><strong>{view === "collection" ? collectionName : view === "trash" ? "回收站" : view === "edited" ? "最近编辑的" : "所有照片"}</strong><span>{visible.length} 张照片　·　按名称</span></header>
        <div className="photo-grid-scroll">
        <div className="photo-grid">
          {visible.length ? visible.map((record) => (
            <article
              className={`photo-card${record.path === project?.source.path || context?.record?.asset_id === record.asset_id ? " selected" : ""}`}
              data-asset-id={record.asset_id}
              data-project-id={record.project_id}
              data-filename={record.filename}
              key={record.asset_id}
              onContextMenu={(event) => showPhotoMenu(event, record)}
              onClick={() => onOpen(record)}
              onDoubleClick={() => onOpenPanel(record, "tools")}
            >
              <span className="photo-card-name">{record.filename}</span>
              <img
                loading="lazy"
                src={`/api/v1/assets/${encodeURIComponent(record.asset_id)}/preview`}
                alt={record.filename}
                style={{ transform: `rotate(${record.rotation || 0}deg)` }}
              />
              <footer><span aria-label={`${record.rating || 0} 星评分`}>{[1, 2, 3, 4, 5].map((star) => <i className={star <= (record.rating || 0) ? "active" : ""} key={star}>☆</i>)}</span><b>{record.favorite ? "♥" : record.rejected ? "×" : ""}</b></footer>
            </article>
          )) : <div className="catalog-empty"><strong>还没有照片</strong><span>使用“添加照片”导入第一张照片</span></div>}
        </div></div>
      </div>
      <aside className="catalog-inspector">
        <div className="metadata-card"><h3>{projectFilename(project)}</h3><p>{project ? `${project.source.width || "-"} × ${project.source.height || "-"}` : "Camera: No Data"}</p><p>{project ? `${project.edits.length} 个编辑` : "Lens: No Data"}</p></div>
        <h3>合并工具</h3>
        <button type="button" onClick={() => onOpenWorkflow("hdr_merge")}><Icon name="hdr" />HDR 合并</button>
        <button type="button" onClick={() => onOpenWorkflow("focus_stacking")}><Icon name="focus" />焦点堆叠</button>
        <button type="button" onClick={() => onOpenWorkflow("panorama_stitching")}><Icon name="panorama" />全景拼接</button>
      </aside>
      {context?.record && <ContextMenu x={context.x} y={context.y} label={`${context.record.filename} 操作`} items={photoMenuItems(context.record)} onClose={() => setContext(undefined)} />}
      {context?.folder && <ContextMenu x={context.x} y={context.y} label="文件夹操作" items={folderMenuItems(context.folder)} onClose={() => setContext(undefined)} />}
    </section>
  );
}
