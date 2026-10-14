"""Reject parity artifacts built from a different validation dataset snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.build_validation_manifest import check


def run(
    source_root: Path,
    snapshot_root: Path,
    manifest_path: Path,
    matrix_path: Path,
    cases_path: Path,
    queue_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    fingerprint = str(manifest.get("dataset_fingerprint", ""))
    artifacts = {
        "matrix": matrix.get("dataset_fingerprint"),
        "cases": cases.get("dataset_fingerprint"),
        "queue": queue.get("dataset_fingerprint"),
    }
    mismatched_artifacts = sorted(
        name for name, value in artifacts.items() if not fingerprint or value != fingerprint
    )
    manifest_records = {
        (str(item["path"]), str(item["sha256"])) for item in manifest.get("records", [])
    }
    invalid_case_inputs = sorted(
        str(case.get("case_id"))
        for case in cases.get("cases", [])
        if (
            str(case.get("input", {}).get("path", "")),
            str(case.get("input", {}).get("sha256", "")),
        )
        not in manifest_records
    )
    manifest_check = check(source_root, manifest_path, snapshot_root)
    issues = {
        "mismatched_artifacts": mismatched_artifacts,
        "invalid_case_inputs": invalid_case_inputs,
        "manifest_status": manifest_check["status"],
    }
    passed = (
        manifest_check["status"] == "fresh"
        and not mismatched_artifacts
        and not invalid_case_inputs
    )
    return {
        "version": "1.0",
        "generated_by": "scripts/validate_dataset_freshness.py",
        "gate": "passed" if passed else "blocked",
        "dataset_fingerprint": fingerprint or None,
        "manifest": manifest_check,
        "artifacts": artifacts,
        "case_count": len(cases.get("cases", [])),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ROOT / "test_data/parity/inputs",
        help="frozen combined validation input root, including exact-only fixtures",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=ROOT / "test_data/parity/inputs",
        help="frozen snapshot root; defaults to the combined validation input root",
    )
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "test_data/parity/validation-samples.json"
    )
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    report = run(
        args.source_dir.resolve(),
        args.snapshot_dir.resolve(),
        args.manifest.resolve(),
        profile.matrix_path,
        profile.cases_path,
        queue,
    )
    output = (args.output or profile.diagnostics_root / "dataset-freshness.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "dataset_fingerprint": report["dataset_fingerprint"],
                "case_count": report["case_count"],
                "issues": report["issues"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
