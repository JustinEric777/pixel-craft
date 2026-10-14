import json
import sqlite3
import uuid
from pathlib import Path

from PIL import Image

from storage.catalogs import LuminarCatalog


def test_catalog_rotation_roundtrip_uses_current_v155_history_state(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (40, 20), (20, 40, 60)).save(source)
    catalog = LuminarCatalog(tmp_path / "catalog.luminarneo")
    asset_id = catalog.upsert_asset(project_id=uuid.uuid4().hex, source=source)

    catalog.update_asset(asset_id, {"rotation_delta": 90})
    assert catalog.records()[0]["rotation"] == 90
    assert catalog.records()[0]["edit_count"] == 1

    catalog.update_asset(asset_id, {"rotation_delta": -90})
    assert catalog.records()[0]["rotation"] == 0
    with sqlite3.connect(catalog.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM img_history_states").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM image_history_state_proxy WHERE current = 1"
        ).fetchone()[0] == 1


def test_catalog_uses_native_schema_version_and_round_trips_attributes(tmp_path: Path) -> None:
    source = tmp_path / "workspace" / "uploads" / "asset" / "photo.jpg"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (32, 24), (20, 40, 60)).save(source)
    project_id = "0123456789abcdef0123456789abcdef"
    catalog_path = tmp_path / "library" / "catalog.luminarneo"
    catalog = LuminarCatalog(catalog_path)

    asset_id = catalog.upsert_asset(project_id=project_id, source=source)
    catalog.update_asset(asset_id, {"favorite": True, "rating": 4})
    [record] = catalog.records()
    assert record["project_id"] == project_id
    assert record["path"] == str(source)
    assert record["favorite"] is True
    assert record["rating"] == 4
    assert record["edit_count"] == 0
    assert record["rotation"] == 0
    with sqlite3.connect(catalog_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 155
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
        }
        exiv_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(image_exiv_attributes)")
        ]
        assert connection.execute("SELECT * FROM settings").fetchall() == [(6, 155)]
        assert connection.execute("SELECT * FROM last_synced_at").fetchall() == [(0, 0, 0)]
        volumes = connection.execute(
            "SELECT _id_int_64, guid_wide_ch, info_wide_ch FROM volumes ORDER BY _id_int_64"
        ).fetchall()
        path_volume = connection.execute("SELECT volume_id_int_64 FROM paths").fetchone()[0]
        assert connection.execute("SELECT * FROM img_history_states").fetchall() == []
        assert connection.execute("SELECT * FROM image_history_state_proxy").fetchall() == []
    assert {
        "images",
        "paths",
        "paths_images",
        "image_user_attributes",
        "img_history_states",
    } <= tables
    assert triggers == {"filter_image_insert_trigger", "filter_image_delete_trigger"}
    assert exiv_columns[25:28] == [
        "date_time_int_64",
        "date_time_tz_offset_min",
        "is_raw_bool",
    ]
    assert volumes[0] == (1, "", "")
    assert volumes[1][0] == 2
    assert set(json.loads(volumes[1][2])) == {
        "kBSDNameSerializationKey",
        "kIsInternalSerializationKey",
        "kEjectableSerializationKey",
        "kVolumeUUIDSerializationKey",
        "kIsKeySensetiveSerializationKey",
        "kMountPointSerializationKey",
    }
    assert path_volume == 2
