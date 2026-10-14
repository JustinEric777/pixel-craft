from __future__ import annotations

from scripts.sync_luminar_presets import _active_effects, preserve_localization


def test_preset_import_flattens_every_edit_up_to_current_cursor() -> None:
    payload = {
        "layers_array": [
            {
                "alive": "true",
                "enabled": "true",
                "curr_edit_inedx": 1,
                "edits_array": [
                    {
                        "enabled": "true",
                        "permanent": "true",
                        "tool_name": "Develop",
                        "effects_array": [
                            {
                                "id": "first",
                                "params_array": [
                                    {"name": "Amount", "value": "12.0", "default": "0"}
                                ],
                            }
                        ],
                    },
                    {
                        "enabled": "true",
                        "permanent": "false",
                        "tool_name": "Curve",
                        "effects_array": [
                            {
                                "id": "second",
                                "params_array": [
                                    {
                                        "name": "RGB",
                                        "value": "50",
                                        "default": "50.0",
                                        "opt_data_type": "1",
                                        "opt_data_value": [0.5, 0.0, 0.0, 1.0, 1.0],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "enabled": "true",
                        "tool_name": "Future",
                        "effects_array": [
                            {
                                "id": "not-active",
                                "params_array": [
                                    {"name": "Amount", "value": "100", "default": "0"}
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
    }

    effects = _active_effects(payload)

    assert [effect["id"] for effect in effects] == ["first", "second"]
    assert effects[0]["source"]["edit_index"] == 0
    assert effects[1]["source"]["tool_name"] == "Curve"
    assert effects[1]["parameters"][0]["opt_data_value"][-2:] == [1.0, 1.0]


def test_graph_refresh_preserves_localized_labels() -> None:
    payload = {"presets": [{"id": "one", "name": "One"}]}
    existing = {
        "category_localization": {"City": "城市"},
        "presets": [
            {
                "id": "one",
                "localized_name": "一个",
                "localized_category": "城市",
            }
        ],
    }

    merged = preserve_localization(payload, existing)

    assert merged["presets"][0]["localized_name"] == "一个"
    assert merged["presets"][0]["localized_category"] == "城市"
    assert merged["category_localization"] == {"City": "城市"}
