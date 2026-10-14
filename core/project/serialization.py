"""Stable JSON representation of the project aggregate."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .entities import Artifact, ArtifactKind, EditNode, ImageRef, LayerRef, MaskRef, ProjectState


def project_to_dict(state: ProjectState) -> dict[str, Any]:
    return {
        "source": {
            "path": str(state.source.path),
            "width": state.source.width,
            "height": state.source.height,
            "color_space": state.source.color_space,
        },
        "artifacts": {
            name: {
                "kind": artifact.kind.value,
                "name": artifact.name,
                "source_model": artifact.source_model,
                "metadata": artifact.metadata,
            }
            for name, artifact in state.artifacts.items()
        },
        "masks": {mask_id: mask.to_dict() for mask_id, mask in state.masks.items()},
        "layers": [layer.to_dict() for layer in state.layers],
        "edits": [
            {
                "id": edit.id,
                "effect": edit.effect,
                "parameters": edit.parameters,
                "mask_artifact": edit.mask_artifact,
                "enabled": edit.enabled,
            }
            for edit in state.edits
        ],
        "metadata": state.metadata,
    }


def project_from_dict(data: dict[str, Any]) -> ProjectState:
    source_data = data["source"]
    artifacts = {
        name: Artifact(
            kind=ArtifactKind(value["kind"]),
            name=value.get("name", name),
            value=None,
            source_model=value.get("source_model"),
            metadata=value.get("metadata", {}),
        )
        for name, value in data.get("artifacts", {}).items()
    }
    edits = [EditNode(**item) for item in data.get("edits", [])]
    layers = [
        LayerRef(
            id=item["id"],
            asset_id=item["asset_id"],
            path=Path(item["path"]),
            name=str(item.get("name") or Path(item["path"]).stem),
            source_kind=str(item.get("source_kind", "upload")),
            visible=bool(item.get("visible", True)),
            opacity=float(item.get("opacity", 1.0)),
            blend_mode=str(item.get("blend_mode", "normal")),
            scale=float(item.get("scale", 1.0)),
            offset_x=float(item.get("offset_x", 0.0)),
            offset_y=float(item.get("offset_y", 0.0)),
            rotation=float(item.get("rotation", 0.0)),
            flip_x=bool(item.get("flip_x", False)),
            flip_y=bool(item.get("flip_y", False)),
            mask_artifact=item.get("mask_artifact"),
        )
        for item in data.get("layers", [])
    ]
    return ProjectState(
        source=ImageRef(
            Path(source_data["path"]),
            source_data.get("width"),
            source_data.get("height"),
            source_data.get("color_space", "sRGB"),
        ),
        artifacts=artifacts,
        masks={
            mask_id: MaskRef(
                id=str(item.get("id", mask_id)),
                path=Path(item["path"]),
                owner_type=str(item["owner_type"]),
                owner_id=str(item["owner_id"]),
                width=int(item["width"]),
                height=int(item["height"]),
                source=str(item.get("source", "imported")),
                inverted=bool(item.get("inverted", False)),
                density=float(item.get("density", 1.0)),
                feather=float(item.get("feather", 0.0)),
                brush_size=(int(item["brush_size"]) if item.get("brush_size") is not None else None),
                brush_softness=(int(item["brush_softness"]) if item.get("brush_softness") is not None else None),
                brush_strength=(int(item["brush_strength"]) if item.get("brush_strength") is not None else None),
                sha256=str(item.get("sha256", "")),
                version=int(item.get("version", 1)),
            )
            for mask_id, item in data.get("masks", {}).items()
        },
        layers=layers,
        edits=edits,
        metadata=data.get("metadata", {}),
    )


def save_project(state: ProjectState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(project_to_dict(state), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_project(path: Path) -> ProjectState:
    return project_from_dict(json.loads(path.read_text(encoding="utf-8")))
