from copy import deepcopy

from scripts.compare_exact_runs import compare


def _report(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "run_root": f"/runs/{run_id}",
        "reference_id": "luminar-neo-macos-1.28.0-23071",
        "level": "exact",
        "status": "passed",
        "failed": 0,
        "optional_failed": 0,
        "fingerprints": {"release": "same"},
        "gates": [{"id": "gate", "required": True}],
    }


def test_compare_accepts_two_independent_identical_runs() -> None:
    report = compare(_report("one"), _report("two"))

    assert report["status"] == "passed"


def test_compare_blocks_fingerprint_drift() -> None:
    first = _report("one")
    second = deepcopy(_report("two"))
    second["fingerprints"] = {"release": "changed"}

    report = compare(first, second)

    assert report["status"] == "blocked"
    assert {issue["id"] for issue in report["issues"]} == {"fingerprint-mismatch"}
