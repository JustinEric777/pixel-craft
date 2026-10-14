"""Compare fixed-viewport web screenshots with captured Luminar UI references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.ui_regions import validate_region_manifest


def _compare(
    reference: Path, candidate: Path, *, mask: np.ndarray | None = None
) -> dict[str, Any]:
    with Image.open(reference) as image:
        expected = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    with Image.open(candidate) as image:
        actual = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    if expected.shape != actual.shape:
        return {
            "shape_match": False,
            "reference_shape": list(expected.shape),
            "candidate_shape": list(actual.shape),
        }
    delta = np.abs(expected - actual)
    if mask is not None:
        if mask.shape != expected.shape[:2] or not mask.any():
            return {"shape_match": True, "region_valid": False}
        selected = delta[mask]
        changed = np.any(delta > (2.0 / 255.0), axis=2)[mask]
        return {
            "shape_match": True,
            "region_valid": True,
            "pixel_count": int(mask.sum()),
            "coverage_ratio": float(mask.mean()),
            "mae": float(selected.mean()),
            "changed_pixel_ratio": float(changed.mean()),
        }
    return {
        "shape_match": True,
        "mae": float(delta.mean()),
        "changed_pixel_ratio": float(np.any(delta > (2.0 / 255.0), axis=2).mean()),
    }


def run(
    config_path: Path,
    reference_root: Path,
    candidate_root: Path,
    *,
    ui_matrix: dict[str, Any],
    reference_manifest: dict[str, Any] | None = None,
    reference_id: str | None = None,
    region_manifest: dict[str, Any] | None = None,
    region_reference_root: Path | None = None,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    capture = config.get("capture", {})
    thresholds = config.get("thresholds", {}).get("ui", {})
    matrix_records = {
        str(record["id"]): record
        for record in ui_matrix.get("records", [])
        if isinstance(record, dict) and record.get("id")
    }
    expected_keys = {
        (f"{width}x{height}", str(record["id"]))
        for width, height in capture.get("ui_viewports", [])
        for record in matrix_records.values()
    }
    pixel_expected_keys = {
        key
        for key in expected_keys
        if matrix_records[key[1]].get("comparison_mode", "pixel") == "pixel"
    }
    matrix_issues: list[dict[str, Any]] = []
    if ui_matrix.get("reference_id") != reference_id:
        matrix_issues.append({"id": "ui-matrix-reference-id-mismatch"})
    matrix_fingerprint = str(ui_matrix.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        matrix_issues.append({"id": "invalid-ui-matrix-fingerprint"})
    region_issues: list[dict[str, Any]] = []
    region_masks: dict[tuple[str, str], np.ndarray] = {}
    if region_manifest is not None:
        region_issues, region_masks = validate_region_manifest(
            region_manifest,
            reference_root=(region_reference_root or reference_root),
            reference_id=str(reference_id or ""),
            expected=pixel_expected_keys,
        )
    records: list[dict[str, Any]] = []
    state_ids = sorted(matrix_records)
    for width, height in capture.get("ui_viewports", []):
        viewport = f"{width}x{height}"
        for state in state_ids:
            comparison_mode = matrix_records[state].get("comparison_mode", "pixel")
            if comparison_mode == "semantic":
                records.append(
                    {
                        "viewport": viewport,
                        "state": state,
                        "status": "delegated-to-interaction",
                        "comparison_mode": "semantic",
                        "delegated_gate": "interaction-execution",
                    }
                )
                continue
            reference = reference_root / viewport / f"{state}.png"
            candidate = candidate_root / viewport / f"{state}.png"
            if not reference.is_file() or not candidate.is_file():
                records.append(
                    {
                        "viewport": viewport,
                        "state": state,
                        "status": "pending-reference",
                        "missing": [
                            name
                            for name, path in (
                                ("reference", reference),
                                ("candidate", candidate),
                            )
                            if not path.is_file()
                        ],
                    }
                )
                continue
            full_screen_metrics = _compare(reference, candidate)
            metrics = _compare(
                reference,
                candidate,
                mask=region_masks.get((viewport, str(state))) if region_manifest is not None else None,
            )
            passed = bool(
                metrics.get("shape_match")
                and metrics.get("mae", 1.0) <= float(thresholds.get("mae_max", 0.03))
                and metrics.get("changed_pixel_ratio", 1.0)
                <= float(thresholds.get("changed_pixel_ratio_max", 0.02))
            )
            records.append(
                {
                    "viewport": viewport,
                    "state": state,
                    "status": "passed" if passed else "failed",
                    "comparison_mode": "pixel",
                    "metrics": metrics,
                    "full_screen_diagnostic_metrics": full_screen_metrics,
                }
            )
    manifest_issues: list[dict[str, Any]] = []
    if reference_manifest is not None:
        if reference_manifest.get("reference_id") != reference_id:
            manifest_issues.append({"id": "reference-manifest-id-mismatch"})
        if reference_manifest.get("matrix_fingerprint") != matrix_fingerprint:
            manifest_issues.append({"id": "reference-manifest-matrix-fingerprint-mismatch"})
        manifest_records = reference_manifest.get("records")
        actual = {
            (
                f"{item['viewport'][0]}x{item['viewport'][1]}",
                str(item["matrix_state_id"]),
            ): item
            for item in manifest_records or []
            if isinstance(item, dict)
            and isinstance(item.get("viewport"), list)
            and len(item["viewport"]) == 2
            and item.get("matrix_state_id")
        }
        for key in sorted(expected_keys):
            item = actual.get(key)
            if item is None:
                manifest_issues.append(
                    {"id": "missing-reference-manifest-state", "viewport": key[0], "state": key[1]}
                )
            elif item.get("status") != "verified" or item.get("issues"):
                manifest_issues.append(
                    {
                        "id": "invalid-reference-manifest-state",
                        "viewport": key[0],
                        "state": key[1],
                        "issues": item.get("issues", []),
                    }
                )
        for key in sorted(set(actual) - expected_keys):
            manifest_issues.append(
                {"id": "unexpected-reference-manifest-state", "viewport": key[0], "state": key[1]}
            )
    pending = sum(item["status"] == "pending-reference" for item in records)
    failed = sum(item["status"] == "failed" for item in records)
    pixel_passed = sum(item["status"] == "passed" for item in records)
    semantic_delegated = sum(
        item["status"] == "delegated-to-interaction" for item in records
    )
    manifest_blocked = bool(manifest_issues or region_issues or matrix_issues)
    return {
        "version": "1.0",
        "reference_id": reference_id,
        "matrix_fingerprint": matrix_fingerprint,
        "case_count": len(records),
        "passed": 0 if manifest_blocked else pixel_passed + semantic_delegated,
        "pixel_case_count": len(pixel_expected_keys),
        "pixel_passed": 0 if manifest_blocked else pixel_passed,
        "semantic_case_count": len(expected_keys) - len(pixel_expected_keys),
        "semantic_delegated": 0 if manifest_blocked else semantic_delegated,
        "failed": failed,
        "pending": pending,
        "reference_manifest_gate": "blocked" if manifest_blocked else "passed",
        "manifest_issues": manifest_issues,
        "matrix_issues": matrix_issues,
        "region_manifest_gate": "blocked" if region_issues else "passed",
        "region_issues": region_issues,
        "gate": (
            "passed"
            if records and not pending and not failed and not manifest_blocked
            else "blocked"
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/parity.yaml")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    parser.add_argument(
        "--references",
        type=Path,
    )
    parser.add_argument("--candidates", type=Path)
    parser.add_argument(
        "--output", type=Path
    )
    parser.add_argument("--regions", type=Path, default=ROOT / "configs/parity/ui-regions.json")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    references = (args.references or profile.ui_reference_root).resolve()
    candidates = (
        args.candidates or profile.diagnostics_root / "ui-candidates"
    ).resolve()
    output = (args.output or profile.diagnostics_root / "ui-parity.json").resolve()
    manifest_path = references / "reference-manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {"reference_id": profile.id, "records": []}
    )
    regions = json.loads(args.regions.read_text(encoding="utf-8"))
    ui_matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    report = run(
        args.config.resolve(),
        references,
        candidates,
        ui_matrix=ui_matrix,
        reference_manifest=manifest,
        reference_id=profile.id,
        region_manifest=regions,
        region_reference_root=references,
    )
    report["reference_id"] = profile.id
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("case_count", "passed", "failed", "pending", "gate")},
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
