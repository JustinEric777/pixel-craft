"""Run the complete Luminar sampling queue in deterministic scan order."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.luminar_sampling import load_luminar_sampling_config
from configs.reference import load_reference_catalog
from scripts.luminar_capture.accessibility_driver import LuminarAccessibilityDriver
from scripts.luminar_capture.app_controller import LuminarAppController
from scripts.luminar_capture.attempt_store import write_json_atomic
from scripts.luminar_capture.layout import CaptureLayout
from scripts.luminar_capture.preflight import (
    NativeCaptureRequirements,
    run_preflight,
)
from scripts.luminar_capture.queue_handlers import LuminarQueueHandlers
from scripts.luminar_capture.queue_runner import SamplingQueueRunner
from scripts.luminar_capture.queue_validator import validate_record
from scripts.luminar_capture.sampling_queue import SamplingKind, SamplingQueue
from scripts.luminar_capture.state_machine import CaptureJournal, CaptureStatus


def _selection_summary(records) -> dict[str, object]:
    return {
        "record_count": len(records),
        "scan_order": [record.scan_order for record in records],
        "counts": dict(sorted(Counter(record.kind.value for record in records).items())),
        "records": [
            {
                "id": record.record_id,
                "capture_id": record.capture_id,
                "scan_order": record.scan_order,
                "kind": record.kind.value,
                "page": record.page,
                "section": record.section,
            }
            for record in records
        ],
    }


def _one_record_per_kind(records):
    selected = []
    seen: set[SamplingKind] = set()
    for record in records:
        if record.kind in seen:
            continue
        seen.add(record.kind)
        selected.append(record)
    return tuple(selected)


def _pending_records(
    records,
    capture_root: Path,
    ui_reference_root: Path,
    *,
    expected_reference_id: str,
    expected_app: dict[str, str],
    retry_failed: bool,
):
    """Reuse only complete, identity-matched, hash-verified capture evidence."""

    pending = []
    ready = 0
    failed = 0
    stale_ready: list[str] = []
    for record in records:
        state = CaptureJournal(CaptureLayout(capture_root, record.capture_id)).read()
        if state.get("status") == CaptureStatus.READY:
            validation = validate_record(
                record,
                capture_root=capture_root,
                ui_reference_root=ui_reference_root,
                expected_reference_id=expected_reference_id,
                expected_app=expected_app,
            )
            if validation["status"] == "ready":
                ready += 1
                continue
            stale_ready.append(record.capture_id)
        if state.get("status") == CaptureStatus.FAILED and not retry_failed:
            failed += 1
            continue
        pending.append(record)
    return tuple(pending), ready, failed, tuple(stale_ready)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--sampling-config", type=Path, default=ROOT / "configs/luminar_sampling.yaml")
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--page", action="append", choices=("catalog", "presets", "edit"))
    parser.add_argument("--kind", action="append", choices=tuple(kind.value for kind in SamplingKind))
    parser.add_argument("--record-id", action="append")
    parser.add_argument(
        "--ui-matrix-kind",
        action="append",
        choices=("workspace-state", "tool-panel-state", "tool-parameter-state"),
        help="limit UI records to one current matrix kind",
    )
    parser.add_argument(
        "--native-parameter-status",
        action="append",
        choices=("supported", "pending-live-probe", "blocked-native-mismatch"),
        help="limit parameter UI records by the current Native binding audit",
    )
    parser.add_argument(
        "--native-parameter-operation",
        action="append",
        choices=(
            "slider",
            "button",
            "menu-choice",
            "semantic-readback",
            "asset-picker",
            "stroke",
            "crop-box",
        ),
        help="limit supported parameter UI records by exact Native operation kind",
    )
    parser.add_argument("--start-order", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--one-per-kind",
        action="store_true",
        help="select the first record of every included sampling kind",
    )
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="include terminal failed records in a resumed batch",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--allow-ui-control",
        action="store_true",
        help="allow Luminar to take foreground keyboard and mouse control",
    )
    parser.add_argument(
        "--low-interference",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="yield while physical keyboard or pointer input is active (default: true)",
    )
    parser.add_argument("--required-idle-seconds", type=float, default=5.0)
    parser.add_argument("--idle-poll-seconds", type=float, default=0.5)
    args = parser.parse_args()

    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    config = load_luminar_sampling_config(args.sampling_config.resolve())
    if config.reference_id != profile.id:
        raise RuntimeError(
            f"sampling reference mismatch: {config.reference_id!r} != {profile.id!r}"
        )
    queue_path = (args.queue or profile.diagnostics_root / "sampling-queue.json").resolve()
    queue = SamplingQueue.load(queue_path, expected_reference_id=profile.id)
    records = queue.select(
        pages=set(args.page or ()) or None,
        kinds={SamplingKind(value) for value in args.kind or ()} or None,
        record_ids=set(args.record_id or ()) or None,
        start_order=args.start_order,
        limit=None,
    )
    if args.ui_matrix_kind:
        allowed_matrix_kinds = set(args.ui_matrix_kind)
        records = tuple(
            record
            for record in records
            if record.kind != SamplingKind.UI
            or str(record.payload.get("matrix_kind")) in allowed_matrix_kinds
        )
    if args.native_parameter_status or args.native_parameter_operation:
        audit_path = ROOT / "configs/parity/native-parameter-bindings.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("reference_id") != profile.id:
            raise RuntimeError("native parameter binding audit reference mismatch")
        bindings = {
            str(item["matrix_state_id"]): item for item in audit.get("records", [])
        }
        allowed_statuses = set(args.native_parameter_status or ())
        allowed_operations = set(args.native_parameter_operation or ())
        records = tuple(
            record
            for record in records
            if record.kind != SamplingKind.UI
            or record.payload.get("matrix_kind") != "tool-parameter-state"
            or (
                record.payload.get("matrix_state_id") in bindings
                and (
                    not allowed_statuses
                    or bindings[str(record.payload["matrix_state_id"])].get("status")
                    in allowed_statuses
                )
                and (
                    not allowed_operations
                    or (
                        isinstance(
                            bindings[str(record.payload["matrix_state_id"])].get("native"),
                            dict,
                        )
                        and bindings[str(record.payload["matrix_state_id"])]["native"].get("kind")
                        in allowed_operations
                    )
                )
            )
        )
    ready_filtered = 0
    failed_filtered = 0
    stale_ready: tuple[str, ...] = ()
    if args.resume:
        records, ready_filtered, failed_filtered, stale_ready = _pending_records(
            records,
            profile.capture_root,
            profile.ui_reference_root,
            expected_reference_id=profile.id,
            expected_app={
                "version": profile.version,
                "build": profile.build,
                "bundle_id": profile.bundle_id,
            },
            retry_failed=args.retry_failed,
        )
    if args.one_per_kind:
        records = _one_record_per_kind(records)
    if args.limit is not None:
        records = records[: args.limit]
    summary = {
        "reference_id": profile.id,
        "queue": str(queue_path),
        "queue_fingerprint": queue.fingerprint,
        "resume": args.resume,
        "ready_filtered": ready_filtered,
        "failed_filtered": failed_filtered,
        "stale_ready": list(stale_ready),
        **_selection_summary(records),
    }
    if args.dry_run:
        print(json.dumps({"status": "dry-run", **summary}, ensure_ascii=False, indent=2))
        return 0
    if not args.allow_ui_control:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "foreground-ui-control-not-authorized",
                    "message": (
                        "Run with --allow-ui-control only in a dedicated macOS GUI "
                        "session; native capture cannot be headless on the active desktop."
                    ),
                    **summary,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    app_path = (args.app or config.app_path).resolve()
    controller = LuminarAppController(app_path)
    app_version = controller.version()
    profile.validate_app_version(app_version)
    driver = LuminarAccessibilityDriver(
        timeout_seconds=config.timeouts.action_seconds,
        low_interference=args.low_interference,
        required_idle_seconds=args.required_idle_seconds,
        idle_poll_seconds=args.idle_poll_seconds,
    )
    controller.set_ui_control_guard(driver.wait_for_user_idle)
    requirements = NativeCaptureRequirements(
        reference_id=profile.id,
        app_version=profile.version,
        app_build=profile.build,
        bundle_id=profile.bundle_id,
        locale=profile.locale,
        logical_viewport=config.logical_viewport,
        physical_viewport=config.viewports[0],
        environment_evidence_path=config.environment_evidence_path,
    )
    try:
        controller.enter_full_screen(
            timeout_seconds=config.timeouts.navigation_seconds
        )
        result = run_preflight(
            controller,
            driver,
            output_dir=profile.diagnostics_root / "preflight",
            timeout_seconds=config.timeouts.action_seconds,
            requirements=requirements,
        )
    except Exception as exc:  # noqa: BLE001 - native app boundary
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if args.preflight:
        print(json.dumps({"status": "ready" if result.get("ok") else "blocked", **result}, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if result.get("ok") is not True:
        print(
            json.dumps(
                {"status": "blocked", "reason": "native-preflight-failed", **result},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    for capture_id in stale_ready:
        CaptureJournal(CaptureLayout(profile.capture_root, capture_id)).invalidate_evidence(
            reason="current-queue-evidence-validation-failed",
            queue_fingerprint=queue.fingerprint,
        )

    handlers = LuminarQueueHandlers(
        config,
        controller,
        driver,
        reference_id=profile.id,
        app_version=app_version,
        ui_reference_root=profile.ui_reference_root,
    )
    execution = SamplingQueueRunner(profile.capture_root, handlers.mapping()).run(
        records, resume=args.resume
    )
    report = {
        "run_id": f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
        "started_at": datetime.now(UTC).isoformat(),
        "reference_id": profile.id,
        "queue_fingerprint": queue.fingerprint,
        "app": str(app_path),
        "app_version": app_version,
        "input_control": driver.interference_report(),
        **execution,
    }
    output = profile.diagnostics_root / "sampling-runs" / f"{report['run_id']}.json"
    write_json_atomic(output, report)
    write_json_atomic(
        profile.diagnostics_root / "sampling-queue-run-latest.json",
        {
            "run_id": report["run_id"],
            "path": str(output),
            "queue_fingerprint": queue.fingerprint,
            "ready": report["ready"],
            "failed": report["failed"],
            "skipped": report["skipped"],
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
