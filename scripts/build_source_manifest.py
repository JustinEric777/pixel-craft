"""Build a deterministic SHA-256 manifest for parity-relevant source files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROOTS = (
    "ai",
    "api",
    "configs",
    "core",
    "frontend/scripts",
    "frontend/src",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "image_ops",
    "models/contracts",
    "scripts",
    "services",
    "storage",
    "tests",
)

IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(project_root: Path, roots: tuple[str, ...] = DEFAULT_ROOTS) -> dict[str, Any]:
    project_root = project_root.resolve()
    records: list[dict[str, Any]] = []
    missing_roots: list[str] = []
    for root_name in roots:
        source_root = project_root / root_name
        if not source_root.exists():
            missing_roots.append(root_name)
            continue
        paths = [source_root] if source_root.is_file() else sorted(source_root.rglob("*"))
        for path in paths:
            if not path.is_file() or IGNORED_PARTS.intersection(path.parts):
                continue
            relative = path.relative_to(project_root).as_posix()
            records.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    fingerprint = hashlib.sha256(
        "".join(
            f"{item['path']}\0{item['size']}\0{item['sha256']}\n" for item in records
        ).encode("utf-8")
    ).hexdigest()
    return {
        "version": "1.0",
        "generated_by": "scripts/build_source_manifest.py",
        "roots": list(roots),
        "file_count": len(records),
        "missing_roots": missing_roots,
        "source_fingerprint": fingerprint,
        "status": "passed" if not missing_roots else "blocked",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--root", action="append", dest="roots")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_manifest(
        args.project_root,
        tuple(args.roots) if args.roots else DEFAULT_ROOTS,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("file_count", "source_fingerprint", "status")
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
