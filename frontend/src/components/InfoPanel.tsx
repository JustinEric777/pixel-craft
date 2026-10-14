import type { CatalogRecord, Project } from "../api";
import { Icon } from "./Icon";

type InfoPanelProps = {
  filename?: string;
  project?: Project;
  record?: CatalogRecord;
};

function value(candidate: unknown): string {
  return candidate === undefined || candidate === null || candidate === "" ? "无数据" : String(candidate);
}

function bytes(size?: number): string {
  if (!size) return "—";
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function dateTime(candidate: unknown): string {
  if (!candidate) return "—";
  const date = new Date(String(candidate));
  return Number.isNaN(date.getTime()) ? String(candidate) : date.toLocaleString("zh-CN", { hour12: false });
}

export function InfoPanel({ filename, project, record }: InfoPanelProps) {
  const metadata = project?.metadata ?? {};
  const camera = value(metadata.camera_model ?? metadata.camera);
  const lens = value(metadata.lens_model ?? metadata.lens);
  return (
    <aside className="right-panel info-panel" aria-label="照片信息">
      <header className="right-panel-heading"><h2>影像资讯</h2></header>
      {project ? (
        <section className="native-info-card">
          <h3 title={filename}>{filename || "未命名照片"}</h3>
          <time>{dateTime(metadata.capture_time ?? record?.added_at)}</time>
          <div className="native-camera-block">
            <Icon name="image" size={20} />
            <strong>Camera: {camera}</strong>
            <span>Lens: {lens}</span>
            <footer>
              <span>{value(project.source.width)} × {value(project.source.height)}</span>
              <span>{bytes(record?.size)}</span>
            </footer>
            <dl>
              <div><dt>ISO</dt><dd>{value(metadata.iso)}</dd></div>
              <div><dt>焦距</dt><dd>{metadata.focal_length ? `${metadata.focal_length} mm` : "—"}</dd></div>
              <div><dt>EV</dt><dd>{value(metadata.exposure_bias)}</dd></div>
              <div><dt>光圈</dt><dd>{metadata.aperture ? `f/${metadata.aperture}` : "—"}</dd></div>
              <div><dt>快门</dt><dd>{value(metadata.shutter_speed)}</dd></div>
            </dl>
          </div>
        </section>
      ) : <div className="info-empty"><Icon name="image" size={28} /><span>未选择照片</span></div>}
    </aside>
  );
}
