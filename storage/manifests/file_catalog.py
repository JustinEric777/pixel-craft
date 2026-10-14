"""File-backed adapter for the YAML model catalog and JSON capability catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai.model.registry import ModelRegistry


class FileManifestCatalog:
    def __init__(self, model_path: Path, capability_path: Path) -> None:
        self.model_path = model_path
        self.capability_path = capability_path

    def models(self) -> dict[str, Any]:
        if not self.model_path.exists():
            return {"models": [], "message": "no project model registry configured"}
        registry = ModelRegistry.from_yaml(self.model_path)
        return {
            "models": [
                {
                    "id": record.id,
                    "logical_id": record.logical_id or record.id,
                    "task": record.task,
                    "format": record.format,
                    "path": self._model_path(record.path, registry.model_root),
                    "status": record.status,
                    "inference_class": record.inference_class,
                    "backend": record.backend,
                }
                for record in registry.records.values()
            ]
        }

    @staticmethod
    def _model_path(path: Path, model_root: Path | None) -> str:
        if model_root is not None:
            try:
                return str(path.relative_to(model_root))
            except ValueError:
                pass
        return str(path)

    def capabilities(self) -> list[dict[str, Any]]:
        if not self.capability_path.exists():
            return []
        payload = json.loads(self.capability_path.read_text(encoding="utf-8"))
        return payload.get("capabilities", [])
