from pathlib import Path

import pytest

from configs.reference import load_reference_catalog
from scripts.run_quality_gates import build_gates, run


def test_functional_gates_do_not_claim_exact_parity() -> None:
    ids = {gate.id for gate in build_gates("functional")}

    assert "sky-e2e" in ids
    assert "overlay-e2e" in ids
    assert "dataset-freshness" in ids
    assert "product-scope" in ids
    assert "luminar-reference-captures" not in ids
    assert "output-parity" not in ids


def test_exact_gates_include_blackbox_output_and_ui() -> None:
    gates = build_gates("exact")
    ids = {gate.id for gate in gates}

    assert {
        "luminar-reference-captures",
        "build-exact-parity-cases",
        "generate-output-candidates",
        "output-parity",
        "generate-exact-incremental-candidates",
        "exact-incremental-data-chain",
        "exact-incremental-parity",
        "ui-parity",
        "interaction-contract-definition",
        "interaction-execution",
        "native-persistence-roundtrip",
        "model-contract-inventory",
        "openvino-runtime",
        "model-validation-matrix",
        "invalid-reference-registry",
    } <= ids
    model_invocations = next(
        gate for gate in gates if gate.id == "candidate-model-invocations"
    )
    assert "--require-active-contracts" in model_invocations.command
    assert gates.index(output_generation := next(
        gate for gate in gates if gate.id == "generate-output-candidates"
    )) < gates.index(model_invocations)
    assert model_invocations.command[model_invocations.command.index("--cases") + 1] == (
        output_generation.command[output_generation.command.index("--output") + 1]
    )
    inventory = next(gate for gate in gates if gate.id == "model-contract-inventory")
    assert inventory.required is True
    runtime_probe_index = inventory.command.index("--runtime-probe") + 1
    assert inventory.command[runtime_probe_index].endswith(
        "openvino-ir-runtime-probe.json"
    )
    matrix = next(gate for gate in gates if gate.id == "model-validation-matrix")
    assert "--require-exact" in matrix.command
    assert next(gate for gate in gates if gate.id == "release-fingerprint").required
    capture = next(gate for gate in gates if gate.id == "luminar-reference-captures")
    active_reference = load_reference_catalog().active_reference
    assert active_reference in capture.command
    assert not any("1.25" in item or "21065" in item for item in capture.command)
    exact_chain = next(
        gate for gate in gates if gate.id == "exact-incremental-data-chain"
    )
    assert any(
        item.endswith("sampling-queue-exact-incremental.json")
        for item in exact_chain.command
    )
    exact_parity = next(
        gate for gate in gates if gate.id == "exact-incremental-parity"
    )
    assert any(
        item.endswith("candidate-outputs-exact-incremental")
        for item in exact_parity.command
    )
    output_parity = next(gate for gate in gates if gate.id == "output-parity")
    assert output_generation.command[output_generation.command.index("--output-root") + 1] == (
        output_parity.command[output_parity.command.index("--candidate-root") + 1]
    )
    incremental_generation = next(
        gate for gate in gates if gate.id == "generate-exact-incremental-candidates"
    )
    assert incremental_generation.command[
        incremental_generation.command.index("--output-root") + 1
    ] == exact_parity.command[exact_parity.command.index("--candidate-root") + 1]
    case_builder = next(gate for gate in gates if gate.id == "build-exact-parity-cases")
    built_cases = case_builder.command[case_builder.command.index("--output") + 1]
    assert incremental_generation.command[
        incremental_generation.command.index("--cases") + 1
    ] == built_cases
    assert exact_parity.command[exact_parity.command.index("--cases") + 1] == built_cases
    interaction = next(gate for gate in gates if gate.id == "interaction-execution")
    assert interaction.required is True
    persistence = next(
        gate for gate in gates if gate.id == "native-persistence-roundtrip"
    )
    assert persistence.required is False
    assert gates.index(persistence) == gates.index(interaction) + 1
    assert len(gates) == 37


def test_dry_run_is_non_mutating_plan() -> None:
    report = run("exact", dry_run=True, run_id="round-6-test")

    assert report["status"] == "planned"
    assert report["run_id"] == "round-6-test"
    assert all(item["status"] == "planned" for item in report["gates"])


def test_dry_run_routes_reports_to_run_root(tmp_path: Path) -> None:
    report = run(
        "exact", dry_run=True, run_id="isolated", runs_root=tmp_path
    )

    assert report["run_root"] == str(tmp_path / "isolated")
    assert not (tmp_path / "isolated").exists()
    report_paths = [
        Path(gate["command"][gate["command"].index("--output") + 1])
        for gate in report["gates"]
        if "--output" in gate["command"]
    ]
    assert report_paths
    assert all(path.is_relative_to(tmp_path / "isolated") for path in report_paths)


def test_run_refuses_to_overwrite_existing_evidence(tmp_path: Path) -> None:
    (tmp_path / "existing").mkdir()

    with pytest.raises(FileExistsError):
        run("functional", run_id="existing", runs_root=tmp_path)
