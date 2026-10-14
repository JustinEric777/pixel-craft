"""Build one deterministic worklist from the current absolute-alignment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"evidence root must be an object: {path}")
    return payload


def _scope_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    dependencies = {
        "missing_exact_amount_anchors": "native-effect-sampling",
        "insufficient_holdout_inputs": "native-holdout-sampling",
        "unrepresented_parameters": "native-parameter-sampling",
        "missing_native_interactions": "native-interaction-observation",
        "missing_browser_interactions": "browser-interaction-execution",
        "missing_ui_execution_states": "browser-ui-capture",
        "missing_ui_reference_states": "native-ui-capture",
        "ui_state_config_mismatch": "ui-contract-reconciliation",
        "unexpected_ui_states": "ui-contract-reconciliation",
        "missing_main_case": "main-effect-reference",
    }
    items: list[dict[str, Any]] = []
    issues = payload.get("issues", {})
    if not isinstance(issues, dict):
        raise TypeError("scope evidence issues must be an object")
    for category, raw_values in sorted(issues.items()):
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        for value in values:
            target = json.dumps(value, ensure_ascii=False, sort_keys=True)
            items.append(
                {
                    "id": f"scope:{category}:{target}",
                    "gate": "absolute-scope-coverage",
                    "category": category,
                    "target": value,
                    "status": "pending",
                    "dependency": dependencies.get(category, "scope-evidence"),
                }
            )
    return items


def _case_items(
    payload: dict[str, Any], *, gate: str, dependency: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise TypeError(f"{gate} cases must be a list")
    for case in cases:
        if not isinstance(case, dict) or case.get("status") == "passed":
            continue
        case_id = str(case.get("case_id") or "")
        if not case_id:
            raise ValueError(f"{gate} contains a failed case without case_id")
        metrics = case.get("metrics") if isinstance(case.get("metrics"), dict) else {}
        items.append(
            {
                "id": f"{gate}:{case_id}",
                "gate": gate,
                "category": "failed-case",
                "target": {
                    "case_id": case_id,
                    "capability_id": case.get("capability_id"),
                    "status": case.get("status"),
                    "mae": metrics.get("mae"),
                    "ssim": metrics.get("ssim"),
                },
                "status": "pending",
                "dependency": dependency,
            }
        )
    return items


def _issue_items(
    payload: dict[str, Any], *, gate: str, dependency: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    issues = payload.get("issues", [])
    if not isinstance(issues, list):
        raise TypeError(f"{gate} issues must be a list")
    for index, issue in enumerate(issues):
        target = issue if isinstance(issue, dict) else {"detail": issue}
        issue_id = str(target.get("id") or f"issue-{index:03d}")
        discriminator = hashlib.sha256(
            json.dumps(target, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        items.append(
            {
                "id": f"{gate}:{issue_id}:{discriminator}",
                "gate": gate,
                "category": issue_id,
                "target": target,
                "status": "pending",
                "dependency": dependency,
            }
        )
    records = payload.get("records", [])
    if records is not None and not isinstance(records, list):
        raise TypeError(f"{gate} records must be a list")
    for index, record in enumerate(records or []):
        if not isinstance(record, dict) or record.get("status") == "passed":
            continue
        state = str(record.get("state") or f"record-{index:03d}")
        viewport = str(record.get("viewport") or "unknown")
        items.append(
            {
                "id": f"{gate}:failed-record:{viewport}:{state}",
                "gate": gate,
                "category": "failed-record",
                "target": record,
                "status": "pending",
                "dependency": dependency,
            }
        )
    return items


def build_worklist(
    *,
    scope_path: Path,
    main_path: Path,
    exact_path: Path,
    ui_execution_path: Path,
    ui_parity_path: Path,
    interaction_path: Path,
) -> dict[str, Any]:
    sources = {
        "scope": scope_path.resolve(),
        "main": main_path.resolve(),
        "exact": exact_path.resolve(),
        "ui_execution": ui_execution_path.resolve(),
        "ui_parity": ui_parity_path.resolve(),
        "interaction": interaction_path.resolve(),
    }
    payloads = {name: _load(path) for name, path in sources.items()}
    items = [
        *_scope_items(payloads["scope"]),
        *_case_items(
            payloads["main"], gate="output-parity", dependency="effect-calibration"
        ),
        *_case_items(
            payloads["exact"],
            gate="exact-incremental-parity",
            dependency="effect-anchor-calibration",
        ),
        *_issue_items(
            payloads["ui_execution"],
            gate="ui-execution-evidence",
            dependency="browser-ui-capture",
        ),
        *_issue_items(
            payloads["ui_parity"], gate="ui-parity", dependency="ui-calibration"
        ),
        *_issue_items(
            payloads["interaction"],
            gate="interaction-execution",
            dependency="interaction-evidence",
        ),
    ]
    items.sort(key=lambda item: str(item["id"]))
    if len({str(item["id"]) for item in items}) != len(items):
        raise RuntimeError("worklist item ids are not unique")
    by_gate: dict[str, int] = {}
    by_dependency: dict[str, int] = {}
    for item in items:
        gate = str(item["gate"])
        dependency = str(item["dependency"])
        by_gate[gate] = by_gate.get(gate, 0) + 1
        by_dependency[dependency] = by_dependency.get(dependency, 0) + 1
    return {
        "version": "1.0",
        "gate": "blocked" if items else "passed",
        "item_count": len(items),
        "summary": {
            "by_gate": dict(sorted(by_gate.items())),
            "by_dependency": dict(sorted(by_dependency.items())),
        },
        "sources": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in sorted(sources.items())
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--exact", type=Path, required=True)
    parser.add_argument("--ui-execution", type=Path, required=True)
    parser.add_argument("--ui-parity", type=Path, required=True)
    parser.add_argument("--interaction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_worklist(
        scope_path=args.scope,
        main_path=args.main,
        exact_path=args.exact,
        ui_execution_path=args.ui_execution,
        ui_parity_path=args.ui_parity,
        interaction_path=args.interaction,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        json.dumps(
            {"gate": report["gate"], "item_count": report["item_count"], "output": str(output)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
