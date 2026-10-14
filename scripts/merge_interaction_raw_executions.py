"""Merge single-contract Browser raw traces after enforcing one environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def merge(paths: list[Path]) -> dict[str, Any]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not payloads:
        raise ValueError("at least one raw execution is required")
    reference_id = payloads[0].get("reference_id")
    environment = payloads[0].get("environment")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, payload in zip(paths, payloads, strict=True):
        if payload.get("reference_id") != reference_id:
            raise ValueError(f"reference mismatch: {path}")
        if payload.get("environment") != environment:
            raise ValueError(f"environment mismatch: {path}")
        for record in payload.get("records", []):
            identifier = record.get("id")
            if not identifier or identifier in seen:
                raise ValueError(f"missing or duplicate contract id: {identifier}")
            seen.add(identifier)
            records.append(record)
    return {
        "version": "2.0",
        "reference_id": reference_id,
        "environment": environment,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = merge([path.resolve() for path in args.raw])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(payload["records"]), "output": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
