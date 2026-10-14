"""Build the complete versioned queue for Luminar black-box sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.sampling_queue import SamplingQueue, SamplingQueueRecord

RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
WORKFLOWS = ("hdr_merge", "focus_stacking", "panorama_stitching")
LOCALIZED_NAME_PATTERN = re.compile(r'^"Name"\s*=\s*"([^"]+)";', re.MULTILINE)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _rasters(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in RASTER_SUFFIXES
    )


def _overlay_category(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) < 2:
        raise ValueError(f"overlay asset has no collection directory: {path}")
    localization = root / relative.parts[0] / "localizations" / "zh-Hans.strings"
    if not localization.is_file():
        raise FileNotFoundError(
            f"overlay collection localization is missing: {localization}"
        )
    match = LOCALIZED_NAME_PATTERN.search(localization.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"overlay collection has no localized Name: {localization}")
    return match.group(1)


def _active_overlay_rasters(
    root: Path, collection_order: tuple[str, ...]
) -> list[tuple[Path, int]]:
    assets: list[tuple[Path, int]] = []
    for collection_id in collection_order:
        collection_root = root / collection_id
        config_path = collection_root / "config.json"
        payload = _load(config_path)
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"overlay collection has no active items: {config_path}")
        for asset_index, raw_asset_id in enumerate(items):
            asset_id = str(raw_asset_id)
            item_config_path = collection_root / asset_id / "config.json"
            item_config = _load(item_config_path)
            relative_path = str(item_config.get("path") or "")
            asset_path = collection_root / asset_id / relative_path
            if not relative_path or not asset_path.is_file():
                raise FileNotFoundError(
                    f"active overlay asset is missing: {item_config_path}: {relative_path}"
                )
            if asset_path.suffix.lower() not in RASTER_SUFFIXES:
                raise ValueError(f"active overlay asset is not a raster: {asset_path}")
            assets.append((asset_path, asset_index))
    return assets


def _first_case(cases: list[dict[str, Any]], capability_id: str) -> dict[str, Any]:
    try:
        return next(
            item for item in cases if str(item.get("capability_id")) == capability_id
        )
    except StopIteration as exc:
        raise ValueError(f"sampling input case is missing: {capability_id}") from exc


def _input_payload(case: dict[str, Any]) -> dict[str, Any]:
    source = case["input"]
    return {"path": source["path"], "sha256": source["sha256"]}


def _input_by_sha256(
    cases: list[dict[str, Any]], digest: str
) -> dict[str, Any]:
    try:
        case = next(
            item
            for item in cases
            if str(item.get("input", {}).get("sha256") or "") == digest
        )
    except StopIteration as exc:
        raise ValueError(f"canonical sampling input is missing: {digest}") from exc
    return _input_payload(case)


def _registry_asset_id(path: Path, assets_root: Path) -> str:
    return str(path.relative_to(assets_root)).replace("/", "__")


def build_queue(
    *,
    reference_id: str,
    cases_payload: dict[str, Any],
    presets_payload: dict[str, Any],
    recipes: dict[str, Any],
    sky_root: Path,
    overlay_root: Path,
    validation_root: Path,
    viewports: tuple[tuple[int, int], ...],
    ui_states: tuple[str, ...],
    page_order: tuple[str, ...],
    ui_state_pages: dict[str, str],
    ui_matrix_payload: dict[str, Any] | None = None,
    excluded_feature_groups: tuple[str, ...] = (),
    excluded_capabilities: frozenset[str] = frozenset(),
    overlay_collection_order: tuple[str, ...] = (),
    canonical_input_sha256: dict[str, str] | None = None,
    asset_manifest_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eligible_cases = [
        case
        for case in cases_payload.get("cases", [])
        if str(case["capability_id"]) not in excluded_capabilities
    ]
    cases: list[dict[str, Any]] = []
    seen_effects: set[tuple[str, str]] = set()
    for case in eligible_cases:
        source = case.get("input", {})
        source_identity = str(source.get("sha256") or source.get("path") or "")
        key = (str(case["capability_id"]), source_identity)
        if key in seen_effects:
            continue
        seen_effects.add(key)
        cases.append(case)
    effect_capabilities = {str(item["capability_id"]) for item in cases}
    missing_recipes = sorted(effect_capabilities - set(recipes))
    if missing_recipes:
        raise ValueError(f"sampling recipes are missing: {', '.join(missing_recipes)}")
    page_index = {page: index for index, page in enumerate(page_order)}
    dramatic_input = _input_payload(_first_case(cases, "ai_enhance"))
    canonical_inputs = canonical_input_sha256 or {}
    preset_input = _input_by_sha256(cases, canonical_inputs["preset"])
    overlay_input = _input_by_sha256(cases, canonical_inputs["overlay"])
    sky_input = _input_payload(_first_case(cases, "sky_replace"))
    sky_assets = _rasters(sky_root)
    assets_root = sky_root.parents[1]
    manifest_assets: dict[str, Path] = {}
    for item in (asset_manifest_payload or {}).get("records", []):
        asset_id = str(item.get("id") or "")
        relative_path = str(item.get("path") or "")
        asset_path = assets_root / relative_path
        if asset_id and relative_path and asset_path.is_file():
            manifest_assets[asset_id] = asset_path
    sky_assets_by_id = {
        _registry_asset_id(path, assets_root): (index, path)
        for index, path in enumerate(sky_assets)
    }
    records: list[dict[str, Any]] = []
    recipe_order = {capability_id: index for index, capability_id in enumerate(recipes)}
    case_order: Counter[str] = Counter()
    for case in cases:
        capability_id = str(case["capability_id"])
        recipe = recipes[capability_id]
        item_order = case_order[capability_id]
        case_order[capability_id] += 1
        record = {
                "id": f"effect:{case['case_id']}",
                "kind": "effect",
                "case_id": case["case_id"],
                "capability_id": capability_id,
                "input": case["input"],
                "parameters": case.get("parameters", {}),
                "asset_id": case.get("asset_id"),
                "locator_id": recipe.locator_id,
                "strategy": recipe.strategy,
                "status": "pending-reference",
                "page": recipe.workspace,
                "section": "enhancement-tools" if recipe.workspace == "catalog" else "tools",
                "_sort": [
                    page_index[recipe.workspace],
                    2,
                    recipe_order[capability_id],
                    0,
                    item_order,
                ],
            }
        asset_id = case.get("asset_id")
        if asset_id and str(asset_id) in manifest_assets:
            asset_path = manifest_assets[str(asset_id)]
            record.update(
                {
                    "asset_path": str(asset_path.resolve()),
                    "asset_sha256": _sha256(asset_path),
                }
            )
        if capability_id == "sky_replace" and asset_id:
            try:
                asset_index, asset_path = sky_assets_by_id[str(asset_id)]
            except KeyError as exc:
                raise ValueError(
                    f"sky effect asset is absent from local inventory: {asset_id}"
                ) from exc
            record.update(
                {
                    "asset_path": str(asset_path.resolve()),
                    "asset_sha256": _sha256(asset_path),
                    "asset_index": asset_index,
                    "asset_count": len(sky_assets),
                }
            )
        records.append(record)
    for preset_order, preset in enumerate(presets_payload.get("presets", [])):
        records.append(
            {
                "id": f"preset:{preset['id']}",
                "kind": "preset",
                "preset_id": preset["id"],
                "name": preset.get("name"),
                "category": preset.get("category"),
                "localized_name": preset.get("localized_name"),
                "localized_category": preset.get("localized_category"),
                "input": preset_input,
                "strategy": "preset",
                "status": "pending-reference",
                "page": "presets",
                "section": "preset-grid",
                "_sort": [1, 1, preset_order, 0, 0],
            }
        )
    for asset_kind, root, source_input, assets in (
        ("sky", sky_root, sky_input, [(path, None) for path in sky_assets]),
        (
            "overlay",
            overlay_root,
            overlay_input,
            _active_overlay_rasters(overlay_root, overlay_collection_order),
        ),
    ):
        for asset_order, (path, asset_index) in enumerate(assets):
            relative = str(path.relative_to(root))
            if asset_kind == "overlay":
                sort_key = [2, 1, asset_order, 0, 0]
                section = "layer-library"
            else:
                sort_key = [2, 2, recipe_order["sky_replace"], 1, asset_order]
                section = "sky-picker"
            records.append(
                {
                    "id": f"{asset_kind}:{relative}",
                    "kind": asset_kind,
                    "asset_id": relative,
                    "asset_path": str(path.resolve()),
                    "asset_sha256": _sha256(path),
                    **(
                        {
                            "localized_category": _overlay_category(path, root),
                            "asset_index": asset_index,
                        }
                        if asset_kind == "overlay"
                        else {
                            "asset_index": asset_order,
                            "asset_count": len(assets),
                        }
                    ),
                    "input": source_input,
                    "strategy": "asset_picker",
                    "status": "pending-reference",
                    "page": "edit",
                    "section": section,
                    "_sort": sort_key,
                }
            )
    matrix_records = (
        list(ui_matrix_payload.get("records", []))
        if isinstance(ui_matrix_payload, dict)
        else [
            {
                "id": f"workspace:{state}",
                "kind": "workspace-state",
                "workspace": state,
            }
            for state in ui_states
        ]
    )
    matrix_fingerprint = (
        str(ui_matrix_payload.get("matrix_fingerprint") or "")
        if isinstance(ui_matrix_payload, dict)
        else ""
    )
    if isinstance(ui_matrix_payload, dict):
        if ui_matrix_payload.get("reference_id") != reference_id:
            raise ValueError("UI matrix reference does not match sampling reference")
        if len(matrix_fingerprint) != 64:
            raise ValueError("UI matrix fingerprint must be a SHA-256 digest")
        if not matrix_records:
            raise ValueError("UI matrix has no records")
    for viewport_order, (width, height) in enumerate(viewports):
        for state_order, matrix_record in enumerate(matrix_records):
            matrix_state_id = str(matrix_record.get("id") or "")
            workspace = str(matrix_record.get("workspace") or "")
            if not matrix_state_id or not workspace:
                raise ValueError("UI matrix record requires id and workspace")
            page = ui_state_pages.get(workspace, workspace)
            if page not in page_index:
                raise ValueError(
                    f"UI matrix state {matrix_state_id!r} uses unknown page {page!r}"
                )
            records.append(
                {
                    "id": f"ui:{width}x{height}:{matrix_state_id}",
                    "kind": "ui",
                    "viewport": [width, height],
                    "ui_state": matrix_state_id,
                    "matrix_state_id": matrix_state_id,
                    "matrix_fingerprint": matrix_fingerprint,
                    "matrix_kind": matrix_record.get("kind"),
                    "workspace_state": workspace,
                    "capability_id": matrix_record.get("capability_id"),
                    "parameter": matrix_record.get("parameter"),
                    "panel_state": matrix_record.get("state"),
                    "native_tool": matrix_record.get("native_tool"),
                    **(
                        {"input": dramatic_input}
                        if workspace not in {"catalog", "multi-image", "multi-image-complete"}
                        else {}
                    ),
                    "status": "pending-reference",
                    "page": page,
                    "section": "page-state",
                    "_sort": [page_index[page], 0, state_order, viewport_order, 0],
                }
            )
    for workflow_order, workflow in enumerate(WORKFLOWS):
        frames = _rasters(validation_root / workflow)
        records.append(
            {
                "id": f"workflow:{workflow}",
                "kind": "workflow",
                "capability_id": workflow,
                "inputs": [
                    {"path": str(path.resolve()), "sha256": _sha256(path)}
                    for path in frames
                ],
                "strategy": "multi_image",
                "status": "pending-reference" if len(frames) >= 2 else "pending-inputs",
                "page": "catalog",
                "section": "multi-image-tools",
                "_sort": [0, 1, workflow_order, 0, 0],
            }
        )
    records.sort(key=lambda record: tuple(record["_sort"]))
    for scan_order, record in enumerate(records, start=1):
        record["scan_order"] = scan_order
        record.pop("_sort")
    counts = Counter(str(record["kind"]) for record in records)
    status_counts = Counter(str(record["status"]) for record in records)
    queue_records = tuple(SamplingQueueRecord.from_payload(item) for item in records)
    queue_fingerprint = SamplingQueue(reference_id, queue_records).fingerprint
    return {
        "version": "2.0",
        "generated_by": "scripts/build_luminar_sampling_queue.py",
        "reference_id": reference_id,
        "profile": "smoke",
        "queue_revision": queue_fingerprint[:16],
        "queue_fingerprint": queue_fingerprint,
        "dataset_fingerprint": cases_payload.get("dataset_fingerprint"),
        "traversal": {
            "page_order": list(page_order),
            "within_page": "left-to-right, top-to-bottom",
        },
        "scope": {
            "excluded_feature_groups": list(excluded_feature_groups),
            "excluded_capabilities": sorted(excluded_capabilities),
            "effect_case_policy": "one-default-case-per-image-and-capability",
        },
        "record_count": len(records),
        "counts": dict(sorted(counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument(
        "--sampling-config", type=Path, default=ROOT / "configs/luminar_sampling.yaml"
    )
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--presets", type=Path, default=ROOT / "configs/presets/free.json")
    parser.add_argument(
        "--sky-root", type=Path, default=ROOT / "assets/materials/SkyTextures"
    )
    parser.add_argument(
        "--overlay-root",
        type=Path,
        default=ROOT / "assets/materials/OverlayTextures/Free",
    )
    parser.add_argument(
        "--validation-root", type=Path, default=ROOT / "test_data/multi_image"
    )
    parser.add_argument(
        "--assets-manifest",
        type=Path,
        default=ROOT / "assets/manifests/registry.json",
    )
    parser.add_argument(
        "--ui-matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    sampling = load_luminar_sampling_config(args.sampling_config.resolve())
    if sampling.reference_id != profile.id:
        raise RuntimeError(
            f"sampling reference mismatch: {sampling.reference_id!r} != {profile.id!r}"
        )
    report = build_queue(
        reference_id=profile.id,
        cases_payload=_load((args.cases or profile.cases_path).resolve()),
        presets_payload=_load(args.presets.resolve()),
        recipes=sampling.recipes,
        sky_root=args.sky_root.resolve(),
        overlay_root=args.overlay_root.resolve(),
        validation_root=args.validation_root.resolve(),
        viewports=sampling.viewports,
        ui_states=sampling.ui_states,
        page_order=sampling.page_order,
        ui_state_pages=sampling.ui_state_pages,
        ui_matrix_payload=_load(args.ui_matrix.resolve()),
        excluded_feature_groups=sampling.excluded_feature_groups,
        excluded_capabilities=sampling.excluded_capabilities,
        overlay_collection_order=sampling.overlay_collection_order,
        canonical_input_sha256=sampling.canonical_input_sha256,
        asset_manifest_payload=_load(args.assets_manifest.resolve()),
    )
    output = (
        args.output or profile.diagnostics_root / "sampling-queue.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "record_count": report["record_count"],
                "counts": report["counts"],
                "status_counts": report["status_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status_counts"].get("pending-inputs", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
