from pathlib import Path

from PIL import Image, ImageChops

from scripts.build_multi_image_validation_data import build


def test_validation_builder_creates_distinct_semantic_workflow_inputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (120, 60), (80, 120, 160)).save(source)

    report = build(source, tmp_path / "multi")

    assert set(report["workflows"]) == {
        "hdr_merge",
        "focus_stacking",
        "panorama_stitching",
    }
    assert all(len(items) == 3 for items in report["workflows"].values())
    hdr_paths = [Path(item["path"]) for item in report["workflows"]["hdr_merge"]]
    with Image.open(hdr_paths[0]) as dark, Image.open(hdr_paths[-1]) as bright:
        assert ImageChops.difference(dark, bright).getbbox() is not None
    hdr_exif = []
    for path in hdr_paths:
        with Image.open(path) as image:
            hdr_exif.append(image.getexif())
    assert [float(exif[0x9204]) for exif in hdr_exif] == [-2.0, 0.0, 2.0]
    assert [float(exif[0x829A]) for exif in hdr_exif] == [
        0.001,
        0.004,
        float(1 / 60),
    ]
    assert {exif[0x9003] for exif in hdr_exif} == {"2026:08:20 12:00:00"}
    assert {exif[0x0110] for exif in hdr_exif} == {
        "Multi Image Validation Camera"
    }
    panorama_paths = [
        Path(item["path"])
        for item in report["workflows"]["panorama_stitching"]
    ]
    with Image.open(panorama_paths[0]) as panorama:
        assert panorama.width < 120
