"""Create evidence metadata only after all required capture files exist."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageCms

from .case_reader import CaptureCase
from .layout import CaptureLayout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _color_profile(path: Path) -> str:
    with Image.open(path) as image:
        profile = image.info.get("icc_profile")
    if not profile:
        return "untagged"
    try:
        name = ImageCms.getProfileName(ImageCms.ImageCmsProfile(io.BytesIO(profile)))
        return name.strip() or "embedded-icc"
    except (OSError, ValueError, TypeError):
        return "embedded-icc"


def build_metadata(
    case: CaptureCase,
    layout: CaptureLayout,
    *,
    reference_build: str,
    operator_mode: str,
    app_version: dict[str, str] | None = None,
    evidence_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    required = {"preview": layout.preview_path, "export": layout.export_path}
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required capture files missing: {', '.join(missing)}")
    files = {
        "preview": layout.preview_path,
        "export": layout.export_path,
        "mask": layout.mask_path,
        "ui_before": layout.before_path,
        "ui_after": layout.after_path,
        "ax_before": layout.before_ax_path,
        "ax_after": layout.after_ax_path,
    }
    return {
        "case_id": case.case_id,
        "reference_build": reference_build,
        "capability_id": case.capability_id,
        "parameters": case.parameters,
        "asset_id": case.asset_id,
        "asset_path": str(case.asset_path) if case.asset_path else None,
        "asset_sha256": case.asset_sha256,
        "input_path": str(case.input_path),
        "input_sha256": case.input_sha256,
        "export_format": layout.export_path.suffix.lstrip(".").upper(),
        "color_profile": _color_profile(layout.export_path),
        "captured_at": datetime.now(UTC).isoformat(),
        "operator_mode": operator_mode,
        "app_version": app_version or {},
        "evidence_sources": evidence_sources or {},
        "sha256": {
            name: sha256_file(path) for name, path in files.items() if path.is_file()
        },
    }


def write_metadata(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
