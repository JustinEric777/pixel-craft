import time
from datetime import UTC, datetime

from core.jobs import InferenceJob
from services.jobs.service import InferenceJobService
from storage.jobs import JsonInferenceJobRepository


def test_long_model_keeps_worker_lease_alive(tmp_path) -> None:
    repository = JsonInferenceJobRepository(tmp_path / "jobs")
    now = datetime.now(UTC).isoformat()
    repository.save(
        InferenceJob(
            id="job-1",
            project_id="project-1",
            source_hash="source-hash",
            requested_models=["slow-model"],
            request_key="request-key",
            status="queued",
            created_at=now,
            updated_at=now,
        )
    )
    claimed = repository.claim_next("worker-1", lease_seconds=0.09)
    assert claimed is not None
    service = InferenceJobService(
        repository=repository,
        projects=None,  # type: ignore[arg-type]
        images=None,  # type: ignore[arg-type]
        models=None,  # type: ignore[arg-type]
        artifacts=None,  # type: ignore[arg-type]
        lease_seconds=0.09,
    )

    with service._maintain_lease(claimed):
        time.sleep(0.14)
        assert repository.claim_next("worker-2", lease_seconds=1) is None


def test_inference_service_rejects_nonpositive_lease(tmp_path) -> None:
    repository = JsonInferenceJobRepository(tmp_path / "jobs")

    try:
        InferenceJobService(
            repository=repository,
            projects=None,  # type: ignore[arg-type]
            images=None,  # type: ignore[arg-type]
            models=None,  # type: ignore[arg-type]
            artifacts=None,  # type: ignore[arg-type]
            lease_seconds=0,
        )
    except ValueError as exc:
        assert str(exc) == "lease_seconds must be positive"
    else:
        raise AssertionError("nonpositive leases must fail closed")
