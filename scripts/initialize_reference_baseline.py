"""Create a pending versioned reference baseline without copying old outputs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import ReferenceProfile, load_reference_catalog


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _project_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _pending_case(case: dict[str, Any], reference_id: str) -> dict[str, Any]:
    return {
        **case,
        "reference_id": reference_id,
        "captures": {
            "luminar_preview": None,
            "luminar_export": None,
            "luminar_mask": None,
            "luminar_ui": None,
        },
        "candidate": {"preview": None, "export": None},
        "status": "pending-reference",
        "pending_reason": "Luminar output for the active reference is not attached",
    }


def initialize(
    target: ReferenceProfile,
    *,
    source: ReferenceProfile | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    if source is not None and source.id == target.id:
        raise ValueError("source and target reference ids must differ")
    generated_at = datetime.now(UTC).isoformat()
    created: list[str] = []
    if source is not None:
        for path in (source.cases_path, source.matrix_path):
            if not path.is_file():
                raise FileNotFoundError(f"source reference file is missing: {path}")
        if overwrite or not target.cases_path.exists():
            source_cases = json.loads(source.cases_path.read_text(encoding="utf-8"))
            cases = [
                _pending_case(case, target.id) for case in source_cases.get("cases", [])
            ]
            _write_json(
                target.cases_path,
                {
                    "version": "1.0",
                    "generated_by": "scripts/initialize_reference_baseline.py",
                    "generated_at": generated_at,
                    "reference_id": target.id,
                    "seed_reference_id": source.id,
                    "dataset_fingerprint": source_cases.get("dataset_fingerprint"),
                    "status": "pending-reference",
                    "case_count": len(cases),
                    "cases": cases,
                },
            )
            created.append(str(target.cases_path))
        if overwrite or not target.matrix_path.exists():
            matrix = json.loads(source.matrix_path.read_text(encoding="utf-8"))
            matrix.update(
                {
                    "version": "1.0",
                    "generated_by": "scripts/initialize_reference_baseline.py",
                    "generated_at": generated_at,
                    "reference_build": target.id,
                    "seed_reference_id": source.id,
                    "scope": (
                        f"{target.product} {target.version} build {target.build} black-box "
                        "capture plan; validation inputs are reused, all outputs are pending"
                    ),
                }
            )
            coverage = matrix.get("coverage")
            if isinstance(coverage, dict):
                coverage["exact_match_gate"] = (
                    f"requires Luminar {target.version} preview/export and UI captures"
                )
            for sample in matrix.get("samples", []):
                sample["capture_status"] = "input-only"
                sample["reference_output_status"] = "pending-black-box-capture"
                label = str(sample.get("label", ""))
                if label:
                    sample["label"] = label.split(" · local ", 1)[0] + " · local validation input"
            _write_json(target.matrix_path, matrix)
            created.append(str(target.matrix_path))
    manifest = {
        "version": "1.0",
        "reference_id": target.id,
        "product": target.product,
        "app_version": target.version,
        "build": target.build,
        "bundle_id": target.bundle_id,
        "locale": target.locale,
        "platform": target.platform,
        "exact_gate_enabled": target.exact_gate_enabled,
        "status": "pending-reference",
        "generated_at": generated_at,
        "cases_path": _project_path(target.cases_path),
        "matrix_path": _project_path(target.matrix_path),
        "capture_root": _project_path(target.capture_root),
        "ui_reference_root": _project_path(target.ui_reference_root),
        "observations_root": _project_path(target.observations_root),
        "seed_reference_id": source.id if source else None,
        "notes": (
            "Reference inputs and plans may be retained across versions; captured outputs, UI, "
            "parameters, thresholds, and exactness results are version-specific."
        ),
    }
    if overwrite or not target.manifest_path.exists():
        _write_json(target.manifest_path, manifest)
        created.append(str(target.manifest_path))
    return {"reference_id": target.id, "created": created, "manifest": str(target.manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--seed-reference-id")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    catalog = load_reference_catalog(args.config, project_root=ROOT)
    target = catalog.resolve(args.reference_id)
    source = catalog.resolve(args.seed_reference_id) if args.seed_reference_id else None
    report = initialize(target, source=source, overwrite=args.overwrite)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
