import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EditorHeader } from "./EditorHeader";

describe("EditorHeader", () => {
  it("does not leak single-image filename or export actions into a multi-image workflow", () => {
    render(<EditorHeader
      busy={false}
      mode="workflow"
      projectId="project-1"
      filename="source.jpg"
      workflowTitle="HDR 合并"
      onUpload={vi.fn()}
      onCatalog={vi.fn()}
      onExport={vi.fn()}
    />);

    expect(screen.getByText("HDR 合并")).toBeInTheDocument();
    expect(screen.queryByText("单个图像编辑")).not.toBeInTheDocument();
    expect(screen.queryByText("source.jpg")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "导出" })).not.toBeInTheDocument();
  });

  it("provides a real catalog navigation action", () => {
    const onCatalog = vi.fn();
    render(<EditorHeader busy={false} mode="editor" onUpload={vi.fn()} onCatalog={onCatalog} onExport={vi.fn()} />);
    screen.getByRole("button", { name: "目录" }).click();
    expect(onCatalog).toHaveBeenCalledTimes(1);
  });
});
