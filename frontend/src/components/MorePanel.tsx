import type { WorkflowKind } from "../api";
import { Icon, type IconName } from "./Icon";

type MorePanelProps = {
  onOpenWorkflow: (kind: WorkflowKind) => void;
};

const WORKFLOWS: Array<[WorkflowKind, IconName, string]> = [
  ["hdr_merge", "hdr", "HDR 合并"],
  ["focus_stacking", "focus", "焦点堆叠"],
  ["panorama_stitching", "panorama", "全景拼接"],
];

export function MorePanel({ onOpenWorkflow }: MorePanelProps) {
  return (
    <aside className="right-panel more-panel" aria-label="更多工具">
      <section className="more-section">
        <h2>合并工具</h2>
        {WORKFLOWS.map(([kind, icon, label]) => (
          <button type="button" className="more-native-card workflow" key={kind} onClick={() => onOpenWorkflow(kind)}>
            <header><Icon name={icon} size={19} /><strong>{label}</strong><span>•••</span><Icon name="info" size={16} /></header>
            <div className="more-drop-zone"><Icon name="export" size={22} /><span>拖放多张照片<br />到此处开始使用</span></div>
            <em>{kind === "hdr_merge" ? "合并" : kind === "focus_stacking" ? "堆叠" : "拼接"}</em>
          </button>
        ))}
      </section>
    </aside>
  );
}
