"""Build discovery-only parity metadata from the local Luminar inventory.

The current parameter schema is an explicit Native/UI contract maintained in
``configs/capabilities/parameter-schema.json``.  Inventory discovery must never
regenerate or overwrite it with generic ``amount``/``opacity`` guesses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EFFECT_MAP = {
    "AIEnhanceAdjustmentLayer": "ai_enhance",
    "MaskingTool": "mask_ai",
    "MPCropToolFilter": "crop_ai",
    "MPLayerProperties": "layers",
    "ERASE": "erase",
    "AIStructureEffect": "structure_ai",
    "ExtendedColorAdjustmentLayer": "color_adjustments",
    "BWChannels_v1_Effect": "bw_channels",
    "DefaultEffects": "default_effects",
    "DefaultEffectsRAW": "raw_default_effects",
    "DetailsEnhancerAdjustmentLayer": "details",
    "DenoiseLaplacianEffect": "denoise",
    "LandscapeEnhancerAdjustmentLayer": "landscape_enhancer",
    "VignetteAdjustmentLayer": "vignette",
    "SkyReplacementAdjustmentLayer": "sky_replace",
    "AugmentedSkyEffect": "augmented_sky",
    "AIFogEffect": "fog",
    "SunLightRaysAdjustmentLayer": "sunrays",
    "ComplexBleachAdjustmentLayer": "complex_bleach",
    "LUTMappingEffect": "lut_mapping",
    "ColorToningAdjustmentLayer": "color_toning",
    "FadeEffect": "fade",
    "ImageRadianceAdjustmentLayer": "radiance",
    "GlowOrtonAdjustmentLayer": "glow_orton",
    "GrainNewAdjustmentLayer": "grain",
    "BlurEffect": "bokeh_ai",
    "NewNeonLightEffect": "new_neon_light",
    "ColorTransferEffect": "color_transfer",
    "WaterAIEffect": "water_enhancer",
    "BlueHourEffect": "blue_hour",
    "VirtualFlashLightEffect": "virtual_flash",
    "MagicLightsEffect": "magic_lights",
    "AIBokehEffect": "bokeh_ai",
    "FaceEnhancer_vn0_Effect": "face_enhancer",
    "FaceEnhancer_vn0_EffectNew": "face_enhancer",
    "FaceEnhancerEffect": "face_enhancer",
    "SkinSoftenerNNEffect": "skin_smooth",
    "SkinSmoothEffect": "skin_smooth",
    "SlimPeopleEffect": "slim_people",
    "SlimPeople_vn0_Effect": "slim_people",
    "HighKeyAdjustmentLayer": "high_key",
    "ProContrastAdjustmentLayer": "pro_contrast",
    "ColorEnhancerAdjustmentLayer": "color_enhancer",
    "DodgeBurnAdjustmentLayer": "dodge_burn",
    "CLONE": "clone",
    "DodgeAndBurnEffect": "dodge_burn",
    "DenoiseAI": "denoise",
    "AI Adjustments": "ai_enhance",
    "DeblurAI": "deblur",
    "AIFaceDepthEffect": "depth_volume",
    "DepthVolumeEffect": "depth_volume",
    "AIBokehNewEffect": "bokeh_ai",
    "HDRMerge": "hdr_merge",
    "FocusStacking": "focus_stacking",
    "PanoramaStitching": "panorama_stitching",
    "UpscaleAI": "super_resolution",
    "PhotoRestoration": "photo_restoration",
}

MODEL_MAP = {
    "sky": ["improved_sky_segmentator_v462_i8", "skyinwater_v16_i8", "horizon_align_i8"],
    "depth": ["depth_map_i8", "DepthAnythingV2SmallOpenVino"],
    "face": [
        "face_detector_retinaface",
        "face_boxes_i8",
        "face_landmarks_i8",
        "eyes_detector_i8",
        "IrisLandmarks",
    ],
    "portrait": ["skin_detector_i8", "hair_exp11_i8", "human_clothes_exp13_v2", "GFPGANv1.3_2023"],
    "restore": [
        "model_luminocity_denoise",
        "srn_deblur_512",
        "defocus_exp35_SBDD_tile256_CBAN_UNet_7",
    ],
}

GROUP_ARTIFACTS = {
    "sky": ["sky_mask", "sky_in_water_mask", "horizon_line"],
    "portrait": ["face_boxes", "face_landmarks", "skin_mask", "hair_mask", "iris_landmarks"],
    "restore": ["source_image"],
    "masking": ["salient_mask", "object_masks", "human_mask"],
    "light": ["depth_map", "light_boxes"],
}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    capabilities = json.loads(args.registry.read_text(encoding="utf-8")).get("capabilities", [])
    by_id = {item["id"]: item for item in capabilities}
    matrix = []
    for effect_id in inventory.get("effect_ids", []):
        if effect_id in {"GenErase", "GenSwap", "GenExpand"}:
            continue
        capability_id = EFFECT_MAP.get(effect_id)
        item = by_id.get(capability_id or "")
        group = item.get("group", "unknown") if item else "unknown"
        models = []
        for key, values in MODEL_MAP.items():
            if key in group or (capability_id and key in capability_id):
                models.extend(values)
        assets = {
            "sky": ["sky", "atmosphere"],
            "portrait": ["face_relight", "face_zones", "makeup", "contact_lens"],
            "color": ["lut", "color_transfer"],
            "light": ["atmosphere", "overlay"],
        }.get(group, [])
        matrix.append(
            {
                "original_effect_id": effect_id,
                "capability_id": capability_id,
                "group": group,
                "original_status": "observed",
                "models": sorted(set(models)),
                "assets": assets,
                "artifacts": GROUP_ARTIFACTS.get(group, []),
                "parameters": ["amount", "opacity"]
                + (
                    ["asset_id"]
                    if capability_id
                    in {"sky_replace", "augmented_sky", "color_transfer", "lut_mapping"}
                    else []
                ),
                "validation_status": "not_started",
            }
        )
    tools = [
        {"original_tool_name": name, "capability_id": EFFECT_MAP.get(name)}
        for name in inventory.get("tool_names", [])
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "parity-matrix.json").write_text(
        json.dumps({"version": "0.2.0", "records": matrix}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "tool-mappings.json").write_text(
        json.dumps({"version": "0.2.0", "records": tools}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "effects": len(matrix),
                "tools": len(tools),
                "capabilities": len(capabilities),
                "parameter_schema": "authoritative-current-contract-not-generated",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
