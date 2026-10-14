"""Run reproducible functional or exact Luminar parity quality gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from configs.reference import load_reference_catalog

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class Gate:
    id: str
    command: tuple[str, ...]
    required: bool = True


def _scope_policy(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"parity configuration root must be an object: {path}")
    policy = payload.get("scope_policy", {})
    if not isinstance(policy, dict):
        raise TypeError(f"scope_policy must be an object: {path}")
    return policy


def build_gates(
    level: str,
    *,
    reference_id: str | None = None,
    reference_config: Path | None = None,
    output_root: Path | None = None,
    parity_config: Path | None = None,
) -> list[Gate]:
    config_path = (reference_config or ROOT / "configs/reference.yaml").resolve()
    profile = load_reference_catalog(config_path, project_root=ROOT).resolve(reference_id)
    python = sys.executable
    reference_args = ("--reference-config", str(config_path), "--reference-id", profile.id)
    diagnostics = profile.diagnostics_root
    reports = (output_root or diagnostics).resolve()
    policy = _scope_policy((parity_config or ROOT / "configs/parity.yaml").resolve())
    gates = (
        [
            Gate(
                "release-fingerprint",
                (
                    python,
                    "scripts/build_release_fingerprint.py",
                    *reference_args,
                    "--output",
                    str(reports / "release-fingerprint.json"),
                ),
            )
        ]
        if level == "exact"
        else []
    )
    gates.extend([
        Gate(
            "dataset-freshness",
            (
                python,
                "scripts/validate_dataset_freshness.py",
                *reference_args,
                "--output",
                str(reports / "dataset-freshness.json"),
            ),
        ),
        Gate("backend-tests", (python, "-m", "pytest", "-q")),
        Gate("python-lint", (str(Path(python).parent / "ruff"), "check", ".")),
        Gate("frontend-tests", ("npm", "test", "--", "--run")),
        Gate("frontend-build", ("npm", "run", "build")),
        Gate(
            "free-capability-coverage",
            (
                python,
                "scripts/validate_free_capability_coverage.py",
                *reference_args,
                "--output",
                str(reports / "free-capability-coverage.json"),
            ),
        ),
        *(
            [
                Gate(
                    "absolute-scope-coverage",
                    (
                        python,
                        "scripts/validate_absolute_scope_coverage.py",
                        *reference_args,
                        "--output",
                        str(reports / "absolute-scope-coverage.json"),
                    ),
                )
            ]
            if level == "exact"
            else []
        ),
        Gate(
            "product-scope",
            (
                python,
                "scripts/validate_product_scope.py",
                "--cases",
                str(profile.cases_path),
                "--output",
                str(reports / "product-scope.json"),
            ),
        ),
        Gate(
            "runtime-policy",
            (
                python,
                "scripts/validate_runtime_policy.py",
                "--output",
                str(reports / "runtime-policy.json"),
            ),
        ),
        Gate(
            "luminar-catalog-schema",
            (
                python,
                "scripts/validate_luminar_catalog_schema.py",
                "--output",
                str(reports / "luminar-catalog-schema.json"),
            ),
        ),
        Gate(
            "model-source-map",
            (
                python,
                "scripts/build_model_source_map.py",
                *reference_args,
                "--output",
                str(reports / "model-source-map.json"),
                *(("--require-exact",) if level == "exact" else ()),
            ),
        ),
        Gate("model-module", (python, ".agents/skills/ai-model-inference/scripts/validate_model_module.py", "--project-root", ".", "--model-dir", "ai/model")),
        Gate(
            "openvino-runtime",
            (
                python,
                "scripts/probe_openvino_ir.py",
                "--output",
                str(reports / "openvino-ir-runtime-probe.json"),
            ),
        ),
        Gate(
            "model-contract-inventory",
            (
                python,
                "scripts/check_model_contracts.py",
                "--runtime-probe",
                str(reports / "openvino-ir-runtime-probe.json"),
                "--output",
                str(reports / "model-contract-audit.json"),
            ),
            required=level == "exact",
        ),
        *(
            [
                Gate(
                    "generate-output-candidates",
                    (
                        python,
                        "scripts/generate_candidate_outputs.py",
                        *reference_args,
                        "--output-root",
                        str(reports / "candidate-outputs"),
                        "--output",
                        str(reports / "candidate-generation.json"),
                        "--force",
                    ),
                )
            ]
            if level == "exact"
            else []
        ),
        Gate(
            "candidate-model-invocations",
            (
                python,
                "scripts/audit_candidate_model_invocations.py",
                *reference_args,
                *(
                    (
                        "--cases",
                        str(reports / "candidate-generation.json"),
                        "--model-source-map",
                        str(reports / "model-source-map.json"),
                    )
                    if level == "exact"
                    else ()
                ),
                "--output",
                str(reports / "candidate-model-invocations.json"),
                *(("--require-active-contracts",) if level == "exact" else ()),
            ),
        ),
        Gate(
            "model-validation-matrix",
            (
                python,
                "scripts/build_model_validation_matrix.py",
                "--source-map",
                str(reports / "model-source-map.json"),
                "--invocations",
                str(reports / "candidate-model-invocations.json"),
                "--runtime-probe",
                str(reports / "openvino-ir-runtime-probe.json"),
                "--output",
                str(reports / "model-validation-matrix.json"),
                *(("--require-exact",) if level == "exact" else ()),
            ),
        ),
        Gate(
            "model-pipelines",
            (
                python,
                "scripts/audit_model_pipelines.py",
                "--output",
                str(reports / "model-pipeline-audit.json"),
            ),
        ),
        Gate(
            "preset-effects",
            (
                python,
                "scripts/run_preset_validation.py",
                "--output",
                str(reports / "preset-validation.json"),
            ),
        ),
        Gate(
            "sky-e2e",
            (
                python,
                "scripts/run_sky_e2e_validation.py",
                *reference_args,
                "--output",
                str(reports / "validation-sky-e2e-report.json"),
            ),
        ),
        Gate(
            "overlay-e2e",
            (
                python,
                "scripts/run_overlay_e2e_validation.py",
                *reference_args,
                "--output",
                str(reports / "overlay-e2e.json"),
            ),
        ),
        Gate(
            "multi-image",
            (
                python,
                "scripts/run_multi_image_workflow_smoke.py",
                "--output",
                str(reports / "multi-image-workflow-smoke.json"),
            ),
        ),
    ])
    if level == "exact":
        gates.extend(
            [
                Gate(
                    "sampling-data-chain",
                    (
                        python,
                        "scripts/validate_sampling_data_chain.py",
                        *reference_args,
                        "--output",
                        str(reports / "sampling-data-chain.json"),
                    ),
                ),
                Gate(
                    "exact-incremental-data-chain",
                    (
                        python,
                        "scripts/validate_sampling_data_chain.py",
                        *reference_args,
                        "--queue",
                        str(diagnostics / "sampling-queue-exact-incremental.json"),
                        "--output",
                        str(reports / "exact-incremental-data-chain.json"),
                    ),
                ),
                Gate(
                    "sampling-queue-evidence",
                    (
                        python,
                        "scripts/validate_sampling_queue_captures.py",
                        *reference_args,
                        "--output",
                        str(reports / "sampling-queue-evidence.json"),
                    ),
                ),
                Gate(
                    "invalid-reference-registry",
                    (
                        python,
                        "scripts/validate_invalid_references.py",
                        *reference_args,
                        "--output",
                        str(reports / "invalid-reference-registry.json"),
                    ),
                ),
                Gate(
                    "luminar-reference-captures",
                    (
                        python,
                        "scripts/validate_reference_captures.py",
                        *reference_args,
                        "--output",
                        str(reports / "reference-capture-audit.json"),
                    ),
                ),
                Gate(
                    "build-exact-parity-cases",
                    (
                        python,
                        "scripts/build_exact_parity_cases.py",
                        "--queue",
                        str(diagnostics / "sampling-queue-exact-incremental.json"),
                        "--output",
                        str(reports / "parity-cases-exact-incremental.json"),
                    ),
                ),
                Gate(
                    "output-parity",
                    (
                        python,
                        "scripts/run_parity_suite.py",
                        *reference_args,
                        "--candidate-root",
                        str(reports / "candidate-outputs"),
                        "--output",
                        str(reports / "parity-report.json"),
                    ),
                ),
                Gate(
                    "generate-exact-incremental-candidates",
                    (
                        python,
                        "scripts/generate_candidate_outputs.py",
                        *reference_args,
                        "--cases",
                        str(reports / "parity-cases-exact-incremental.json"),
                        "--output-root",
                        str(reports / "candidate-outputs-exact-incremental"),
                        "--output",
                        str(reports / "exact-incremental-candidate-generation.json"),
                        "--force",
                    ),
                ),
                Gate(
                    "exact-incremental-parity",
                    (
                        python,
                        "scripts/run_parity_suite.py",
                        *reference_args,
                        "--cases",
                        str(reports / "parity-cases-exact-incremental.json"),
                        "--candidate-root",
                        str(reports / "candidate-outputs-exact-incremental"),
                        "--output",
                        str(reports / "exact-incremental-parity.json"),
                    ),
                ),
                Gate(
                    "ui-execution-evidence",
                    (
                        python,
                        "scripts/validate_ui_execution_evidence.py",
                        *reference_args,
                        "--output",
                        str(reports / "ui-execution-evidence.json"),
                    ),
                ),
                Gate(
                    "ui-parity",
                    (
                        python,
                        "scripts/validate_ui_references.py",
                        *reference_args,
                        "--output",
                        str(reports / "ui-parity.json"),
                    ),
                ),
                Gate(
                    "interaction-contract-definition",
                    (
                        python,
                        "scripts/validate_interaction_contracts.py",
                        "--output",
                        str(reports / "interaction-contracts.json"),
                    ),
                ),
                Gate(
                    "interaction-execution",
                    (
                        python,
                        "scripts/validate_interaction_execution.py",
                        *reference_args,
                        "--output",
                        str(reports / "interaction-execution.json"),
                    ),
                ),
                Gate(
                    "native-persistence-roundtrip",
                    (
                        python,
                        "scripts/validate_native_persistence_roundtrip.py",
                        *reference_args,
                        "--output",
                        str(reports / "native-persistence-roundtrip.json"),
                    ),
                    required=bool(policy.get("native_persistence_required", True)),
                ),
            ]
        )
    return gates


def run(
    level: str,
    *,
    dry_run: bool = False,
    reference_id: str | None = None,
    reference_config: Path | None = None,
    run_id: str | None = None,
    runs_root: Path | None = None,
) -> dict[str, object]:
    config_path = (reference_config or ROOT / "configs/reference.yaml").resolve()
    profile = load_reference_catalog(config_path, project_root=ROOT).resolve(reference_id)
    resolved_run_id = run_id or (
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    )
    if not RUN_ID_PATTERN.fullmatch(resolved_run_id):
        raise ValueError(f"invalid run id: {resolved_run_id!r}")
    resolved_runs_root = (runs_root or profile.diagnostics_root / "runs").resolve()
    run_root = resolved_runs_root / resolved_run_id
    if not dry_run:
        run_root.mkdir(parents=True, exist_ok=False)
    records = []
    for gate in build_gates(
        level,
        reference_id=profile.id,
        reference_config=config_path,
        output_root=run_root,
    ):
        cwd = ROOT / "frontend" if gate.id.startswith("frontend-") else ROOT
        if dry_run:
            records.append({**asdict(gate), "cwd": str(cwd), "status": "planned"})
            continue
        progress_path = run_root / "gate-progress.json"
        progress_path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "run_id": resolved_run_id,
                    "current_gate": gate.id,
                    "current_status": "running",
                    "completed": [item["id"] for item in records],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            gate.command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        records.append(
            {
                **asdict(gate),
                "cwd": str(cwd),
                "status": "passed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        )
        progress_path.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "run_id": resolved_run_id,
                    "current_gate": None,
                    "current_status": None,
                    "completed": [
                        {"id": item["id"], "status": item["status"]}
                        for item in records
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    failed = [
        item["id"]
        for item in records
        if item["status"] == "failed" and item["required"]
    ]
    optional_failed = [
        item["id"]
        for item in records
        if item["status"] == "failed" and not item["required"]
    ]
    release_fingerprint: dict[str, object] | None = None
    fingerprint_path = run_root / "release-fingerprint.json"
    if not dry_run and fingerprint_path.is_file():
        fingerprint_report = json.loads(fingerprint_path.read_text(encoding="utf-8"))
        release_fingerprint = {
            "release": fingerprint_report.get("release_fingerprint"),
            **dict(fingerprint_report.get("fingerprints", {})),
        }
    report: dict[str, object] = {
        "version": "1.0",
        "run_id": resolved_run_id,
        "run_root": str(run_root),
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_id": profile.id,
        "reference_version": profile.version,
        "reference_build": profile.build,
        "level": level,
        "dry_run": dry_run,
        "gate_count": len(records),
        "required_gate_count": sum(item["required"] for item in records),
        "optional_gate_count": sum(not item["required"] for item in records),
        "passed": sum(item["status"] == "passed" for item in records),
        "failed": len(failed),
        "failed_gates": failed,
        "optional_failed": len(optional_failed),
        "optional_failed_gates": optional_failed,
        "fingerprints": release_fingerprint,
        "status": "planned" if dry_run else "passed" if not failed else "blocked",
        "gates": records,
    }
    if not dry_run:
        artifacts = []
        for path in sorted(run_root.rglob("*")):
            if not path.is_file() or path.name == "evidence-index.json":
                continue
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            artifacts.append(
                {
                    "path": path.relative_to(run_root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
            )
        (run_root / "evidence-index.json").write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "run_id": resolved_run_id,
                    "reference_id": profile.id,
                    "fingerprints": release_fingerprint,
                    "artifacts": artifacts,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--level", choices=("functional", "exact"), default="functional")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--run-id",
        help="stable identifier linking every report produced by this quality run",
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        help="parent directory for immutable per-run evidence",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    report = run(
        args.level,
        dry_run=args.dry_run,
        reference_id=profile.id,
        reference_config=args.reference_config.resolve(),
        run_id=args.run_id,
        runs_root=args.runs_root,
    )
    output = (
        args.output or Path(str(report["run_root"])) / f"quality-gates-{args.level}.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("run_id", "level", "gate_count", "passed", "failed", "status")
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] in {"passed", "planned"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
