import hashlib
import json
from pathlib import Path

import numpy as np
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from api.app import create_app
from scripts.build_parity_cases import build_cases
from scripts.generate_candidate_outputs import (
    _canonical_case_parameters,
    _merge_existing_candidates,
    _trace_versions_current,
)
from scripts.generate_candidate_outputs import generate as generate_candidates
from scripts.import_blackbox_captures import attach_payload
from scripts.run_parity_suite import run as run_parity
from scripts.validate_free_capability_coverage import run as validate_coverage
from scripts.validate_reference_captures import run as validate_captures
from scripts.validate_runtime_policy import run as validate_runtime
from scripts.validate_ui_references import run as validate_ui


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_candidate_reuse_rejects_stale_model_contract_versions(tmp_path: Path) -> None:
    trace = _write_json(
        tmp_path / "execution.json",
        {
            "status": "ready",
            "models": [
                {
                    "id": "model",
                    "invoked": True,
                    "preprocess_version": "old-input",
                    "postprocess_version": "output-v1",
                }
            ],
        },
    )

    assert not _trace_versions_current(
        trace, {"model": ("input-v2", "output-v1")}
    )
    assert _trace_versions_current(
        trace, {"model": ("old-input", "output-v1")}
    )


def test_candidate_parameters_drop_only_undeclared_neutral_defaults() -> None:
    schema = {
        "common_parameters": {
            "amount": {"default": 0.4},
            "opacity": {"default": 1.0},
        },
        "capabilities": {"tool": {"parameters": ["amount"]}},
    }

    assert _canonical_case_parameters(
        "tool", {"amount": 0.4, "opacity": 1.0}, schema
    ) == {"amount": 0.4}
    assert _canonical_case_parameters(
        "tool", {"amount": 0.4, "opacity": 0.5}, schema
    ) == {"amount": 0.4, "opacity": 0.5}


def test_coverage_reports_visible_tool_without_case(tmp_path: Path) -> None:
    ui = _write_json(
        tmp_path / "ui.json",
        {"tool_groups": [{"capabilities": ["tool"]}]},
    )
    registry = _write_json(
        tmp_path / "registry.json", {"capabilities": [{"id": "tool"}]}
    )
    schema = _write_json(
        tmp_path / "schema.json", {"capabilities": {"tool": {}}}
    )
    graphs = _write_json(
        tmp_path / "graphs.json",
        {"graphs": [{"capability_id": "tool", "implementation": "deterministic"}]},
    )
    policy = _write_json(
        tmp_path / "policy.json",
        {"image_effect_pipelines": [], "local_effect_pipelines": ["tool"]},
    )
    cases = _write_json(tmp_path / "cases.json", {"cases": []})

    report = validate_coverage(ui, registry, schema, graphs, policy, cases)

    assert report["gate"] == "blocked"
    assert report["issues"]["missing_cases"] == ["tool"]


def test_parity_case_builder_uses_visible_schema_and_typed_assets() -> None:
    matrix = {
        "samples": [
            {
                "id": "sample",
                "role": "general",
                "path": "sample.jpg",
                "intended_uses": ["erase", "hidden"],
            }
        ],
        "capabilities": [
            {"id": "erase", "parameters": ["amount"]},
            {"id": "hidden", "parameters": ["amount"]},
        ],
    }
    schema = {
        "common_parameters": {
            "amount": {"type": "float", "default": 0.4, "min": 0.0, "max": 1.0},
            "strokes": {"type": "array", "default": []},
            "asset_id": {"type": "string"},
        },
        "capabilities": {
            "erase": {"parameters": ["amount", "strokes"]},
            "lut_mapping": {"parameters": ["amount", "asset_id"]},
        },
    }
    ui = {"tool_groups": [{"id": "common", "capabilities": ["erase", "lut_mapping"]}]}
    parity = {
        "scope": {"fallback_sample_roles_by_tool_group": {"common": "general"}},
        "capture": {
            "case_defaults": {"erase": {"strokes": [{"points": [[0.5, 0.5]]}]}},
            "asset_family_by_capability": {"lut_mapping": "lut"},
        },
    }
    assets = {"records": [{"id": "lut.cube", "family": "lut"}]}

    cases = build_cases(matrix, schema, ui=ui, parity=parity, asset_manifest=assets)

    assert {case["capability_id"] for case in cases} == {"erase", "lut_mapping"}
    assert len(cases) == 2
    erase = next(case for case in cases if case["capability_id"] == "erase")
    lut = next(case for case in cases if case["capability_id"] == "lut_mapping")
    assert erase["parameters"]["strokes"]
    assert lut["asset_id"] == "lut.cube"


def test_parity_case_builder_prefers_explicit_fixture_over_group_fallback() -> None:
    matrix = {
        "samples": [
            {
                "id": "explicit-denoise",
                "role": "denoise",
                "path": "noise.png",
                "intended_uses": ["denoise"],
            },
            {
                "id": "fallback-sharpness",
                "role": "sharpness",
                "path": "sharp.jpg",
                "intended_uses": ["deblur"],
            },
        ],
        "capabilities": [],
    }
    schema = {
        "common_parameters": {"amount": {"default": 0.4}},
        "capabilities": {
            "denoise": {"parameters": ["amount"]},
            "deblur": {"parameters": ["amount"]},
        },
    }
    ui = {
        "tool_groups": [
            {"id": "extensions", "capabilities": ["denoise", "deblur"]}
        ]
    }
    parity = {
        "scope": {
            "fallback_sample_roles_by_tool_group": {"extensions": "sharpness"}
        }
    }

    cases = build_cases(matrix, schema, ui=ui, parity=parity)

    assert [(case["sample_id"], case["capability_id"]) for case in cases] == [
        ("explicit-denoise", "denoise"),
        ("fallback-sharpness", "deblur"),
    ]


def test_runtime_policy_rejects_coreml(tmp_path: Path) -> None:
    model_config = tmp_path / "model.yaml"
    model_config.write_text(
        yaml.safe_dump(
            {
                "selection": {"primary": "onnxruntime", "fallback": "openvino"},
                "models": [
                    {
                        "id": "bad",
                        "format": "onnx",
                        "backend": "onnxruntime",
                        "notes": "CoreML replacement",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    module = tmp_path / "ai"
    module.mkdir()

    report = validate_runtime(model_config, module)

    assert report["gate"] == "blocked"
    assert report["coreml_references"] == 1


def test_grain_parity_compares_distribution_not_random_phase(tmp_path: Path) -> None:
    yy, xx = np.indices((128, 128), dtype=np.float32)
    source = np.repeat(((xx + yy) % 192 + 32)[..., None], 3, axis=2)
    reference_noise = np.random.default_rng(1).normal(0.0, 16.0, (128, 128, 1))
    candidate_noise = np.random.default_rng(2).normal(0.0, 16.0, (128, 128, 1))
    source_path = tmp_path / "source.png"
    reference_path = tmp_path / "reference.png"
    candidate_path = tmp_path / "candidate.png"
    Image.fromarray(source.astype(np.uint8), "RGB").save(source_path)
    Image.fromarray(np.clip(source + reference_noise, 0, 255).astype(np.uint8), "RGB").save(
        reference_path
    )
    Image.fromarray(np.clip(source + candidate_noise, 0, 255).astype(np.uint8), "RGB").save(
        candidate_path
    )
    payload = {
        "cases": [
            {
                "case_id": "grain",
                "capability_id": "grain",
                "input": {"path": str(source_path)},
                "captures": {"luminar_export": str(reference_path)},
                "candidate": {"export": str(candidate_path)},
            }
        ]
    }
    thresholds = {
        "default": {"ssim_min": 0.999, "mae_max": 0.001},
        "capabilities": {
            "grain": {
                "comparator": "grain-statistical",
                "low_frequency_ssim_min": 0.99,
                "residual_std_relative_error_max": 0.08,
                "residual_mean_delta_max": 0.01,
                "gradient_delta_max": 0.01,
            }
        },
    }

    report = run_parity(payload, thresholds)

    assert report["exactness_gate"] == "passed"
    assert report["cases"][0]["grain_metrics"]["low_frequency_ssim"] > 0.99


def test_zero_grain_uses_identity_comparator_not_residual_statistics(
    tmp_path: Path,
) -> None:
    source = np.full((32, 32, 3), 128, dtype=np.uint8)
    reference = source.copy()
    reference[::8, ::8] += 1
    source_path = tmp_path / "source.png"
    reference_path = tmp_path / "reference.png"
    candidate_path = tmp_path / "candidate.png"
    Image.fromarray(source, "RGB").save(source_path)
    Image.fromarray(reference, "RGB").save(reference_path)
    Image.fromarray(source, "RGB").save(candidate_path)
    payload = {
        "cases": [
            {
                "case_id": "grain-zero",
                "capability_id": "grain",
                "parameters": {"amount": 0.0},
                "input": {"path": str(source_path)},
                "captures": {"luminar_export": str(reference_path)},
                "candidate": {"export": str(candidate_path)},
            }
        ]
    }
    thresholds = {
        "default": {"ssim_min": 0.98, "mae_max": 0.03},
        "capabilities": {
            "grain": {
                "comparator": "grain-statistical",
                "low_frequency_ssim_min": 1.0,
                "residual_std_relative_error_max": 0.0,
                "residual_mean_delta_max": 0.0,
                "gradient_delta_max": 0.0,
            }
        },
    }

    report = run_parity(payload, thresholds)

    assert report["exactness_gate"] == "passed"
    assert "grain_metrics" not in report["cases"][0]


def test_reference_capture_requires_metadata_when_outputs_exist(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    case_id = "case"
    cases = _write_json(
        tmp_path / "cases.json",
        {
            "cases": [
                {
                    "case_id": case_id,
                    "capability_id": "tool",
                    "parameters": {"amount": 0.4},
                    "input": {
                        "path": str(source),
                        "sha256": hashlib.sha256(b"source").hexdigest(),
                    },
                }
            ]
        },
    )
    output = tmp_path / "captures" / "luminar_outputs" / case_id
    output.mkdir(parents=True)
    (output / "preview.png").write_bytes(b"preview")
    (output / "export.png").write_bytes(b"export")

    report = validate_captures(cases, tmp_path / "captures", "build")

    assert report["invalid"] == 1
    assert "metadata-missing" in report["records"][0]["errors"]


def test_capture_attachment_rejects_output_without_reference_metadata(
    tmp_path: Path,
) -> None:
    case_id = "case"
    output = tmp_path / "captures" / "luminar_outputs" / case_id
    output.mkdir(parents=True)
    (output / "preview.png").write_bytes(b"preview")

    report = attach_payload(
        {"cases": [{"case_id": case_id}]},
        tmp_path / "captures",
        expected_reference_id="luminar-neo-macos-1.25.1-21065",
    )

    assert report["cases"][0]["status"] == "invalid-reference"
    assert "metadata is missing" in report["cases"][0]["pending_reason"]


def test_capture_attachment_rejects_different_reference_build(tmp_path: Path) -> None:
    case_id = "case"
    capture_root = tmp_path / "captures"
    output = capture_root / "luminar_outputs" / case_id
    metadata = capture_root / "metadata"
    output.mkdir(parents=True)
    metadata.mkdir(parents=True)
    (output / "preview.png").write_bytes(b"preview")
    _write_json(
        metadata / f"{case_id}.json",
        {"reference_build": "luminar-neo-macos-1.26.0-21267"},
    )

    report = attach_payload(
        {"cases": [{"case_id": case_id}]},
        capture_root,
        expected_reference_id="luminar-neo-macos-1.25.1-21065",
    )

    assert report["cases"][0]["status"] == "invalid-reference"
    assert "capture reference mismatch" in report["cases"][0]["pending_reason"]


def test_candidate_generator_uses_real_preview_and_export(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "workspace"))
    source = tmp_path / "source.png"
    Image.new("RGB", (24, 16), (30, 60, 90)).save(source)
    payload = {
        "cases": [
            {
                "case_id": "candidate",
                "capability_id": "color_adjustments",
                "input": {"path": str(source)},
                "parameters": {"amount": 0.4},
            }
        ]
    }

    with TestClient(create_app()) as client:
        report = generate_candidates(payload, client, tmp_path / "candidate")

    case = report["cases"][0]
    assert report["candidate_summary"] == {
        "generated": 1,
        "failed": 0,
        "skipped": 0,
        "reused": 0,
    }
    assert Path(case["candidate"]["preview"]).is_file()
    assert Path(case["candidate"]["export"]).is_file()
    trace = json.loads(Path(case["candidate"]["execution"]).read_text(encoding="utf-8"))
    assert trace["status"] == "ready"


def test_candidate_partial_run_preserves_existing_evidence() -> None:
    base = {"cases": [{"case_id": "one"}, {"case_id": "two"}]}
    existing = {
        "cases": [
            {
                "case_id": "one",
                "candidate": {"execution": "/tmp/one.json"},
                "status": "pending-reference",
            }
        ]
    }

    merged = _merge_existing_candidates(base, existing)

    assert merged["cases"][0]["candidate"] == {"execution": "/tmp/one.json"}
    assert merged["cases"][0]["status"] == "pending-reference"
    assert merged["cases"][1] == {"case_id": "two"}


def test_ui_reference_gate_accepts_identical_fixed_viewport(tmp_path: Path) -> None:
    config = tmp_path / "parity.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "capture": {"ui_viewports": [[10, 8]], "ui_states": ["edit"]},
                "thresholds": {
                    "ui": {"mae_max": 0.0, "changed_pixel_ratio_max": 0.0}
                },
            }
        ),
        encoding="utf-8",
    )
    reference = tmp_path / "reference" / "10x8"
    candidate = tmp_path / "candidate" / "10x8"
    reference.mkdir(parents=True)
    candidate.mkdir(parents=True)
    image = Image.new("RGB", (10, 8), (30, 40, 50))
    image.save(reference / "edit.png")
    image.save(candidate / "edit.png")

    report = validate_ui(
        config,
        tmp_path / "reference",
        tmp_path / "candidate",
        ui_matrix={
            "reference_id": None,
            "matrix_fingerprint": "c" * 64,
            "records": [{"id": "edit"}],
        },
    )

    assert report["gate"] == "passed"
    assert report["passed"] == 1


def test_parity_suite_uses_configured_thresholds(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (12, 8), (20, 40, 60)).save(reference)
    Image.new("RGB", (12, 8), (20, 40, 60)).save(candidate)
    payload = {
        "cases": [
            {
                "case_id": "case",
                "capability_id": "tool",
                "captures": {"luminar_export": str(reference)},
                "candidate": {"export": str(candidate)},
            }
        ]
    }

    report = run_parity(
        payload,
        {
            "default": {
                "ssim_min": 1.0,
                "mae_max": 0.0,
                "require_shape_match": True,
            }
        },
    )

    assert report["exactness_gate"] == "passed"
    assert report["passed"] == 1
