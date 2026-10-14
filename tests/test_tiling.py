from __future__ import annotations

import numpy as np

from ai.preprocess.tiling import Tile, plan_tiles, stitch_tiles


def test_plan_tiles_covers_edges_without_duplicates() -> None:
    tiles = plan_tiles(100, 80, (32, 32), overlap=0.25)
    assert tiles
    assert max(tile.x + tile.width for tile in tiles) == 100
    assert max(tile.y + tile.height for tile in tiles) == 80
    assert len({(tile.x, tile.y) for tile in tiles}) == len(tiles)


def test_stitch_tiles_preserves_constant_values() -> None:
    tile = Tile(0, 0, 8, 8)
    value = np.ones((8, 8, 3), dtype=np.float32) * 0.75
    result = stitch_tiles([(tile, value)], (8, 8))
    assert result.shape == (8, 8, 3)
    assert np.allclose(result, 0.75)


def test_stitch_tiles_resizes_float_rgb_outputs() -> None:
    tile = Tile(0, 0, 4, 4)
    value = np.zeros((8, 8, 3), dtype=np.float32)
    value[..., 0] = 0.2
    value[..., 1] = 0.5
    value[..., 2] = 0.8
    result = stitch_tiles([(tile, value)], (4, 4), scale=1.0)
    assert result.shape == (4, 4, 3)
    assert np.allclose(result[2, 2], [0.2, 0.5, 0.8], atol=1e-3)
