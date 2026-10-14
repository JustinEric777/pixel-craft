"""Application services for project, analysis and edit-graph use cases."""

from __future__ import annotations

import hashlib
import io
import json
import threading
import uuid
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import (
    ExifTags,
    Image,
    ImageChops,
    ImageCms,
    ImageDraw,
    ImageFilter,
    UnidentifiedImageError,
)

from core.capabilities import CapabilitySchema
from core.errors import (
    AssetRequiredError,
    CapabilityConflictError,
    ProjectNotFoundError,
    UnknownAssetError,
    UnsupportedMediaTypeError,
)
from core.project.entities import EditNode, LayerRef, MaskRef, ProjectState
from core.project.serialization import project_to_dict
from services.ports.catalog import ManifestCatalog
from services.ports.editing import (
    ArtifactCachePort,
    AssetCatalogPort,
    CatalogRepository,
    ModelServicePort,
    ProjectRenderer,
    ProjectRepository,
)
from services.ports.images import ImageReader


class EditorService:
    """Coordinate use cases while keeping HTTP and persistence details outside."""

    def __init__(
        self,
        *,
        projects: ProjectRepository,
        catalog_store: CatalogRepository,
        assets: AssetCatalogPort,
        capabilities: CapabilitySchema,
        artifact_cache: ArtifactCachePort,
        model_service: ModelServicePort,
        renderer: ProjectRenderer,
        manifests: ManifestCatalog,
        image_reader: ImageReader,
        asset_root: Path,
        policy: Any,
        presets: tuple[dict[str, Any], ...],
        preset_source: dict[str, str],
    ) -> None:
        self.projects = projects
        self.catalog_store = catalog_store
        self.assets = assets
        self.capabilities = capabilities
        self.artifact_cache = artifact_cache
        self.model_service = model_service
        self.renderer = renderer
        self.manifests = manifests
        self.image_reader = image_reader
        self.asset_root = asset_root.resolve()
        self.policy = policy
        self._presets = presets
        self._preset_source = dict(preset_source)
        self._preview_render_cache: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self._preview_cache_lock = threading.RLock()
        self._preview_inflight: dict[str, threading.Event] = {}
        self._execution_traces: dict[str, dict[str, Any]] = {}
        self._last_exports: dict[str, dict[str, Any]] = {}

    def upload_asset(
        self, filename: str, content: bytes, *, collection: str | None = None
    ) -> dict[str, str]:
        suffix = Path(filename or "upload.jpg").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            raise UnsupportedMediaTypeError("supported image formats: jpg, png, webp, tiff")
        _, asset_path = self.projects.add_asset(
            filename, content, collection=collection
        )
        project_id, state = self.projects.create_project(
            asset_path, original_filename=filename
        )
        self._populate_source_metadata(state, asset_path)
        self.projects.save(project_id, state)
        catalog_asset_id = self._upsert_catalog_asset(asset_path, project_id)
        return {
            "asset_id": catalog_asset_id,
            "project_id": project_id,
            "filename": filename,
        }

    def catalog(self, *, view: str = "all", query: str = "", sort: str = "name") -> dict[str, Any]:
        """Return the local library state used by the Catalog workspace."""
        records = self._read_catalog()
        query = query.strip().lower()
        if query:
            records = [
                item for item in records
                if query in str(item.get("filename", "")).lower()
                or query in str(item.get("path", "")).lower()
            ]
        if view == "recent":
            records = [item for item in records if item.get("deleted_at") is None]
            records.sort(key=lambda item: item.get("added_at", ""), reverse=True)
        elif view == "edited":
            records = [item for item in records if item.get("edit_count", 0) > 0]
            records.sort(key=lambda item: item.get("edited_at", ""), reverse=True)
        elif view == "trash":
            records = [item for item in records if item.get("deleted_at")]
        else:
            records = [item for item in records if not item.get("deleted_at")]
            if sort == "added_at":
                records.sort(key=lambda item: item.get("added_at", ""), reverse=True)
            elif sort == "capture_time":
                records.sort(key=lambda item: item.get("capture_time") or "", reverse=True)
            elif sort == "size":
                records.sort(key=lambda item: item.get("size", 0), reverse=True)
            else:
                records.sort(key=lambda item: str(item.get("filename", "")).lower())
        return {"view": view, "query": query, "sort": sort, "count": len(records), "records": records}

    def update_catalog_asset(self, asset_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Persist catalog-only state used by native-style library actions."""
        records = self._read_catalog()
        record = next((item for item in records if item.get("asset_id") == asset_id), None)
        if record is None:
            raise UnknownAssetError(f"catalog asset not found: {asset_id}")
        try:
            self.catalog_store.update_asset(asset_id, changes)
        except (KeyError, ValueError) as exc:
            raise UnknownAssetError(f"catalog asset not found: {asset_id}") from exc
        updated = next(
            item for item in self._read_catalog() if item.get("asset_id") == asset_id
        )
        return {"record": deepcopy(updated)}

    def presets(self, category: str | None = None) -> dict[str, Any]:
        presets = self._builtin_presets()
        if category:
            presets = [item for item in presets if item["category"] == category]
        return {"count": len(presets), "categories": sorted({item["category"] for item in presets}), "records": presets}

    def import_preset(self, files: list[tuple[str, bytes]]) -> dict[str, Any]:
        """Persist one local Luminar ``.lnp`` package selected by the user."""
        template = next(
            ((name, content) for name, content in files if Path(name).suffix.lower() in {".lmps", ".json"}),
            None,
        )
        if template is None:
            raise UnsupportedMediaTypeError("请选择包含 template.lmps 的 Luminar 预设文件夹")
        try:
            payload = json.loads(template[1].decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnsupportedMediaTypeError("预设文件不是有效的 Luminar JSON") from exc

        native_effects = self._active_preset_effects(payload)
        if native_effects:
            edit_graph = [{
                "effect": "luminar_preset",
                "parameters": {"source_effects": native_effects, "opacity": 1.0},
            }]
        else:
            edit_graph = payload.get("edit_graph")
        if not isinstance(edit_graph, list) or not edit_graph:
            raise UnsupportedMediaTypeError("预设不包含可执行的编辑效果")

        source_id = str(payload.get("uuid") or hashlib.sha256(template[1]).hexdigest()[:24])
        preset_id = f"local_{source_id.lower()}"
        record = {
            "id": preset_id,
            "name": str(payload.get("name") or Path(template[0]).stem),
            "category": "本地预设",
            "status": "local-imported",
            "source": {"product": "Luminar Neo", "uuid": source_id, "filename": template[0]},
            "edit_graph": edit_graph,
        }
        records = self._read_local_presets()
        records = [item for item in records if item.get("id") != preset_id]
        records.append(record)
        self._write_local_presets(records)

        icon = next(
            ((name, content) for name, content in files if Path(name).name.lower() in {"icon.jpg", "icon.jpeg", "icon.png"}),
            None,
        )
        if icon:
            artwork_dir = self.projects.root / "local-presets" / "artwork"
            artwork_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(icon[0]).suffix.lower() or ".jpg"
            (artwork_dir / f"{preset_id}{suffix}").write_bytes(icon[1])
        return {"preset": deepcopy(record), **self.presets()}

    def apply_preset(self, project_id: str, preset_id: str) -> dict[str, Any]:
        preset = next((item for item in self._builtin_presets() if item["id"] == preset_id), None)
        if preset is None:
            raise UnknownAssetError(f"unknown preset: {preset_id}")
        state = self._load(project_id)
        effects = [str(spec["effect"]) for spec in preset["edit_graph"]]
        self.model_service.assert_effects_ready(effects)
        added = []
        nodes: list[EditNode] = []
        for spec in preset["edit_graph"]:
            effect = str(spec["effect"])
            self._assert_editable(effect)
            normalized = self._normalize_parameters(effect, dict(spec.get("parameters", {})))
            node = EditNode(uuid.uuid4().hex, effect, normalized, None, True)
            nodes.append(node)
            added.append(node.id)
        state.append_edits(nodes)
        state.metadata["last_preset"] = {"id": preset_id, "name": preset["name"], "added_edits": added}
        self.projects.save(project_id, state)
        return {"preset": preset, "project": project_to_dict(state)}

    def preset_preview(self, project_id: str, preset_id: str, width: int = 360) -> Path:
        preset = next((item for item in self._builtin_presets() if item["id"] == preset_id), None)
        if preset is None:
            raise UnknownAssetError(f"unknown preset: {preset_id}")
        state = deepcopy(self._load(project_id))
        for spec in preset["edit_graph"]:
            effect = str(spec["effect"])
            self._assert_editable(effect)
            normalized = self._normalize_parameters(effect, dict(spec.get("parameters", {})))
            state.append_edit(EditNode(uuid.uuid4().hex, effect, normalized, None, True))
        self.model_service.assert_effects_ready(
            [edit.effect for edit in state.edits if edit.enabled]
        )
        image = self.renderer.render(
            state, asset_root=self.asset_root, model_service=self.model_service
        )
        image.thumbnail((max(160, min(720, width)), max(160, min(720, width))))
        output = self.projects.root / "preset-previews" / f"{project_id}-{preset_id}.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(output, format="JPEG", quality=88)
        return output

    def preset_artwork_path(self, preset_id: str) -> Path:
        """Resolve the version-locked native icon for a configured preset."""
        preset = next((item for item in self._builtin_presets() if item["id"] == preset_id), None)
        if preset is None:
            raise UnknownAssetError(f"unknown preset: {preset_id}")
        if preset_id.startswith("local_"):
            artwork_dir = self.projects.root / "local-presets" / "artwork"
            artwork = next((path for path in artwork_dir.glob(f"{preset_id}.*") if path.is_file()), None) if artwork_dir.is_dir() else None
            if artwork:
                return artwork
            fallback = next(iter((self.asset_root / "materials" / "PresetPacks" / "Collections").glob("*/small.jpg")), None)
            if fallback:
                return fallback
            raise UnknownAssetError(f"preset artwork is unavailable: {preset_id}")
        index = self._preset_artwork_index()
        record = next((item for item in index["records"] if item["id"] == preset_id), None)
        if record is None or not record.get("icon"):
            raise UnknownAssetError(f"preset artwork is unavailable: {preset_id}")
        return self._resolve_preset_artwork(str(record["icon"]))

    def preset_category_artwork_path(self, category: str, variant: str = "big") -> Path:
        """Resolve a native collection cover without exposing arbitrary paths."""
        if variant not in {"big", "small"}:
            raise UnknownAssetError(f"unknown preset artwork variant: {variant}")
        record = self._preset_artwork_index()["categories"].get(category)
        if not isinstance(record, dict) or not record.get(variant):
            raise UnknownAssetError(f"preset category artwork is unavailable: {category}")
        return self._resolve_preset_artwork(str(record[variant]))

    def get_project(self, project_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        if (
            state.source.width is None or state.source.height is None
        ) and state.source.path.is_file():
            self._populate_source_metadata(state, state.source.path)
            self.projects.save(project_id, state)
        payload = project_to_dict(state)
        with self._preview_cache_lock:
            trace = self._execution_traces.get(project_id)
            export = self._last_exports.get(project_id)
        if trace is not None:
            payload["metadata"]["last_execution"] = deepcopy(trace)
        if export is not None:
            payload["metadata"]["last_export"] = deepcopy(export)
        return payload

    @staticmethod
    def _populate_source_metadata(state: ProjectState, path: Path) -> None:
        """Persist factual source dimensions and available EXIF at import time."""
        with Image.open(path) as image:
            state.source = replace(
                state.source,
                width=image.width,
                height=image.height,
                color_space=image.mode,
            )
            exif = {
                ExifTags.TAGS.get(tag, str(tag)): value
                for tag, value in image.getexif().items()
            }
        mappings = {
            "Model": "camera_model",
            "LensModel": "lens_model",
            "DateTimeOriginal": "capture_time",
            "ISOSpeedRatings": "iso",
            "PhotographicSensitivity": "iso",
            "FocalLength": "focal_length",
            "FNumber": "aperture",
            "ExposureBiasValue": "exposure_bias",
            "ExposureTime": "shutter_speed",
        }
        for source_key, target_key in mappings.items():
            candidate = exif.get(source_key)
            if candidate is not None and target_key not in state.metadata:
                state.metadata[target_key] = str(candidate)

    def source_path(self, project_id: str) -> Path:
        path = self._load(project_id).source.path
        if not path.is_file():
            raise UnknownAssetError("project source image is missing")
        return path

    def add_layer_upload(self, project_id: str, filename: str, content: bytes) -> dict[str, Any]:
        suffix = Path(filename or "layer.png").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            raise UnsupportedMediaTypeError("supported image formats: jpg, png, webp, tiff")
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise UnsupportedMediaTypeError("layer is not a readable image") from exc
        state = self._load(project_id)
        asset_id, asset_path = self.projects.add_asset(filename, content)
        state.append_layer(
            LayerRef(uuid.uuid4().hex, asset_id, asset_path, Path(filename).stem)
        )
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def add_layer_material(self, project_id: str, material_id: str) -> dict[str, Any]:
        try:
            material = self.assets.require_layer_material(material_id)
            source = self.assets.resolve_layer_material(material_id)
        except (FileNotFoundError, KeyError) as exc:
            raise UnknownAssetError(f"unknown layer material: {material_id}") from exc
        state = self._load(project_id)
        state.append_layer(
            LayerRef(
                id=uuid.uuid4().hex,
                asset_id=material_id,
                path=source,
                name=str(material["name"]),
                source_kind="library",
                opacity=float(material["opacity"]),
                blend_mode=str(material["blend_mode"]),
            )
        )
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def update_layer(
        self, project_id: str, layer_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        state = self._load(project_id)
        index = next((i for i, layer in enumerate(state.layers) if layer.id == layer_id), None)
        if index is None:
            raise UnknownAssetError(f"unknown layer: {layer_id}")
        allowed_modes = {"normal", "screen", "multiply", "overlay", "soft_light", "lighten", "darken"}
        if changes.get("blend_mode") not in (None, *allowed_modes):
            raise CapabilityConflictError("unsupported layer blend mode")
        values = {key: value for key, value in changes.items() if value is not None}
        state.replace_layer(replace(state.layers[index], **values))
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def reorder_layers(self, project_id: str, layer_ids: list[str]) -> dict[str, Any]:
        state = self._load(project_id)
        current = {layer.id: layer for layer in state.layers}
        if len(layer_ids) != len(current) or set(layer_ids) != set(current):
            raise CapabilityConflictError("layer_ids must contain every layer exactly once")
        state.reorder_layers(layer_ids)
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def delete_layer(self, project_id: str, layer_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        next_layers = [layer for layer in state.layers if layer.id != layer_id]
        if len(next_layers) == len(state.layers):
            raise UnknownAssetError(f"unknown layer: {layer_id}")
        state.remove_layer(layer_id)
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def layer_path(self, project_id: str, layer_id: str) -> Path:
        state = self._load(project_id)
        layer = next((item for item in state.layers if item.id == layer_id), None)
        if layer is None or not layer.path.is_file():
            raise UnknownAssetError(f"unknown layer: {layer_id}")
        return layer.path

    def add_mask_upload(
        self,
        project_id: str,
        owner_type: str,
        owner_id: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        if owner_type not in {"edit", "layer"}:
            raise CapabilityConflictError("mask owner_type must be edit or layer")
        if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise UnsupportedMediaTypeError("supported mask formats: png, jpg, webp")
        state = self._load(project_id)
        with self.image_reader.open(state.source.path) as source:
            target_size = source.size
        try:
            with Image.open(io.BytesIO(content)) as uploaded:
                mask_image = uploaded.convert("L").resize(
                    target_size, Image.Resampling.BILINEAR
                )
        except (OSError, UnidentifiedImageError) as exc:
            raise UnsupportedMediaTypeError("mask is not a readable image") from exc
        mask_id = uuid.uuid4().hex
        path = self.projects.root / "masks" / project_id / f"{mask_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        mask_image.save(path, format="PNG")
        digest = hashlib.sha256(mask_image.tobytes()).hexdigest()
        state.attach_mask(
            MaskRef(
                id=mask_id,
                path=path,
                owner_type=owner_type,
                owner_id=owner_id,
                width=mask_image.width,
                height=mask_image.height,
                sha256=digest,
            )
        )
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def update_mask(
        self, project_id: str, mask_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        state = self._load(project_id)
        mask = state.masks.get(mask_id)
        if mask is None:
            raise UnknownAssetError(f"unknown mask: {mask_id}")
        values = {key: value for key, value in changes.items() if value is not None}
        state.replace_mask(replace(mask, **values))
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def paint_mask(
        self,
        project_id: str,
        owner_type: str,
        owner_id: str,
        strokes: list[list[tuple[float, float]]],
        *,
        size: int,
        softness: int,
        strength: int,
    ) -> dict[str, Any]:
        if owner_type not in {"edit", "layer"}:
            raise CapabilityConflictError("mask owner_type must be edit or layer")
        state = self._load(project_id)
        with self.image_reader.open(state.source.path) as source:
            target_size = source.size
        width, height = target_size
        mask_image = Image.new("L", target_size, 0)
        for stroke in strokes:
            if len(stroke) < 2:
                raise CapabilityConflictError("mask brush stroke requires at least two points")
            points = [
                (
                    round(max(0.0, min(1.0, float(x))) * (width - 1)),
                    round(max(0.0, min(1.0, float(y))) * (height - 1)),
                )
                for x, y in stroke
            ]
            stroke_image = Image.new("L", target_size, 0)
            draw = ImageDraw.Draw(stroke_image)
            draw.line(points, fill=255, width=size, joint="curve")
            radius = size / 2
            for x, y in (points[0], points[-1]):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
            blur_radius = size * softness / 400
            if blur_radius > 0:
                stroke_image = stroke_image.filter(ImageFilter.GaussianBlur(blur_radius))
            if strength < 100:
                stroke_image = stroke_image.point(lambda value: round(value * strength / 100))
            mask_image = ImageChops.lighter(mask_image, stroke_image)
        mask_id = uuid.uuid4().hex
        path = self.projects.root / "masks" / project_id / f"{mask_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        mask_image.save(path, format="PNG")
        state.attach_mask(
            MaskRef(
                id=mask_id,
                path=path,
                owner_type=owner_type,
                owner_id=owner_id,
                width=width,
                height=height,
                source="brush",
                brush_size=size,
                brush_softness=softness,
                brush_strength=strength,
                sha256=hashlib.sha256(mask_image.tobytes()).hexdigest(),
            )
        )
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def delete_mask(self, project_id: str, mask_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        mask = state.masks.get(mask_id)
        if mask is None:
            raise UnknownAssetError(f"unknown mask: {mask_id}")
        state.remove_mask(mask_id)
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def mask_path(self, project_id: str, mask_id: str) -> Path:
        state = self._load(project_id)
        mask = state.masks.get(mask_id)
        if mask is None or not mask.path.is_file():
            raise UnknownAssetError(f"unknown mask: {mask_id}")
        return mask.path

    def add_edit(
        self,
        project_id: str,
        effect: str,
        parameters: dict[str, Any],
        mask_artifact: str | None,
        enabled: bool,
    ) -> dict[str, Any]:
        self._assert_editable(effect)
        normalized = self._normalize_parameters(effect, parameters)
        self.model_service.assert_effects_ready([effect])
        state = self._load(project_id)
        node = EditNode(uuid.uuid4().hex, effect, normalized, mask_artifact, enabled)
        # Luminar's Sky AI is a singleton tool in the Edit workspace. Repeated
        # clicks update the tool instead of stacking another translucent sky
        # layer on top of the previous one. Keeping old nodes disabled also
        # preserves the non-destructive history without compounding masks.
        if effect == "sky_replace" and enabled:
            active_sky = [item for item in state.edits if item.effect == effect and item.enabled]
            for previous in active_sky[:-1]:
                state.replace_edit(
                    EditNode(previous.id, previous.effect, previous.parameters, previous.mask_artifact, False)
                )
            if active_sky:
                node = EditNode(active_sky[-1].id, effect, normalized, mask_artifact, enabled)
                state.replace_edit(node)
            else:
                state.append_edit(node)
        else:
            state.append_edit(node)
        self.projects.save(project_id, state)
        payload = project_to_dict(state)
        return {
            "edit": next(item for item in payload["edits"] if item["id"] == node.id),
            "project": payload,
        }

    def update_edit(
        self,
        project_id: str,
        edit_id: str,
        effect: str,
        parameters: dict[str, Any],
        mask_artifact: str | None,
        enabled: bool,
    ) -> dict[str, Any]:
        self._assert_editable(effect)
        normalized = self._normalize_parameters(effect, parameters)
        self.model_service.assert_effects_ready([effect])
        state = self._load(project_id)
        state.replace_edit(EditNode(edit_id, effect, normalized, mask_artifact, enabled))
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def delete_edit(self, project_id: str, edit_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        state.remove_edit(edit_id)
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def reset_project(self, project_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        state.reset_to_original()
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def reorder_edits(self, project_id: str, edit_ids: list[str]) -> dict[str, Any]:
        state = self._load(project_id)
        state.reorder_edits(edit_ids)
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def undo(self, project_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        state.undo()
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def redo(self, project_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        state.redo()
        self.projects.save(project_id, state)
        return project_to_dict(state)

    def analyze(self, project_id: str, models: str | None = None) -> dict[str, Any]:
        state = self._load(project_id)
        with self.image_reader.open(state.source.path) as image:
            state.source = state.source.__class__(
                state.source.path, image.width, image.height, "sRGB"
            )
            state.metadata["analysis_status"] = "ready-for-model-specific-pipelines"
            state.metadata["artifacts"] = {
                "source_image": {
                    "kind": "image",
                    "status": "ready",
                    "size": [image.width, image.height],
                },
            }
            requested = (
                [item.strip() for item in models.split(",") if item.strip()] if models else None
            )
            source_hash = self.artifact_cache.source_hash(state.source.path)
            state.metadata["analysis_source_hash"] = source_hash
            state.metadata["onnx_analysis"] = self.model_service.analyze(
                image,
                requested,
                artifact_cache=self.artifact_cache,
                source_hash=source_hash,
            )
            for artifact_name, result in state.metadata["onnx_analysis"].items():
                state.metadata["artifacts"][artifact_name] = {
                    "kind": "embedding" if artifact_name == "image_embedding" else "analysis",
                    "status": result.get("status", "unknown"),
                    "model": result.get("model"),
                    "cache_hit": result.get("cache_hit"),
                }
            state.metadata["analysis_cache"] = {
                "root": str(self.artifact_cache.root),
                "records": len(self.artifact_cache.list_records()),
            }
        self.projects.save(project_id, state)
        return {"project_id": project_id, "metadata": state.metadata}

    def project_artifacts(self, project_id: str) -> dict[str, Any]:
        state = self._load(project_id)
        return {
            "project_id": project_id,
            "analysis_source_hash": state.metadata.get("analysis_source_hash"),
            "analysis": state.metadata.get("onnx_analysis", {}),
            "cache": state.metadata.get("analysis_cache", {"records": 0}),
        }

    def search(self, project_id: str, query: str) -> dict[str, Any]:
        state = self._load(project_id)
        with self.image_reader.open(state.source.path) as image:
            result = self.model_service.search(image, query)
        state.metadata["last_search"] = result
        self.projects.save(project_id, state)
        return {"project_id": project_id, **result}

    def render_preview(
        self,
        project_id: str,
        output: Path | None = None,
        width: int | None = None,
        operation: str = "preview",
    ) -> Any:
        state = self._load(project_id)
        render_key = self._render_key(state)
        owns_preview_render = False
        wait_for_preview: threading.Event | None = None
        if operation == "preview" and width is None:
            with self._preview_cache_lock:
                if render_key not in self._preview_render_cache:
                    wait_for_preview = self._preview_inflight.get(render_key)
                    if wait_for_preview is None:
                        wait_for_preview = threading.Event()
                        self._preview_inflight[render_key] = wait_for_preview
                        owns_preview_render = True
        if wait_for_preview is not None and not owns_preview_render:
            if not wait_for_preview.wait(timeout=300):
                raise TimeoutError("timed out waiting for the current preview render")
            with self._preview_cache_lock:
                if render_key not in self._preview_render_cache:
                    raise RuntimeError("the current preview render failed")
        if operation in {"preview", "export"}:
            with self._preview_cache_lock:
                cached = self._preview_render_cache.get(render_key)
            if cached:
                image_bytes, cached_trace = cached
                image = Image.open(io.BytesIO(image_bytes)).copy()
                if width and width < image.width:
                    image.thumbnail((width, width))
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    if width is None:
                        output.write_bytes(image_bytes)
                    else:
                        image.save(output, format="PNG")
                trace = deepcopy(cached_trace)
                trace.update(
                    {
                        "execution_id": uuid.uuid4().hex,
                        "operation": operation,
                        "status": "ready",
                        "cache_hit": True,
                        "duration_ms": 0.0,
                        "result_sha256": hashlib.sha256(
                            image.mode.encode("ascii")
                            + str(image.size).encode("ascii")
                            + image.tobytes()
                        ).hexdigest(),
                        "result_size": list(image.size),
                    }
                )
                latest = self._load(project_id)
                if self._render_key(latest) == render_key:
                    with self._preview_cache_lock:
                        self._execution_traces[project_id] = deepcopy(trace)
                return image
        trace: dict[str, Any] | None = None
        rendered_image: Image.Image | None = None
        try:
            capability_ids = [edit.effect for edit in state.edits if edit.enabled]
            with self.model_service.execution(capability_ids, operation) as active_trace:
                trace = active_trace
                trace["source_sha256"] = self.artifact_cache.source_hash(state.source.path)
                trace["assets"] = self._execution_assets(state)
                self.model_service.assert_effects_ready(capability_ids)
                image = self.renderer.render(
                    state, asset_root=self.asset_root, model_service=self.model_service
                )
                if width and width < image.width:
                    image.thumbnail((width, width))
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output)
                trace["result_sha256"] = hashlib.sha256(
                    image.mode.encode("ascii")
                    + str(image.size).encode("ascii")
                    + image.tobytes()
                ).hexdigest()
                trace["result_size"] = list(image.size)
                rendered_image = image
                return image
        finally:
            if trace is not None:
                latest = self._load(project_id)
                render_is_current = self._render_key(latest) == render_key
                if render_is_current:
                    with self._preview_cache_lock:
                        self._execution_traces[project_id] = deepcopy(trace)
                if (
                    render_is_current
                    and
                    operation == "preview"
                    and width is None
                    and rendered_image is not None
                    and trace.get("status") == "ready"
                ):
                    encoded = io.BytesIO()
                    rendered_image.save(encoded, format="PNG")
                    with self._preview_cache_lock:
                        self._preview_render_cache[render_key] = (
                            encoded.getvalue(),
                            deepcopy(trace),
                        )
                        while len(self._preview_render_cache) > 32:
                            self._preview_render_cache.pop(
                                next(iter(self._preview_render_cache))
                            )
            if owns_preview_render:
                with self._preview_cache_lock:
                    event = self._preview_inflight.pop(render_key, None)
                    if event is not None:
                        event.set()

    def export(
        self,
        project_id: str,
        output: Path,
        *,
        width: int | None = None,
        image_format: str = "png",
        color_profile: str = "sRGB",
    ) -> dict[str, Any]:
        normalized_format = image_format.lower()
        if normalized_format not in {"png", "jpeg", "tiff"}:
            raise UnsupportedMediaTypeError(
                "supported export formats: png, jpeg, tiff"
            )
        if color_profile != "sRGB":
            raise UnsupportedMediaTypeError("supported export color profile: sRGB")
        output.parent.mkdir(parents=True, exist_ok=True)
        image = self.render_preview(
            project_id,
            output if normalized_format == "png" and width is None else None,
            width=width,
            operation="export",
        )
        if normalized_format != "png" or width is not None:
            if normalized_format == "jpeg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            save_options: dict[str, Any] = {"icc_profile": profile}
            if normalized_format == "jpeg":
                save_options.update({"quality": 95, "subsampling": 0})
            image.save(output, format=normalized_format.upper(), **save_options)
        metadata = {
            "format": normalized_format,
            "size": list(image.size),
            "color_profile": color_profile,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
        with self._preview_cache_lock:
            self._last_exports[project_id] = deepcopy(metadata)
        return metadata

    @staticmethod
    def _render_key(state: ProjectState) -> str:
        payload = {
            "source": str(state.source.path),
            "source_size": [state.source.width, state.source.height],
            "edits": [edit.to_dict() for edit in state.edits],
            "layers": [layer.to_dict() for layer in state.layers],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def execution_trace(self, project_id: str) -> dict[str, Any]:
        self._load(project_id)
        with self._preview_cache_lock:
            trace = self._execution_traces.get(project_id)
        return deepcopy(trace) if trace is not None else {
            "status": "not-run",
            "models": [],
            "capabilities": [],
        }

    def list_assets(self, family: str | None = None) -> dict[str, Any]:
        records = self.assets.list(family)
        return {
            "count": len(records),
            "families": self.assets.payload.get("families", []),
            "records": records,
        }

    def list_layer_materials(self) -> dict[str, Any]:
        groups = self.assets.layer_material_groups()
        return {"count": sum(group["count"] for group in groups), "groups": groups}

    def layer_material_path(self, material_id: str) -> Path:
        try:
            return self.assets.resolve_layer_material(material_id)
        except (FileNotFoundError, KeyError) as exc:
            raise UnknownAssetError(f"unknown layer material: {material_id}") from exc

    def asset_path(self, asset_id: str) -> Path:
        """Resolve a manifest asset for a read-only preview response."""
        try:
            return self.assets.resolve(asset_id)
        except (FileNotFoundError, KeyError) as exc:
            raise UnknownAssetError(f"unknown asset_id: {asset_id}") from exc

    def asset_preview_path(self, asset_id: str, size: int = 320) -> Path:
        """Create/reuse a bounded preview without mutating the source asset."""
        try:
            source = self.asset_path(asset_id)
        except UnknownAssetError:
            catalog_record = next(
                (item for item in self._read_catalog() if item.get("asset_id") == asset_id),
                None,
            )
            source = Path(str(catalog_record.get("path"))) if catalog_record else Path()
            if not source.is_file():
                raise UnknownAssetError(f"unknown asset_id: {asset_id}")
        size = max(96, min(640, int(size)))
        catalog_record = next(
            (item for item in self._read_catalog() if item.get("asset_id") == asset_id),
            None,
        )
        rotation = int(catalog_record.get("rotation", 0)) if catalog_record else 0
        token = hashlib.sha256(
            f"{asset_id}:{source.stat().st_mtime_ns}:{size}:{rotation}".encode()
        ).hexdigest()[:24]
        preview_root = self.projects.preview_root
        preview = preview_root / f"{token}.jpg"
        if not preview.is_file():
            preview_root.mkdir(parents=True, exist_ok=True)
            try:
                with Image.open(source) as image:
                    image = image.convert("RGB")
                    if rotation:
                        image = image.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    image.save(preview, format="JPEG", quality=86, optimize=True)
            except (OSError, UnidentifiedImageError) as exc:
                raise UnknownAssetError(f"asset is not a previewable image: {asset_id}") from exc
        return preview

    def health(self) -> dict[str, Any]:
        return self.model_service.health()

    def list_models(self) -> dict[str, Any]:
        return self.manifests.models()

    def list_capabilities(self) -> dict[str, Any]:
        capabilities = []
        for item in self.manifests.capabilities():
            record = dict(item)
            readiness = self.model_service.capability_readiness(record)
            record["readiness"] = readiness
            capabilities.append(record)
        return {"capabilities": capabilities}

    def _load(self, project_id: str) -> ProjectState:
        try:
            return self.projects.load(project_id)
        except FileNotFoundError as exc:
            raise ProjectNotFoundError("project not found") from exc

    def _assert_editable(self, effect: str) -> None:
        if effect in self.policy.analysis_only:
            raise CapabilityConflictError(
                f"{effect} is an analysis capability; run /analyze instead"
            )
        if effect in self.policy.multi_image_only:
            raise CapabilityConflictError(
                f"{effect} requires a dedicated multi-input or coordinate workflow"
            )

    def _normalize_parameters(self, effect: str, parameters: dict[str, Any]) -> dict[str, Any]:
        parameters = dict(parameters)
        asset_id = parameters.pop("asset_id", None)
        self.capabilities.require_capability(effect)
        if effect in self.policy.asset_required and not asset_id:
            raise AssetRequiredError(f"{effect} requires asset_id")
        if asset_id:
            try:
                parameters["asset_id"] = str(asset_id)
                parameters["asset_path"] = str(
                    self.assets.resolve(asset_id).relative_to(self.asset_root)
                )
            except (FileNotFoundError, KeyError, ValueError) as exc:
                raise UnknownAssetError(f"unknown asset_id: {asset_id}") from exc
        return self.capabilities.validate(effect, parameters)

    def _execution_assets(self, state: ProjectState) -> list[dict[str, Any]]:
        manifest = {
            str(record.get("id")): record
            for record in self.assets.payload.get("records", [])
        }
        evidence: list[dict[str, Any]] = []
        seen: set[str] = set()
        for edit in state.edits:
            asset_id = str(edit.parameters.get("asset_id", ""))
            if not edit.enabled or not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            record = manifest.get(asset_id, {})
            evidence.append(
                {
                    "id": asset_id,
                    "family": record.get("family"),
                    "sha256": record.get("sha256"),
                }
            )
        return evidence

    def _read_catalog(self) -> list[dict[str, Any]]:
        return self.catalog_store.records()

    def _upsert_catalog_asset(self, path: Path, project_id: str) -> str:
        return self.catalog_store.upsert_asset(
            project_id=project_id, source=path
        )

    def _builtin_presets(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in (*self._presets, *self._read_local_presets())]

    def _read_local_presets(self) -> list[dict[str, Any]]:
        path = self.projects.root / "local-presets" / "index.json"
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        records = payload.get("presets", [])
        return records if isinstance(records, list) else []

    def _write_local_presets(self, records: list[dict[str, Any]]) -> None:
        path = self.projects.root / "local-presets" / "index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"presets": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _active_preset_effects(payload: dict[str, Any]) -> list[dict[str, Any]]:
        effects: list[dict[str, Any]] = []
        for layer_index, layer in enumerate(payload.get("layers_array", [])):
            if str(layer.get("alive", True)).lower() in {"0", "false", "no"}:
                continue
            edits = layer.get("edits_array", [])
            if not edits:
                continue
            cursor = min(max(int(layer.get("curr_edit_inedx", len(edits) - 1)), 0), len(edits) - 1)
            for edit_index, edit in enumerate(edits[:cursor + 1]):
                if str(edit.get("enabled", True)).lower() in {"0", "false", "no"}:
                    continue
                for effect in edit.get("effects_array", []):
                    parameters = []
                    for parameter in effect.get("params_array", []):
                        optional_value = parameter.get("opt_data_value")
                        has_optional = optional_value not in (None, 0, "0", "")
                        if parameter.get("value") == parameter.get("default") and not has_optional and parameter.get("opt_data_type") in {None, 0, "0"}:
                            continue
                        parameters.append({
                            key: parameter[key]
                            for key in ("name", "value", "default", "min", "max", "normalized_value", "opt_data_type", "opt_data_value")
                            if key in parameter
                        })
                    if parameters:
                        effects.append({
                            "id": str(effect["id"]),
                            "parameters": parameters,
                            "source": {"layer_index": layer_index, "edit_index": edit_index, "tool_name": str(edit.get("tool_name") or "")},
                        })
        return effects

    def _preset_artwork_index(self) -> dict[str, Any]:
        path = self.asset_root / "materials" / "PresetPacks" / "index.json"
        if not path.is_file():
            raise UnknownAssetError("preset artwork index is unavailable")
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = payload.get("source", {})
        expected = (
            self._preset_source.get("version", ""),
            self._preset_source.get("build", ""),
        )
        actual = (str(source.get("version", "")), str(source.get("build", "")))
        if actual != expected:
            raise UnknownAssetError(
                "preset artwork does not match configured Luminar Neo source "
                f"{expected[0]}-{expected[1]}"
            )
        return payload

    def _resolve_preset_artwork(self, relative: str) -> Path:
        root = (self.asset_root / "materials" / "PresetPacks").resolve()
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise UnknownAssetError("preset artwork file is unavailable")
        return candidate
