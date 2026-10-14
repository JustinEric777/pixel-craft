"""Framework-neutral pipeline contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BasePipeline(ABC, Generic[InputT, OutputT]):
    @abstractmethod
    def run(self, value: InputT) -> OutputT:
        """Execute one configured inference workflow."""
