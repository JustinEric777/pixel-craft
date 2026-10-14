"""Small output adapters shared by model-specific wrappers."""

from .binary_mask import binary_class_mask, single_channel_mask
from .output_adapters import (
    dense_nhwc_heatmaps,
    detection_boxes,
    first_tensor,
    heatmap_landmarks,
    multiclass_segmentation,
    normalized_depth,
    retinaface_detections,
    yolo_light_boxes,
)

__all__ = [
    "binary_class_mask",
    "dense_nhwc_heatmaps",
    "detection_boxes",
    "first_tensor",
    "heatmap_landmarks",
    "multiclass_segmentation",
    "normalized_depth",
    "retinaface_detections",
    "single_channel_mask",
    "yolo_light_boxes",
]
