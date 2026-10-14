"""Model-backed analysis, search and artifact pipelines."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from PIL import Image

from ai.preprocess.image import ResizeTransform, softmax

from .output_utils import is_probability_output
from .ports import ArtifactCachePort

logger = logging.getLogger(__name__)


class AnalysisPipelinesMixin:
    def analyze(
        self,
        image: Image.Image,
        requested: list[str] | None = None,
        *,
        artifact_cache: ArtifactCachePort | None = None,
        source_hash: str | None = None,
    ) -> dict[str, Any]:
        requested = requested or [
            "face_detector_retinaface",
            "salient_object_improve_exp19_it150k",
            "MulticlassSegmentationV2",
            "SemanticSearchImage",
            "DepthAnythingV2SmallOpenVino",
            "improved_sky_segmentator_v462_i8",
        ]
        results: dict[str, Any] = {}
        for requested_model_id in requested:
            model_id = self._resolve_model_id(requested_model_id)
            if (
                model_id not in self.registry.records
                or not self.registry.require(model_id).path.exists()
            ):
                unavailable = {
                    "DepthAnythingV2SmallOpenVino": (
                        "depth_map",
                        "converted model is not ORT-valid",
                    ),
                    "improved_sky_segmentator_v462_i8": (
                        "sky_mask",
                        "dedicated sky model is unavailable in the active runtime",
                    ),
                }
                name, reason = unavailable.get(
                    requested_model_id, (requested_model_id, "model is not registered")
                )
                results[name] = {"status": "blocked", "model": requested_model_id, "reason": reason}
                continue
            dispatch: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
                "face_detector_retinaface": (
                    "face_boxes",
                    lambda model_id=model_id: self._face_boxes(image, model_id),
                ),
                "salient_object_improve_exp19_it150k": (
                    "salient_mask",
                    lambda model_id=model_id: self._mask(image, model_id, (512, 512)),
                ),
                "SemanticSearchImage": (
                    "image_embedding",
                    lambda model_id=model_id: self._embedding(image, model_id),
                ),
                "mobilenet_exp78_portrait_BOKEH12": (
                    "bokeh_mask",
                    lambda model_id=model_id: self._single_mask(image, model_id, (513, 513)),
                ),
                "MulticlassSegmentationV2": (
                    "semantic_mask",
                    lambda model_id=model_id: self._semantic_mask(image, model_id, (1024, 1024)),
                ),
                "SegmentAnything": (
                    "interactive_segmentation",
                    lambda model_id=model_id: self._tensor_summary(image, model_id, (1024, 1024)),
                ),
                "LPTN_exp108_wires": (
                    "wire_mask",
                    lambda model_id=model_id: self._single_mask(image, model_id, (1024, 1024)),
                ),
                "DFINEHumanTransportDetection": (
                    "human_detections",
                    lambda model_id=model_id: self._detection_summary(image, model_id),
                ),
                "dust_spot_det_i8": (
                    "dust_detections",
                    lambda model_id=model_id: self._tensor_summary(image, model_id, (640, 640)),
                ),
                "GFPGANv1.3_2023": (
                    "face_restoration_preview",
                    lambda model_id=model_id: self._restoration_summary(
                        image, model_id, (512, 512)
                    ),
                ),
                "improved_sky_segmentator_v462_i8": (
                    "sky_mask",
                    lambda: self._sky_analysis(image),
                ),
                "depth_map_i8": (
                    "depth_map",
                    lambda model_id=model_id: self._single_mask(image, model_id, (513, 513)),
                ),
                "DepthAnythingV2SmallOpenVino": (
                    "depth_map",
                    lambda model_id=model_id: self._single_mask(image, model_id, (518, 518)),
                ),
                "face_boxes_i8": (
                    "face_boxes_ir",
                    lambda model_id=model_id: self._detection_summary(image, model_id),
                ),
                "skin_detector_i8": (
                    "skin_mask",
                    lambda model_id=model_id: self._mask(image, model_id, (513, 513)),
                ),
                "hair_exp11_i8": (
                    "hair_mask",
                    lambda model_id=model_id: self._single_mask(image, model_id, (513, 513)),
                ),
                "human_clothes_exp13_v2": (
                    "clothes_mask",
                    lambda model_id=model_id: self._semantic_mask(image, model_id, (1024, 1024)),
                ),
                "horizon_align_i8": (
                    "horizon_angle",
                    lambda model_id=model_id: self._horizon_analysis(image, model_id),
                ),
                "skyinwater_v16_i8": (
                    "sky_reflection_mask",
                    lambda model_id=model_id: self._single_mask(image, model_id, (513, 513)),
                ),
                "HumanLandmarks": (
                    "human_landmarks",
                    lambda model_id=model_id: self._tensor_summary(image, model_id, (256, 256)),
                ),
                "IrisLandmarks": (
                    "iris_landmarks",
                    lambda model_id=model_id: self._tensor_summary(image, model_id, (256, 256)),
                ),
            }
            dispatch_key = (
                requested_model_id if requested_model_id in dispatch else model_id
            )
            if dispatch_key not in dispatch:
                results[requested_model_id] = {"status": "registered-not-dispatched"}
                continue
            artifact_name, compute = dispatch[dispatch_key]
            results[artifact_name] = self._cached_analysis(
                artifact_name,
                model_id,
                compute,
                artifact_cache,
                source_hash,
            )
        return results

    def search(self, image: Image.Image, query: str) -> dict[str, Any]:
        """Compare one source image with a text query using local ONNX models."""
        if not query.strip():
            return {"status": "invalid", "reason": "query must not be empty"}
        image_model = self._resolve_model_id("SemanticSearchImage")
        text_model = self._resolve_model_id("SemanticSearchText")
        if image_model not in self.registry.records or text_model not in self.registry.records:
            return {"status": "blocked", "reason": "semantic search models are not registered"}
        if self._tokenizer is None:
            return {"status": "blocked", "reason": "local tokenizer asset is missing"}
        image_result = self._embedding(image, image_model)
        input_ids, attention_mask = self._tokenizer.encode(query)
        text_result = self._run_text(text_model, input_ids, attention_mask)
        vector = np.asarray(text_result, dtype=np.float32).reshape(-1)
        vector /= max(float(np.linalg.norm(vector)), 1e-8)
        image_vector = np.asarray(image_result["vector"], dtype=np.float32)
        return {
            "status": "ready",
            "query": query,
            "model": {"image": image_model, "text": text_model},
            "dimensions": int(vector.size),
            "similarity": float(np.dot(image_vector, vector)),
            "tokens": input_ids,
        }

    def _run_text(self, model_id: str, input_ids: list[int], attention_mask: list[int]) -> np.ndarray:
        with self.lease(model_id) as inference:
            result = inference.predict({
                "input_ids": np.asarray([input_ids], dtype=np.int32),
                "attention_mask": np.asarray([attention_mask], dtype=np.int32),
            })
        return np.asarray(self._select_output(result), dtype=np.float32)

    def _sky_analysis(self, image: Image.Image) -> dict[str, Any]:
        mask, info = self._sky_mask(image)
        horizon_angle = self._horizon_value(image)
        return {
            "status": "ready",
            "model": info["model"],
            "quality": info["quality"],
            "shape": list(mask.shape),
            "mean": float(mask.mean()),
            "horizon_fraction": float(info["horizon_fraction"]),
            "horizon_angle": horizon_angle,
            "_artifact_array": mask,
        }

    def _cached_analysis(
        self,
        artifact_name: str,
        model_id: str,
        compute: Callable[[], dict[str, Any]],
        cache: ArtifactCachePort | None,
        source_hash: str | None,
    ) -> dict[str, Any]:
        record = self.registry.require(model_id)
        key = (
            cache.key(
                source_hash=source_hash or "uncached-source",
                artifact_name=artifact_name,
                model_id=model_id,
                model_hash=record.sha256,
                preprocess_version=record.preprocess_version,
                postprocess_version=record.postprocess_version,
            )
            if cache
            else None
        )
        if cache and key:
            cached = cache.get_envelope(key)
            if cached:
                cached["cache_hit"] = True
                return cached
        try:
            result = compute()
        except Exception as exc:  # noqa: BLE001 - surface per-model failures as API data
            result = {
                "status": "failed",
                "model": model_id,
                "error": f"{type(exc).__name__}: {exc}",
            }
        artifact_array = result.pop("_artifact_array", None)
        artifact_arrays = result.pop("_artifact_arrays", None)
        result["cache_hit"] = False
        if key:
            result["cache_key"] = key
        result["runtime"] = self._runtime_for(record)
        result["preprocess_version"] = record.preprocess_version
        result["postprocess_version"] = record.postprocess_version
        if cache and key and result.get("status") == "ready":
            if artifact_array is not None:
                artifact_path = cache.put_array(
                    key,
                    np.asarray(artifact_array),
                    metadata={"artifact_name": artifact_name, "model": model_id},
                )
                result["artifact_path"] = str(artifact_path.relative_to(cache.root))
                result["artifact_dtype"] = str(np.asarray(artifact_array).dtype)
                result["artifact_shape"] = list(np.asarray(artifact_array).shape)
            elif artifact_arrays:
                bundle = {
                    str(name): np.asarray(value)
                    for name, value in dict(artifact_arrays).items()
                }
                artifact_path = cache.put_array_bundle(key, bundle)
                result["artifact_path"] = str(artifact_path.relative_to(cache.root))
                result["artifact_tensors"] = {
                    name: {
                        "dtype": str(value.dtype),
                        "shape": list(value.shape),
                    }
                    for name, value in bundle.items()
                }
            cache.put_json(key, result)
        return result

    @staticmethod
    def _runtime_for(record: Any) -> str:
        if record.format == "openvino_ir":
            return "openvino"
        if record.format in {"onnx", "ort"}:
            return "onnxruntime"
        return record.backend

    def _face_boxes(self, image: Image.Image, model_id: str) -> dict[str, Any]:
        outputs = self._run(image, model_id, size=(1024, 1024)).data
        boxes = np.asarray(outputs.get("boxes", []), dtype=np.float32)
        scores = np.asarray(outputs.get("scores", []), dtype=np.float32)
        landmarks = np.asarray(outputs.get("landmarks", []), dtype=np.float32)
        if boxes.ndim != 2 or boxes.shape[-1:] != (4,):
            raise ValueError(f"RetinaFace wrapper returned invalid boxes: {boxes.shape}")
        return {
            "status": "ready",
            "model": model_id,
            "boxes": boxes.tolist(),
            "scores": scores.tolist(),
            "landmarks": landmarks.tolist(),
        }

    def _single_mask(
        self, image: Image.Image, model_id: str, size: tuple[int, int]
    ) -> dict[str, Any]:
        restored = self._mask_array(image, model_id, size)
        return {
            "status": "ready",
            "model": model_id,
            "shape": list(restored.shape),
            "mean": float(restored.mean()),
            "max": float(restored.max()),
            "_artifact_array": restored,
        }

    def _mask(self, image: Image.Image, model_id: str, size: tuple[int, int]) -> dict[str, Any]:
        output_name, output = self._select_mask_output_entry(
            self._run(image, model_id, size=size).data
        )
        transform = ResizeTransform(image.size, size)
        values = np.asarray(output)
        if values.ndim == 2:
            mask = np.clip(values.astype(np.float32, copy=False), 0.0, 1.0)
        elif values.ndim == 4 and values.shape[1] > 1:
            probabilities = (
                values
                if is_probability_output(output_name, values)
                else softmax(values, axis=1)
            )
            mask = probabilities[:, 1:, :, :].max(axis=1)[0]
        else:
            raise ValueError(
                "expected normalized [H,W] mask or [N,C,H,W] class output, "
                f"got {values.shape}"
            )
        restored = transform.restore_mask(mask)
        return {
            "status": "ready",
            "model": model_id,
            "shape": list(restored.shape),
            "mean": float(restored.mean()),
            "max": float(restored.max()),
            "_artifact_array": restored,
        }

    def _semantic_mask(
        self, image: Image.Image, model_id: str, size: tuple[int, int]
    ) -> dict[str, Any]:
        outputs = self._run(image, model_id, size=size).data
        transform = ResizeTransform(image.size, size)
        labels = next(
            (
                np.asarray(value)
                for value in outputs.values()
                if np.asarray(value).ndim == 2
                and np.issubdtype(np.asarray(value).dtype, np.integer)
            ),
            None,
        )
        if labels is None:
            output = next(
                (np.asarray(value) for value in outputs.values() if np.asarray(value).ndim == 4),
                None,
            )
            if output is None:
                shapes = {name: list(np.asarray(value).shape) for name, value in outputs.items()}
                raise ValueError(
                    "expected semantic labels [H,W] or logits [N,C,H,W], "
                    f"got {shapes}"
                )
            labels = np.argmax(output, axis=1)[0]
        restored = transform.restore_labels(labels)
        values, counts = np.unique(restored, return_counts=True)
        return {
            "status": "ready",
            "model": model_id,
            "shape": list(restored.shape),
            "classes": {str(int(label)): int(count) for label, count in zip(values, counts)},
            "_artifact_array": restored,
        }

    def _horizon_analysis(self, image: Image.Image, model_id: str) -> dict[str, Any]:
        return {"status": "ready", "model": model_id, "angle": self._horizon_value(image, model_id)}

    def _horizon_value(self, image: Image.Image, model_id: str = "horizon_align_i8") -> float | None:
        resolved_id = self._resolve_model_id(model_id)
        if resolved_id not in self.registry.records:
            return None
        try:
            output = self._select_output(
                self._run(image, resolved_id, size=(224, 224)).data
            )
            return float(np.asarray(output, dtype=np.float32).mean())
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("horizon model unavailable: %s", exc)
            return None

    def _tensor_summary(
        self, image: Image.Image, model_id: str, size: tuple[int, int]
    ) -> dict[str, Any]:
        outputs = self._run(image, model_id, size=size).data
        return {
            "status": "ready",
            "model": model_id,
            "outputs": {
                name: {
                    "shape": list(np.asarray(value).shape),
                    "finite": bool(np.isfinite(value).all()),
                }
                for name, value in outputs.items()
            },
            "_artifact_arrays": outputs,
        }

    def _detection_summary(self, image: Image.Image, model_id: str) -> dict[str, Any]:
        raw_outputs = self._run(image, model_id, size=(640, 640)).data
        outputs = list(raw_outputs.values())
        return {
            "status": "ready",
            "model": model_id,
            "outputs": [list(np.asarray(value).shape) for value in outputs],
            "detections": int(np.asarray(outputs[-1]).shape[-2])
            if outputs and np.asarray(outputs[-1]).ndim >= 2
            else 0,
            "_artifact_arrays": raw_outputs,
        }

    def _restoration_summary(
        self, image: Image.Image, model_id: str, size: tuple[int, int]
    ) -> dict[str, Any]:
        restored = self._restore_rgb(image, model_id, size)
        array = np.asarray(restored, dtype=np.float32) / 255.0
        return {
            "status": "ready",
            "model": model_id,
            "shape": list(array.shape),
            "mean": float(array.mean()),
            "min": float(array.min()),
            "max": float(array.max()),
            "_artifact_array": array,
        }

    def _embedding(self, image: Image.Image, model_id: str) -> dict[str, Any]:
        result = self._run(
            image,
            model_id,
            size=(224, 224),
            mean=(0.48145466, 0.4578275, 0.40821073),
            std=(0.26862954, 0.26130258, 0.27577711),
        )
        output = np.asarray(next(iter(result.data.values())), dtype=np.float32).reshape(-1)
        output /= max(float(np.linalg.norm(output)), 1e-8)
        return {
            "status": "ready",
            "model": model_id,
            "dimensions": int(output.size),
            "vector": output.tolist(),
        }
