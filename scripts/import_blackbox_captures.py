"""Attach legally captured Luminar preview/export/UI evidence to parity cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _attach(
    case: dict[str, Any], capture_root: Path, expected_reference_id: str | None = None
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    output_root = capture_root / "luminar_outputs" / case_id
    ui_root = capture_root / "luminar_ui" / case_id
    captures = dict(case.get("captures", {}))
    metadata_path = capture_root / "metadata" / f"{case_id}.json"
    available_capture_paths = [
        output_root / "preview.png",
        output_root / "export.png",
        output_root / "mask.png",
        ui_root / "after.png",
    ]
    if expected_reference_id and any(path.is_file() for path in available_capture_paths):
        if not metadata_path.is_file():
            return {
                **case,
                "status": "invalid-reference",
                "pending_reason": f"capture metadata is missing: {metadata_path}",
            }
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        actual_reference_id = metadata.get("reference_build")
        if actual_reference_id != expected_reference_id:
            return {
                **case,
                "status": "invalid-reference",
                "pending_reason": (
                    f"capture reference mismatch: {actual_reference_id!r} != "
                    f"{expected_reference_id!r}"
                ),
            }
    for key, (root, filename) in {
        "luminar_preview": (output_root, "preview.png"),
        "luminar_export": (output_root, "export.png"),
        "luminar_mask": (output_root, "mask.png"),
        "luminar_ui": (ui_root, "after.png"),
    }.items():
        path = root / filename
        if path.is_file():
            captures[key] = str(path.resolve())
    updated = {**case, "captures": captures}
    reference = captures.get("luminar_export") or captures.get("luminar_preview")
    if reference:
        has_candidate = bool(
            updated.get("candidate", {}).get("export")
            or updated.get("candidate", {}).get("preview")
        )
        updated["status"] = "ready" if has_candidate else "pending-candidate"
        updated["pending_reason"] = (
            None if updated["status"] == "ready" else "candidate output is not attached"
        )
        updated["reference_hashes"] = {
            key: _sha256(Path(value))
            for key, value in captures.items()
            if key.startswith("luminar_") and value and Path(value).is_file()
        }
    return updated


def attach_payload(
    payload: dict[str, Any],
    capture_root: Path,
    *,
    expected_reference_id: str | None = None,
) -> dict[str, Any]:
    cases = [
        _attach(case, capture_root, expected_reference_id)
        for case in payload.get("cases", [])
    ]
    result = {
        **payload,
        "generated_by": "scripts/import_blackbox_captures.py",
        "cases": cases,
    }
    result["status"] = (
        "ready"
        if any(case.get("status") == "ready" for case in cases)
        else "pending-reference"
    )
    return result


def run(
    cases_path: Path,
    capture_root: Path,
    output_path: Path,
    *,
    expected_reference_id: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    result = attach_payload(
        payload, capture_root, expected_reference_id=expected_reference_id
    )
    cases = result["cases"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "case_count": len(cases),
        "captured": sum(
            bool(
                case.get("captures", {}).get("luminar_export")
                or case.get("captures", {}).get("luminar_preview")
            )
            for case in cases
        ),
        "output": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--capture-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases = (args.cases or profile.cases_path).resolve()
    capture_root = (args.capture_root or profile.capture_root).resolve()
    output = (
        args.output or profile.diagnostics_root / "parity-cases-attached.json"
    ).resolve()
    report = run(
        cases,
        capture_root,
        output,
        expected_reference_id=profile.id,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
