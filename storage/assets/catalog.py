"""Resolve effect assets by manifest id without exposing filesystem traversal."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SELECTABLE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".cube"
}


class AssetCatalog:
    def __init__(
        self,
        root: Path,
        manifest: Path | None = None,
        layer_library: dict[str, Any] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.manifest = manifest or root / "manifests" / "registry.json"
        self.layer_library = layer_library or {}
        self._payload: dict[str, Any] | None = None
        self._layer_groups: list[dict[str, Any]] | None = None

    @property
    def payload(self) -> dict[str, Any]:
        if self._payload is None:
            if not self.manifest.exists():
                self._payload = {"count": 0, "families": [], "records": []}
            else:
                self._payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        return self._payload

    def list(self, family: str | None = None) -> list[dict[str, Any]]:
        records = self.payload.get("records", [])
        return [
            record
            for record in records
            if (family is None or record.get("family") == family)
            and Path(str(record.get("path", ""))).suffix.lower() in SELECTABLE_EXTENSIONS
        ]

    def require(self, asset_id: str) -> dict[str, Any]:
        for record in self.list():
            if record.get("id") == asset_id:
                return record
        raise KeyError(f"asset is not registered: {asset_id}")

    def resolve(self, asset_id: str) -> Path:
        record = self.require(asset_id)
        candidate = (self.root / str(record["path"])).resolve()
        if not candidate.is_relative_to(self.root) or not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    def layer_material_groups(self) -> list[dict[str, Any]]:
        """Return the 38 overlay materials published by Luminar's root configs."""
        if self._layer_groups is None:
            self._layer_groups = [
                self._read_layer_group(spec)
                for spec in self.layer_library.get("groups", [])
            ]
        return self._layer_groups

    def require_layer_material(self, material_id: str) -> dict[str, Any]:
        for group in self.layer_material_groups():
            for material in group["items"]:
                if material["id"] == material_id:
                    return material
        raise KeyError(f"layer material is not registered: {material_id}")

    def resolve_layer_material(self, material_id: str) -> Path:
        record = self.require_layer_material(material_id)
        candidate = (self.root / record["path"]).resolve()
        if not candidate.is_relative_to(self.root) or not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    def _read_layer_group(self, spec: dict[str, Any]) -> dict[str, Any]:
        collection_id = str(spec["collection_id"])
        group_root = self.root / "materials" / "OverlayTextures" / "Free" / collection_id
        payload = json.loads((group_root / "config.json").read_text(encoding="utf-8"))
        items = [self._read_layer_material(group_root, str(item_id)) for item_id in payload["items"]]
        expected = int(spec.get("expected_count", len(items)))
        if len(items) != expected:
            raise ValueError(
                f"layer material group {collection_id} has {len(items)} items; expected {expected}"
            )
        return {
            "id": str(spec["id"]),
            "label": str(spec.get("label") or self._localized_name(group_root) or collection_id),
            "collection_id": collection_id,
            "preview_limit": int(spec.get("preview_limit", 6)),
            "count": len(items),
            "items": items,
        }

    def _read_layer_material(self, group_root: Path, material_id: str) -> dict[str, Any]:
        material_root = group_root / material_id
        payload = json.loads((material_root / "config.json").read_text(encoding="utf-8"))
        properties = payload.get("properties", {})
        source = (material_root / str(payload["path"])).resolve()
        if not source.is_relative_to(self.root) or not source.is_file():
            raise FileNotFoundError(source)
        return {
            "id": material_id,
            "name": self._localized_name(material_root) or source.stem,
            "path": str(source.relative_to(self.root)),
            "blend_mode": str(properties.get("blend", "normal")),
            "opacity": float(properties.get("opacity", 1.0)),
        }

    @staticmethod
    def _localized_name(root: Path) -> str | None:
        for filename in ("zh-Hans.strings", "zh-CN.strings", "en.strings"):
            path = root / "localizations" / filename
            if not path.is_file():
                continue
            match = re.search(r'"Name"\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
            if match:
                return match.group(1)
        return None
