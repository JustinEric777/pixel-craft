"""Run durable local inference jobs with per-model checkpoints."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.app import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        raise ValueError("poll-seconds must be positive")
    service = create_app(data_root=args.data_root).state.jobs
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    while True:
        result = service.run_next(worker_id)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False))
        if args.once:
            return 0
        if result is None:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
