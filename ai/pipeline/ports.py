"""Ports needed by model pipelines without binding to storage or render packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image


class ArtifactCachePort(Protocol):
    root: Path

    def key(self, **values: Any) -> str: ...

    def get_envelope(self, key: str) -> dict[str, Any] | None: ...

    def put_array(
        self, key: str, value: np.ndarray, *, metadata: dict[str, Any] | None = None
    ) -> Path: ...

    def put_array_bundle(self, key: str, values: dict[str, np.ndarray]) -> Path: ...

    def put_json(self, key: str, value: dict[str, Any]) -> Path: ...


class SkyCompositor(Protocol):
    def __call__(
        self,
        base: Image.Image,
        texture: Image.Image,
        mask: np.ndarray,
        parameters: dict[str, Any],
    ) -> Image.Image: ...
