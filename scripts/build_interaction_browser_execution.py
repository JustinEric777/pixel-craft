"""Build hash-linked Browser interaction evidence from explicit raw traces."""

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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, value: str) -> Path:
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"interaction artifact escapes evidence root: {value}") from exc
    return resolved


def build_execution(
    contracts: dict[str, Any],
    raw_execution: dict[str, Any],
    *,
    evidence_root: Path,
    native_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    if raw_execution.get("reference_id") != contracts.get("reference_id"):
        raise ValueError("raw interaction reference id does not match contracts")
    matrix_fingerprint = str(contracts.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        raise ValueError("interaction matrix fingerprint must be a SHA-256 digest")
    if raw_execution.get("matrix_fingerprint") != matrix_fingerprint:
        raise ValueError("raw interaction matrix fingerprint does not match contracts")
    environment = raw_execution.get("environment")
    required_environment = {
        "browser",
        "browser_version",
        "logical_viewport",
        "device_scale_factor",
        "physical_viewport",
        "locale",
        "timezone",
        "build_hash",
    }
    if not isinstance(environment, dict) or not required_environment <= set(environment):
        raise ValueError("raw interaction environment is incomplete")
    for field in (
        "logical_viewport",
        "device_scale_factor",
        "physical_viewport",
    ):
        if environment[field] != contracts.get(field):
            raise ValueError(f"raw interaction {field} does not match contracts")

    expected = {
        str(item["id"]): item
        for item in contracts.get("records", [])
        if isinstance(item, dict) and item.get("id")
    }
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for raw in raw_execution.get("records", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            raise ValueError("raw interaction record is invalid")
        contract_id = str(raw["id"])
        if contract_id in seen:
            raise ValueError(f"duplicate raw interaction record: {contract_id}")
        seen.add(contract_id)
        contract = expected.get(contract_id)
        if contract is None:
            raise ValueError(f"unknown raw interaction contract: {contract_id}")
        if raw.get("status") != "passed":
            raise ValueError(f"raw interaction did not pass: {contract_id}")
        if raw.get("events") != contract.get("events"):
            raise ValueError(f"raw interaction events differ from contract: {contract_id}")
        if set(raw.get("visible_assertions", [])) != set(
            contract.get("visible_assertions", [])
        ):
            raise ValueError(f"raw visible assertions are incomplete: {contract_id}")
        if set(raw.get("api_assertions", [])) != set(contract.get("api_assertions", [])):
            raise ValueError(f"raw API assertions are incomplete: {contract_id}")
        waits = raw.get("wait_conditions")
        if not isinstance(waits, list) or not set(waits) <= set(
            contract.get("allowed_wait_conditions", [])
        ):
            raise ValueError(f"raw interaction uses undeclared waits: {contract_id}")
        if raw.get("fixed_sleep") is not False:
            raise ValueError(f"raw interaction must declare fixed_sleep=false: {contract_id}")

        screenshot = _inside(evidence_root, str(raw.get("final_screenshot", "")))
        if not screenshot.is_file():
            raise FileNotFoundError(f"final interaction screenshot is missing: {screenshot}")
        native_observation = (native_root / contract_id / "observation.json").resolve()
        if not native_observation.is_file():
            raise FileNotFoundError(
                f"native interaction observation is missing: {native_observation}"
            )
        record = {
                "id": contract_id,
                "status": "passed",
                "event_count": len(raw["events"]),
                "visible_assertions": raw["visible_assertions"],
                "api_assertions": raw["api_assertions"],
                "wait_conditions": waits,
                "fixed_sleep": False,
                "final_screenshot": screenshot.relative_to(output_root).as_posix(),
                "final_screenshot_sha256": _sha256(screenshot),
                "native_observation": native_observation.as_posix(),
                "native_observation_sha256": _sha256(native_observation),
            }
        for field in (
            "dom_snapshot",
            "accessibility_tree",
            "execution_trace",
            "network_trace",
            "console_log",
        ):
            artifact = _inside(evidence_root, str(raw.get(field, "")))
            if not artifact.is_file():
                raise FileNotFoundError(
                    f"interaction {field} is missing for {contract_id}: {artifact}"
                )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            if payload in ({}, [], None):
                raise ValueError(f"interaction {field} is empty: {contract_id}")
            record[field] = artifact.relative_to(output_root).as_posix()
            record[f"{field}_sha256"] = _sha256(artifact)
        records.append(record)
    return {
        "version": "1.0",
        "reference_id": contracts.get("reference_id"),
        "matrix_fingerprint": matrix_fingerprint,
        "environment": environment,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--contracts",
        type=Path,
        default=ROOT / "configs/parity/core-interaction-matrix.json",
    )
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--native-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    output = (
        args.output
        or profile.diagnostics_root / "interaction-browser-execution.json"
    ).resolve()
    payload = build_execution(
        json.loads(args.contracts.read_text(encoding="utf-8")),
        json.loads(args.raw.read_text(encoding="utf-8")),
        evidence_root=args.evidence_root.resolve(),
        native_root=(
            args.native_root or profile.observations_root / "interactions"
        ).resolve(),
        output_root=output.parent,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(json.dumps({"records": len(payload["records"]), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
