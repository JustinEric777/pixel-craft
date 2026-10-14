import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.build_exact_sampling_matrix import semantic_key
from scripts.build_incremental_sampling_queue import (
    _canonical_evidence_parameters,
    build_active_cohort,
    build_incremental_queue,
)
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue, SamplingQueueRecord
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus


def test_historical_evidence_drops_only_neutral_undeclared_common_parameter() -> None:
    schema = {
        "common_parameters": {
            "amount": {"default": 0.4},
            "opacity": {"default": 1.0},
        },
        "capabilities": {"tool": {"parameters": ["amount"]}},
    }

    canonical, reason = _canonical_evidence_parameters(
        "tool", {"amount": 0.5, "opacity": 1.0}, schema
    )

    assert canonical == {"amount": 0.5}
    assert reason is None


def test_historical_evidence_rejects_removed_or_nonneutral_parameter() -> None:
    schema = {
        "common_parameters": {"opacity": {"default": 1.0}},
        "capabilities": {"bokeh": {"parameters": ["amount", "bokeh_shape"]}},
    }

    removed, removed_reason = _canonical_evidence_parameters(
        "bokeh", {"amount": 1.0, "radius": 8.0}, schema
    )
    nonneutral, nonneutral_reason = _canonical_evidence_parameters(
        "bokeh", {"amount": 1.0, "opacity": 0.5}, schema
    )

    assert removed is None
    assert removed_reason == "undeclared-nonneutral-parameter:radius"
    assert nonneutral is None
    assert nonneutral_reason == "undeclared-nonneutral-parameter:opacity"


def _write_slider_observation(
    capture_root: Path, case_id: str, *, minimum: float, maximum: float
) -> None:
    layout = CaptureLayout(capture_root, case_id)
    layout.prepare()
    layout.event_log_path.write_text(
        json.dumps(
            {
                "status": "default-captured",
                "controls": [
                    {
                        "role": "AXSlider",
                        "identifier": "amount",
                        "enabled": True,
                        "min_value": minimum,
                        "max_value": maximum,
                        "position": [10, 20],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_committed_slider_observation(
    capture_root: Path, case_id: str, *, committed_minimum: float
) -> None:
    layout = CaptureLayout(capture_root, case_id)
    layout.prepare()
    events = [
        {
            "status": "default-captured",
            "controls": [
                {
                    "role": "AXSlider",
                    "identifier": "first-by-position",
                    "enabled": True,
                    "min_value": -100,
                    "max_value": 100,
                    "position": [10, 10],
                },
                {
                    "role": "AXSlider",
                    "identifier": "actual-amount",
                    "enabled": True,
                    "min_value": committed_minimum,
                    "max_value": 100,
                    "position": [10, 20],
                },
            ],
        },
        {"status": "effect-applied", "control": "actual-amount", "value": 50},
    ]
    layout.event_log_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


def test_incremental_queue_excludes_canonical_semantics(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke_payload = {
        "id": "effect:case",
        "scan_order": 1,
        "kind": "effect",
        "case_id": "case",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 0.4},
        "locator_id": "tool",
        "strategy": "primary_slider",
        "page": "edit",
        "section": "tools",
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(SamplingQueueRecord.from_payload(smoke_payload),),
    )
    CaptureJournal(CaptureLayout(tmp_path / "captures", "case")).transition(
        CaptureStatus.READY
    )
    existing = {
        "id": "exact:tool:default",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 0.4},
    }
    existing["semantic_key"] = semantic_key("reference", existing)
    added = {
        "id": "exact:tool:max",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 1.0},
    }
    added["semantic_key"] = semantic_key("reference", added)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "matrix_fingerprint": "matrix", "records": [existing, added]},
        smoke,
        tmp_path / "captures",
    )

    assert diff["existing_count"] == 1
    assert diff["added_count"] == 1
    assert diff["duplicate_count"] == 0
    assert queue["record_count"] == 1
    assert queue["records"][0]["parameters"] == {"amount": 1.0}
    assert queue["records"][0]["parameter_binding"] == {
        "parameter": "amount",
        "value": 1.0,
        "value_space": "normalized-signed",
    }


def test_incremental_queue_blocks_unautomated_parameter_anchor(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:case",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "case",
                    "capability_id": "tool",
                    "input": input_record,
                    "parameters": {"amount": 0.4, "opacity": 1.0},
                    "locator_id": "tool",
                    "strategy": "primary_slider",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    record = {
        "id": "exact:tool:opacity:0",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 0.4, "opacity": 0.0},
        "anchor": {"parameter": "opacity", "value": 0.0},
    }
    record["semantic_key"] = semantic_key("reference", record)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert queue["record_count"] == 0
    assert diff["added_count"] == 0
    assert diff["blocked_count"] == 1
    assert diff["blocked"][0]["reason"] == "native-parameter-not-automated"


def test_incremental_queue_accepts_native_sky_parameter_binding(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    asset_id = "materials__SkyTextures__Blue Sky__Blue Sky 1.jpg"
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:sky",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "sky",
                    "capability_id": "sky_replace",
                    "input": input_record,
                    "parameters": {"sky_global": 1.0, "asset_id": asset_id},
                    "asset_id": asset_id,
                    "locator_id": "sky",
                    "strategy": "asset_picker",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    record = {
        "id": "exact:sky_replace:sky_global:max",
        "capability_id": "sky_replace",
        "input": input_record,
        "parameters": {"sky_global": 1.5},
        "asset_id": asset_id,
        "anchor": {"parameter": "sky_global", "value": 1.5},
        "native_parameter_binding": {
            "parameter": "sky_global",
            "value": 100,
            "value_space": "native",
        },
    }
    record["semantic_key"] = semantic_key("reference", record)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert diff["blocked_count"] == 0
    assert queue["record_count"] == 1
    assert queue["records"][0]["parameter_binding"] == {
        "parameter": "sky_global",
        "value": 100,
        "value_space": "native",
    }


def test_incremental_queue_accepts_explicit_native_amount_binding(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:case",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "case",
                    "capability_id": "tool",
                    "input": input_record,
                    "parameters": {"amount": 0.4},
                    "locator_id": "tool",
                    "strategy": "primary_slider",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    record = {
        "id": "exact:tool:amount:max",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 1.0},
        "anchor": {"parameter": "amount", "value": 1.0},
        "native_parameter_binding": {
            "parameter": "amount",
            "value": 100,
            "value_space": "native",
        },
    }
    record["semantic_key"] = semantic_key("reference", record)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert diff["blocked_count"] == 0
    assert queue["records"][0]["parameter_binding"] == record["native_parameter_binding"]


def test_incremental_queue_excludes_ready_exact_capture(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:case",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "case",
                    "capability_id": "tool",
                    "input": input_record,
                    "parameters": {"amount": 0.4},
                    "locator_id": "tool",
                    "strategy": "primary_slider",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    record = {
        "id": "exact:tool:max",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": 1.0},
    }
    record["semantic_key"] = semantic_key("reference", record)
    capture_id = f"exact-tool-{record['semantic_key'][:12]}"
    CaptureJournal(CaptureLayout(tmp_path / "captures", capture_id)).transition(
        CaptureStatus.READY
    )

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert queue["record_count"] == 0
    assert diff["existing_count"] == 1
    assert diff["added_count"] == 0


def test_incremental_queue_blocks_negative_anchor_for_unipolar_native_slider(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:case",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "case",
                    "capability_id": "tool",
                    "input": input_record,
                    "parameters": {"amount": 0.4},
                    "locator_id": "tool",
                    "strategy": "primary_slider",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    _write_slider_observation(tmp_path / "captures", "case", minimum=0, maximum=100)
    record = {
        "id": "exact:tool:min",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": -1.0},
        "anchor": {"parameter": "amount", "value": -1.0},
    }
    record["semantic_key"] = semantic_key("reference", record)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert queue["record_count"] == 0
    assert diff["blocked"][0] == {
        "id": "exact:tool:min",
        "semantic_key": record["semantic_key"],
        "reason": "native-negative-amount-unrepresentable",
        "native_range": [0.0, 100.0],
    }


def test_incremental_queue_uses_committed_control_range_not_visual_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    smoke = SamplingQueue(
        reference_id="reference",
        records=(
            SamplingQueueRecord.from_payload(
                {
                    "id": "effect:case",
                    "scan_order": 1,
                    "kind": "effect",
                    "case_id": "case",
                    "capability_id": "tool",
                    "input": input_record,
                    "parameters": {"amount": 0.4},
                    "locator_id": "tool",
                    "strategy": "primary_slider",
                    "page": "edit",
                    "section": "tools",
                }
            ),
        ),
    )
    _write_committed_slider_observation(
        tmp_path / "captures", "case", committed_minimum=0
    )
    record = {
        "id": "exact:tool:min",
        "capability_id": "tool",
        "input": input_record,
        "parameters": {"amount": -1.0},
        "anchor": {"parameter": "amount", "value": -1.0},
    }
    record["semantic_key"] = semantic_key("reference", record)

    queue, diff = build_incremental_queue(
        {"reference_id": "reference", "records": [record]},
        smoke,
        tmp_path / "captures",
    )

    assert queue["record_count"] == 0
    assert diff["blocked"][0]["reason"] == "native-negative-amount-unrepresentable"
    assert diff["blocked"][0]["native_range"] == [0.0, 100.0]


def test_active_cohort_preserves_ready_and_replaces_removed_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
    input_record = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }

    def record(case_id: str, amount: float) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": f"effect:{case_id}",
            "scan_order": 1,
            "kind": "effect",
            "page": "edit",
            "section": "tools",
            "strategy": "primary_slider",
            "locator_id": "tool",
            "case_id": case_id,
            "capability_id": "tool",
            "input": input_record,
            "parameters": {"amount": amount},
            "parameter_binding": {
                "parameter": "amount",
                "value": amount,
                "value_space": "normalized-signed",
            },
        }
        payload["semantic_key_exact"] = semantic_key("reference", payload)
        return payload

    ready = record("exact-tool-ready", 1.0)
    removed = record("exact-tool-removed", -1.0)
    added = record("exact-tool-added", 0.5)
    CaptureJournal(
        CaptureLayout(tmp_path / "captures", "exact-tool-ready")
    ).transition(CaptureStatus.READY)
    matrix_records = [
        {
            "semantic_key": payload["semantic_key_exact"],
            "capability_id": "tool",
        }
        for payload in (ready, added)
    ]
    cohort, diff = build_active_cohort(
        {
            "reference_id": "reference",
            "matrix_fingerprint": "matrix-new",
            "records": matrix_records,
        },
        {
            "reference_id": "reference",
            "record_count": 2,
            "records": [ready, {**removed, "scan_order": 2}],
        },
        {
            "reference_id": "reference",
            "record_count": 1,
            "records": [added],
        },
        tmp_path / "captures",
    )

    assert cohort["profile"] == "exact-active-cohort"
    assert cohort["record_count"] == 2
    assert diff["retained_count"] == 1
    assert diff["added_count"] == 1
    assert diff["excluded_count"] == 1
    by_case = {item["case_id"]: item for item in cohort["records"]}
    assert by_case["exact-tool-ready"]["evidence_status"] == "ready"
    assert by_case["exact-tool-added"]["evidence_status"] == "missing"
    assert "exact-tool-removed" not in by_case
    assert all(item["contract_hash"] for item in cohort["records"])
    assert len(cohort["source_queue_fingerprints"]) == 2
