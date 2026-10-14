import { assetPreviewUrl, type AssetRecord } from "../api";

type AssetPickerProps = {
  assets: AssetRecord[];
  selectedId: string;
  disabled: boolean;
  label?: string;
  preview?: boolean;
  onChange: (assetId: string) => void;
};

export function AssetPicker({
  assets,
  selectedId,
  disabled,
  label = "天空素材",
  preview = true,
  onChange,
}: AssetPickerProps) {
  return (
    <div className="asset-picker">
      <div className="asset-picker-heading">
        <span>{label}</span>
        <small>{assets.length} 个可用素材</small>
      </div>
      <div className="asset-grid" role="listbox" aria-label={label}>
        {assets.map((asset) => (
          <button
            className={`asset-card${selectedId === asset.id ? " selected" : ""}`}
            key={asset.id}
            type="button"
            role="option"
            aria-selected={selectedId === asset.id}
            disabled={disabled}
            onClick={() => onChange(asset.id)}
          >
            {preview ? (
              <img src={assetPreviewUrl(asset.id)} alt="" loading="lazy" />
            ) : (
              <i className="lut-swatch" aria-hidden="true" />
            )}
            <span title={asset.filename}>{asset.filename}</span>
          </button>
        ))}
      </div>
      {!assets.length && <div className="panel-empty">暂无可用{label}</div>}
    </div>
  );
}
