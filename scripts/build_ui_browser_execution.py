"""Publish current-build Browser screenshots as fail-closed UI evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.validate_ui_execution_evidence import frontend_build_hash


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_execution(
    *,
    reference_manifest: Path,
    ui_matrix: Path,
    fixture_manifest: Path,
    candidate_root: Path,
    source_capture_root: Path,
    diagnostics_root: Path,
    frontend_root: Path,
    browser: str,
    browser_version: str,
    capture_engine: str,
    locale: str,
    timezone: str,
    logical_viewport: tuple[int, int],
    device_scale_factor: float,
    region_manifest: Path | None = None,
    allow_incomplete: bool = False,
) -> dict[str, object]:
    manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
    matrix = json.loads(ui_matrix.read_text(encoding="utf-8"))
    fixture = json.loads(fixture_manifest.read_text(encoding="utf-8"))
    if matrix.get("reference_id") != manifest.get("reference_id"):
        raise ValueError("UI matrix and Native reference manifest use different references")
    matrix_fingerprint = str(matrix.get("matrix_fingerprint") or "")
    if len(matrix_fingerprint) != 64:
        raise ValueError("UI matrix fingerprint must be a SHA-256 digest")
    if manifest.get("matrix_fingerprint") != matrix_fingerprint:
        raise ValueError("Native UI manifest does not bind the current UI matrix")
    required_fixture_fields = {
        "collection",
        "expected_count",
        "catalog_count",
        "unique_source_hash_count",
        "fixture_fingerprint",
        "records",
    }
    if not isinstance(fixture, dict) or not required_fixture_fields <= set(fixture):
        raise ValueError(f"UI fixture manifest is incomplete: {fixture_manifest}")
    if (
        fixture["expected_count"] != fixture["catalog_count"]
        or fixture["catalog_count"] != fixture["unique_source_hash_count"]
    ):
        raise ValueError(f"UI fixture manifest is not a unique complete catalog: {fixture_manifest}")
    fixture_records = fixture["records"]
    if not isinstance(fixture_records, list):
        raise TypeError("UI fixture records must be a list")
    fixture_sources = {
        str(record.get("filename")): str(record.get("source_sha256"))
        for record in fixture_records
        if isinstance(record, dict)
    }
    fixture_fingerprint = str(fixture["fixture_fingerprint"])
    if len(fixture_fingerprint) != 64:
        raise ValueError("UI fixture fingerprint must be a SHA-256 digest")
    records: list[dict[str, object]] = []
    missing_records: list[dict[str, object]] = []
    reference_records = {
        str(record.get("matrix_state_id")): record
        for record in manifest.get("records", [])
        if isinstance(record, dict) and record.get("matrix_state_id")
    }
    for matrix_record in matrix.get("records", []):
        state_id = str(matrix_record.get("id") or "")
        reference = reference_records.get(state_id)
        if reference is None:
            if allow_incomplete:
                missing_records.append(
                    {
                        "viewport": None,
                        "matrix_state_id": state_id,
                        "reason": "missing-native-reference",
                    }
                )
                continue
            raise ValueError(f"native UI reference is missing: {state_id}")
        if reference.get("status") != "verified":
            if allow_incomplete:
                missing_records.append(
                    {
                        "viewport": (
                            f"{reference['viewport'][0]}x{reference['viewport'][1]}"
                            if isinstance(reference.get("viewport"), list)
                            and len(reference["viewport"]) == 2
                            else None
                        ),
                        "matrix_state_id": state_id,
                        "reason": "native-reference-not-verified",
                        "native_issues": reference.get("issues", []),
                    }
                )
                continue
            raise ValueError(
                f"native UI reference is not verified: {reference.get('matrix_state_id')}"
            )
        width, height = (int(value) for value in reference["viewport"])
        fixture_id = str(reference["fixture_id"])
        fixture_hash = str(reference["fixture_hash"])
        if fixture_id.startswith("single-image:"):
            filename = fixture_id.split(":", 1)[1]
            if fixture_sources.get(filename) != fixture_hash:
                raise ValueError(
                    f"UI fixture does not contain the Native single-image source: {fixture_id}"
                )
        elif fixture_id.startswith("catalog:"):
            collection = fixture_id.split(":", 1)[1]
            if fixture.get("collection") != collection:
                raise ValueError(
                    f"UI fixture collection mismatch: {fixture.get('collection')} != {collection}"
                )
        viewport = f"{width}x{height}"
        screenshot = (
            candidate_root / viewport / f"{reference['matrix_state_id']}.png"
        ).resolve()
        if not screenshot.is_file():
            if allow_incomplete:
                missing_records.append(
                    {
                        "viewport": viewport,
                        "matrix_state_id": reference["matrix_state_id"],
                        "reason": "missing-ui-candidate",
                    }
                )
                continue
            raise FileNotFoundError(f"UI candidate is missing: {screenshot}")
        with Image.open(screenshot) as image:
            if image.size != (width, height):
                raise ValueError(
                    f"UI candidate size mismatch: {screenshot}: {image.size} != {(width, height)}"
                )
        source_capture = (
            source_capture_root / viewport / f"{reference['matrix_state_id']}.png"
        ).resolve()
        if not source_capture.is_file():
            raise FileNotFoundError(f"native DPR UI capture is missing: {source_capture}")
        with Image.open(source_capture) as source_image, Image.open(screenshot) as candidate_image:
            if source_image.size != (width, height):
                raise ValueError(
                    f"native DPR UI capture size mismatch: {source_capture}: "
                    f"{source_image.size} != {(width, height)}"
                )
            if ImageChops.difference(
                source_image.convert("RGB"), candidate_image.convert("RGB")
            ).getbbox():
                raise ValueError(f"UI candidate differs from native DPR capture: {screenshot}")
        dom_snapshot = (
            source_capture_root / viewport / f"{reference['matrix_state_id']}.dom.json"
        ).resolve()
        accessibility_tree = (
            source_capture_root / viewport / f"{reference['matrix_state_id']}.ax.json"
        ).resolve()
        for label, artifact in (
            ("DOM snapshot", dom_snapshot),
            ("Browser accessibility tree", accessibility_tree),
        ):
            if not artifact.is_file():
                raise FileNotFoundError(f"{label} is missing: {artifact}")
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            if payload in ({}, [], None):
                raise ValueError(f"{label} is empty: {artifact}")
        records.append(
            {
                "viewport": viewport,
                "matrix_state_id": reference["matrix_state_id"],
                "fixture_id": fixture_id,
                "fixture_hash": fixture_hash,
                "actual_fixture_fingerprint": fixture_fingerprint,
                "screenshot": screenshot.relative_to(diagnostics_root).as_posix(),
                "screenshot_sha256": sha256_file(screenshot),
                "source_capture": source_capture.relative_to(diagnostics_root).as_posix(),
                "source_capture_sha256": sha256_file(source_capture),
                "dom_snapshot": dom_snapshot.relative_to(diagnostics_root).as_posix(),
                "dom_snapshot_sha256": sha256_file(dom_snapshot),
                "accessibility_tree": accessibility_tree.relative_to(
                    diagnostics_root
                ).as_posix(),
                "accessibility_tree_sha256": sha256_file(accessibility_tree),
                "capture_method": "native-dpr2",
            }
        )
    logical_width, logical_height = logical_viewport
    expected_physical = (
        round(logical_width * device_scale_factor),
        round(logical_height * device_scale_factor),
    )
    viewports = [f"{expected_physical[0]}x{expected_physical[1]}"]
    actual_physical = {
        tuple(int(value) for value in viewport.split("x", 1)) for viewport in viewports
    }
    if actual_physical != {expected_physical}:
        raise ValueError(
            "UI viewport contract mismatch: "
            f"logical={logical_viewport}, dpr={device_scale_factor}, "
            f"physical={sorted(actual_physical)}"
        )
    payload: dict[str, object] = {
        "version": "2.0",
        "reference_id": manifest["reference_id"],
        "matrix_fingerprint": matrix_fingerprint,
        "fixture": {
            "manifest": fixture_manifest.resolve().relative_to(
                diagnostics_root.resolve()
            ).as_posix(),
            "manifest_sha256": sha256_file(fixture_manifest),
            "fixture_fingerprint": fixture_fingerprint,
            "collection": fixture["collection"],
            "expected_count": fixture["expected_count"],
            "catalog_count": fixture["catalog_count"],
            "unique_source_hash_count": fixture["unique_source_hash_count"],
        },
        "environment": {
            "browser": browser,
            "browser_version": browser_version,
            "capture_engine": capture_engine,
            "logical_viewport": [logical_width, logical_height],
            "physical_viewport": viewports,
            "device_scale_factor": device_scale_factor,
            "locale": locale,
            "timezone": timezone,
            "motion": "reduce",
            "build_hash": frontend_build_hash(frontend_root),
        },
        "records": records,
    }
    if region_manifest is not None:
        resolved_regions = region_manifest.resolve()
        if not resolved_regions.is_file():
            raise FileNotFoundError(f"UI region manifest is missing: {resolved_regions}")
        payload["regions"] = {
            "manifest": resolved_regions.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha256_file(resolved_regions),
        }
    if missing_records:
        payload["gate"] = "blocked"
        payload["missing_records"] = missing_records
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs/parity/core-ui-state-matrix.json",
    )
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--source-captures", type=Path)
    parser.add_argument("--frontend-root", type=Path, default=ROOT / "frontend")
    parser.add_argument("--regions", type=Path, default=ROOT / "configs/parity/ui-regions.json")
    parser.add_argument("--browser", default="Codex In-app Browser")
    parser.add_argument("--browser-version", required=True)
    parser.add_argument("--capture-engine", default="Chrome Headless CDP")
    parser.add_argument("--locale", default="zh-Hans")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--logical-width", type=int, default=1440)
    parser.add_argument("--logical-height", type=int, default=900)
    parser.add_argument("--device-scale-factor", type=float, default=2.0)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Publish available records with a blocked gate when candidates are missing.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    diagnostics_root = profile.diagnostics_root.resolve()
    payload = build_execution(
        reference_manifest=(args.reference_manifest or profile.ui_reference_root / "reference-manifest.json").resolve(),
        ui_matrix=args.matrix.resolve(),
        fixture_manifest=args.fixture_manifest.resolve(),
        candidate_root=(args.candidates or diagnostics_root / "ui-candidates").resolve(),
        source_capture_root=(
            args.source_captures or diagnostics_root / "ui-capture-raw"
        ).resolve(),
        diagnostics_root=diagnostics_root,
        frontend_root=args.frontend_root.resolve(),
        browser=args.browser,
        browser_version=args.browser_version,
        capture_engine=args.capture_engine,
        locale=args.locale,
        timezone=args.timezone,
        logical_viewport=(args.logical_width, args.logical_height),
        device_scale_factor=args.device_scale_factor,
        region_manifest=args.regions,
        allow_incomplete=args.allow_incomplete,
    )
    output = (args.output or diagnostics_root / "ui-browser-execution.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"records": len(payload["records"]), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
