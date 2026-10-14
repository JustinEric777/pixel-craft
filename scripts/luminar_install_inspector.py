"""Read a local Luminar bundle without copying or modifying its resources."""

from __future__ import annotations

import hashlib
import json
import plistlib
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.reference import ModelSourcePolicy, ModelVariant, ReferenceBuild

RESOURCE_RELATIVE = Path(
    "Contents/Frameworks/MIPLResources.framework/Versions/A/Resources"
)
MODEL_SUFFIXES = {".xml", ".onnx", ".ort"}
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
CONFIG_NAMES = {
    "EffectsConfig.json",
    "EffectsLayoutNeo.json",
    "MPEditPanelLayoutConfig.json",
    "MiplToolsParameters.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class LuminarInstallInspector:
    def __init__(self, app_path: Path) -> None:
        self.app_path = app_path.resolve()
        self.resources = self.app_path / RESOURCE_RELATIVE
        self.profiles = self.resources / "profiles"

    def inspect(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        build = self._reference_build()
        variants = self._model_variants(build.id)
        configs = self._config_records()
        preset_collections = self._preset_collections()
        overlay_collections = self._overlay_collections()
        material_counts = self._material_counts(overlay_collections)
        manifest = {
            "version": "1.0.0",
            "generated_by": "LuminarInstallInspector",
            "read_only": True,
            "reference_build": build.__dict__,
            "counts": {
                "model_variants": len(variants),
                "configs": len(configs),
                "onnx": sum(item.format in {"onnx", "ort"} for item in variants),
                "openvino_ir": sum(item.format == "openvino_ir" for item in variants),
                "preset_collections": len(preset_collections),
                "presets": sum(item["preset_count"] for item in preset_collections),
                "presets_declared": sum(
                    item["declared_preset_count"] for item in preset_collections
                ),
                **material_counts,
            },
            "configs": configs,
            "preset_collections": preset_collections,
            "free_overlay_collections": overlay_collections,
            "model_variants": [self._variant_payload(item) for item in variants],
        }
        contracts = self._ui_contract(build)
        lock = {
            "version": "1.0.0",
            "reference_build_id": build.id,
            "app_path": str(self.app_path),
            "resources_path": str(self.resources),
            "model_paths": {
                item.id: str(self.resources / item.relative_path) for item in variants
            },
        }
        return manifest, contracts, lock

    def _reference_build(self) -> ReferenceBuild:
        info_path = self.app_path / "Contents/Info.plist"
        if not info_path.is_file() or not self.resources.is_dir():
            raise FileNotFoundError(f"invalid Luminar installation: {self.app_path}")
        with info_path.open("rb") as handle:
            info = plistlib.load(handle)
        version = str(info.get("CFBundleShortVersionString", "unknown"))
        bundle_version = str(info.get("CFBundleVersion", "unknown"))
        reference_id = f"luminar-neo-macos-{version}-{bundle_version}"
        return ReferenceBuild(
            id=reference_id,
            product=str(info.get("CFBundleName", "Luminar Neo")),
            platform="macOS",
            version=version,
            build=bundle_version,
        )

    def _model_variants(self, reference_id: str) -> list[ModelVariant]:
        variants: list[ModelVariant] = []
        for path in sorted(self.profiles.iterdir()):
            if path.is_file() and path.suffix.lower() in MODEL_SUFFIXES:
                if path.suffix.lower() == ".xml" and path.with_suffix(".bin").is_file():
                    variants.append(
                        self._variant(path, "openvino_ir", "openvino", reference_id)
                    )
                elif path.suffix.lower() in {".onnx", ".ort"}:
                    variants.append(
                        self._variant(path, path.suffix[1:], "onnxruntime", reference_id)
                    )
        return variants

    def _variant(
        self, path: Path, model_format: str, backend: str, reference_id: str
    ) -> ModelVariant:
        logical_id = path.stem
        variant_id = f"{logical_id}:{backend}:{reference_id}"
        return ModelVariant(
            id=variant_id,
            logical_model_id=logical_id,
            format=model_format,
            backend=backend,
            relative_path=str(path.relative_to(self.resources)),
            sha256=sha256_file(path),
            source_policy=ModelSourcePolicy.EXTERNAL_LOCAL_ONLY,
        )

    def _config_records(self) -> list[dict[str, Any]]:
        records = []
        for name in sorted(CONFIG_NAMES):
            path = self.resources / name
            records.append(
                {
                    "name": name,
                    "relative_path": str(path.relative_to(self.resources)),
                    "exists": path.is_file(),
                    "sha256": sha256_file(path) if path.is_file() else None,
                    "size_bytes": path.stat().st_size if path.is_file() else None,
                }
            )
        return records

    def _preset_collections(self) -> list[dict[str, Any]]:
        root = self.resources / "TemplatePacks/Collections"
        if not root.is_dir():
            return []
        records = []
        for path in sorted(root.glob("*/config.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            templates = payload.get("templates", [])
            existing_templates = [
                name
                for name in templates
                if (path.parent / str(name) / "template.lmps").is_file()
            ]
            records.append(
                {
                    "id": str(payload.get("identifier") or path.parent.name),
                    "name": str(payload.get("name") or path.parent.name),
                    "preset_count": len(existing_templates),
                    "declared_preset_count": len(templates),
                    "missing_preset_count": len(templates) - len(existing_templates),
                    "relative_path": str(path.relative_to(self.resources)),
                }
            )
        return records

    def _overlay_collections(self) -> list[dict[str, Any]]:
        root = self.resources / "OverlayTextures/Free"
        if not root.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for config_path in sorted(root.glob("*/config.json")):
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            declared_ids = [str(item) for item in payload.get("items", [])]
            existing_ids = []
            for asset_id in declared_ids:
                item_config_path = config_path.parent / asset_id / "config.json"
                if not item_config_path.is_file():
                    continue
                item_payload = json.loads(item_config_path.read_text(encoding="utf-8"))
                asset_path = item_config_path.parent / str(item_payload.get("path") or "")
                if asset_path.is_file() and asset_path.suffix.lower() in RASTER_SUFFIXES:
                    existing_ids.append(asset_id)
            discovered = {
                path.parent.name
                for path in config_path.parent.glob("*/config.json")
            }
            records.append(
                {
                    "id": str(payload.get("identifier") or config_path.parent.name),
                    "active_item_ids": existing_ids,
                    "active_item_count": len(existing_ids),
                    "declared_item_count": len(declared_ids),
                    "missing_item_count": len(declared_ids) - len(existing_ids),
                    "discovered_item_count": len(discovered),
                    "orphan_item_count": len(discovered - set(declared_ids)),
                    "relative_path": str(config_path.relative_to(self.resources)),
                }
            )
        return records

    def _material_counts(
        self, overlay_collections: list[dict[str, Any]]
    ) -> dict[str, int]:
        sky_root = self.resources / "SkyTextures"
        overlay_root = self.resources / "OverlayTextures/Free"
        return {
            "sky_collections": self._child_directory_count(sky_root),
            "sky_textures": self._raster_count(sky_root),
            "free_overlay_collections": len(overlay_collections),
            "free_overlay_textures": sum(
                item["active_item_count"] for item in overlay_collections
            ),
            "free_overlay_files_discovered": self._raster_count(overlay_root),
            "free_overlay_orphan_items": sum(
                item["orphan_item_count"] for item in overlay_collections
            ),
        }

    @staticmethod
    def _child_directory_count(root: Path) -> int:
        if not root.is_dir():
            return 0
        return sum(path.is_dir() for path in root.iterdir())

    @staticmethod
    def _raster_count(root: Path) -> int:
        if not root.is_dir():
            return 0
        return sum(
            path.is_file() and path.suffix.lower() in RASTER_SUFFIXES
            for path in root.rglob("*")
        )

    def _ui_contract(self, build: ReferenceBuild) -> dict[str, Any]:
        layout = json.loads((self.resources / "EffectsLayoutNeo.json").read_text("utf-8"))
        panel = json.loads(
            (self.resources / "MPEditPanelLayoutConfig.json").read_text("utf-8")
        )
        effects_text = (self.resources / "EffectsConfig.json").read_text(
            "utf-8", errors="replace"
        )
        sky_sections = self._tool_sections(layout, "SkyReplacementAdjustmentLayer")
        sky_parameters = [
            parameter
            for section in sky_sections
            for parameter in section["parameters"]
        ]
        return {
            "version": "1.0.0",
            "reference_build_id": build.id,
            "workspaces": ["catalog", "presets", "edit"],
            "reference_screenshots": {
                "catalog": [2760, 1750],
                "presets": [2880, 1800],
                "edit": [2880, 1800],
            },
            "tool_groups": self._tool_groups(panel),
            "tools": {
                "sky_replace": {
                    "source_tool": "SkyReplacementAdjustmentLayer",
                    "source_effect": "MIPLSkyReplacementEffect",
                    "sections": sky_sections,
                    "parameters": {
                        name: self._parameter_metadata(effects_text, name)
                        for name in dict.fromkeys(sky_parameters)
                    },
                }
            },
        }

    @staticmethod
    def _tool_sections(payload: dict[str, Any], tool_name: str) -> list[dict[str, Any]]:
        sections = payload.get("AdjustmentLayers", {}).get(tool_name, [])
        result = []
        for index, section in enumerate(sections):
            parameters = []
            for row in section.get("children", []):
                for child in row:
                    name = child.get("parameter")
                    if name and name not in parameters:
                        parameters.append(name)
            result.append(
                {
                    "id": re.sub(r"[^a-z0-9]+", "-", section.get("title", "texture").lower()).strip("-"),
                    "title": section.get("title", "Texture"),
                    "expandable": bool(section.get("expandable")),
                    "expanded": bool(section.get("expanded", index == 0)),
                    "parameters": parameters,
                }
            )
        return result

    @staticmethod
    def _tool_groups(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = next((item for item in payload if item.get("Identifier") == "Tools"), {})
        result = []
        for group in tools.get("Items", []):
            result.append(
                {
                    "id": group.get("Identifier") or "common",
                    "title": group.get("Hint") or "Common",
                    "start_color": group.get("StartGradientColor"),
                    "end_color": group.get("EndGradientColor"),
                    "tools": [item.get("Identifier") for item in group.get("Items", [])],
                }
            )
        return result

    @staticmethod
    def _parameter_metadata(text: str, parameter: str) -> dict[str, Any]:
        block_start = text.find('"MIPLSkyReplacementEffect"')
        block = text[block_start : block_start + 12000] if block_start >= 0 else text
        match = re.search(
            rf'"{re.escape(parameter)}"\s*:\s*\{{(?P<body>.*?)\n\s*\}}',
            block,
            re.DOTALL,
        )
        body = match.group("body") if match else ""
        display = re.search(r'"name"\s*:\s*"([^"]+)"', body)
        control = re.search(r'"type"\s*:\s*"([^"]+)"', body)
        disable = re.search(r'"disableCondition"\s*:\s*"([^"]+)"', body)
        return {
            "source_id": parameter,
            "display_name": display.group(1) if display else parameter,
            "control_type": control.group(1) if control else "parameter",
            "disable_condition": disable.group(1) if disable else None,
            "range": "pending-black-box-calibration",
            "default": "pending-black-box-calibration",
        }

    def _variant_payload(self, variant: ModelVariant) -> dict[str, Any]:
        payload = variant.__dict__.copy()
        payload["source_policy"] = variant.source_policy.value
        if variant.format == "openvino_ir":
            xml_path = self.resources / variant.relative_path
            weights_path = xml_path.with_suffix(".bin")
            payload["weights_relative_path"] = str(
                weights_path.relative_to(self.resources)
            )
            payload["weights_sha256"] = sha256_file(weights_path)
        return payload
