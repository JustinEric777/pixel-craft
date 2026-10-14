"""Build one new, semantically deduplicated Luminar effect calibration record."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.build_exact_sampling_matrix import semantic_key
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.sampling_queue import (
    SamplingQueue,
    SamplingQueueRecord,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _semantic(reference_id: str, payload: dict[str, Any]) -> str:
    return semantic_key(
        reference_id,
        {
            "capability_id": payload.get("capability_id"),
            "input": payload.get("input"),
            "asset_id": payload.get("asset_id")
            or (payload.get("parameters") or {}).get("asset_id"),
            "asset_sha256": payload.get("asset_sha256"),
            "parameters": payload.get("parameters", {}),
        },
    )


def _canonical_semantics(reference_id: str, metadata_root: Path) -> dict[str, str]:
    semantics: dict[str, str] = {}
    for path in sorted(metadata_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("reference_build") != reference_id.replace("neo-macos-", ""):
            continue
        if not payload.get("input_sha256") or not payload.get("capability_id"):
            continue
        record = {
            "capability_id": payload["capability_id"],
            "input": {"sha256": payload["input_sha256"]},
            "parameters": payload.get("parameters", {}),
            "asset_id": payload.get("asset_id"),
            "asset_sha256": payload.get("asset_sha256"),
        }
        semantics[_semantic(reference_id, record)] = str(payload.get("case_id") or path.stem)
    return semantics


def build(
    *,
    reference_id: str,
    smoke_queue: SamplingQueue,
    metadata_root: Path,
    capability_id: str,
    input_path: Path,
    parameters: dict[str, Any],
    parameter_binding: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    templates = [
        record.payload
        for record in smoke_queue.records
        if record.kind.value == "effect"
        and record.payload.get("capability_id") == capability_id
    ]
    if not templates:
        raise ValueError(f"effect template is missing: {capability_id}")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    with Image.open(input_path) as image:
        width, height = image.size
    template = templates[0]
    source = {
        "path": str(input_path),
        "sha256": _sha256(input_path),
        "width": width,
        "height": height,
    }
    semantic_payload = {
        "capability_id": capability_id,
        "input": source,
        "parameters": parameters,
        "asset_id": template.get("asset_id"),
        "asset_sha256": template.get("asset_sha256"),
    }
    key = _semantic(reference_id, semantic_payload)
    existing = _canonical_semantics(reference_id, metadata_root)
    if key in existing:
        return (
            {
                "version": "2.0",
                "reference_id": reference_id,
                "profile": "effect-calibration",
                "queue_fingerprint": None,
                "record_count": 0,
                "records": [],
            },
            {
                "gate": "skipped-existing-canonical",
                "semantic_key": key,
                "existing_case_id": existing[key],
            },
        )
    capture_id = f"calibration-{capability_id}-{key[:12]}"
    state_path = metadata_root.parent / "state" / f"{capture_id}.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return (
            {
                "version": "2.0",
                "reference_id": reference_id,
                "profile": "effect-calibration",
                "queue_fingerprint": None,
                "record_count": 0,
                "records": [],
            },
            {
                "gate": "skipped-existing-attempt",
                "semantic_key": key,
                "existing_case_id": capture_id,
                "existing_status": str(state.get("status") or "unknown"),
            },
        )
    record = {
        "kind": "effect",
        "page": template["page"],
        "section": template["section"],
        "strategy": template.get("strategy"),
        "locator_id": template["locator_id"],
        "id": f"effect:{capture_id}",
        "case_id": capture_id,
        "capability_id": capability_id,
        "input": source,
        "parameters": parameters,
        "asset_id": template.get("asset_id"),
        "semantic_key_exact": key,
        "scan_order": 1,
    }
    if parameter_binding is not None:
        parameter = parameter_binding.get("parameter")
        value = parameter_binding.get("value")
        value_space = parameter_binding.get("value_space")
        if (
            not isinstance(parameter, str)
            or not parameter
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value_space not in {"native", "normalized-signed"}
            or parameters.get(parameter) != value
        ):
            raise ValueError(
                "parameter_binding must identify the same numeric value in parameters"
            )
        record["parameter_binding"] = parameter_binding
    for name in ("asset_path", "asset_sha256", "asset_index", "asset_count"):
        if template.get(name) is not None:
            record[name] = template[name]
    queue_record = SamplingQueueRecord.from_payload(record)
    queue = SamplingQueue(reference_id, (queue_record,))
    return (
        {
            "version": "2.0",
            "generated_by": "scripts/build_effect_calibration_queue.py",
            "reference_id": reference_id,
            "profile": "effect-calibration",
            "queue_revision": queue.fingerprint[:16],
            "queue_fingerprint": queue.fingerprint,
            "record_count": 1,
            "records": [record],
        },
        {
            "gate": "ready",
            "semantic_key": key,
            "existing_case_id": None,
            "capture_id": capture_id,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--smoke-queue", type=Path)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--parameters",
        default='{"amount": 0.4, "opacity": 1.0}',
        help="JSON object using the product parameter space",
    )
    parser.add_argument(
        "--parameter-binding",
        help='optional JSON object, for example {"parameter":"sky_global","value":30,"value_space":"native"}',
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    try:
        parameters = json.loads(args.parameters)
    except json.JSONDecodeError as exc:
        raise ValueError("--parameters must be valid JSON") from exc
    if not isinstance(parameters, dict):
        raise TypeError("--parameters must be a JSON object")
    parameter_binding = None
    if args.parameter_binding:
        try:
            parameter_binding = json.loads(args.parameter_binding)
        except json.JSONDecodeError as exc:
            raise ValueError("--parameter-binding must be valid JSON") from exc
        if not isinstance(parameter_binding, dict):
            raise TypeError("--parameter-binding must be a JSON object")
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    smoke_path = (
        args.smoke_queue or profile.diagnostics_root / "sampling-queue.json"
    ).resolve()
    smoke_queue = SamplingQueue.load(smoke_path, expected_reference_id=profile.id)
    queue, audit = build(
        reference_id=profile.id,
        smoke_queue=smoke_queue,
        metadata_root=profile.capture_root / "metadata",
        capability_id=args.capability,
        input_path=args.input.resolve(),
        parameters=parameters,
        parameter_binding=parameter_binding,
    )
    write_json_atomic(args.output.resolve(), queue)
    audit_output = (
        args.audit_output or args.output.with_name(f"{args.output.stem}-audit.json")
    )
    write_json_atomic(audit_output.resolve(), audit)
    print(json.dumps({**audit, "record_count": queue["record_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
