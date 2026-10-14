"""Execution evidence and policy values shared by editing use cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionMode(StrEnum):
    DEVELOPMENT = "development"
    EXACT = "exact"

    @classmethod
    def parse(cls, value: str | None) -> ExecutionMode:
        normalized = (value or cls.DEVELOPMENT.value).strip().lower()
        return cls(normalized)


@dataclass(frozen=True)
class CapabilityExecutionGraph:
    capability_id: str
    implementation: str = "deterministic"
    required_models: tuple[str, ...] = ()
    conditional_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionPolicy:
    analysis_only: frozenset[str] = frozenset()
    asset_required: frozenset[str] = frozenset()
    multi_image_only: frozenset[str] = frozenset()
    image_effect_pipelines: frozenset[str] = frozenset()
    local_effect_pipelines: frozenset[str] = frozenset()
