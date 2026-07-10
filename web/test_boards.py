#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
#     "pillow>=10.0",
#     "python-multipart>=0.0.9",
# ]
# ///
"""Tests for UI-created boards."""

import io
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import api

client = TestClient(api.app)


def _make_db(dir_path: Path) -> Path:
    db_path = dir_path / "assets.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
            version TEXT, theme TEXT, preview_path TEXT, preview_generated BOOLEAN DEFAULT FALSE,
            asset_count INTEGER DEFAULT 0, source TEXT DEFAULT 'indexed'
        );
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL, filetype TEXT NOT NULL, file_hash TEXT NOT NULL,
            file_size INTEGER, width INTEGER, height INTEGER,
            preview_x INTEGER, preview_y INTEGER, preview_width INTEGER, preview_height INTEGER,
            category TEXT, asset_kind TEXT DEFAULT 'image', rig TEXT, thumbnail_path TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        assets_dir = root / "assets"
        assets_dir.mkdir()
        db_path = _make_db(root)
        api.set_db_path(db_path)
        api.set_assets_path(assets_dir)
        yield {"root": root, "assets": assets_dir, "db": db_path}
        api.set_db_path(None)
        api.set_assets_path(None)


def png_bytes(color=(255, 0, 0), size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_filters_marks_board_packs(env):
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('Indexed Pack', 'p1', 'indexed')")
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('My Board', '.boards/my-board', 'user')")
    conn.commit()
    conn.close()

    data = client.get("/api/filters").json()
    by_name = {p["name"]: p for p in data["packs"]}
    assert by_name["My Board"]["is_board"] is True
    assert by_name["Indexed Pack"]["is_board"] is False
    assert isinstance(by_name["My Board"]["id"], int)


def test_slugify_and_unique(env):
    import boards
    assert boards.slugify("My Cool Board!") == "my-cool-board"
    assert boards.slugify("  A/B  c ") == "a-b-c"
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('x', '.boards/my-board', 'user')")
    conn.commit()
    assert boards.unique_slug(conn, "My Board") == "my-board-2"
    conn.close()


def test_validate_upload(env):
    import boards
    assert boards.validate_upload("a.PNG", png_bytes()) == "png"
    with pytest.raises(ValueError):
        boards.validate_upload("a.svg", b"<svg/>")
    with pytest.raises(ValueError):
        boards.validate_upload("a.png", b"x" * (boards.MAX_UPLOAD_BYTES + 1))


def test_validate_upload_rejects_corrupt_bytes(env):
    import boards
    with pytest.raises(ValueError):
        boards.validate_upload("bad.png", b"not an image")


def test_validate_upload_rejects_missing_filename(env):
    import boards
    with pytest.raises(ValueError):
        boards.validate_upload(None, png_bytes())
    with pytest.raises(ValueError):
        boards.validate_upload("", png_bytes())


def test_save_image_writes_file_and_dims(env):
    import boards
    rel, w, h = boards.save_image(env["assets"], "my-board", png_bytes(size=(12, 7)), "png")
    assert rel.startswith(".boards/my-board/")
    assert rel.endswith(".png")
    assert (env["assets"] / rel).exists()
    assert (w, h) == (12, 7)


def test_create_board(env):
    r = client.post("/api/boards", json={"name": "My Board", "tags": ["inspo"]})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My Board"
    assert body["path"] == ".boards/my-board"
    conn = sqlite3.connect(env["db"])
    row = conn.execute("SELECT source FROM packs WHERE id = ?", [body["id"]]).fetchone()
    assert row[0] == "user"
    tag = conn.execute(
        "SELECT tag FROM pack_tags WHERE pack_id = ?", [body["id"]]
    ).fetchone()
    conn.close()
    assert tag[0] == "inspo"


def test_create_board_duplicate_name(env):
    client.post("/api/boards", json={"name": "Dup"})
    r = client.post("/api/boards", json={"name": "Dup"})
    assert r.status_code == 409


def _create(name="Board"):
    return client.post("/api/boards", json={"name": name}).json()


def test_upload_images_creates_rows_and_files(env):
    board = _create("Uploads")
    files = [
        ("files", ("a.png", png_bytes((255, 0, 0)), "image/png")),
        ("files", ("b.png", png_bytes((0, 255, 0)), "image/png")),
    ]
    r = client.post(f"/api/boards/{board['id']}/images", files=files)
    assert r.status_code == 201
    body = r.json()
    assert len(body["assets"]) == 2
    for a in body["assets"]:
        assert (env["assets"] / a["path"]).exists()
    conn = sqlite3.connect(env["db"])
    prev = conn.execute(
        "SELECT preview_path FROM packs WHERE id = ?", [board["id"]]
    ).fetchone()[0]
    conn.close()
    assert prev == body["cover_asset_path"] == body["assets"][0]["path"]


def test_upload_rejects_bad_type(env):
    board = _create("Bad")
    r = client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.svg", b"<svg/>", "image/svg+xml"))],
    )
    assert r.status_code == 400
    conn = sqlite3.connect(env["db"])
    n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()
    assert n == 0


def test_upload_batch_with_corrupt_file_writes_nothing(env):
    board = _create("Atomic")
    files = [
        ("files", ("good.png", png_bytes(), "image/png")),
        ("files", ("bad.png", b"not an image", "image/png")),
    ]
    r = client.post(f"/api/boards/{board['id']}/images", files=files)
    assert r.status_code == 400
    conn = sqlite3.connect(env["db"])
    n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()
    assert n == 0
    board_dir = env["assets"] / ".boards" / "atomic"
    assert not board_dir.exists() or list(board_dir.iterdir()) == []


def test_upload_missing_board_404(env):
    r = client.post("/api/boards/999/images",
                    files=[("files", ("a.png", png_bytes(), "image/png"))])
    assert r.status_code == 404


def test_rename_board(env):
    board = _create("Old Name")
    r = client.patch(f"/api/boards/{board['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"
    assert r.json()["path"] == ".boards/old-name"  # slug fixed


def test_set_cover(env):
    board = _create("Cover")
    up = client.post(
        f"/api/boards/{board['id']}/images",
        files=[
            ("files", ("a.png", png_bytes((1, 1, 1)), "image/png")),
            ("files", ("b.png", png_bytes((2, 2, 2)), "image/png")),
        ],
    ).json()
    second = up["assets"][1]["id"]
    r = client.patch(f"/api/boards/{board['id']}", json={"cover_asset_id": second})
    assert r.status_code == 200
    assert r.json()["preview_path"] == up["assets"][1]["path"]


def test_set_cover_foreign_asset_400(env):
    board = _create("Guard")
    r = client.patch(f"/api/boards/{board['id']}", json={"cover_asset_id": 12345})
    assert r.status_code == 400


def test_pack_preview_serves_board_cover(env):
    board = _create("Preview Board")
    client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.png", png_bytes((9, 9, 9)), "image/png"))],
    )
    r = client.get("/api/pack-preview/Preview%20Board")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_delete_board_image(env):
    board = _create("Del")
    up = client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.png", png_bytes(), "image/png"))],
    ).json()
    a = up["assets"][0]
    r = client.delete(f"/api/asset/{a['id']}")
    assert r.status_code == 200
    assert not (env["assets"] / a["path"]).exists()
    conn = sqlite3.connect(env["db"])
    n = conn.execute("SELECT COUNT(*) FROM assets WHERE id = ?", [a["id"]]).fetchone()[0]
    conn.close()
    assert n == 0


def test_delete_asset_refuses_indexed(env):
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('P', 'p', 'indexed')")
    pid = conn.execute("SELECT id FROM packs WHERE path='p'").fetchone()[0]
    conn.execute(
        "INSERT INTO assets (pack_id, path, filename, filetype, file_hash) "
        "VALUES (?, 'p/x.png', 'x.png', 'png', 'h')", [pid])
    aid = conn.execute("SELECT id FROM assets WHERE path='p/x.png'").fetchone()[0]
    conn.commit(); conn.close()
    r = client.delete(f"/api/asset/{aid}")
    assert r.status_code == 400


def test_delete_board(env):
    board = _create("Whole")
    client.post(f"/api/boards/{board['id']}/images",
                files=[("files", ("a.png", png_bytes(), "image/png"))])
    r = client.delete(f"/api/boards/{board['id']}")
    assert r.status_code == 200
    assert not (env["assets"] / ".boards" / "whole").exists()
    conn = sqlite3.connect(env["db"])
    assert conn.execute("SELECT COUNT(*) FROM packs WHERE id = ?", [board["id"]]).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assets WHERE pack_id = ?", [board["id"]]).fetchone()[0] == 0
    conn.close()


def test_api_imports_under_server_layout():
    """Guard: `uvicorn web.api:app` must import without web/ pre-added to sys.path."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-c", "import web.api"],
        cwd=root, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
