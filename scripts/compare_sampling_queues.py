"""Compare sampling queues by semantic operation identity instead of record ids."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_capture.attempt_store import write_json_atomic


def _semantic_key(payload: dict[str, Any]) -> str:
    identity = {
        "kind": payload.get("kind"),
        "capability_id": payload.get("capability_id"),
        "parameters": payload.get("parameters", {}),
        "strategy": payload.get("strategy"),
        "ui_state": payload.get("ui_state"),
        "viewport": payload.get("viewport"),
        "preset_id": payload.get("preset_id"),
        "asset_sha256": payload.get("asset_sha256"),
    }
    source = payload.get("input")
    if isinstance(source, dict):
        identity["input_sha256"] = source.get("sha256")
    inputs = payload.get("inputs")
    if isinstance(inputs, list):
        identity["input_sha256s"] = [item.get("sha256") for item in inputs]
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _logical_key(payload: dict[str, Any]) -> str:
    kind = str(payload.get("kind"))
    identity: Any
    if kind == "effect":
        identity = payload.get("capability_id")
    elif kind == "preset":
        identity = payload.get("preset_id")
    elif kind in {"sky", "overlay"}:
        identity = payload.get("asset_sha256") or payload.get("asset_id")
    elif kind == "ui":
        identity = payload.get("ui_state")
    elif kind == "workflow":
        identity = payload.get("capability_id")
    else:
        identity = payload.get("id")
    return f"{kind}:{identity}"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_keys"] = [_semantic_key(item) for item in payload.get("records", [])]
    return payload


def compare_queues(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    baseline = _load(baseline_path.resolve())
    candidate = _load(candidate_path.resolve())
    baseline_by_key = dict(zip(baseline["_keys"], baseline.get("records", [])))
    candidate_by_key = dict(zip(candidate["_keys"], candidate.get("records", [])))
    common = baseline_by_key.keys() & candidate_by_key.keys()
    removed = baseline_by_key.keys() - candidate_by_key.keys()
    added = candidate_by_key.keys() - baseline_by_key.keys()
    baseline_ids = {str(item.get("id")) for item in baseline.get("records", [])}
    candidate_ids = {str(item.get("id")) for item in candidate.get("records", [])}
    baseline_logical = {_logical_key(item) for item in baseline.get("records", [])}
    candidate_logical = {_logical_key(item) for item in candidate.get("records", [])}

    def summary(payload: dict[str, Any]) -> dict[str, Any]:
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "reference_id": payload["reference_id"],
                    "semantic_keys": payload["_keys"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "reference_id": payload["reference_id"],
            "profile": payload.get("profile", "historical-unspecified"),
            "record_count": len(payload.get("records", [])),
            "fingerprint": fingerprint,
            "kinds": dict(sorted(Counter(item.get("kind") for item in payload.get("records", [])).items())),
        }

    def rows(keys: set[str], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "semantic_key": key,
                "record_id": records[key].get("id"),
                "kind": records[key].get("kind"),
                "capability_id": records[key].get("capability_id"),
            }
            for key in sorted(keys)
        ]

    return {
        "baseline": summary(baseline),
        "candidate": summary(candidate),
        "alignment": {
            "common": len(common),
            "removed": len(removed),
            "added": len(added),
            "removed_records": rows(removed, baseline_by_key),
            "added_records": rows(added, candidate_by_key),
        },
        "record_id_alignment": {
            "common": len(baseline_ids & candidate_ids),
            "removed": len(baseline_ids - candidate_ids),
            "added": len(candidate_ids - baseline_ids),
        },
        "logical_inventory_alignment": {
            "common": len(baseline_logical & candidate_logical),
            "removed": len(baseline_logical - candidate_logical),
            "added": len(candidate_logical - baseline_logical),
            "removed_keys": sorted(baseline_logical - candidate_logical),
            "added_keys": sorted(candidate_logical - baseline_logical),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare_queues(args.baseline, args.candidate)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
