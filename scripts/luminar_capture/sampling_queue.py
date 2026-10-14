"""Typed records for the complete Luminar sampling queue."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .case_reader import CaptureCase


class SamplingKind(StrEnum):
    UI = "ui"
    EFFECT = "effect"
    PRESET = "preset"
    SKY = "sky"
    OVERLAY = "overlay"
    WORKFLOW = "workflow"


@dataclass(frozen=True)
class SamplingQueueRecord:
    record_id: str
    scan_order: int
    kind: SamplingKind
    page: str
    section: str
    strategy: str | None
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SamplingQueueRecord:
        required = {
            "id": payload.get("id"),
            "scan_order": payload.get("scan_order"),
            "kind": payload.get("kind"),
            "page": payload.get("page"),
            "section": payload.get("section"),
        }
        missing = [name for name, value in required.items() if value in {None, ""}]
        if missing:
            raise ValueError(f"sampling queue record is missing: {', '.join(missing)}")
        try:
            kind = SamplingKind(str(payload["kind"]))
        except ValueError as exc:
            raise ValueError(f"unsupported sampling kind: {payload['kind']!r}") from exc
        scan_order = int(payload["scan_order"])
        if scan_order <= 0:
            raise ValueError("sampling scan_order must be positive")
        record = cls(
            record_id=str(payload["id"]),
            scan_order=scan_order,
            kind=kind,
            page=str(payload["page"]),
            section=str(payload["section"]),
            strategy=str(payload["strategy"]) if payload.get("strategy") else None,
            payload=dict(payload),
        )
        record._validate_kind_fields()
        return record

    @property
    def capture_id(self) -> str:
        if self.kind is SamplingKind.EFFECT:
            return str(self.payload["case_id"])
        digest = hashlib.sha256(self.record_id.encode("utf-8")).hexdigest()[:12]
        return f"queue-{self.kind.value}-{digest}"

    @property
    def semantic_key(self) -> str:
        """Identity of the operation, independent of order, labels and file paths."""

        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "capability_id": self.payload.get("capability_id"),
            "parameters": self.payload.get("parameters", {}),
            "strategy": self.strategy,
            "ui_state": self.payload.get("ui_state"),
            "viewport": self.payload.get("viewport"),
            "matrix_state_id": self.payload.get("matrix_state_id"),
            "matrix_fingerprint": self.payload.get("matrix_fingerprint"),
            "preset_id": self.payload.get("preset_id"),
            "asset_sha256": self.payload.get("asset_sha256"),
        }
        source = self.payload.get("input")
        if self.payload.get("parameter_binding") is not None:
            payload["parameter_binding"] = self.payload["parameter_binding"]
        if isinstance(source, dict):
            payload["input_sha256"] = source.get("sha256")
        inputs = self.payload.get("inputs")
        if isinstance(inputs, list):
            payload["input_sha256s"] = [item.get("sha256") for item in inputs]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @property
    def input_path(self) -> Path | None:
        source = self.payload.get("input")
        if not isinstance(source, dict) or not source.get("path"):
            return None
        return Path(str(source["path"])).expanduser().resolve()

    def to_capture_case(self) -> CaptureCase:
        source = self.payload.get("input")
        if not isinstance(source, dict):
            raise TypeError(f"{self.record_id} has no single capture input")
        capability_id = {
            SamplingKind.EFFECT: self.payload.get("capability_id"),
            SamplingKind.PRESET: "preset_apply",
            SamplingKind.SKY: "sky_replace",
            SamplingKind.OVERLAY: "overlay_apply",
        }.get(self.kind)
        if not capability_id:
            raise ValueError(f"{self.record_id} cannot be converted to CaptureCase")
        parameters = dict(self.payload.get("parameters", {}))
        if self.kind is SamplingKind.PRESET:
            parameters.update(
                {
                    "preset_id": self.payload["preset_id"],
                    "preset_name": self.payload["name"],
                    "category": self.payload.get("category"),
                }
            )
        return CaptureCase.from_payload(
            {
                "case_id": self.capture_id,
                "capability_id": capability_id,
                "input": source,
                "parameters": parameters,
                "asset_id": self.payload.get("asset_id"),
                "asset_path": self.payload.get("asset_path"),
                "asset_sha256": self.payload.get("asset_sha256"),
            }
        )

    def verify_inputs(self) -> None:
        sources: list[tuple[Path, str]] = []
        source = self.payload.get("input")
        if isinstance(source, dict):
            sources.append((Path(str(source["path"])).resolve(), str(source["sha256"])))
        for item in self.payload.get("inputs", []):
            sources.append((Path(str(item["path"])).resolve(), str(item["sha256"])))
        if self.payload.get("asset_path"):
            sources.append(
                (
                    Path(str(self.payload["asset_path"])).resolve(),
                    str(self.payload["asset_sha256"]),
                )
            )
        for path, expected in sources:
            if not path.is_file():
                raise FileNotFoundError(f"sampling input does not exist: {path}")
            actual = _sha256(path)
            if actual != expected:
                raise RuntimeError(
                    f"sampling input hash mismatch for {self.record_id}: "
                    f"{path}: {actual} != {expected}"
                )

    def _validate_kind_fields(self) -> None:
        required_by_kind = {
            SamplingKind.UI: (
                "viewport",
                "ui_state",
                "matrix_state_id",
                "matrix_fingerprint",
                "matrix_kind",
                "workspace_state",
            ),
            SamplingKind.EFFECT: ("case_id", "capability_id", "input", "locator_id"),
            SamplingKind.PRESET: ("preset_id", "name", "input"),
            SamplingKind.SKY: ("asset_id", "asset_path", "asset_sha256", "input"),
            SamplingKind.OVERLAY: ("asset_id", "asset_path", "asset_sha256", "input"),
            SamplingKind.WORKFLOW: ("capability_id", "inputs"),
        }
        missing = []
        for field in required_by_kind[self.kind]:
            value = self.payload.get(field)
            if value is None or value == "":
                missing.append(field)
        if missing:
            raise ValueError(
                f"{self.record_id} is missing {self.kind.value} fields: "
                + ", ".join(missing)
            )
        if self.kind is SamplingKind.UI:
            viewport = self.payload["viewport"]
            if not (
                isinstance(viewport, list)
                and len(viewport) == 2
                and all(isinstance(value, int) and value > 0 for value in viewport)
            ):
                raise ValueError(f"{self.record_id} has invalid viewport")
            if self.payload["ui_state"] != self.payload["matrix_state_id"]:
                raise ValueError(
                    f"{self.record_id} UI state must equal its current matrix state id"
                )
            if len(str(self.payload["matrix_fingerprint"])) != 64:
                raise ValueError(f"{self.record_id} has invalid UI matrix fingerprint")
        if self.kind is SamplingKind.WORKFLOW and len(self.payload["inputs"]) < 2:
            raise ValueError(f"{self.record_id} requires at least two inputs")


@dataclass(frozen=True)
class SamplingQueue:
    reference_id: str
    records: tuple[SamplingQueueRecord, ...]

    @property
    def fingerprint(self) -> str:
        payload = {
            "reference_id": self.reference_id,
            "semantic_keys": [record.semantic_key for record in self.records],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def load(cls, path: Path, *, expected_reference_id: str) -> SamplingQueue:
        payload = json.loads(path.read_text(encoding="utf-8"))
        reference_id = str(payload.get("reference_id") or "")
        if reference_id != expected_reference_id:
            raise RuntimeError(
                f"sampling queue reference mismatch: {reference_id!r} "
                f"!= {expected_reference_id!r}"
            )
        records = tuple(
            SamplingQueueRecord.from_payload(item) for item in payload.get("records", [])
        )
        if not records:
            raise ValueError("sampling queue has no records")
        ids = [record.record_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("sampling queue contains duplicate record ids")
        orders = [record.scan_order for record in records]
        if orders != list(range(1, len(records) + 1)):
            raise ValueError("sampling queue scan_order must be contiguous and ordered")
        declared_count = int(payload.get("record_count", 0))
        if declared_count != len(records):
            raise ValueError(
                f"sampling queue record_count mismatch: {declared_count} != {len(records)}"
            )
        queue = cls(reference_id=reference_id, records=records)
        declared_fingerprint = payload.get("queue_fingerprint")
        if declared_fingerprint and str(declared_fingerprint) != queue.fingerprint:
            raise ValueError(
                "sampling queue fingerprint mismatch: "
                f"{declared_fingerprint} != {queue.fingerprint}"
            )
        return queue

    def select(
        self,
        *,
        pages: set[str] | None = None,
        kinds: set[SamplingKind] | None = None,
        record_ids: set[str] | None = None,
        start_order: int | None = None,
        limit: int | None = None,
    ) -> tuple[SamplingQueueRecord, ...]:
        records = self.records
        if pages:
            records = tuple(record for record in records if record.page in pages)
        if kinds:
            records = tuple(record for record in records if record.kind in kinds)
        if record_ids:
            records = tuple(record for record in records if record.record_id in record_ids)
            missing = sorted(record_ids - {record.record_id for record in records})
            if missing:
                raise ValueError(f"unknown sampling record ids: {', '.join(missing)}")
        if start_order is not None:
            if start_order <= 0:
                raise ValueError("sampling start_order must be positive")
            records = tuple(record for record in records if record.scan_order >= start_order)
        if limit is not None:
            if limit <= 0:
                raise ValueError("sampling limit must be positive")
            records = records[:limit]
        return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
