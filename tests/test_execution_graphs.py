import json
from pathlib import Path

from configs import load_config

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_EXECUTION_GRAPHS = load_config(ROOT).execution_graphs


def test_every_registered_capability_has_an_explicit_execution_graph() -> None:
    payload = json.loads((ROOT / "configs/capabilities/registry.json").read_text(encoding="utf-8"))
    registered = {item["id"] for item in payload["capabilities"]}

    assert set(CAPABILITY_EXECUTION_GRAPHS) == registered


def test_sky_graph_has_real_required_and_conditional_models() -> None:
    graph = CAPABILITY_EXECUTION_GRAPHS["sky_replace"]

    assert graph.implementation == "model-backed"
    assert graph.required_models == (
        "improved_sky_segmentator_v462_i8",
        "horizon_align_i8",
    )
    assert graph.conditional_models == (
        "skyinwater_v16_i8",
        "human_clothes_exp13_v2",
        "salient_object_improve_exp19_it150k",
    )


def test_ai_named_capabilities_do_not_claim_a_deterministic_only_pipeline() -> None:
    model_backed = {
        "ai_enhance",
        "structure_ai",
        "sky_enhancer",
        "bokeh_ai",
        "mask_ai",
        "face_ai",
        "skin_ai",
        "crop_ai",
    }

    assert all(
        CAPABILITY_EXECUTION_GRAPHS[capability_id].implementation == "model-backed"
        and CAPABILITY_EXECUTION_GRAPHS[capability_id].required_models
        for capability_id in model_backed
    )


def test_crop_graph_matches_the_active_onnx_panel_suggestion_path() -> None:
    graph = CAPABILITY_EXECUTION_GRAPHS["crop_ai"]

    assert graph.required_models == (
        "saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8",
    )
    assert graph.conditional_models == ()


def test_classifier_uses_imported_openvino_model() -> None:
    graph = CAPABILITY_EXECUTION_GRAPHS["classifier"]

    assert graph.required_models == ("image_classifier_i8",)
