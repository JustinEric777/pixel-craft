import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EditHistoryPanel } from "./EditHistoryPanel";
import { InfoPanel } from "./InfoPanel";
import { MorePanel } from "./MorePanel";

const project = {
  source: { path: "/photos/source.jpg", width: 1200, height: 800 },
  layers: [],
  edits: [{ id: "edit-1", effect: "details", parameters: { amount: 0.4 } }],
  metadata: { camera_model: "Camera" },
};

describe("editor side panels", () => {
  it("renders and deletes real project edits", () => {
    const onDeleteEdit = vi.fn();
    const onUpdateEdit = vi.fn();
    render(<EditHistoryPanel busy={false} items={[{ id: "details", title: "详细信息", group: "global", status: "implemented" }]} project={project} onDeleteEdit={onDeleteEdit} onUpdateEdit={onUpdateEdit} />);

    fireEvent.click(screen.getByRole("button", { name: "详细信息编辑 1" }));
    expect(screen.getByLabelText("详细信息参数")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider", { name: "强度" }), { target: { value: "0.6" } });
    fireEvent.click(screen.getByRole("button", { name: "应用" }));
    expect(onUpdateEdit).toHaveBeenCalledWith("edit-1", "details", { amount: 0.6 });
    fireEvent.click(screen.getByRole("button", { name: "删除详细信息" }));
    expect(onDeleteEdit).toHaveBeenCalledWith("edit-1");
  });

  it("shows the native empty state for the current photo", () => {
    render(<EditHistoryPanel busy={false} items={[]} project={{ ...project, edits: [] }} onDeleteEdit={vi.fn()} onUpdateEdit={vi.fn()} />);
    expect(screen.getByText("没有编辑")).toBeInTheDocument();
  });

  it("routes only the in-scope local multi-image workflows", () => {
    const onOpenWorkflow = vi.fn();
    render(<MorePanel onOpenWorkflow={onOpenWorkflow} />);

    fireEvent.click(screen.getByRole("button", { name: /HDR 合并/ }));
    expect(onOpenWorkflow).toHaveBeenCalledWith("hdr_merge");
    expect(screen.queryByText("提升分辨率")).not.toBeInTheDocument();
    expect(screen.queryByText("修复")).not.toBeInTheDocument();
    expect(screen.queryByText("生成式擦除")).not.toBeInTheDocument();
  });

  it("shows only available image metadata without inventing fields", () => {
    render(<InfoPanel filename="source.jpg" project={project} />);
    expect(screen.getByText("1200 × 800")).toBeInTheDocument();
    expect(screen.getByText(/Camera: Camera/)).toBeInTheDocument();
    expect(screen.getByText(/Lens: 无数据/)).toBeInTheDocument();
  });
});
