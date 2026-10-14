"""Remove obsolete stability polls while retaining failed-attempt diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.luminar_capture.attempt_store import write_json_atomic


def plan_prune(capture_root: Path, *, apply: bool) -> dict[str, object]:
    capture_root = capture_root.resolve()
    removed: list[str] = []
    reclaimed = 0
    for case_dir in sorted((capture_root / "staging").glob("*")):
        if not case_dir.is_dir():
            continue
        state_path = capture_root / "state" / f"{case_dir.name}.json"
        state = (
            json.loads(state_path.read_text(encoding="utf-8"))
            if state_path.is_file()
            else {}
        )
        candidates = sorted(set(case_dir.glob("stable-*.png")))
        keep = set()
        if state.get("status") != "ready":
            full = sorted(case_dir.glob("stable-[0-9][0-9][0-9].png"))[-3:]
            previews = sorted(case_dir.glob("stable-preview-*.png"))[-3:]
            keep.update(full + previews)
        for path in candidates:
            if path in keep or not path.is_file():
                continue
            reclaimed += path.stat().st_size
            removed.append(str(path.relative_to(capture_root)))
            if apply:
                path.unlink()
    return {
        "capture_root": str(capture_root),
        "applied": apply,
        "removed_count": len(removed),
        "reclaimed_bytes": reclaimed,
        "removed": removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = plan_prune(args.capture_root, apply=args.apply)
    if args.output:
        write_json_atomic(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
