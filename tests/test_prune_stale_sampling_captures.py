from pathlib import Path

from scripts.prune_stale_sampling_captures import apply_plan, build_plan


def test_prune_plan_keeps_active_final_evidence_and_removes_transients(
    tmp_path: Path,
) -> None:
    capture_root = tmp_path / "captures"
    active_id = "active"
    stale_id = "stale"
    for collection in ("luminar_outputs", "luminar_ui"):
        (capture_root / collection / active_id).mkdir(parents=True)
        stale = capture_root / collection / stale_id
        stale.mkdir(parents=True)
        (stale / "image.png").write_bytes(b"stale")
    for collection, suffix in {
        "metadata": ".json",
        "state": ".json",
        "logs": ".jsonl",
    }.items():
        root = capture_root / collection
        root.mkdir(parents=True)
        (root / f"{active_id}{suffix}").write_text("active", encoding="utf-8")
        (root / f"{stale_id}{suffix}").write_text("stale", encoding="utf-8")
    staging = capture_root / "staging" / active_id
    staging.mkdir(parents=True)
    (staging / "stable-000.png").write_bytes(b"transient")

    plan = build_plan(capture_root, {active_id})

    assert len(plan["stale_paths"]) == 5
    assert plan["transient_paths"] == [str(staging.resolve())]
    assert plan["reclaimable_bytes"] > 0

    apply_plan(capture_root, plan)

    assert (capture_root / "luminar_outputs" / active_id).is_dir()
    assert (capture_root / "metadata" / f"{active_id}.json").is_file()
    assert not (capture_root / "luminar_outputs" / stale_id).exists()
    assert not staging.exists()
