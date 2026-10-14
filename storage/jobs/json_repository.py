"""Atomic, lease-based JSON repository for local inference workers."""

from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.errors import JobNotFoundError
from core.jobs import InferenceJob


class JsonInferenceJobRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.root / ".claim.lock"

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def get(self, job_id: str) -> InferenceJob:
        path = self._path(job_id)
        if not path.is_file():
            raise JobNotFoundError(f"inference job not found: {job_id}")
        return InferenceJob.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[InferenceJob]:
        jobs: list[InferenceJob] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                jobs.append(
                    InferenceJob.from_dict(json.loads(path.read_text(encoding="utf-8")))
                )
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        return jobs

    def find_by_request_key(self, request_key: str) -> InferenceJob | None:
        return next(
            (
                job
                for job in reversed(self.list())
                if job.request_key == request_key
                and job.status not in {"failed", "cancelled"}
            ),
            None,
        )

    def latest_for_project(self, project_id: str) -> InferenceJob | None:
        matching = [job for job in self.list() if job.project_id == project_id]
        return max(matching, key=lambda job: (job.created_at, job.id), default=None)

    def save(self, job: InferenceJob) -> None:
        with self._claim_lock():
            self._save_unlocked(job)

    def _save_unlocked(self, job: InferenceJob) -> None:
        path = self._path(job.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(job.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @contextmanager
    def _claim_lock(self) -> Iterator[None]:
        with self.lock_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def claim_next(self, worker_id: str, *, lease_seconds: int) -> InferenceJob | None:
        with self._claim_lock():
            now = datetime.now(UTC)
            candidates = []
            for job in self.list():
                expired = (
                    job.status == "running"
                    and job.lease_expires_at is not None
                    and datetime.fromisoformat(job.lease_expires_at) <= now
                )
                if job.status == "queued" or expired:
                    candidates.append(job)
            if not candidates:
                return None
            job = min(candidates, key=lambda item: item.created_at)
            job.status = "running"
            job.lease_owner = worker_id
            job.updated_at = now.isoformat()
            job.lease_expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
            self._save_unlocked(job)
            return job

    def heartbeat(
        self, job: InferenceJob, *, lease_seconds: int
    ) -> InferenceJob | None:
        """Checkpoint only while this worker still owns a running job."""
        with self._claim_lock():
            current = self.get(job.id)
            if (
                current.status != "running"
                or current.lease_owner != job.lease_owner
            ):
                return None
            now = datetime.now(UTC)
            current.completed_models = job.completed_models
            current.error = job.error
            current.updated_at = now.isoformat()
            current.lease_expires_at = (
                now + timedelta(seconds=lease_seconds)
            ).isoformat()
            self._save_unlocked(current)
            return current

    def cancel(self, job_id: str) -> InferenceJob:
        with self._claim_lock():
            job = self.get(job_id)
            if job.status in {"succeeded", "completed", "failed", "cancelled"}:
                return job
            job.status = "cancelled"
            job.updated_at = datetime.now(UTC).isoformat()
            job.lease_owner = None
            job.lease_expires_at = None
            self._save_unlocked(job)
            return job

    def finish(self, job: InferenceJob, *, status: str, error: str | None = None) -> InferenceJob:
        """Publish a terminal state unless ownership was cancelled or superseded."""
        with self._claim_lock():
            current = self.get(job.id)
            if (
                current.status != "running"
                or current.lease_owner != job.lease_owner
            ):
                return current
            current.completed_models = job.completed_models
            current.status = status
            current.error = error
            current.updated_at = datetime.now(UTC).isoformat()
            current.lease_owner = None
            current.lease_expires_at = None
            self._save_unlocked(current)
            return current
