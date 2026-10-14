"""Versioned model input/output contracts used by probes and parity reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TensorContract:
    name: str
    shape: tuple[int | str, ...]
    dtype: str
    semantic: str | None = None


@dataclass(frozen=True)
class ModelContract:
    model_id: str
    format: str
    input_layout: str = "NCHW"
    color_order: str = "RGB"
    normalization: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[TensorContract, ...] = ()
    outputs: tuple[TensorContract, ...] = ()
    postprocess: dict[str, Any] = field(default_factory=dict)
    signature_status: str = "pending"
    runtime_status: str = "pending"
    source_backend_parity: str = "not-applicable"
    luminar_effect_parity: str = "pending-reference"
    version: str = "contract-v2"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["inputs"] = [asdict(item) for item in self.inputs]
        payload["outputs"] = [asdict(item) for item in self.outputs]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelContract:
        return cls(
            model_id=str(payload["model_id"]),
            format=str(payload["format"]),
            input_layout=str(payload.get("input_layout", "NCHW")),
            color_order=str(payload.get("color_order", "RGB")),
            normalization=dict(payload.get("normalization", {})),
            inputs=tuple(TensorContract(**item) for item in payload.get("inputs", [])),
            outputs=tuple(TensorContract(**item) for item in payload.get("outputs", [])),
            postprocess=dict(payload.get("postprocess", {})),
            signature_status=str(payload.get("signature_status", "pending")),
            runtime_status=str(payload.get("runtime_status", "pending")),
            source_backend_parity=str(
                payload.get("source_backend_parity", "not-applicable")
            ),
            luminar_effect_parity=str(
                payload.get("luminar_effect_parity", "pending-reference")
            ),
            version=str(payload.get("version", "contract-v2")),
        )


class ModelContractCatalog:
    """Filesystem adapter for contracts; absent contracts remain explicit."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, model_id: str) -> Path:
        safe_id = "".join(char if char.isalnum() or char in "._-" else "_" for char in model_id)
        return self.root / f"{safe_id}.json"

    def get(self, model_id: str) -> ModelContract | None:
        path = self.path_for(model_id)
        if not path.is_file():
            return None
        try:
            return ModelContract.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def put(self, contract: ModelContract) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(contract.model_id)
        path.write_text(json.dumps(contract.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
