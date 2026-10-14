import { Icon, type IconName } from "./Icon";

export type EditorPanel = "presets" | "tools" | "edits" | "more" | "info";

type WorkspaceRailProps = {
  panel: EditorPanel;
  panelOpen: boolean;
  onPanelChange: (panel: EditorPanel) => void;
};

const PRIMARY_ITEMS: Array<[EditorPanel, IconName, string]> = [
  ["presets", "presets", "预设"],
  ["tools", "edit", "工具"],
  ["edits", "history", "编辑"],
];

const SECONDARY_ITEMS: Array<[EditorPanel, IconName, string]> = [
  ["more", "more", "更多"],
  ["info", "info", "信息"],
];

export function WorkspaceRail({ panel, panelOpen, onPanelChange }: WorkspaceRailProps) {
  function item([value, icon, label]: [EditorPanel, IconName, string]) {
    const selected = panelOpen && panel === value;
    return (
      <button
        className={selected ? "selected" : ""}
        key={value}
        type="button"
        aria-current={selected ? "page" : undefined}
        aria-pressed={selected}
        onClick={() => onPanelChange(value)}
      >
        <Icon name={icon} size={18} />
        <span>{label}</span>
      </button>
    );
  }

  return (
    <nav className="workspace-nav-rail" aria-label="编辑器面板">
      {PRIMARY_ITEMS.map(item)}
      <span className="workspace-rail-divider" />
      {SECONDARY_ITEMS.map(item)}
    </nav>
  );
}
