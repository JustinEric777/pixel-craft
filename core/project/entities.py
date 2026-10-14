"""Pure project aggregate entities.

No filesystem, image library, FastAPI or inference-runtime dependency belongs
in this module. Those concerns are implemented by application/infrastructure
adapters around these values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..errors import CapabilityConflictError, EditNotFoundError


class ArtifactKind(StrEnum):
    IMAGE = "image"
    MASK = "mask"
    DEPTH = "depth"
    LANDMARKS = "landmarks"
    BOXES = "boxes"
    EMBEDDING = "embedding"
    METADATA = "metadata"


@dataclass(frozen=True)
class ImageRef:
    path: Path
    width: int | None = None
    height: int | None = None
    color_space: str = "sRGB"


@dataclass
class Artifact:
    kind: ArtifactKind
    name: str
    value: Any
    source_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EditNode:
    id: str
    effect: str
    parameters: dict[str, Any] = field(default_factory=dict)
    mask_artifact: str | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "effect": self.effect,
            "parameters": self.parameters,
            "mask_artifact": self.mask_artifact,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class MaskRef:
    id: str
    path: Path
    owner_type: str
    owner_id: str
    width: int
    height: int
    source: str = "imported"
    inverted: bool = False
    density: float = 1.0
    feather: float = 0.0
    brush_size: int | None = None
    brush_softness: int | None = None
    brush_strength: int | None = None
    sha256: str = ""
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "owner_type": self.owner_type,
            "owner_id": self.owner_id,
            "width": self.width,
            "height": self.height,
            "source": self.source,
            "inverted": self.inverted,
            "density": self.density,
            "feather": self.feather,
            "brush_size": self.brush_size,
            "brush_softness": self.brush_softness,
            "brush_strength": self.brush_strength,
            "sha256": self.sha256,
            "version": self.version,
        }


@dataclass(frozen=True)
class LayerRef:
    id: str
    asset_id: str
    path: Path
    name: str
    source_kind: str = "upload"
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    rotation: float = 0.0
    flip_x: bool = False
    flip_y: bool = False
    mask_artifact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "path": str(self.path),
            "name": self.name,
            "source_kind": self.source_kind,
            "visible": self.visible,
            "opacity": self.opacity,
            "blend_mode": self.blend_mode,
            "scale": self.scale,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "rotation": self.rotation,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "mask_artifact": self.mask_artifact,
        }


@dataclass
class ProjectState:
    source: ImageRef
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    masks: dict[str, MaskRef] = field(default_factory=dict)
    layers: list[LayerRef] = field(default_factory=list)
    edits: list[EditNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def append_edit(self, edit: EditNode) -> None:
        self._record_history()
        self.edits.append(edit)

    def append_edits(self, edits: list[EditNode]) -> None:
        if not edits:
            return
        self._record_history()
        self.edits.extend(edits)

    def replace_edit(self, edit: EditNode) -> None:
        for index, current in enumerate(self.edits):
            if current.id == edit.id:
                self._record_history()
                self.edits[index] = edit
                return
        raise EditNotFoundError("edit not found")

    def remove_edit(self, edit_id: str) -> None:
        if not any(edit.id == edit_id for edit in self.edits):
            raise EditNotFoundError("edit not found")
        self._record_history()
        self.edits = [edit for edit in self.edits if edit.id != edit_id]
        self.masks = {
            mask_id: mask
            for mask_id, mask in self.masks.items()
            if not (mask.owner_type == "edit" and mask.owner_id == edit_id)
        }

    def reorder_edits(self, edit_ids: list[str]) -> None:
        current = {edit.id: edit for edit in self.edits}
        if set(current) != set(edit_ids) or len(edit_ids) != len(current):
            raise CapabilityConflictError("edit_ids must contain every edit exactly once")
        self._record_history()
        self.edits = [current[edit_id] for edit_id in edit_ids]

    def append_layer(self, layer: LayerRef) -> None:
        self._record_history()
        self.layers.append(layer)

    def replace_layer(self, layer: LayerRef) -> None:
        for index, current in enumerate(self.layers):
            if current.id == layer.id:
                self._record_history()
                self.layers[index] = layer
                return
        raise CapabilityConflictError("layer not found")

    def remove_layer(self, layer_id: str) -> None:
        if not any(layer.id == layer_id for layer in self.layers):
            raise CapabilityConflictError("layer not found")
        self._record_history()
        self.layers = [layer for layer in self.layers if layer.id != layer_id]
        self.masks = {
            mask_id: mask
            for mask_id, mask in self.masks.items()
            if not (mask.owner_type == "layer" and mask.owner_id == layer_id)
        }

    def reorder_layers(self, layer_ids: list[str]) -> None:
        current = {layer.id: layer for layer in self.layers}
        if set(current) != set(layer_ids) or len(layer_ids) != len(current):
            raise CapabilityConflictError("layer_ids must contain every layer exactly once")
        self._record_history()
        self.layers = [current[layer_id] for layer_id in layer_ids]

    def attach_mask(self, mask: MaskRef) -> None:
        if mask.owner_type not in {"edit", "layer"}:
            raise CapabilityConflictError("mask owner_type must be edit or layer")
        if mask.owner_type == "edit":
            owner_index = next(
                (index for index, edit in enumerate(self.edits) if edit.id == mask.owner_id),
                None,
            )
            if owner_index is None:
                raise EditNotFoundError("mask edit owner not found")
            previous_mask_id = self.edits[owner_index].mask_artifact
        else:
            owner_index = next(
                (index for index, layer in enumerate(self.layers) if layer.id == mask.owner_id),
                None,
            )
            if owner_index is None:
                raise CapabilityConflictError("mask layer owner not found")
            previous_mask_id = self.layers[owner_index].mask_artifact

        self._record_history()
        if mask.owner_type == "edit":
            edit = self.edits[owner_index]
            self.edits[owner_index] = EditNode(
                edit.id,
                edit.effect,
                edit.parameters,
                mask.id,
                edit.enabled,
            )
        else:
            layer = self.layers[owner_index]
            self.layers[owner_index] = LayerRef(
                **{**layer.__dict__, "mask_artifact": mask.id}
            )
        if previous_mask_id and previous_mask_id != mask.id:
            self.masks.pop(previous_mask_id, None)
        self.masks[mask.id] = mask

    def replace_mask(self, mask: MaskRef) -> None:
        if mask.id not in self.masks:
            raise CapabilityConflictError("mask not found")
        self._record_history()
        self.masks[mask.id] = mask

    def remove_mask(self, mask_id: str) -> None:
        mask = self.masks.get(mask_id)
        if mask is None:
            raise CapabilityConflictError("mask not found")
        self._record_history()
        if mask.owner_type == "edit":
            self.edits = [
                EditNode(
                    edit.id,
                    edit.effect,
                    edit.parameters,
                    None if edit.mask_artifact == mask_id else edit.mask_artifact,
                    edit.enabled,
                )
                for edit in self.edits
            ]
        else:
            self.layers = [
                LayerRef(
                    **{
                        **layer.__dict__,
                        "mask_artifact": (
                            None if layer.mask_artifact == mask_id else layer.mask_artifact
                        ),
                    }
                )
                for layer in self.layers
            ]
        self.masks.pop(mask_id)

    def reset_to_original(self) -> None:
        if not self.edits and not self.layers and not self.masks:
            return
        self._record_history()
        self.edits = []
        self.layers = []
        self.masks = {}

    def undo(self) -> None:
        undo_stack = self.metadata.setdefault("undo_stack", [])
        if not undo_stack:
            return
        redo_stack = self.metadata.setdefault("redo_stack", [])
        redo_stack.append(self._snapshot())
        self._restore(undo_stack.pop())

    def redo(self) -> None:
        redo_stack = self.metadata.setdefault("redo_stack", [])
        if not redo_stack:
            return
        undo_stack = self.metadata.setdefault("undo_stack", [])
        undo_stack.append(self._snapshot())
        self._restore(redo_stack.pop())

    def _record_history(self) -> None:
        self.metadata.setdefault("undo_stack", []).append(self._snapshot())
        self.metadata["redo_stack"] = []

    def _snapshot(self) -> dict[str, Any]:
        return {
            "edits": [edit.to_dict() for edit in self.edits],
            "layers": [layer.to_dict() for layer in self.layers],
            "masks": {mask_id: mask.to_dict() for mask_id, mask in self.masks.items()},
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self.edits = [EditNode(**item) for item in snapshot.get("edits", [])]
        self.layers = [
            LayerRef(**{**item, "path": Path(str(item["path"]))})
            for item in snapshot.get("layers", [])
        ]
        self.masks = {
            mask_id: MaskRef(**{**item, "path": Path(str(item["path"]))})
            for mask_id, item in snapshot.get("masks", {}).items()
        }
