import json
from pathlib import Path

from scripts.build_exact_sampling_matrix import build_matrix


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_exact_matrix_deduplicates_defaults_and_preserves_asset(tmp_path: Path) -> None:
    schema = _write(
        tmp_path / "schema.json",
        {
            "common_parameters": {
                "amount": {"type": "float", "default": 0.4, "min": 0.0, "max": 1.0},
                "asset_id": {"type": "asset"},
            },
            "capabilities": {
                "sky_replace": {"parameters": ["amount", "asset_id"]}
            },
        },
    )
    cases = _write(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "capability_id": "sky_replace",
                    "input": {"path": "/machine/source.jpg", "sha256": "a" * 64},
                    "asset_id": "sky.jpg",
                    "parameters": {"amount": 0.4, "asset_id": "sky.jpg"},
                }
            ]
        },
    )

    first = build_matrix(schema, cases, "reference")
    second = build_matrix(schema, cases, "reference")

    assert first["generated_effect_case_count"] == 5
    assert first["effect_case_count"] == 4
    assert first["duplicate_semantic_count"] == 1
    assert first["invalid_count"] == 0
    assert first["matrix_fingerprint"] == second["matrix_fingerprint"]
    assert all(record["asset_id"] == "sky.jpg" for record in first["records"])
    assert len({record["semantic_key"] for record in first["records"]}) == 4


def test_exact_matrix_emits_native_sky_bindings(tmp_path: Path) -> None:
    schema = _write(
        tmp_path / "schema.json",
        {
            "common_parameters": {
                "asset_id": {"type": "asset"},
                "sky_global": {
                    "type": "float",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.5,
                    "anchor_values": [1.0, 0.0, 1.5],
                    "native_anchors": [
                        {"value": 1.0, "native_value": 30},
                        {"value": 0.0, "native_value": 4},
                        {"value": 1.5, "native_value": 100},
                    ],
                },
                "sky_flip": {"type": "boolean", "default": False},
            },
            "capabilities": {
                "sky_replace": {
                    "parameters": ["asset_id", "sky_global", "sky_flip"]
                }
            },
        },
    )
    cases = _write(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "capability_id": "sky_replace",
                    "input": {"path": "/machine/sky.jpg", "sha256": "d" * 64},
                    "asset_id": "Blue Sky 1.jpg",
                }
            ]
        },
    )

    matrix = build_matrix(schema, cases, "reference")
    bindings = {
        (
            record["native_parameter_binding"]["parameter"],
            record["native_parameter_binding"]["value"],
        )
        for record in matrix["records"]
    }

    assert ("asset_id", "Blue Sky 1.jpg") in bindings
    assert {("sky_global", 4), ("sky_global", 100)} <= bindings
    assert ("sky_flip", True) in bindings


def test_exact_semantic_key_ignores_machine_path(tmp_path: Path) -> None:
    schema_payload = {
        "common_parameters": {
            "amount": {"type": "float", "default": 0.4, "min": 0.0, "max": 1.0}
        },
        "capabilities": {"tool": {"parameters": ["amount"]}},
    }
    schema = _write(tmp_path / "schema.json", schema_payload)
    case = {
        "capability_id": "tool",
        "input": {"path": "/one/source.jpg", "sha256": "b" * 64},
        "parameters": {"amount": 0.4},
    }
    first = _write(tmp_path / "one.json", {"cases": [case]})
    second = _write(
        tmp_path / "two.json",
        {"cases": [{**case, "input": {**case["input"], "path": "/two/source.jpg"}}]},
    )

    assert build_matrix(schema, first, "reference")["matrix_fingerprint"] == build_matrix(
        schema, second, "reference"
    )["matrix_fingerprint"]


def test_exact_matrix_honors_capability_parameter_range(tmp_path: Path) -> None:
    schema = _write(
        tmp_path / "schema.json",
        {
            "common_parameters": {
                "amount": {"type": "float", "default": 0.4, "min": -1.0, "max": 1.0}
            },
            "capabilities": {
                "face_ai": {
                    "parameters": ["amount"],
                    "parameter_overrides": {
                        "amount": {
                            "min": 0.0,
                            "signed": False,
                            "native_min": 0,
                            "native_max": 100,
                        }
                    },
                }
            },
        },
    )
    cases = _write(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "capability_id": "face_ai",
                    "input": {"path": "/machine/portrait.jpg", "sha256": "c" * 64},
                    "parameters": {"amount": 0.4},
                }
            ]
        },
    )

    matrix = build_matrix(schema, cases, "reference")
    amounts = {
        record["parameters"]["amount"]
        for record in matrix["records"]
        if record["capability_id"] == "face_ai"
    }

    assert amounts == {0.0, 0.4, 0.5, 1.0}
    assert all(amount >= 0 for amount in amounts)
    bindings = {
        (record["anchor"]["value"], record["native_parameter_binding"]["value"])
        for record in matrix["records"]
        if isinstance(record.get("anchor"), dict)
        and "native_parameter_binding" in record
    }
    assert {(0.0, 0), (1.0, 100)} <= bindings


def test_exact_matrix_rejects_negative_unipolar_override(tmp_path: Path) -> None:
    schema = _write(
        tmp_path / "schema.json",
        {
            "common_parameters": {
                "amount": {"type": "float", "default": 0.4, "min": -1.0, "max": 1.0}
            },
            "capabilities": {
                "tool": {
                    "parameters": ["amount"],
                    "parameter_overrides": {"amount": {"signed": False}},
                }
            },
        },
    )
    cases = _write(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "capability_id": "tool",
                    "input": {"path": "/machine/source.jpg", "sha256": "f" * 64},
                }
            ]
        },
    )

    try:
        build_matrix(schema, cases, "reference")
    except ValueError as exc:
        assert "unipolar parameter has a negative minimum" in str(exc)
    else:
        raise AssertionError("invalid unipolar range must fail closed")


def test_exact_matrix_overrides_only_the_selected_anchor_fixture(tmp_path: Path) -> None:
    schema = _write(
        tmp_path / "schema.json",
        {
            "common_parameters": {
                "amount": {"type": "float", "default": 0.4, "min": -1.0, "max": 1.0}
            },
            "fixture_overrides": [
                {
                    "capability_id": "denoise",
                    "parameter": "amount",
                    "values": [1.0],
                    "input": {"path": "/fixtures/noise.png", "sha256": "d" * 64},
                }
            ],
            "capabilities": {"denoise": {"parameters": ["amount"]}},
        },
    )
    cases = _write(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "capability_id": "denoise",
                    "input": {"path": "/inputs/clean.jpg", "sha256": "e" * 64},
                    "parameters": {"amount": 0.4},
                }
            ]
        },
    )

    matrix = build_matrix(schema, cases, "reference")
    by_amount = {record["parameters"]["amount"]: record for record in matrix["records"]}

    assert by_amount[1.0]["input"]["path"] == "/fixtures/noise.png"
    assert by_amount[1.0]["input"]["sha256"] == "d" * 64
    assert by_amount[-1.0]["input"]["path"] == "/inputs/clean.jpg"
