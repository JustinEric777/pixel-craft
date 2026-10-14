"""Render every sampled overlay through the public layer API and compare exports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app
from configs.reference import load_reference_catalog
from scripts.compare_outputs import compare


def _raise_for_status(response: Any, stage: str) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("detail", response.text)
    except (AttributeError, ValueError):
        detail = response.text
    raise RuntimeError(f"{stage} returned HTTP {response.status_code}: {detail}")


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def run(
    *,
    metadata_root: Path,
    capture_root: Path,
    candidate_root: Path,
    output: Path,
    reference_id: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    with TestClient(create_app()) as client:
        for metadata_path in sorted(metadata_root.glob("queue-overlay-*.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            case_id = str(metadata["case_id"])
            source = Path(str(metadata["input_path"]))
            asset_id = str(metadata["asset_id"])
            material_id = Path(asset_id).parent.name
            reference = capture_root / "luminar_outputs" / case_id / "export.png"
            candidate = candidate_root / case_id / "export.png"
            try:
                with source.open("rb") as handle:
                    uploaded = client.post(
                        "/api/v1/assets",
                        files={"file": (source.name, handle, "image/jpeg")},
                    )
                _raise_for_status(uploaded, "upload")
                project_id = str(uploaded.json()["project_id"])
                layered = client.post(
                    f"/api/v1/projects/{project_id}/layers/assets",
                    json={"material_id": material_id},
                )
                _raise_for_status(layered, "add-layer-material")
                exported = client.post(f"/api/v1/projects/{project_id}/export")
                _raise_for_status(exported, "export")
                _write_atomic(candidate, exported.content)
                metrics = compare(reference, candidate)
                passed = bool(
                    metrics["shape_match"]
                    and metrics["ssim"] >= 0.98
                    and metrics["mae"] <= 0.03
                )
                records.append(
                    {
                        "case_id": case_id,
                        "asset_id": asset_id,
                        "material_id": material_id,
                        "status": "passed" if passed else "failed",
                        "reference": str(reference),
                        "candidate": str(candidate),
                        "metrics": metrics,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - preserve all per-overlay evidence
                records.append(
                    {
                        "case_id": case_id,
                        "asset_id": asset_id,
                        "material_id": material_id,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    report = {
        "version": "1.0",
        "generated_by": "scripts/run_overlay_e2e_validation.py",
        "reference_id": reference_id,
        "count": len(records),
        "passed": sum(item["status"] == "passed" for item in records),
        "failed": sum(item["status"] == "failed" for item in records),
        "gate": (
            "passed"
            if records and all(item["status"] == "passed" for item in records)
            else "blocked"
        ),
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report[key] for key in ("count", "passed", "failed", "gate")},
            ensure_ascii=False,
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--metadata-root", type=Path)
    parser.add_argument("--capture-root", type=Path)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    diagnostics = profile.diagnostics_root
    os.environ["ZPIXEL_DATA_ROOT"] = str(diagnostics / "overlay-workspace")
    os.environ.setdefault("ZPIXEL_EXECUTION_MODE", "development")
    report = run(
        metadata_root=(args.metadata_root or profile.capture_root / "metadata").resolve(),
        capture_root=(args.capture_root or profile.capture_root).resolve(),
        candidate_root=(
            args.candidate_root or diagnostics / "overlay-candidates"
        ).resolve(),
        output=(args.output or diagnostics / "overlay-e2e-current.json").resolve(),
        reference_id=profile.id,
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
