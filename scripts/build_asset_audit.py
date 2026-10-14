"""Audit local effect assets, hashes, paths and redistribution status."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run(asset_root: Path, manifest_path: Path, license_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    licenses = json.loads(license_path.read_text(encoding="utf-8"))
    families = licenses.get("families", {})
    records: list[dict[str, Any]] = []
    for record in manifest.get("records", []):
        family = str(record.get("family", "unknown"))
        path = (asset_root / str(record.get("path", ""))).resolve()
        exists = path.is_file() and path.is_relative_to(asset_root.resolve())
        computed_hash = _sha256(path) if exists else None
        expected_hash = record.get("sha256")
        license_record = families.get(family, {})
        status = str(license_record.get("status", "unknown"))
        records.append(
            {
                "id": record.get("id"),
                "family": family,
                "path": str(path),
                "exists": exists,
                "hash_match": computed_hash == expected_hash if exists and expected_hash else False,
                "license_status": status,
                "redistributable": bool(license_record.get("redistributable", False)),
            }
        )
    missing = [item for item in records if not item["exists"]]
    hash_mismatch = [item for item in records if item["exists"] and not item["hash_match"]]
    status_counts = Counter(item["license_status"] for item in records)
    availability_passed = not missing and not hash_mismatch
    authorization_passed = bool(records) and all(
        item["license_status"] in {"authorized", "original-owned"} for item in records
    )
    return {
        "version": "0.1.0",
        "asset_root": str(asset_root),
        "manifest": str(manifest_path),
        "license_registry": str(license_path),
        "count": len(records),
        "families": sorted({item["family"] for item in records}),
        "missing_count": len(missing),
        "hash_mismatch_count": len(hash_mismatch),
        "license_status_counts": dict(status_counts),
        "redistributable_count": sum(item["redistributable"] for item in records),
        "availability_gate": "passed" if availability_passed else "blocked",
        "authorization_gate": "passed" if authorization_passed else "blocked",
        "exact_gate": "passed"
        if availability_passed and authorization_passed
        else "blocked",
        "gate": "passed" if availability_passed else "blocked",
        "missing": missing,
        "hash_mismatch": hash_mismatch,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=ROOT / "assets")
    parser.add_argument("--manifest", type=Path, default=ROOT / "assets/manifests/registry.json")
    parser.add_argument(
        "--license-registry", type=Path, default=ROOT / "assets/manifests/licenses.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/asset-audit.json")
    args = parser.parse_args()
    report = run(args.asset_root.resolve(), args.manifest.resolve(), args.license_registry.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "count",
                    "missing_count",
                    "hash_mismatch_count",
                    "availability_gate",
                    "authorization_gate",
                    "exact_gate",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["exact_gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
