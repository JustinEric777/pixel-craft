import { useEffect, type CSSProperties } from "react";
import { Icon } from "./Icon";

export type ContextMenuItem = {
  label?: string;
  action?: () => void;
  checked?: boolean;
  danger?: boolean;
  disabled?: boolean;
  divider?: boolean;
  shortcut?: string;
  submenu?: ContextMenuItem[];
};

type ContextMenuProps = {
  x: number;
  y: number;
  items: ContextMenuItem[];
  label: string;
  onClose: () => void;
};

export function ContextMenu({ x, y, items, label, onClose }: ContextMenuProps) {
  useEffect(() => {
    function close() { onClose(); }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("pointerdown", close);
    window.addEventListener("blur", close);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", close);
      window.removeEventListener("blur", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  const style = {
    left: Math.max(8, Math.min(x, window.innerWidth - 260)),
    top: Math.max(8, Math.min(y, window.innerHeight - 520)),
  } satisfies CSSProperties;

  function run(item: ContextMenuItem) {
    if (item.disabled || item.submenu) return;
    item.action?.();
    onClose();
  }

  return <div className="native-context-menu" role="menu" aria-label={label} style={style} onPointerDown={(event) => event.stopPropagation()}>
    {items.map((item, index) => item.divider
      ? <hr key={`divider-${index}`} />
      : <div className="native-context-entry" key={`${item.label}-${index}`}>
        <button
          type="button"
          role="menuitem"
          className={`${item.danger ? "danger" : ""}${item.submenu ? " has-submenu" : ""}`}
          disabled={item.disabled}
          onClick={() => run(item)}
        >
          <span className="context-check">{item.checked ? "✓" : ""}</span>
          <span>{item.label}</span>
          {item.shortcut && <kbd>{item.shortcut}</kbd>}
          {item.submenu && <Icon name="chevronRight" size={14} />}
        </button>
        {item.submenu && <div className="native-context-submenu" role="menu" aria-label={item.label}>
          {item.submenu.map((child, childIndex) => child.divider
            ? <hr key={`sub-divider-${childIndex}`} />
            : <button key={`${child.label}-${childIndex}`} type="button" role="menuitem" disabled={child.disabled} className={child.danger ? "danger" : ""} onClick={() => run(child)}>
              <span className="context-check">{child.checked ? "✓" : ""}</span>
              <span>{child.label}</span>
              {child.shortcut && <kbd>{child.shortcut}</kbd>}
            </button>)}
        </div>}
      </div>)}
  </div>;
}
