"""Typed configuration entry point for the whole application."""

from .reference import (
    ReferenceCatalog,
    ReferenceProfile,
    load_reference_catalog,
    resolve_reference,
)
from .schemas import (
    AppConfig,
    ModelCatalogConfig,
    ModelEntryConfig,
    ModelSelectionConfig,
    PathConfig,
    RuntimeConfig,
)
from .store import load_config

__all__ = [
    "AppConfig",
    "ModelCatalogConfig",
    "ModelEntryConfig",
    "ModelSelectionConfig",
    "PathConfig",
    "ReferenceCatalog",
    "ReferenceProfile",
    "RuntimeConfig",
    "load_config",
    "load_reference_catalog",
    "resolve_reference",
]
