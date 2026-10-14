"""Measure Luminar self-variance before freezing parity thresholds."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.compare_outputs import compare
from scripts.luminar_capture.attempt_store import write_json_atomic


def analyze(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    groups = []
    issues = []
    for raw in manifest.get("groups", []):
        captures = [Path(item).resolve() for item in raw.get("captures", [])]
        missing = [str(path) for path in captures if not path.is_file()]
        if missing or len(captures) < 3:
            issues.append(
                {
                    "family": raw.get("family"),
                    "reason": "requires at least three existing captures",
                    "missing": missing,
                }
            )
            continue
        metrics = [compare(left, right) for left, right in itertools.combinations(captures, 2)]
        max_mae = max(item["mae"] for item in metrics)
        min_ssim = min(item["ssim"] for item in metrics)
        groups.append(
            {
                "family": raw["family"],
                "capture_count": len(captures),
                "pair_count": len(metrics),
                "self_variance": {"mae_max": max_mae, "ssim_min": min_ssim},
                "suggested_gate": {
                    "mae_max": min(1.0, max_mae + 0.002),
                    "ssim_min": max(0.0, min_ssim - 0.002),
                },
                "pairs": metrics,
            }
        )
    return {
        "manifest": str(manifest_path.resolve()),
        "status": "passed" if groups and not issues else "blocked",
        "group_count": len(groups),
        "groups": groups,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.manifest.resolve())
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
