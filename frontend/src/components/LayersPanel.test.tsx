import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { LayerMaterialGroup, Project } from "../api";
import { LayerInspector, LayersPanel } from "./LayersPanel";

const groups: LayerMaterialGroup[] = [
  {
    id: "stardust",
    label: "星尘散景",
    collection_id: "collection",
    preview_limit: 1,
    count: 1,
    items: [
      {
        id: "champagne",
        name: "Champagne",
        path: "material.png",
        blend_mode: "screen",
        opacity: 1,
      },
    ],
  },
];

const project: Project = {
  source: { path: "source.png" },
  edits: [],
  layers: [
    {
      id: "layer",
      asset_id: "champagne",
      path: "material.png",
      name: "Champagne",
      source_kind: "library",
      visible: true,
      opacity: 1,
      blend_mode: "screen",
      scale: 1,
      offset_x: 0,
      offset_y: 0,
      rotation: 0,
      flip_x: false,
      flip_y: false,
    },
  ],
};

function props(overrides: Partial<ComponentProps<typeof LayersPanel>> = {}) {
  return {
    busy: false,
    groups,
    project,
    projectId: "project",
    sourceUrl: "/source",
    onAddLayer: vi.fn(),
    onAddMaterial: vi.fn(),
    onDeleteLayer: vi.fn(),
    onReorderLayers: vi.fn(),
    onSelectLayer: vi.fn(),
    onUpdateLayer: vi.fn(),
    ...overrides,
  };
}

describe("LayersPanel", () => {
  it("opens the free material library and applies one material", () => {
    const onAddMaterial = vi.fn();
    render(<LayersPanel {...props({ onAddMaterial })} />);

    fireEvent.click(screen.getByRole("button", { name: "添加图层" }));

    expect(screen.getByText("加载图像")).toBeInTheDocument();
    expect(screen.getByText("星尘散景")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Champagne" }));
    expect(onAddMaterial).toHaveBeenCalledWith("champagne");
  });

  it("matches the native summary controls and commits opacity", () => {
    const onUpdateLayer = vi.fn();
    render(<LayerInspector busy={false} layer={project.layers[0]} onUpdate={(changes) => onUpdateLayer("layer", changes)} />);

    const opacity = screen.getByRole("slider");
    fireEvent.change(opacity, { target: { value: "0.5" } });
    fireEvent.pointerUp(opacity);

    expect(screen.getByRole("tab", { name: "摘要资讯" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "适合" })).toBeInTheDocument();
    expect(onUpdateLayer).toHaveBeenCalledWith("layer", { opacity: 0.5 });
  });

  it("opens the mask tab and uploads a layer mask", () => {
    const onUploadMask = vi.fn();
    render(<LayerInspector busy={false} layer={project.layers[0]} projectId="project" onUpdate={vi.fn()} onUploadMask={onUploadMask} />);

    fireEvent.click(screen.getByRole("tab", { name: "遮罩" }));
    const file = new File(["mask"], "mask.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("加载遮罩"), { target: { files: [file] } });

    expect(screen.getByRole("tab", { name: "遮罩" })).toHaveAttribute("aria-selected", "true");
    expect(onUploadMask).toHaveBeenCalledWith(file);
  });

  it("exposes the canonical brush parameters for a non-destructive mask stroke", () => {
    const onMaskBrushActiveChange = vi.fn();
    const onMaskBrushSettingsChange = vi.fn();
    render(<LayerInspector
      busy={false}
      layer={project.layers[0]}
      projectId="project"
      onUpdate={vi.fn()}
      maskBrushActive={false}
      maskBrushSettings={{ size: 80, softness: 24, strength: 70 }}
      onMaskBrushActiveChange={onMaskBrushActiveChange}
      onMaskBrushSettingsChange={onMaskBrushSettingsChange}
    />);

    fireEvent.click(screen.getByRole("tab", { name: "遮罩" }));
    fireEvent.click(screen.getByRole("button", { name: "画笔" }));

    expect(onMaskBrushActiveChange).toHaveBeenCalledWith(true);
    expect(screen.getByRole("slider", { name: "画笔大小" })).toHaveValue("80");
    expect(screen.getByRole("slider", { name: "画笔柔和度" })).toHaveValue("24");
    expect(screen.getByRole("slider", { name: "画笔强度" })).toHaveValue("70");
  });

  it("updates and removes an attached mask", () => {
    const mask = {
      id: "mask",
      path: "mask.png",
      owner_type: "layer" as const,
      owner_id: "layer",
      width: 20,
      height: 10,
      source: "imported",
      inverted: false,
      density: 1,
      feather: 0,
      sha256: "abc",
      version: 1,
    };
    const onUpdateMask = vi.fn();
    const onDeleteMask = vi.fn();
    render(<LayerInspector busy={false} layer={{ ...project.layers[0], mask_artifact: mask.id }} mask={mask} projectId="project" onUpdate={vi.fn()} onUpdateMask={onUpdateMask} onDeleteMask={onDeleteMask} />);

    fireEvent.click(screen.getByRole("tab", { name: "遮罩" }));
    fireEvent.click(screen.getByLabelText("反转遮罩"));
    fireEvent.click(screen.getByRole("button", { name: "删除遮罩" }));

    expect(screen.getByAltText("当前图层遮罩")).toHaveAttribute("src", "/api/v1/projects/project/masks/mask/preview");
    expect(onUpdateMask).toHaveBeenCalledWith("mask", { inverted: true });
    expect(onDeleteMask).toHaveBeenCalledWith("mask");
  });

  it("keeps layer actions disabled while a mutation is running", () => {
    render(<LayersPanel {...props({ busy: true })} />);

    expect(screen.getByRole("button", { name: "添加图层" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "隐藏图层" })).toBeDisabled();
  });

  it("exposes hide, show, and remove through the native layer context menu", () => {
    const onUpdateLayer = vi.fn();
    const onDeleteLayer = vi.fn();
    render(<LayersPanel {...props({ onUpdateLayer, onDeleteLayer })} />);

    fireEvent.contextMenu(document.querySelector(".layer-stack-row:not(.source)")!);
    fireEvent.click(screen.getByRole("menuitem", { name: "Hide Layer" }));

    expect(onUpdateLayer).toHaveBeenCalledWith("layer", { visible: false });

    fireEvent.contextMenu(document.querySelector(".layer-stack-row:not(.source)")!);
    fireEvent.click(screen.getByRole("menuitem", { name: "移除图层" }));
    expect(onDeleteLayer).toHaveBeenCalledWith("layer");
  });

  it("selects a layer and exposes the native asset entry", () => {
    const onSelectLayer = vi.fn();
    const onAddLayer = vi.fn();
    render(<LayersPanel {...props({ onAddLayer, onSelectLayer })} />);

    fireEvent.click(screen.getByRole("button", { name: "Champagne内置素材" }));
    expect(onSelectLayer).toHaveBeenCalledWith("layer");

    fireEvent.click(screen.getByRole("button", { name: "添加图层" }));
    const file = new File(["layer"], "local-layer.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("添加本地素材"), { target: { files: [file] } });
    expect(onAddLayer).toHaveBeenCalledWith(file);
  });

  it("reorders layers with a pointer drag gesture", () => {
    const onReorderLayers = vi.fn();
    const second = { ...project.layers[0], id: "layer-2", name: "Fiesta" };
    render(<LayersPanel {...props({ project: { ...project, layers: [project.layers[0], second] }, onReorderLayers })} />);

    const rows = document.querySelectorAll(".layer-stack-row:not(.source)");
    fireEvent.pointerDown(rows[0]);
    fireEvent.pointerUp(rows[1]);

    expect(onReorderLayers).toHaveBeenCalledWith(["layer-2", "layer"]);
  });
});
