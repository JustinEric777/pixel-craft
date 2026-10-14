import hashlib
import json
from pathlib import Path

from scripts.audit_external_luminar_assets import run


def test_external_asset_audit_uses_declared_version_and_never_copies(tmp_path: Path) -> None:
    source = tmp_path / "misleading-1.28-name"
    app = source / "Luminar Neo" / "App"
    install = app / "Luminar Neo"
    appinfo = app / "AppInfo" / "appinfo.ini"
    sky = install / "profiles" / "SkyTextures" / "Blue Sky.jpg"
    promo = install / "profiles" / "SkyTexturesPromo" / "Promo.jpg"
    appinfo.parent.mkdir(parents=True)
    sky.parent.mkdir(parents=True)
    promo.parent.mkdir(parents=True)
    appinfo.write_text(
        "[Version]\nPackageVersion=1.27.1.17225\nDisplayVersion=1.27.1.17225 x64\n",
        encoding="utf-8",
    )
    sky.write_bytes(b"same-sky")
    promo.write_bytes(b"promo")
    manifest = tmp_path / "registry.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "path": "materials/SkyTextures/Blue Sky.jpg",
                        "sha256": hashlib.sha256(b"same-sky").hexdigest(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = run(source, manifest)

    assert report["declared_version"]["package_version"] == "1.27.1.17225"
    assert report["target_build_match"] is False
    assert report["copy_performed"] is False
    assert report["count"] == 1
    assert report["project_hash_match_count"] == 1
    assert report["records"][0]["import_status"] == "already-present"
