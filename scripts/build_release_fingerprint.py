"""Build source, model, validation and environment fingerprints for an exact run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.build_source_manifest import DEFAULT_ROOTS, build_manifest

MODEL_ROOTS = ("configs/model.yaml", "models")
BASE_VALIDATION_ROOTS = (
    "configs/reference.yaml",
    "configs/parity.yaml",
    "configs/capabilities/parameter-schema.json",
    "configs/ui/editor.json",
    "configs/parity/interaction-contracts.json",
    "configs/parity/core-ui-state-matrix.json",
    "configs/parity/core-interaction-matrix.json",
    "configs/parity/native-capture-environment.json",
    "configs/parity/native-parameter-bindings.json",
    "configs/parity/ui-regions.json",
    "assets/manifests",
    "test_data/parity/inputs",
)
PACKAGE_NAMES = (
    "fastapi",
    "numpy",
    "onnx",
    "onnxruntime",
    "openvino",
    "Pillow",
    "pydantic",
    "pytest",
    "PyYAML",
    "ruff",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validation_roots(project_root: Path, profile: Any) -> tuple[str, ...]:
    paths = (
        profile.cases_path.parent,
        profile.diagnostics_root / "sampling-queue.json",
        profile.diagnostics_root / "sampling-queue-exact-incremental.json",
        profile.observations_root / "interactions",
        profile.ui_reference_root / "reference-manifest.json",
    )
    relative = tuple(path.resolve().relative_to(project_root).as_posix() for path in paths)
    return (*BASE_VALIDATION_ROOTS, *relative)


def _existing_artifacts(payload: Any, project_root: Path) -> Iterable[Path]:
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _existing_artifacts(value, project_root)
        return
    if isinstance(payload, list):
        for value in payload:
            yield from _existing_artifacts(value, project_root)
        return
    if not isinstance(payload, str) or not payload:
        return
    raw = Path(payload)
    candidates = [raw] if raw.is_absolute() else [project_root / raw]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(project_root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            yield resolved


def _ui_reference_artifacts(project_root: Path, manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    records: list[dict[str, Any]] = []
    for item in payload.get("records", []):
        for field in ("screenshot", "accessibility_tree"):
            value = item.get(field)
            if not value:
                continue
            path = (root / str(value)).resolve()
            try:
                relative = path.relative_to(project_root).as_posix()
            except ValueError:
                continue
            if path.is_file():
                records.append(
                    {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)}
                )
    return records


def _command_version(command: tuple[str, ...]) -> str | None:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or result.stderr).strip() or None


def _json_environment(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    environment = payload.get("environment")
    return environment if isinstance(environment, dict) else None


def _scope_summary(project_root: Path) -> dict[str, int]:
    ui_matrix = json.loads(
        (project_root / "configs/parity/core-ui-state-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    interaction_matrix = json.loads(
        (project_root / "configs/parity/core-interaction-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    editor = json.loads(
        (project_root / "configs/ui/editor.json").read_text(encoding="utf-8")
    )
    model_config = yaml.safe_load(
        (project_root / "configs/model.yaml").read_text(encoding="utf-8")
    )
    capabilities = {
        str(capability_id)
        for group in editor.get("tool_groups", [])
        for capability_id in group.get("capabilities", [])
    }
    capabilities.update(
        str(item["capability_id"])
        for item in editor.get("catalog_actions", [])
        if item.get("capability_id")
    )
    return {
        "ui_state_count": len(ui_matrix.get("records", [])),
        "pixel_ui_state_count": sum(
            record.get("comparison_mode", "pixel") == "pixel"
            for record in ui_matrix.get("records", [])
        ),
        "semantic_ui_state_count": sum(
            record.get("comparison_mode", "pixel") == "semantic"
            for record in ui_matrix.get("records", [])
        ),
        "interaction_contract_count": len(interaction_matrix.get("records", [])),
        "visible_capability_count": len(capabilities),
        "active_model_count": len(model_config.get("models", [])),
    }


def build_release_fingerprint(
    project_root: Path,
    *,
    reference_config: Path,
    reference_id: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    profile = load_reference_catalog(
        reference_config.resolve(), project_root=project_root
    ).resolve(reference_id)
    source = build_manifest(project_root, DEFAULT_ROOTS)
    models = build_manifest(project_root, MODEL_ROOTS)
    validation = build_manifest(project_root, _validation_roots(project_root, profile))

    referenced_files: dict[str, dict[str, Any]] = {}
    for manifest in (profile.cases_path, profile.matrix_path, profile.manifest_path):
        if not manifest.is_file():
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for path in _existing_artifacts(payload, project_root):
            relative = path.relative_to(project_root).as_posix()
            referenced_files[relative] = {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
    ui_manifest = profile.ui_reference_root / "reference-manifest.json"
    for record in _ui_reference_artifacts(project_root, ui_manifest):
        referenced_files[str(record["path"])] = record
    validation_records = sorted(
        [*validation["records"], *referenced_files.values()],
        key=lambda item: str(item["path"]),
    )
    validation_fingerprint = _fingerprint(validation_records)
    scope = _scope_summary(project_root)

    packages: dict[str, str | None] = {}
    for name in PACKAGE_NAMES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    parity = yaml.safe_load((project_root / "configs/parity.yaml").read_text(encoding="utf-8"))
    environment = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "packages": packages,
        "node": _command_version(("node", "--version")),
        "npm": _command_version(("npm", "--version")),
        "locale": profile.locale,
        "reference_platform": profile.platform,
        "timezone": os.environ.get("TZ", "Asia/Shanghai"),
        "parity_contract": {
            "scope_policy": parity.get("scope_policy", {}),
            "capture": parity.get("capture", {}),
            "thresholds": parity.get("thresholds", {}),
            "runtime": parity.get("runtime", {}),
        },
        "ui_browser": _json_environment(
            profile.diagnostics_root / "ui-browser-execution.json"
        ),
        "interaction_browser": _json_environment(
            profile.diagnostics_root / "interaction-browser-execution.json"
        ),
    }
    fingerprints = {
        "source": source["source_fingerprint"],
        "models": models["source_fingerprint"],
        "validation": validation_fingerprint,
        "environment": _fingerprint(environment),
        "scope": _fingerprint(scope),
    }
    missing = {
        "source": source["missing_roots"],
        "models": models["missing_roots"],
        "validation": validation["missing_roots"],
    }
    status = "passed" if not any(missing.values()) else "blocked"
    return {
        "version": "1.0",
        "generated_by": "scripts/build_release_fingerprint.py",
        "reference_id": profile.id,
        "fingerprints": fingerprints,
        "release_fingerprint": _fingerprint(fingerprints),
        "status": status,
        "missing": missing,
        "source": source,
        "models": models,
        "validation": {
            **validation,
            "records": validation_records,
            "source_fingerprint": validation_fingerprint,
        },
        "environment": environment,
        "scope": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--reference-config", type=Path, default=ROOT / "configs/reference.yaml"
    )
    parser.add_argument("--reference-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_release_fingerprint(
        args.project_root,
        reference_config=args.reference_config,
        reference_id=args.reference_id,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "release_fingerprint": report["release_fingerprint"],
                "status": report["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
