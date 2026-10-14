import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkspaceRail } from "./WorkspaceRail";

describe("WorkspaceRail", () => {
  it("exposes every native editor panel without disabled placeholders", () => {
    const onPanelChange = vi.fn();
    render(<WorkspaceRail panel="tools" panelOpen onPanelChange={onPanelChange} />);

    for (const label of ["预设", "工具", "编辑", "更多", "信息"]) {
      const button = screen.getByRole("button", { name: label });
      expect(button).toBeEnabled();
      fireEvent.click(button);
    }

    expect(onPanelChange.mock.calls).toEqual([
      ["presets"],
      ["tools"],
      ["edits"],
      ["more"],
      ["info"],
    ]);
    expect(screen.getByRole("button", { name: "工具" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "帮助" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "升级" })).not.toBeInTheDocument();
  });
});
