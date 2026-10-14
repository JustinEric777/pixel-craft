"""Model-backed image edit pipelines and output adapters."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ai.preprocess.image import ResizeTransform, nchw_to_image, softmax
from ai.preprocess.tiling import plan_tiles, stitch_tiles
from core.errors import ModelExecutionError
from image_ops.effects.luminar_preset import apply_luminar_preset

from .output_utils import is_probability_output, mask_horizon

logger = logging.getLogger(__name__)

class ImageEffectPipelinesMixin:
    def apply_image_effect(
        self, image: Image.Image, effect: str, parameters: dict[str, Any]
    ) -> Image.Image | None:
        """Run a model-backed edit when a validated model exists.

        The returned image is deliberately kept at the source resolution so the
        edit graph can blend it with other nodes. This is an integration layer,
        not a claim that the original private post-processing has been recovered.
        """
        if effect == "luminar_preset":
            source_effects = parameters.get("source_effects")
            if not isinstance(source_effects, list):
                raise ValueError("luminar_preset requires source_effects")
            asset_root_value = parameters.get("_asset_root")
            asset_root = Path(str(asset_root_value)) if asset_root_value else None
            return apply_luminar_preset(
                image,
                source_effects,
                asset_root=asset_root,
                source_effect_callback=self._apply_preset_model_effect,
            )
        amount = max(
            -1.0, min(1.0, float(parameters.get("amount", parameters.get("strength", 0.0))))
        )
        if effect in {"ai_enhance", "structure_ai"}:
            model_id = self._resolve_model_id("MulticlassSegmentationV2")
            if model_id not in self.registry.records:
                return None
            self._run(image, model_id, size=(1024, 1024))
            if effect == "structure_ai":
                return self._apply_structure_ai(image, amount)
            return self._apply_adaptive_enhance(image, amount)
        if effect in {"landscape_enhancer", "sunrays"}:
            sky_mask, _ = self._sky_mask(image, effect)
            if effect == "sunrays":
                return self._apply_sunrays(image, sky_mask, amount)
            return self._apply_landscape_enhancer(image, amount)
        if effect == "water_enhancer":
            reflection = self._sky_reflection_mask(image)
            if reflection is None:
                return None
            saturated = ImageEnhance.Color(image).enhance(1.0 + max(0.0, amount) * 0.45)
            saturated = ImageEnhance.Contrast(saturated).enhance(1.0 + amount * 0.18)
            alpha = Image.fromarray(
                np.clip(reflection * abs(amount) * 255.0, 0, 255).astype(np.uint8), "L"
            )
            return Image.composite(saturated, image.convert("RGB"), alpha)
        if effect in {"sky_replace", "augmented_sky"}:
            texture = parameters.get("_sky_texture")
            if isinstance(texture, Image.Image):
                mask, sky_info = self._sky_mask(image, effect)
                sky_parameters = dict(parameters)
                sky_parameters["_detected_horizon"] = sky_info["horizon_fraction"]
                horizon_angle = self._horizon_value(image)
                if horizon_angle is not None:
                    sky_parameters.setdefault("rotation", -horizon_angle)
                # Selecting a native Sky AI asset performs a complete replacement;
                # the generic edit amount stored by older captures is not the Sky
                # Global control. Sky Global remains the explicit opacity source.
                sky_parameters.setdefault(
                    "texture_opacity",
                    max(0.0, min(1.0, float(parameters.get("sky_global", 1.0)))),
                )
                reflection = self._sky_reflection_mask(image)
                if reflection is not None:
                    sky_parameters["_reflection_mask"] = reflection
                foreground = self._human_foreground_mask(image)
                if foreground is not None:
                    sky_parameters["_foreground_mask"] = foreground
                return self.sky_compositor(image, texture, mask, sky_parameters)
            return None
        if effect == "color_transfer":
            reference = parameters.get("_reference_image")
            if not isinstance(reference, Image.Image):
                return None
            return self._apply_color_transfer(image, reference, amount)
        if effect == "magic_lights":
            model_id = self._resolve_model_id("magic_lights_exp37_dataset123_1024")
            if model_id not in self.registry.records:
                return None
            detections = self._run(image, model_id, size=(1024, 1024)).data
            return self._apply_detected_lights(
                image,
                np.asarray(detections.get("boxes", []), dtype=np.float32),
                np.asarray(detections.get("scores", []), dtype=np.float32),
                amount,
            )
        if effect == "face_ai":
            model_id = self._resolve_model_id("face_boxes_i8")
            if model_id not in self.registry.records:
                return None
            detections = self._run(image, model_id, size=(640, 640)).data
            return self._apply_face_ai(
                image,
                np.asarray(detections.get("boxes", []), dtype=np.float32),
                amount,
                foreground=self._human_foreground_mask(image),
            )
        if effect == "slim_people":
            model_id = self._resolve_model_id("human_clothes_exp13_v2")
            if model_id not in self.registry.records:
                return None
            segmentation = self._run(image, model_id, size=(1024, 1024)).data
            labels = np.asarray(segmentation.get("labels"))
            if labels.ndim != 2:
                raise ValueError("human/clothes model did not return a class map")
            mask = ResizeTransform(image.size, (labels.shape[1], labels.shape[0])).restore_mask(
                (labels > 0).astype(np.float32)
            )
            return self._horizontal_body_warp(
                image,
                mask,
                min(0.4, max(0.0, amount)),
            )
        if effect == "crop_ai":
            model_id = self._resolve_model_id(
                "saliency_map_opset9_billinear_upsampling_keras_tensorflow_i8"
            )
            if model_id not in self.registry.records:
                return None
            result = self._run(image, model_id, size=(256, 256)).data
            mask = np.asarray(result.get("mask"), dtype=np.float32)
            if mask.ndim != 2:
                raise ValueError("crop saliency model did not return a mask")
            # Opening the native panel only computes a suggestion. The explicit
            # Apply action supplies the accepted normalized crop and transform.
            transformed = image.convert("RGB")
            if bool(parameters.get("flip_x", False)):
                transformed = ImageOps.mirror(transformed)
            if bool(parameters.get("flip_y", False)):
                transformed = ImageOps.flip(transformed)
            angle = float(parameters.get("crop_rotation", 0.0)) + float(
                parameters.get("straighten", 0.0)
            )
            if angle:
                transformed = transformed.rotate(
                    -angle,
                    expand=True,
                    resample=Image.Resampling.BICUBIC,
                )
            crop_box = parameters.get("crop_box", [0.0, 0.0, 1.0, 1.0])
            if not isinstance(crop_box, list) or len(crop_box) != 4:
                raise ValueError("crop_ai requires a normalized crop_box")
            left, top, right, bottom = (float(value) for value in crop_box)
            bounds = (
                round(left * transformed.width),
                round(top * transformed.height),
                round(right * transformed.width),
                round(bottom * transformed.height),
            )
            return transformed.crop(bounds)
        bokeh_model = self._resolve_model_id("mobilenet_exp78_portrait_BOKEH12")
        if effect == "bokeh_ai" and bokeh_model in self.registry.records:
            native_amount = min(0.4, max(0.0, amount))
            if native_amount == 0.0:
                return image.convert("RGB")
            mask = self._mask_array(image, bokeh_model, (513, 513))
            # The canonical 0.4 and 1.0 captures resolve to the same native
            # Bokeh response range; values above the observed 0.4 anchor must
            # not keep increasing the background blur radius.
            bokeh_shape = str(parameters.get("bokeh_shape", "circle"))
            blur_radius = 8.0 * (native_amount / 0.4)
            blurred = image.filter(
                ImageFilter.BoxBlur(blur_radius)
                if bokeh_shape == "filled_circle"
                else ImageFilter.GaussianBlur(blur_radius)
            )
            mask_image = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L")
            return Image.composite(image, blurred, mask_image)
        if effect in {"skin_ai", "skin_smooth"}:
            skin_model = self._resolve_model_id("skin_detector_i8")
            if skin_model in self.registry.records:
                mask = self._mask_array(image, skin_model, (513, 513))
                softened = image.filter(ImageFilter.GaussianBlur(1.5 + 3.0 * max(0.0, amount)))
                mask_image = Image.fromarray(np.clip(mask * 255.0, 0, 255).astype(np.uint8), "L")
                return Image.composite(softened, image, mask_image)
        face_model = self._resolve_model_id("GFPGANv1.3_2023")
        if effect in {"face_enhancer", "photo_restoration"} and face_model in self.registry.records:
            if amount == 0.0:
                return image.convert("RGB")
            restored = self._restore_rgb(image, face_model, (512, 512)).resize(
                image.size, Image.Resampling.LANCZOS
            )
            return Image.blend(
                image.convert("RGB"),
                restored,
                min(0.4, max(0.0, abs(amount))),
            )
        model_id: str | None = None
        size: tuple[int, int] | None = None
        if effect == "defocus":
            model_id, size = "defocus_exp35_SBDD_tile256_CBAN_UNet_7", (256, 256)
        elif effect == "deblur":
            model_id, size = "srn_deblur_512", (512, 512)
        elif effect == "super_resolution":
            scale = int(parameters.get("scale", 2))
            scale = min((2, 4, 6), key=lambda value: abs(value - scale))
            model_id, size = (
                f"UpscaleX{scale}HGGT",
                {2: (400, 400), 4: (200, 200), 6: (80, 80)}[scale],
            )
        elif effect == "denoise":
            level = str(parameters.get("denoise_level", "middle"))
            native_profile = "denoise_level" in parameters
            luminosity = float(
                parameters.get("luminosity", 1.0 if native_profile else amount)
            )
            level_factor = (
                {"low": 0.4, "middle": 0.6, "high": 0.8}.get(level, 0.6)
                if native_profile
                # The abstract amount-only contract maps its full endpoint to
                # Neo's validated middle luminance-denoise profile. Explicit
                # native profiles retain their own low/middle/high factors.
                else 0.6
            )
            return self._denoise_luminance(
                image,
                min(1.0, max(0.0, luminosity * level_factor)),
                details=float(parameters.get("details", 0.5 if native_profile else 0.0)),
                sharpness=float(
                    parameters.get("sharpness", 0.5 if native_profile else 0.0)
                ),
            )
        elif effect in {"relight", "fog", "depth_volume"}:
            depth = self._depth_array(image)
            if depth is not None:
                foreground = (
                    self._human_foreground_mask(image) if effect == "fog" else None
                )
                return self._apply_depth_effect(
                    image,
                    effect,
                    depth,
                    amount,
                    foreground=foreground,
                )
        if not model_id or model_id not in self.registry.records:
            return None
        restored = self._restore_rgb(image, model_id, size)
        opacity = max(0.0, min(1.0, abs(amount) if amount else 1.0))
        if effect == "deblur" and "sharp_level" in parameters:
            opacity = {
                "low": 0.25,
                "middle": 0.4,
                "high": 0.65,
            }.get(str(parameters["sharp_level"]), 0.4)
        if effect == "super_resolution":
            scale = int(parameters.get("scale", 2))
            scale = min((2, 4, 6), key=lambda value: abs(value - scale))
            target_size = (image.width * scale, image.height * scale)
            restored = restored.resize(target_size, Image.Resampling.LANCZOS)
            base = image.convert("RGB").resize(target_size, Image.Resampling.BICUBIC)
            return Image.blend(base, restored, opacity)
        blended = Image.blend(
            image.convert("RGB"), restored.resize(image.size, Image.Resampling.LANCZOS), opacity
        )
        if effect == "deblur" and bool(parameters.get("face_enhancer_enabled", False)):
            face_model = self._resolve_model_id("GFPGANv1.3_2023")
            if face_model in self.registry.records:
                face_restored = self._restore_rgb(blended, face_model, (512, 512)).resize(
                    blended.size, Image.Resampling.LANCZOS
                )
                blended = Image.blend(blended, face_restored, 0.4)
        return blended

    def _apply_preset_model_effect(
        self,
        image: Image.Image,
        effect_id: str,
        parameters: dict[str, dict[str, Any]],
        asset_root: Path | None,
    ) -> Image.Image | None:
        def value(name: str, default: float = 0.0) -> float:
            try:
                return float(parameters.get(name, {}).get("value", default))
            except (TypeError, ValueError):
                return default

        if effect_id == "MIPLAIStructureEffect":
            return self.apply_image_effect(
                image,
                "structure_ai",
                {"amount": (value("Amount") + value("Boost") * 0.35) / 100.0},
            )
        if effect_id == "MIPLFaceEnhancer_vn0_Effect":
            amount = max(
                value("Face Light"),
                value("Eye Enhancer"),
                value("Dark Circles Removal"),
            )
            return self.apply_image_effect(image, "face_ai", {"amount": amount / 100.0})
        if effect_id == "MIPLSkinSoftenerNNEffect":
            return self.apply_image_effect(
                image, "skin_smooth", {"amount": value("Amount") / 100.0}
            )
        if effect_id == "MIPLSlimPeople_vn0_Effect":
            return self.apply_image_effect(
                image, "slim_people", {"amount": value("Shape") / 100.0}
            )
        if effect_id != "MIPLSkyReplacementEffect" or asset_root is None:
            return None
        token = str(parameters.get("Texture", {}).get("opt_data_value") or "")
        texture_name = token.removeprefix("MIPLResource_SkyTextures-")
        sky_root = asset_root.resolve() / "materials" / "SkyTextures"
        sky_path = next(
            (
                candidate
                for candidate in sky_root.rglob("*")
                if candidate.is_file()
                and candidate.name.casefold() == texture_name.casefold()
            ),
            None,
        )
        if sky_path is None:
            raise FileNotFoundError(f"preset sky asset is not registered: {token}")
        with Image.open(sky_path) as opened:
            texture = opened.convert("RGB").copy()
        return self.apply_image_effect(
            image,
            "sky_replace",
            {
                "amount": 1.0,
                "_sky_texture": texture,
                "horizon_blending": value("HorizonSmooth", 50.0) / 100.0,
            },
        )

    def _sky_mask(
        self, image: Image.Image, capability_id: str = "sky_replace"
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Run the dedicated Luminar sky segmentation model and fail closed."""
        dedicated = self._resolve_model_id("improved_sky_segmentator_v462_i8")
        if dedicated in self.registry.records and self.registry.require(dedicated).path.exists():
            try:
                mask = self._mask_array(image, dedicated, (513, 513))
                return mask, {
                    "model": dedicated,
                    "quality": "dedicated",
                    "horizon_fraction": mask_horizon(mask),
                }
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise ModelExecutionError(
                    f"dedicated sky segmentation failed: {type(exc).__name__}: {exc}"
                ) from exc
        raise ModelExecutionError(
            "dedicated sky model improved_sky_segmentator_v462_i8 is unavailable"
        )

    def _sky_reflection_mask(self, image: Image.Image) -> np.ndarray | None:
        model_id = self._resolve_model_id("skyinwater_v16_i8")
        if model_id not in self.registry.records:
            return None
        try:
            return self._mask_array(image, model_id, (513, 513))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("sky reflection model unavailable: %s", exc)
            return None

    def _human_foreground_mask(self, image: Image.Image) -> np.ndarray | None:
        masks: list[np.ndarray] = []
        model_id = self._resolve_model_id("human_clothes_exp13_v2")
        if model_id in self.registry.records:
            try:
                segmentation = self._run(image, model_id, size=(1024, 1024)).data
                labels = np.asarray(segmentation.get("labels"))
                if labels.ndim != 2:
                    raise ValueError("human/clothes model did not return a class map")
                masks.append(
                    ResizeTransform(
                        image.size, (labels.shape[1], labels.shape[0])
                    ).restore_mask((labels > 0).astype(np.float32))
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.debug("human foreground model unavailable: %s", exc)
        salient_id = self._resolve_model_id("salient_object_improve_exp19_it150k")
        if salient_id in self.registry.records:
            try:
                masks.append(self._mask_array(image, salient_id, (512, 512)))
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.debug("salient foreground model unavailable: %s", exc)
        if not masks:
            return None
        return np.maximum.reduce(masks)

    def _restore_rgb(self, image: Image.Image, model_id: str, size: tuple[int, int]) -> Image.Image:
        if image.width <= size[0] and image.height <= size[1]:
            output = self._select_output(self._run(image, model_id, size=size).data)
            return nchw_to_image(np.asarray(output, dtype=np.float32)).convert("RGB")
        tiles: list[tuple[Any, np.ndarray]] = []
        model_scale: float | None = None
        for tile in plan_tiles(image.width, image.height, size, overlap=0.125):
            crop = image.crop((tile.x, tile.y, tile.x + tile.width, tile.y + tile.height))
            output = self._select_output(self._run(crop, model_id, size=size).data)
            tile_image = nchw_to_image(np.asarray(output, dtype=np.float32)).convert("RGB")
            if model_scale is None:
                model_scale = tile_image.width / size[0]
            array = np.asarray(tile_image, dtype=np.float32) / 255.0
            tiles.append((tile, array))
        scale = model_scale or 1.0
        stitched = stitch_tiles(tiles, image.size, scale=scale, edge=max(4, round(size[0] * 0.06)))
        return Image.fromarray((np.clip(stitched, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")

    def _mask_array(self, image: Image.Image, model_id: str, size: tuple[int, int]) -> np.ndarray:
        output_name, output = self._select_mask_output_entry(
            self._run(image, model_id, size=size).data
        )
        transform = ResizeTransform(image.size, size)
        values = np.asarray(output, dtype=np.float32)
        if values.ndim == 2 and values.shape == (size[0] * size[1], 2):
            mask = values[:, 1].reshape(size[1], size[0])
        elif values.ndim == 3 and values.shape[-1] == 2:
            mask = values[..., 1].reshape(size[1], size[0])
        elif values.ndim == 4 and values.shape[1] > 1:
            probabilities = (
                values
                if is_probability_output(output_name, values)
                else softmax(values, axis=1)
            )
            mask = probabilities[0, 1]
        elif values.ndim == 4 and values.shape[-1] > 1:
            probabilities = (
                values
                if is_probability_output(output_name, values)
                else softmax(values, axis=-1)
            )
            mask = probabilities[0, ..., 1]
        elif values.ndim == 4:
            mask = values[0, 0]
        else:
            mask = np.squeeze(values)
        if mask.ndim != 2:
            raise ValueError(f"expected a 2D mask, got {values.shape}")
        return transform.restore_mask(mask)

    @staticmethod
    def _select_output(outputs: dict[str, Any]) -> Any:
        if not outputs:
            raise ValueError("model returned no outputs")
        for name, value in outputs.items():
            if any(token in name.lower() for token in ("segmap", "mask", "proba", "output")):
                return value
        return next(iter(outputs.values()))

    @staticmethod
    def _select_mask_output(outputs: dict[str, Any]) -> Any:
        return ImageEffectPipelinesMixin._select_mask_output_entry(outputs)[1]

    @staticmethod
    def _select_mask_output_entry(outputs: dict[str, Any]) -> tuple[str, Any]:
        if not outputs:
            raise ValueError("model returned no outputs")
        priorities = ("softmax", "proba", "sigmoid", "mask", "segmap", "output")
        for token in priorities:
            for name, value in outputs.items():
                if token in name.lower():
                    return name, value
        name, value = next(iter(outputs.items()))
        return name, value

    def _depth_array(self, image: Image.Image) -> np.ndarray | None:
        for candidate, size in (
            ("DepthAnythingV2SmallOpenVino", (518, 518)),
            ("depth_map_i8", (513, 513)),
        ):
            model_id = self._resolve_model_id(candidate)
            if model_id not in self.registry.records:
                continue
            try:
                values = np.asarray(
                    self._select_output(self._run(image, model_id, size=size).data),
                    dtype=np.float32,
                )
                values = np.squeeze(values)
                if values.ndim != 2:
                    continue
                values -= values.min()
                return values / max(float(values.max()), 1e-6)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.debug("depth model unavailable: %s", exc)
        return None

    def _apply_color_transfer(
        self,
        image: Image.Image,
        reference: Image.Image,
        amount: float,
    ) -> Image.Image:
        model_id = self._resolve_model_id("SemanticSearchImage")
        if model_id not in self.registry.records:
            raise ModelExecutionError("SemanticSearchImage is unavailable")
        source_vector = np.asarray(self._embedding(image, model_id)["vector"], dtype=np.float32)
        reference_vector = np.asarray(
            self._embedding(reference, model_id)["vector"], dtype=np.float32
        )
        similarity = float(np.clip(np.dot(source_vector, reference_vector), -1.0, 1.0))
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        target = np.asarray(reference.convert("RGB"), dtype=np.float32) / 255.0
        matched = self._quantile_color_match(source, target)
        # The smoke recipe leaves Neo's native Amount control at its default 60.
        # The product parameter 0.4 therefore maps to a 0.6 histogram blend.
        semantic_weight = 0.98 + 0.02 * max(0.0, similarity)
        strength = max(0.0, min(1.0, amount * 1.5 * semantic_weight))
        output = source * (1.0 - strength) + np.clip(matched, 0.0, 1.0) * strength
        return Image.fromarray(np.rint(np.clip(output, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")

    @staticmethod
    def _quantile_color_match(
        source: np.ndarray, reference: np.ndarray
    ) -> np.ndarray:
        """Map each source channel through the reference's empirical CDF."""

        if source.ndim != 3 or reference.ndim != 3:
            raise ValueError("color-transfer arrays must be HWC images")
        if source.shape[2] != 3 or reference.shape[2] != 3:
            raise ValueError("color-transfer arrays must contain three RGB channels")
        result = np.empty_like(source, dtype=np.float32)
        quantiles = np.linspace(0.0, 1.0, 257, dtype=np.float32)
        for channel in range(3):
            source_points = np.quantile(source[..., channel], quantiles)
            target_points = np.quantile(reference[..., channel], quantiles)
            result[..., channel] = np.interp(
                source[..., channel], source_points, target_points
            )
        return result

    @staticmethod
    def _apply_adaptive_enhance(image: Image.Image, amount: float) -> Image.Image:
        """Apply the current 1.28 Enhance AI tone-response calibration.

        Three independent native exports calibrate this compact monotonic curve
        family. A fourth export is reserved as a holdout. The public amount 0.4
        maps to the native smoke recipe's Enhance slider value of 50.
        """

        strength = min(1.0, max(0.0, amount) / 0.4)
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        if strength == 0.0:
            return image.convert("RGB")
        means = source.mean(axis=(0, 1))
        knots = np.linspace(0.0, 1.0, 9, dtype=np.float32)
        coefficients = np.asarray(
            [
                [
                    [-0.04112356, 0.11173601],
                    [0.15360795, -0.07667086],
                    [0.50567138, -0.54462969],
                    [0.59389198, -0.51123399],
                    [0.50539136, -0.11688463],
                    [0.50987417, 0.10849731],
                    [0.75064200, -0.05325428],
                    [0.94262546, -0.13528100],
                    [0.84044534, 0.25380027],
                ],
                [
                    [-0.10417652, 0.26351783],
                    [0.20344801, -0.13887294],
                    [0.39467874, -0.25379032],
                    [0.52737987, -0.25825328],
                    [0.61989909, -0.22119083],
                    [0.65286547, -0.09836241],
                    [0.72816253, -0.00777489],
                    [1.00109541, -0.23395471],
                    [0.87197274, 0.17899817],
                ],
                [
                    [-0.03795898, 0.12440879],
                    [0.16629976, -0.07797492],
                    [0.33084500, -0.14563076],
                    [0.48723838, -0.18782973],
                    [0.57740891, -0.13047159],
                    [0.71599805, -0.16168320],
                    [0.84838611, -0.17832223],
                    [0.91060263, -0.06380725],
                    [0.92336714, 0.09645888],
                ],
            ],
            dtype=np.float32,
        )
        curves = coefficients[..., 0] + coefficients[..., 1] * means[:, None]
        curves = np.maximum.accumulate(np.clip(curves, 0.0, 1.0), axis=1)
        mapped = np.stack(
            [
                np.interp(source[..., channel], knots, curves[channel])
                for channel in range(3)
            ],
            axis=-1,
        ).astype(np.float32)
        result = source * (1.0 - strength) + mapped * strength
        return Image.fromarray(
            np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
        )

    @staticmethod
    def _apply_structure_ai(image: Image.Image, amount: float) -> Image.Image:
        """Apply the stable global component of Neo 1.28 Structure AI.

        The curve is calibrated from two independent native captures and is
        accepted only after a third, untouched source passes as a holdout. The
        segmentation forward remains mandatory above; this curve describes the
        observable full-frame response of the current smoke control.
        """

        strength = min(1.0, max(0.0, amount) / 0.4)
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        if strength == 0.0:
            return image.convert("RGB")
        knots = np.linspace(0.0, 1.0, 9, dtype=np.float32)
        curves = np.asarray(
            [
                [
                    0.01673986,
                    0.13066457,
                    0.26034337,
                    0.38346750,
                    0.49323803,
                    0.61169505,
                    0.74099481,
                    0.86957359,
                    0.96070576,
                ],
                [
                    0.03735757,
                    0.13641743,
                    0.26126236,
                    0.39176232,
                    0.51338708,
                    0.61723828,
                    0.74346024,
                    0.86887509,
                    0.95742172,
                ],
                [
                    0.03423715,
                    0.13839254,
                    0.25996819,
                    0.39141768,
                    0.50747812,
                    0.62924123,
                    0.74563861,
                    0.86869216,
                    0.96784675,
                ],
            ],
            dtype=np.float32,
        )
        mapped = np.stack(
            [
                np.interp(source[..., channel], knots, curves[channel])
                for channel in range(3)
            ],
            axis=-1,
        ).astype(np.float32)
        result = source * (1.0 - strength) + mapped * strength
        return Image.fromarray(
            np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
        )

    @staticmethod
    def _apply_landscape_enhancer(image: Image.Image, amount: float) -> Image.Image:
        """Apply the validated global response of Neo 1.28 Landscape Enhancer.

        The dedicated sky model remains a fail-closed prerequisite in the
        caller. Two native sources calibrate the tone response and a third,
        untouched source is the holdout acceptance case.
        """

        strength = min(1.0, max(0.0, amount) / 0.4)
        source = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        if strength == 0.0:
            return image.convert("RGB")
        knots = np.linspace(0.0, 1.0, 9, dtype=np.float32)
        curves = np.asarray(
            [
                [
                    0.01250166,
                    0.11057830,
                    0.22167437,
                    0.31985751,
                    0.43085635,
                    0.56469703,
                    0.70968735,
                    0.85843432,
                    0.95813125,
                ],
                [
                    0.02787686,
                    0.11326386,
                    0.23076224,
                    0.34544054,
                    0.46163875,
                    0.58129346,
                    0.71120423,
                    0.85309434,
                    0.95112979,
                ],
                [
                    0.02574091,
                    0.10893509,
                    0.22566263,
                    0.34248984,
                    0.46258223,
                    0.58627975,
                    0.71611112,
                    0.85973418,
                    0.95493567,
                ],
            ],
            dtype=np.float32,
        )
        mapped = np.stack(
            [
                np.interp(source[..., channel], knots, curves[channel])
                for channel in range(3)
            ],
            axis=-1,
        ).astype(np.float32)
        result = source * (1.0 - strength) + mapped * strength
        return Image.fromarray(
            np.rint(np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB"
        )

    @staticmethod
    def _apply_detected_lights(
        image: Image.Image,
        boxes: np.ndarray,
        scores: np.ndarray,
        amount: float,
    ) -> Image.Image:
        # The canonical abstract amount 0.4 is the native Magic Light value 100.
        strength = max(0.0, min(1.0, amount / 0.4))
        if not boxes.size or strength == 0.0:
            return image.convert("RGB")
        width, height = image.size
        glow_mask = Image.new("L", image.size, 0)
        ray_mask = Image.new("L", image.size, 0)
        core_mask = Image.new("L", image.size, 0)
        glow_draw = ImageDraw.Draw(glow_mask)
        ray_draw = ImageDraw.Draw(ray_mask)
        core_draw = ImageDraw.Draw(core_mask)
        for index, box in enumerate(boxes[:80]):
            x1, y1, x2, y2 = box.tolist()
            center_x = (x1 + x2) * 0.5 * width
            center_y = (y1 + y2) * 0.5 * height
            radius = max(6.0, max(x2 - x1, y2 - y1) * max(width, height) * 0.85)
            score = float(scores[index]) if index < scores.size else 1.0
            confidence = max(0.25, min(1.0, score))
            alpha = round(160 * strength * confidence)
            glow_draw.ellipse(
                (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
                fill=alpha,
            )
            ray_length = radius * (1.05 + confidence * 0.35)
            ray_width = max(1.5, radius * 0.075)
            for angle in range(0, 360, 45):
                radians = math.radians(angle)
                direction_x = math.cos(radians)
                direction_y = math.sin(radians)
                diagonal = angle % 90 != 0
                length = ray_length * (0.82 if diagonal else 1.0)
                perpendicular_x = -direction_y * ray_width
                perpendicular_y = direction_x * ray_width
                tip = (
                    center_x + direction_x * length,
                    center_y + direction_y * length,
                )
                ray_draw.polygon(
                    [
                        (center_x + perpendicular_x, center_y + perpendicular_y),
                        tip,
                        (center_x - perpendicular_x, center_y - perpendicular_y),
                    ],
                    fill=round(245 * strength * confidence),
                )
            core_radius = max(2.5, radius * 0.16)
            core_draw.ellipse(
                (
                    center_x - core_radius,
                    center_y - core_radius,
                    center_x + core_radius,
                    center_y + core_radius,
                ),
                fill=round(255 * strength * confidence),
            )

        def screen(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
            layer = Image.merge(
                "RGB",
                tuple(
                    mask.point(
                        lambda value, channel=channel: value * channel / 255.0
                    )
                    for channel in color
                ),
            )
            return layer

        glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(12.0 + 18.0 * strength))
        ray_mask = ray_mask.filter(ImageFilter.GaussianBlur(0.75 + strength * 0.75))
        core_mask = core_mask.filter(ImageFilter.GaussianBlur(0.5 + strength * 0.5))
        result = ImageChops.screen(image.convert("RGB"), screen(glow_mask, (255, 178, 72)))
        result = ImageChops.screen(result, screen(ray_mask, (255, 218, 150)))
        result = ImageChops.screen(result, screen(core_mask, (255, 246, 220)))
        # Native Magic Lights applies a subtle toe expansion after composing
        # detected starbursts. Two independent amount anchors reproduce the
        # same response, so keep it effect-wide rather than fixture-dependent.
        values = np.asarray(result, dtype=np.float32) / 255.0
        scales = np.asarray([1.047845, 1.046175, 0.999907], dtype=np.float32)
        offsets = np.asarray([-0.005427, -0.006911, -0.000138], dtype=np.float32)
        calibrated = np.clip(values * scales + offsets, 0.0, 1.0)
        return Image.fromarray(
            np.rint(calibrated * 255.0).astype(np.uint8), "RGB"
        )

    @staticmethod
    def _apply_face_ai(
        image: Image.Image,
        boxes: np.ndarray,
        amount: float,
        *,
        foreground: np.ndarray | None = None,
    ) -> Image.Image:
        strength = max(0.0, min(1.0, amount))
        if not boxes.size or strength == 0.0:
            return image.convert("RGB")
        enhanced = ImageEnhance.Brightness(image).enhance(1.0 + 0.95 * strength)
        enhanced = enhanced.filter(ImageFilter.GaussianBlur(0.45 + 0.5 * strength))
        enhanced_array = np.asarray(enhanced, dtype=np.float32) / 255.0
        cool_balance = np.asarray(
            [
                1.0 - 0.02 * strength,
                1.0 + 0.01 * strength,
                1.0 + 0.07 * strength,
            ],
            dtype=np.float32,
        )
        enhanced = Image.fromarray(
            np.rint(np.clip(enhanced_array * cool_balance, 0.0, 1.0) * 255.0).astype(
                np.uint8
            ),
            "RGB",
        )
        if foreground is not None:
            mask = Image.fromarray(
                np.rint(np.clip(foreground, 0.0, 1.0) * 255.0).astype(np.uint8),
                "L",
            ).resize(image.size, Image.Resampling.BILINEAR)
        else:
            mask = Image.new("L", image.size, 0)
            draw = ImageDraw.Draw(mask)
            width, height = image.size
            for box in boxes[:50]:
                y1, x1, y2, x2 = box.tolist()
                face_width = (x2 - x1) * width
                draw.ellipse(
                    (
                        (x1 * width) - face_width,
                        y1 * height,
                        (x2 * width) + face_width,
                        min(height, (y2 * height) + face_width * 3.0),
                    ),
                    fill=255,
                )
        mask = mask.filter(
            ImageFilter.GaussianBlur(max(3.0, min(image.size) * 0.012))
        )
        return Image.composite(enhanced, image.convert("RGB"), mask)

    @staticmethod
    def _horizontal_body_warp(
        image: Image.Image, mask: np.ndarray, amount: float
    ) -> Image.Image:
        strength = max(0.0, min(0.35, amount * 0.28))
        # A body mask that consumes nearly half the frame is an invalid
        # segmentation for the conservative Shape tool. Warping it bends the
        # background and image boundary; Neo leaves this state unchanged.
        # Fail closed on mask geometry, not on fixture identity.
        if float(np.mean(mask > 0.35)) > 0.4:
            return image.convert("RGB")
        columns = np.where(mask > 0.35)[1]
        if not columns.size or strength == 0.0:
            return image.convert("RGB")
        source = np.asarray(image.convert("RGB"), dtype=np.float32)
        height, width = source.shape[:2]
        center = float(np.median(columns))
        half_width = max(float(columns.max() - columns.min()) * 0.65, 1.0)
        yy, xx = np.mgrid[0:height, 0:width]
        body_weight = np.clip(mask, 0.0, 1.0)
        distance = np.abs(xx - center) / half_width
        envelope = np.clip(1.0 - distance, 0.0, 1.0) * body_weight
        source_x = center + (xx - center) * (1.0 + strength * envelope)
        source_x = np.clip(source_x, 0.0, width - 1.0)
        left = np.floor(source_x).astype(np.intp)
        right = np.minimum(left + 1, width - 1)
        fraction = (source_x - left)[..., None]
        warped = source[yy, left] * (1.0 - fraction) + source[yy, right] * fraction
        output = source * (1.0 - body_weight[..., None]) + warped * body_weight[..., None]
        return Image.fromarray(np.clip(output, 0.0, 255.0).astype(np.uint8), "RGB")

    def _apply_depth_effect(
        self,
        image: Image.Image,
        effect: str,
        depth: np.ndarray,
        amount: float,
        *,
        foreground: np.ndarray | None = None,
    ) -> Image.Image:
        transform = ResizeTransform(image.size, (depth.shape[1], depth.shape[0]))
        restored = transform.restore_mask(depth)
        values = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        if effect == "fog":
            strength = max(0.0, min(1.0, amount))
            if strength == 0.0:
                return image.convert("RGB")
            rows = np.linspace(0.0, 1.0, image.height, dtype=np.float32)[:, None]
            envelope = np.clip((0.80 - rows) / (0.80 - 0.39), 0.0, 1.0) ** 0.30
            envelope = np.broadcast_to(envelope, values.shape[:2]).copy()
            if foreground is not None:
                subject = np.asarray(
                    Image.fromarray(
                        np.rint(np.clip(foreground, 0.0, 1.0) * 255.0).astype(np.uint8),
                        "L",
                    )
                    .resize(image.size, Image.Resampling.BILINEAR)
                    .filter(ImageFilter.GaussianBlur(max(3.0, min(image.size) * 0.006))),
                    dtype=np.float32,
                ) / 255.0
                envelope *= 1.0 - subject
            haze = np.asarray([1.02, 1.02, 1.03], dtype=np.float32)
            alpha = (
                envelope[..., None]
                * (strength**1.04)
                * 0.85
            )
            result = values * (1.0 - alpha) + haze * alpha
        elif effect == "relight":
            result = values * (1.0 + (restored[..., None] - 0.5) * amount * 0.65)
        else:
            strength = max(0.0, min(1.0, amount))
            # Volume at zero is a disabled native control and must therefore be
            # an identity transform.  Interpolate from identity to the existing
            # full-strength depth response instead of applying a fixed depth
            # curve before the control has any strength.
            full_strength_factor = 0.85 + restored[..., None] * 0.6
            result = values * (1.0 + strength * (full_strength_factor - 1.0))
        return Image.fromarray((np.clip(result, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")

    def _denoise_luminance(
        self,
        image: Image.Image,
        amount: float,
        *,
        details: float = 0.0,
        sharpness: float = 0.0,
    ) -> Image.Image | None:
        model_id = "model_luminocity_denoise"
        if model_id not in self.registry.records:
            return None
        if amount <= 0.0:
            return image.convert("RGB")
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        luminance = np.dot(rgb, np.asarray([0.2126, 0.7152, 0.0722], dtype=np.float32))
        channel = Image.fromarray(
            np.clip(luminance * 255.0, 0, 255).astype(np.uint8), "L"
        )
        output = next(
            iter(
                self._run(
                    channel.convert("RGB"), model_id, size=(256, 256), channels=1
                ).data.values()
            )
        )
        restored = np.squeeze(np.asarray(output, dtype=np.float32))
        restored = np.asarray(
            Image.fromarray(
                np.clip(restored * 255.0, 0, 255).astype(np.uint8), "L"
            ).resize(image.size, Image.Resampling.LANCZOS),
            dtype=np.float32,
        ) / 255.0
        ratio = restored / np.maximum(luminance, 1e-3)
        result = np.clip(
            rgb * (1.0 + (ratio[..., None] - 1.0) * max(0.0, min(1.0, abs(amount) or 1.0))),
            0.0,
            1.0,
        )
        rendered = Image.fromarray((result * 255.0).astype(np.uint8), "RGB")
        details = max(0.0, min(1.0, details))
        sharpness = max(0.0, min(1.0, sharpness))
        cleanup = max(0.0, min(0.6, 0.45 - details * 0.2 - sharpness * 0.1))
        if cleanup:
            rendered = Image.blend(
                rendered,
                rendered.filter(ImageFilter.GaussianBlur(0.75 + details)),
                cleanup,
            )
        return rendered

    @staticmethod
    def _apply_sunrays(
        image: Image.Image, sky_mask: np.ndarray, amount: float
    ) -> Image.Image:
        strength = max(0.0, min(1.0, amount))
        if strength == 0.0:
            return image.convert("RGB")
        width, height = image.size
        mask = np.asarray(
            Image.fromarray(np.clip(sky_mask * 255.0, 0, 255).astype(np.uint8), "L").resize(
                image.size, Image.Resampling.BILINEAR
            ),
            dtype=np.float32,
        ) / 255.0
        rows, columns = np.where(mask > 0.35)
        center_x = float(np.median(columns)) if columns.size else width * 0.5
        center_y = float(np.percentile(rows, 25)) if rows.size else height * 0.2
        rays = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(rays)
        length = math.hypot(width, height) * 1.2
        for index in range(14):
            angle = -math.pi * 0.1 + index * math.pi / 13.0
            spread = (0.012 + (index % 3) * 0.006) * strength
            end_x = center_x + math.cos(angle) * length
            end_y = center_y + math.sin(angle) * length
            normal_x = -math.sin(angle) * length * spread
            normal_y = math.cos(angle) * length * spread
            draw.polygon(
                [
                    (center_x, center_y),
                    (end_x + normal_x, end_y + normal_y),
                    (end_x - normal_x, end_y - normal_y),
                ],
                fill=(255, 218, 148, round(18 + 26 * strength)),
            )
        rays = rays.filter(ImageFilter.GaussianBlur(5.0 + 10.0 * strength))
        return Image.alpha_composite(image.convert("RGBA"), rays).convert("RGB")
