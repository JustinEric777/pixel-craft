"""Run the three local multi-image workflows on project validation images."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import resolve_reference
from scripts.compare_outputs import compare
from services.multi_image.service import MultiImageService

KINDS = ("hdr_merge", "focus_stacking", "panorama_stitching")


def _image_files(root: Path, limit: int) -> list[Path]:
    suffixes = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes),
        key=lambda path: str(path),
    )[:limit]


def _image_size(path: Path) -> list[int]:
    with Image.open(path) as image:
        return list(image.size)


def _workflow_references(capture_root: Path) -> dict[str, dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    for path in sorted((capture_root / "metadata").glob("queue-workflow-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        capability_id = str(payload.get("capability_id") or "")
        case_id = str(payload.get("case_id") or "")
        export = capture_root / "luminar_outputs" / case_id / "export.png"
        if capability_id in KINDS and case_id and export.is_file():
            references[capability_id] = {
                "case_id": case_id,
                "export": export,
                "inputs": payload.get("parameters", {}).get("inputs", []),
            }
    return references


def run(
    validation_root: Path,
    output: Path,
    *,
    capture_root: Path,
    reference_id: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    all_frames: dict[str, list[str]] = {}
    references = _workflow_references(capture_root)
    candidate_root = output.parent / "workflow-candidates"
    candidate_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="zpixel-workflow-smoke-") as temporary:
        service = MultiImageService(Path(temporary))
        for kind in KINDS:
            frames = _image_files(validation_root / kind, 3)
            if len(frames) < 2:
                raise RuntimeError(f"at least two validation images are required: {kind}")
            all_frames[kind] = [str(frame) for frame in frames]
            session = service.create(kind)
            workflow_id = session["id"]
            for frame in frames:
                service.add_frame(workflow_id, frame.name, frame.read_bytes())
            analyzed = service.analyze(workflow_id)
            preview = service.preview(workflow_id)
            exported = service.preview(workflow_id, export=True)
            candidate = candidate_root / f"{kind}.png"
            temporary_candidate = candidate.with_suffix(".tmp.png")
            shutil.copy2(exported, temporary_candidate)
            temporary_candidate.replace(candidate)
            reference = references.get(kind)
            input_hashes = [hashlib.sha256(frame.read_bytes()).hexdigest() for frame in frames]
            reference_hashes = [
                str(item.get("sha256") or "")
                for item in (reference or {}).get("inputs", [])
                if isinstance(item, dict)
            ]
            metrics = (
                compare(Path(reference["export"]), candidate)
                if reference is not None and reference_hashes == input_hashes
                else None
            )
            passed = bool(
                metrics is not None
                and metrics["shape_match"]
                and metrics["mae"] <= 0.03
                and metrics["ssim"] >= 0.98
            )
            records.append(
                {
                    "kind": kind,
                    "status": "passed" if passed else "failed",
                    "frame_count": analyzed["analysis"]["frame_count"],
                    "frame_sha256": input_hashes,
                    "preview_size": _image_size(preview),
                    "export_size": _image_size(exported),
                    "candidate_path": str(candidate),
                    "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "reference_case_id": (reference or {}).get("case_id"),
                    "reference_input_match": reference_hashes == input_hashes,
                    "metrics": metrics,
                }
            )
    report = {
        "version": "0.1.0",
        "generated_by": "scripts/run_multi_image_workflow_smoke.py",
        "reference_id": reference_id,
        "validation_root": str(validation_root),
        "frames": all_frames,
        "count": len(records),
        "passed": sum(record["status"] == "passed" for record in records),
        "failed": sum(record["status"] == "failed" for record in records),
        "gate": "passed" if records and all(record["status"] == "passed" for record in records) else "blocked",
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("count", "passed", "failed", "gate")}, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-root", type=Path, default=ROOT / "test_data/multi_image"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/diagnostics/multi-image-workflow-smoke.json"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--capture-root", type=Path)
    args = parser.parse_args()
    profile = resolve_reference(args.reference_id, project_root=ROOT)
    report = run(
        args.validation_root.resolve(),
        args.output.resolve(),
        capture_root=(args.capture_root or profile.capture_root).resolve(),
        reference_id=profile.id,
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
