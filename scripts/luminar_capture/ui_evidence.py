"""Stable fixture identities for native Luminar UI reference evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from configs.luminar_sampling import LuminarSamplingConfig

from .sampling_queue import SamplingQueueRecord


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ui_fixture_identity(
    record: SamplingQueueRecord, config: LuminarSamplingConfig
) -> tuple[str, str]:
    """Return a reproducible fixture id/hash for one native UI state."""

    source = record.payload.get("input")
    if isinstance(source, dict):
        path = Path(str(source["path"]))
        return f"single-image:{path.name}", str(source["sha256"])
    state = str(record.payload["matrix_state_id"])
    workspace = str(record.payload["workspace_state"])
    if workspace in {"multi-image", "multi-image-complete"}:
        root = config.multi_image_validation_root / "hdr_merge"
        records = [
            {"name": path.name, "sha256": sha256_file(path)}
            for path in sorted(root.iterdir())
            if path.is_file()
        ]
        if len(records) < 2:
            raise RuntimeError(f"multi-image UI fixture is incomplete: {root}")
        fixture_id = "multi-image:hdr_merge"
        payload = {"inputs": records, "matrix_state_id": state}
    else:
        fixture_id = f"catalog:{config.catalog_collection}"
        payload = {"catalog_collection": config.catalog_collection, "state": state}
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return fixture_id, hashlib.sha256(encoded).hexdigest()
