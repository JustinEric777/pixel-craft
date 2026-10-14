import { useEffect, useState, type ChangeEvent, type DragEvent } from "react";
import type { CatalogRecord, WorkflowKind } from "../api";
import { Icon } from "./Icon";

type WorkflowWorkspaceProps = {
  initialKind: WorkflowKind;
  collectionName: string;
  records: CatalogRecord[];
  busy: boolean;
  previewUrl?: string;
  status?: string;
  canExport: boolean;
  onBack: () => void;
  onKindChange: (kind: WorkflowKind) => void;
  onRun: (kind: WorkflowKind, files: File[]) => void;
  onExport: () => void;
};

const definitions: Array<{ kind: WorkflowKind; title: string; label: string }> = [
  { kind: "hdr_merge", title: "HDR 合并", label: "HDR Merge" },
  { kind: "focus_stacking", title: "焦点堆叠", label: "Focus Stacking" },
  { kind: "panorama_stitching", title: "全景拼接", label: "Panorama Stitching" },
];

function FileThumbnail({
  file,
  selected,
  onDragStart,
  onDrop,
  onRemove,
}: {
  file: File;
  selected: boolean;
  onDragStart: () => void;
  onDrop: (event: DragEvent) => void;
  onRemove: () => void;
}) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  const title = file.name.replace(/\.[^.]+$/, "");
  return (
    <article className={`workflow-photo-card${selected ? " selected" : ""}`} draggable onDragStart={onDragStart} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
      <strong title={file.name}>{title}</strong>
      {url && <img src={url} alt={title} />}
      <button type="button" aria-label={`移除${title}`} onClick={onRemove}>×</button>
    </article>
  );
}

export function WorkflowWorkspace({ initialKind, collectionName, records, busy, previewUrl, status, canExport, onBack, onKindChange, onRun, onExport }: WorkflowWorkspaceProps) {
  const [kind, setKind] = useState<WorkflowKind>(initialKind);
  const [files, setFiles] = useState<File[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number>();

  useEffect(() => {
    setKind(initialKind);
    setFiles([]);
  }, [initialKind]);

  function choose(event: ChangeEvent<HTMLInputElement>) {
    setFiles(event.target.files ? Array.from(event.target.files) : []);
    event.target.value = "";
  }

  function dropFile(event: DragEvent, targetIndex: number) {
    event.preventDefault();
    if (draggedIndex === undefined || draggedIndex === targetIndex) return;
    setFiles((current) => {
      const next = [...current];
      const [moved] = next.splice(draggedIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
    setDraggedIndex(undefined);
  }

  const current = definitions.find((item) => item.kind === kind) ?? definitions[0];
  const activeRecords = records.filter((record) => !record.deleted_at);
  const editedRecords = activeRecords.filter((record) => record.edit_count > 0);
  const deletedRecords = records.filter((record) => Boolean(record.deleted_at));
  return (
    <section className="workflow-workspace" aria-label={current.title}>
      <aside className="workflow-catalog-sidebar">
        <label className="workflow-search"><Icon name="search" /><input type="search" placeholder="搜索…" /></label>
        <label className={`workflow-add${busy ? " is-disabled" : ""}`}>
          添加照片
          <input type="file" accept="image/*" multiple disabled={busy} onChange={choose} />
        </label>
        <nav aria-label="照片来源">
          <button type="button"><Icon name="folder" size={16} /><span>所有照片</span><b>{activeRecords.length}</b></button>
          <button type="button"><Icon name="grid" size={16} /><span>单个图像编辑</span><b>{activeRecords.length}</b></button>
          <button type="button"><Icon name="recent" size={16} /><span>最近添加的</span><b>{activeRecords.length}</b></button>
          <button type="button"><Icon name="history" size={16} /><span>最近编辑的</span><b>{editedRecords.length}</b></button>
          <button type="button"><Icon name="missing" size={16} /><span>丢失的编辑修改</span><b>0</b></button>
          <button type="button"><Icon name="trash" size={16} /><span>回收站</span><b>{deletedRecords.length}</b></button>
        </nav>
        <div className="workflow-folders">
          <small>文件夹</small>
          {definitions.map((item) => (
            <button key={item.kind} type="button" className={kind === item.kind ? "selected" : ""} onClick={() => onKindChange(item.kind)}>
              <Icon name={item.kind === "hdr_merge" ? "hdr" : item.kind === "focus_stacking" ? "focus" : "panorama"} />
              <span>{item.label}</span><b>{kind === item.kind ? files.length : 0}</b>
            </button>
          ))}
          <button type="button"><Icon name="folder" /><span>{collectionName}</span><b>{activeRecords.length}</b></button>
        </div>
      </aside>

      <div className="workflow-catalog-content">
        <header className="workflow-selection-header">
          <div><button type="button" className="workflow-back" onClick={onBack}><Icon name="back" size={15} />返回目录</button><strong>{current.title}</strong><span>/ {files.length} 张照片</span>{files.length > 0 && <button type="button" onClick={() => setFiles([])}>取消选择</button>}</div>
          <div className="workflow-header-actions">
            <button type="button">操作<Icon name="chevronDown" size={13} /></button>
            <button className="workflow-run" type="button" disabled={busy || files.length < 2} onClick={() => onRun(kind, files)}>{busy ? "处理中…" : <>合并<Icon name="chevronDown" size={13} /></>}</button>
            <button className="workflow-export" type="button" disabled={busy || !canExport} onClick={onExport}>导出</button>
          </div>
        </header>

        {files.length ? (
          <div className="workflow-photo-grid">
            {files.map((file, index) => <FileThumbnail
              key={`${file.name}-${file.size}-${file.lastModified}`}
              file={file}
              selected={index === 0}
              onDragStart={() => setDraggedIndex(index)}
              onDrop={(event) => dropFile(event, index)}
              onRemove={() => setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index))}
            />)}
          </div>
        ) : (
          <label className={`workflow-empty-picker${busy ? " is-disabled" : ""}`}>
            <Icon name="image" />
            <strong>为 {current.title} 选择照片</strong>
            <span>选择两张或更多尺寸一致的源图像</span>
            <em>添加照片</em>
            <input type="file" accept="image/*" multiple disabled={busy} onChange={choose} />
          </label>
        )}

        {previewUrl && <div className="workflow-result"><img src={previewUrl} alt={`${current.title}预览`} /></div>}
        {status && <p className="workflow-status" role="status">{status}</p>}
        <footer className="workflow-bottom-bar"><span><Icon name="singleImage" size={17} /><Icon name="grid" size={17} /><Icon name="image" size={17} /><Icon name="more" size={17} /></span><span>{files.length} 张照片</span><span><Icon name="menu" size={17} /><Icon name="sort" size={17} /></span></footer>
      </div>
    </section>
  );
}
