import json
from pathlib import Path

from scripts.validate_product_scope import run


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_product_scope_rejects_paid_presets_and_visible_tools_without_cases(
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "App.tsx").write_text("export const App = () => null;", encoding="utf-8")
    ui = _write(
        tmp_path / "ui.json",
        {"tool_groups": [{"id": "essentials", "capabilities": ["enhance"]}]},
    )
    presets = _write(
        tmp_path / "presets.json",
        {"presets": [{"id": "paid", "category": "推荐", "paid": True}]},
    )
    cases = _write(tmp_path / "cases.json", {"cases": []})

    report = run(ui, presets, cases, frontend)

    assert report["gate"] == "blocked"
    assert report["issues"]["invalid_presets"] == ["paid"]
    assert report["issues"]["visible_capabilities_without_cases"] == ["enhance"]


def test_product_scope_allows_native_already_purchased_label(tmp_path: Path) -> None:
    ui = tmp_path / "ui.json"
    presets = tmp_path / "presets.json"
    cases = tmp_path / "cases.json"
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    ui.write_text('{"tool_groups": [], "catalog_actions": []}', encoding="utf-8")
    presets.write_text(
        '{"presets": [{"id": "free", "category": "内置"}]}', encoding="utf-8"
    )
    cases.write_text('{"cases": []}', encoding="utf-8")
    (frontend / "PresetBrowser.tsx").write_text('const label = "已购买";', encoding="utf-8")

    report = run(ui, presets, cases, frontend)

    assert report["gate"] == "passed"
