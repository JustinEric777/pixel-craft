import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import type { Project } from "../api";
import { CatalogWorkspace } from "./CatalogWorkspace";

const project: Project = {
  source: { path: "source.jpg", width: 1280, height: 960 },
  edits: [],
  layers: [],
};

const record = {
  asset_id: "asset",
  project_id: "project",
  filename: "source.jpg",
  path: "source.jpg",
  size: 1200,
  added_at: "2026-08-28T00:00:00Z",
  edit_count: 0,
  rating: 0,
};

function props(overrides: Partial<ComponentProps<typeof CatalogWorkspace>> = {}) {
  return {
    collectionName: "夏日户外拍照",
    project,
    records: [],
    busy: false,
    onUpload: vi.fn(),
    onOpen: vi.fn(),
    onOpenPanel: vi.fn(),
    onOpenWorkflow: vi.fn(),
    onUpdateRecord: vi.fn(),
    onExportRecord: vi.fn(),
    ...overrides,
  };
}

describe("CatalogWorkspace", () => {
  it("selects all photos by default", () => {
    render(<CatalogWorkspace {...props()} />);

    expect(screen.getByRole("button", { name: /所有照片/ })).toHaveClass("selected");
  });

  it("does not expose excluded enhancement tools", () => {
    render(<CatalogWorkspace {...props()} />);

    expect(screen.queryByText("增强工具")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提升分辨率" })).not.toBeInTheDocument();
  });

  it("opens a multi-image workflow from the catalog folder section", () => {
    const onOpenWorkflow = vi.fn();
    render(<CatalogWorkspace {...props({ onOpenWorkflow })} />);

    fireEvent.click(screen.getByRole("button", { name: "HDR Merge" }));

    expect(onOpenWorkflow).toHaveBeenCalledWith("hdr_merge");
  });

  it("exposes native photo context operations and persists a rating", () => {
    const onUpdateRecord = vi.fn();
    render(<CatalogWorkspace {...props({ records: [record], onUpdateRecord })} />);

    fireEvent.contextMenu(screen.getByRole("article"), { clientX: 80, clientY: 90 });
    expect(screen.getByRole("menu", { name: "source.jpg 操作" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "★★★★★" }));

    expect(onUpdateRecord).toHaveBeenCalledWith(record, { rating: 5 });
  });

  it("renders the persisted catalog rotation in the photo grid", () => {
    render(<CatalogWorkspace {...props({ records: [{ ...record, rotation: 90 }] })} />);

    expect(screen.getByRole("img", { name: "source.jpg" })).toHaveStyle({
      transform: "rotate(90deg)",
    });
  });

  it("opens the selected photo in the editor on double click", () => {
    const onOpenPanel = vi.fn();
    render(<CatalogWorkspace {...props({ records: [record], onOpenPanel })} />);

    fireEvent.doubleClick(screen.getByRole("article"));

    expect(onOpenPanel).toHaveBeenCalledWith(record, "tools");
  });

  it("exposes the matching folder context menu", () => {
    render(<CatalogWorkspace {...props()} />);

    fireEvent.contextMenu(screen.getByRole("button", { name: "Focus Stacking" }), { clientX: 30, clientY: 50 });

    expect(screen.getByRole("menu", { name: "文件夹操作" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "导入图片到该文件夹…" })).toBeInTheDocument();
  });
});
