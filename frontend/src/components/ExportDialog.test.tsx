import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { defaultFilename, ExportDialog, type ExportSettings } from "./ExportDialog";

function ControlledExportDialog({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState<ExportSettings>({
    value: defaultFilename("portrait.raw"),
    format: "png",
    width: 1080,
    profile: "sRGB",
  });
  return <ExportDialog
    settings={settings}
    onSettingsChange={setSettings}
    hasRestorableEdit
    projectId="project one"
    onClose={onClose}
  />;
}

test("exports the selected format, width and color profile", () => {
  const onClose = vi.fn();
  render(
    <ControlledExportDialog onClose={onClose} />,
  );

  fireEvent.change(screen.getByLabelText("导出格式"), { target: { value: "jpeg" } });
  fireEvent.change(screen.getByLabelText("导出宽度"), { target: { value: "2048" } });

  const exportLink = screen.getByRole("link", { name: "导出" });
  expect(exportLink).toHaveAttribute("download", "portrait-edited.jpg");
  expect(exportLink).toHaveAttribute(
    "href",
    "/api/v1/projects/project one/export?format=jpeg&width=2048&profile=sRGB&filename=portrait-edited.jpg",
  );
  expect(screen.getByLabelText("导出颜色配置")).toBeEnabled();

  fireEvent.click(exportLink);
  expect(onClose).toHaveBeenCalledOnce();
});
