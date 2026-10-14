"""Build exact pending work and an optional immutable active validation cohort."""

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

from scripts.build_exact_sampling_matrix import semantic_key
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue

VALUE_STRATEGIES = {"primary_slider", "subject_aware", "positioned_effect"}


def _native_primary_slider_range(
    capture_root: Path, capture_id: str
) -> tuple[float, float] | None:
    """Read the range of the slider the smoke capture actually committed."""

    event_log = CaptureLayout(capture_root, capture_id).event_log_path
    if not event_log.is_file():
        return None
    observed_controls: dict[str, tuple[float, float]] = {}
    fallback: tuple[float, float] | None = None
    committed_control: str | None = None
    for line in event_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("status") == "effect-applied" and event.get("control"):
            committed_control = str(event["control"])
            continue
        if event.get("status") != "default-captured":
            continue
        sliders = [
            control
            for control in event.get("controls", [])
            if isinstance(control, dict)
            and control.get("role") == "AXSlider"
            and control.get("enabled") is not False
            and isinstance(control.get("min_value"), (int, float))
            and isinstance(control.get("max_value"), (int, float))
        ]
        if not sliders:
            continue
        sliders.sort(
            key=lambda control: (control.get("position") or [10**9, 10**9])[1]
        )
        primary = sliders[0]
        fallback = float(primary["min_value"]), float(primary["max_value"])
        for control in sliders:
            identifier = control.get("identifier")
            if identifier:
                observed_controls[str(identifier)] = (
                    float(control["min_value"]),
                    float(control["max_value"]),
                )
    if committed_control:
        return observed_controls.get(committed_control)
    return fallback


def _parameter_binding(
    matrix_record: dict[str, Any], template: dict[str, Any],
    *,
    native_range: tuple[float, float] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return the one exact parameter operation the native handler can prove."""

    parameters = matrix_record.get("parameters") or {}
    anchors = matrix_record.get("anchors", [matrix_record.get("anchor")])
    has_defaults = "defaults" in anchors
    changed = {
        str(anchor.get("parameter"))
        for anchor in anchors
        if isinstance(anchor, dict)
    }
    if matrix_record.get("capability_id") == "sky_replace":
        asset_id = matrix_record.get("asset_id")
        if has_defaults:
            if not isinstance(asset_id, str) or not asset_id:
                return None, "native-sky-asset-binding-missing"
            return {
                "parameter": "asset_id",
                "value": asset_id,
                "value_space": "asset-id",
            }, None
        if len(changed) != 1:
            return None, "native-sky-single-variable-required"
        binding = matrix_record.get("native_parameter_binding")
        if not isinstance(binding, dict):
            return None, "native-sky-parameter-binding-missing"
        parameter = next(iter(changed))
        if (
            binding.get("parameter") != parameter
            or binding.get("value_space") != "native"
            or not isinstance(binding.get("value"), (bool, int, float))
        ):
            return None, "native-sky-parameter-binding-invalid"
        return dict(binding), None

    explicit_binding = matrix_record.get("native_parameter_binding")
    if isinstance(explicit_binding, dict) and changed:
        parameter = next(iter(changed)) if len(changed) == 1 else None
        if (
            explicit_binding.get("parameter") != parameter
            or explicit_binding.get("value_space") != "native"
            or not isinstance(explicit_binding.get("value"), (bool, int, float))
        ):
            return None, "native-parameter-binding-invalid"
        return dict(explicit_binding), None

    if template.get("strategy") not in VALUE_STRATEGIES:
        return None, "native-parameter-contract-missing"
    amount = parameters.get("amount")
    if not isinstance(amount, (int, float)):
        return None, "native-amount-binding-missing"
    if not has_defaults and changed - {"amount"}:
        return None, "native-parameter-not-automated"
    if float(amount) < 0:
        if native_range is None:
            return None, "native-amount-range-missing"
        if native_range[0] >= 0:
            return None, "native-negative-amount-unrepresentable"
    return {
        "parameter": "amount",
        "value": float(amount),
        "value_space": "normalized-signed",
    }, None


def _canonical_semantic(
    reference_id: str, payload: dict[str, Any]
) -> str:
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


def _canonical_evidence_parameters(
    capability_id: str,
    parameters: dict[str, Any],
    parameter_schema: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    capability = (parameter_schema.get("capabilities") or {}).get(capability_id)
    if not isinstance(capability, dict):
        return None, "capability-not-in-current-schema"
    declared = set(capability.get("parameters") or [])
    common = parameter_schema.get("common_parameters") or {}
    canonical: dict[str, Any] = {}
    for name, value in parameters.items():
        if name in declared:
            canonical[name] = value
            continue
        spec = common.get(name)
        if isinstance(spec, dict) and "default" in spec and value == spec["default"]:
            continue
        return None, f"undeclared-nonneutral-parameter:{name}"
    return canonical, None


def _historical_exact_evidence(
    reference_id: str,
    capture_root: Path,
    parameter_schema: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Index only ready evidence that remains legal under the current contract."""

    accepted: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    metadata_root = capture_root / "metadata"
    for metadata_path in sorted(metadata_root.glob("exact-*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        case_id = str(metadata.get("case_id") or metadata_path.stem)
        state_path = CaptureLayout(capture_root, case_id).state_path
        if not state_path.is_file():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (state.get("canonical") or {}).get("status") != "ready":
            continue
        capability_id = str(metadata.get("capability_id") or "")
        parameters, reason = _canonical_evidence_parameters(
            capability_id,
            dict(metadata.get("parameters") or {}),
            parameter_schema,
        )
        if parameters is None:
            rejected.append({"case_id": case_id, "reason": reason})
            continue
        native_export = metadata.get("native_export") or {}
        export_path = Path(str(native_export.get("path") or ""))
        input_path = Path(str(metadata.get("input_path") or ""))
        if not export_path.is_file() or not input_path.is_file():
            rejected.append({"case_id": case_id, "reason": "evidence-file-missing"})
            continue
        if native_export.get("sha256") != hashlib.sha256(export_path.read_bytes()).hexdigest():
            rejected.append({"case_id": case_id, "reason": "native-export-hash-mismatch"})
            continue
        with Image.open(input_path) as source_image, Image.open(export_path) as output_image:
            if source_image.size != output_image.size:
                rejected.append(
                    {
                        "case_id": case_id,
                        "reason": "native-export-dimensions-mismatch",
                        "source_size": list(source_image.size),
                        "output_size": list(output_image.size),
                    }
                )
                continue
        payload = {
            "capability_id": capability_id,
            "input": {"sha256": metadata.get("input_sha256")},
            "asset_id": metadata.get("asset_id"),
            "asset_sha256": metadata.get("asset_sha256"),
            "parameters": parameters,
        }
        key = _canonical_semantic(reference_id, payload)
        original_payload = {**payload, "parameters": dict(metadata.get("parameters") or {})}
        evidence = {
            "case_id": case_id,
            "semantic_key": key,
            "original_semantic_key": _canonical_semantic(
                reference_id, original_payload
            ),
            "metadata": str(metadata_path.resolve()),
            "parameters": parameters,
            "captured_at": metadata.get("captured_at"),
        }
        previous = accepted.get(key)
        if previous is None or str(evidence.get("captured_at") or "") > str(
            previous.get("captured_at") or ""
        ):
            accepted[key] = evidence
    return accepted, rejected


def _records_fingerprint(reference_id: str, records: list[dict[str, Any]]) -> str:
    payload = {
        "reference_id": reference_id,
        "semantic_keys": [
            record.get("semantic_key_exact")
            or _canonical_semantic(reference_id, record)
            for record in records
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _contract_hash(record: dict[str, Any]) -> str:
    payload = {
        "capability_id": record.get("capability_id"),
        "input_sha256": (record.get("input") or {}).get("sha256"),
        "asset_id": record.get("asset_id"),
        "asset_sha256": record.get("asset_sha256"),
        "parameters": record.get("parameters") or {},
        "parameter_binding": record.get("parameter_binding"),
        "strategy": record.get("strategy"),
        "locator_id": record.get("locator_id"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _with_evidence_status(
    record: dict[str, Any], capture_root: Path
) -> dict[str, Any]:
    state_path = CaptureLayout(capture_root, str(record["case_id"])).state_path
    status = "missing"
    attempt_id = None
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        status = str(state.get("status") or "missing")
        canonical = state.get("canonical") or {}
        if status == "ready" and canonical.get("status") == "ready":
            attempt_id = canonical.get("attempt_id")
    return {
        **record,
        "contract_hash": _contract_hash(record),
        "evidence_status": status,
        "canonical_attempt_id": attempt_id,
    }


def build_active_cohort(
    matrix: dict[str, Any],
    previous_cohort: dict[str, Any],
    pending_queue: dict[str, Any],
    capture_root: Path,
    parameter_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preserve legal prior records and replace only pending/changed semantics."""

    reference_id = str(matrix.get("reference_id") or "")
    if previous_cohort.get("reference_id") != reference_id:
        raise RuntimeError("exact matrix and previous cohort reference ids differ")
    if pending_queue.get("reference_id") != reference_id:
        raise RuntimeError("exact matrix and pending queue reference ids differ")

    legal_keys = {
        str(record["semantic_key"])
        for record in matrix.get("records", [])
        if record.get("semantic_key")
    }
    previous_records = list(previous_cohort.get("records") or [])
    previous_fingerprint = _records_fingerprint(reference_id, previous_records)
    retained: dict[str, dict[str, Any]] = {}
    excluded = []
    for record in previous_records:
        key = str(record.get("semantic_key_exact") or "")
        recertified_from = None
        if key not in legal_keys and parameter_schema is not None:
            parameters, reason = _canonical_evidence_parameters(
                str(record.get("capability_id") or ""),
                dict(record.get("parameters") or {}),
                parameter_schema,
            )
            if parameters is not None:
                candidate = {**record, "parameters": parameters}
                current_key = _canonical_semantic(reference_id, candidate)
                evidence = _with_evidence_status(record, capture_root)
                if current_key in legal_keys and evidence["evidence_status"] == "ready":
                    recertified_from = key
                    key = current_key
                    record = {
                        **record,
                        "parameters": parameters,
                        "semantic_key_exact": current_key,
                        "recertified_from_semantic_key": recertified_from,
                    }
                elif current_key in legal_keys:
                    reason = "historical-evidence-not-ready"
                else:
                    reason = "canonical-contract-not-in-current-matrix"
            if key not in legal_keys:
                excluded.append(
                    {
                        "id": record.get("id"),
                        "case_id": record.get("case_id"),
                        "semantic_key": key or None,
                        "reason": reason or "current-parameter-contract-rejected",
                    }
                )
                continue
        if not key or key not in legal_keys:
            excluded.append(
                {
                    "id": record.get("id"),
                    "case_id": record.get("case_id"),
                    "semantic_key": key or None,
                    "reason": "excluded-illegal-or-removed-contract",
                }
            )
            continue
        normalized_record = dict(record)
        if not normalized_record.get("strategy") or not normalized_record.get(
            "locator_id"
        ):
            state_path = CaptureLayout(
                capture_root, str(normalized_record.get("case_id") or "")
            ).state_path
            if state_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                last_attempt = state.get("last_attempt") or {}
                normalized_record["strategy"] = normalized_record.get(
                    "strategy"
                ) or last_attempt.get("strategy")
                normalized_record["locator_id"] = normalized_record.get(
                    "locator_id"
                ) or last_attempt.get("locator_id")
        retained[key] = {
            **normalized_record,
            "page": record.get("page") or "edit",
            "section": record.get("section") or "tools",
            "source_queue_fingerprint": record.get("source_queue_fingerprint")
            or previous_fingerprint,
        }

    if parameter_schema is not None:
        matrix_by_key = {
            str(record["semantic_key"]): record
            for record in matrix.get("records", [])
            if record.get("semantic_key")
        }
        historical, _historical_rejected = _historical_exact_evidence(
            reference_id, capture_root, parameter_schema
        )
        for key, evidence in historical.items():
            if key not in legal_keys or key in retained:
                continue
            matrix_record = matrix_by_key[key]
            case_id = str(evidence["case_id"])
            state = json.loads(
                CaptureLayout(capture_root, case_id).state_path.read_text(
                    encoding="utf-8"
                )
            )
            retained[key] = {
                "kind": "effect",
                "page": "edit",
                "section": "tools",
                "strategy": (state.get("last_attempt") or {}).get("strategy"),
                "locator_id": (state.get("last_attempt") or {}).get(
                    "locator_id"
                ),
                "id": f"effect:{case_id}",
                "case_id": case_id,
                "capability_id": matrix_record["capability_id"],
                "input": matrix_record["input"],
                "parameters": evidence["parameters"],
                "asset_id": matrix_record.get("asset_id"),
                "asset_sha256": matrix_record.get("asset_sha256"),
                "semantic_key_exact": key,
                "parameter_binding": (state.get("last_attempt") or {}).get(
                    "parameter_binding"
                ),
                "anchors": matrix_record.get(
                    "anchors", [matrix_record.get("anchor")]
                ),
                "recertified_from_semantic_key": evidence[
                    "original_semantic_key"
                ],
                "source_queue_fingerprint": previous_fingerprint,
            }

    pending_records = list(pending_queue.get("records") or [])
    pending_fingerprint = (
        _records_fingerprint(reference_id, pending_records) if pending_records else None
    )
    added = []
    replaced = []
    for record in pending_records:
        key = str(record.get("semantic_key_exact") or "")
        if not key or key not in legal_keys:
            raise ValueError(f"pending exact record is outside the active matrix: {key}")
        if key in retained:
            replaced.append(key)
        else:
            added.append(key)
        retained[key] = {
            **record,
            "source_queue_fingerprint": pending_fingerprint,
        }

    records = [
        _with_evidence_status(record, capture_root) for record in retained.values()
    ]
    for index, record in enumerate(records, 1):
        record["scan_order"] = index
    fingerprint_payload = {
        "reference_id": reference_id,
        "matrix_fingerprint": matrix.get("matrix_fingerprint"),
        "contracts": [
            {
                "semantic_key": record["semantic_key_exact"],
                "contract_hash": record["contract_hash"],
            }
            for record in records
        ],
    }
    cohort_fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    source_fingerprints = sorted(
        {
            str(record["source_queue_fingerprint"])
            for record in records
            if record.get("source_queue_fingerprint")
        }
    )
    cohort = {
        "version": "3.0",
        "reference_id": reference_id,
        "profile": "exact-active-cohort",
        "source_matrix_fingerprint": matrix.get("matrix_fingerprint"),
        "cohort_revision": int(previous_cohort.get("cohort_revision") or 0) + 1,
        "cohort_fingerprint": cohort_fingerprint,
        "queue_fingerprint_exact": cohort_fingerprint,
        "source_queue_fingerprints": source_fingerprints,
        "record_count": len(records),
        "records": records,
    }
    report = {
        "version": "1.0",
        "reference_id": reference_id,
        "cohort_fingerprint": cohort_fingerprint,
        "retained_count": len(records) - len(added),
        "added_count": len(added),
        "replaced_count": len(replaced),
        "excluded_count": len(excluded),
        "added_semantic_keys": added,
        "replaced_semantic_keys": replaced,
        "excluded": excluded,
        "recertified_count": sum(
            bool(record.get("recertified_from_semantic_key"))
            for record in records
        ),
        "source_queue_fingerprints": source_fingerprints,
    }
    return cohort, report


def build_incremental_queue(
    matrix: dict[str, Any],
    smoke_queue: SamplingQueue,
    capture_root: Path,
    parameter_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reference_id = smoke_queue.reference_id
    if matrix.get("reference_id") != reference_id:
        raise RuntimeError("exact matrix and smoke queue reference ids differ")
    templates = {
        str(record.payload.get("capability_id")): record
        for record in smoke_queue.records
        if record.kind.value == "effect"
    }
    canonical = set()
    for record in smoke_queue.records:
        if record.kind.value != "effect":
            continue
        state = CaptureLayout(capture_root, record.capture_id).state_path
        if not state.is_file():
            continue
        payload = json.loads(state.read_text(encoding="utf-8"))
        if (payload.get("canonical") or {}).get("status") == "ready":
            canonical.add(_canonical_semantic(reference_id, record.payload))
    historical, historical_rejected = (
        _historical_exact_evidence(
            reference_id, capture_root, parameter_schema
        )
        if parameter_schema is not None
        else ({}, [])
    )

    seen: set[str] = set()
    existing = []
    added = []
    duplicate = []
    invalid = []
    blocked = []
    records = []
    for matrix_record in matrix.get("records", []):
        key = semantic_key(reference_id, matrix_record)
        if key != matrix_record.get("semantic_key"):
            invalid.append({"id": matrix_record.get("id"), "reason": "semantic-key-mismatch"})
            continue
        if key in seen:
            duplicate.append({"id": matrix_record.get("id"), "semantic_key": key})
            continue
        seen.add(key)
        capture_id = f"exact-{matrix_record['capability_id']}-{key[:12]}"
        exact_state = CaptureLayout(capture_root, capture_id).state_path
        exact_ready = False
        if exact_state.is_file():
            state_payload = json.loads(exact_state.read_text(encoding="utf-8"))
            exact_ready = (state_payload.get("canonical") or {}).get("status") == "ready"
        historical_record = historical.get(key)
        if key in canonical or exact_ready or historical_record is not None:
            existing.append(
                {
                    "id": matrix_record["id"],
                    "semantic_key": key,
                    "source": (
                        "historical-exact-recertified"
                        if historical_record is not None
                        else "current-canonical"
                    ),
                    **(
                        {"source_case_id": historical_record["case_id"]}
                        if historical_record is not None
                        else {}
                    ),
                }
            )
            continue
        template_record = templates.get(str(matrix_record.get("capability_id")))
        if template_record is None:
            invalid.append({"id": matrix_record.get("id"), "reason": "effect-template-missing"})
            continue
        template = template_record.payload
        native_range = _native_primary_slider_range(
            capture_root, template_record.capture_id
        )
        binding, blocked_reason = _parameter_binding(
            matrix_record, template, native_range=native_range
        )
        if binding is None:
            blocked.append(
                {
                    "id": matrix_record.get("id"),
                    "semantic_key": key,
                    "reason": blocked_reason,
                    "native_range": list(native_range) if native_range else None,
                }
            )
            continue
        asset_id = matrix_record.get("asset_id")
        if asset_id and template.get("asset_id") != asset_id:
            invalid.append({"id": matrix_record.get("id"), "reason": "asset-template-mismatch"})
            continue
        parameters = dict(matrix_record.get("parameters") or {})
        if asset_id:
            parameters["asset_id"] = asset_id
        record = {
            **{
                name: template.get(name)
                for name in ("kind", "page", "section", "strategy", "locator_id")
            },
            "id": f"effect:{capture_id}",
            "case_id": capture_id,
            "capability_id": matrix_record["capability_id"],
            "input": matrix_record["input"],
            "parameters": parameters,
            "asset_id": asset_id,
            "semantic_key_exact": key,
            "parameter_binding": binding,
            "anchors": matrix_record.get("anchors", [matrix_record.get("anchor")]),
        }
        for name in ("asset_path", "asset_sha256"):
            if template.get(name):
                record[name] = template[name]
        records.append(record)
        added.append({"id": matrix_record["id"], "semantic_key": key, "capture_id": capture_id})

    if duplicate or invalid:
        raise ValueError(
            f"incremental exact queue is invalid: duplicate={len(duplicate)}, invalid={len(invalid)}"
        )
    for index, record in enumerate(records, 1):
        record["scan_order"] = index
    fingerprint_payload = {
        "reference_id": reference_id,
        "records": [
            {
                "semantic_key": item["semantic_key_exact"],
                "parameter_binding": item["parameter_binding"],
            }
            for item in records
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    queue = {
        "version": "2.0",
        "reference_id": reference_id,
        "profile": "exact-incremental",
        "source_matrix_fingerprint": matrix.get("matrix_fingerprint"),
        "queue_revision": 1,
        "queue_fingerprint_exact": fingerprint,
        "record_count": len(records),
        "records": records,
    }
    diff = {
        "version": "1.0",
        "reference_id": reference_id,
        "matrix_fingerprint": matrix.get("matrix_fingerprint"),
        "canonical_semantic_count": len(canonical),
        "existing_count": len(existing),
        "added_count": len(added),
        "duplicate_count": len(duplicate),
        "invalid_count": len(invalid),
        "blocked_count": len(blocked),
        "existing": existing,
        "added": added,
        "duplicate": duplicate,
        "invalid": invalid,
        "blocked": blocked,
        "historical_recertified_count": sum(
            item.get("source") == "historical-exact-recertified"
            for item in existing
        ),
        "historical_rejected_count": len(historical_rejected),
        "historical_rejected": historical_rejected,
    }
    return queue, diff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--smoke-queue", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=ROOT / "configs/capabilities/parameter-schema.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diff-output", type=Path, required=True)
    parser.add_argument("--previous-cohort", type=Path)
    parser.add_argument("--cohort-output", type=Path)
    parser.add_argument("--cohort-diff-output", type=Path)
    args = parser.parse_args()
    cohort_args = (
        args.previous_cohort,
        args.cohort_output,
        args.cohort_diff_output,
    )
    if any(cohort_args) and not all(cohort_args):
        parser.error(
            "--previous-cohort, --cohort-output and --cohort-diff-output "
            "must be provided together"
        )
    raw_queue = json.loads(args.smoke_queue.read_text(encoding="utf-8"))
    smoke_queue = SamplingQueue.load(
        args.smoke_queue.resolve(), expected_reference_id=str(raw_queue["reference_id"])
    )
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    parameter_schema = json.loads(args.schema.read_text(encoding="utf-8"))
    queue, diff = build_incremental_queue(
        matrix,
        smoke_queue,
        args.capture_root.resolve(),
        parameter_schema=parameter_schema,
    )
    write_json_atomic(args.output.resolve(), queue)
    write_json_atomic(args.diff_output.resolve(), diff)
    cohort = None
    cohort_diff = None
    if args.previous_cohort:
        previous_cohort = json.loads(
            args.previous_cohort.read_text(encoding="utf-8")
        )
        cohort, cohort_diff = build_active_cohort(
            matrix,
            previous_cohort,
            queue,
            args.capture_root.resolve(),
            parameter_schema=parameter_schema,
        )
        write_json_atomic(args.cohort_output.resolve(), cohort)
        write_json_atomic(args.cohort_diff_output.resolve(), cohort_diff)
    print(
        json.dumps(
            {
                "reference_id": queue["reference_id"],
                "record_count": queue["record_count"],
                "existing_count": diff["existing_count"],
                "historical_recertified_count": diff[
                    "historical_recertified_count"
                ],
                "historical_rejected_count": diff["historical_rejected_count"],
                "duplicate_count": diff["duplicate_count"],
                "invalid_count": diff["invalid_count"],
                "cohort_count": cohort["record_count"] if cohort else None,
                "cohort_excluded_count": (
                    cohort_diff["excluded_count"] if cohort_diff else None
                ),
                "cohort_recertified_count": (
                    cohort_diff["recertified_count"] if cohort_diff else None
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
