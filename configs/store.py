"""Load project configuration once and apply supported environment overrides."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.capabilities import CapabilitySchema
from core.execution import CapabilityExecutionGraph, ExecutionMode, ExecutionPolicy

from .schemas import AppConfig, PathConfig, RuntimeConfig


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"required configuration is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON configuration: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"configuration root must be an object: {path}")
    return payload


def _path(value: str, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def load_config(project_root: Path | None = None) -> AppConfig:
    root = (project_root or Path.cwd()).resolve()
    app_payload = _json(root / "configs/app.json")
    runtime_payload = _json(root / "configs/runtime.json")
    policy_payload = _json(root / "configs/capabilities/policy.json")
    graph_payload = _json(root / "configs/capabilities/execution-graphs.json")
    preset_payload = _json(root / "configs/presets/free.json")
    ui_payload = _json(root / "configs/ui/editor.json")

    configured_paths = app_payload["paths"]
    paths = PathConfig(
        data_root=_path(os.environ.get("ZPIXEL_DATA_ROOT", configured_paths["data_root"]), root),
        asset_root=_path(os.environ.get("ZPIXEL_ASSET_ROOT", configured_paths["asset_root"]), root),
        model_root=_path(os.environ.get("ZPIXEL_MODEL_ROOT", configured_paths["model_root"]), root),
        parameter_schema=_path(
            os.environ.get("ZPIXEL_PARAMETER_SCHEMA", configured_paths["parameter_schema"]), root
        ),
        model_manifest=_path(
            os.environ.get("ZPIXEL_MODEL_MANIFEST", configured_paths["model_manifest"]), root
        ),
        capability_manifest=_path(
            os.environ.get(
                "ZPIXEL_CAPABILITY_MANIFEST", configured_paths["capability_manifest"]
            ),
            root,
        ),
    )
    mode = ExecutionMode.parse(
        os.environ.get("ZPIXEL_PARITY_MODE", runtime_payload["execution_mode"])
    )
    openvino_value = os.environ.get("ZPIXEL_ENABLE_OPENVINO")
    if openvino_value is None:
        openvino = runtime_payload["openvino"]
    elif openvino_value.strip().lower() in {"1", "true", "yes", "on"}:
        openvino = "enabled"
    else:
        openvino = "disabled"
    cache_value = os.environ.get("ZPIXEL_OPENVINO_CACHE_DIR")
    runtime = RuntimeConfig(
        execution_mode=mode,
        model_cache_mb=int(os.environ.get("ZPIXEL_MODEL_CACHE_MB", runtime_payload["model_cache_mb"])),
        openvino=openvino,
        openvino_cache_dir=_path(cache_value, root) if cache_value else None,
        log_level=os.environ.get("ZPIXEL_LOG_LEVEL", runtime_payload["log_level"]),
    )
    policy = ExecutionPolicy(
        **{key: frozenset(value) for key, value in policy_payload.items()}
    )
    graphs = {
        item["capability_id"]: CapabilityExecutionGraph(
            capability_id=item["capability_id"],
            implementation=item.get("implementation", "deterministic"),
            required_models=tuple(item.get("required_models", ())),
            conditional_models=tuple(item.get("conditional_models", ())),
        )
        for item in graph_payload["graphs"]
    }
    preset_sources = {
        (
            str(item.get("source", {}).get("version", "")),
            str(item.get("source", {}).get("build", "")),
        )
        for item in preset_payload["presets"]
    }
    if len(preset_sources) != 1 or any(not value for value in next(iter(preset_sources))):
        raise ValueError("preset configuration must have one version-locked source")
    preset_version, preset_build = next(iter(preset_sources))
    return AppConfig(
        paths=paths,
        runtime=runtime,
        policy=policy,
        execution_graphs=graphs,
        presets=tuple(preset_payload["presets"]),
        preset_source={
            "reference_id": str(preset_payload.get("reference_id", "")),
            "version": preset_version,
            "build": preset_build,
        },
        ui=ui_payload,
    )


def resolve_openvino(runtime: RuntimeConfig) -> tuple[bool, str]:
    if _running_under_rosetta():
        return False, "rosetta-openvino-unsupported-use-native-arm64-python"
    if runtime.openvino == "disabled":
        return False, "disabled-by-configuration"
    if runtime.openvino == "enabled":
        return True, "explicitly-enabled"
    if sys.platform == "darwin":
        return False, "macos-requires-explicit-compatible-runtime"
    return True, "auto-enabled-on-non-macos"


def _running_under_rosetta() -> bool:
    """Return whether this process is x86 translated on Apple Silicon."""
    if sys.platform != "darwin" or platform.machine().lower() not in {"x86_64", "amd64"}:
        return False
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0:
        return result.stdout.strip() == "1"
    try:
        arm_probe = subprocess.run(
            ["/usr/bin/arch", "-arm64", "/usr/bin/uname", "-m"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return arm_probe.returncode == 0 and arm_probe.stdout.strip() == "arm64"


def load_capability_schema(path: Path) -> CapabilitySchema:
    return CapabilitySchema(_json(path))
