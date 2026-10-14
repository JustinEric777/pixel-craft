"""Resolve versioned Luminar reference data without version-specific branches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ReferenceProfile:
    id: str
    product: str
    version: str
    build: str
    bundle_id: str
    locale: str
    platform: str
    cases_path: Path
    matrix_path: Path
    manifest_path: Path
    capture_root: Path
    ui_reference_root: Path
    observations_root: Path
    diagnostics_root: Path
    exact_gate_enabled: bool

    def validate_app_version(self, actual: dict[str, str]) -> None:
        expected = {
            "version": self.version,
            "build": self.build,
            "bundle_id": self.bundle_id,
        }
        mismatches = [
            f"{key}={actual.get(key)!r} (expected {value!r})"
            for key, value in expected.items()
            if str(actual.get(key, "")) != value
        ]
        if mismatches:
            raise RuntimeError(
                f"Luminar application does not match reference {self.id}: "
                + ", ".join(mismatches)
            )


@dataclass(frozen=True)
class ReferenceCatalog:
    active_reference: str
    references: dict[str, ReferenceProfile]

    def resolve(self, reference_id: str | None = None) -> ReferenceProfile:
        selected = reference_id or self.active_reference
        try:
            return self.references[selected]
        except KeyError as exc:
            known = ", ".join(sorted(self.references))
            raise KeyError(f"unknown reference id {selected!r}; known references: {known}") from exc


def _resolve_path(value: Any, project_root: Path, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"reference field must be a non-empty path: {field}")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def load_reference_catalog(
    config_path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> ReferenceCatalog:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    path = (config_path or root / "configs/reference.yaml").resolve()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"reference configuration is missing: {path}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid reference configuration: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"reference configuration root must be an object: {path}")
    active = str(payload.get("active_reference") or "")
    raw_references = payload.get("references")
    if not active or not isinstance(raw_references, dict) or not raw_references:
        raise ValueError("reference configuration requires active_reference and references")
    references: dict[str, ReferenceProfile] = {}
    path_fields = (
        "cases_path",
        "matrix_path",
        "manifest_path",
        "capture_root",
        "ui_reference_root",
        "observations_root",
        "diagnostics_root",
    )
    for reference_id, raw in raw_references.items():
        if not isinstance(raw, dict):
            raise TypeError(f"reference profile must be an object: {reference_id}")
        missing = [
            field
            for field in ("product", "version", "build", "bundle_id", *path_fields)
            if raw.get(field) in {None, ""}
        ]
        if missing:
            raise ValueError(
                f"reference profile {reference_id} is missing fields: {', '.join(missing)}"
            )
        resolved = {
            field: _resolve_path(raw[field], root, f"{reference_id}.{field}")
            for field in path_fields
        }
        references[str(reference_id)] = ReferenceProfile(
            id=str(reference_id),
            product=str(raw["product"]),
            version=str(raw["version"]),
            build=str(raw["build"]),
            bundle_id=str(raw["bundle_id"]),
            locale=str(raw.get("locale", "zh-Hans")),
            platform=str(raw.get("platform", "macOS")),
            exact_gate_enabled=bool(raw.get("exact_gate_enabled", False)),
            **resolved,
        )
    catalog = ReferenceCatalog(active_reference=active, references=references)
    catalog.resolve()
    return catalog


def resolve_reference(
    reference_id: str | None = None,
    *,
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> ReferenceProfile:
    return load_reference_catalog(config_path, project_root=project_root).resolve(reference_id)
