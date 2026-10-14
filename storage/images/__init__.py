"""Image input/output adapters."""

from .frame_codec import frame_from_pillow, pillow_from_frame
from .pillow_reader import PillowImageReader

__all__ = ["PillowImageReader", "frame_from_pillow", "pillow_from_frame"]
