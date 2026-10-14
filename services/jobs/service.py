"""Checkpoint model analysis and merge it into a project only once at completion."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any

from core.errors import ProjectNotFoundError, WorkflowStateError
from core.jobs import InferenceJob
from services.ports.editing import ArtifactCachePort, ModelServicePort, ProjectRepository
from services.ports.images import ImageReader
from storage.jobs import JsonInferenceJobRepository

DEFAULT_MODELS = [
    "face_detector_retinaface",
    "salient_object_improve_exp19_it150k",
    "MulticlassSegmentationV2",
    "SemanticSearchImage",
    "DepthAnythingV2SmallOpenVino",
    "improved_sky_segmentator_v462_i8",
]


class InferenceJobService:
    def __init__(
        self,
        *,
        repository: JsonInferenceJobRepository,
        projects: ProjectRepository,
        images: ImageReader,
        models: ModelServicePort,
        artifacts: ArtifactCachePort,
        lease_seconds: int = 3600,
    ) -> None:
        self.repository = repository
        self.projects = projects
        self.images = images
        self.models = models
        self.artifacts = artifacts
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.lease_seconds = lease_seconds

    def enqueue(
        self,
        project_id: str,
        requested_models: list[str] | None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        try:
            state = self.projects.load(project_id)
        except FileNotFoundError as exc:
            raise ProjectNotFoundError(project_id) from exc
        source_hash = self.artifacts.source_hash(state.source.path)
        requested = list(dict.fromkeys(requested_models or DEFAULT_MODELS))
        if not requested:
            raise WorkflowStateError("inference job requires at least one model")
        identity = {
            "project_id": project_id,
            "source_hash": source_hash,
            "models": requested,
            "idempotency_key": idempotency_key,
        }
        request_key = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = self.repository.find_by_request_key(request_key)
        if existing:
            return existing.to_dict()
        now = datetime.now(UTC).isoformat()
        job = InferenceJob(
            id=uuid.uuid4().hex,
            project_id=project_id,
            source_hash=source_hash,
            requested_models=requested,
            request_key=request_key,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self.repository.save(job)
        return job.to_dict()

    def get(self, job_id: str) -> dict[str, Any]:
        return self.repository.get(job_id).to_dict()

    def latest(self, project_id: str) -> dict[str, Any] | None:
        job = self.repository.latest_for_project(project_id)
        return job.to_dict() if job is not None else None

    def result(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get(job_id)
        return {
            "job_id": job.id,
            "project_id": job.project_id,
            "status": job.status,
            "complete": job.status in {"succeeded", "completed", "failed", "cancelled"},
            "models": job.completed_models,
            "error": job.error,
        }

    def cancel(self, job_id: str) -> dict[str, Any]:
        return self.repository.cancel(job_id).to_dict()

    def run_next(self, worker_id: str) -> dict[str, Any] | None:
        job = self.repository.claim_next(worker_id, lease_seconds=self.lease_seconds)
        if job is None:
            return None
        try:
            state = self.projects.load(job.project_id)
            if self.artifacts.source_hash(state.source.path) != job.source_hash:
                raise WorkflowStateError("project source changed after job creation")
            for model_id in job.requested_models:
                current = self.repository.get(job.id)
                if current.status == "cancelled":
                    return current.to_dict()
                job = current
                if model_id in job.completed_models:
                    continue
                try:
                    with (
                        self._maintain_lease(job) as lease_lost,
                        self.images.open(state.source.path) as image,
                    ):
                        output = self.models.analyze(
                            image,
                            [model_id],
                            artifact_cache=self.artifacts,
                            source_hash=job.source_hash,
                        )
                    if lease_lost.is_set():
                        return self.repository.get(job.id).to_dict()
                    job.completed_models[model_id] = self._with_integrity(output)
                except Exception as exc:  # noqa: BLE001 - checkpoint every model failure
                    job.completed_models[model_id] = {
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                checkpoint = self.repository.heartbeat(
                    job, lease_seconds=self.lease_seconds
                )
                if checkpoint is None:
                    return self.repository.get(job.id).to_dict()
                job = checkpoint
            has_errors = any(self._output_has_errors(output) for output in job.completed_models.values())
            self._merge_project(
                job,
                state,
                analysis_status="completed-with-errors" if has_errors else "ready",
            )
            job = self.repository.finish(
                job, status="completed" if has_errors else "succeeded"
            )
        except Exception as exc:  # noqa: BLE001 - terminal infrastructure failure
            job = self.repository.finish(
                job,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        return job.to_dict()

    @contextmanager
    def _maintain_lease(self, job: InferenceJob):
        """Keep ownership alive while one model performs a long inference."""

        stop = Event()
        lease_lost = Event()
        interval = max(0.05, min(30.0, self.lease_seconds / 3.0))

        def renew() -> None:
            while not stop.wait(interval):
                if self.repository.heartbeat(
                    job, lease_seconds=self.lease_seconds
                ) is None:
                    lease_lost.set()
                    return

        thread = Thread(target=renew, name=f"inference-lease-{job.id}", daemon=True)
        thread.start()
        try:
            yield lease_lost
        finally:
            stop.set()
            thread.join(timeout=interval + 0.1)

    def _with_integrity(self, output: dict[str, Any]) -> dict[str, Any]:
        for result in output.values():
            if not isinstance(result, dict) or not result.get("artifact_path"):
                continue
            path = self.artifacts.root / str(result["artifact_path"])
            if path.is_file():
                result["artifact_sha256"] = self._sha256(path)
                result["artifact_size"] = path.stat().st_size
        return output

    def _merge_project(
        self, job: InferenceJob, state: Any, *, analysis_status: str
    ) -> None:
        merged: dict[str, Any] = {}
        for output in job.completed_models.values():
            merged.update(output)
        state.metadata["analysis_source_hash"] = job.source_hash
        state.metadata["onnx_analysis"] = merged
        state.metadata["analysis_job_id"] = job.id
        state.metadata["analysis_status"] = analysis_status
        state.metadata["analysis_cache"] = {
            "root": str(self.artifacts.root),
            "records": len(self.artifacts.list_records()),
        }
        self.projects.save(job.project_id, state)

    @staticmethod
    def _output_has_errors(output: dict[str, Any]) -> bool:
        if output.get("status") in {"failed", "blocked"}:
            return True
        return any(
            isinstance(result, dict)
            and result.get("status") in {"failed", "blocked"}
            for result in output.values()
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
