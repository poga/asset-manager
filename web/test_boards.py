#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
#     "pillow>=10.0",
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
