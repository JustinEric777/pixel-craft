from datetime import UTC, datetime
from pathlib import Path

from core.jobs import InferenceJob
from storage.jobs import JsonInferenceJobRepository


def _job() -> InferenceJob:
    now = datetime.now(UTC).isoformat()
    return InferenceJob(
        id="job-1",
        project_id="project-1",
        source_hash="source",
        requested_models=["model-1"],
        request_key="request",
        status="queued",
        created_at=now,
        updated_at=now,
    )


def test_cancelled_job_cannot_be_resurrected_by_stale_heartbeat(
    tmp_path: Path,
) -> None:
    repository = JsonInferenceJobRepository(tmp_path / "jobs")
    repository.save(_job())
    claimed = repository.claim_next("worker-1", lease_seconds=60)
    assert claimed is not None
    claimed.completed_models["model-1"] = {"status": "ready"}

    cancelled = repository.cancel(claimed.id)
    checkpoint = repository.heartbeat(claimed, lease_seconds=60)

    assert cancelled.status == "cancelled"
    assert checkpoint is None
    assert repository.get(claimed.id).status == "cancelled"


def test_stale_worker_cannot_finish_job_reclaimed_by_another_worker(
    tmp_path: Path,
) -> None:
    repository = JsonInferenceJobRepository(tmp_path / "jobs")
    repository.save(_job())
    stale = repository.claim_next("worker-1", lease_seconds=-1)
    assert stale is not None
    current = repository.claim_next("worker-2", lease_seconds=60)
    assert current is not None

    result = repository.finish(stale, status="succeeded")

    assert result.status == "running"
    assert result.lease_owner == "worker-2"


def test_latest_for_project_is_scoped_and_deterministic(tmp_path: Path) -> None:
    repository = JsonInferenceJobRepository(tmp_path / "jobs")
    first = _job()
    repository.save(first)
    second = _job()
    second.id = "job-2"
    second.created_at = first.created_at + "Z"
    repository.save(second)
    unrelated = _job()
    unrelated.id = "job-3"
    unrelated.project_id = "project-2"
    unrelated.created_at = second.created_at + "Z"
    repository.save(unrelated)

    assert repository.latest_for_project("project-1").id == "job-2"
    assert repository.latest_for_project("missing") is None
