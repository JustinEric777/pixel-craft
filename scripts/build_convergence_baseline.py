"""Freeze the current parity failures and report hashes for one convergence run."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog


def _default_profile() -> Path:
    return load_reference_catalog(project_root=ROOT).resolve().diagnostics_root.parent
DEFAULT_REPORT_NAMES = {
    "quality_gates": "quality-gates-exact-final.json",
    "output_parity": "parity-report.json",
    "exact_parity": "exact-incremental-parity.json",
    "ui_parity": "ui-parity.json",
    "ui_execution": "ui-execution-evidence.json",
    "interaction": "interaction-execution.json",
    "multi_image": "multi-image-workflow-smoke.json",
    "cleanup": "test-data-cleanup-final-postcheck.json",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": _sha256(path)}


def _image_hash(value: Any) -> str | None:
    path = Path(str(value or ""))
    return _sha256(path) if path.is_file() else None


def _failed_cases(report: dict[str, Any], *, domain: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case in report.get("cases", []):
        if case.get("status") != "failed":
            continue
        metrics = case.get("metrics", {})
        failures.append(
            {
                "domain": domain,
                "case_id": case.get("case_id"),
                "capability_id": case.get("capability_id"),
                "status": "failed",
                "owner_batch": None,
                "root_cause_hypothesis": None,
                "metrics": {
                    "mae": metrics.get("mae"),
                    "ssim": metrics.get("ssim"),
                    "shape_match": metrics.get("shape_match"),
                },
                "reference": {
                    "path": metrics.get("reference"),
                    "sha256": _image_hash(metrics.get("reference")),
                },
                "candidate": {
                    "path": metrics.get("candidate"),
                    "sha256": _image_hash(metrics.get("candidate")),
                },
            }
        )
    return failures


def build_baseline(
    profile_root: Path,
    *,
    report_paths: Mapping[str, Path] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    diagnostics = profile_root / "diagnostics"
    paths = {name: diagnostics / filename for name, filename in DEFAULT_REPORT_NAMES.items()}
    if report_paths is not None:
        unknown = sorted(set(report_paths) - set(paths))
        if unknown:
            raise ValueError(f"unknown convergence report inputs: {unknown}")
        paths.update({name: path.resolve() for name, path in report_paths.items()})
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing convergence reports: {missing}")

    reports = {name: _load(path) for name, path in paths.items()}
    reference_id = reports["quality_gates"].get("reference_id")
    if not reference_id:
        raise ValueError("quality gate report is missing reference_id")
    semantic_reports = (
        "output_parity",
        "exact_parity",
        "ui_parity",
        "ui_execution",
        "interaction",
        "multi_image",
    )
    mismatched = {
        name: reports[name].get("reference_id")
        for name in semantic_reports
        if reports[name].get("reference_id") != reference_id
    }
    if mismatched:
        raise ValueError(
            f"convergence reports do not match reference_id {reference_id!r}: {mismatched}"
        )
    failures = _failed_cases(reports["output_parity"], domain="output-parity")
    failures.extend(_failed_cases(reports["exact_parity"], domain="exact-parity"))
    for record in reports["ui_parity"].get("records", []):
        if record.get("status") == "failed":
            failures.append(
                {
                    "domain": "ui-parity",
                    "case_id": record.get("state"),
                    "capability_id": None,
                    "status": "failed",
                    "owner_batch": "P3",
                    "root_cause_hypothesis": "current-build capture and UI structure",
                    "viewport": record.get("viewport"),
                    "metrics": record.get("metrics", {}),
                }
            )

    quality = reports["quality_gates"]
    interaction = reports["interaction"]
    interaction_contracts = int(interaction.get("contract_count", 0))
    interaction_passed = int(interaction.get("passed", 0))
    baseline = {
        "version": "1.0",
        "reference_id": reference_id,
        "quality_gates": {
            "gate_count": quality.get("gate_count"),
            "passed": quality.get("passed"),
            "required_failed": quality.get("failed"),
            "optional_failed": quality.get("optional_failed"),
            "status": quality.get("status"),
            "failed_gates": quality.get("failed_gates", []),
            "optional_failed_gates": quality.get("optional_failed_gates", []),
        },
        "domains": {
            "output_parity": {
                key: reports["output_parity"].get(key)
                for key in ("case_count", "passed", "failed", "pending")
            },
            "exact_parity": {
                key: reports["exact_parity"].get(key)
                for key in ("case_count", "passed", "failed", "pending")
            },
            "ui_parity": {
                key: reports["ui_parity"].get(key)
                for key in ("case_count", "passed", "failed", "pending")
            },
            "ui_execution": {
                key: reports["ui_execution"].get(key)
                for key in ("expected", "executed", "passed", "issue_count", "gate")
            },
            "interaction_execution": {
                "contract_count": interaction_contracts,
                "passed": interaction_passed,
                "missing": max(0, interaction_contracts - interaction_passed),
                "issue_count": interaction.get("issue_count"),
            },
            "multi_image": {
                key: reports["multi_image"].get(key)
                for key in ("count", "passed", "failed", "gate")
            },
            "cleanup": {
                "path_count": reports["cleanup"].get("path_count"),
                "reclaimable_bytes": reports["cleanup"].get("reclaimable_bytes"),
            },
        },
        "reports": {name: _artifact(path) for name, path in paths.items()},
        "failure_count": len(failures),
    }
    registry = {
        "version": "1.0",
        "reference_id": reference_id,
        "failure_count": len(failures),
        "failures": failures,
    }
    return baseline, registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-root", type=Path, default=_default_profile())
    for name in DEFAULT_REPORT_NAMES:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failure-output", type=Path, required=True)
    args = parser.parse_args()
    report_paths = {
        name: getattr(args, name)
        for name in DEFAULT_REPORT_NAMES
        if getattr(args, name) is not None
    }
    baseline, failures = build_baseline(
        args.profile_root.resolve(), report_paths=report_paths
    )
    for path, payload in ((args.output, baseline), (args.failure_output, failures)):
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(baseline, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
