import json
from pathlib import Path

from scripts.validate_native_persistence_roundtrip import REQUIRED_STATES, validate

REFERENCE_ID = "luminar-neo-macos-1.28.0-23071"


def test_missing_manifest_fails_closed(tmp_path: Path) -> None:
    report = validate(tmp_path / "missing.json", REFERENCE_ID)

    assert report["gate"] == "blocked"
    assert report["issue_count"] == 1


def test_complete_native_roundtrip_manifest_passes(tmp_path: Path) -> None:
    digest = "a" * 64
    manifest = tmp_path / "roundtrip.json"
    manifest.write_text(
        json.dumps(
            {
                "reference_id": REFERENCE_ID,
                "native_provenance": {
                    "app_id": "com.skylum.luminarneo",
                    "version": "1.28.0",
                    "build": "23071",
                    "source_hash": digest,
                    "snapshot_hash": digest,
                    "fullscreen": True,
                    "isolated_display": True,
                    "isolated_input": True,
                },
                "roundtrips": [
                    {
                        "state": state,
                        "status": "passed",
                        "serialized_hash": digest,
                        "reload_hash": digest,
                        "output_hash": digest,
                    }
                    for state in REQUIRED_STATES
                ],
                "active_repositories": ["native-catalog", "native-resource-store"],
                "restart_status": "passed",
            }
        ),
        encoding="utf-8",
    )

    assert validate(manifest, REFERENCE_ID)["gate"] == "passed"
