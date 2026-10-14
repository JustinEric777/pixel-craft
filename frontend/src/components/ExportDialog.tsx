import { exportUrl } from "../api";
import { Icon } from "./Icon";

type ExportDialogProps = {
  hasRestorableEdit: boolean;
  projectId: string;
  onClose: () => void;
  settings: ExportSettings;
  onSettingsChange: (settings: ExportSettings) => void;
};

export type ExportFormat = "png" | "jpeg" | "tiff";
export type ExportSettings = {
  value: string;
  format: ExportFormat;
  width: number;
  profile: "sRGB";
};

const EXTENSIONS: Record<ExportFormat, string> = { png: "png", jpeg: "jpg", tiff: "tiff" };

export function defaultFilename(filename?: string, format: ExportFormat = "png"): string {
  return `${(filename || "zpixel-export").replace(/\.[^.]+$/, "")}-edited.${EXTENSIONS[format]}`;
}

function safeFilename(value: string, format: ExportFormat): string {
  const cleaned = value.trim().replace(/[\\/:*?"<>|]/g, "-");
  const extension = EXTENSIONS[format];
  if (!cleaned) return `zpixel-export.${extension}`;
  const stem = cleaned.replace(/\.[^.]+$/, "");
  return `${stem}.${extension}`;
}

export function ExportDialog({ hasRestorableEdit, projectId, onClose, settings, onSettingsChange }: ExportDialogProps) {
  const { value, format, width, profile } = settings;
  const downloadName = safeFilename(value, format);
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="export-dialog" role="dialog" aria-modal="true" aria-labelledby="export-dialog-title">
        <header><Icon name="export" size={20} /><h2 id="export-dialog-title">导出</h2><button type="button" onClick={onClose} aria-label="关闭">×</button></header>
        <label>文件名<input aria-label="导出文件名" value={value} onChange={(event) => onSettingsChange({ ...settings, value: event.target.value })} /></label>
        <label>格式<select aria-label="导出格式" value={format} onChange={(event) => {
          const nextFormat = event.target.value as ExportFormat;
          onSettingsChange({ ...settings, format: nextFormat, value: safeFilename(value, nextFormat) });
        }}><option value="png">PNG</option><option value="jpeg">JPEG</option><option value="tiff">TIFF</option></select></label>
        <label>宽度<input aria-label="导出宽度" type="number" min="1" max="32768" value={width} onChange={(event) => onSettingsChange({ ...settings, width: Math.max(1, Number(event.target.value) || 1) })} /></label>
        <label>颜色配置<select aria-label="导出颜色配置" value={profile} onChange={(event) => onSettingsChange({ ...settings, profile: event.target.value as "sRGB" })}><option value="sRGB">sRGB</option></select></label>
        <p className={hasRestorableEdit ? "export-valid" : "export-warning"}>{hasRestorableEdit ? "当前图片包含可恢复的非破坏性编辑。" : "当前图片没有编辑；导出结果将与原图一致。"}</p>
        <footer>
          <button type="button" onClick={onClose}>取消</button>
          <a href={exportUrl(projectId, { format, width, profile, filename: downloadName })} download={downloadName} onClick={onClose}>导出</a>
        </footer>
      </section>
    </div>
  );
}
