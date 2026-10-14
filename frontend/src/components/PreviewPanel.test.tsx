import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PreviewPanel } from "./PreviewPanel";

function renderPanel() {
  render(
    <PreviewPanel
      analysisActive={false}
      busy={false}
      onAnalyze={vi.fn()}
      onCancelAnalysis={vi.fn()}
      onHistory={vi.fn()}
      onExport={vi.fn()}
      onReset={vi.fn()}
      onToggleBefore={vi.fn()}
      onPreviewReady={vi.fn()}
      onUpload={vi.fn()}
      previewNonce={1}
      projectId="project"
      showBefore={false}
      sourceUrl="/source"
      mode="edit"
      strokes={[]}
      brushRadius={0.04}
      onStrokesChange={vi.fn()}
    />,
  );
  const image = screen.getByAltText("编辑预览");
  fireEvent.load(image);
  return image;
}

describe("PreviewPanel viewport interactions", () => {
  it("keeps the native empty-state file input hidden", () => {
    render(
      <PreviewPanel
        analysisActive={false}
        busy={false}
        onAnalyze={vi.fn()}
        onCancelAnalysis={vi.fn()}
        onHistory={vi.fn()}
        onExport={vi.fn()}
        onReset={vi.fn()}
        onToggleBefore={vi.fn()}
        onPreviewReady={vi.fn()}
        onUpload={vi.fn()}
        previewNonce={1}
        showBefore={false}
        mode="edit"
        strokes={[]}
        brushRadius={0.04}
        onStrokesChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("添加照片").querySelector("input")).toHaveAttribute("hidden");
  });

  it("zooms, pans, and restores fit-to-view without mutating the project", () => {
    const image = renderPanel();
    const canvas = image.closest(".canvas");
    const stage = image.closest(".image-stage") as HTMLElement;

    fireEvent.wheel(canvas!, { deltaY: -100 });
    expect(screen.getByRole("button", { name: "适合视图" })).toHaveTextContent("110%");

    fireEvent.pointerDown(image, { pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(image, { pointerId: 1, clientX: 125, clientY: 118 });
    fireEvent.pointerUp(image, { pointerId: 1, clientX: 125, clientY: 118 });
    expect(stage).toHaveAttribute("data-pan-x", "25");
    expect(stage).toHaveAttribute("data-pan-y", "18");

    fireEvent.click(screen.getByRole("button", { name: "适合视图" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "适合屏幕" }));
    expect(screen.getByRole("button", { name: "适合视图" })).toHaveTextContent("100%");
    expect(stage).toHaveStyle("transform: translate(0px, 0px) scale(1)");
  });

  it("selects an exact 200 percent zoom from the native-style menu", () => {
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: "适合视图" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "200%" }));

    expect(screen.getByRole("button", { name: "适合视图" })).toHaveTextContent("200%");
  });

  it("shows the source only while the compare control is held", () => {
    const onToggleBefore = vi.fn();
    render(
      <PreviewPanel
        analysisActive={false}
        busy={false}
        onAnalyze={vi.fn()}
        onCancelAnalysis={vi.fn()}
        onHistory={vi.fn()}
        onExport={vi.fn()}
        onReset={vi.fn()}
        onToggleBefore={onToggleBefore}
        onPreviewReady={vi.fn()}
        onUpload={vi.fn()}
        previewNonce={1}
        projectId="project"
        showBefore={false}
        sourceUrl="/source"
        mode="edit"
        strokes={[]}
        brushRadius={0.04}
        onStrokesChange={vi.fn()}
      />,
    );
    const compare = screen.getByTitle("前后对比");

    fireEvent.pointerDown(compare);
    fireEvent.pointerUp(compare);

    expect(onToggleBefore).toHaveBeenCalledTimes(2);
  });

  it("measures crop straightening on the overlay that receives preview input", () => {
    const onStraightenComplete = vi.fn();
    render(
      <PreviewPanel
        analysisActive={false}
        busy={false}
        onAnalyze={vi.fn()}
        onCancelAnalysis={vi.fn()}
        onHistory={vi.fn()}
        onExport={vi.fn()}
        onReset={vi.fn()}
        onToggleBefore={vi.fn()}
        onPreviewReady={vi.fn()}
        onUpload={vi.fn()}
        previewNonce={1}
        projectId="project"
        showBefore={false}
        sourceUrl="/source"
        mode="edit"
        strokes={[]}
        brushRadius={0.04}
        onStrokesChange={vi.fn()}
        cropActive
        straightenActive
        onStraightenComplete={onStraightenComplete}
      />,
    );
    fireEvent.load(screen.getByAltText("编辑预览"));
    const overlay = screen.getByLabelText("裁切区域");

    fireEvent.pointerDown(overlay, { pointerId: 7, clientX: 100, clientY: 100 });
    fireEvent.pointerUp(overlay, { pointerId: 7, clientX: 300, clientY: 110 });

    expect(onStraightenComplete).toHaveBeenCalledWith(2.9);
  });

  it("keeps every point from a rapid brush gesture", () => {
    const onStrokesChange = vi.fn();
    render(
      <PreviewPanel
        analysisActive={false}
        busy={false}
        onAnalyze={vi.fn()}
        onCancelAnalysis={vi.fn()}
        onHistory={vi.fn()}
        onExport={vi.fn()}
        onReset={vi.fn()}
        onToggleBefore={vi.fn()}
        onPreviewReady={vi.fn()}
        onUpload={vi.fn()}
        previewNonce={1}
        projectId="project"
        showBefore={false}
        sourceUrl="/source"
        mode="edit"
        interactiveTool="mask"
        strokes={[]}
        brushRadius={0.08}
        onStrokesChange={onStrokesChange}
      />,
    );
    const image = screen.getByAltText("编辑预览");
    fireEvent.load(image);
    Object.defineProperty(image, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 400, height: 300 }) });

    fireEvent.pointerDown(image, { pointerId: 3, clientX: 40, clientY: 60 });
    fireEvent.pointerMove(image, { pointerId: 3, clientX: 120, clientY: 100 });
    fireEvent.pointerMove(image, { pointerId: 3, clientX: 200, clientY: 140 });
    fireEvent.pointerUp(image, { pointerId: 3, clientX: 200, clientY: 140 });

    expect(onStrokesChange).toHaveBeenCalledOnce();
    expect(onStrokesChange.mock.calls[0][0][0].points).toHaveLength(3);
  });
});
