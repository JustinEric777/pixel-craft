"""Publish an exact incremental sampling queue as parity case definitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import LuminarSamplingConfig, load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic


def _positioned_fixture_parameters(
    capability_id: str,
    sampling_config: LuminarSamplingConfig | None,
) -> dict[str, Any]:
    if sampling_config is None:
        return {}
    recipe = sampling_config.recipe_for(capability_id)
    stroke = recipe.effective.get("stroke")
    if recipe.strategy != "positioned_effect" or stroke is None:
        return {}
    if (
        not isinstance(stroke, list)
        or len(stroke) != 4
        or not all(isinstance(value, (int, float)) for value in stroke)
    ):
        raise ValueError(f"invalid positioned stroke fixture: {capability_id}")
    return {
        "strokes": [
            {
                "points": [
                    [float(stroke[0]), float(stroke[1])],
                    [float(stroke[2]), float(stroke[3])],
                ]
            }
        ]
    }


def build_cases(
    queue: dict[str, Any],
    *,
    sampling_config: LuminarSamplingConfig | None = None,
) -> dict[str, Any]:
    reference_id = queue.get("reference_id")
    if not isinstance(reference_id, str) or not reference_id:
        raise ValueError("exact queue is missing reference_id")
    cases: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    semantic_keys: set[str] = set()
    for record in queue.get("records", []):
        if record.get("kind") != "effect":
            continue
        case_id = record.get("case_id")
        capability_id = record.get("capability_id")
        semantic_key = record.get("semantic_key_exact")
        input_record = record.get("input")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("exact effect record is missing case_id")
        if case_id in case_ids:
            raise ValueError(f"duplicate exact case_id: {case_id}")
        if not isinstance(capability_id, str) or not capability_id:
            raise ValueError(f"exact case is missing capability_id: {case_id}")
        if not isinstance(semantic_key, str) or not semantic_key:
            raise ValueError(f"exact case is missing semantic key: {case_id}")
        if semantic_key in semantic_keys:
            raise ValueError(f"duplicate exact semantic key: {semantic_key}")
        if (
            not isinstance(input_record, dict)
            or not input_record.get("path")
            or not input_record.get("sha256")
        ):
            raise ValueError(f"exact case has invalid input evidence: {case_id}")
        # Positioned effects are executed against the geometry committed in the
        # Native sampling recipe. Schema defaults such as ``strokes: []`` must
        # not overwrite that geometry or the candidate cannot represent the
        # Native capture that this exact case is meant to compare.
        parameters = {
            **dict(record.get("parameters") or {}),
            **_positioned_fixture_parameters(capability_id, sampling_config),
        }
        case: dict[str, Any] = {
            "case_id": case_id,
            "capability_id": capability_id,
            "input": input_record,
            "parameters": parameters,
            "exact": {
                "semantic_key": semantic_key,
                "anchors": list(record.get("anchors") or []),
                "queue_record_id": record.get("id"),
            },
        }
        for key in ("asset_id", "asset_sha256"):
            if record.get(key):
                case[key] = record[key]
        cases.append(case)
        case_ids.add(case_id)
        semantic_keys.add(semantic_key)
    return {
        "version": "1.0",
        "reference_id": reference_id,
        "profile": "exact-incremental",
        "source_queue_fingerprint": queue.get("queue_fingerprint_exact"),
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--queue", type=Path)
    parser.add_argument(
        "--sampling-config",
        type=Path,
        default=ROOT / "configs/luminar_sampling.yaml",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config, project_root=ROOT
    ).resolve(args.reference_id)
    queue = args.queue or profile.diagnostics_root / "sampling-queue-exact-incremental.json"
    output = args.output or profile.diagnostics_root / "parity-cases-exact-incremental.json"
    payload = build_cases(
        json.loads(queue.read_text(encoding="utf-8")),
        sampling_config=load_luminar_sampling_config(args.sampling_config.resolve()),
    )
    write_json_atomic(output.resolve(), payload)
    print(
        json.dumps(
            {"case_count": payload["case_count"], "output": str(output.resolve())},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
