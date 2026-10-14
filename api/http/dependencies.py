"""FastAPI dependency accessors."""

from __future__ import annotations

from fastapi import Request

from services.editor.service import EditorService
from services.jobs.service import InferenceJobService
from services.multi_image.service import MultiImageService


def get_editor(request: Request) -> EditorService:
    return request.app.state.editor


def get_workflows(request: Request) -> MultiImageService:
    return request.app.state.workflows


def get_jobs(request: Request) -> InferenceJobService:
    return request.app.state.jobs
