import type { ChangeEvent } from "react";
import { Icon } from "./Icon";

type EditorHeaderProps = {
  busy: boolean;
  runtimeLabel?: string;
  mode: "catalog" | "editor" | "workflow";
  projectId?: string;
  filename?: string;
  workflowTitle?: string;
  catalogCollection?: string;
  onUpload: (file?: File) => void;
  onCatalog: () => void;
  onExport: () => void;
};

export function EditorHeader({
  busy,
  runtimeLabel,
  mode,
  projectId,
  filename,
  workflowTitle,
  catalogCollection,
  onUpload,
  onCatalog,
  onExport,
}: EditorHeaderProps) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onUpload(event.target.files?.[0]);
    event.target.value = "";
  }

  return (
    <header className="topbar">
      <div className="window-actions" aria-label="应用状态">
        <span className="app-wordmark"><span className="app-mark" aria-hidden="true"><Icon name="spark" size={18} /></span><b>luminar</b><Icon name="chevronDown" size={13} /></span>
        <span className="history-arrows" aria-hidden="true"><Icon name="back" size={18} /><Icon name="forward" size={18} /></span>
        <button className="header-breadcrumb header-breadcrumb-button" type="button" onClick={onCatalog}>目录</button>
        {mode === "catalog" && catalogCollection && <><span className="breadcrumb-separator">/</span><span className="header-breadcrumb">{catalogCollection}</span></>}
        {mode === "editor" && <><span className="breadcrumb-separator">/</span><span className="header-breadcrumb">单个图像编辑</span></>}
        {mode === "workflow" && <><span className="breadcrumb-separator">/</span><span className="header-breadcrumb">{workflowTitle || "合并工具"}</span></>}
        {filename && mode === "editor" && <><span className="breadcrumb-separator">/</span><strong className="header-filename">{filename}</strong></>}
        {filename && mode === "catalog" && <><span className="breadcrumb-separator">/</span><strong className="header-filename">{filename}</strong></>}
        <span className="runtime-badge">{runtimeLabel || "正在检查本机模型"}</span>
      </div>
      <div className="topbar-actions">
        {mode === "editor" && projectId ? (
          <button className="chrome-button export-button" type="button" onClick={onExport}>
            <Icon name="export" size={16} />导出
          </button>
        ) : mode !== "workflow" ? (
          <label className={`chrome-button${busy ? " is-disabled" : ""}`}>
            <Icon name="export" size={16} />{busy ? "处理中…" : "打开图片"}
            <input type="file" accept="image/*" disabled={busy} onChange={handleFileChange} />
          </label>
        ) : null}
      </div>
    </header>
  );
}
