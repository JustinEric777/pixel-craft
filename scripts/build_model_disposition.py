"""Build an auditable retain/retire decision for every registered model artifact."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_disposition(
    source_map: dict[str, Any], backend_parity: dict[str, Any]
) -> dict[str, Any]:
    parity = {
        str(item["fallback_model_id"]): item
        for item in backend_parity.get("results", [])
    }
    rows = []
    for model in source_map.get("models", []):
        model_id = str(model["id"])
        scope = str(model["product_scope_status"])
        runtime_selected = bool(model.get("runtime_selected"))
        contract_status = str(model.get("contract_status", "missing"))
        parity_result = parity.get(model_id)
        if scope == "inventory-unreachable":
            disposition = "retired"
            reason = "unreachable-from-frozen-core-ui-and-execution-graphs"
            evidence = ["product_scope_status", "consumers", "product_capabilities"]
        elif runtime_selected and contract_status == "model-specific":
            disposition = "retained"
            reason = "runtime-selected-required-model-with-model-specific-contract"
            evidence = ["runtime_selected", "contract_status", "product_capabilities"]
        elif parity_result is not None and parity_result.get("status") == "passed":
            disposition = "retained"
            reason = "required-fallback-with-strict-backend-parity"
            evidence = ["backend_parity"]
        elif parity_result is not None and parity_result.get("status") != "passed":
            disposition = "retired"
            reason = "required-fallback-failed-strict-backend-parity"
            evidence = ["backend_parity"]
        else:
            disposition = "blocked"
            reason = "required-model-without-terminal-contract-or-backend-evidence"
            evidence = []
        rows.append(
            {
                "model_id": model_id,
                "logical_id": model.get("logical_id") or model_id,
                "format": model.get("format"),
                "product_scope_status": scope,
                "runtime_selected": runtime_selected,
                "contract_status": contract_status,
                "consumers": model.get("consumers", []),
                "product_capabilities": model.get("product_capabilities", []),
                "backend_parity_status": (
                    parity_result.get("status") if parity_result is not None else "not-applicable"
                ),
                "disposition": disposition,
                "reason": reason,
                "evidence": evidence,
            }
        )
    counts = Counter(str(item["disposition"]) for item in rows)
    active_model_ids = sorted(
        str(item["model_id"]) for item in rows if item["disposition"] == "retained"
    )
    return {
        "version": "1.0",
        "generated_by": "scripts/build_model_disposition.py",
        "source_model_count": len(rows),
        "counts": dict(sorted(counts.items())),
        "active_model_ids": active_model_ids,
        "gate": "passed" if rows and not counts.get("blocked", 0) else "blocked",
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-map", type=Path, required=True)
    parser.add_argument("--backend-parity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-exact", action="store_true")
    args = parser.parse_args()
    report = build_disposition(_load(args.source_map), _load(args.backend_parity))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "source_model_count": report["source_model_count"],
                "counts": report["counts"],
                "gate": report["gate"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not args.require_exact or report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
