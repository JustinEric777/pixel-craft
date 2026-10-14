"""Fail closed on gaps hidden by the current minimum parity denominators."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.validate_interaction_execution import _validate_native_observation


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _visible_capabilities(ui: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(capability_id)
            for group in ui.get("tool_groups", [])
            for capability_id in group.get("capabilities", [])
        }
    )


def _case_matrix(
    capabilities: list[str],
    schema: dict[str, Any],
    main_cases: dict[str, Any],
    exact_queue: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    cases_by_capability: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in main_cases.get("cases", []):
        cases_by_capability[str(case.get("capability_id"))].append(case)
    for record in exact_queue.get("records", []):
        if record.get("kind") == "effect":
            cases_by_capability[str(record.get("capability_id"))].append(record)

    common = schema.get("common_parameters", {})
    capability_schemas = schema.get("capabilities", {})
    matrix: list[dict[str, Any]] = []
    issues: dict[str, list[str]] = {
        "missing_main_case": [],
        "missing_exact_amount_anchors": [],
        "insufficient_holdout_inputs": [],
        "unrepresented_parameters": [],
    }
    main_ids = {
        str(case.get("capability_id")) for case in main_cases.get("cases", [])
    }
    exact_ids = {
        str(record.get("capability_id"))
        for record in exact_queue.get("records", [])
        if record.get("kind") == "effect"
    }
    for capability_id in capabilities:
        records = cases_by_capability.get(capability_id, [])
        capability_schema = capability_schemas.get(capability_id, {})
        parameters = list(capability_schema.get("parameters", []))
        parameter_overrides = capability_schema.get("parameter_overrides", {})
        input_hashes = sorted(
            {
                str((record.get("input") or {}).get("sha256"))
                for record in records
                if (record.get("input") or {}).get("sha256")
            }
        )
        represented = {
            str(parameter)
            for record in records
            for parameter in (record.get("parameters") or {})
        }
        if any(record.get("asset_id") for record in records):
            represented.add("asset_id")
        amount_values = sorted(
            {
                float(record["parameters"]["amount"])
                for record in records
                if isinstance(record.get("parameters"), dict)
                and isinstance(record["parameters"].get("amount"), (int, float))
            }
        )
        missing_parameters = sorted(set(parameters) - represented)
        if capability_id not in main_ids:
            issues["missing_main_case"].append(capability_id)
        if "amount" in parameters and (
            capability_id not in exact_ids or len(amount_values) < 3
        ):
            issues["missing_exact_amount_anchors"].append(capability_id)
        if len(input_hashes) < 3:
            issues["insufficient_holdout_inputs"].append(capability_id)
        issues["unrepresented_parameters"].extend(
            f"{capability_id}:{parameter}" for parameter in missing_parameters
        )
        matrix.append(
            {
                "capability_id": capability_id,
                "parameters": parameters,
                "parameter_definitions": {
                    parameter: {
                        **common.get(parameter, {}),
                        **parameter_overrides.get(parameter, {}),
                    }
                    for parameter in parameters
                },
                "represented_parameters": sorted(represented),
                "missing_parameters": missing_parameters,
                "amount_anchors": amount_values,
                "distinct_input_count": len(input_hashes),
                "main_case": capability_id in main_ids,
                "exact_case": capability_id in exact_ids,
            }
        )
    return matrix, issues


def _valid_native_ids(
    contracts: dict[str, Any],
    *,
    native_root: Path,
    reference_id: str,
    expected_app: dict[str, str],
) -> set[str]:
    """Return only observations that satisfy the canonical Native contract."""

    matrix_fingerprint = str(contracts.get("matrix_fingerprint") or "")
    valid: set[str] = set()
    for contract in contracts.get("records", []):
        if not isinstance(contract, dict) or not contract.get("id"):
            continue
        contract_id = str(contract["id"])
        _, issues = _validate_native_observation(
            contract_id,
            contract,
            native_root=native_root,
            reference_id=reference_id,
            expected_app=expected_app,
            matrix_fingerprint=matrix_fingerprint,
        )
        if not issues:
            valid.add(contract_id)
    return valid


def run(
    *,
    ui: dict[str, Any],
    schema: dict[str, Any],
    main_cases: dict[str, Any],
    exact_queue: dict[str, Any],
    ui_matrix: dict[str, Any],
    ui_reference: dict[str, Any],
    ui_execution: dict[str, Any],
    interaction_matrix: dict[str, Any],
    native_ids: set[str],
    browser_execution: dict[str, Any],
) -> dict[str, Any]:
    capabilities = _visible_capabilities(ui)
    matrix, capability_issues = _case_matrix(
        capabilities, schema, main_cases, exact_queue
    )

    ui_records = list(ui_matrix.get("records", []))
    expected_states = {str(record.get("id")) for record in ui_records}
    matrix_fingerprint = str(ui_matrix.get("matrix_fingerprint") or "")

    def ui_evidence_ids(
        payload: dict[str, Any], *, require_verified: bool
    ) -> tuple[set[str], set[str], set[str]]:
        canonical: set[str] = set()
        invalid: set[str] = set()
        unexpected: set[str] = set()
        fingerprint_matches = payload.get("matrix_fingerprint") == matrix_fingerprint
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            matrix_state_id = record.get("matrix_state_id")
            if matrix_state_id:
                value = str(matrix_state_id)
                valid = fingerprint_matches and (
                    not require_verified
                    or (
                        record.get("status") == "verified"
                        and not record.get("issues")
                    )
                )
                (canonical if valid else invalid).add(value)
                continue
            historical = record.get("id") or record.get("state")
            if historical:
                unexpected.add(str(historical))
        return canonical, invalid, unexpected

    reference_evidence_ids, invalid_reference_ids, unexpected_reference_ids = ui_evidence_ids(
        ui_reference, require_verified=True
    )
    execution_evidence_ids, invalid_execution_ids, unexpected_execution_ids = ui_evidence_ids(
        ui_execution, require_verified=False
    )
    reference_states = expected_states & reference_evidence_ids
    execution_states = expected_states & execution_evidence_ids

    interaction_records = list(interaction_matrix.get("records", []))
    contract_ids = {str(contract.get("id")) for contract in interaction_records}
    all_browser_ids = {
        str(record.get("id"))
        for record in browser_execution.get("records", [])
        if isinstance(record, dict) and record.get("id")
    }
    browser_ids = {
        str(record.get("id"))
        for record in browser_execution.get("records", [])
        if isinstance(record, dict)
        and record.get("id")
        and record.get("status") == "passed"
        and browser_execution.get("matrix_fingerprint")
        == interaction_matrix.get("matrix_fingerprint")
    }
    resolved_native_ids = contract_ids & native_ids
    resolved_browser_ids = contract_ids & browser_ids
    issues: dict[str, list[str]] = {
        **capability_issues,
        "missing_ui_reference_states": sorted(expected_states - reference_states),
        "missing_ui_execution_states": sorted(expected_states - execution_states),
        "unexpected_ui_reference_evidence": sorted(
            (reference_evidence_ids - expected_states) | unexpected_reference_ids
        ),
        "unexpected_ui_execution_evidence": sorted(
            (execution_evidence_ids - expected_states) | unexpected_execution_ids
        ),
        "invalid_ui_reference_evidence": sorted(invalid_reference_ids),
        "invalid_ui_execution_evidence": sorted(invalid_execution_ids),
        "missing_native_interactions": sorted(contract_ids - resolved_native_ids),
        "missing_browser_interactions": sorted(contract_ids - resolved_browser_ids),
        "unexpected_native_interactions": sorted(
            native_ids - contract_ids
        ),
        "unexpected_browser_interactions": sorted(all_browser_ids - contract_ids),
        "invalid_browser_interactions": sorted(
            (all_browser_ids - browser_ids) & contract_ids
        ),
    }
    passed = all(not values for values in issues.values())
    return {
        "version": "1.0",
        "scope": "selected Luminar Neo local free core",
        "capability_count": len(capabilities),
        "ui_state_count": len(expected_states),
        "interaction_contract_count": len(contract_ids),
        "capabilities": matrix,
        "ui_states": {
            "expected": sorted(expected_states),
            "native_reference": sorted(reference_states),
            "browser_execution": sorted(execution_states),
        },
        "interactions": {
            "expected": sorted(contract_ids),
            "native": sorted(resolved_native_ids),
            "browser": sorted(resolved_browser_ids),
        },
        "issues": issues,
        "issue_count": sum(len(values) for values in issues.values()),
        "gate": "passed" if passed else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    diagnostics = profile.diagnostics_root.resolve()
    native_root = profile.observations_root.resolve() / "interactions"
    interaction_matrix = _load_json(
        ROOT / "configs/parity/core-interaction-matrix.json"
    )
    native_ids = _valid_native_ids(
        interaction_matrix,
        native_root=native_root,
        reference_id=profile.id,
        expected_app={
            "version": profile.version,
            "build": profile.build,
            "bundle_id": profile.bundle_id,
        },
    )
    report = run(
        ui=_load_json(ROOT / "configs/ui/editor.json"),
        schema=_load_json(ROOT / "configs/capabilities/parameter-schema.json"),
        main_cases=_load_json(profile.cases_path.resolve()),
        exact_queue=_load_json(
            diagnostics / "sampling-queue-exact-incremental.json"
        ),
        ui_matrix=_load_json(ROOT / "configs/parity/core-ui-state-matrix.json"),
        ui_reference=_load_json(profile.ui_reference_root / "reference-manifest.json"),
        ui_execution=_load_json(diagnostics / "ui-browser-execution.json"),
        interaction_matrix=interaction_matrix,
        native_ids=native_ids,
        browser_execution=_load_json(
            diagnostics / "interaction-browser-execution.json"
        ),
    )
    output = (args.output or diagnostics / "absolute-scope-coverage.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "issue_count": report["issue_count"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
