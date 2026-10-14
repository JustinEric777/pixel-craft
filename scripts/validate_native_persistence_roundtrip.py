"""Validate fail-closed Native persistence provenance and roundtrip evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

REQUIRED_STATES = (
    "project",
    "edit-history",
    "layer",
    "mask",
    "workflow",
    "preset",
    "preview-export",
)
FORBIDDEN_REPOSITORY_MARKERS = (
    "json-primary",
    "dual-write",
    "compatibility-reader",
    "runtime-migration",
    "sqlite-history-projection",
)


def validate(manifest: Path, reference_id: str) -> dict[str, Any]:
    issues: list[str] = []
    payload: dict[str, Any] = {}
    if not manifest.is_file():
        issues.append(f"missing Native persistence roundtrip manifest: {manifest}")
    else:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"invalid Native persistence manifest: {exc}")

    if payload:
        if payload.get("reference_id") != reference_id:
            issues.append("reference_id does not match the selected Native reference")
        provenance = payload.get("native_provenance")
        if not isinstance(provenance, dict):
            issues.append("native_provenance is missing")
        else:
            for field in ("app_id", "version", "build", "source_hash", "snapshot_hash"):
                if not provenance.get(field):
                    issues.append(f"native_provenance.{field} is missing")
            if provenance.get("fullscreen") is not True:
                issues.append("Native capture was not proven full-screen")
            if provenance.get("isolated_display") is not True or provenance.get("isolated_input") is not True:
                issues.append("Native capture isolation is not proven")

        roundtrips = payload.get("roundtrips")
        indexed = {
            item.get("state"): item
            for item in roundtrips
            if isinstance(item, dict) and isinstance(item.get("state"), str)
        } if isinstance(roundtrips, list) else {}
        for state in REQUIRED_STATES:
            item = indexed.get(state)
            if not item:
                issues.append(f"missing roundtrip state: {state}")
                continue
            if item.get("status") != "passed":
                issues.append(f"roundtrip state is not passed: {state}")
            for field in ("serialized_hash", "reload_hash", "output_hash"):
                value = item.get(field)
                if not isinstance(value, str) or len(value) != 64:
                    issues.append(f"{state}.{field} is not a SHA-256")
            if item.get("serialized_hash") != item.get("reload_hash"):
                issues.append(f"serialized/reload hash mismatch: {state}")

        repositories = payload.get("active_repositories")
        if not isinstance(repositories, list) or not repositories:
            issues.append("active_repositories is missing")
        else:
            normalized = "\n".join(str(item).lower() for item in repositories)
            for marker in FORBIDDEN_REPOSITORY_MARKERS:
                if marker in normalized:
                    issues.append(f"forbidden active repository marker: {marker}")
        if payload.get("restart_status") != "passed":
            issues.append("restart_status is not passed")

    return {
        "version": "1.0",
        "reference_id": reference_id,
        "manifest": str(manifest),
        "required_states": list(REQUIRED_STATES),
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "gate": "passed" if not issues else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = load_reference_catalog(args.reference_config.resolve(), project_root=ROOT).resolve(args.reference_id)
    manifest = (args.manifest or profile.diagnostics_root / "native-persistence-roundtrip-manifest.json").resolve()
    report = validate(manifest, profile.id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": report["gate"], "issue_count": report["issue_count"]}))
    return 0 if report["gate"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
