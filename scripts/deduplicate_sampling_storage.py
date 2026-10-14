"""Audit duplicate sampling files and detach unsafe shared hard links."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_capture.attempt_store import write_json_atomic


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _detach_shared_inode(paths: list[Path]) -> int:
    """Give every path its own inode while preserving its current bytes."""

    detached = 0
    for path in paths[1:]:
        temporary = path.with_name(path.name + ".detach-tmp")
        shutil.copy2(path, temporary)
        temporary.replace(path)
        detached += 1
    return detached


def audit_storage(root: Path, *, detach_hardlinks: bool) -> dict[str, object]:
    root = root.resolve()
    sizes: dict[int, list[Path]] = defaultdict(list)
    inodes: dict[tuple[int, int], list[Path]] = defaultdict(list)
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.stat().st_size:
            stat = path.stat()
            sizes[stat.st_size].append(path)
            inodes[(stat.st_dev, stat.st_ino)].append(path)

    shared_inode_groups = [
        sorted(paths) for paths in inodes.values() if len(paths) > 1
    ]
    detached_path_count = 0
    if detach_hardlinks:
        for paths in shared_inode_groups:
            detached_path_count += _detach_shared_inode(paths)

    duplicate_records = []
    reclaimable = 0
    for size, paths in sizes.items():
        if len(paths) < 2:
            continue
        groups: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            groups[_sha256(path)].append(path)
        for duplicate_paths in groups.values():
            if len(duplicate_paths) < 2:
                continue
            canonical = duplicate_paths[0]
            for duplicate in duplicate_paths[1:]:
                duplicates_record = (
                    {
                        "canonical": str(canonical.relative_to(root)),
                        "duplicate": str(duplicate.relative_to(root)),
                        "bytes": size,
                    }
                )
                duplicate_records.append(duplicates_record)
                reclaimable += size
    return {
        "root": str(root),
        "mode": "detach-hardlinks" if detach_hardlinks else "audit-only",
        "shared_inode_group_count": len(shared_inode_groups),
        "shared_inode_path_count": sum(len(paths) for paths in shared_inode_groups),
        "detached_path_count": detached_path_count,
        "duplicate_count": len(duplicate_records),
        "reclaimable_bytes": reclaimable,
        "duplicates": duplicate_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--detach-hardlinks",
        action="store_true",
        help="replace every shared hard-link path with an independent copy",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_storage(args.root, detach_hardlinks=args.detach_hardlinks)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
