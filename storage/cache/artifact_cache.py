"""Content-addressed JSON and NumPy artifact cache.

The cache is deliberately independent of the edit graph. A source image and a
model/pre-postprocess contract determine an artifact key, so face boxes,
segmentation summaries and embeddings can be reused by several tools without
running the same ONNX session repeatedly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


class ArtifactCache:
    """Store reproducible intermediate results below one project data root."""

    # v3 makes the artifact envelope explicit: array payloads and the JSON
    # record share one versioned contract and carry runtime/model provenance.
    version = "artifact-cache-v3"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def source_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def key(
        self,
        *,
        source_hash: str,
        artifact_name: str,
        model_id: str,
        model_hash: str | None,
        preprocess_version: str,
        postprocess_version: str,
    ) -> str:
        contract = {
            "cache_version": self.version,
            "source_hash": source_hash,
            "artifact_name": artifact_name,
            "model_id": model_id,
            "model_hash": model_hash,
            "preprocess_version": preprocess_version,
            "postprocess_version": postprocess_version,
        }
        encoded = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _json_path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def _array_path(self, key: str) -> Path:
        return self.root / f"{key}.npy"

    def _bundle_path(self, key: str) -> Path:
        return self.root / f"{key}.npz"

    def get_json(self, key: str) -> dict[str, Any] | None:
        path = self._json_path(key)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def put_json(self, key: str, value: dict[str, Any]) -> Path:
        path = self._json_path(key)
        value = {"artifact_cache_version": self.version, **value}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
        return path

    def put_array(
        self,
        key: str,
        value: np.ndarray,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        path = self._array_path(key)
        temporary = path.with_suffix(".tmp.npy")
        with temporary.open("wb") as handle:
            np.save(handle, np.asarray(value))
        temporary.replace(path)
        if metadata:
            self.put_json(
                key,
                {
                    "artifact_path": path.name,
                    "artifact_dtype": str(np.asarray(value).dtype),
                    "artifact_shape": list(np.asarray(value).shape),
                    **metadata,
                },
            )
        return path

    def get_array(self, key: str) -> np.ndarray | None:
        path = self._array_path(key)
        if not path.is_file():
            return None
        try:
            value = np.load(path, allow_pickle=False)
        except (OSError, ValueError):
            return None
        return np.asarray(value)

    def put_array_bundle(self, key: str, values: dict[str, np.ndarray]) -> Path:
        """Atomically preserve every raw tensor emitted by one inference call."""

        path = self._bundle_path(key)
        temporary = path.with_suffix(".tmp.npz")
        with temporary.open("wb") as handle:
            np.savez_compressed(
                handle, **{name: np.asarray(value) for name, value in values.items()}
            )
        temporary.replace(path)
        return path

    def list_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            record = self.get_json(path.stem)
            if record:
                records.append(record)
        return records

    def get_envelope(self, key: str) -> dict[str, Any] | None:
        """Return the v3 record only when it carries the current contract."""
        record = self.get_json(key)
        if not record or record.get("artifact_cache_version") != self.version:
            return None
        return record
