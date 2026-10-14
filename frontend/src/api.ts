export type CapabilityReadiness = { status: string; reason: string; mode: string; required_models: string[]; conditional_models: string[]; runnable_models: string[]; missing_or_blocked_models: string[]; parity: string };
export type Capability = { id: string; title: string; group: string; status: string; artifacts?: string[]; readiness?: CapabilityReadiness };
export type AssetRecord = { id: string; family: string; filename: string; path: string };
export type Edit = { id: string; effect: string; parameters: Record<string, unknown>; mask_artifact?: string | null; enabled?: boolean };
export type BrushStroke = { points: number[][]; radius: number; source?: number[] };
export type MaskArtifact = {
  id: string;
  path: string;
  owner_type: "edit" | "layer";
  owner_id: string;
  width: number;
  height: number;
  source: string;
  inverted: boolean;
  density: number;
  feather: number;
  brush_size?: number | null;
  brush_softness?: number | null;
  brush_strength?: number | null;
  sha256: string;
  version: number;
};
export type MaskUpdate = Partial<Pick<MaskArtifact, "inverted" | "density" | "feather">>;
export type MaskBrushSettings = { size: number; softness: number; strength: number };
export type Layer = {
  id: string;
  asset_id: string;
  path: string;
  name: string;
  source_kind: "library" | "upload";
  visible: boolean;
  opacity: number;
  blend_mode: string;
  scale: number;
  offset_x: number;
  offset_y: number;
  rotation: number;
  flip_x: boolean;
  flip_y: boolean;
  mask_artifact?: string | null;
};
export type LayerUpdate = Partial<Pick<Layer, "visible" | "opacity" | "blend_mode" | "scale" | "offset_x" | "offset_y" | "rotation" | "flip_x" | "flip_y">>;
export type LayerMaterial = { id: string; name: string; path: string; blend_mode: string; opacity: number };
export type LayerMaterialGroup = { id: string; label: string; collection_id: string; preview_limit: number; count: number; items: LayerMaterial[] };
export type Project = { source: { path: string; width?: number | null; height?: number | null }; masks?: Record<string, MaskArtifact>; layers: Layer[]; edits: Edit[]; metadata?: Record<string, unknown> };
export type CatalogRecord = { asset_id: string; project_id: string; filename: string; path: string; collection?: string | null; size: number; added_at: string; edited_at?: string | null; edit_count: number; favorite?: boolean; rejected?: boolean; rating?: number; color_label?: string | null; rotation?: number; deleted_at?: string | null };
export type Preset = { id: string; name: string; category: string; status: string; edit_graph: Array<{ effect: string; parameters: Record<string, unknown> }> };
export type WorkflowKind = "hdr_merge" | "focus_stacking" | "panorama_stitching";
export type ToolGroup = { id: string; label: string; tone: string; capabilities: string[] };
export type CapabilityVisual = { icon: string; ai_badge: boolean };
export type PublicConfiguration = {
  default_capability: string;
  catalog_collection: string;
  workspaces: Array<{ id: string; label: string }>;
  workflow_labels: Record<WorkflowKind, string>;
  tool_groups: ToolGroup[];
  capability_visuals: Record<string, CapabilityVisual>;
  sky_defaults: Record<string, number>;
};
export type WorkflowSession = { id: string; kind: WorkflowKind; status: string; frames: Array<{ id: string; filename: string; width: number; height: number }>; analysis?: Record<string, unknown> };
export type RuntimeHealth = {
  runtime: string;
  models?: {
    registered?: number;
    missing?: string[];
    registered_formats?: string[];
    openvino?: { enabled?: boolean; reason?: string };
    cache?: { loaded?: string[]; estimated_memory_mb?: number };
  };
};
export type ExecutionTrace = {
  execution_id?: string;
  operation?: string;
  mode?: string;
  status: string;
  capabilities: string[];
  models: Array<{ id: string; backend: string; status: string; duration_ms: number; invoked: boolean }>;
  duration_ms?: number;
  error?: string;
};
export type AnalysisJobStatus = "queued" | "running" | "succeeded" | "completed" | "failed" | "cancelled";
export type AnalysisJob = {
  id: string;
  project_id: string;
  status: AnalysisJobStatus;
  requested_models: string[];
  completed_models: Record<string, Record<string, unknown>>;
  error?: string | null;
};
export type AnalysisJobResult = {
  job_id: string;
  project_id: string;
  status: AnalysisJobStatus;
  complete: boolean;
  models: Record<string, Record<string, unknown>>;
  error?: string | null;
};

export async function upload(file: File, collection?: string): Promise<{ project_id: string }> {
  const body = new FormData(); body.append("file", file);
  const query = collection ? `?collection=${encodeURIComponent(collection)}` : "";
  const response = await fetch(`/api/v1/assets${query}`, { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function capabilities(): Promise<Capability[]> {
  const response = await fetch("/api/v1/capabilities");
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).capabilities;
}

export async function health(): Promise<RuntimeHealth> {
  const response = await fetch("/api/v1/health");
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function configuration(): Promise<PublicConfiguration> {
  const response = await fetch("/api/v1/configuration");
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function assetCatalog(family?: string): Promise<AssetRecord[]> {
  const query = family ? `?family=${encodeURIComponent(family)}` : "";
  const response = await fetch(`/api/v1/assets/catalog${query}`);
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).records;
}

export async function createWorkflow(kind: WorkflowKind): Promise<WorkflowSession> {
  const response = await fetch(`/api/v1/workflows/${kind}`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function addWorkflowFrame(workflowId: string, file: File): Promise<WorkflowSession> {
  const body = new FormData(); body.append("file", file);
  const response = await fetch(`/api/v1/workflows/${workflowId}/frames`, { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function analyzeWorkflow(workflowId: string): Promise<WorkflowSession> {
  const response = await fetch(`/api/v1/workflows/${workflowId}/analyze`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function workflowPreview(workflowId: string): Promise<Blob> {
  const response = await fetch(`/api/v1/workflows/${workflowId}/preview`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.blob();
}

export async function workflowExport(workflowId: string): Promise<Blob> {
  const response = await fetch(`/api/v1/workflows/${workflowId}/export`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.blob();
}

export async function catalog(view = "all", query = "", sort = "added_at"): Promise<CatalogRecord[]> {
  const params = new URLSearchParams({ view, query, sort });
  const response = await fetch(`/api/v1/catalog?${params.toString()}`);
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).records;
}

export async function updateCatalogAsset(
  assetId: string,
  changes: Partial<Pick<CatalogRecord, "favorite" | "rejected" | "rating" | "color_label">> & { deleted?: boolean; rotation_delta?: number },
): Promise<CatalogRecord> {
  const response = await fetch(`/api/v1/catalog/assets/${encodeURIComponent(assetId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).record;
}

export async function presets(category?: string): Promise<Preset[]> {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  const response = await fetch(`/api/v1/presets${query}`);
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).records;
}

export async function importPreset(files: File[]): Promise<Preset[]> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file, file.webkitRelativePath || file.name));
  const response = await fetch("/api/v1/presets/import", { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).records;
}

export async function applyPreset(projectId: string, presetId: string): Promise<Project> {
  const response = await fetch(`/api/v1/projects/${projectId}/presets/${encodeURIComponent(presetId)}/apply`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).project;
}

export async function addEdit(projectId: string, effect: string, parameters: Record<string, unknown>, assetId?: string): Promise<Project> {
  const response = await fetch(`/api/v1/projects/${projectId}/edits`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ effect, parameters: { ...parameters, ...(assetId ? { asset_id: assetId } : {}) } }),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).project;
}

export async function updateEdit(projectId: string, editId: string, effect: string, parameters: Record<string, unknown>, assetId?: string): Promise<Project> {
  const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/edits/${encodeURIComponent(editId)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ effect, parameters: { ...parameters, ...(assetId ? { asset_id: assetId } : {}) } }),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).project;
}

export async function addLayer(projectId: string, file: File): Promise<Project> {
  const body = new FormData(); body.append("file", file);
  const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/layers/uploads`, { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).project;
}

export async function layerMaterials(): Promise<LayerMaterialGroup[]> {
  const response = await fetch("/api/v1/layer-materials");
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()).groups;
}

export async function addLayerMaterial(projectId: string, materialId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/layers/assets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ material_id: materialId }),
  });
}

export async function updateLayer(projectId: string, layerId: string, changes: LayerUpdate): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/layers/${encodeURIComponent(layerId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

export async function reorderLayers(projectId: string, layerIds: string[]): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/layers/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layer_ids: layerIds }),
  });
}

export async function deleteLayer(projectId: string, layerId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/layers/${encodeURIComponent(layerId)}`, { method: "DELETE" });
}

export async function uploadMask(projectId: string, ownerType: "edit" | "layer", ownerId: string, file: File): Promise<Project> {
  const body = new FormData(); body.append("file", file);
  const params = new URLSearchParams({ owner_type: ownerType, owner_id: ownerId });
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/masks/uploads?${params.toString()}`, { method: "POST", body });
}

export async function paintMask(projectId: string, ownerType: "edit" | "layer", ownerId: string, strokes: BrushStroke[], settings: MaskBrushSettings): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/masks/brush`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      owner_type: ownerType,
      owner_id: ownerId,
      strokes: strokes.map((stroke) => ({ points: stroke.points })),
      ...settings,
    }),
  });
}

export async function updateMask(projectId: string, maskId: string, changes: MaskUpdate): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/masks/${encodeURIComponent(maskId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

export async function deleteMask(projectId: string, maskId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/masks/${encodeURIComponent(maskId)}`, { method: "DELETE" });
}

export async function enqueueAnalysisJob(
  projectId: string,
  options: { models?: string[]; idempotencyKey?: string } = {},
): Promise<AnalysisJob> {
  const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/analysis-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(options.models ? { models: options.models } : {}),
      ...(options.idempotencyKey ? { idempotency_key: options.idempotencyKey } : {}),
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getAnalysisJob(jobId: string): Promise<AnalysisJob> {
  const response = await fetch(`/api/v1/analysis-jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getLatestAnalysisJob(projectId: string): Promise<AnalysisJob | null> {
  const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/analysis-jobs/latest`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getAnalysisJobResult(jobId: string): Promise<AnalysisJobResult> {
  const response = await fetch(`/api/v1/analysis-jobs/${encodeURIComponent(jobId)}/result`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function cancelAnalysisJob(jobId: string): Promise<AnalysisJob> {
  const response = await fetch(`/api/v1/analysis-jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function executionTrace(projectId: string): Promise<ExecutionTrace> {
  const response = await fetch(`/api/v1/projects/${projectId}/execution`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function search(projectId: string, query: string): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/projects/${projectId}/search?query=${encodeURIComponent(query)}`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function projectMutation(url: string, init: RequestInit = {}): Promise<Project> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(await response.text());
  const body = await response.json();
  return body.project || body;
}

export function undo(projectId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${projectId}/undo`, { method: "POST" });
}

export function redo(projectId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${projectId}/redo`, { method: "POST" });
}

export function deleteEdit(projectId: string, editId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${projectId}/edits/${editId}`, { method: "DELETE" });
}

export function resetProject(projectId: string): Promise<Project> {
  return projectMutation(`/api/v1/projects/${encodeURIComponent(projectId)}/reset`, { method: "POST" });
}

export function previewUrl(projectId: string, nonce: number): string {
  return `/api/v1/projects/${projectId}/preview?nonce=${nonce}`;
}

export function sourceImageUrl(projectId: string): string {
  return `/api/v1/projects/${encodeURIComponent(projectId)}/source`;
}

export function exportUrl(projectId: string, options?: { format?: "png" | "jpeg" | "tiff"; width?: number; profile?: "sRGB"; filename?: string }): string {
  const parameters = new URLSearchParams();
  if (options?.format) parameters.set("format", options.format);
  if (options?.width) parameters.set("width", String(options.width));
  if (options?.profile) parameters.set("profile", options.profile);
  if (options?.filename) parameters.set("filename", options.filename);
  const query = parameters.toString();
  return `/api/v1/projects/${projectId}/export${query ? `?${query}` : ""}`;
}

export function assetPreviewUrl(assetId: string): string {
  return `/api/v1/assets/${encodeURIComponent(assetId)}/preview`;
}

export function layerPreviewUrl(projectId: string, layerId: string): string {
  return `/api/v1/projects/${encodeURIComponent(projectId)}/layers/${encodeURIComponent(layerId)}/preview`;
}

export function layerMaterialPreviewUrl(materialId: string): string {
  return `/api/v1/layer-materials/${encodeURIComponent(materialId)}/preview`;
}

export function maskPreviewUrl(projectId: string, maskId: string): string {
  return `/api/v1/projects/${encodeURIComponent(projectId)}/masks/${encodeURIComponent(maskId)}/preview`;
}

export function presetPreviewUrl(projectId: string, presetId: string): string {
  return `/api/v1/projects/${encodeURIComponent(projectId)}/presets/${encodeURIComponent(presetId)}/preview`;
}

export function presetArtworkUrl(presetId: string): string {
  return `/api/v1/presets/${encodeURIComponent(presetId)}/artwork`;
}

export function presetCategoryArtworkUrl(category: string, variant: "big" | "small" = "big"): string {
  return `/api/v1/preset-categories/${encodeURIComponent(category)}/artwork?variant=${variant}`;
}
