#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
# ]
# ///
"""Tests for web API."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


@pytest.fixture
def test_db():
    """Create a temporary test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            version TEXT,
            preview_path TEXT,
            asset_count INTEGER DEFAULT 0
        );
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY,
            pack_id INTEGER,
            path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER,
            width INTEGER,
            height INTEGER,
            frame_count INTEGER,
            frame_width INTEGER,
            frame_height INTEGER
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);

        INSERT INTO packs (id, name, path) VALUES (1, 'creatures', '/assets/creatures');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (1, 1, '/assets/creatures/goblin.png', 'goblin.png', 'png', 'abc123', 64, 64);
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (2, 1, '/assets/creatures/orc.png', 'orc.png', 'png', 'def456', 128, 128);
        INSERT INTO tags (id, name) VALUES (1, 'creature'), (2, 'goblin'), (3, 'orc');
        INSERT INTO asset_tags VALUES (1, 1), (1, 2), (2, 1), (2, 3);
        INSERT INTO asset_colors VALUES (1, '#00ff00', 0.5), (2, '#ff0000', 0.6);
    """)
    conn.close()

    yield db_path
    db_path.unlink()


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_returns_all_assets(test_db):
    """Search with no filters returns all assets."""
    from api import app, set_db_path
    set_db_path(test_db)

    response = client.get("/api/search")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 2
    assert data["total"] == 2


def test_search_by_query(test_db):
    """Search by filename query."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?q=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert data["assets"][0]["filename"] == "goblin.png"


def test_search_by_tag(test_db):
    """Search by tag filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?tag=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert "goblin" in data["assets"][0]["tags"]


def test_search_by_color(test_db):
    """Search by color filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?color=green")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert data["assets"][0]["filename"] == "goblin.png"


def test_search_by_pack(test_db):
    """Search by pack filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?pack=creatures")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
