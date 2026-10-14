"""Versioned identities for an external application reference build."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModelSourcePolicy(StrEnum):
    PROJECT = "project"
    EXTERNAL_LOCAL_ONLY = "external-local-only"


@dataclass(frozen=True)
class ReferenceBuild:
    id: str
    product: str
    platform: str
    version: str
    build: str
    language: str = "zh-Hans"
    theme: str = "dark"


@dataclass(frozen=True)
class ModelVariant:
    id: str
    logical_model_id: str
    format: str
    backend: str
    relative_path: str
    sha256: str
    source_policy: ModelSourcePolicy
    redistributable: bool = False
