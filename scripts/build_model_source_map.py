"""Map portable Luminar model files to registered wrappers and feature consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.model.model_contract import ModelContractCatalog
from ai.model.registry import ModelRegistry
from configs import load_config
from configs.reference import load_reference_catalog
from configs.store import resolve_openvino


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records")
    if isinstance(records, list):
        return [item for item in records if isinstance(item, dict)]
    variants = payload.get("model_variants")
    if not isinstance(variants, list):
        return []
    expanded: list[dict[str, Any]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        relative_path = Path(str(variant.get("relative_path", "")))
        expanded.append(
            {
                "name": relative_path.name,
                "format": variant.get("format"),
                "sha256": variant.get("sha256"),
                "path": relative_path.as_posix(),
            }
        )
        weights_path = Path(str(variant.get("weights_relative_path", "")))
        if weights_path.name:
            expanded.append(
                {
                    "name": weights_path.name,
                    "format": "openvino_ir_weights",
                    "sha256": variant.get("weights_sha256"),
                    "path": weights_path.as_posix(),
                }
            )
    return expanded


def _registry_inventory(registry: ModelRegistry) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for model in registry.records.values():
        if model.path.is_file():
            records.append(
                {
                    "name": model.path.name,
                    "format": model.format,
                    "sha256": _sha256(model.path),
                    "path": str(model.path),
                }
            )
        if model.weights_path is not None and model.weights_path.is_file():
            records.append(
                {
                    "name": model.weights_path.name,
                    "format": "openvino_ir_weights",
                    "sha256": _sha256(model.weights_path),
                    "path": str(model.weights_path),
                }
            )
    return records


def _project_model_inventory(project_root: Path) -> list[dict[str, Any]]:
    formats = {
        ".onnx": "onnx",
        ".ort": "ort",
        ".xml": "openvino_ir",
        ".bin": "openvino_ir_weights",
    }
    model_root = project_root / "models"
    return [
        {
            "name": path.name,
            "format": formats[path.suffix.lower()],
            "sha256": _sha256(path),
            "path": str(path),
        }
        for path in sorted(model_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in formats
    ]


def _class_file(class_path: str, project_root: Path) -> Path:
    module = class_path.partition(":")[0]
    return project_root / (module.replace(".", "/") + ".py")


def _consumer_files(project_root: Path) -> tuple[Path, ...]:
    roots = (project_root / "ai/pipeline", project_root / "configs/capabilities")
    return tuple(
        sorted(
            path
            for root in roots
            if root.is_dir()
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml"}
        )
    )


def build_model_source_map(
    *,
    registry_path: Path,
    portable_inventory_path: Path,
    project_inventory_paths: tuple[Path, ...],
    project_root: Path,
    execution_graph_path: Path,
    ui_config_path: Path,
    contract_root: Path | None = None,
    allow_openvino: bool = False,
    openvino_reason: str = "not-specified",
) -> dict[str, object]:
    registry = ModelRegistry.from_yaml(registry_path)
    contracts = ModelContractCatalog(contract_root or project_root / "models/contracts")
    portable = _load(portable_inventory_path)
    project_records = _project_model_inventory(project_root) + _registry_inventory(registry) + [
        item
        for path in project_inventory_paths
        if path.is_file()
        for item in _inventory_records(_load(path))
    ]
    project_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in project_records:
        project_by_name.setdefault(str(item["name"]), []).append(item)
    ui_config = _load(ui_config_path)
    visible_capabilities = {
        str(capability_id)
        for group in ui_config.get("tool_groups", [])
        for capability_id in group.get("capabilities", [])
    }
    execution_graphs = {
        str(item["capability_id"]): item
        for item in _load(execution_graph_path).get("graphs", [])
    }
    direct_consumers: dict[str, set[str]] = {}
    transitive_consumers: dict[str, set[str]] = {}
    for capability_id in visible_capabilities:
        graph = execution_graphs.get(capability_id, {})
        for model_id in graph.get("required_models", []):
            direct_consumers.setdefault(str(model_id), set()).add(capability_id)
        for model_id in graph.get("conditional_models", []):
            transitive_consumers.setdefault(str(model_id), set()).add(capability_id)
    required_logical_ids = set(direct_consumers) | set(transitive_consumers)
    model_formats = {"onnx", "ort", "openvino_ir", "openvino_ir_weights"}
    source_files = []
    ancillary_source_files = []
    for source in _inventory_records(portable):
        matches = project_by_name.get(str(source["name"]), [])
        project = next(
            (
                item
                for item in matches
                if item.get("sha256") == source.get("sha256")
                and item.get("format") == source.get("format")
            ),
            matches[0] if matches else None,
        )
        status = (
            "exact"
            if project is not None
            and project.get("sha256") == source.get("sha256")
            and project.get("format") == source.get("format")
            else "missing-or-different"
        )
        mapped = {
            "name": source["name"],
            "format": source["format"],
            "sha256": source["sha256"],
            "status": status,
            "project_path": project.get("path") if project else None,
        }
        target = (
            source_files
            if str(source.get("format")) in model_formats
            else ancillary_source_files
        )
        target.append(mapped)

    consumer_files = _consumer_files(project_root)
    consumer_text = {
        path: path.read_text(encoding="utf-8", errors="replace")
        for path in consumer_files
    }
    selected_variants: dict[str, str] = {}
    unresolved_logical_models: list[str] = []
    for logical_id in sorted(required_logical_ids):
        try:
            selected_variants[logical_id] = registry.resolve(
                logical_id, allow_openvino=allow_openvino
            ).id
        except KeyError:
            unresolved_logical_models.append(logical_id)
    models = []
    for record in registry.records.values():
        wrapper = _class_file(record.inference_class, project_root)
        identifiers = {record.id, record.logical_id or record.id}
        consumers = sorted(
            str(path.relative_to(project_root))
            for path, text in consumer_text.items()
            if any(identifier in text for identifier in identifiers)
        )
        artifact_status = "missing"
        if record.path.is_file():
            artifact_status = (
                "exact"
                if record.sha256 and _sha256(record.path) == record.sha256
                else "hash-mismatch"
            )
        weights_status = "not-applicable"
        if record.weights_path is not None:
            weights_status = "missing"
            if record.weights_path.is_file():
                weights_status = (
                    "exact"
                    if record.weights_sha256
                    and _sha256(record.weights_path) == record.weights_sha256
                    else "hash-mismatch"
                )
        contract = contracts.get(record.id)
        contract_specific = bool(
            contract
            and contract.normalization.get("status")
            in {"validated", "model-specific-validated", "parity-validated"}
            and contract.postprocess.get("status")
            in {"validated", "model-specific-validated", "parity-validated"}
        )
        logical_id = record.logical_id or record.id
        if logical_id in direct_consumers:
            product_scope_status = "required-direct"
            product_capabilities = sorted(direct_consumers[logical_id])
        elif logical_id in transitive_consumers:
            product_scope_status = "required-transitive"
            product_capabilities = sorted(transitive_consumers[logical_id])
        else:
            product_scope_status = "inventory-unreachable"
            product_capabilities = []
        models.append(
            {
                "id": record.id,
                "logical_id": record.logical_id,
                "task": record.task,
                "format": record.format,
                "backend": record.backend,
                "artifact": str(record.path),
                "artifact_status": artifact_status,
                "weights": str(record.weights_path) if record.weights_path else None,
                "weights_status": weights_status,
                "inference_class": record.inference_class,
                "wrapper": str(wrapper.relative_to(project_root)),
                "wrapper_status": "present" if wrapper.is_file() else "missing",
                "consumers": consumers,
                "consumer_status": "mapped" if consumers else "unmapped",
                "product_scope_status": product_scope_status,
                "product_capabilities": product_capabilities,
                "runtime_selected": selected_variants.get(logical_id) == record.id,
                "contract_status": (
                    "model-specific" if contract_specific else "pending-model-specific"
                ),
            }
        )
    source_counts = Counter(str(item["status"]) for item in source_files)
    model_counts = Counter(str(item["artifact_status"]) for item in models)
    wrapper_counts = Counter(str(item["wrapper_status"]) for item in models)
    consumer_counts = Counter(str(item["consumer_status"]) for item in models)
    contract_counts = Counter(str(item["contract_status"]) for item in models)
    product_scope_counts = Counter(str(item["product_scope_status"]) for item in models)
    selected_required_models = [
        item
        for item in models
        if item["runtime_selected"]
        and str(item["product_scope_status"]).startswith("required-")
    ]
    selected_contract_counts = Counter(
        str(item["contract_status"]) for item in selected_required_models
    )
    pending_required_models = sorted(
        str(item["id"])
        for item in selected_required_models
        if item["contract_status"] != "model-specific"
    )
    return {
        "version": "1.0",
        "portable_inventory": str(portable_inventory_path),
        "registry": str(registry_path),
        "portable_record_count": len(source_files) + len(ancillary_source_files),
        "source_file_count": len(source_files),
        "ancillary_source_file_count": len(ancillary_source_files),
        "registered_model_count": len(models),
        "source_file_counts": dict(sorted(source_counts.items())),
        "artifact_counts": dict(sorted(model_counts.items())),
        "wrapper_counts": dict(sorted(wrapper_counts.items())),
        "consumer_counts": dict(sorted(consumer_counts.items())),
        "contract_counts": dict(sorted(contract_counts.items())),
        "visible_capability_count": len(visible_capabilities),
        "visible_capabilities": sorted(visible_capabilities),
        "required_logical_model_count": len(required_logical_ids),
        "required_logical_models": sorted(required_logical_ids),
        "selected_variants": dict(sorted(selected_variants.items())),
        "unresolved_logical_models": unresolved_logical_models,
        "runtime": {
            "primary": "onnxruntime",
            "openvino_enabled": allow_openvino,
            "openvino_reason": openvino_reason,
        },
        "product_scope_counts": dict(sorted(product_scope_counts.items())),
        "selected_required_contract_counts": dict(
            sorted(selected_contract_counts.items())
        ),
        "pending_required_models": pending_required_models,
        "source_gate": "passed" if source_counts == {"exact": len(source_files)} else "blocked",
        "registry_gate": (
            "passed"
            if model_counts == {"exact": len(models)}
            and wrapper_counts == {"present": len(models)}
            else "blocked"
        ),
        "exact_behavior_gate": (
            "passed"
            if required_logical_ids
            and not unresolved_logical_models
            and not pending_required_models
            else "blocked"
        ),
        "source_files": source_files,
        "ancillary_source_files": ancillary_source_files,
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/reference.yaml")
    parser.add_argument("--reference-id")
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/model.yaml")
    parser.add_argument("--contract-root", type=Path, default=ROOT / "models/contracts")
    parser.add_argument(
        "--execution-graphs",
        type=Path,
        default=ROOT / "configs/capabilities/execution-graphs.json",
    )
    parser.add_argument(
        "--ui-config", type=Path, default=ROOT / "configs/ui/editor.json"
    )
    parser.add_argument("--portable-inventory", type=Path)
    parser.add_argument("--project-inventory", type=Path, action="append")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-exact",
        action="store_true",
        help="fail unless every model reachable from the frozen product UI resolves to a model-specific runtime contract",
    )
    args = parser.parse_args()
    profile = load_reference_catalog(
        args.reference_config.resolve(), project_root=ROOT
    ).resolve(args.reference_id)
    openvino_enabled, openvino_reason = resolve_openvino(load_config(ROOT).runtime)
    portable = (
        args.portable_inventory
        or profile.diagnostics_root.parent / "inventory" / "install-manifest.json"
    ).resolve()
    project_inventories = tuple(
        path.resolve()
        for path in (
            args.project_inventory
            or [
                profile.diagnostics_root / "project-onnx-inventory.json",
                profile.diagnostics_root / "project-openvino-inventory.json",
            ]
        )
    )
    report = {
        "reference_id": profile.id,
        **build_model_source_map(
            registry_path=args.registry.resolve(),
            portable_inventory_path=portable,
            project_inventory_paths=project_inventories,
            project_root=ROOT,
            execution_graph_path=args.execution_graphs.resolve(),
            ui_config_path=args.ui_config.resolve(),
            contract_root=args.contract_root.resolve(),
            allow_openvino=openvino_enabled,
            openvino_reason=openvino_reason,
        ),
    }
    output = (args.output or profile.diagnostics_root / "model-source-map.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "source_file_count",
                    "registered_model_count",
                    "source_file_counts",
                    "artifact_counts",
                    "wrapper_counts",
                    "consumer_counts",
                    "contract_counts",
                    "product_scope_counts",
                    "required_logical_model_count",
                    "selected_required_contract_counts",
                    "pending_required_models",
                    "source_gate",
                    "registry_gate",
                    "exact_behavior_gate",
                )
            },
            ensure_ascii=False,
        )
    )
    gate = report["exact_behavior_gate"] if args.require_exact else report["registry_gate"]
    return 0 if gate == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
