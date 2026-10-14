from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from core.image_frame import ImageFrame
from storage.cache.artifact_cache import ArtifactCache
from storage.images import frame_from_pillow, pillow_from_frame


def test_frame_round_trips_rgb_and_metadata() -> None:
    source = Image.new("RGB", (5, 4), (10, 20, 30))
    frame = frame_from_pillow(source)
    assert frame.size == (5, 4)
    assert frame.channel_order == "RGB"
    restored = pillow_from_frame(frame)
    assert restored.size == source.size
    assert np.asarray(restored)[0, 0].tolist() == [10, 20, 30]


def test_frame_validates_contract() -> None:
    with pytest.raises(ValueError, match="shape"):
        ImageFrame(np.zeros((4, 5), dtype=np.uint8))


def test_artifact_v3_envelope_persists_array_metadata(tmp_path) -> None:
    cache = ArtifactCache(tmp_path)
    array = np.zeros((3, 4), dtype=np.float32)
    cache.put_array("artifact", array, metadata={"artifact_name": "sky_mask", "model": "sky"})
    envelope = cache.get_envelope("artifact")
    assert envelope is not None
    assert envelope["artifact_cache_version"] == "artifact-cache-v3"
    assert envelope["artifact_shape"] == [3, 4]
