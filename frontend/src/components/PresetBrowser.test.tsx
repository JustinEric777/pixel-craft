import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Preset } from "../api";
import { PresetBrowser } from "./PresetBrowser";

const preset: Preset = {
  id: "local-canonical",
  name: "Canonical Details",
  category: "本地预设",
  status: "local-imported",
  edit_graph: [{ effect: "details", parameters: { amount: 0.35 } }],
};

describe("PresetBrowser", () => {
  it("previews a preset before enabling the explicit apply action", () => {
    const onPreview = vi.fn();
    const onApply = vi.fn();
    const { rerender } = render(
      <PresetBrowser projectId="project" presets={[preset]} busy={false} onPreview={onPreview} onApply={onApply} onImport={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开本地预设预设" }));
    fireEvent.click(screen.getByRole("button", { name: "Canonical Details" }));
    expect(onPreview).toHaveBeenCalledWith(preset);
    expect(screen.getByRole("button", { name: "应用预设" })).toBeDisabled();

    rerender(
      <PresetBrowser projectId="project" presets={[preset]} selectedPresetId={preset.id} busy={false} onPreview={onPreview} onApply={onApply} onImport={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "应用预设" }));
    expect(onApply).toHaveBeenCalledOnce();
  });
});
