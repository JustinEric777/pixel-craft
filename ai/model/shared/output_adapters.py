"""Small, model-agnostic adapters for validated tensor output families."""

from __future__ import annotations

from typing import Any

import numpy as np


def first_tensor(outputs: dict[str, Any]) -> np.ndarray:
    if not outputs:
        raise ValueError("model returned no outputs")
    return np.asarray(next(iter(outputs.values())))


def multiclass_segmentation(outputs: dict[str, Any]) -> dict[str, np.ndarray]:
    tensors = [np.asarray(value) for value in outputs.values()]
    probabilities = next((value for value in tensors if value.ndim == 4), None)
    labels = next((value for value in tensors if value.ndim == 3), None)
    if probabilities is None:
        raise ValueError("multiclass model returned no NCHW tensor")
    logits = probabilities.astype(np.float32, copy=False)
    if float(logits.min()) < 0.0 or float(logits.max()) > 1.0:
        shifted = logits - logits.max(axis=1, keepdims=True)
        exponential = np.exp(np.clip(shifted, -30.0, 30.0))
        probabilities = exponential / np.maximum(exponential.sum(axis=1, keepdims=True), 1e-8)
    if labels is None:
        labels = np.argmax(probabilities, axis=1)
    return {
        "probabilities": np.asarray(probabilities[0], dtype=np.float32),
        "labels": np.asarray(labels[0], dtype=np.int32),
    }


def heatmap_landmarks(outputs: dict[str, Any]) -> dict[str, np.ndarray]:
    heatmaps = first_tensor(outputs).astype(np.float32, copy=False)
    if heatmaps.ndim != 4 or heatmaps.shape[0] != 1:
        raise ValueError(f"expected landmark heatmaps, got {heatmaps.shape}")
    channels = heatmaps[0]
    height, width = channels.shape[1:]
    flat = channels.reshape(channels.shape[0], -1)
    indices = np.argmax(flat, axis=1)
    points = np.column_stack((indices % width, indices // width)).astype(np.float32)
    points[:, 0] /= max(width - 1, 1)
    points[:, 1] /= max(height - 1, 1)
    confidence = np.max(flat, axis=1).astype(np.float32)
    return {"points": points, "confidence": confidence, "heatmaps": channels}


def dense_nhwc_heatmaps(outputs: dict[str, Any], *, channels: int) -> dict[str, np.ndarray]:
    """Preserve a validated NHWC dense-landmark tensor and derive class ids."""
    heatmaps = first_tensor(outputs).astype(np.float32, copy=False)
    if heatmaps.ndim != 4 or heatmaps.shape[0] != 1 or heatmaps.shape[-1] != channels:
        raise ValueError(
            f"expected one NHWC tensor with {channels} channels, got {heatmaps.shape}"
        )
    values = heatmaps[0]
    if not np.isfinite(values).all():
        raise ValueError("dense landmark heatmaps contain non-finite values")
    return {
        "heatmaps": values,
        "labels": np.argmax(values, axis=-1).astype(np.int32),
    }


def normalized_depth(outputs: dict[str, Any]) -> np.ndarray:
    depth = np.squeeze(first_tensor(outputs)).astype(np.float32, copy=False)
    if depth.ndim != 2:
        raise ValueError(f"expected a two-dimensional depth map, got {depth.shape}")
    minimum, maximum = float(depth.min()), float(depth.max())
    if maximum - minimum <= 1e-8:
        return np.zeros_like(depth, dtype=np.float32)
    return (depth - minimum) / (maximum - minimum)


def detection_boxes(
    outputs: dict[str, Any], *, confidence_threshold: float = 0.25
) -> dict[str, np.ndarray]:
    values = [np.asarray(value) for value in outputs.values()]
    boxes = next((value for value in values if value.ndim == 3 and value.shape[-1] == 4), None)
    classes = next(
        (value for value in values if value.ndim == 2 and np.issubdtype(value.dtype, np.integer)),
        None,
    )
    scores = next(
        (value for value in values if value.ndim == 2 and np.issubdtype(value.dtype, np.floating)),
        None,
    )
    if boxes is None or classes is None or scores is None:
        raise ValueError("detector output signature is incomplete")
    selected = scores[0] >= confidence_threshold
    return {
        "boxes": np.asarray(boxes[0][selected], dtype=np.float32),
        "classes": np.asarray(classes[0][selected], dtype=np.int32),
        "scores": np.asarray(scores[0][selected], dtype=np.float32),
    }


def retinaface_detections(
    outputs: dict[str, Any],
    *,
    input_size: tuple[int, int] = (1024, 1024),
    confidence_threshold: float = 0.5,
    nms_iou_threshold: float = 0.4,
    max_detections: int = 100,
) -> dict[str, np.ndarray]:
    """Normalize decoded RetinaFace tensors and apply score-ordered NMS."""

    boxes = np.asarray(outputs.get("boxes"), dtype=np.float32)
    scores = np.asarray(outputs.get("scores"), dtype=np.float32)
    landmarks = np.asarray(outputs.get("landmarks"), dtype=np.float32)
    if boxes.ndim != 3 or boxes.shape[0] != 1 or boxes.shape[-1] != 4:
        raise ValueError(f"RetinaFace boxes are invalid: {boxes.shape}")
    if scores.shape != (1, boxes.shape[1], 2):
        raise ValueError(f"RetinaFace scores are invalid: {scores.shape}")
    if landmarks.shape != (1, boxes.shape[1], 10):
        raise ValueError(f"RetinaFace landmarks are invalid: {landmarks.shape}")
    confidence = scores[0, :, 1]
    selected = np.flatnonzero(
        np.isfinite(confidence) & (confidence >= confidence_threshold)
    )
    if not selected.size:
        return {
            "boxes": np.empty((0, 4), np.float32),
            "scores": np.empty(0, np.float32),
            "landmarks": np.empty((0, 5, 2), np.float32),
        }
    candidates = boxes[0, selected]
    candidate_landmarks = landmarks[0, selected].reshape(-1, 5, 2)
    candidate_scores = confidence[selected]
    finite = np.isfinite(candidates).all(axis=1) & np.isfinite(
        candidate_landmarks
    ).all(axis=(1, 2))
    candidates = candidates[finite]
    candidate_landmarks = candidate_landmarks[finite]
    candidate_scores = candidate_scores[finite]
    order = np.argsort(candidate_scores)[::-1]
    keep: list[int] = []
    while order.size and len(keep) < max_detections:
        current = int(order[0])
        keep.append(current)
        if order.size == 1:
            break
        rest = order[1:]
        box = candidates[current]
        other = candidates[rest]
        top_left = np.maximum(box[:2], other[:, :2])
        bottom_right = np.minimum(box[2:], other[:, 2:])
        intersection = np.prod(np.maximum(bottom_right - top_left, 0.0), axis=1)
        area = np.prod(np.maximum(box[2:] - box[:2], 0.0))
        other_area = np.prod(np.maximum(other[:, 2:] - other[:, :2], 0.0), axis=1)
        iou = intersection / np.maximum(area + other_area - intersection, 1e-8)
        order = rest[iou < nms_iou_threshold]
    width, height = input_size
    box_scale = np.asarray([width, height, width, height], dtype=np.float32)
    point_scale = np.asarray([width, height], dtype=np.float32)
    return {
        "boxes": np.clip(candidates[keep] / box_scale, 0.0, 1.0).astype(
            np.float32
        ),
        "scores": candidate_scores[keep].astype(np.float32),
        "landmarks": np.clip(
            candidate_landmarks[keep] / point_scale, 0.0, 1.0
        ).astype(np.float32),
    }


def yolo_light_boxes(
    outputs: dict[str, Any],
    *,
    input_size: int = 1024,
    confidence_threshold: float = 0.25,
    nms_iou_threshold: float = 0.45,
    max_detections: int = 256,
) -> dict[str, np.ndarray]:
    anchors = {
        32: ((116, 90), (156, 198), (373, 326)),
        64: ((30, 61), (62, 45), (59, 119)),
        128: ((10, 13), (16, 30), (33, 23)),
    }
    candidates: list[np.ndarray] = []
    compatible_tensors = 0
    for tensor in outputs.values():
        values = np.asarray(tensor, dtype=np.float32)
        if (
            values.ndim != 5
            or values.shape[0] != 1
            or values.shape[1] != 3
            or values.shape[2] != values.shape[3]
            or values.shape[-1] != 6
        ):
            continue
        scale = values.shape[2]
        if scale not in anchors:
            continue
        compatible_tensors += 1
        prediction = 1.0 / (1.0 + np.exp(-np.clip(values[0], -30.0, 30.0)))
        yy, xx = np.meshgrid(np.arange(scale), np.arange(scale), indexing="ij")
        grid = np.stack((xx, yy), axis=-1)[None]
        center = (prediction[..., :2] * 2.0 - 0.5 + grid) / scale
        anchor = np.asarray(anchors[scale], dtype=np.float32)[:, None, None, :] / input_size
        size = (prediction[..., 2:4] * 2.0) ** 2 * anchor
        confidence = prediction[..., 4] * prediction[..., 5]
        selected = confidence >= confidence_threshold
        if not np.any(selected):
            continue
        xyxy = np.concatenate((center - size / 2.0, center + size / 2.0), axis=-1)
        candidates.append(np.column_stack((xyxy[selected], confidence[selected])))
    if compatible_tensors == 0:
        shapes = {name: list(np.asarray(value).shape) for name, value in outputs.items()}
        raise ValueError(f"magic-lights YOLO output signature is incompatible: {shapes}")
    if not candidates:
        return {"boxes": np.empty((0, 4), np.float32), "scores": np.empty(0, np.float32)}
    detections = np.concatenate(candidates, axis=0)
    order = np.argsort(detections[:, 4])[::-1]
    keep: list[int] = []
    while order.size and len(keep) < max_detections:
        current = int(order[0])
        keep.append(current)
        if order.size == 1:
            break
        rest = order[1:]
        box = detections[current, :4]
        other = detections[rest, :4]
        top_left = np.maximum(box[:2], other[:, :2])
        bottom_right = np.minimum(box[2:], other[:, 2:])
        intersection = np.prod(np.maximum(bottom_right - top_left, 0.0), axis=1)
        area = np.prod(np.maximum(box[2:] - box[:2], 0.0))
        other_area = np.prod(np.maximum(other[:, 2:] - other[:, :2], 0.0), axis=1)
        iou = intersection / np.maximum(area + other_area - intersection, 1e-8)
        order = rest[iou < nms_iou_threshold]
    selected = detections[keep]
    return {
        "boxes": np.clip(selected[:, :4], 0.0, 1.0).astype(np.float32),
        "scores": selected[:, 4].astype(np.float32),
    }
