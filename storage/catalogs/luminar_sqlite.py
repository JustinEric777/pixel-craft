"""SQLite catalog using the schema observed in Luminar Neo 1.28.0 (build 23071)."""

from __future__ import annotations

import hashlib
import json
import plistlib
import sqlite3
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

SCHEMA_VERSION = 155

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS volumes (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, guid_wide_ch TEXT NOT NULL, info_wide_ch TEXT NOT NULL, PRIMARY KEY (_id_int_64), UNIQUE(guid_wide_ch,info_wide_ch));
CREATE TABLE IF NOT EXISTS paths (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, volume_id_int_64 INTEGER NOT NULL, path_wide_ch TEXT NOT NULL, PRIMARY KEY (_id_int_64), FOREIGN KEY (volume_id_int_64) REFERENCES volumes (_id_int_64), UNIQUE(volume_id_int_64,path_wide_ch));
CREATE TABLE IF NOT EXISTS filters (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, name_wide_ch TEXT, library_order REAL NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS filter_attribute (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, _out_id_int_64 INTEGER NOT NULL UNIQUE, favourite_bool INTEGER NOT NULL DEFAULT 0, user_conditions_wide_ch TEXT NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_out_id_int_64) REFERENCES filters (_id_int_64));
CREATE TABLE IF NOT EXISTS images (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, guid_wide_ch TEXT NOT NULL UNIQUE, path_wide_ch TEXT NOT NULL, width INTEGER NOT NULL DEFAULT 0, height INTEGER NOT NULL DEFAULT 0, file_size_int_64 INTEGER NOT NULL DEFAULT 0, modification_date_int_64 INTEGER NOT NULL DEFAULT 0, import_date_int_64 INTEGER NOT NULL DEFAULT 0, import_index INTEGER NOT NULL DEFAULT 0, creation_date_int_64 INTEGER NOT NULL DEFAULT 0, file_type INTEGER NOT NULL DEFAULT 0, cloud_id_wide_ch TEXT NOT NULL DEFAULT '', updated_at_int_64 INTEGER NOT NULL DEFAULT 0, deleted_at_int_64 INTEGER NOT NULL DEFAULT 0, sync_status INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS image_user_attributes (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, _out_id_int_64 INTEGER NOT NULL UNIQUE, trash_bool INTEGER NOT NULL DEFAULT 0, marker INTEGER NOT NULL DEFAULT 0, color INTEGER NOT NULL DEFAULT 0, rating INTEGER NOT NULL DEFAULT 0, edit_date_int_64 INTEGER NOT NULL DEFAULT 0, opened_bool INTEGER NOT NULL DEFAULT 0, origin_path_wide_ch TEXT NOT NULL DEFAULT '', _trashed_date_int_64 INTEGER NOT NULL DEFAULT 0, lost_bool INTEGER NOT NULL DEFAULT 0, tutorial INTEGER NOT NULL DEFAULT 0, smart_search_indexed INTEGER NOT NULL DEFAULT 0, virtual_copy_bool INTEGER NOT NULL DEFAULT 0, virtual_copy_date_int_64 INTEGER NOT NULL DEFAULT 0, virtual_copy_number INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_out_id_int_64) REFERENCES images (_id_int_64));
CREATE TABLE IF NOT EXISTS image_exiv_attributes (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, _out_id_int_64 INTEGER NOT NULL UNIQUE, iso_speed REAL NOT NULL DEFAULT -1.0, shutter_speed REAL NOT NULL DEFAULT -1.0, number REAL NOT NULL DEFAULT -1.0, focal_len REAL NOT NULL DEFAULT -1.0, focal_len35mm REAL NOT NULL DEFAULT -1.0, ev REAL NOT NULL DEFAULT -1.0, focal_len_min REAL NOT NULL DEFAULT -1.0, focal_len_max REAL NOT NULL DEFAULT -1.0, shutter_min REAL NOT NULL DEFAULT -1.0, shutter_max REAL NOT NULL DEFAULT -1.0, aperture REAL NOT NULL DEFAULT 0.0, focus_distance REAL NOT NULL DEFAULT 0.0, bits_per_sample INTEGER NOT NULL DEFAULT 0, white_balance INTEGER NOT NULL DEFAULT -1, white_balance_index INTEGER NOT NULL DEFAULT -1, light_source INTEGER NOT NULL DEFAULT -1, metering_mode INTEGER NOT NULL DEFAULT -1, camera_maker_wide_ch TEXT, camera_name_wide_ch TEXT, camera_model_wide_ch TEXT, lens_maker_wide_ch TEXT, lens_pretty_name_wide_ch TEXT, date_time_int_64 INTEGER NOT NULL DEFAULT 0, date_time_tz_offset_min INTEGER NOT NULL DEFAULT 0, is_raw_bool INTEGER NOT NULL DEFAULT 0, analog_balance TEXT NOT NULL DEFAULT 'analog_balance: [1.0, 1.0, 1.0, 1.0]', ad_tone_exposure REAL NOT NULL DEFAULT 0.0, ad_tone_contrast REAL NOT NULL DEFAULT 0.0, is_full_filled_bool INTEGER NOT NULL DEFAULT 0, exiv_version INTEGER NOT NULL DEFAULT 0, duration REAL NOT NULL DEFAULT -1.0, exif_rating REAL NOT NULL DEFAULT 0.0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_out_id_int_64) REFERENCES images (_id_int_64));
CREATE TABLE IF NOT EXISTS tags (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, name_wide_ch TEXT, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS img_history_states (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, name_wide_ch TEXT NOT NULL, data_wide_ch TEXT NOT NULL, guid_wide_ch TEXT NOT NULL, crop_info_wide_ch TEXT NOT NULL, image_orientation_int_64 INTEGER NOT NULL DEFAULT 1, hash_wide_ch TEXT NOT NULL, state_version_wide_ch TEXT NOT NULL DEFAULT '0.7', original_bool INTEGER NOT NULL DEFAULT 0, cloud_id_wide_ch TEXT NOT NULL DEFAULT '', updated_at_int_64 INTEGER NOT NULL DEFAULT 0, deleted_at_int_64 INTEGER NOT NULL DEFAULT 0, sync_status INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS reffolders (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, id_path_int_64 INTEGER, guid_wide_ch TEXT NOT NULL, library_order REAL NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (id_path_int_64) REFERENCES paths (_id_int_64));
CREATE TABLE IF NOT EXISTS reffolder_attribute (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, _out_id_int_64 INTEGER NOT NULL UNIQUE, favourite_bool INTEGER NOT NULL DEFAULT 0, user_conditions_wide_ch TEXT NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_out_id_int_64) REFERENCES reffolders (_id_int_64));
CREATE TABLE IF NOT EXISTS entity_favorite_aliases (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, favorite_bool INTEGER NOT NULL DEFAULT 0, fav_order REAL NOT NULL DEFAULT 0, orig_entity_type TEXT NOT NULL, orig_entity_id_int_64 INTEGER NOT NULL DEFAULT -1, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS smart_filters (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, name_wide_ch TEXT, identifier_wide_ch TEXT, filter_conditions_wide_ch TEXT NOT NULL DEFAULT '', applying_conditions_wide_ch TEXT NOT NULL DEFAULT '', PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS smartfilter_attribute (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, _out_id_int_64 INTEGER NOT NULL UNIQUE, user_conditions_wide_ch TEXT NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_out_id_int_64) REFERENCES smart_filters (_id_int_64));
CREATE TABLE IF NOT EXISTS resources (_id_int_64 INTEGER NOT NULL, marked_to_delete_bool INTEGER NOT NULL DEFAULT 0, path_wide_ch TEXT NOT NULL, cloud_id_wide_ch TEXT NOT NULL DEFAULT '', updated_at_int_64 INTEGER NOT NULL DEFAULT 0, deleted_at_int_64 INTEGER NOT NULL DEFAULT 0, sync_status INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64));
CREATE TABLE IF NOT EXISTS reffolder_system (ancestor_int_64 INTEGER NOT NULL, descendant_int_64 INTEGER NOT NULL, PRIMARY KEY (ancestor_int_64,descendant_int_64));
CREATE TABLE IF NOT EXISTS filter_system (ancestor_int_64 INTEGER NOT NULL, descendant_int_64 INTEGER NOT NULL, PRIMARY KEY (ancestor_int_64,descendant_int_64));
CREATE TABLE IF NOT EXISTS smart_filter_system (ancestor_int_64 INTEGER NOT NULL, descendant_int_64 INTEGER NOT NULL, PRIMARY KEY (ancestor_int_64,descendant_int_64));
CREATE TABLE IF NOT EXISTS filters_images (_id_int_64 INTEGER NOT NULL, _key_id_int_64 INTEGER, _val_id_int_64 INTEGER, PRIMARY KEY (_id_int_64), FOREIGN KEY (_key_id_int_64) REFERENCES filters (_id_int_64), FOREIGN KEY (_val_id_int_64) REFERENCES images (_id_int_64));
CREATE UNIQUE INDEX IF NOT EXISTS fitler_image_idx ON filters_images(_key_id_int_64, _val_id_int_64);
CREATE TRIGGER IF NOT EXISTS filter_image_insert_trigger AFTER INSERT ON filters_images BEGIN SELECT NotifyFilterRefUpdate('filters_images', 'INSERT', NEW._key_id_int_64, NEW._val_id_int_64); END;
CREATE TRIGGER IF NOT EXISTS filter_image_delete_trigger AFTER DELETE ON filters_images BEGIN SELECT NotifyFilterRefUpdate('filters_images', 'DELETE', OLD._key_id_int_64, OLD._val_id_int_64); END;
CREATE TABLE IF NOT EXISTS paths_images (_key_id_int_64 INTEGER NOT NULL, _val_id_int_64 INTEGER NOT NULL, PRIMARY KEY (_key_id_int_64,_val_id_int_64));
CREATE TABLE IF NOT EXISTS tag_system (ancestor_int_64 INTEGER NOT NULL, descendant_int_64 INTEGER NOT NULL, PRIMARY KEY (ancestor_int_64,descendant_int_64));
CREATE TABLE IF NOT EXISTS image_history_state_proxy (_id_int_64 INTEGER NOT NULL, _image_id_int_64 INTEGER, _state_id_int_64 INTEGER, current INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (_id_int_64), FOREIGN KEY (_image_id_int_64) REFERENCES images (_id_int_64), FOREIGN KEY (_state_id_int_64) REFERENCES img_history_states (_id_int_64));
CREATE TABLE IF NOT EXISTS img_history_states_resources (_key_id_int_64 INTEGER NOT NULL, _val_id_int_64 INTEGER NOT NULL, FOREIGN KEY (_key_id_int_64) REFERENCES img_history_states (_id_int_64), FOREIGN KEY (_val_id_int_64) REFERENCES resources (_id_int_64));
CREATE TABLE IF NOT EXISTS settings (main_app_version INTEGER NOT NULL, db_version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS image_virtual_copy (_key_id_int_64 INTEGER NOT NULL, _val_id_int_64 INTEGER NOT NULL UNIQUE, FOREIGN KEY (_key_id_int_64) REFERENCES images (_id_int_64), FOREIGN KEY (_val_id_int_64) REFERENCES images (_id_int_64));
CREATE TABLE IF NOT EXISTS last_synced_at (images_int_64 INTEGER NOT NULL DEFAULT 0, img_history_states_int_64 INTEGER NOT NULL DEFAULT 0, resources_int_64 INTEGER NOT NULL DEFAULT 0);
"""

COLOR_TO_NATIVE = {None: 0, "red": 1, "yellow": 2, "green": 3, "blue": 4, "purple": 5}
NATIVE_TO_COLOR = {value: key for key, value in COLOR_TO_NATIVE.items()}
ORIENTATION_TO_DEGREES = {1: 0, 6: 90, 3: 180, 8: 270}
DEGREES_TO_ORIENTATION = {
    degrees: orientation for orientation, degrees in ORIENTATION_TO_DEGREES.items()
}


def _epoch_to_iso(value: int) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat() if value else None


def _root_volume_info() -> str:
    """Serialize the root volume using the keys present in Native schema v155."""
    info: dict[str, object] = {
        "kBSDNameSerializationKey": "",
        "kIsInternalSerializationKey": True,
        "kEjectableSerializationKey": False,
        "kVolumeUUIDSerializationKey": "",
        "kIsKeySensetiveSerializationKey": False,
        "kMountPointSerializationKey": "/",
    }
    try:
        result = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", "/"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        disk = plistlib.loads(result.stdout)
        info.update(
            {
                "kBSDNameSerializationKey": str(disk.get("DeviceIdentifier", "")),
                "kIsInternalSerializationKey": bool(disk.get("Internal", True)),
                "kEjectableSerializationKey": bool(disk.get("Ejectable", False)),
                "kVolumeUUIDSerializationKey": str(disk.get("VolumeUUID", "")),
                "kIsKeySensetiveSerializationKey": bool(disk.get("CaseSensitive", False)),
                "kMountPointSerializationKey": str(disk.get("MountPoint", "/")),
            }
        )
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException):
        # Sandboxed runtimes may deny Disk Arbitration. The six-key Native payload
        # remains structurally exact; unavailable device values stay empty.
        pass
    return json.dumps(info, separators=(",", ":"))


class LuminarCatalog:
    """Own one `.luminarneo` catalog; JSON is deliberately unsupported."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current not in {0, SCHEMA_VERSION}:
                raise RuntimeError(
                    f"unsupported Luminar catalog schema {current}; expected {SCHEMA_VERSION}"
                )
            connection.executescript(SCHEMA_SQL)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            if connection.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
                connection.execute(
                    "INSERT INTO settings(main_app_version, db_version) VALUES (?, ?)",
                    (6, SCHEMA_VERSION),
                )
            if connection.execute("SELECT COUNT(*) FROM last_synced_at").fetchone()[0] == 0:
                connection.execute(
                    "INSERT INTO last_synced_at(images_int_64, img_history_states_int_64, resources_int_64) VALUES (0, 0, 0)"
                )
            if connection.execute("SELECT COUNT(*) FROM volumes").fetchone()[0] == 0:
                connection.execute(
                    "INSERT INTO volumes(_id_int_64, guid_wide_ch, info_wide_ch) VALUES (1, '', '')"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.create_function("NotifyFilterRefUpdate", 4, lambda *_args: None)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def catalog_guid(project_id: str) -> str:
        return str(uuid.UUID(project_id)).upper()

    def records(self) -> list[dict[str, Any]]:
        query = """
            SELECT i._id_int_64, i.guid_wide_ch, i.path_wide_ch, i.file_size_int_64,
                   i.import_date_int_64, i.creation_date_int_64, u.trash_bool,
                   u.marker, u.color, u.rating, u.edit_date_int_64,
                   u._trashed_date_int_64, p.path_wide_ch AS directory,
                   h.image_orientation_int_64,
                   CASE WHEN h._id_int_64 IS NULL OR h.original_bool = 1 THEN 0 ELSE 1 END AS edit_count
              FROM images i
              JOIN image_user_attributes u ON u._out_id_int_64 = i._id_int_64
         LEFT JOIN paths_images pi ON pi._val_id_int_64 = i._id_int_64
         LEFT JOIN paths p ON p._id_int_64 = pi._key_id_int_64
         LEFT JOIN image_history_state_proxy hp
                ON hp._image_id_int_64 = i._id_int_64 AND hp.current = 1
         LEFT JOIN img_history_states h ON h._id_int_64 = hp._state_id_int_64
          ORDER BY i._id_int_64
        """
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        records = []
        for row in rows:
            directory = str(row["directory"] or "")
            source = Path("/") / directory / str(row["path_wide_ch"])
            project_id = str(uuid.UUID(str(row["guid_wide_ch"]))).replace("-", "")
            collection = (
                source.parent.parent.name if source.parent.parent.name != "uploads" else None
            )
            records.append(
                {
                    "asset_id": str(row["guid_wide_ch"]),
                    "project_id": project_id,
                    "filename": str(row["path_wide_ch"]),
                    "path": str(source),
                    "collection": collection,
                    "size": int(row["file_size_int_64"]),
                    "capture_time": _epoch_to_iso(int(row["creation_date_int_64"])),
                    "added_at": _epoch_to_iso(int(row["import_date_int_64"])),
                    "edited_at": _epoch_to_iso(int(row["edit_date_int_64"])),
                    "edit_count": int(row["edit_count"]),
                    "favorite": int(row["marker"]) == 1,
                    "rejected": int(row["marker"]) == -1,
                    "rating": int(row["rating"]),
                    "color_label": NATIVE_TO_COLOR.get(int(row["color"])),
                    "rotation": ORIENTATION_TO_DEGREES.get(
                        int(row["image_orientation_int_64"] or 1), 0
                    ),
                    "deleted_at": _epoch_to_iso(int(row["_trashed_date_int_64"]))
                    if row["trash_bool"]
                    else None,
                }
            )
        return records

    def upsert_asset(self, *, project_id: str, source: Path) -> str:
        guid = self.catalog_guid(project_id)
        stat = source.stat()
        now = int(datetime.now(UTC).timestamp())
        width = height = 0
        try:
            with Image.open(source) as image:
                width, height = image.size
        except (OSError, UnidentifiedImageError):
            pass
        directory = str(source.parent.resolve()).lstrip("/")
        with self._connect() as connection:
            volume = connection.execute(
                "SELECT _id_int_64 FROM volumes WHERE _id_int_64 <> 1 ORDER BY _id_int_64 LIMIT 1"
            ).fetchone()
            if volume is None:
                connection.execute(
                    "INSERT INTO volumes(_id_int_64, guid_wide_ch, info_wide_ch) VALUES (2, ?, ?)",
                    (str(uuid.uuid4()).upper(), _root_volume_info()),
                )
                volume_id = 2
            else:
                volume_id = int(volume[0])
            connection.execute(
                "INSERT OR IGNORE INTO paths(volume_id_int_64, path_wide_ch) VALUES (?, ?)",
                (volume_id, directory),
            )
            path_id = int(
                connection.execute(
                    "SELECT _id_int_64 FROM paths WHERE volume_id_int_64 = ? AND path_wide_ch = ?",
                    (volume_id, directory),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO images(guid_wide_ch, path_wide_ch, width, height,
                                   file_size_int_64, modification_date_int_64,
                                   import_date_int_64, creation_date_int_64)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid_wide_ch) DO UPDATE SET
                    path_wide_ch=excluded.path_wide_ch, width=excluded.width,
                    height=excluded.height, file_size_int_64=excluded.file_size_int_64,
                    modification_date_int_64=excluded.modification_date_int_64
                """,
                (
                    guid,
                    source.name,
                    width,
                    height,
                    stat.st_size,
                    int(stat.st_mtime),
                    now,
                    int(stat.st_ctime),
                ),
            )
            image_id = int(
                connection.execute(
                    "SELECT _id_int_64 FROM images WHERE guid_wide_ch = ?", (guid,)
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT OR IGNORE INTO image_user_attributes(_out_id_int_64, opened_bool) VALUES (?, 1)",
                (image_id,),
            )
            connection.execute("DELETE FROM paths_images WHERE _val_id_int_64 = ?", (image_id,))
            connection.execute(
                "INSERT INTO paths_images(_key_id_int_64, _val_id_int_64) VALUES (?, ?)",
                (path_id, image_id),
            )
        return guid

    def update_asset(self, asset_id: str, changes: dict[str, Any]) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT _id_int_64 FROM images WHERE guid_wide_ch = ?", (asset_id,)
            ).fetchone()
            if row is None:
                raise KeyError(asset_id)
            image_id = int(row[0])
            fields: dict[str, Any] = {}
            if "favorite" in changes or "rejected" in changes:
                fields["marker"] = (
                    1 if changes.get("favorite") else -1 if changes.get("rejected") else 0
                )
            if "rating" in changes:
                fields["rating"] = int(changes["rating"])
            if "color_label" in changes:
                if changes["color_label"] not in COLOR_TO_NATIVE:
                    raise ValueError("unsupported Luminar color label")
                fields["color"] = COLOR_TO_NATIVE[changes["color_label"]]
            if "deleted" in changes:
                deleted_at = int(datetime.now(UTC).timestamp()) if changes["deleted"] else 0
                fields.update(
                    {"trash_bool": int(changes["deleted"]), "_trashed_date_int_64": deleted_at}
                )
            if "rotation_delta" in changes:
                delta = int(changes["rotation_delta"])
                if delta % 90:
                    raise ValueError("Luminar catalog rotation must use 90-degree increments")
                current = connection.execute(
                    """
                    SELECT h._id_int_64, h.image_orientation_int_64
                      FROM image_history_state_proxy hp
                      JOIN img_history_states h ON h._id_int_64 = hp._state_id_int_64
                     WHERE hp._image_id_int_64 = ? AND hp.current = 1
                    """,
                    (image_id,),
                ).fetchone()
                current_orientation = (
                    int(current["image_orientation_int_64"] or 1) if current else 1
                )
                next_degrees = (ORIENTATION_TO_DEGREES.get(current_orientation, 0) + delta) % 360
                orientation = DEGREES_TO_ORIENTATION[next_degrees]
                now = int(datetime.now(UTC).timestamp())
                state_hash = hashlib.sha256(
                    f"orientation:{orientation}".encode()
                ).hexdigest()
                if current:
                    connection.execute(
                        "UPDATE img_history_states SET image_orientation_int_64 = ?, updated_at_int_64 = ?, hash_wide_ch = ? WHERE _id_int_64 = ?",
                        (orientation, now, state_hash, int(current["_id_int_64"])),
                    )
                else:
                    state_id = int(
                        connection.execute(
                            "SELECT COALESCE(MAX(_id_int_64), 0) + 1 FROM img_history_states"
                        ).fetchone()[0]
                    )
                    connection.execute(
                        """
                        INSERT INTO img_history_states(
                            _id_int_64, name_wide_ch, data_wide_ch, guid_wide_ch,
                            crop_info_wide_ch, image_orientation_int_64, hash_wide_ch,
                            state_version_wide_ch, original_bool, updated_at_int_64
                        ) VALUES (?, ?, '{}', ?, '{}', ?, ?, '0.7', 0, ?)
                        """,
                        (
                            state_id,
                            str(asset_id),
                            str(uuid.uuid4()).upper(),
                            orientation,
                            state_hash,
                            now,
                        ),
                    )
                    proxy_id = int(
                        connection.execute(
                            "SELECT COALESCE(MAX(_id_int_64), 0) + 1 FROM image_history_state_proxy"
                        ).fetchone()[0]
                    )
                    connection.execute(
                        "UPDATE image_history_state_proxy SET current = 0 WHERE _image_id_int_64 = ?",
                        (image_id,),
                    )
                    connection.execute(
                        "INSERT INTO image_history_state_proxy(_id_int_64, _image_id_int_64, _state_id_int_64, current) VALUES (?, ?, ?, 1)",
                        (proxy_id, image_id, state_id),
                    )
                fields["edit_date_int_64"] = now
            if fields:
                assignments = ", ".join(f"{key} = ?" for key in fields)
                connection.execute(
                    f"UPDATE image_user_attributes SET {assignments} WHERE _out_id_int_64 = ?",
                    (*fields.values(), image_id),
                )
