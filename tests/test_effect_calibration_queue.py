import json
from pathlib import Path

from PIL import Image

from scripts.build_effect_calibration_queue import build
from scripts.luminar_capture.sampling_queue import SamplingQueue, SamplingQueueRecord


def _smoke_queue(source: Path) -> SamplingQueue:
    record = SamplingQueueRecord.from_payload(
        {
            "id": "effect:existing",
            "case_id": "existing",
            "kind": "effect",
            "capability_id": "magic_lights",
            "input": {"path": str(source), "sha256": "old"},
            "parameters": {"amount": 0.4, "opacity": 1.0},
            "locator_id": "EditExpandButton_MagicLightsEffect",
            "strategy": "primary_slider",
            "page": "edit",
            "section": "tools",
            "scan_order": 1,
        }
    )
    return SamplingQueue("luminar-neo-macos-1.28.0-23071", (record,))


def test_builds_new_semantic_calibration_record(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 8), (10, 20, 30)).save(source)

    queue, audit = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=tmp_path / "metadata",
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
    )

    assert audit["gate"] == "ready"
    assert queue["record_count"] == 1
    assert queue["records"][0]["input"]["width"] == 12
    assert queue["records"][0]["semantic_key_exact"] == audit["semantic_key"]


def test_binds_a_calibration_parameter_to_the_record(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 8), (10, 20, 30)).save(source)
    binding = {
        "parameter": "amount",
        "value": 0.4,
        "value_space": "normalized-signed",
    }

    queue, _audit = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=tmp_path / "metadata",
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
        parameter_binding=binding,
    )

    assert queue["records"][0]["parameter_binding"] == binding


def test_skips_matching_current_version_canonical(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 8), (10, 20, 30)).save(source)
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    queue, audit = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=metadata,
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
    )
    record = queue["records"][0]
    (metadata / "existing.json").write_text(
        json.dumps(
            {
                "case_id": "existing-current",
                "reference_build": "luminar-1.28.0-23071",
                "capability_id": "magic_lights",
                "input_sha256": record["input"]["sha256"],
                "parameters": record["parameters"],
                "asset_id": None,
                "asset_sha256": None,
            }
        ),
        encoding="utf-8",
    )

    queue, audit = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=metadata,
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
    )

    assert queue["record_count"] == 0
    assert audit == {
        "gate": "skipped-existing-canonical",
        "semantic_key": record["semantic_key_exact"],
        "existing_case_id": "existing-current",
    }


def test_skips_an_existing_failed_attempt_without_resampling(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (12, 8), (10, 20, 30)).save(source)
    metadata = tmp_path / "captures/metadata"
    metadata.mkdir(parents=True)
    queue, _ = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=metadata,
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
    )
    record = queue["records"][0]
    state = metadata.parent / "state" / f"{record['case_id']}.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"status": "failed"}), encoding="utf-8")

    queue, audit = build(
        reference_id="luminar-neo-macos-1.28.0-23071",
        smoke_queue=_smoke_queue(source),
        metadata_root=metadata,
        capability_id="magic_lights",
        input_path=source,
        parameters={"amount": 0.4, "opacity": 1.0},
    )

    assert queue["record_count"] == 0
    assert audit["gate"] == "skipped-existing-attempt"
    assert audit["existing_status"] == "failed"
