export type SkySettings = {
  horizon_offset: number;
  vertical_offset: number;
  horizontal_offset: number;
  sky_flip: boolean;
  sky_global: number;
  fix_gaps: number;
  edge_refinement: number;
  foreground_relight: number;
  relight_saturation: number;
  relight_human: number;
  reflection_amount: number;
  reflection_blur: number;
  sky_blur: number;
  sky_grain: number;
  atmospheric_haze: number;
  temperature: number;
  brightness: number;
};

export const DEFAULT_SKY_SETTINGS: SkySettings = {
  horizon_offset: 0,
  vertical_offset: 0,
  horizontal_offset: 0,
  sky_flip: false,
  sky_global: 30,
  // Conservative defaults keep solid foreground objects (walls, roofs and
  // poles) outside the sky mask. Users can still widen/refine the boundary
  // explicitly when a source image needs it.
  fix_gaps: 10,
  edge_refinement: 30,
  foreground_relight: 20,
  relight_saturation: 0,
  relight_human: 0,
  reflection_amount: 50,
  reflection_blur: 0,
  sky_blur: 0,
  sky_grain: 0,
  atmospheric_haze: 0,
  temperature: 0,
  brightness: 0,
};

export function toSkyParameters(settings: SkySettings): Record<string, number | boolean> {
  return {
    horizon_offset: 0.58 + settings.horizon_offset / 200,
    vertical_offset: settings.vertical_offset / 200,
    horizontal_offset: settings.horizontal_offset / 200,
    sky_flip: settings.sky_flip,
    // Native control values are kept in the UI. These deterministic adapters
    // preserve the compositor's normalized contract until single-variable
    // Native exports finish calibrating each response curve.
    sky_global: Math.min(1.5, settings.sky_global / 30),
    fix_gaps: (settings.fix_gaps - 2) / 38,
    edge_refinement: settings.edge_refinement / 5,
    foreground_relight: settings.foreground_relight / 100,
    relight_saturation: 1 + settings.relight_saturation / 100,
    relight_human: settings.relight_human / 100,
    reflection_amount: settings.reflection_amount / 100,
    reflection_blur: settings.reflection_blur / 5,
    sky_blur: settings.sky_blur / 5,
    sky_grain: settings.sky_grain / 100,
    atmospheric_haze: settings.atmospheric_haze / 100,
    temperature: settings.temperature / 100,
    brightness: 2 ** (settings.brightness / 100),
  };
}

type NumericSkySetting = Exclude<keyof SkySettings, "sky_flip">;

type SliderDefinition = {
  key: NumericSkySetting;
  label: string;
  min: number;
  max: number;
  step: number;
};

type SkySection = {
  title: string;
  sliders: SliderDefinition[];
  toggle?: { key: "sky_flip"; label: string };
};

const sections: SkySection[] = [
  {
    title: "天空方向",
    sliders: [
      { key: "horizon_offset", label: "地平线位置", min: -100, max: 100, step: 1 },
      { key: "vertical_offset", label: "垂直位置", min: -100, max: 100, step: 1 },
      { key: "horizontal_offset", label: "水平位置", min: -100, max: 100, step: 1 },
    ],
    toggle: { key: "sky_flip", label: "翻转" },
  },
  {
    title: "蒙板细调",
    sliders: [
      { key: "edge_refinement", label: "修复细节", min: 10, max: 100, step: 1 },
      { key: "sky_global", label: "全局", min: 4, max: 100, step: 1 },
      { key: "fix_gaps", label: "消除间隙", min: 2, max: 40, step: 1 },
    ],
  },
  {
    title: "场景改光",
    sliders: [
      { key: "foreground_relight", label: "改光强度", min: 0, max: 100, step: 1 },
      { key: "relight_saturation", label: "改光饱和度", min: 0, max: 100, step: 1 },
      { key: "relight_human", label: "手动改光", min: 0, max: 100, step: 1 },
    ],
  },
  {
    title: "反射",
    sliders: [
      { key: "reflection_blur", label: "水效模糊", min: 0, max: 100, step: 1 },
      { key: "reflection_amount", label: "反射量", min: 0, max: 100, step: 1 },
    ],
  },
  {
    title: "天空调整",
    sliders: [
      { key: "sky_grain", label: "木纹", min: 0, max: 100, step: 1 },
      { key: "sky_blur", label: "散焦", min: 0, max: 100, step: 1 },
      { key: "atmospheric_haze", label: "大气霾雾", min: 0, max: 100, step: 1 },
      { key: "temperature", label: "暖色", min: -100, max: 100, step: 1 },
      { key: "brightness", label: "亮度", min: -100, max: 100, step: 1 },
    ],
  },
];

type SkyControlsProps = {
  disabled: boolean;
  settings: SkySettings;
  onChange: (key: keyof SkySettings, value: number | boolean) => void;
};

export function SkyControls({ disabled, settings, onChange }: SkyControlsProps) {
  return <div className="sky-controls">
    {sections.map((section) => <details key={section.title}>
      <summary>{section.title}</summary>
      <div className="sky-control-section">
        {section.toggle && <label className="sky-toggle">
          <span>{section.toggle.label}</span>
          <input type="checkbox" data-parameter-id={section.toggle.key} checked={settings[section.toggle.key]} disabled={disabled} onChange={(event) => onChange(section.toggle!.key, event.target.checked)} />
        </label>}
        {section.sliders.map((slider) => <div className="sky-slider" key={slider.key}>
          <label htmlFor={`sky-${slider.key}`}><span>{slider.label}</span><output>{settings[slider.key].toFixed(slider.step < 1 ? 2 : 0)}</output></label>
          <input
            id={`sky-${slider.key}`}
            data-parameter-id={slider.key}
            type="range"
            min={slider.min}
            max={slider.max}
            step={slider.step}
            value={settings[slider.key]}
            disabled={disabled}
            onChange={(event) => onChange(slider.key, Number(event.target.value))}
          />
        </div>)}
      </div>
    </details>)}
  </div>;
}
