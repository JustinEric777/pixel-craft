"""Verify that two independent exact runs passed with identical fingerprints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compare(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for label, report in (("first", first), ("second", second)):
        if report.get("level") != "exact":
            issues.append({"id": "not-exact", "run": label})
        if report.get("status") != "passed" or int(report.get("failed", 1)) != 0:
            issues.append({"id": "required-gate-failure", "run": label})
        if int(report.get("optional_failed", 0)) != 0:
            issues.append({"id": "optional-gate-failure", "run": label})
        if not report.get("fingerprints"):
            issues.append({"id": "missing-fingerprints", "run": label})
    if first.get("run_id") == second.get("run_id"):
        issues.append({"id": "run-id-reused"})
    if first.get("run_root") == second.get("run_root"):
        issues.append({"id": "run-root-reused"})
    if first.get("reference_id") != second.get("reference_id"):
        issues.append({"id": "reference-id-mismatch"})
    if first.get("fingerprints") != second.get("fingerprints"):
        issues.append({"id": "fingerprint-mismatch"})
    first_gates = [
        (item.get("id"), item.get("required")) for item in first.get("gates", [])
    ]
    second_gates = [
        (item.get("id"), item.get("required")) for item in second.get("gates", [])
    ]
    if first_gates != second_gates:
        issues.append({"id": "gate-contract-mismatch"})
    return {
        "version": "1.0",
        "first_run_id": first.get("run_id"),
        "second_run_id": second.get("run_id"),
        "reference_id": first.get("reference_id"),
        "fingerprints": first.get("fingerprints"),
        "issue_count": len(issues),
        "status": "passed" if not issues else "blocked",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(_load(args.first.resolve()), _load(args.second.resolve()))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("issue_count", "status")},
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
