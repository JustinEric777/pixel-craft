"""Run attached parity cases and preserve pending cases as evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from configs.reference import load_reference_catalog
from scripts.compare_outputs import compare, compare_grain_statistics
from scripts.import_blackbox_captures import attach_payload


def _attach_candidates(payload: dict[str, Any], candidate_root: Path) -> dict[str, Any]:
    cases = []
    for case in payload.get("cases", []):
        case_root = candidate_root / str(case["case_id"])
        candidate = dict(case.get("candidate", {}))
        for key, filename in (("preview", "preview.png"), ("export", "export.png")):
            path = case_root / filename
            if path.is_file():
                candidate[key] = str(path.resolve())
        cases.append({**case, "candidate": candidate})
    return {**payload, "cases": cases}


def run(
    payload: dict[str, Any], thresholds: dict[str, Any] | None = None
) -> dict[str, Any]:
    threshold_config = thresholds or {}
    default_threshold = threshold_config.get(
        "default", {"ssim_min": 0.98, "mae_max": 0.03, "require_shape_match": True}
    )
    by_capability = threshold_config.get("capabilities", {})
    passed = failed = pending = 0
    results = []
    for case in payload.get("cases", []):
        captures = case.get("captures", {})
        reference = captures.get("luminar_export") or captures.get("luminar_preview")
        candidate = case.get("candidate", {}).get("export") or case.get(
            "candidate", {}
        ).get("preview")
        if not reference or not candidate:
            case = {**case, "status": "pending-reference", "pending_reason": "reference/candidate output missing"}
            pending += 1
        else:
            try:
                metrics = compare(Path(reference), Path(candidate))
                case = {**case, "metrics": metrics, "status": "ready"}
                regions = case.get("regions", {})
                if regions:
                    case["region_metrics"] = {
                        name: compare(
                            Path(reference), Path(candidate), tuple(bounds)
                        )
                        for name, bounds in regions.items()
                    }
                gate = {**default_threshold, **by_capability.get(case.get("capability_id"), {})}
                case["thresholds"] = gate
                shape_passed = metrics["shape_match"] or not gate.get(
                    "require_shape_match", True
                )
                comparator = gate.get("comparator", "pixel-structural")
                amount_value = case.get("parameters", {}).get("amount")
                zero_amount = amount_value is not None and abs(float(amount_value)) <= 1e-12
                if comparator == "grain-statistical" and not zero_amount:
                    grain_metrics = compare_grain_statistics(
                        Path(str(case.get("input", {}).get("path", ""))),
                        Path(reference),
                        Path(candidate),
                    )
                    case["grain_metrics"] = grain_metrics
                    gate_passed = (
                        grain_metrics.get("shape_match") is True
                        and grain_metrics["low_frequency_ssim"]
                        >= float(gate["low_frequency_ssim_min"])
                        and grain_metrics["residual_std_relative_error_max"]
                        <= float(gate["residual_std_relative_error_max"])
                        and grain_metrics["residual_mean_delta_max"]
                        <= float(gate["residual_mean_delta_max"])
                        and grain_metrics["gradient_delta"]
                        <= float(gate["gradient_delta_max"])
                    )
                else:
                    # A zero Grain amount is an identity contract. Comparing
                    # stochastic residual distributions here would classify
                    # ordinary Native export/codec noise as applied grain.
                    gate_passed = (
                        shape_passed
                        and metrics["ssim"] >= float(gate["ssim_min"])
                        and metrics["mae"] <= float(gate["mae_max"])
                    )
                if gate_passed:
                    case["status"] = "passed"
                    passed += 1
                else:
                    case["status"] = "failed"
                    failed += 1
            except (OSError, ValueError) as exc:
                case = {
                    **case,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                failed += 1
        results.append(case)
    return {
        "version": "0.1.0",
        "generated_by": "scripts/run_parity_suite.py",
        "case_count": len(results),
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "capability_count": len(
            {str(item.get("capability_id")) for item in results}
        ),
        "exactness_gate": "blocked" if pending or failed else "passed",
        "cases": results,
    }


def filter_cases(
    payload: dict[str, Any],
    *,
    capabilities: set[str] | None = None,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    return {
        **payload,
        "cases": [
            case
            for case in payload.get("cases", [])
            if (not capabilities or str(case.get("capability_id")) in capabilities)
            and (not case_ids or str(case.get("case_id")) in case_ids)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--capture-root", type=Path)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/parity.yaml")
    parser.add_argument("--capability", action="append", dest="capabilities")
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument(
        "--scope",
        type=Path,
        help="optional capability scope; only records marked in-scope-free are evaluated",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases_path = (args.cases or profile.cases_path).resolve()
    output_path = (
        args.output or profile.diagnostics_root / "parity-report.json"
    ).resolve()
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    payload_reference_id = payload.get("reference_id")
    if profile.exact_gate_enabled and payload_reference_id != profile.id:
        raise RuntimeError(
            f"case reference mismatch: {payload_reference_id!r} != {profile.id!r}"
        )
    payload = attach_payload(
        payload,
        (args.capture_root or profile.capture_root).resolve(),
        expected_reference_id=profile.id,
    )
    payload = _attach_candidates(
        payload,
        (args.candidate_root or profile.diagnostics_root / "candidate-outputs").resolve(),
    )
    payload = filter_cases(
        payload,
        capabilities=set(args.capabilities or []),
        case_ids=set(args.case_ids or []),
    )
    if args.scope:
        scope = json.loads(args.scope.read_text(encoding="utf-8"))
        included = {
            str(item["id"])
            for item in scope.get("capabilities", [])
            if item.get("scope") == "in-scope-free"
        }
        payload = {
            **payload,
            "cases": [
                case
                for case in payload.get("cases", [])
                if str(case.get("capability_id")) in included
            ],
        }
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = run(payload, config.get("thresholds", {}))
    report["reference_id"] = profile.id
    if args.scope:
        report["scope"] = str(args.scope)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "case_count",
                    "passed",
                    "failed",
                    "pending",
                    "exactness_gate",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["exactness_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
