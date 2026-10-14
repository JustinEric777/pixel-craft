"""Audit Luminar sampling storage, duplicate bytes and state/queue alignment."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.sampling_queue import SamplingQueue


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path, ignored: set[Path]) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.resolve() not in ignored
    ]


def build_audit(capture_root: Path, queue_path: Path | None = None) -> dict[str, Any]:
    capture_root = capture_root.resolve()
    paths = _files(capture_root, set())
    extension_counts = Counter(path.suffix.lower() or "<none>" for path in paths)
    area_bytes: Counter[str] = Counter()
    area_files: Counter[str] = Counter()
    by_size: dict[int, list[Path]] = defaultdict(list)
    total_bytes = 0
    for path in paths:
        size = path.stat().st_size
        total_bytes += size
        relative = path.relative_to(capture_root)
        area = relative.parts[0] if len(relative.parts) > 1 else "<root>"
        area_bytes[area] += size
        area_files[area] += 1
        if size:
            by_size[size].append(path)

    duplicate_groups: list[dict[str, Any]] = []
    reclaimable = 0
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        hashes: dict[str, list[Path]] = defaultdict(list)
        for path in candidates:
            hashes[_sha256(path)].append(path)
        for digest, duplicates in hashes.items():
            if len(duplicates) < 2:
                continue
            physical = {
                (path.stat().st_dev, path.stat().st_ino): path for path in duplicates
            }
            if len(physical) < 2:
                continue
            reclaimable += size * (len(physical) - 1)
            duplicate_groups.append(
                {
                    "sha256": digest,
                    "size": size,
                    "logical_path_count": len(duplicates),
                    "physical_copy_count": len(physical),
                    "paths": [str(path.relative_to(capture_root)) for path in duplicates],
                }
            )

    states: dict[str, dict[str, Any]] = {}
    for path in sorted((capture_root / "state").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {"status": "invalid"}
        states[path.stem] = payload
    state_counts = Counter(str(item.get("status", "missing")) for item in states.values())
    schema_counts = Counter(str(item.get("schema_version", "legacy")) for item in states.values())

    queue_report: dict[str, Any] | None = None
    if queue_path:
        raw = json.loads(queue_path.read_text(encoding="utf-8"))
        queue = SamplingQueue.load(
            queue_path.resolve(), expected_reference_id=str(raw["reference_id"])
        )
        queue_ids = {record.capture_id for record in queue.records}
        state_ids = set(states)
        queue_report = {
            "path": str(queue_path.resolve()),
            "reference_id": queue.reference_id,
            "queue_fingerprint": queue.fingerprint,
            "record_count": len(queue.records),
            "missing_states": sorted(queue_ids - state_ids),
            "orphan_states": sorted(state_ids - queue_ids),
            "ready": sum(states.get(case_id, {}).get("status") == "ready" for case_id in queue_ids),
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "capture_root": str(capture_root),
        "storage": {
            "file_count": len(paths),
            "total_bytes": total_bytes,
            "extensions": dict(sorted(extension_counts.items())),
            "areas": {
                area: {"files": area_files[area], "bytes": area_bytes[area]}
                for area in sorted(area_files)
            },
        },
        "duplicates": {
            "group_count": len(duplicate_groups),
            "extra_physical_copy_count": sum(
                item["physical_copy_count"] - 1 for item in duplicate_groups
            ),
            "reclaimable_bytes": reclaimable,
            "groups": sorted(duplicate_groups, key=lambda item: (-item["size"], item["sha256"])),
        },
        "states": {
            "count": len(states),
            "status_counts": dict(sorted(state_counts.items())),
            "schema_counts": dict(sorted(schema_counts.items())),
            "canonical_ready": sum(
                (item.get("canonical") or {}).get("status") == "ready"
                for item in states.values()
            ),
        },
        "queue": queue_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_audit(args.capture_root, args.queue)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
