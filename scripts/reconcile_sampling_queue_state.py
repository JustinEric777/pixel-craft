"""Project the immutable queue and canonical states into one fresh run report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.sampling_queue import SamplingQueue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    queue_path = profile.diagnostics_root / "sampling-queue.json"
    raw = json.loads(queue_path.read_text(encoding="utf-8"))
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    results = []
    for record in queue.records:
        state = CaptureLayout(profile.capture_root, record.capture_id).state_path
        payload = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else {}
        canonical = payload.get("canonical") or {}
        status = "ready" if canonical.get("status") == "ready" else "pending"
        results.append(
            {
                "record_id": record.record_id,
                "capture_id": record.capture_id,
                "kind": record.kind.value,
                "status": status,
                "canonical_attempt_id": canonical.get("attempt_id"),
                "last_attempt_status": (payload.get("last_attempt") or {}).get("status"),
            }
        )
    counts = Counter(item["status"] for item in results)
    now = datetime.now(UTC)
    run_id = f"reconcile-{now.strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "run_id": run_id,
        "kind": "state-reconciliation",
        "generated_at": now.isoformat(),
        "reference_id": profile.id,
        "queue_version": raw.get("version"),
        "queue_fingerprint": queue.fingerprint,
        "record_count": len(results),
        "ready": counts["ready"],
        "pending": counts["pending"],
        "status": "passed" if counts["pending"] == 0 else "blocked",
        "results": results,
    }
    output = profile.diagnostics_root / "sampling-runs" / f"{run_id}.json"
    write_json_atomic(output, report)
    write_json_atomic(
        profile.diagnostics_root / "sampling-queue-run-latest.json",
        {
            "run_id": run_id,
            "path": str(output),
            "queue_fingerprint": queue.fingerprint,
            "ready": counts["ready"],
            "pending": counts["pending"],
            "status": report["status"],
        },
    )
    print(json.dumps({key: report[key] for key in ("run_id", "record_count", "ready", "pending", "status")}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
