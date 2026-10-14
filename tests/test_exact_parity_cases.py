from pathlib import Path

import pytest

from configs.luminar_sampling import load_luminar_sampling_config
from scripts.build_exact_parity_cases import build_cases

ROOT = Path(__file__).resolve().parents[1]


def _queue() -> dict:
    return {
        "reference_id": "reference",
        "queue_fingerprint_exact": "fingerprint",
        "records": [
            {
                "kind": "effect",
                "id": "effect:one",
                "case_id": "one",
                "capability_id": "details",
                "semantic_key_exact": "semantic-one",
                "input": {"path": "/input.jpg", "sha256": "abc"},
                "parameters": {"amount": 1},
                "anchors": [{"parameter": "amount", "value": 1}],
            }
        ],
    }


def test_builds_exact_case_with_queue_provenance() -> None:
    result = build_cases(_queue())

    assert result["case_count"] == 1
    assert result["source_queue_fingerprint"] == "fingerprint"
    assert result["cases"][0]["exact"] == {
        "semantic_key": "semantic-one",
        "anchors": [{"parameter": "amount", "value": 1}],
        "queue_record_id": "effect:one",
    }


def test_rejects_duplicate_semantic_cases() -> None:
    queue = _queue()
    queue["records"].append({**queue["records"][0], "case_id": "two", "id": "effect:two"})

    with pytest.raises(ValueError, match="duplicate exact semantic key"):
        build_cases(queue)


def test_positioned_effect_includes_the_native_fixture_geometry() -> None:
    queue = _queue()
    queue["records"][0]["capability_id"] = "new_neon_light"
    queue["records"][0]["parameters"]["strokes"] = []

    result = build_cases(
        queue,
        sampling_config=load_luminar_sampling_config(
            ROOT / "configs/luminar_sampling.yaml"
        ),
    )

    assert result["cases"][0]["parameters"]["strokes"] == [
        {"points": [[0.25, 0.32], [0.72, 0.62]]}
    ]
