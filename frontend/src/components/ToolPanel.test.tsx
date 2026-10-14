import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ToolPanel } from "./ToolPanel";
import { DEFAULT_SKY_SETTINGS } from "./SkyControls";

const capability = {
  id: "bw_channels",
  title: "黑白",
  group: "global",
  status: "alternative-model",
  readiness: {
    status: "runtime-ready",
    reason: "ready",
    mode: "development",
    required_models: [],
    conditional_models: [],
    runnable_models: [],
    missing_or_blocked_models: [],
    parity: "pending",
  },
};
const cropSettings = { box: [0, 0, 1, 1] as [number, number, number, number], ratio: "original" as const, rotation: 0, straighten: 0, flipX: false, flipY: false };

function renderPanel() {
  const onApply = vi.fn();
  render(<ToolPanel
    amount={0.4}
    assetId=""
    skySettings={DEFAULT_SKY_SETTINGS}
    busy={false}
    groups={[{ id: "essentials", label: "基本功能", tone: "essential", capabilities: ["bw_channels"] }]}
    visuals={{ bw_channels: { icon: "mono", ai_badge: false } }}
    items={[capability]}
    onAmountChange={vi.fn()}
    onDenoiseLevelChange={vi.fn()}
    onApply={onApply}
    onAssetChange={vi.fn()}
    onSkySettingChange={vi.fn()}
    onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }}
    selected="bw_channels"
    colorAssets={[]}
    colorAssetId=""
    onColorAssetChange={vi.fn()}
    strokesCount={0}
    brushRadius={0.04}
    onBrushRadiusChange={vi.fn()}
    onClearStrokes={vi.fn()}
    lutAssets={[]}
    lutAssetId=""
    onLutAssetChange={vi.fn()}
    skyAssets={[]}
    cropSettings={cropSettings}
    onCropSettingsChange={vi.fn()}
  />);
  fireEvent.click(screen.getByRole("button", { name: "黑白" }));
  return onApply;
}

test("black and white channel controls stay disabled until conversion", () => {
  const onApply = renderPanel();

  expect(screen.getByRole("slider", { name: /^红色亮度/ })).toBeDisabled();
  expect(screen.getByRole("tab", { name: "亮度" })).toBeDisabled();
  expect(screen.getByRole("tab", { name: "饱和度" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "应用" })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "转换为黑白" }));

  expect(screen.getByRole("slider", { name: /^红色亮度/ })).toBeEnabled();
  expect(screen.getByRole("tab", { name: "亮度" })).toBeEnabled();
  expect(screen.getByRole("tab", { name: "饱和度" })).toBeEnabled();
  fireEvent.click(screen.getByRole("tab", { name: "饱和度" }));
  expect(screen.getByRole("slider", { name: /^红色饱和度/ })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "应用" }));
  expect(onApply).toHaveBeenCalledOnce();
  expect(onApply).toHaveBeenCalledWith();
});

test("does not expose capabilities outside the configured local scope", () => {
  render(<ToolPanel
    amount={0.4}
    assetId=""
    skySettings={DEFAULT_SKY_SETTINGS}
    busy={false}
    groups={[{ id: "essentials", label: "基本功能", tone: "essential", capabilities: ["bw_channels"] }]}
    visuals={{}}
    items={[capability, { ...capability, id: "super_resolution", title: "提升分辨率 AI" }]}
    onAmountChange={vi.fn()}
    onDenoiseLevelChange={vi.fn()}
    onApply={vi.fn()}
    onAssetChange={vi.fn()}
    onSkySettingChange={vi.fn()}
    onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }}
    selected="bw_channels"
    colorAssets={[]}
    colorAssetId=""
    onColorAssetChange={vi.fn()}
    strokesCount={0}
    brushRadius={0.04}
    onBrushRadiusChange={vi.fn()}
    onClearStrokes={vi.fn()}
    lutAssets={[]}
    lutAssetId=""
    onLutAssetChange={vi.fn()}
    skyAssets={[]}
    cropSettings={cropSettings}
    onCropSettingsChange={vi.fn()}
  />);

  expect(screen.getByRole("button", { name: "黑白" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /提升分辨率/ })).not.toBeInTheDocument();
  expect(screen.queryByText("更多工具")).not.toBeInTheDocument();
});

test("denoise opens with the native recommended middle profile", () => {
  const onDenoiseLevelChange = vi.fn();
  render(<ToolPanel
    amount={0.4}
    assetId=""
    skySettings={DEFAULT_SKY_SETTINGS}
    busy={false}
    groups={[{ id: "extensions", label: "图像质量", tone: "quality", capabilities: ["denoise"] }]}
    visuals={{ denoise: { icon: "quality", ai_badge: true } }}
    items={[{ ...capability, id: "denoise", title: "降噪 AI" }]}
    onAmountChange={vi.fn()}
    onDenoiseLevelChange={onDenoiseLevelChange}
    onApply={vi.fn()}
    onAssetChange={vi.fn()}
    onSkySettingChange={vi.fn()}
    onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }}
    selected="denoise"
    colorAssets={[]}
    colorAssetId=""
    onColorAssetChange={vi.fn()}
    strokesCount={0}
    brushRadius={0.04}
    onBrushRadiusChange={vi.fn()}
    onClearStrokes={vi.fn()}
    lutAssets={[]}
    lutAssetId=""
    onLutAssetChange={vi.fn()}
    skyAssets={[]}
    cropSettings={cropSettings}
    onCropSettingsChange={vi.fn()}
  />);
  fireEvent.click(screen.getByRole("button", { name: "降噪AI" }));
  expect(screen.getByText("建议：对此图像使用 中等调整")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "中等" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("slider", { name: /^光度降噪/ })).toHaveValue("1");
  expect(screen.getByRole("slider", { name: /^详细信息/ })).toHaveValue("0.5");
  expect(screen.getByRole("slider", { name: /^锐度/ })).toHaveValue("0.5");
  expect(screen.getByRole("slider", { name: "强度" })).toHaveValue("0.4");
  expect(screen.queryByRole("slider", { name: "不透明度" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "应用" })).toBeEnabled();
  fireEvent.click(screen.getByRole("radio", { name: "中等" }));
  expect(onDenoiseLevelChange).toHaveBeenCalledWith("middle");
});

test("crop opens the native composition and transform controls", () => {
  const onCropSettingsChange = vi.fn();
  const onStraightenActiveChange = vi.fn();
  const onExpandedChange = vi.fn();
  const onApply = vi.fn();
  render(<ToolPanel
    amount={0.4} assetId="" skySettings={DEFAULT_SKY_SETTINGS} busy={false}
    groups={[{ id: "common", label: "通用", tone: "common", capabilities: ["crop_ai"] }]}
    visuals={{ crop_ai: { icon: "crop", ai_badge: true } }}
    items={[{ ...capability, id: "crop_ai", title: "裁切 AI" }]}
    onAmountChange={vi.fn()} onDenoiseLevelChange={vi.fn()} onApply={onApply}
    onAssetChange={vi.fn()} onSkySettingChange={vi.fn()} onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }} selected="crop_ai"
    colorAssets={[]} colorAssetId="" onColorAssetChange={vi.fn()} strokesCount={0}
    brushRadius={0.04} onBrushRadiusChange={vi.fn()} onClearStrokes={vi.fn()}
    lutAssets={[]} lutAssetId="" onLutAssetChange={vi.fn()} skyAssets={[]}
    cropSettings={cropSettings} onCropSettingsChange={onCropSettingsChange}
    straightenActive={false} onStraightenActiveChange={onStraightenActiveChange}
    onExpandedChange={onExpandedChange}
  />);
  fireEvent.click(screen.getByRole("button", { name: "裁切AI" }));
  expect(screen.getByRole("combobox", { name: "裁切比例" })).toHaveValue("original");
  expect(screen.getByRole("button", { name: /构图/ })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "水平翻转" }));
  expect(onCropSettingsChange).toHaveBeenCalledWith({ flipX: true });
  fireEvent.click(screen.getByRole("button", { name: "水平对齐" }));
  expect(onStraightenActiveChange).toHaveBeenCalledWith(true);
  expect(screen.queryByRole("slider", { name: "水平对齐角度" })).not.toBeInTheDocument();
  expect(screen.queryByRole("slider", { name: "强度" })).not.toBeInTheDocument();
  expect(screen.queryByRole("slider", { name: "不透明度" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "应用" }));
  expect(onApply).toHaveBeenCalledOnce();
  expect(onStraightenActiveChange).toHaveBeenLastCalledWith(false);
  expect(onExpandedChange).toHaveBeenLastCalledWith(undefined);
  expect(screen.getByRole("button", { name: "裁切AI" })).toHaveAttribute("aria-expanded", "false");
});

test("neon exposes positioned brush and every canonical parameter", () => {
  const onNeonSettingChange = vi.fn();
  render(<ToolPanel
    amount={0.4} assetId="" skySettings={DEFAULT_SKY_SETTINGS} busy={false}
    groups={[{ id: "creative", label: "创意", tone: "creative", capabilities: ["new_neon_light"] }]}
    visuals={{ new_neon_light: { icon: "adjust", ai_badge: false } }}
    items={[{ ...capability, id: "new_neon_light", title: "霓虹灯" }]}
    onAmountChange={vi.fn()} onDenoiseLevelChange={vi.fn()} onApply={vi.fn()}
    onAssetChange={vi.fn()} onSkySettingChange={vi.fn()} onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }} selected="new_neon_light"
    colorAssets={[]} colorAssetId="" onColorAssetChange={vi.fn()} strokesCount={1}
    brushRadius={0.04} onBrushRadiusChange={vi.fn()} onClearStrokes={vi.fn()}
    neonSettings={{ spread: 0.6, atmosphere: 0.05, hue: 270, whiteness: 0.3 }}
    onNeonSettingChange={onNeonSettingChange}
    lutAssets={[]} lutAssetId="" onLutAssetChange={vi.fn()} skyAssets={[]}
    cropSettings={cropSettings} onCropSettingsChange={vi.fn()}
  />);

  fireEvent.click(screen.getByRole("button", { name: "霓虹灯" }));
  expect(screen.getByRole("slider", { name: "画笔大小" })).toBeEnabled();
  expect(screen.getByRole("slider", { name: "扩散" })).toHaveValue("0.6");
  expect(screen.getByRole("slider", { name: "氛围" })).toHaveValue("0.05");
  expect(screen.getByRole("slider", { name: "色相" })).toHaveValue("270");
  expect(screen.getByRole("slider", { name: "白度" })).toHaveValue("0.3");
  expect(screen.getByRole("slider", { name: "强度" })).toHaveValue("0.4");
  expect(screen.queryByRole("slider", { name: "不透明度" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("slider", { name: "色相" }), { target: { value: "280" } });
  expect(onNeonSettingChange).toHaveBeenCalledWith("hue", 280);
});

test("bokeh exposes the native shape choices", () => {
  const onBokehShapeChange = vi.fn();
  render(<ToolPanel
    amount={0.4} assetId="" skySettings={DEFAULT_SKY_SETTINGS} busy={false}
    groups={[{ id: "portrait", label: "人像", tone: "portrait", capabilities: ["bokeh_ai"] }]}
    visuals={{ bokeh_ai: { icon: "portrait", ai_badge: true } }}
    items={[{ ...capability, id: "bokeh_ai", title: "散景 AI" }]}
    onAmountChange={vi.fn()} onDenoiseLevelChange={vi.fn()} onApply={vi.fn()}
    onAssetChange={vi.fn()} onSkySettingChange={vi.fn()} onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }} selected="bokeh_ai"
    colorAssets={[]} colorAssetId="" onColorAssetChange={vi.fn()} strokesCount={0}
    brushRadius={0.04} onBrushRadiusChange={vi.fn()} onClearStrokes={vi.fn()}
    bokehShape="circle" onBokehShapeChange={onBokehShapeChange}
    lutAssets={[]} lutAssetId="" onLutAssetChange={vi.fn()} skyAssets={[]}
    cropSettings={cropSettings} onCropSettingsChange={vi.fn()}
  />);

  fireEvent.click(screen.getByRole("button", { name: "散景AI" }));
  expect(screen.getByRole("radio", { name: "圆环" })).toHaveAttribute("aria-checked", "true");
  fireEvent.click(screen.getByRole("radio", { name: "实心圆" }));
  expect(onBokehShapeChange).toHaveBeenCalledWith("filled_circle");
});

test("sky replacement exposes only its canonical matrix and no generic strength", () => {
  render(<ToolPanel
    amount={0.4} assetId="sky-1" skySettings={DEFAULT_SKY_SETTINGS} busy={false}
    groups={[{ id: "landscape", label: "风景", tone: "landscape", capabilities: ["sky_replace"] }]}
    visuals={{ sky_replace: { icon: "sky", ai_badge: true } }}
    items={[{ ...capability, id: "sky_replace", title: "天空 AI" }]}
    onAmountChange={vi.fn()} onDenoiseLevelChange={vi.fn()} onApply={vi.fn()}
    onAssetChange={vi.fn()} onSkySettingChange={vi.fn()} onSelect={vi.fn()}
    project={{ source: { path: "/fixture.jpg" }, layers: [], edits: [] }} selected="sky_replace"
    colorAssets={[]} colorAssetId="" onColorAssetChange={vi.fn()} strokesCount={0}
    brushRadius={0.04} onBrushRadiusChange={vi.fn()} onClearStrokes={vi.fn()}
    lutAssets={[]} lutAssetId="" onLutAssetChange={vi.fn()}
    skyAssets={[{ id: "sky-1", family: "sky", filename: "Blue Sky.jpg", path: "sky/Blue Sky.jpg" }]}
    cropSettings={cropSettings} onCropSettingsChange={vi.fn()}
  />);

  fireEvent.click(screen.getByRole("button", { name: "天空AI" }));
  expect(screen.queryByRole("slider", { name: "强度" })).not.toBeInTheDocument();
  expect(screen.queryByRole("slider", { name: "不透明度" })).not.toBeInTheDocument();
  expect(screen.getByText("修复细节")).toBeInTheDocument();
});
