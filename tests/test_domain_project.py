from pathlib import Path

import pytest

from core.errors import CapabilityConflictError, EditNotFoundError
from core.project.entities import EditNode, ImageRef, LayerRef, MaskRef, ProjectState
from core.project.serialization import (
    load_project,
    project_from_dict,
    project_to_dict,
    save_project,
)


def _project() -> ProjectState:
    return ProjectState(source=ImageRef(Path("source.png")))


def test_project_aggregate_keeps_edit_history_invariants() -> None:
    project = _project()
    first = EditNode("first", "ai_enhance")
    second = EditNode("second", "structure_ai")

    project.append_edit(first)
    project.append_edit(second)
    project.undo()
    project.redo()
    project.reorder_edits(["second", "first"])

    assert [edit.id for edit in project.edits] == ["second", "first"]
    assert project.metadata["redo_stack"] == []


def test_project_aggregate_rejects_invalid_reorder() -> None:
    project = _project()
    project.append_edit(EditNode("first", "ai_enhance"))

    with pytest.raises(CapabilityConflictError):
        project.reorder_edits([])


def test_project_aggregate_rejects_unknown_edit_update() -> None:
    project = _project()

    with pytest.raises(EditNotFoundError):
        project.replace_edit(EditNode("missing", "ai_enhance"))


def test_project_history_restores_layer_mutations() -> None:
    project = _project()
    first = LayerRef("first", "asset-1", Path("one.png"), "One")
    second = LayerRef("second", "asset-2", Path("two.png"), "Two")

    project.append_layer(first)
    project.append_layer(second)
    project.replace_layer(LayerRef(**{**second.__dict__, "offset_x": 0.25}))
    project.reorder_layers(["second", "first"])
    project.remove_layer("first")
    project.undo()
    project.undo()

    assert [layer.id for layer in project.layers] == ["first", "second"]
    assert project.layers[1].offset_x == 0.25
    project.redo()
    assert [layer.id for layer in project.layers] == ["second", "first"]


def test_append_edits_is_one_history_action() -> None:
    project = _project()
    project.append_edits([EditNode("first", "one"), EditNode("second", "two")])

    project.undo()

    assert project.edits == []


def test_mask_attachment_is_serialized_and_restored_with_history() -> None:
    project = _project()
    project.append_layer(LayerRef("layer", "asset", Path("layer.png"), "Layer"))
    mask = MaskRef(
        "mask",
        Path("mask.png"),
        "layer",
        "layer",
        20,
        10,
        density=0.75,
        feather=2.0,
        sha256="abc",
    )

    project.attach_mask(mask)
    restored = project_from_dict(project_to_dict(project))

    assert restored.layers[0].mask_artifact == "mask"
    assert restored.masks["mask"].density == 0.75
    project.undo()
    assert project.layers[0].mask_artifact is None
    assert project.masks == {}


def test_mask_lifecycle_does_not_leave_orphans() -> None:
    project = _project()
    layer = LayerRef("layer", "asset", Path("layer.png"), "Layer")
    project.append_layer(layer)
    first = MaskRef("mask-1", Path("mask-1.png"), "layer", layer.id, 20, 10)
    second = MaskRef("mask-2", Path("mask-2.png"), "layer", layer.id, 20, 10)

    project.attach_mask(first)
    project.attach_mask(second)

    assert project.layers[0].mask_artifact == second.id
    assert set(project.masks) == {second.id}

    project.remove_layer(layer.id)
    assert project.masks == {}
    project.undo()
    assert project.layers[0].mask_artifact == second.id
    assert set(project.masks) == {second.id}

    project.reset_to_original()
    assert project.layers == []
    assert project.masks == {}


def test_project_save_publishes_complete_json_with_atomic_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "project.json"
    original = _project()
    original.metadata["version"] = 1
    save_project(original, target)
    updated = _project()
    updated.metadata["version"] = 2
    real_replace = Path.replace
    replacements: list[tuple[Path, Path]] = []

    def inspect_replace(source: Path, destination: Path) -> Path:
        assert source != target
        assert load_project(source).metadata["version"] == 2
        assert load_project(target).metadata["version"] == 1
        replacements.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(Path, "replace", inspect_replace)

    save_project(updated, target)

    assert len(replacements) == 1
    assert replacements[0][1] == target
    assert load_project(target).metadata["version"] == 2
    assert list(tmp_path.glob("*.tmp")) == []
