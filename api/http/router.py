"""Thin HTTP routes that translate requests into application use cases."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from services.editor.service import EditorService
from services.jobs.service import InferenceJobService
from services.multi_image.service import MultiImageService

from .dependencies import get_editor, get_jobs, get_workflows
from .schemas import (
    AnalysisJobRequest,
    CatalogAssetUpdateRequest,
    EditRequest,
    LayerMaterialRequest,
    LayerOrderRequest,
    LayerUpdateRequest,
    MaskBrushRequest,
    MaskUpdateRequest,
    PreviewRequest,
    ReorderRequest,
    WorkflowFrameOrderRequest,
)

EditorDependency = Annotated[EditorService, Depends(get_editor)]
WorkflowDependency = Annotated[MultiImageService, Depends(get_workflows)]
JobDependency = Annotated[InferenceJobService, Depends(get_jobs)]


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/health")
    def health(editor: EditorDependency) -> dict[str, Any]:
        models = editor.health()
        return {
            "status": "ok",
            "runtime": models.get("runtime", "auto"),
            "data_root": str(editor.projects.root),
            "models": models,
        }

    @router.get("/api/v1/configuration")
    def public_configuration(request: Request) -> dict[str, Any]:
        return request.app.state.public_config

    @router.post("/api/v1/assets")
    async def upload_asset(
        file: UploadFile,
        editor: EditorDependency,
        collection: str | None = None,
    ) -> dict[str, str]:
        return editor.upload_asset(
            file.filename or "upload.jpg",
            await file.read(),
            collection=collection,
        )

    @router.get("/api/v1/catalog")
    def catalog(
        editor: EditorDependency,
        view: str = "all",
        query: str = "",
        sort: str = "name",
    ) -> dict[str, Any]:
        return editor.catalog(view=view, query=query, sort=sort)

    @router.patch("/api/v1/catalog/assets/{asset_id}")
    def update_catalog_asset(
        asset_id: str,
        request: CatalogAssetUpdateRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return editor.update_catalog_asset(asset_id, request.model_dump(exclude_none=True))

    @router.get("/api/v1/presets")
    def presets(editor: EditorDependency, category: str | None = None) -> dict[str, Any]:
        return editor.presets(category)

    @router.post("/api/v1/presets/import")
    async def import_preset(files: list[UploadFile], editor: EditorDependency) -> dict[str, Any]:
        return editor.import_preset([
            (file.filename or "preset-file", await file.read()) for file in files
        ])

    @router.post("/api/v1/projects/{project_id}/presets/{preset_id}/apply")
    def apply_preset(
        project_id: str,
        preset_id: str,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return editor.apply_preset(project_id, preset_id)

    @router.get("/api/v1/projects/{project_id}/presets/{preset_id}/preview")
    def preset_preview(
        project_id: str,
        preset_id: str,
        editor: EditorDependency,
    ) -> FileResponse:
        return FileResponse(editor.preset_preview(project_id, preset_id), media_type="image/jpeg")

    @router.get("/api/v1/presets/{preset_id}/artwork")
    def preset_artwork(preset_id: str, editor: EditorDependency) -> FileResponse:
        return FileResponse(editor.preset_artwork_path(preset_id), media_type="image/jpeg")

    @router.get("/api/v1/preset-categories/{category}/artwork")
    def preset_category_artwork(
        category: str,
        editor: EditorDependency,
        variant: str = "big",
    ) -> FileResponse:
        return FileResponse(
            editor.preset_category_artwork_path(category, variant), media_type="image/jpeg"
        )

    @router.get("/api/v1/projects/{project_id}")
    def get_project(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.get_project(project_id)

    @router.get("/api/v1/projects/{project_id}/source")
    def project_source(project_id: str, editor: EditorDependency) -> FileResponse:
        path = editor.source_path(project_id)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return FileResponse(path, media_type=media_type)

    @router.post("/api/v1/projects/{project_id}/layers/uploads")
    async def add_layer_upload(
        project_id: str,
        file: UploadFile,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {
            "project": editor.add_layer_upload(
                project_id, file.filename or "layer.png", await file.read()
            )
        }

    @router.post("/api/v1/projects/{project_id}/layers/assets")
    def add_layer_material(
        project_id: str,
        request: LayerMaterialRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {"project": editor.add_layer_material(project_id, request.material_id)}

    @router.patch("/api/v1/projects/{project_id}/layers/{layer_id}")
    def update_layer(
        project_id: str,
        layer_id: str,
        request: LayerUpdateRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {
            "project": editor.update_layer(
                project_id, layer_id, request.model_dump(exclude_none=True)
            )
        }

    @router.put("/api/v1/projects/{project_id}/layers/order")
    def reorder_layers(
        project_id: str,
        request: LayerOrderRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {"project": editor.reorder_layers(project_id, request.layer_ids)}

    @router.delete("/api/v1/projects/{project_id}/layers/{layer_id}")
    def delete_layer(
        project_id: str,
        layer_id: str,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {"project": editor.delete_layer(project_id, layer_id)}

    @router.get("/api/v1/projects/{project_id}/layers/{layer_id}/preview")
    def layer_preview(project_id: str, layer_id: str, editor: EditorDependency) -> FileResponse:
        path = editor.layer_path(project_id, layer_id)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @router.post("/api/v1/projects/{project_id}/masks/uploads")
    async def add_mask_upload(
        project_id: str,
        owner_type: str,
        owner_id: str,
        file: UploadFile,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {
            "project": editor.add_mask_upload(
                project_id,
                owner_type,
                owner_id,
                file.filename or "mask.png",
                await file.read(),
            )
        }

    @router.post("/api/v1/projects/{project_id}/masks/brush")
    def paint_mask(
        project_id: str,
        request: MaskBrushRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {
            "project": editor.paint_mask(
                project_id,
                request.owner_type,
                request.owner_id,
                [stroke.points for stroke in request.strokes],
                size=request.size,
                softness=request.softness,
                strength=request.strength,
            )
        }

    @router.patch("/api/v1/projects/{project_id}/masks/{mask_id}")
    def update_mask(
        project_id: str,
        mask_id: str,
        request: MaskUpdateRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {
            "project": editor.update_mask(
                project_id, mask_id, request.model_dump(exclude_none=True)
            )
        }

    @router.delete("/api/v1/projects/{project_id}/masks/{mask_id}")
    def delete_mask(
        project_id: str,
        mask_id: str,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return {"project": editor.delete_mask(project_id, mask_id)}

    @router.get("/api/v1/projects/{project_id}/masks/{mask_id}/preview")
    def mask_preview(
        project_id: str,
        mask_id: str,
        editor: EditorDependency,
    ) -> FileResponse:
        return FileResponse(editor.mask_path(project_id, mask_id), media_type="image/png")

    @router.post("/api/v1/projects/{project_id}/edits")
    def add_edit(
        project_id: str,
        request: EditRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return editor.add_edit(
            project_id, request.effect, request.parameters, request.mask_artifact, request.enabled
        )

    @router.patch("/api/v1/projects/{project_id}/edits/{edit_id}")
    def update_edit(
        project_id: str,
        edit_id: str,
        request: EditRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return editor.update_edit(
            project_id,
            edit_id,
            request.effect,
            request.parameters,
            request.mask_artifact,
            request.enabled,
        )

    @router.delete("/api/v1/projects/{project_id}/edits/{edit_id}")
    def delete_edit(project_id: str, edit_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.delete_edit(project_id, edit_id)

    @router.post("/api/v1/projects/{project_id}/reset")
    def reset_project(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.reset_project(project_id)

    @router.post("/api/v1/projects/{project_id}/edits/reorder")
    def reorder_edits(
        project_id: str,
        request: ReorderRequest,
        editor: EditorDependency,
    ) -> dict[str, Any]:
        return editor.reorder_edits(project_id, request.edit_ids)

    @router.post("/api/v1/projects/{project_id}/undo")
    def undo(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.undo(project_id)

    @router.post("/api/v1/projects/{project_id}/redo")
    def redo(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.redo(project_id)

    @router.post("/api/v1/projects/{project_id}/analyze")
    def analyze(
        project_id: str,
        editor: EditorDependency,
        models: str | None = None,
    ) -> dict[str, Any]:
        return editor.analyze(project_id, models)

    @router.post("/api/v1/projects/{project_id}/analysis-jobs", status_code=202)
    def create_analysis_job(
        project_id: str,
        jobs: JobDependency,
        request: AnalysisJobRequest | None = None,
    ) -> dict[str, Any]:
        payload = request or AnalysisJobRequest()
        return jobs.enqueue(
            project_id,
            payload.models,
            idempotency_key=payload.idempotency_key,
        )

    @router.get("/api/v1/projects/{project_id}/analysis-jobs/latest")
    def latest_analysis_job(
        project_id: str, jobs: JobDependency
    ) -> dict[str, Any] | None:
        return jobs.latest(project_id)

    @router.get("/api/v1/analysis-jobs/{job_id}")
    def analysis_job(job_id: str, jobs: JobDependency) -> dict[str, Any]:
        return jobs.get(job_id)

    @router.get("/api/v1/analysis-jobs/{job_id}/result")
    def analysis_job_result(job_id: str, jobs: JobDependency) -> dict[str, Any]:
        return jobs.result(job_id)

    @router.delete("/api/v1/analysis-jobs/{job_id}")
    def cancel_analysis_job(job_id: str, jobs: JobDependency) -> dict[str, Any]:
        return jobs.cancel(job_id)

    @router.post("/api/v1/projects/{project_id}/search")
    def search(project_id: str, query: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.search(project_id, query)

    @router.get("/api/v1/projects/{project_id}/artifacts")
    def artifacts(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.project_artifacts(project_id)

    @router.get("/api/v1/projects/{project_id}/execution")
    def execution(project_id: str, editor: EditorDependency) -> dict[str, Any]:
        return editor.execution_trace(project_id)

    @router.post("/api/v1/projects/{project_id}/preview")
    def preview(
        project_id: str,
        editor: EditorDependency,
        request: PreviewRequest | None = None,
    ) -> FileResponse:
        return _preview_file(editor, project_id, request.width if request else None)

    @router.get("/api/v1/projects/{project_id}/preview")
    def preview_get(
        project_id: str,
        editor: EditorDependency,
        width: Annotated[int | None, Query(ge=1, le=32768)] = None,
    ) -> FileResponse:
        return _preview_file(editor, project_id, width)

    @router.post("/api/v1/projects/{project_id}/export")
    def export(
        project_id: str,
        editor: EditorDependency,
        format: Literal["png", "jpeg", "tiff"] = "png",
        width: Annotated[int | None, Query(ge=1, le=32768)] = None,
        profile: Literal["sRGB"] = "sRGB",
        filename: str | None = None,
    ) -> FileResponse:
        return _export_file(editor, project_id, format, width, profile, filename)

    @router.get("/api/v1/projects/{project_id}/export")
    def export_get(
        project_id: str,
        editor: EditorDependency,
        format: Literal["png", "jpeg", "tiff"] = "png",
        width: Annotated[int | None, Query(ge=1, le=32768)] = None,
        profile: Literal["sRGB"] = "sRGB",
        filename: str | None = None,
    ) -> FileResponse:
        return _export_file(editor, project_id, format, width, profile, filename)

    @router.get("/api/v1/models")
    def models(editor: EditorDependency) -> dict[str, Any]:
        return editor.list_models()

    @router.get("/api/v1/capabilities")
    def capabilities(editor: EditorDependency) -> dict[str, Any]:
        return editor.list_capabilities()

    @router.get("/api/v1/assets/catalog")
    def asset_catalog(
        editor: EditorDependency,
        family: str | None = None,
    ) -> dict[str, Any]:
        return editor.list_assets(family)

    @router.get("/api/v1/layer-materials")
    def layer_materials(editor: EditorDependency) -> dict[str, Any]:
        return editor.list_layer_materials()

    @router.get("/api/v1/layer-materials/{material_id}/preview")
    def layer_material_preview(material_id: str, editor: EditorDependency) -> FileResponse:
        path = editor.layer_material_path(material_id)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @router.get("/api/v1/assets/{asset_id}/preview")
    def asset_preview(asset_id: str, editor: EditorDependency) -> FileResponse:
        path = editor.asset_preview_path(asset_id)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @router.post("/api/v1/workflows/{kind}")
    def create_workflow(kind: str, workflows: WorkflowDependency) -> dict[str, Any]:
        return workflows.create(kind)

    @router.post("/api/v1/workflows/{workflow_id}/frames")
    async def add_workflow_frame(
        workflow_id: str,
        file: UploadFile,
        workflows: WorkflowDependency,
    ) -> dict[str, Any]:
        return workflows.add_frame(workflow_id, file.filename or "frame.jpg", await file.read())

    @router.delete("/api/v1/workflows/{workflow_id}/frames/{frame_id}")
    def delete_workflow_frame(
        workflow_id: str,
        frame_id: str,
        workflows: WorkflowDependency,
    ) -> dict[str, Any]:
        return workflows.remove_frame(workflow_id, frame_id)

    @router.put("/api/v1/workflows/{workflow_id}/frames/order")
    def reorder_workflow_frames(
        workflow_id: str,
        request: WorkflowFrameOrderRequest,
        workflows: WorkflowDependency,
    ) -> dict[str, Any]:
        return workflows.reorder_frames(workflow_id, request.frame_ids)

    @router.get("/api/v1/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, workflows: WorkflowDependency) -> dict[str, Any]:
        return workflows.get(workflow_id)

    @router.post("/api/v1/workflows/{workflow_id}/analyze")
    def analyze_workflow(workflow_id: str, workflows: WorkflowDependency) -> dict[str, Any]:
        return workflows.analyze(workflow_id)

    @router.post("/api/v1/workflows/{workflow_id}/preview")
    def preview_workflow(workflow_id: str, workflows: WorkflowDependency) -> FileResponse:
        path = workflows.preview(workflow_id)
        return FileResponse(path, media_type="image/png", filename="workflow-preview.png")

    @router.get("/api/v1/workflows/{workflow_id}/preview")
    def preview_workflow_get(workflow_id: str, workflows: WorkflowDependency) -> FileResponse:
        path = workflows.preview(workflow_id)
        return FileResponse(path, media_type="image/png", filename="workflow-preview.png")

    @router.post("/api/v1/workflows/{workflow_id}/export")
    def export_workflow(workflow_id: str, workflows: WorkflowDependency) -> FileResponse:
        path = workflows.preview(workflow_id, export=True)
        return FileResponse(path, media_type="image/png", filename="workflow-export.png")

    @router.get("/api/v1/workflows/{workflow_id}/export")
    def export_workflow_get(workflow_id: str, workflows: WorkflowDependency) -> FileResponse:
        path = workflows.preview(workflow_id, export=True)
        return FileResponse(path, media_type="image/png", filename="workflow-export.png")

    return router


def _export_filename(
    editor: EditorService,
    project_id: str,
    extension: str = "png",
    requested: str | None = None,
) -> str:
    if requested:
        stem = Path(requested.replace("\\", "/")).stem
    else:
        metadata = editor.get_project(project_id).get("metadata", {})
        original = str(metadata.get("original_filename") or "zpixel-export")
        stem = f"{Path(original.replace(chr(92), '/')).stem}-edited"
    safe_stem = "".join(
        "_" if character in {"/", "\\", "\r", "\n", "\t", ":", "*", "?", '"', "<", ">", "|"} else character
        for character in stem
    ).strip(" .")
    return f"{safe_stem or 'zpixel-export'}.{extension}"


def _export_file(
    editor: EditorService,
    project_id: str,
    image_format: Literal["png", "jpeg", "tiff"],
    width: int | None,
    profile: Literal["sRGB"],
    filename: str | None,
) -> FileResponse:
    extension = {"png": "png", "jpeg": "jpg", "tiff": "tiff"}[image_format]
    output = (
        editor.projects.root
        / "outputs"
        / f"{project_id}-export-{uuid.uuid4().hex}.{extension}"
    )
    metadata = editor.export(
        project_id,
        output,
        width=width,
        image_format=image_format,
        color_profile=profile,
    )
    return FileResponse(
        output,
        media_type={
            "png": "image/png",
            "jpeg": "image/jpeg",
            "tiff": "image/tiff",
        }[image_format],
        filename=_export_filename(editor, project_id, extension, filename),
        headers={
            "X-ZPixel-Export-Width": str(metadata["size"][0]),
            "X-ZPixel-Export-Height": str(metadata["size"][1]),
            "X-ZPixel-Export-Profile": str(metadata["color_profile"]),
            "X-ZPixel-Export-SHA256": str(metadata["sha256"]),
        },
        background=BackgroundTask(output.unlink, missing_ok=True),
    )


def _preview_file(
    editor: EditorService, project_id: str, width: int | None
) -> FileResponse:
    output = (
        editor.projects.root
        / "outputs"
        / f"{project_id}-preview-{uuid.uuid4().hex}.png"
    )
    editor.render_preview(project_id, output, width)
    trace = editor.execution_trace(project_id)
    return FileResponse(
        output,
        media_type="image/png",
        headers={
            "X-Zpixel-Execution-Id": str(trace.get("execution_id", "")),
            "X-Zpixel-Execution-Status": str(trace.get("status", "unknown")),
        },
        background=BackgroundTask(output.unlink, missing_ok=True),
    )
