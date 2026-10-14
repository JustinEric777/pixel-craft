import { useMemo, useState } from "react";
import type { Capability, Edit, Project } from "../api";
import { Icon } from "./Icon";

type EditHistoryPanelProps = {
  busy: boolean;
  items: Capability[];
  project?: Project;
  onDeleteEdit: (editId: string) => void;
  onUpdateEdit: (editId: string, effect: string, parameters: Record<string, unknown>) => void;
};

const PARAMETER_LABELS: Record<string, string> = {
  amount: "强度",
  luminosity: "光度降噪",
  details: "详细信息",
  sharpness: "锐度",
  denoise_level: "调整等级",
  face_enhancer: "面部增强器",
  converted: "转换为黑白",
};

function visibleParameters(edit: Edit): Array<[string, unknown]> {
  return Object.entries(edit.parameters).filter(([key]) => !key.startsWith("_") && key !== "asset_id");
}

export function EditHistoryPanel({ busy, items, project, onDeleteEdit, onUpdateEdit }: EditHistoryPanelProps) {
  const titles = useMemo(() => new Map(items.map((item) => [item.id, item.title])), [items]);
  const [expandedEditId, setExpandedEditId] = useState<string>();
  const [draftParameters, setDraftParameters] = useState<Record<string, unknown>>({});

  function toggleEdit(edit: Edit) {
    if (expandedEditId === edit.id) {
      setExpandedEditId(undefined);
      return;
    }
    setExpandedEditId(edit.id);
    setDraftParameters({ ...edit.parameters });
  }

  return (
    <aside className="right-panel edit-history-panel" aria-label="编辑历史">
      <header className="right-panel-heading"><h2>编辑</h2></header>
      {project?.edits.length ? (
        <div className="edit-stack">
          {[...project.edits].reverse().map((edit, reverseIndex) => {
            const title = titles.get(edit.effect) || edit.effect;
            const expanded = expandedEditId === edit.id;
            return (
              <article className={`edit-card${expanded ? " expanded" : ""}`} key={edit.id}>
                <div className="edit-row">
                  <button className="edit-row-main" type="button" disabled={busy} aria-expanded={expanded} onClick={() => toggleEdit(edit)}>
                    <span className="edit-row-icon"><Icon name="history" size={17} /></span>
                    <span className="edit-row-label"><strong>{title}</strong><small>编辑 {project.edits.length - reverseIndex}</small></span>
                    <Icon name="chevronDown" size={13} />
                  </button>
                  <button className="edit-row-delete" type="button" disabled={busy} onClick={() => onDeleteEdit(edit.id)} aria-label={`删除${title}`}><Icon name="trash" size={15} /></button>
                </div>
                {expanded && <div className="edit-parameters" aria-label={`${title}参数`}>
                  {visibleParameters(edit).map(([key, originalValue]) => {
                    const value = draftParameters[key] ?? originalValue;
                    const label = PARAMETER_LABELS[key] ?? key.replaceAll("_", " ");
                    if (typeof originalValue === "number") {
                      const normalized = Math.abs(originalValue) <= 1;
                      return <label key={key}>{label}<output>{normalized ? Math.round(Number(value) * 100) : Number(value)}</output><input aria-label={label} type="range" min={normalized ? -1 : 0} max={normalized ? 1 : Math.max(100, Math.ceil(originalValue * 2))} step={normalized ? 0.01 : 1} value={Number(value)} disabled={busy} onChange={(event) => setDraftParameters((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>;
                    }
                    if (typeof originalValue === "boolean") {
                      return <label className="edit-boolean" key={key}><input type="checkbox" checked={Boolean(value)} disabled={busy} onChange={(event) => setDraftParameters((current) => ({ ...current, [key]: event.target.checked }))} />{label}</label>;
                    }
                    if (key === "denoise_level") {
                      return <label key={key}>{label}<select aria-label={label} value={String(value)} disabled={busy} onChange={(event) => setDraftParameters((current) => ({ ...current, [key]: event.target.value }))}><option value="low">低</option><option value="middle">中等</option><option value="high">高</option></select></label>;
                    }
                    return <div className="edit-static-parameter" key={key}><span>{label}</span><strong>{String(value)}</strong></div>;
                  })}
                  <button className="apply edit-update" type="button" disabled={busy} onClick={() => onUpdateEdit(edit.id, edit.effect, draftParameters)}>{busy ? "应用中…" : "应用"}</button>
                </div>}
              </article>
            );
          })}
        </div>
      ) : <div className="edit-empty-card"><strong>没有编辑</strong></div>}
    </aside>
  );
}
