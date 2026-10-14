"""FastAPI composition root kept stable for existing launch commands."""

from __future__ import annotations

import uuid
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai.pipeline.factory import build_model_service
from api.http.router import build_router
from api.logging import configure_logging, request_logger
from configs import load_config
from configs.store import load_capability_schema
from core.errors import CoreError
from image_ops.rendering import EditGraphRenderer
from services.editor.service import EditorService
from services.jobs.service import InferenceJobService
from services.multi_image.service import MultiImageService
from storage.assets.catalog import AssetCatalog
from storage.cache.artifact_cache import ArtifactCache
from storage.catalogs import LuminarCatalog
from storage.images import PillowImageReader
from storage.jobs import JsonInferenceJobRepository
from storage.manifests import FileManifestCatalog
from storage.projects.json_repository import JsonProjectRepository


def create_app(*, data_root: Path | None = None) -> FastAPI:
    config = load_config(Path(__file__).resolve().parent.parent)
    configure_logging(config.runtime.log_level)
    root = data_root or config.paths.data_root
    asset_root = config.paths.asset_root
    model_root = config.paths.model_root
    workspace_root = root / "workspace"
    projects = JsonProjectRepository(
        workspace_root,
        preview_root=root / "library" / "thumbnails",
    )
    catalog_store = LuminarCatalog(root / "library" / "catalog.luminarneo")
    artifact_cache = ArtifactCache(root / "cache" / "inference")
    model_service = build_model_service(config, model_root=model_root)
    image_reader = PillowImageReader()
    editor = EditorService(
        projects=projects,
        catalog_store=catalog_store,
        assets=AssetCatalog(asset_root, layer_library=config.ui.get("layer_library")),
        capabilities=load_capability_schema(config.paths.parameter_schema),
        artifact_cache=artifact_cache,
        model_service=model_service,
        renderer=EditGraphRenderer(config.execution_graphs),
        manifests=FileManifestCatalog(
            config.paths.model_manifest, config.paths.capability_manifest
        ),
        image_reader=image_reader,
        asset_root=asset_root,
        policy=config.policy,
        presets=config.presets,
        preset_source=config.preset_source,
    )
    workflows = MultiImageService(workspace_root)
    jobs = InferenceJobService(
        repository=JsonInferenceJobRepository(root / "jobs" / "inference"),
        projects=projects,
        images=image_reader,
        models=model_service,
        artifacts=artifact_cache,
    )
    app = FastAPI(title="zpixel_edit", version="0.1.0")
    app.state.editor = editor
    app.state.store = projects
    app.state.workflows = workflows
    app.state.jobs = jobs
    app.state.public_config = config.ui

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            request_logger.exception(
                "request_failed method=%s path=%s duration_ms=%.3f request_id=%s",
                request.method,
                request.url.path,
                (perf_counter() - started) * 1000.0,
                request_id,
            )
            raise
        response.headers["x-request-id"] = request_id
        request_logger.info(
            "request_complete method=%s path=%s status=%s duration_ms=%.3f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started) * 1000.0,
            request_id,
        )
        return response

    @app.exception_handler(CoreError)
    async def core_error_handler(_: Request, exc: CoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/")
    def root_status() -> dict[str, str]:
        return {
            "name": "zpixel_edit",
            "status": "ok",
            "web": "http://127.0.0.1:5173/",
            "health": "/api/v1/health",
            "docs": "/docs",
        }

    app.include_router(build_router())
    return app


app = create_app()
