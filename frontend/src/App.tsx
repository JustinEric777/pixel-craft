import { useEffect, useState } from "react";
import {
  addEdit,
  addLayer,
  addLayerMaterial,
  applyPreset,
  assetCatalog,
  catalog,
  capabilities,
  configuration,
  type AssetRecord,
  type BrushStroke,
  type Capability,
  deleteEdit,
  deleteLayer,
  deleteMask,
  layerMaterials,
  type LayerMaterialGroup,
  type LayerUpdate,
  type MaskUpdate,
  type MaskBrushSettings,
  paintMask,
  reorderLayers,
  updateLayer,
  updateMask,
  uploadMask,
  updateEdit,
  updateCatalogAsset,
  redo,
  resetProject,
  undo,
  upload,
  type Project,
  health,
  type RuntimeHealth,
  type ExecutionTrace,
  executionTrace,
  getProject,
  importPreset,
  presetPreviewUrl,
  sourceImageUrl,
  presets,
  type CatalogRecord,
  type Preset,
  type ToolGroup,
  addWorkflowFrame,
  analyzeWorkflow,
  createWorkflow,
  type WorkflowKind,
  workflowPreview,
  workflowExport,
} from "./api";
import { EditorHeader } from "./components/EditorHeader";
import { PreviewPanel } from "./components/PreviewPanel";
import { ToolPanel, type BokehShape, type CropSettings } from "./components/ToolPanel";
import { LayersPanel } from "./components/LayersPanel";
import { CatalogWorkspace } from "./components/CatalogWorkspace";
import { PresetBrowser } from "./components/PresetBrowser";
import { DEFAULT_SKY_SETTINGS, toSkyParameters, type SkySettings } from "./components/SkyControls";
import { WorkflowWorkspace } from "./components/WorkflowWorkspace";
import { EditHistoryPanel } from "./components/EditHistoryPanel";
import { InfoPanel } from "./components/InfoPanel";
import { MorePanel } from "./components/MorePanel";
import { WorkspaceRail, type EditorPanel } from "./components/WorkspaceRail";
import { defaultFilename, ExportDialog, type ExportSettings } from "./components/ExportDialog";
import { useAnalysisJob } from "./useAnalysisJob";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function historyActionForKeyboardEvent(event: KeyboardEvent): "undo" | "redo" | undefined {
  if ((!event.metaKey && !event.ctrlKey) || event.altKey || event.key.toLowerCase() !== "z") {
    return undefined;
  }
  if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [contenteditable='true']")) {
    return undefined;
  }
  return event.shiftKey ? "redo" : "undo";
}

export function App() {
  const [projectId, setProjectId] = useState<string>();
  const [sourceUrl, setSourceUrl] = useState<string>();
  const [previewNonce, setPreviewNonce] = useState(0);
  const [selected, setSelected] = useState("color_adjustments");
  const [amount, setAmount] = useState(0.4);
  const [skySettings, setSkySettings] = useState<SkySettings>(DEFAULT_SKY_SETTINGS);
  const [items, setItems] = useState<Capability[]>([]);
  const [skyAssets, setSkyAssets] = useState<AssetRecord[]>([]);
  const [lutAssets, setLutAssets] = useState<AssetRecord[]>([]);
  const [colorAssets, setColorAssets] = useState<AssetRecord[]>([]);
  const [assetId, setAssetId] = useState("");
  const [lutAssetId, setLutAssetId] = useState("");
  const [colorAssetId, setColorAssetId] = useState("");
  const [strokes, setStrokes] = useState<BrushStroke[]>([]);
  const [brushRadius, setBrushRadius] = useState(0.04);
  const [bokehShape, setBokehShape] = useState<BokehShape>("circle");
  const [neonSettings, setNeonSettings] = useState({ spread: 0.6, atmosphere: 0.05, hue: 270, whiteness: 0.3 });
  const [error, setError] = useState<string>();
  const [project, setProject] = useState<Project>();
  const [showBefore, setShowBefore] = useState(false);
  const [pendingAction, setPendingAction] = useState<string>();
  const [workspace, setWorkspace] = useState<"catalog" | "editor" | "workflow">("editor");
  const [editorPanel, setEditorPanel] = useState<EditorPanel>("tools");
  const [runtime, setRuntime] = useState<RuntimeHealth>();
  const [trace, setTrace] = useState<ExecutionTrace>();
  const [catalogRecords, setCatalogRecords] = useState<CatalogRecord[]>([]);
  const [catalogCollection, setCatalogCollection] = useState("");
  const [presetRecords, setPresetRecords] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<Preset>();
  const [toolGroups, setToolGroups] = useState<ToolGroup[]>([]);
  const [capabilityVisuals, setCapabilityVisuals] = useState<Record<string, { icon: string; ai_badge: boolean }>>({});
  const [layerMaterialGroups, setLayerMaterialGroups] = useState<LayerMaterialGroup[]>([]);
  const [selectedLayerId, setSelectedLayerId] = useState<string>();
  const [workflowPreviewUrl, setWorkflowPreviewUrl] = useState<string>();
  const [workflowStatus, setWorkflowStatus] = useState<string>();
  const [workflowId, setWorkflowId] = useState<string>();
  const [workflowKind, setWorkflowKind] = useState<WorkflowKind>("hdr_merge");
  const [editorPanelsOpen, setEditorPanelsOpen] = useState(true);
  const [denoiseLevel, setDenoiseLevel] = useState<"low" | "middle" | "high">("middle");
  const [denoiseSettings, setDenoiseSettings] = useState({ luminosity: 1, details: 0.5, sharpness: 0.5 });
  const [sharpLevel, setSharpLevel] = useState<"low" | "middle" | "high">("middle");
  const [sharpFaceEnhancer, setSharpFaceEnhancer] = useState(false);
  const [expandedTool, setExpandedTool] = useState<string>();
  const [cropSettings, setCropSettings] = useState<CropSettings>({
    box: [0, 0, 1, 1], ratio: "original", rotation: 0, straighten: 0, flipX: false, flipY: false,
  });
  const [cropStraightenActive, setCropStraightenActive] = useState(false);
  const [maskBrushActive, setMaskBrushActive] = useState(false);
  const [maskBrushSettings, setMaskBrushSettings] = useState<MaskBrushSettings>({ size: 80, softness: 24, strength: 70 });
  const [maskStrokes, setMaskStrokes] = useState<BrushStroke[]>([]);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportSettings, setExportSettings] = useState<(ExportSettings & { projectId: string })>();
  const analysisJob = useAnalysisJob(projectId);

  const originalFilename = project?.metadata?.original_filename;
  const projectFilename = typeof originalFilename === "string"
    ? originalFilename
    : project?.source.path.split(/[\\/]/).pop();
  const selectedCatalogRecord = catalogRecords.find((record) => record.project_id === projectId);

  function updateCropSettings(changes: Partial<CropSettings>) {
    setCropSettings((current) => {
      const next = { ...current, ...changes };
      if (!changes.ratio || changes.ratio === "free") return next;
      if (changes.ratio === "original") return { ...next, box: [0, 0, 1, 1] };
      const ratio = { "1:1": 1, "4:3": 4 / 3, "3:2": 3 / 2, "16:9": 16 / 9 }[changes.ratio];
      const sourceWidth = Number(project?.source.width) || 1;
      const sourceHeight = Number(project?.source.height) || 1;
      const normalizedRatio = ratio / (sourceWidth / sourceHeight);
      const width = Math.min(1, normalizedRatio);
      const height = Math.min(1, 1 / normalizedRatio);
      return { ...next, box: [(1 - width) / 2, (1 - height) / 2, (1 + width) / 2, (1 + height) / 2] };
    });
  }

  useEffect(() => {
    let active = true;
    Promise.all([capabilities(), assetCatalog("sky"), assetCatalog("lut"), assetCatalog("color_transfer"), health(), catalog(), presets(), configuration(), layerMaterials()])
      .then(([nextItems, nextAssets, nextLuts, nextColorAssets, nextRuntime, nextCatalog, nextPresets, nextConfig, nextLayerMaterials]) => {
        if (!active) return;
        setItems(nextItems.filter((item) => item.group !== "generative"));
        setSkyAssets(nextAssets);
        setLutAssets(nextLuts);
        setLutAssetId(nextLuts[0]?.id || "");
        setColorAssets(nextColorAssets);
        setColorAssetId(nextColorAssets[0]?.id || "");
        setRuntime(nextRuntime);
        setCatalogRecords(nextCatalog);
        setCatalogCollection(nextConfig.catalog_collection);
        setPresetRecords(nextPresets);
        setToolGroups(nextConfig.tool_groups);
        setCapabilityVisuals(nextConfig.capability_visuals);
        setLayerMaterialGroups(nextLayerMaterials);
        setSelected(nextConfig.default_capability);
        setSkySettings((current) => ({ ...current, ...nextConfig.sky_defaults }));
      })
      .catch((reason: unknown) => active && setError(errorMessage(reason)));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    };
  }, [sourceUrl]);

  useEffect(() => () => {
    if (workflowPreviewUrl) URL.revokeObjectURL(workflowPreviewUrl);
  }, [workflowPreviewUrl]);

  useEffect(() => {
    if (!analysisJob.view.project) return;
    setProject(analysisJob.view.project);
    setPreviewNonce((value) => value + 1);
  }, [analysisJob.view.project]);

  useEffect(() => {
    const layers = project?.layers ?? [];
    if (!layers.length) {
      setSelectedLayerId(undefined);
    } else if (!selectedLayerId || !layers.some((layer) => layer.id === selectedLayerId)) {
      setSelectedLayerId(layers[layers.length - 1].id);
    }
  }, [project?.layers, selectedLayerId]);

  useEffect(() => {
    setMaskBrushActive(false);
    setMaskStrokes([]);
  }, [projectId, selectedLayerId]);

  useEffect(() => {
    function setCanonicalParameter(event: Event) {
      if (!(event instanceof CustomEvent)) return;
      const target = event.target instanceof HTMLElement ? event.target : undefined;
      const capabilityId = target?.closest<HTMLElement>("[data-capability-id]")?.dataset.capabilityId;
      const parameterId = target?.closest<HTMLElement>("[data-parameter-id]")?.dataset.parameterId;
      if (!target || capabilityId !== selected || !parameterId) return;
      const value = event.detail?.value;
      if (parameterId === "crop_box" && Array.isArray(value) && value.length === 4) {
        setCropSettings((current) => ({ ...current, box: value.map(Number) as CropSettings["box"], ratio: "free" }));
      } else if (parameterId === "strokes") {
        setStrokes([{ points: [[0.45, 0.45], [0.55, 0.55]], radius: 0.05 }]);
      } else if (parameterId === "asset_id") {
        if (capabilityId === "sky_replace") setAssetId(skyAssets[0]?.id ?? "");
        else if (capabilityId === "lut_mapping") setLutAssetId(lutAssets[0]?.id ?? "");
        else if (capabilityId === "color_transfer") setColorAssetId(colorAssets[0]?.id ?? "");
      } else if (parameterId === "denoise_level" && ["low", "middle", "high"].includes(String(value))) {
        setDenoiseLevel(String(value) as "low" | "middle" | "high");
      } else if (parameterId === "sharp_level" && ["low", "middle", "high"].includes(String(value))) {
        setSharpLevel(String(value) as "low" | "middle" | "high");
      }
      target.dataset.value = JSON.stringify(value);
    }

    document.addEventListener("zpixel:set-parameter", setCanonicalParameter);
    return () => document.removeEventListener("zpixel:set-parameter", setCanonicalParameter);
  }, [colorAssets, lutAssets, selected, skyAssets]);

  const busy = Boolean(pendingAction);
  const runtimeLabel = runtime
    ? `${runtime.runtime.toUpperCase().replaceAll("ONNXRUNTIME", "ORT")} · ${runtime.models?.openvino?.enabled ? "IR READY" : "LOCAL"}`
    : undefined;

  function selectCapability(value: string) {
    setSelected(value);
    setAmount(0.4);
    setStrokes([]);
    if (value === "denoise") setDenoiseLevel("middle");
  }

  async function onUpload(file?: File | File[], collection?: string) {
    const files = Array.isArray(file) ? file : file ? [file] : [];
    if (!files.length || busy) return;
    setPendingAction("upload");
    setError(undefined);
    try {
      let lastResult: { project_id: string } | undefined;
      for (const currentFile of files) {
        lastResult = await upload(currentFile, collection);
      }
      if (!lastResult) return;
      setProjectId(lastResult.project_id);
      setSelectedPreset(undefined);
      setProject(await getProject(lastResult.project_id));
      setSourceUrl(URL.createObjectURL(files[files.length - 1]));
      setCatalogRecords(await catalog());
      setPreviewNonce((value) => value + 1);
      setWorkspace("editor");
      setEditorPanel("tools");
      setEditorPanelsOpen(true);
      setTrace(undefined);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function openCatalogRecord(record: CatalogRecord, enterEditor = false, panel: EditorPanel = "tools") {
    if (busy) return;
    setPendingAction("open");
    setError(undefined);
    try {
      const nextProject = await getProject(record.project_id);
      setProjectId(record.project_id);
      setProject(nextProject);
      setSourceUrl(sourceImageUrl(record.project_id));
      setPreviewNonce((value) => value + 1);
      if (enterEditor) {
        setWorkspace("editor");
        setEditorPanel(panel);
        setEditorPanelsOpen(true);
      }
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function updateCatalogRecord(record: CatalogRecord, changes: Record<string, unknown>) {
    if (busy) return;
    setPendingAction("catalog-update");
    setError(undefined);
    try {
      await updateCatalogAsset(record.asset_id, changes);
      setCatalogRecords(await catalog());
      if (record.project_id === projectId && "rotation_delta" in changes) {
        setProject(await getProject(record.project_id));
        setPreviewNonce((value) => value + 1);
      }
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function exportCatalogRecord(record: CatalogRecord) {
    await openCatalogRecord(record, true, "tools");
    setExportSettings({ projectId: record.project_id, value: defaultFilename(record.filename), format: "png", width: 1080, profile: "sRGB" });
    setExportDialogOpen(true);
  }

  function openExportDialog() {
    if (!projectId) return;
    setExportSettings((current) => current?.projectId === projectId ? current : {
      projectId,
      value: defaultFilename(projectFilename),
      format: "png",
      width: 1080,
      profile: "sRGB",
    });
    setExportDialogOpen(true);
  }

  async function applySelectedPreset(preset: Preset) {
    if (!projectId || busy) return;
    setPendingAction("preset");
    setError(undefined);
    try {
      setProject(await applyPreset(projectId, preset.id));
      setSelectedPreset(undefined);
      setPreviewNonce((value) => value + 1);
      setCatalogRecords(await catalog());
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function importLocalPreset(files: File[]) {
    if (!files.length || busy) return;
    setPendingAction("preset-import");
    setError(undefined);
    try {
      setPresetRecords(await importPreset(files));
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function apply(amountOverride?: number) {
    if (!projectId || busy) return;
    setPendingAction("apply");
    setError(undefined);
    try {
      const parameters: Record<string, unknown> = {};
      if (!["sky_replace", "crop_ai", "deblur", "erase", "clone"].includes(selected)) {
        parameters.amount = amountOverride ?? amount;
      }
      if (selected === "bw_channels") {
        parameters.converted = true;
      }
      if (selected === "denoise" && denoiseLevel) {
        parameters.denoise_level = denoiseLevel;
        Object.assign(parameters, denoiseSettings);
      }
      if (selected === "deblur") {
        parameters.sharp_type = "universal";
        parameters.sharp_level = sharpLevel;
        parameters.face_enhancer_enabled = sharpFaceEnhancer;
      }
      if (selected === "crop_ai") {
        parameters.crop_box = cropSettings.box;
        parameters.crop_ratio = cropSettings.ratio;
        parameters.crop_rotation = cropSettings.rotation;
        parameters.straighten = cropSettings.straighten;
        parameters.flip_x = cropSettings.flipX;
        parameters.flip_y = cropSettings.flipY;
      }
      if (selected === "bokeh_ai") {
        parameters.bokeh_shape = bokehShape;
      }
      if (selected === "sky_replace" || selected === "augmented_sky") {
        Object.assign(parameters, toSkyParameters(skySettings));
      }
      if (selected === "erase" || selected === "dodge_burn" || selected === "clone" || selected === "new_neon_light") {
        parameters.strokes = strokes;
      }
      if (selected === "new_neon_light") {
        parameters.neon_spread = neonSettings.spread;
        parameters.neon_atmosphere = neonSettings.atmosphere;
        parameters.neon_hue = neonSettings.hue;
        parameters.neon_whiteness = neonSettings.whiteness;
      }
      const selectedAssetId = selected === "lut_mapping"
        ? lutAssetId
        : selected === "color_transfer"
          ? colorAssetId
        : selected === "sky_replace" || selected === "augmented_sky"
          ? assetId
          : undefined;
      const existing = [...(project?.edits ?? [])]
        .reverse()
        .find((edit) => edit.effect === selected && edit.enabled !== false);
      const next = existing
        ? await updateEdit(projectId, existing.id, selected, parameters, selectedAssetId)
        : await addEdit(projectId, selected, parameters, selectedAssetId);
      setProject(next);
      setStrokes([]);
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function removeEdit(editId: string) {
    if (!projectId || busy) return;
    setPendingAction("delete");
    setError(undefined);
    try {
      setProject(await deleteEdit(projectId, editId));
      setPreviewNonce((value) => value + 1);
      setCatalogRecords(await catalog());
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function updateProjectEdit(editId: string, effect: string, parameters: Record<string, unknown>) {
    if (!projectId || busy) return;
    setPendingAction("edit-update");
    setError(undefined);
    try {
      setProject(await updateEdit(
        projectId,
        editId,
        effect,
        parameters,
        typeof parameters.asset_id === "string" ? parameters.asset_id : undefined,
      ));
      setPreviewNonce((value) => value + 1);
      setCatalogRecords(await catalog());
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function addProjectLayer(file?: File) {
    if (!projectId || !file || busy) return;
    setPendingAction("layer-add");
    setError(undefined);
    try {
      const nextProject = await addLayer(projectId, file);
      setProject(nextProject);
      setSelectedLayerId(nextProject.layers[nextProject.layers.length - 1]?.id);
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function addProjectLayerMaterial(materialId: string) {
    if (!projectId || busy) return;
    setPendingAction("layer-add");
    setError(undefined);
    try {
      const nextProject = await addLayerMaterial(projectId, materialId);
      setProject(nextProject);
      setSelectedLayerId(nextProject.layers[nextProject.layers.length - 1]?.id);
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function updateProjectLayer(layerId: string, changes: LayerUpdate) {
    if (!projectId || busy) return;
    setPendingAction("layer-update");
    setError(undefined);
    try {
      setProject(await updateLayer(projectId, layerId, changes));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function uploadProjectLayerMask(layerId: string, file: File) {
    if (!projectId || busy) return;
    setPendingAction("mask-upload");
    setError(undefined);
    try {
      setProject(await uploadMask(projectId, "layer", layerId, file));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function paintProjectLayerMask(layerId: string, nextStrokes: BrushStroke[]) {
    if (!projectId || busy || !nextStrokes.length) return;
    setMaskStrokes(nextStrokes);
    setPendingAction("mask-brush");
    setError(undefined);
    try {
      setProject(await paintMask(projectId, "layer", layerId, nextStrokes, maskBrushSettings));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function updateProjectMask(maskId: string, changes: MaskUpdate) {
    if (!projectId || busy) return;
    setPendingAction("mask-update");
    setError(undefined);
    try {
      setProject(await updateMask(projectId, maskId, changes));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function removeProjectMask(maskId: string) {
    if (!projectId || busy) return;
    setPendingAction("mask-delete");
    setError(undefined);
    try {
      setProject(await deleteMask(projectId, maskId));
      setMaskBrushActive(false);
      setMaskStrokes([]);
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function reorderProjectLayers(layerIds: string[]) {
    if (!projectId || busy) return;
    setPendingAction("layer-reorder");
    setError(undefined);
    try {
      setProject(await reorderLayers(projectId, layerIds));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function removeProjectLayer(layerId: string) {
    if (!projectId || busy) return;
    setPendingAction("layer-delete");
    setError(undefined);
    try {
      const nextProject = await deleteLayer(projectId, layerId);
      setProject(nextProject);
      setSelectedLayerId(nextProject.layers[nextProject.layers.length - 1]?.id);
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  function openWorkflow(kind: WorkflowKind) {
    setWorkflowKind(kind);
    setWorkflowId(undefined);
    setWorkflowPreviewUrl(undefined);
    setWorkflowStatus(undefined);
    setWorkspace("workflow");
  }

  function changeEditorPanel(nextPanel: EditorPanel) {
    if (editorPanel === nextPanel && editorPanelsOpen && workspace === "editor") {
      setEditorPanelsOpen(false);
      return;
    }
    setEditorPanel(nextPanel);
    setEditorPanelsOpen(true);
    if (projectId || nextPanel === "more" || nextPanel === "info") {
      setWorkspace("editor");
    }
  }

  function openEditorPanel(nextPanel: "presets" | "tools" | "edits" | "info") {
    setEditorPanel(nextPanel);
    setEditorPanelsOpen(true);
    setWorkspace("editor");
  }

  async function stepHistory(action: "undo" | "redo") {
    if (!projectId || busy) return;
    setPendingAction(action);
    setError(undefined);
    try {
      setProject(await (action === "undo" ? undo(projectId) : redo(projectId)));
      setPreviewNonce((value) => value + 1);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const action = historyActionForKeyboardEvent(event);
      if (!action || workspace !== "editor" || !projectId || busy) return;
      event.preventDefault();
      void stepHistory(action);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, projectId, workspace]);

  async function restoreOriginal() {
    if (!projectId || busy) return;
    setPendingAction("reset");
    setError(undefined);
    try {
      setProject(await resetProject(projectId));
      setStrokes([]);
      setShowBefore(false);
      setTrace(undefined);
      setPreviewNonce((value) => value + 1);
      setCatalogRecords(await catalog());
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  function runAnalysis() {
    if (!projectId || busy || analysisJob.active) return;
    setError(undefined);
    void analysisJob.start();
  }

  async function refreshExecutionTrace() {
    if (!projectId || showBefore) return;
    try {
      setTrace(await executionTrace(projectId));
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    }
  }

  async function runWorkflow(kind: WorkflowKind, files: File[]) {
    if (busy || files.length < 2) return;
    setPendingAction("workflow");
    setError(undefined);
    setWorkflowStatus("正在创建多图工作流…");
    try {
      const session = await createWorkflow(kind);
      setWorkflowId(session.id);
      for (const file of files) await addWorkflowFrame(session.id, file);
      await analyzeWorkflow(session.id);
      const blob = await workflowPreview(session.id);
      setWorkflowPreviewUrl(URL.createObjectURL(blob));
      setWorkflowStatus(`${files.length} 张图片已完成 ${kind === "hdr_merge" ? "HDR 合并" : kind === "focus_stacking" ? "焦点堆叠" : "全景拼接"} 预览`);
    } catch (reason: unknown) {
      setWorkflowStatus(undefined);
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  async function exportWorkflow() {
    if (!workflowId || busy) return;
    setPendingAction("workflow-export");
    setError(undefined);
    try {
      const blob = await workflowExport(workflowId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "zpixel-workflow-export.png";
      link.click();
      URL.revokeObjectURL(url);
      setWorkflowStatus("多图结果已导出 PNG");
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setPendingAction(undefined);
    }
  }

  return (
    <main className="app-shell">
      <EditorHeader
        busy={busy}
        runtimeLabel={runtimeLabel}
        mode={workspace}
        projectId={projectId}
        filename={projectFilename}
        workflowTitle={workflowKind === "hdr_merge" ? "HDR 合并" : workflowKind === "focus_stacking" ? "焦点堆叠" : "全景拼接"}
        catalogCollection={catalogCollection}
        onUpload={onUpload}
        onCatalog={() => setWorkspace("catalog")}
        onExport={openExportDialog}
      />
      {error && <div className="error" role="alert"><span>{error}</span><button onClick={() => setError(undefined)} aria-label="关闭错误">×</button></div>}
      {workspace === "catalog" ? <CatalogWorkspace collectionName={catalogCollection} project={project} records={catalogRecords} busy={busy} onUpload={onUpload} onOpen={(record) => openCatalogRecord(record)} onOpenPanel={(record, panel) => openCatalogRecord(record, true, panel)} onOpenWorkflow={openWorkflow} onUpdateRecord={updateCatalogRecord} onExportRecord={exportCatalogRecord} /> : workspace === "workflow" ? <WorkflowWorkspace initialKind={workflowKind} collectionName={catalogCollection} records={catalogRecords} busy={busy} previewUrl={workflowPreviewUrl} status={workflowStatus} canExport={Boolean(workflowId && workflowPreviewUrl)} onBack={() => setWorkspace("catalog")} onKindChange={openWorkflow} onRun={runWorkflow} onExport={exportWorkflow} /> : <section className={`workspace workspace-edit workspace-panel-${editorPanel}${!editorPanelsOpen ? " workspace-edit-collapsed" : ""}`}>
        {editorPanelsOpen && !["more", "info"].includes(editorPanel) && <LayersPanel
          busy={busy}
          groups={layerMaterialGroups}
          project={project}
          projectId={projectId}
          selectedLayerId={selectedLayerId}
          sourceUrl={sourceUrl}
          onAddLayer={addProjectLayer}
          onAddMaterial={addProjectLayerMaterial}
          onDeleteLayer={removeProjectLayer}
          onReorderLayers={reorderProjectLayers}
          onSelectLayer={setSelectedLayerId}
          onUpdateLayer={updateProjectLayer}
        />}
        <PreviewPanel
          analysis={analysisJob.view.message}
          analysisActive={analysisJob.active}
          analysisError={analysisJob.view.error}
          busy={busy}
          onCancelAnalysis={() => void analysisJob.cancel()}
          onAnalyze={runAnalysis}
          onHistory={stepHistory}
          onExport={openExportDialog}
          onReset={() => void restoreOriginal()}
          onToggleBefore={() => setShowBefore((value) => !value)}
          onPreviewReady={refreshExecutionTrace}
          onUpload={onUpload}
          previewNonce={previewNonce}
          previewOverrideUrl={projectId && selectedPreset ? presetPreviewUrl(projectId, selectedPreset.id) : undefined}
          projectId={projectId}
          showBefore={showBefore}
          sourceUrl={sourceUrl}
          trace={trace}
          filename={projectFilename}
          mode={editorPanel === "presets" ? "presets" : "edit"}
          interactiveTool={maskBrushActive && selectedLayerId ? "mask" : selected === "erase" || selected === "dodge_burn" || selected === "clone" || selected === "new_neon_light" ? selected : undefined}
          strokes={maskBrushActive ? maskStrokes : strokes}
          brushRadius={maskBrushActive ? Math.max(0.01, Math.min(0.15, maskBrushSettings.size / 1000)) : brushRadius}
          onStrokesChange={(nextStrokes) => {
            if (maskBrushActive && selectedLayerId) void paintProjectLayerMask(selectedLayerId, nextStrokes);
            else setStrokes(nextStrokes);
          }}
          filmstrip={catalogRecords.map((record) => ({
            projectId: record.project_id,
            filename: record.filename,
            url: sourceImageUrl(record.project_id),
            selected: record.project_id === projectId,
          }))}
          onSelectFilmstrip={(nextProjectId) => {
            const record = catalogRecords.find((item) => item.project_id === nextProjectId);
            if (record) void openCatalogRecord(record, true);
          }}
          catalogRecord={selectedCatalogRecord}
          onCatalogUpdate={(changes) => selectedCatalogRecord && updateCatalogRecord(selectedCatalogRecord, changes)}
          onOpenPanel={openEditorPanel}
          onOpenWorkflow={openWorkflow}
          cropActive={editorPanelsOpen && editorPanel === "tools" && expandedTool === "crop_ai"}
          cropBox={cropSettings.box}
          onCropBoxChange={(box) => setCropSettings((current) => ({ ...current, box, ratio: "free" }))}
          straightenActive={cropStraightenActive}
          onStraightenComplete={(straighten) => {
            setCropSettings((current) => ({ ...current, straighten }));
            setCropStraightenActive(false);
          }}
        />
        {editorPanelsOpen && editorPanel === "presets" && <PresetBrowser projectId={projectId} presets={presetRecords} selectedPresetId={selectedPreset?.id} busy={busy} onPreview={setSelectedPreset} onApply={() => selectedPreset && void applySelectedPreset(selectedPreset)} onImport={importLocalPreset} />}
        {editorPanelsOpen && editorPanel === "tools" && <ToolPanel
          amount={amount}
          assetId={assetId}
          skySettings={skySettings}
          busy={busy}
          groups={toolGroups}
          visuals={capabilityVisuals}
          items={items}
          onAmountChange={setAmount}
          onAmountCommit={(value) => void apply(value)}
          denoiseLevel={denoiseLevel}
          onDenoiseLevelChange={setDenoiseLevel}
          denoiseSettings={denoiseSettings}
          onDenoiseSettingChange={(key, value) => setDenoiseSettings((current) => ({ ...current, [key]: value }))}
          sharpLevel={sharpLevel}
          sharpType="universal"
          sharpFaceEnhancer={sharpFaceEnhancer}
          onSharpLevelChange={setSharpLevel}
          onSharpFaceEnhancerChange={setSharpFaceEnhancer}
          onApply={apply}
          onAssetChange={setAssetId}
          onSkySettingChange={(key, value) => setSkySettings((current) => ({ ...current, [key]: value }))}
          onSelect={selectCapability}
          project={project}
          selected={selected}
          colorAssets={colorAssets}
          colorAssetId={colorAssetId}
          onColorAssetChange={setColorAssetId}
          strokesCount={strokes.length}
          brushRadius={brushRadius}
          onBrushRadiusChange={setBrushRadius}
          onClearStrokes={() => setStrokes([])}
          bokehShape={bokehShape}
          onBokehShapeChange={setBokehShape}
          neonSettings={neonSettings}
          onNeonSettingChange={(key, value) => setNeonSettings((current) => ({ ...current, [key]: value }))}
          lutAssets={lutAssets}
          lutAssetId={lutAssetId}
          onLutAssetChange={setLutAssetId}
          skyAssets={skyAssets}
          selectedLayer={project?.layers.find((layer) => layer.id === selectedLayerId)}
          projectId={projectId}
          onDeleteMask={removeProjectMask}
          onUpdateLayer={updateProjectLayer}
          onUpdateMask={updateProjectMask}
          onUploadLayerMask={uploadProjectLayerMask}
          cropSettings={cropSettings}
          onCropSettingsChange={updateCropSettings}
          straightenActive={cropStraightenActive}
          onStraightenActiveChange={setCropStraightenActive}
          onExpandedChange={setExpandedTool}
          maskBrushActive={maskBrushActive}
          maskBrushSettings={maskBrushSettings}
          onMaskBrushActiveChange={setMaskBrushActive}
          onMaskBrushSettingsChange={setMaskBrushSettings}
        />}
        {editorPanelsOpen && editorPanel === "edits" && <EditHistoryPanel key={projectId || "empty"} busy={busy} items={items} project={project} onDeleteEdit={removeEdit} onUpdateEdit={updateProjectEdit} />}
        {editorPanelsOpen && editorPanel === "more" && <MorePanel onOpenWorkflow={openWorkflow} />}
        {editorPanelsOpen && editorPanel === "info" && <InfoPanel filename={projectFilename} project={project} record={selectedCatalogRecord} />}
      </section>}
      <WorkspaceRail panel={editorPanel} panelOpen={workspace === "editor" && editorPanelsOpen} onPanelChange={changeEditorPanel} />
      {exportDialogOpen && projectId && exportSettings?.projectId === projectId && <ExportDialog settings={exportSettings} onSettingsChange={(settings) => setExportSettings({ ...settings, projectId })} hasRestorableEdit={Boolean(project?.edits.length || project?.layers.length)} projectId={projectId} onClose={() => setExportDialogOpen(false)} />}
    </main>
  );
}
