from pathlib import Path

import numpy as np
import pytest

from ai.model.backend import TensorSpec
from ai.model.onnx.deblur_restore.srn_deblur_512 import SrnDeblur512Inference
from ai.model.onnx.face_analysis.eyes_detector_i8 import EyesDetectorI8OnnxInference
from ai.model.onnx.face_analysis.face_landmarks_i8 import (
    FaceLandmarksI8OnnxInference,
)
from ai.model.onnx.face_detection.face_detector_retinaface import (
    FaceDetectorRetinafaceInference,
)
from ai.model.onnx.face_restoration.gfpganv1_3_2023 import GFPGANv132023Inference
from ai.model.onnx.human_analysis.human_landmarks import HumanLandmarksOnnxInference
from ai.model.onnx.image_embedding.semantic_search_image import SemanticSearchImageInference
from ai.model.onnx.iris_landmarks.iris_landmarks import IrisLandmarksOnnxInference
from ai.model.onnx.light_detection.magic_lights_exp37_dataset123_1024 import (
    MagicLightsExp37OnnxInference,
)
from ai.model.onnx.luminance_denoise.model_luminocity_denoise import (
    ModelLuminocityDenoiseInference,
)
from ai.model.onnx.portrait_bokeh.mobilenet_exp78_portrait_bokeh12 import (
    MobilenetExp78PortraitBOKEH12Inference,
)
from ai.model.onnx.salient_segmentation.salient_object_improve_exp19_it150k import (
    SalientObjectImproveExp19It150KInference,
)
from ai.model.onnx.semantic_segmentation.multiclass_segmentation_v2 import (
    MulticlassSegmentationV2Inference,
)
from ai.model.onnx.semantic_segmentation.segmentator_i8 import (
    SegmentatorI8OnnxInference,
)
from ai.model.openvino.depth_estimation.depth_anything_v2_small_open_vino import (
    DepthAnythingV2SmallOpenVinoInference,
)
from ai.model.openvino.face_analysis.eyes_detector_i8 import EyesDetectorI8Inference
from ai.model.openvino.face_analysis.face_boxes_i8 import FaceBoxesI8Inference
from ai.model.openvino.face_analysis.face_landmarks_i8 import FaceLandmarksI8Inference
from ai.model.openvino.face_restoration.gfpganv1_3_2023_ir import (
    GFPGANv132023IrInference,
)
from ai.model.openvino.human_analysis.human_clothes_exp13_v2 import (
    HumanClothesExp13V2Inference,
)
from ai.model.openvino.human_analysis.human_landmarks import HumanLandmarksInference
from ai.model.openvino.iris_landmarks.iris_landmarks import IrisLandmarksInference
from ai.model.openvino.light_detection.magic_lights_exp37_dataset123_1024 import (
    MagicLightsExp37Dataset1231024Inference,
)
from ai.model.openvino.portrait_bokeh.mobilenet_exp78_portrait_bokeh12_ir import (
    MobilenetExp78PortraitBOKEH12IrInference,
)
from ai.model.openvino.saliency_segmentation.saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8 import (
    SaliencyMapOpset9BillinearUpsamplingKerasTensorflowI8Inference,
)
from ai.model.openvino.semantic_segmentation.segmentator_i8 import SegmentatorI8Inference
from ai.model.openvino.skin_segmentation.skin_detector_i8 import SkinDetectorI8Inference


class _InputBackend:
    def __init__(self, name: str, shape: tuple[int, ...]) -> None:
        self.spec = TensorSpec(name=name, shape=shape, dtype="tensor(float)")

    def input_specs(self) -> tuple[TensorSpec, ...]:
        return (self.spec,)


def _wrapper(wrapper_type: type, name: str, shape: tuple[int, ...]):
    return wrapper_type(
        "test-model",
        Path("unused.onnx"),
        backend=_InputBackend(name, shape),
    )


def test_gfpgan_owns_minus_one_to_one_input_and_zero_one_output() -> None:
    wrapper = _wrapper(GFPGANv132023Inference, "input", (1, 3, 512, 512))
    image = np.zeros((512, 512, 3), dtype=np.uint8)
    image[..., 0] = 255  # BGR blue becomes the final RGB channel.

    tensor = wrapper.preprocess(image)["input"]
    restored = wrapper.postprocess(
        {"1434/sink_port_0": np.asarray([[[[-1.2]], [[0.0]], [[1.2]]]], np.float32)}
    )["restored"]

    assert tensor.shape == (1, 3, 512, 512)
    np.testing.assert_allclose(tensor[0, :, 0, 0], [-1.0, -1.0, 1.0])
    np.testing.assert_allclose(restored.reshape(-1), [0.0, 0.5, 1.0])


def test_semantic_search_owns_clip_normalization_and_unit_embedding() -> None:
    wrapper = _wrapper(SemanticSearchImageInference, "image", (1, 3, 224, 224))
    image = np.full((224, 224, 3), 255, dtype=np.uint8)

    tensor = wrapper.preprocess(image)["image"]
    vector = wrapper.postprocess({"features": np.asarray([[3.0, 4.0]], np.float32)})[
        "vector"
    ]

    assert tensor.shape == (1, 3, 224, 224)
    np.testing.assert_allclose(float(np.linalg.norm(vector)), 1.0, atol=1e-6)
    np.testing.assert_allclose(vector, [0.6, 0.8], atol=1e-6)


def test_multiclass_wrapper_converts_logits_to_probabilities_and_labels() -> None:
    wrapper = _wrapper(
        MulticlassSegmentationV2Inference, "input", (1, 3, 1024, 1024)
    )
    logits = np.zeros((1, 8, 2, 2), dtype=np.float32)
    logits[:, 3] = 5.0

    result = wrapper.postprocess({"output": logits})

    assert result["probabilities"].shape == (8, 2, 2)
    np.testing.assert_array_equal(result["labels"], np.full((2, 2), 3, np.int32))


def test_converted_eye_and_scene_segmentators_preserve_class_contract() -> None:
    eyes = _wrapper(EyesDetectorI8OnnxInference, "input", (1, 3, 80, 160))
    eye_logits = np.zeros((1, 3, 2, 3), dtype=np.float32)
    eye_logits[:, 2] = 4.0
    eye_result = eyes.postprocess({"probability": eye_logits})
    assert eye_result["probabilities"].shape == (3, 2, 3)
    np.testing.assert_array_equal(eye_result["labels"], np.full((2, 3), 2, np.int32))

    scene = _wrapper(SegmentatorI8OnnxInference, "input", (1, 3, 513, 513))
    scene_logits = np.zeros((1, 151, 2, 2), dtype=np.float32)
    scene_logits[:, 13] = 5.0
    scene_result = scene.postprocess({"probability": scene_logits})
    assert scene_result["probabilities"].shape == (151, 2, 2)
    np.testing.assert_array_equal(scene_result["labels"], np.full((2, 2), 13, np.int32))


def test_face_landmarks_return_normalized_points_and_confidence() -> None:
    wrapper = _wrapper(FaceLandmarksI8OnnxInference, "input", (1, 3, 256, 256))
    heatmaps = np.zeros((1, 69, 4, 5), dtype=np.float32)
    heatmaps[:, :, 2, 3] = 0.75

    result = wrapper.postprocess({"heatmaps": heatmaps})

    assert result["points"].shape == (69, 2)
    np.testing.assert_allclose(result["points"][0], [0.75, 2.0 / 3.0])
    np.testing.assert_allclose(result["confidence"], 0.75)


@pytest.mark.parametrize(
    "wrapper_type",
    [HumanLandmarksOnnxInference, IrisLandmarksOnnxInference],
)
def test_dense_landmark_wrappers_preserve_heatmaps_and_derive_labels(
    wrapper_type: type,
) -> None:
    wrapper = _wrapper(wrapper_type, "in", (1, 256, 256, 3))
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[..., 0] = 255
    tensor = wrapper.preprocess(image)["in"]
    heatmaps = np.zeros((1, 3, 4, 18), dtype=np.float32)
    heatmaps[..., 7] = 0.5

    result = wrapper.postprocess({"out": heatmaps})

    assert tensor.shape == (1, 256, 256, 3)
    np.testing.assert_allclose(tensor[0, 0, 0], [0.0, 0.0, 1.0])
    assert result["heatmaps"].shape == (3, 4, 18)
    np.testing.assert_array_equal(result["labels"], np.full((3, 4), 7, np.int32))


def test_retinaface_normalizes_decoded_boxes_landmarks_and_applies_nms() -> None:
    wrapper = _wrapper(
        FaceDetectorRetinafaceInference, "input_1", (1, 3, 1024, 1024)
    )
    boxes = np.asarray([[[100, 200, 500, 600], [110, 210, 490, 590], [700, 50, 900, 250]]], np.float32)
    scores = np.asarray([[[0.01, 0.99], [0.02, 0.98], [0.2, 0.8]]], np.float32)
    landmarks = np.asarray(
        [[[200, 300] * 5, [210, 310] * 5, [750, 100] * 5]], np.float32
    )

    result = wrapper.postprocess(
        {"boxes": boxes, "scores": scores, "landmarks": landmarks}
    )

    assert result["boxes"].shape == (2, 4)
    np.testing.assert_allclose(
        result["boxes"][0], np.asarray([100, 200, 500, 600]) / 1024
    )
    assert result["landmarks"].shape == (2, 5, 2)
    np.testing.assert_allclose(result["scores"], [0.99, 0.8])


def test_portrait_bokeh_selects_probability_not_thresholded_segmap() -> None:
    wrapper = _wrapper(
        MobilenetExp78PortraitBOKEH12Inference, "input", (1, 3, 513, 513)
    )
    probability = np.full((1, 1, 513, 513), 0.35, dtype=np.float32)
    labels = np.zeros((1, 513, 513), dtype=np.int32)

    result = wrapper.postprocess(
        {
            "Decoder/segmap/sink_port_0": labels,
            "Decoder/Sigmoid/sink_port_0": probability,
        }
    )

    assert result["mask"].shape == (513, 513)
    np.testing.assert_allclose(result["mask"], 0.35)


def test_luminance_denoise_clips_small_model_overshoot() -> None:
    wrapper = _wrapper(
        ModelLuminocityDenoiseInference, "input", (1, 1, 256, 256)
    )
    output = np.zeros((1, 1, 256, 256), dtype=np.float32)
    output[..., 0, 0] = -0.1
    output[..., 0, 1] = 1.1

    result = wrapper.postprocess({"output": output})["luminance"]

    assert float(result.min()) == 0.0
    assert float(result.max()) == 1.0


def test_salient_object_returns_foreground_probability_mask() -> None:
    wrapper = _wrapper(
        SalientObjectImproveExp19It150KInference, "input", (1, 3, 512, 512)
    )
    logits = np.zeros((1, 2, 512, 512), dtype=np.float32)
    logits[:, 1] = 2.0

    mask = wrapper.postprocess({"output": logits})["mask"]

    assert mask.shape == (512, 512)
    np.testing.assert_allclose(mask, 1.0 / (1.0 + np.exp(-2.0)), atol=1e-6)


def test_srn_deblur_validates_shape_and_clips_output() -> None:
    wrapper = _wrapper(SrnDeblur512Inference, "Placeholder:0", (1, 3, 512, 512))
    output = np.full((1, 3, 512, 512), 1.1, dtype=np.float32)

    restored = wrapper.postprocess({"g_net/dec1_0_2/BiasAdd:0": output})["restored"]

    assert restored.shape == (1, 3, 512, 512)
    assert float(restored.max()) == 1.0
    with pytest.raises(ValueError, match="SRN deblur output is invalid"):
        wrapper.postprocess({"output": np.zeros((1, 3, 8, 8), np.float32)})


def _magic_lights_logits(*, scale: int = 32) -> np.ndarray:
    return np.full((1, 3, scale, scale, 6), -30.0, dtype=np.float32)


def test_magic_lights_owns_rgb_input_and_yolov5_decode_contract() -> None:
    wrapper = _wrapper(
        MagicLightsExp37OnnxInference, "images", (1, 3, 1024, 1024)
    )
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[..., 0] = 255  # BGR blue becomes the final RGB channel.
    tensor = wrapper.preprocess(image)["images"]

    logits = _magic_lights_logits()
    logits[0, 0, 3, 5, :4] = 0.0
    logits[0, 0, 3, 5, 4:] = 2.0
    result = wrapper.postprocess({"609": logits})

    expected_center = np.asarray([(5.5 / 32), (3.5 / 32)], dtype=np.float32)
    expected_size = np.asarray([116 / 1024, 90 / 1024], dtype=np.float32)
    expected_box = np.concatenate(
        (expected_center - expected_size / 2, expected_center + expected_size / 2)
    )
    assert tensor.shape == (1, 3, 1024, 1024)
    np.testing.assert_allclose(tensor[0, :, 0, 0], [0.0, 0.0, 1.0])
    np.testing.assert_allclose(result["boxes"], expected_box[None], atol=1e-6)
    np.testing.assert_allclose(
        result["scores"], [(1.0 / (1.0 + np.exp(-2.0))) ** 2], atol=1e-6
    )


def test_magic_lights_threshold_nms_and_signature_are_fail_closed() -> None:
    below = _magic_lights_logits()
    below[0, 0, 3, 5, :4] = 0.0
    below[0, 0, 3, 5, 4:] = -0.01
    wrapper = _wrapper(
        MagicLightsExp37OnnxInference, "images", (1, 3, 1024, 1024)
    )
    assert wrapper.postprocess({"609": below})["boxes"].shape == (0, 4)

    detected = _magic_lights_logits()
    detected[0, 0, 3, 5, :4] = 0.0
    detected[0, 0, 3, 5, 4:] = 2.0
    deduplicated = wrapper.postprocess({"first": detected, "duplicate": detected})
    assert deduplicated["boxes"].shape == (1, 4)

    with pytest.raises(ValueError, match="output signature is incompatible"):
        wrapper.postprocess({"unexpected": np.zeros((1, 6, 32, 32), np.float32)})


@pytest.mark.parametrize(
    "wrapper_type,input_name,input_shape,outputs,expected_key",
    [
        (
            GFPGANv132023IrInference,
            "input",
            (1, 3, 512, 512),
            {"output": np.zeros((1, 3, 1, 1), dtype=np.float32)},
            "restored",
        ),
        (
            EyesDetectorI8Inference,
            "input",
            (1, 3, 80, 160),
            {"probability": np.zeros((1, 3, 2, 3), dtype=np.float32)},
            "labels",
        ),
        (
            FaceLandmarksI8Inference,
            "input",
            (1, 3, 256, 256),
            {"heatmaps": np.zeros((1, 69, 4, 5), dtype=np.float32)},
            "points",
        ),
        (
            HumanLandmarksInference,
            "input",
            (1, 256, 256, 3),
            {"heatmaps": np.zeros((1, 3, 4, 18), dtype=np.float32)},
            "labels",
        ),
        (
            IrisLandmarksInference,
            "input",
            (1, 256, 256, 3),
            {"heatmaps": np.zeros((1, 3, 4, 18), dtype=np.float32)},
            "labels",
        ),
        (
            HumanClothesExp13V2Inference,
            "input",
            (1, 3, 1024, 1024),
            {"probability": np.zeros((1, 3, 2, 3), dtype=np.float32)},
            "labels",
        ),
        (
            SegmentatorI8Inference,
            "input",
            (1, 3, 513, 513),
            {"probability": np.zeros((1, 151, 2, 2), dtype=np.float32)},
            "labels",
        ),
    ],
)
def test_openvino_fallbacks_expose_model_specific_output_contracts(
    wrapper_type: type,
    input_name: str,
    input_shape: tuple[int, ...],
    outputs: dict[str, np.ndarray],
    expected_key: str,
) -> None:
    wrapper = _wrapper(wrapper_type, input_name, input_shape)
    assert expected_key in wrapper.postprocess(outputs)


def test_openvino_fallbacks_own_model_specific_input_and_decode_rules() -> None:
    image = np.full((8, 8, 3), 255, dtype=np.uint8)

    depth = _wrapper(
        DepthAnythingV2SmallOpenVinoInference, "input", (1, 3, 518, 518)
    )
    depth_tensor = depth.preprocess(image)["input"]
    expected = np.asarray(
        [(1.0 - 0.485) / 0.229, (1.0 - 0.456) / 0.224, (1.0 - 0.406) / 0.225]
    )
    np.testing.assert_allclose(depth_tensor[0, :, 0, 0], expected, atol=1e-6)
    depth_output = np.linspace(0.0, 10.0, 518 * 518, dtype=np.float32).reshape(
        1, 1, 518, 518
    )
    normalized = depth.postprocess({"depth": depth_output})["depth"]
    assert normalized.shape == (518, 518)
    assert float(normalized.min()) == 0.0
    assert float(normalized.max()) == 1.0

    face_boxes = _wrapper(FaceBoxesI8Inference, "input", (1, 3, 256, 256))
    raw = face_boxes.preprocess(image)["input"]
    np.testing.assert_allclose(raw, 255.0)
    boxes = face_boxes.postprocess(
        {
            "boxes": np.asarray([[[0.1, 0.2, 0.8, 0.9]]], dtype=np.float32),
            "classes": np.asarray([[1]], dtype=np.int64),
            "scores": np.asarray([[0.75]], dtype=np.float32),
        }
    )
    assert boxes["boxes"].shape == (1, 4)

    magic = _wrapper(
        MagicLightsExp37Dataset1231024Inference,
        "images",
        (1, 3, 1024, 1024),
    )
    assert magic.preprocess(image)["images"].shape == (1, 3, 1024, 1024)
    assert magic.postprocess({"output": _magic_lights_logits()})["boxes"].shape == (
        0,
        4,
    )

    portrait = _wrapper(
        MobilenetExp78PortraitBOKEH12IrInference,
        "input",
        (1, 3, 513, 513),
    )
    probability = np.full((1, 1, 513, 513), 0.35, dtype=np.float32)
    np.testing.assert_allclose(
        portrait.postprocess({"Sigmoid": probability})["mask"], 0.35
    )

    saliency = _wrapper(
        SaliencyMapOpset9BillinearUpsamplingKerasTensorflowI8Inference,
        "input",
        (1, 3, 256, 256),
    )
    probabilities = np.full((1, 1, 256, 256), 0.75, dtype=np.float32)
    np.testing.assert_allclose(
        saliency.postprocess({"probabilities": probabilities})["mask"], 0.75
    )

    skin = _wrapper(SkinDetectorI8Inference, "input", (1, 3, 513, 513))
    assert skin.preprocess(np.zeros((8, 8, 3), dtype=np.uint8))["input"].shape == (
        1,
        3,
        513,
        513,
    )
