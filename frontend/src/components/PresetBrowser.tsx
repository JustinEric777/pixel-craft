import { useState, type ChangeEvent, type InputHTMLAttributes } from "react";

import { presetArtworkUrl, presetCategoryArtworkUrl, type Preset } from "../api";
import { Icon } from "./Icon";

type PresetBrowserProps = {
  projectId?: string;
  presets: Preset[];
  selectedPresetId?: string;
  busy: boolean;
  onApply: () => void;
  onPreview: (preset: Preset) => void;
  onImport: (files: File[]) => void;
};

const localizedCategories: Record<string, string> = {
  "Big City Lights": "城市灯光",
  "Big Screen": "大屏幕",
  Blockbuster: "电影大片",
  Objects: "对象",
  Closeups: "特写",
  Sunsets: "日落",
  Experimental: "实验",
  Nature: "自然",
  Savannah: "大草原",
  "Animal Friends": "动物朋友",
  Waterscapes: "水景",
  Scenery: "风景",
  "Easy Portraits": "简单人像",
  "Urban Style": "城市风貌",
  Artistic: "艺术",
  "Natural Skies": "自然天空",
  Essence: "本质精髓",
  Monochrome: "单色",
  Overcast: "阴天",
  Influencer: "影响者",
  "Easy Landscapes": "轻快风景",
  Filmatic: "电影效果",
};

const SECTION_ORDER = ["风景", "大自然", "人像", "创意", "本地预设", "其他"];

function sectionForCategory(category: string): string {
  if (["Big City Lights", "Sunsets", "Waterscapes", "Scenery", "Urban Style", "Natural Skies", "Overcast", "Easy Landscapes"].includes(category)) return "风景";
  if (["Nature", "Savannah", "Animal Friends"].includes(category)) return "大自然";
  if (["Closeups", "Easy Portraits", "Influencer"].includes(category)) return "人像";
  if (["Big Screen", "Blockbuster", "Objects", "Experimental", "Artistic", "Essence", "Monochrome", "Filmatic"].includes(category)) return "创意";
  if (category === "本地预设") return "本地预设";
  return "其他";
}

export function PresetBrowser({ projectId, presets, selectedPresetId, busy, onApply, onPreview, onImport }: PresetBrowserProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>();
  const categories = Array.from(new Set(presets.map((preset) => preset.category)));
  const categoryPresets = selectedCategory
    ? presets.filter((preset) => preset.category === selectedCategory)
    : [];

  if (selectedCategory) {
    return (
      <aside className="preset-browser preset-category-detail">
        <button className="preset-back" type="button" onClick={() => setSelectedCategory(undefined)}>
          <Icon name="back" size={16} />预设
        </button>
        <div className="preset-section-heading"><h2>{localizedCategories[selectedCategory] ?? selectedCategory}</h2></div>
        <div className="preset-grid">
          {categoryPresets.map((preset) => (
            <button className={`preset-card preset-${preset.id}${selectedPresetId === preset.id ? " selected" : ""}`} type="button" disabled={!projectId || busy} title={projectId ? `预览 ${preset.name}` : "请先打开照片"} key={preset.id} onClick={() => onPreview(preset)}>
              <img src={presetArtworkUrl(preset.id)} alt="" loading="lazy" />
              <span>{preset.name}</span>
            </button>
          ))}
        </div>
        <footer className="preset-apply-bar">
          <span>{selectedPresetId ? "预设预览已就绪" : "选择一个预设以预览"}</span>
          <button className="apply" type="button" disabled={!selectedPresetId || busy} onClick={onApply}>应用预设</button>
        </footer>
      </aside>
    );
  }

  const groupedCategories = SECTION_ORDER.map((label) => ({
    label,
    categories: categories.filter((category) => sectionForCategory(category) === label),
  })).filter((section) => section.categories.length);

  function importLocalPreset(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (files.length) onImport(files);
    event.target.value = "";
  }

  const directoryInput = {
    type: "file",
    multiple: true,
    disabled: busy,
    webkitdirectory: "",
    directory: "",
  } as unknown as InputHTMLAttributes<HTMLInputElement>;

  return (
    <aside className="preset-browser preset-overview">
      <div className="preset-overview-heading"><Icon name="back" size={17} /><h2>预设</h2><label className={`preset-import${busy ? " is-disabled" : ""}`}>添加<input {...directoryInput} onChange={importLocalPreset} /></label></div>
      {groupedCategories.length ? groupedCategories.map((section) => (
        <section className="preset-category-section" key={section.label}>
          <h3>{section.label}</h3>
          <div className="preset-category-grid">
            {section.categories.map((category) => {
              const representative = presets.find((preset) => preset.category === category);
              if (!representative) return null;
              return <button type="button" disabled={busy} key={category} aria-label={`打开${localizedCategories[category] ?? category}预设`} onClick={() => setSelectedCategory(category)}>
                <img src={category === "本地预设" ? presetArtworkUrl(representative.id) : presetCategoryArtworkUrl(category, "small")} alt="" loading="lazy" />
                <span>{localizedCategories[category] ?? category}</span>
              </button>;
            })}
          </div>
        </section>
      )) : <div className="panel-empty">正在读取预设…</div>}
    </aside>
  );
}
