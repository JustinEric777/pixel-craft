"""HTTP request DTOs kept separate from core entities."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EditRequest(BaseModel):
    effect: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    mask_artifact: str | None = None
    enabled: bool = True


class PreviewRequest(BaseModel):
    width: int | None = None


class ReorderRequest(BaseModel):
    edit_ids: list[str]


class CatalogAssetUpdateRequest(BaseModel):
    favorite: bool | None = None
    rejected: bool | None = None
    rating: int | None = Field(default=None, ge=0, le=5)
    color_label: str | None = None
    deleted: bool | None = None
    rotation_delta: int | None = Field(default=None, ge=-270, le=270)


class AnalysisJobRequest(BaseModel):
    models: list[str] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class LayerMaterialRequest(BaseModel):
    material_id: str = Field(min_length=1)


class LayerUpdateRequest(BaseModel):
    visible: bool | None = None
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    blend_mode: str | None = None
    scale: float | None = Field(default=None, ge=0.1, le=8.0)
    offset_x: float | None = Field(default=None, ge=-2.0, le=2.0)
    offset_y: float | None = Field(default=None, ge=-2.0, le=2.0)
    rotation: float | None = Field(default=None, ge=-180.0, le=180.0)
    flip_x: bool | None = None
    flip_y: bool | None = None
    mask_artifact: str | None = None


class LayerOrderRequest(BaseModel):
    layer_ids: list[str]


class WorkflowFrameOrderRequest(BaseModel):
    frame_ids: list[str]


class MaskUpdateRequest(BaseModel):
    inverted: bool | None = None
    density: float | None = Field(default=None, ge=0.0, le=1.0)
    feather: float | None = Field(default=None, ge=0.0, le=100.0)


class MaskBrushStrokeRequest(BaseModel):
    points: list[tuple[float, float]] = Field(min_length=2)


class MaskBrushRequest(BaseModel):
    owner_type: Literal["edit", "layer"]
    owner_id: str = Field(min_length=1)
    strokes: list[MaskBrushStrokeRequest] = Field(min_length=1)
    size: int = Field(ge=1, le=500)
    softness: int = Field(ge=0, le=100)
    strength: int = Field(ge=1, le=100)
