"""Serializable state for resumable inference work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InferenceJob:
    id: str
    project_id: str
    source_hash: str
    requested_models: list[str]
    request_key: str
    status: str
    created_at: str
    updated_at: str
    completed_models: dict[str, dict[str, Any]] = field(default_factory=dict)
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InferenceJob:
        return cls(**payload)
