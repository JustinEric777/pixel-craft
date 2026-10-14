"""Validate Native-anchored UI comparison regions and build pixel masks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_sha256(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "content_sha256"}
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rectangle(value: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        return None
    x, y, width, height = value
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _overlap(
    left: tuple[int, int, int, int], right: tuple[int, int, int, int]
) -> bool:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    return lx < rx + rw and rx < lx + lw and ly < ry + rh and ry < ly + lh


def _selector_matches(node: dict[str, Any], selector: dict[str, Any]) -> bool:
    return bool(selector) and all(node.get(key) == value for key, value in selector.items())


def validate_region_manifest(
    payload: dict[str, Any],
    *,
    reference_root: Path,
    reference_id: str,
    expected: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], np.ndarray]]:
    issues: list[dict[str, Any]] = []
    masks: dict[tuple[str, str], np.ndarray] = {}
    if payload.get("reference_id") != reference_id:
        issues.append({"id": "region-reference-id-mismatch"})
    declared_digest = payload.get("content_sha256")
    if declared_digest != content_sha256(payload):
        issues.append({"id": "region-content-hash-mismatch"})
    records = payload.get("records")
    if not isinstance(records, list):
        return issues + [{"id": "missing-region-records"}], masks

    actual: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            issues.append({"id": "invalid-region-record"})
            continue
        viewport = record.get("viewport")
        state = str(record.get("state") or "")
        if not isinstance(viewport, list) or len(viewport) != 2:
            issues.append({"id": "invalid-region-viewport", "state": state})
            continue
        key = (f"{viewport[0]}x{viewport[1]}", state)
        if key in actual:
            issues.append({"id": "duplicate-region-state", "viewport": key[0], "state": state})
            continue
        actual[key] = record

    for viewport_name, state in sorted(expected):
        record = actual.get((viewport_name, state))
        if record is None:
            issues.append({"id": "missing-region-state", "viewport": viewport_name, "state": state})
            continue
        try:
            viewport_width, viewport_height = (int(value) for value in viewport_name.split("x", 1))
        except ValueError:
            issues.append({"id": "invalid-region-viewport", "viewport": viewport_name, "state": state})
            continue
        state_issues_before = len(issues)
        reference_ax_value = record.get("reference_ax")
        reference_ax = (reference_root / str(reference_ax_value or "")).resolve()
        try:
            reference_ax.relative_to(reference_root.resolve())
        except ValueError:
            issues.append({"id": "region-ax-path-escapes-root", "viewport": viewport_name, "state": state})
        ax_nodes: list[dict[str, Any]] = []
        if not reference_ax.is_file():
            issues.append({"id": "missing-region-native-ax", "viewport": viewport_name, "state": state})
        else:
            if sha256_file(reference_ax) != record.get("reference_ax_sha256"):
                issues.append({"id": "region-native-ax-hash-mismatch", "viewport": viewport_name, "state": state})
            try:
                ax_payload = json.loads(reference_ax.read_text(encoding="utf-8"))
                ax_nodes = [node for node in ax_payload.get("nodes", []) if isinstance(node, dict)]
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                issues.append({"id": "invalid-region-native-ax", "viewport": viewport_name, "state": state})

        includes: list[tuple[int, int, int, int]] = []
        for value in record.get("include", []):
            rectangle = _rectangle(value)
            if rectangle is None:
                issues.append({"id": "invalid-include-region", "viewport": viewport_name, "state": state})
                continue
            x, y, width, height = rectangle
            if x + width > viewport_width or y + height > viewport_height:
                issues.append({"id": "region-out-of-bounds", "kind": "include", "viewport": viewport_name, "state": state})
                continue
            includes.append(rectangle)
        if not includes:
            issues.append({"id": "missing-include-region", "viewport": viewport_name, "state": state})

        exclusions: list[tuple[int, int, int, int]] = []
        for exclusion in record.get("exclude", []):
            if not isinstance(exclusion, dict):
                issues.append({"id": "invalid-exclude-region", "viewport": viewport_name, "state": state})
                continue
            rectangle = _rectangle(exclusion.get("bounds"))
            if rectangle is None:
                issues.append({"id": "invalid-exclude-region", "viewport": viewport_name, "state": state})
                continue
            x, y, width, height = rectangle
            if x + width > viewport_width or y + height > viewport_height:
                issues.append({"id": "region-out-of-bounds", "kind": "exclude", "viewport": viewport_name, "state": state})
            if not any(
                x >= ix and y >= iy and x + width <= ix + iw and y + height <= iy + ih
                for ix, iy, iw, ih in includes
            ):
                issues.append({"id": "exclude-outside-include", "viewport": viewport_name, "state": state})
            reason = exclusion.get("scope_reason")
            if not isinstance(reason, str) or not reason.strip():
                issues.append({"id": "missing-region-scope-reason", "viewport": viewport_name, "state": state})
            selector = exclusion.get("native_ax_selector")
            if not isinstance(selector, dict) or not _selector_matches_any(ax_nodes, selector):
                issues.append({"id": "region-native-ax-selector-missing", "viewport": viewport_name, "state": state})
            if any(_overlap(rectangle, previous) for previous in exclusions):
                issues.append({"id": "ambiguous-overlapping-exclusions", "viewport": viewport_name, "state": state})
            exclusions.append(rectangle)

        if len(issues) == state_issues_before:
            mask = np.zeros((viewport_height, viewport_width), dtype=bool)
            for x, y, width, height in includes:
                mask[y : y + height, x : x + width] = True
            for x, y, width, height in exclusions:
                mask[y : y + height, x : x + width] = False
            if not mask.any():
                issues.append({"id": "empty-in-scope-region", "viewport": viewport_name, "state": state})
            else:
                masks[(viewport_name, state)] = mask

    for viewport, state in sorted(set(actual) - expected):
        issues.append({"id": "unexpected-region-state", "viewport": viewport, "state": state})
    return issues, masks


def _selector_matches_any(nodes: list[dict[str, Any]], selector: dict[str, Any]) -> bool:
    allowed = {"identifier", "title", "description", "help", "value"}
    if not selector or not set(selector) <= allowed:
        return False
    return any(_selector_matches(node, selector) for node in nodes)
