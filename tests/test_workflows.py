import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from api.app import create_app


def _image_bytes(color: tuple[int, int, int], *, marker: int = 0) -> bytes:
    image = Image.new("RGB", (64, 48), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((8 + marker, 8, 30 + marker, 30), fill=(220, 220, 220))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_multi_image_workflows_create_analyze_and_render(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    for kind in ("hdr_merge", "focus_stacking", "panorama_stitching"):
        created = client.post(f"/api/v1/workflows/{kind}")
        assert created.status_code == 200
        workflow_id = created.json()["id"]
        for index, color in enumerate(((25, 40, 60), (90, 70, 45))):
            response = client.post(
                f"/api/v1/workflows/{workflow_id}/frames",
                files={
                    "file": (
                        f"frame-{index}.png",
                        _image_bytes(color, marker=index * 4),
                        "image/png",
                    )
                },
            )
            assert response.status_code == 200
        analysis = client.post(f"/api/v1/workflows/{workflow_id}/analyze")
        assert analysis.status_code == 200
        assert analysis.json()["analysis"]["status"] == "ready"
        preview = client.post(f"/api/v1/workflows/{workflow_id}/preview")
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/")
        exported = client.post(f"/api/v1/workflows/{workflow_id}/export")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("image/")


def test_multi_image_workflow_requires_two_frames(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    workflow_id = client.post("/api/v1/workflows/hdr_merge").json()["id"]
    response = client.post(f"/api/v1/workflows/{workflow_id}/preview")
    assert response.status_code == 409
    assert "at least 2" in response.json()["detail"]


def test_multi_image_workflow_reorders_removes_and_reuses_preview_for_export(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    workflow_id = client.post("/api/v1/workflows/hdr_merge").json()["id"]
    frames = []
    for index, color in enumerate(((20, 30, 40), (80, 90, 100), (140, 150, 160))):
        response = client.post(
            f"/api/v1/workflows/{workflow_id}/frames",
            files={"file": (f"frame-{index}.png", _image_bytes(color), "image/png")},
        )
        frames = response.json()["frames"]

    reordered_ids = [frames[2]["id"], frames[0]["id"], frames[1]["id"]]
    reordered = client.put(
        f"/api/v1/workflows/{workflow_id}/frames/order",
        json={"frame_ids": reordered_ids},
    )
    assert [frame["id"] for frame in reordered.json()["frames"]] == reordered_ids

    removed = client.delete(
        f"/api/v1/workflows/{workflow_id}/frames/{frames[0]['id']}"
    )
    assert [frame["id"] for frame in removed.json()["frames"]] == [
        frames[2]["id"],
        frames[1]["id"],
    ]
    analysis = client.post(f"/api/v1/workflows/{workflow_id}/analyze").json()["analysis"]
    assert analysis["duplicate_frames"] == 0
    assert len(analysis["render_signature"]) == 64

    preview = client.post(f"/api/v1/workflows/{workflow_id}/preview")
    exported = client.post(f"/api/v1/workflows/{workflow_id}/export")
    assert preview.content == exported.content
