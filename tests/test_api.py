import io
import json
import threading
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from api.app import create_app


def test_stale_preview_cannot_overwrite_concurrent_edit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    entered = threading.Event()
    release = threading.Event()
    original_render = app.state.editor.renderer.render

    def delayed_render(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return original_render(*args, **kwargs)

    monkeypatch.setattr(app.state.editor.renderer, "render", delayed_render)
    failures: list[BaseException] = []

    def preview() -> None:
        try:
            app.state.editor.render_preview(project_id)
        except Exception as error:  # noqa: BLE001  # pragma: no cover - asserted below
            failures.append(error)

    worker = threading.Thread(target=preview)
    worker.start()
    assert entered.wait(timeout=5)
    added = app.state.editor.add_edit(
        project_id, "color_adjustments", {"amount": 0.4}, None, True
    )
    assert len(added["project"]["edits"]) == 1
    release.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert failures == []
    assert len(client.get(f"/api/v1/projects/{project_id}").json()["edits"]) == 1


def test_identical_concurrent_previews_share_one_render(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    entered = threading.Event()
    release = threading.Event()
    render_count = 0
    original_render = app.state.editor.renderer.render

    def delayed_render(*args, **kwargs):
        nonlocal render_count
        render_count += 1
        entered.set()
        assert release.wait(timeout=5)
        return original_render(*args, **kwargs)

    monkeypatch.setattr(app.state.editor.renderer, "render", delayed_render)
    failures: list[BaseException] = []

    def preview() -> None:
        try:
            app.state.editor.render_preview(project_id)
        except Exception as error:  # noqa: BLE001  # pragma: no cover - asserted below
            failures.append(error)

    first = threading.Thread(target=preview)
    second = threading.Thread(target=preview)
    first.start()
    assert entered.wait(timeout=5)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert failures == []
    assert render_count == 1
    assert not first.is_alive()
    assert not second.is_alive()


def test_preview_runtime_metadata_never_saves_the_project(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    def unexpected_save(*args, **kwargs):
        raise AssertionError("preview runtime metadata must not save the project aggregate")

    monkeypatch.setattr(app.state.editor.projects, "save", unexpected_save)
    app.state.editor.render_preview(project_id)

    project = app.state.editor.get_project(project_id)
    assert project["metadata"]["last_execution"]["status"] == "ready"


def test_preview_and_export_responses_use_unique_ephemeral_files(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    preview_paths: list[Path] = []
    export_paths: list[Path] = []
    original_preview = app.state.editor.render_preview
    original_export = app.state.editor.export

    def record_preview(project_id, output=None, width=None, operation="preview"):
        if output is not None and operation == "preview":
            preview_paths.append(output)
        return original_preview(project_id, output, width, operation)

    def record_export(project_id, output, **kwargs):
        export_paths.append(output)
        return original_export(project_id, output, **kwargs)

    monkeypatch.setattr(app.state.editor, "render_preview", record_preview)
    assert client.get(f"/api/v1/projects/{project_id}/preview").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/preview").status_code == 200
    monkeypatch.setattr(app.state.editor, "export", record_export)
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 200

    assert len(set(preview_paths)) == 2
    assert len(set(export_paths)) == 2
    assert all(not path.exists() for path in [*preview_paths, *export_paths])


def test_scaled_export_reuses_current_full_preview(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (64, 48), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    render_count = 0
    original_render = app.state.editor.renderer.render

    def count_render(*args, **kwargs):
        nonlocal render_count
        render_count += 1
        return original_render(*args, **kwargs)

    monkeypatch.setattr(app.state.editor.renderer, "render", count_render)
    assert client.get(f"/api/v1/projects/{project_id}/preview").status_code == 200
    exported = client.get(
        f"/api/v1/projects/{project_id}/export", params={"width": 32}
    )

    assert exported.status_code == 200
    assert exported.headers["x-zpixel-export-width"] == "32"
    assert render_count == 1
    assert client.get(f"/api/v1/projects/{project_id}/execution").json()["cache_hit"] is True


def test_upload_edit_preview_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    image = Image.new("RGB", (32, 24), (30, 60, 90))
    source = tmp_path / "source.png"
    image.save(source)
    with source.open("rb") as handle:
        response = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        )
    assert response.status_code == 200
    project_id = response.json()["project_id"]
    project = client.get(f"/api/v1/projects/{project_id}")
    assert project.status_code == 200
    assert project.json()["metadata"]["original_filename"] == "source.png"
    assert project.json()["source"]["width"] == 32
    assert project.json()["source"]["height"] == 24
    response = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "color_adjustments", "parameters": {"amount": 0.4}},
    )
    assert response.status_code == 200
    assert len(response.json()["project"]["edits"]) == 1
    reset = client.post(f"/api/v1/projects/{project_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["edits"] == []
    assert reset.json()["layers"] == []
    restored = client.get(f"/api/v1/projects/{project_id}/preview")
    assert restored.status_code == 200
    assert restored.content == source.read_bytes()
    client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "color_adjustments", "parameters": {"amount": 0.4}},
    )
    preview = client.post(f"/api/v1/projects/{project_id}/preview")
    exported = client.post(f"/api/v1/projects/{project_id}/export")
    assert preview.status_code == 200
    assert exported.status_code == 200
    assert exported.content == preview.content
    assert (
        exported.headers["content-disposition"]
        == 'attachment; filename="source-edited.png"'
    )
    trace = client.get(f"/api/v1/projects/{project_id}/execution").json()
    assert trace["operation"] == "export"
    assert trace["cache_hit"] is True


def test_preview_export_cache_is_invalidated_by_edit_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "color_adjustments", "parameters": {"amount": 0.2}},
    )
    preview = client.post(f"/api/v1/projects/{project_id}/preview").content
    client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "high_key", "parameters": {"amount": 0.4}},
    )

    exported = client.post(f"/api/v1/projects/{project_id}/export")
    trace = client.get(f"/api/v1/projects/{project_id}/execution").json()

    assert exported.status_code == 200
    assert exported.content != preview
    assert not trace.get("cache_hit", False)


def test_export_format_width_profile_and_validation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    exported = client.get(
        f"/api/v1/projects/{project_id}/export",
        params={"format": "jpeg", "width": 16, "profile": "sRGB"},
    )

    assert exported.status_code == 200
    assert exported.headers["content-type"] == "image/jpeg"
    assert exported.headers["content-disposition"] == 'attachment; filename="source-edited.jpg"'
    assert exported.headers["x-zpixel-export-width"] == "16"
    assert exported.headers["x-zpixel-export-height"] == "12"
    assert exported.headers["x-zpixel-export-profile"] == "sRGB"
    assert len(exported.headers["x-zpixel-export-sha256"]) == 64
    with Image.open(io.BytesIO(exported.content)) as image:
        assert image.format == "JPEG"
        assert image.size == (16, 12)
        assert image.info.get("icc_profile")

    assert client.get(
        f"/api/v1/projects/{project_id}/export", params={"format": "webp"}
    ).status_code == 422
    assert client.get(
        f"/api/v1/projects/{project_id}/export", params={"width": 0}
    ).status_code == 422

    renamed = client.get(
        f"/api/v1/projects/{project_id}/export",
        params={"format": "png", "filename": "canonical:export.png"},
    )
    assert renamed.status_code == 200
    assert renamed.headers["content-disposition"] == 'attachment; filename="canonical_export.png"'


def test_catalog_and_preset_actions_are_real_state_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        uploaded = client.post("/api/v1/assets", files={"file": ("source.png", handle, "image/png")})
    assert uploaded.status_code == 200
    project_id = uploaded.json()["project_id"]

    catalog = client.get("/api/v1/catalog")
    assert catalog.status_code == 200
    record = next(item for item in catalog.json()["records"] if item["project_id"] == project_id)
    assert client.get(f"/api/v1/assets/{record['asset_id']}/preview").status_code == 200
    updated = client.patch(
        f"/api/v1/catalog/assets/{record['asset_id']}", json={"favorite": True, "rating": 5}
    )
    assert updated.status_code == 200
    assert updated.json()["record"]["favorite"] is True
    assert updated.json()["record"]["rating"] == 5
    trashed = client.patch(
        f"/api/v1/catalog/assets/{record['asset_id']}", json={"deleted": True}
    )
    assert trashed.status_code == 200
    assert trashed.json()["record"]["deleted_at"]
    restored = client.patch(
        f"/api/v1/catalog/assets/{record['asset_id']}", json={"deleted": False}
    )
    assert restored.status_code == 200
    assert restored.json()["record"]["deleted_at"] is None

    presets = client.get("/api/v1/presets")
    assert presets.status_code == 200
    preset = presets.json()["records"][0]
    assert client.get(f"/api/v1/presets/{preset['id']}/artwork").status_code == 200
    assert client.get(
        f"/api/v1/preset-categories/{preset['category']}/artwork"
    ).status_code == 200
    assert client.get(
        f"/api/v1/projects/{project_id}/presets/{preset['id']}/preview"
    ).status_code == 200
    applied = client.post(f"/api/v1/projects/{project_id}/presets/{preset['id']}/apply")
    assert applied.status_code == 200
    assert applied.json()["project"]["metadata"]["last_preset"]["id"] == preset["id"]
    assert len(applied.json()["project"]["edits"]) == len(preset["edit_graph"])


def test_folder_import_persists_native_catalog_collection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "folder-photo.png"
    Image.new("RGB", (24, 18), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        uploaded = client.post(
            "/api/v1/assets",
            params={"collection": "validation-folder"},
            files={"file": (source.name, handle, "image/png")},
        )

    assert uploaded.status_code == 200
    [record] = client.get("/api/v1/catalog").json()["records"]
    assert record["collection"] == "validation-folder"
    assert Path(record["path"]).is_file()


def test_imports_local_luminar_preset_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    template = {
        "name": "Local Landscape",
        "uuid": "local-landscape-id",
        "layers_array": [{
            "alive": True,
            "curr_edit_inedx": 0,
            "edits_array": [{
                "enabled": True,
                "tool_name": "Develop",
                "effects_array": [{
                    "id": "develop",
                    "params_array": [{"name": "Amount", "value": "25", "default": "0"}],
                }],
            }],
        }],
    }
    icon = io.BytesIO()
    Image.new("RGB", (120, 80), (40, 80, 120)).save(icon, format="JPEG")

    imported = client.post("/api/v1/presets/import", files=[
        ("files", ("template.lmps", json.dumps(template).encode(), "application/json")),
        ("files", ("icon.jpg", icon.getvalue(), "image/jpeg")),
    ])

    assert imported.status_code == 200
    preset = imported.json()["preset"]
    assert preset["id"] == "local_local-landscape-id"
    assert preset["category"] == "本地预设"
    assert client.get(f"/api/v1/presets/{preset['id']}/artwork").status_code == 200
    assert any(item["id"] == preset["id"] for item in client.get("/api/v1/presets").json()["records"])


def test_root_status() -> None:
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "zpixel_edit"


def test_public_configuration_uses_luminar_tool_group_order() -> None:
    response = TestClient(create_app()).get("/api/v1/configuration")
    assert response.status_code == 200
    groups = response.json()["tool_groups"]
    assert [group["id"] for group in groups] == [
        "common",
        "extensions",
        "essentials",
        "landscape",
        "creative",
        "portrait",
        "pro",
    ]
    configured = [capability for group in groups for capability in group["capabilities"]]
    assert len(configured) == len(set(configured))


def test_catalog_endpoints_are_composition_root_backed() -> None:
    client = TestClient(create_app())
    models = client.get("/api/v1/models")
    capabilities = client.get("/api/v1/capabilities")
    assert models.status_code == 200
    assert len(models.json()["models"]) == 22
    assert capabilities.status_code == 200
    assert len(capabilities.json()["capabilities"]) == 58


def test_upload_rejects_unsupported_media_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/assets", files={"file": ("source.bmp", b"not-an-image", "image/bmp")}
    )
    assert response.status_code == 415


def test_capabilities_endpoint() -> None:
    response = TestClient(create_app()).get("/api/v1/capabilities")
    assert response.status_code == 200
    assert any(item["id"] == "sky_replace" for item in response.json()["capabilities"])
    sky = next(item for item in response.json()["capabilities"] if item["id"] == "sky_replace")
    assert "implementation_status" not in sky
    assert sky["readiness"]["status"] == "runtime-ready"
    assert sky["readiness"]["missing_or_blocked_models"] == []


def test_asset_catalog_and_asset_id_effect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_ASSET_ROOT", str(Path("assets")))
    client = TestClient(create_app())
    catalog = client.get("/api/v1/assets/catalog", params={"family": "sky"})
    assert catalog.status_code == 200
    assert catalog.json()["count"] > 0
    asset_id = catalog.json()["records"][0]["id"]
    image = Image.new("RGB", (32, 24), (30, 60, 90))
    source = tmp_path / "source.png"
    image.save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={
            "effect": "sky_replace",
            "parameters": {"asset_id": asset_id, "texture_opacity": 0.2},
        },
    )
    assert response.status_code == 200
    assert response.json()["project"]["edits"][0]["effect"] == "sky_replace"
    preview = client.get(f"/api/v1/assets/{asset_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/")


def test_asset_catalog_excludes_non_raster_metadata() -> None:
    client = TestClient(create_app())
    records = client.get("/api/v1/assets/catalog", params={"family": "sky"}).json()["records"]
    assert records
    assert all(Path(record["path"]).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"} for record in records)


def test_non_raster_asset_preview_returns_not_found() -> None:
    client = TestClient(create_app())
    response = client.get(
        "/api/v1/assets/materials__SkyTextures__Blue%20Sky__config.json/preview"
    )
    assert response.status_code == 404


def test_analyze_reports_model_and_artifact_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    response = client.post(f"/api/v1/projects/{project_id}/analyze")
    assert response.status_code == 200
    assert response.json()["metadata"]["onnx_analysis"]["image_embedding"]["status"] == "ready"
    assert response.json()["metadata"]["onnx_analysis"]["semantic_mask"]["status"] == "ready"
    sky_mask = response.json()["metadata"]["onnx_analysis"]["sky_mask"]
    assert sky_mask["status"] == "ready"
    assert sky_mask["model"] == "improved_sky_segmentator_v462_i8_onnx"
    assert response.json()["metadata"]["onnx_analysis"]["depth_map"]["status"] == "ready"


def test_analyze_can_request_canonical_bokeh_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/analyze",
        params={"models": "mobilenet_exp78_portrait_BOKEH12"},
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["onnx_analysis"]["bokeh_mask"]["status"] == "ready"


def test_analyze_reuses_content_addressed_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    first = client.post(f"/api/v1/projects/{project_id}/analyze")
    assert first.status_code == 200
    assert first.json()["metadata"]["onnx_analysis"]["image_embedding"]["cache_hit"] is False
    second = client.post(f"/api/v1/projects/{project_id}/analyze")
    assert second.status_code == 200
    assert second.json()["metadata"]["onnx_analysis"]["image_embedding"]["cache_hit"] is True
    artifacts = client.get(f"/api/v1/projects/{project_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["cache"]["records"] >= 3
    semantic = second.json()["metadata"]["onnx_analysis"]["semantic_mask"]
    assert semantic["artifact_path"].endswith(".npy")


def test_analysis_job_is_idempotent_checkpointed_and_complete(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    app = create_app()
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]

    payload = {"models": ["SemanticSearchImage"], "idempotency_key": "one"}
    first = client.post(
        f"/api/v1/projects/{project_id}/analysis-jobs", json=payload
    )
    second = client.post(
        f"/api/v1/projects/{project_id}/analysis-jobs", json=payload
    )
    assert first.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    latest = client.get(
        f"/api/v1/projects/{project_id}/analysis-jobs/latest"
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == first.json()["id"]

    completed = app.state.jobs.run_next("test-worker")
    assert completed["status"] == "succeeded"
    result = client.get(
        f"/api/v1/analysis-jobs/{first.json()['id']}/result"
    ).json()
    assert result["complete"] is True
    assert result["models"]["SemanticSearchImage"]["image_embedding"]["status"] == "ready"
    assert client.get(f"/api/v1/projects/{project_id}").json()["metadata"][
        "analysis_job_id"
    ] == first.json()["id"]


def test_sky_replacement_runs_with_dedicated_onnx_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_ASSET_ROOT", str(Path("assets")))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    client = TestClient(create_app())
    source = Image.new("RGB", (128, 96), (42, 112, 180))
    for y in range(48, 96):
        for x in range(128):
            source.putpixel((x, y), (35, 48, 42))
    source_path = tmp_path / "landscape.png"
    source.save(source_path)
    with source_path.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("landscape.png", handle, "image/png")}
        ).json()["project_id"]
    asset_id = client.get("/api/v1/assets/catalog", params={"family": "sky"}).json()["records"][0][
        "id"
    ]
    added = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "sky_replace", "parameters": {"asset_id": asset_id, "amount": 1.0}},
    )
    assert added.status_code == 200
    assert len(client.get(f"/api/v1/projects/{project_id}").json()["edits"]) == 1
    assert client.post(f"/api/v1/projects/{project_id}/preview").status_code == 200


def test_exact_mode_blocks_effect_without_passed_parity_or_creating_preview(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_PARITY_MODE", "exact")
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    blocked = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "ai_enhance", "parameters": {"amount": 0.4}},
    )
    assert blocked.status_code == 503
    assert "exact mode blocked" in blocked.json()["detail"]
    assert "Luminar parity has not passed for ai_enhance" in blocked.json()["detail"]
    assert client.get(f"/api/v1/projects/{project_id}").json()["edits"] == []
    assert not (tmp_path / "data/workspace/outputs" / f"{project_id}-preview.png").exists()


def test_exact_mode_blocks_sky_until_black_box_parity_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_ASSET_ROOT", str(Path("assets")))
    monkeypatch.setenv("ZPIXEL_PARITY_MODE", "exact")
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    asset_id = client.get("/api/v1/assets/catalog", params={"family": "sky"}).json()[
        "records"
    ][0]["id"]
    blocked = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "sky_replace", "parameters": {"asset_id": asset_id, "amount": 1.0}},
    )
    assert blocked.status_code == 503
    assert "exact mode blocked" in blocked.json()["detail"]
    assert "sky_replace" in blocked.json()["detail"]


def test_sky_replace_requires_asset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    response = client.post(f"/api/v1/projects/{project_id}/edits", json={"effect": "sky_replace"})
    assert response.status_code == 400


def test_sky_replace_reuses_single_active_tool_node(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_ASSET_ROOT", str(Path("assets")))
    app = create_app()
    app.state.editor.model_service.assert_effects_ready = lambda _: None
    client = TestClient(app)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    asset_id = client.get("/api/v1/assets/catalog", params={"family": "sky"}).json()["records"][0]["id"]
    first = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "sky_replace", "parameters": {"asset_id": asset_id, "amount": 0.2}},
    ).json()
    second = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "sky_replace", "parameters": {"asset_id": asset_id, "amount": 0.8}},
    ).json()
    assert first["edit"]["id"] == second["edit"]["id"]
    assert len(second["project"]["edits"]) == 1
    assert second["project"]["edits"][0]["parameters"]["amount"] == 0.8


def test_edit_contract_and_history_endpoints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    invalid = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "ai_enhance", "parameters": {"amount": 4}},
    )
    assert invalid.status_code == 422
    added = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "color_adjustments", "parameters": {"amount": 0.2}},
    )
    assert added.status_code == 200
    edit_id = added.json()["edit"]["id"]
    updated = client.patch(
        f"/api/v1/projects/{project_id}/edits/{edit_id}",
        json={"effect": "details", "parameters": {"amount": 0.5}},
    )
    assert updated.status_code == 200
    assert updated.json()["edits"][0]["effect"] == "details"
    undone = client.post(f"/api/v1/projects/{project_id}/undo").json()["edits"]
    assert undone[0]["effect"] == "color_adjustments"
    redone = client.post(f"/api/v1/projects/{project_id}/redo").json()["edits"]
    assert redone[0]["effect"] == "details"


def test_multi_input_effects_are_explicitly_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    for effect in ("hdr_merge", "focus_stacking", "panorama_stitching"):
        assert (
            client.post(f"/api/v1/projects/{project_id}/edits", json={"effect": effect}).status_code
            == 409
        )


def test_unavailable_super_resolution_fails_closed_without_compatibility_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ZPIXEL_MODEL_ROOT", str(Path("models")))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (128, 96), (30, 60, 90)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/edits",
        json={"effect": "super_resolution", "parameters": {"amount": 0.8, "scale": 2}},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "model readiness blocked: super_resolution requires UpscaleX2HGGT"
    )
    project = client.get(f"/api/v1/projects/{project_id}")
    assert project.status_code == 200
    assert project.json()["edits"] == []


def test_project_image_layers_are_real_state_and_render_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    layer = tmp_path / "layer.png"
    Image.new("RGB", (48, 32), (20, 30, 40)).save(source)
    Image.new("RGB", (48, 32), (220, 120, 30)).save(layer)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    before = client.get(f"/api/v1/projects/{project_id}/preview").content
    with layer.open("rb") as handle:
        added = client.post(
            f"/api/v1/projects/{project_id}/layers/uploads",
            files={"file": ("layer.png", handle, "image/png")},
        )
    assert added.status_code == 200
    layer_record = added.json()["project"]["layers"][0]
    assert client.get(
        f"/api/v1/projects/{project_id}/layers/{layer_record['id']}/preview"
    ).status_code == 200
    after = client.get(f"/api/v1/projects/{project_id}/preview").content
    assert after != before
    deleted = client.delete(f"/api/v1/projects/{project_id}/layers/{layer_record['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["project"]["layers"] == []


def test_layer_mask_upload_update_undo_and_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    layer = tmp_path / "layer.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (48, 32), (20, 30, 40)).save(source)
    Image.new("RGB", (48, 32), (220, 120, 30)).save(layer)
    mask_image = Image.new("L", (48, 32), 0)
    mask_image.paste(255, (0, 0, 24, 32))
    mask_image.save(mask)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    with layer.open("rb") as handle:
        layer_id = client.post(
            f"/api/v1/projects/{project_id}/layers/uploads",
            files={"file": ("layer.png", handle, "image/png")},
        ).json()["project"]["layers"][0]["id"]
    with mask.open("rb") as handle:
        response = client.post(
            f"/api/v1/projects/{project_id}/masks/uploads",
            params={"owner_type": "layer", "owner_id": layer_id},
            files={"file": ("mask.png", handle, "image/png")},
        )
    assert response.status_code == 200
    project = response.json()["project"]
    mask_id = project["layers"][0]["mask_artifact"]
    assert project["masks"][mask_id]["sha256"]
    assert client.get(
        f"/api/v1/projects/{project_id}/masks/{mask_id}/preview"
    ).status_code == 200

    updated = client.patch(
        f"/api/v1/projects/{project_id}/masks/{mask_id}",
        json={"inverted": True, "density": 0.5, "feather": 2},
    )
    assert updated.status_code == 200
    assert updated.json()["project"]["masks"][mask_id]["density"] == 0.5
    undone = client.post(f"/api/v1/projects/{project_id}/undo").json()
    assert undone["masks"][mask_id]["inverted"] is False
    deleted = client.delete(f"/api/v1/projects/{project_id}/masks/{mask_id}")
    assert deleted.status_code == 200
    assert deleted.json()["project"]["masks"] == {}
    assert deleted.json()["project"]["layers"][0]["mask_artifact"] is None


def test_layer_mask_brush_persists_parameters_and_history(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    layer = tmp_path / "layer.png"
    Image.new("RGB", (96, 64), (20, 30, 40)).save(source)
    Image.new("RGB", (96, 64), (220, 120, 30)).save(layer)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    with layer.open("rb") as handle:
        layer_id = client.post(
            f"/api/v1/projects/{project_id}/layers/uploads",
            files={"file": ("layer.png", handle, "image/png")},
        ).json()["project"]["layers"][0]["id"]

    painted = client.post(
        f"/api/v1/projects/{project_id}/masks/brush",
        json={
            "owner_type": "layer",
            "owner_id": layer_id,
            "strokes": [{"points": [[0.2, 0.3], [0.5, 0.5], [0.8, 0.6]]}],
            "size": 80,
            "softness": 24,
            "strength": 70,
        },
    )
    assert painted.status_code == 200
    project = painted.json()["project"]
    mask_id = project["layers"][0]["mask_artifact"]
    mask = project["masks"][mask_id]
    assert mask["source"] == "brush"
    assert (mask["brush_size"], mask["brush_softness"], mask["brush_strength"]) == (80, 24, 70)
    assert client.get(f"/api/v1/projects/{project_id}/masks/{mask_id}/preview").status_code == 200
    undone = client.post(f"/api/v1/projects/{project_id}/undo").json()
    assert undone["layers"][0]["mask_artifact"] is None
    redone = client.post(f"/api/v1/projects/{project_id}/redo").json()
    assert redone["layers"][0]["mask_artifact"] == mask_id


def test_layer_material_catalog_and_screen_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    response = client.get("/api/v1/layer-materials")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 38
    assert [(group["label"], group["count"]) for group in payload["groups"]] == [
        ("星尘散景", 12),
        ("漏光", 12),
        ("烟火", 8),
        ("耀斑", 6),
    ]
    assert all(
        item["blend_mode"] == "screen"
        for group in payload["groups"]
        for item in group["items"]
    )


def test_builtin_layer_material_can_be_added_and_updated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ZPIXEL_DATA_ROOT", str(tmp_path / "data"))
    client = TestClient(create_app())
    source = tmp_path / "source.png"
    Image.new("RGB", (80, 60), (20, 30, 40)).save(source)
    with source.open("rb") as handle:
        project_id = client.post(
            "/api/v1/assets", files={"file": ("source.png", handle, "image/png")}
        ).json()["project_id"]
    material = client.get("/api/v1/layer-materials").json()["groups"][0]["items"][0]
    added = client.post(
        f"/api/v1/projects/{project_id}/layers/assets",
        json={"material_id": material["id"]},
    )
    assert added.status_code == 200
    layer = added.json()["project"]["layers"][0]
    assert layer["source_kind"] == "library"
    assert layer["blend_mode"] == "screen"
    updated = client.patch(
        f"/api/v1/projects/{project_id}/layers/{layer['id']}",
        json={"opacity": 0.25, "visible": False},
    )
    assert updated.status_code == 200
    assert updated.json()["project"]["layers"][0]["opacity"] == 0.25
    assert updated.json()["project"]["layers"][0]["visible"] is False
    undone = client.post(f"/api/v1/projects/{project_id}/undo").json()["layers"][0]
    assert undone["opacity"] == layer["opacity"]
    assert undone["visible"] is True
    redone = client.post(f"/api/v1/projects/{project_id}/redo").json()["layers"][0]
    assert redone["opacity"] == 0.25
    assert redone["visible"] is False
