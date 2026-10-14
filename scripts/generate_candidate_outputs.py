"""Generate zpixel preview/export evidence for deterministic parity cases."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.registry import ModelRegistry
from api.app import create_app
from configs.reference import load_reference_catalog


def _canonical_case_parameters(
    effect: str,
    parameters: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Remove only undeclared common parameters carrying their neutral default.

    Parity case identifiers intentionally remain stable when a previously generic
    default is proven not to be part of the current Native tool contract. Unknown
    non-default values stay in the request so the API continues to fail closed.
    """

    capability = schema.get("capabilities", {}).get(effect, {})
    declared = set(capability.get("parameters", [])) | set(
        capability.get("internal_parameters", [])
    )
    common = schema.get("common_parameters", {})
    canonical: dict[str, Any] = {}
    for name, value in parameters.items():
        definition = common.get(name)
        if (
            name not in declared
            and isinstance(definition, dict)
            and "default" in definition
            and value == definition["default"]
        ):
            continue
        canonical[name] = value
    return canonical


def _write_bytes(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path.resolve())


def _raise_for_status(response: Any, stage: str) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("detail", response.text)
    except (ValueError, AttributeError):
        detail = response.text
    raise RuntimeError(f"{stage} returned HTTP {response.status_code}: {detail}")


def _merge_existing_candidates(
    payload: dict[str, Any], existing: dict[str, Any]
) -> dict[str, Any]:
    existing_by_id = {
        str(case.get("case_id")): case for case in existing.get("cases", [])
    }
    merged = []
    for case in payload.get("cases", []):
        current = existing_by_id.get(str(case.get("case_id")))
        if current is None:
            merged.append(case)
            continue
        evidence = {
            key: current[key]
            for key in ("candidate", "status", "pending_reason", "candidate_error")
            if key in current
        }
        merged.append({**case, **evidence})
    return {**payload, "cases": merged}


def _trace_versions_current(
    trace_path: Path,
    model_versions: dict[str, tuple[str | None, str | None]],
) -> bool:
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    if trace.get("status") != "ready":
        return False
    for item in trace.get("models", []):
        if item.get("invoked") is not True:
            continue
        expected = model_versions.get(str(item.get("id", "")))
        if expected is None:
            return False
        actual = (item.get("preprocess_version"), item.get("postprocess_version"))
        if actual != expected:
            return False
    return True


def generate(
    payload: dict[str, Any],
    client: TestClient,
    output_root: Path,
    *,
    capability: str | None = None,
    case_ids: set[str] | None = None,
    limit: int | None = None,
    force: bool = False,
    model_versions: dict[str, tuple[str | None, str | None]] | None = None,
    parameter_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated = failed = skipped = reused = 0
    cases: list[dict[str, Any]] = []
    for case in payload.get("cases", []):
        if capability and case.get("capability_id") != capability:
            cases.append(case)
            skipped += 1
            continue
        if case_ids and str(case.get("case_id")) not in case_ids:
            cases.append(case)
            skipped += 1
            continue
        if limit is not None and generated + failed >= limit:
            cases.append(case)
            skipped += 1
            continue
        case_id = str(case["case_id"])
        case_root = output_root / case_id
        source = Path(str(case.get("input", {}).get("path", "")))
        preview_file = case_root / "preview.png"
        export_file = case_root / "export.png"
        trace_file = case_root / "execution.json"
        if (
            not force
            and preview_file.is_file()
            and export_file.is_file()
            and trace_file.is_file()
            and (
                model_versions is None
                or _trace_versions_current(trace_file, model_versions)
            )
        ):
            cases.append(
                {
                    **case,
                    "candidate": {
                        "preview": str(preview_file.resolve()),
                        "export": str(export_file.resolve()),
                        "execution": str(trace_file.resolve()),
                    },
                    "status": "pending-reference",
                    "pending_reason": "Luminar reference output is not attached",
                }
            )
            generated += 1
            reused += 1
            continue
        try:
            if not source.is_file():
                raise FileNotFoundError(f"input is missing: {source}")
            with source.open("rb") as handle:
                uploaded = client.post(
                    "/api/v1/assets",
                    files={"file": (source.name, handle, "image/jpeg")},
                )
            _raise_for_status(uploaded, "upload")
            project_id = str(uploaded.json()["project_id"])
            parameters = dict(case.get("parameters", {}))
            if parameter_schema is not None:
                parameters = _canonical_case_parameters(
                    str(case["capability_id"]), parameters, parameter_schema
                )
            if case.get("asset_id") and not parameters.get("asset_id"):
                parameters["asset_id"] = case["asset_id"]
            edited = client.post(
                f"/api/v1/projects/{project_id}/edits",
                json={
                    "effect": case["capability_id"],
                    "parameters": parameters,
                    "enabled": True,
                },
            )
            _raise_for_status(edited, "add-edit")
            preview = client.post(f"/api/v1/projects/{project_id}/preview")
            _raise_for_status(preview, "preview")
            exported = client.post(f"/api/v1/projects/{project_id}/export")
            _raise_for_status(exported, "export")
            trace_response = client.get(f"/api/v1/projects/{project_id}/execution")
            _raise_for_status(trace_response, "execution-trace")
            preview_path = _write_bytes(case_root / "preview.png", preview.content)
            export_path = _write_bytes(case_root / "export.png", exported.content)
            trace_path = case_root / "execution.json"
            trace_path.write_text(
                json.dumps(trace_response.json(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            updated = {
                **case,
                "candidate": {
                    "preview": preview_path,
                    "export": export_path,
                    "execution": str(trace_path.resolve()),
                },
                "status": "pending-reference",
                "pending_reason": "Luminar reference output is not attached",
            }
            generated += 1
        except Exception as exc:  # noqa: BLE001 - one failed case must not abort the evidence batch
            updated = {
                **case,
                "candidate": {"preview": None, "export": None},
                "status": "candidate-failed",
                "candidate_error": f"{type(exc).__name__}: {exc}",
            }
            failed += 1
        cases.append(updated)
    return {
        **payload,
        "version": "1.0",
        "generated_by": "scripts/generate_candidate_outputs.py",
        "candidate_summary": {
            "generated": generated,
            "failed": failed,
            "skipped": skipped,
            "reused": reused,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capability")
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenerate selected candidate evidence even when all files exist",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    cases_path = (args.cases or profile.cases_path).resolve()
    output_root = (args.output_root or profile.diagnostics_root / "candidate-outputs").resolve()
    output = (args.output or profile.diagnostics_root / "parity-cases-candidates.json").resolve()
    workspace = output_root / "workspace"
    os.environ["ZPIXEL_DATA_ROOT"] = str(workspace)
    os.environ.setdefault("ZPIXEL_EXECUTION_MODE", "development")
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    parameter_schema = json.loads(
        (ROOT / "configs/capabilities/parameter-schema.json").read_text(
            encoding="utf-8"
        )
    )
    registry = ModelRegistry.from_yaml((ROOT / "configs/model.yaml").resolve())
    model_versions = {
        record.id: (record.preprocess_version, record.postprocess_version)
        for record in registry.records.values()
    }
    if output.is_file() and (args.capability or args.case_ids or args.limit is not None):
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            existing = {}
        payload = _merge_existing_candidates(payload, existing)
    with TestClient(create_app()) as client:
        report = generate(
            payload,
            client,
            output_root,
            capability=args.capability,
            case_ids=set(args.case_ids or []),
            limit=args.limit,
            force=args.force,
            model_versions=model_versions,
            parameter_schema=parameter_schema,
        )
    report["reference_id"] = profile.id
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = report["candidate_summary"]
    print(json.dumps({**summary, "output": str(output)}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
