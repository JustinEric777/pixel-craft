export type IconName =
  | "add"
  | "catalog"
  | "presets"
  | "edit"
  | "export"
  | "crop"
  | "quality"
  | "erase"
  | "structure"
  | "color"
  | "mono"
  | "sky"
  | "landscape"
  | "water"
  | "light"
  | "portrait"
  | "adjust"
  | "clone"
  | "hdr"
  | "focus"
  | "panorama"
  | "upscale"
  | "undo"
  | "redo"
  | "compare"
  | "eye"
  | "search"
  | "image"
  | "spark"
  | "history"
  | "more"
  | "info"
  | "help"
  | "upgrade"
  | "trash"
  | "lock"
  | "restore"
  | "generativeErase"
  | "generativeReplace"
  | "generativeExpand"
  | "chevronDown"
  | "chevronRight"
  | "back"
  | "forward"
  | "folder"
  | "mobile"
  | "grid"
  | "singleImage"
  | "recent"
  | "missing"
  | "tutorial"
  | "learn"
  | "marketplace"
  | "sort"
  | "menu";

type IconProps = {
  name: IconName;
  size?: number;
  className?: string;
};

export function Icon({ name, size = 18, className }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: `ui-icon${className ? ` ${className}` : ""}`,
    "aria-hidden": true,
  };
  switch (name) {
    case "add":
      return <svg {...common}><path d="M12 4v16M4 12h16" /></svg>;
    case "catalog":
      return <svg {...common}><path d="M3.5 7.5h6l2-2h9v13h-17z" /></svg>;
    case "presets":
      return <svg {...common}><path d="m4 20 10-10M12 4l.7 2.3L15 7l-2.3.7L12 10l-.7-2.3L9 7l2.3-.7zM18 12l.6 1.9 1.9.6-1.9.6L18 17l-.6-1.9-1.9-.6 1.9-.6z" /></svg>;
    case "edit":
    case "adjust":
      return <svg {...common}><path d="M4 6h10M18 6h2M4 12h3M11 12h9M4 18h8M16 18h4" /><circle cx="16" cy="6" r="2" /><circle cx="9" cy="12" r="2" /><circle cx="14" cy="18" r="2" /></svg>;
    case "export":
      return <svg {...common}><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v6h14v-6" /></svg>;
    case "crop":
      return <svg {...common}><path d="M7 3v14a2 2 0 0 0 2 2h12M3 7h12a2 2 0 0 1 2 2v12" /></svg>;
    case "quality":
      return <svg {...common}><path d="M5 5h14v14H5zM8 8h3v3H8zM13 13h3v3h-3z" /></svg>;
    case "erase":
      return <svg {...common}><path d="m4 15 8-9 7 6-7 8H8zM12 20h8" /></svg>;
    case "structure":
      return <svg {...common}><circle cx="6" cy="7" r="1.5" /><circle cx="12" cy="5" r="1.5" /><circle cx="18" cy="8" r="1.5" /><circle cx="8" cy="14" r="1.5" /><circle cx="15" cy="16" r="1.5" /><path d="m7.5 7 3-1.4m3 .2 3 1.4M7 8.5l.5 4m2 1 4-5m.8 1 .4 5" /></svg>;
    case "color":
      return <svg {...common}><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 1 0 16 5 5 0 0 0 0-10 3 3 0 0 1 0-6z" /></svg>;
    case "mono":
      return <svg {...common}><circle cx="12" cy="12" r="8" /><path d="M12 4v16" /><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none" opacity=".45" /></svg>;
    case "sky":
      return <svg {...common}><path d="M5 18h13a3 3 0 0 0 .3-6A6 6 0 0 0 7 10.5 3.8 3.8 0 0 0 5 18z" /></svg>;
    case "landscape":
      return <svg {...common}><path d="m3 18 6-8 4 5 3-4 5 7z" /><path d="M4 6h5" /></svg>;
    case "water":
      return <svg {...common}><path d="M12 3S6 10 6 15a6 6 0 0 0 12 0c0-5-6-12-6-12z" /></svg>;
    case "light":
      return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2" /></svg>;
    case "portrait":
      return <svg {...common}><circle cx="12" cy="8" r="4" /><path d="M5 21a7 7 0 0 1 14 0" /></svg>;
    case "clone":
      return <svg {...common}><rect x="4" y="7" width="10" height="10" rx="2" /><rect x="10" y="3" width="10" height="10" rx="2" /></svg>;
    case "hdr":
      return <svg {...common}><rect x="4" y="6" width="13" height="12" rx="1" /><path d="m8 14 3-3 2 2 2-2M8 3h12v12" /></svg>;
    case "focus":
      return <svg {...common}><path d="M8 4H4v4m12-4h4v4M8 20H4v-4m12 4h4v-4" /><circle cx="12" cy="12" r="3" /></svg>;
    case "panorama":
      return <svg {...common}><path d="M3 7c5-2 13-2 18 0v10c-5 2-13 2-18 0zM8 6v12m8-12v12" /></svg>;
    case "upscale":
      return <svg {...common}><path d="M9 4H4v5m11-5h5v5M9 20H4v-5m11 5h5v-5M4 9l6-6m10 6-6-6M4 15l6 6m10-6-6 6" /></svg>;
    case "undo":
      return <svg {...common}><path d="m9 7-4 4 4 4M5 11h8a6 6 0 0 1 6 6" /></svg>;
    case "redo":
      return <svg {...common}><path d="m15 7 4 4-4 4m4-4h-8a6 6 0 0 0-6 6" /></svg>;
    case "compare":
      return <svg {...common}><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M12 5v14" /></svg>;
    case "eye":
      return <svg {...common}><path d="M3 12s3.5-5 9-5 9 5 9 5-3.5 5-9 5-9-5-9-5z" /><circle cx="12" cy="12" r="2.5" /></svg>;
    case "history":
      return <svg {...common}><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" /><path d="M4 4v4.5h4.5M12 8v4l3 2" /></svg>;
    case "more":
      return <svg {...common}><path d="M5 6h14M5 12h14M5 18h14" /><circle cx="3" cy="6" r=".7" fill="currentColor" stroke="none" /><circle cx="3" cy="12" r=".7" fill="currentColor" stroke="none" /><circle cx="3" cy="18" r=".7" fill="currentColor" stroke="none" /></svg>;
    case "info":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".8" fill="currentColor" stroke="none" /></svg>;
    case "help":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.4 2.4 0 1 1 3.5 2.2c-.9.5-1.3 1-1.3 2" /><circle cx="12" cy="17" r=".7" fill="currentColor" stroke="none" /></svg>;
    case "upgrade":
      return <svg {...common}><circle cx="12" cy="12" r="9" fill="currentColor" stroke="none" /><path d="M12 16V8m0 0-3 3m3-3 3 3" stroke="#161616" strokeWidth="2" /></svg>;
    case "trash":
      return <svg {...common}><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" /></svg>;
    case "lock":
      return <svg {...common}><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>;
    case "restore":
      return <svg {...common}><path d="M4 17V7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="m6 16 4-4 3 3 2-2 3 3M16 7l.5 1.5L18 9l-1.5.5L16 11l-.5-1.5L14 9l1.5-.5z" /></svg>;
    case "generativeErase":
      return <svg {...common}><path d="m4 15 8-9 7 6-7 8H8zM12 20h8" /><path d="m18 3 .6 1.9 1.9.6-1.9.6L18 8l-.6-1.9-1.9-.6 1.9-.6z" /></svg>;
    case "generativeReplace":
      return <svg {...common}><path d="M7 7h10v10H7zM4 12a8 8 0 0 1 13-6m3 6a8 8 0 0 1-13 6" /><path d="m16 3 1 3-3 1m-6 14-1-3 3-1" /></svg>;
    case "generativeExpand":
      return <svg {...common}><path d="M9 4H4v5m11-5h5v5M9 20H4v-5m11 5h5v-5M8 8h8v8H8z" /></svg>;
    case "chevronDown":
      return <svg {...common}><path d="m7 10 5 5 5-5" /></svg>;
    case "chevronRight":
      return <svg {...common}><path d="m9 6 6 6-6 6" /></svg>;
    case "back":
      return <svg {...common}><path d="m15 5-7 7 7 7" /></svg>;
    case "forward":
      return <svg {...common}><path d="m9 5 7 7-7 7" /></svg>;
    case "folder":
      return <svg {...common}><path d="M3 7h7l2-2h9v14H3z" /></svg>;
    case "mobile":
      return <svg {...common}><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M10 5h4m-3 14h2" /></svg>;
    case "grid":
      return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>;
    case "singleImage":
      return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m5 17 5-5 3 3 2-2 4 4" /></svg>;
    case "recent":
      return <svg {...common}><path d="M4 12a8 8 0 1 0 2-5.3L4 9" /><path d="M4 5v4h4M12 7v5h4" /></svg>;
    case "missing":
      return <svg {...common}><path d="M4 5h16v14H4zM8 2v6m8-6v6" /><path d="m9 12 6 6m0-6-6 6" /></svg>;
    case "tutorial":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4z" fill="currentColor" stroke="none" /></svg>;
    case "learn":
      return <svg {...common}><path d="m3 9 9-5 9 5-9 5zM7 12v5c3 2 7 2 10 0v-5" /></svg>;
    case "marketplace":
      return <svg {...common}><path d="M5 8h14l-1 12H6zM8 8a4 4 0 0 1 8 0" /></svg>;
    case "sort":
      return <svg {...common}><path d="M7 4v16m0 0-3-3m3 3 3-3M17 20V4m0 0-3 3m3-3 3 3" /></svg>;
    case "menu":
      return <svg {...common}><path d="M4 6h16M4 12h16M4 18h16" /></svg>;
    case "search":
      return <svg {...common}><circle cx="10.5" cy="10.5" r="6" /><path d="m15 15 4 4" /></svg>;
    case "image":
      return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.5" /><path d="m4 17 5-5 3 3 2-2 6 5" /></svg>;
    case "spark":
    default:
      return <svg {...common}><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5zM19 16l.6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></svg>;
  }
}
