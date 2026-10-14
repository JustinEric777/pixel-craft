from pathlib import Path

import pytest
from PIL import Image

from scripts.prepare_ui_candidate import prepare_candidate


def test_prepare_ui_candidate_derives_physical_pixels(tmp_path: Path) -> None:
    source = tmp_path / "logical.jpg"
    output = tmp_path / "physical.png"
    Image.new("RGB", (20, 10), (20, 30, 40)).save(source)

    report = prepare_candidate(
        source,
        output,
        logical_viewport=(20, 10),
        device_scale_factor=2,
    )

    with Image.open(output) as image:
        assert image.size == (40, 20)
    assert report["scale_method"] == "lanczos"
    assert len(str(report["source_sha256"])) == 64
    assert len(str(report["output_sha256"])) == 64


def test_prepare_ui_candidate_rejects_wrong_logical_size(tmp_path: Path) -> None:
    source = tmp_path / "logical.jpg"
    Image.new("RGB", (20, 10)).save(source)

    with pytest.raises(ValueError, match="size mismatch"):
        prepare_candidate(
            source,
            tmp_path / "physical.png",
            logical_viewport=(10, 10),
            device_scale_factor=2,
        )
