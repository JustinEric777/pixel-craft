"""Infrastructure adapter around the existing edit graph implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.execution import CapabilityExecutionGraph
from core.project.entities import ProjectState
from image_ops.effects.graph import render_project


class EditGraphRenderer:
    def __init__(self, execution_graphs: dict[str, CapabilityExecutionGraph]) -> None:
        self.execution_graphs = execution_graphs

    def render(self, state: ProjectState, *, asset_root: Path, model_service: Any) -> Any:
        return render_project(
            state,
            asset_root=asset_root,
            model_service=model_service,
            execution_graphs=self.execution_graphs,
        )
