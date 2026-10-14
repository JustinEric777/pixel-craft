"""Read and validate the generated Luminar parity cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaptureCase:
    case_id: str
    capability_id: str
    input_path: Path
    input_sha256: str
    parameters: dict[str, Any]
    asset_id: str | None
    asset_path: Path | None = None
    asset_sha256: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CaptureCase:
        input_payload = payload.get("input", {})
        input_path = Path(str(input_payload.get("path", ""))).expanduser().resolve()
        required = {
            "case_id": payload.get("case_id"),
            "capability_id": payload.get("capability_id"),
            "input.path": str(input_path) if str(input_path) else None,
            "input.sha256": input_payload.get("sha256"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"capture case is missing fields: {', '.join(missing)}")
        if not input_path.is_file():
            raise FileNotFoundError(f"capture input does not exist: {input_path}")
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, dict):
            raise TypeError("capture case parameters must be an object")
        return cls(
            case_id=str(payload["case_id"]),
            capability_id=str(payload["capability_id"]),
            input_path=input_path,
            input_sha256=str(input_payload["sha256"]),
            parameters=dict(parameters),
            asset_id=str(payload["asset_id"]) if payload.get("asset_id") else None,
            asset_path=(
                Path(str(payload["asset_path"])).expanduser().resolve()
                if payload.get("asset_path")
                else None
            ),
            asset_sha256=(
                str(payload["asset_sha256"])
                if payload.get("asset_sha256")
                else None
            ),
        )


def load_cases(
    path: Path,
    *,
    case_ids: set[str] | None = None,
    capability_ids: set[str] | None = None,
    limit: int | None = None,
) -> list[CaptureCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = list(payload.get("cases", []))
    if case_ids:
        raw_cases = [item for item in raw_cases if item.get("case_id") in case_ids]
        missing = sorted(case_ids - {str(item.get("case_id")) for item in raw_cases})
        if missing:
            raise ValueError(f"unknown case ids: {', '.join(missing)}")
    if capability_ids:
        raw_cases = [
            item for item in raw_cases if item.get("capability_id") in capability_ids
        ]
    if limit is not None:
        if limit <= 0:
            raise ValueError("capture case limit must be positive")
        raw_cases = raw_cases[:limit]
    return [CaptureCase.from_payload(item) for item in raw_cases]
