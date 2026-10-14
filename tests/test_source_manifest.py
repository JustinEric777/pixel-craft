from pathlib import Path

from scripts.build_source_manifest import DEFAULT_ROOTS, build_manifest


def test_default_roots_include_browser_evidence_runners() -> None:
    assert "frontend/scripts" in DEFAULT_ROOTS


def test_source_manifest_is_deterministic_and_detects_changes(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    target = source / "example.py"
    target.write_text("value = 1\n", encoding="utf-8")

    first = build_manifest(tmp_path, ("src",))
    second = build_manifest(tmp_path, ("src",))

    assert first == second
    assert first["status"] == "passed"
    assert first["records"][0]["path"] == "src/example.py"

    target.write_text("value = 2\n", encoding="utf-8")
    changed = build_manifest(tmp_path, ("src",))
    assert changed["source_fingerprint"] != first["source_fingerprint"]


def test_source_manifest_blocks_when_a_requested_root_is_missing(tmp_path: Path) -> None:
    report = build_manifest(tmp_path, ("missing",))

    assert report["status"] == "blocked"
    assert report["missing_roots"] == ["missing"]


def test_source_manifest_accepts_individual_files(tmp_path: Path) -> None:
    package = tmp_path / "package.json"
    package.write_text('{"name":"fixture"}\n', encoding="utf-8")

    report = build_manifest(tmp_path, ("package.json",))

    assert report["status"] == "passed"
    assert report["records"] == [
        {
            "path": "package.json",
            "size": package.stat().st_size,
            "sha256": report["records"][0]["sha256"],
        }
    ]
