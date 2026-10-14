"""Thread-safe lazy model loader with bounded LRU eviction."""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any

from .base_inference import BaseInference
from .factory import create_inference
from .registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    model: BaseInference
    memory_mb: int
    loaded_at: float
    last_used_at: float
    use_count: int = 0
    active_leases: int = 0


class ModelLoader:
    """Load each registered wrapper once and release only inactive LRU entries."""

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        max_memory_mb: int = 2048,
        factory: Callable[..., BaseInference] = create_inference,
    ) -> None:
        self.registry = registry
        self.max_memory_mb = max_memory_mb
        self.factory = factory
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()

    def load_model(self, model_id: str) -> BaseInference:
        with self._lock:
            return self._load_model_locked(model_id)

    @contextmanager
    def lease_model(self, model_id: str) -> Iterator[BaseInference]:
        with self._lock:
            model = self._load_model_locked(model_id)
            entry = self._cache[model_id]
            entry.active_leases += 1
        try:
            yield model
        finally:
            with self._lock:
                entry = self._cache.get(model_id)
                if entry is not None:
                    entry.active_leases = max(0, entry.active_leases - 1)
                    self._touch(model_id, entry)

    def unload_model(self, model_id: str) -> bool:
        with self._lock:
            entry = self._cache.get(model_id)
            if entry is None or entry.active_leases:
                return False
            self._cache.pop(model_id)
            entry.model.unload_model()
            return True

    def clear(self) -> int:
        with self._lock:
            unloaded = 0
            for model_id in list(self._cache):
                if self.unload_model(model_id):
                    unloaded += 1
            return unloaded

    def loaded_ids(self) -> list[str]:
        with self._lock:
            return list(self._cache)

    def loaded_models(self) -> dict[str, BaseInference]:
        with self._lock:
            return {model_id: entry.model for model_id, entry in self._cache.items()}

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "loaded": self.loaded_ids(),
                "max_memory_mb": self.max_memory_mb,
                "estimated_memory_mb": sum(entry.memory_mb for entry in self._cache.values()),
                "active_leases": sum(entry.active_leases for entry in self._cache.values()),
            }

    def _touch(self, model_id: str, entry: CacheEntry) -> None:
        entry.last_used_at = monotonic()
        entry.use_count += 1
        self._cache.move_to_end(model_id)

    def _load_model_locked(self, model_id: str) -> BaseInference:
        cached = self._cache.get(model_id)
        if cached is not None:
            self._touch(model_id, cached)
            return cached.model
        record = self.registry.require(model_id)
        if record.max_memory_mb > self.max_memory_mb:
            raise MemoryError(
                f"model exceeds loader memory budget: {model_id}: "
                f"{record.max_memory_mb}MB > {self.max_memory_mb}MB"
            )
        self._evict_until_available(record.max_memory_mb)
        if self._memory_used() + record.max_memory_mb > self.max_memory_mb:
            raise MemoryError(
                f"no inactive models can be evicted for: {model_id}: "
                f"required={record.max_memory_mb}MB, used={self._memory_used()}MB, "
                f"budget={self.max_memory_mb}MB"
            )
        model = self.factory(record)
        try:
            model.load_model()
            if not model.is_loaded:
                raise RuntimeError(f"model did not report loaded state: {model_id}")
        except Exception:
            try:
                model.unload_model()
            except Exception as unload_error:  # noqa: BLE001 - preserve load failure
                logger.warning("partial model cleanup failed: %s: %s", model_id, unload_error)
            raise
        now = monotonic()
        self._cache[model_id] = CacheEntry(
            model=model,
            memory_mb=record.max_memory_mb,
            loaded_at=now,
            last_used_at=now,
            use_count=1,
        )
        return model

    def _evict_until_available(self, required_mb: int) -> None:
        while self._cache and self._memory_used() + required_mb > self.max_memory_mb:
            candidate_id = next(
                (model_id for model_id, entry in self._cache.items() if entry.active_leases == 0),
                None,
            )
            if candidate_id is None:
                break
            self.unload_model(candidate_id)

    def _memory_used(self) -> int:
        return sum(entry.memory_mb for entry in self._cache.values())
