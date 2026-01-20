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
            frame_height INTEGER,
            analysis_method TEXT,
            animation_type TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);
        CREATE TABLE sprite_frames (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER,
            frame_index INTEGER,
            x INTEGER,
            y INTEGER,
            width INTEGER,
            height INTEGER
        );

        INSERT INTO packs (id, name, path) VALUES (1, 'creatures', '/assets/creatures');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (1, 1, '/assets/creatures/goblin.png', 'goblin.png', 'png', 'abc123', 64, 64);
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (2, 1, '/assets/creatures/orc.png', 'orc.png', 'png', 'def456', 128, 128);
        INSERT INTO tags (id, name) VALUES (1, 'creature'), (2, 'goblin'), (3, 'orc');
        INSERT INTO asset_tags VALUES (1, 1), (1, 2), (2, 1), (2, 3);
        INSERT INTO asset_colors VALUES (1, '#00ff00', 0.5), (2, '#ff0000', 0.6);
        INSERT INTO asset_phash VALUES (1, X'0000000000000000'), (2, X'0000000000000001');
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


def test_similar_returns_similar_assets(test_db):
    """Find similar returns assets by visual similarity."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/similar/1")
    assert response.status_code == 200
    data = response.json()
    assert "assets" in data
    # Asset 2 has hamming distance of 1 from asset 1
    assert len(data["assets"]) == 1
    assert data["assets"][0]["id"] == 2


def test_similar_respects_distance(test_db):
    """Find similar respects max distance parameter."""
    from api import set_db_path
    set_db_path(test_db)

    # Distance 0 should return nothing (only exact matches, excluding self)
    response = client.get("/api/similar/1?distance=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 0


def test_similar_not_found(test_db):
    """Find similar returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/similar/999")
    assert response.status_code == 404


def test_asset_detail(test_db):
    """Get asset detail returns full info."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["filename"] == "goblin.png"
    assert data["path"] == "/assets/creatures/goblin.png"
    assert data["pack"] == "creatures"
    assert "goblin" in data["tags"]
    assert len(data["colors"]) > 0


def test_asset_detail_not_found(test_db):
    """Get asset detail returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/999")
    assert response.status_code == 404


def test_filters_returns_options(test_db):
    """Get filters returns available filter options."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/filters")
    assert response.status_code == 200
    data = response.json()
    assert "packs" in data
    assert "tags" in data
    assert "colors" in data
    assert "creatures" in data["packs"]
    assert "creature" in data["tags"]


def test_image_not_found(test_db):
    """Image endpoint returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/image/999")
    assert response.status_code == 404


def test_image_serves_file(test_db, tmp_path):
    """Image endpoint serves actual image file."""
    from api import set_db_path, set_assets_path
    set_db_path(test_db)

    # Create assets folder structure
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    pack_dir = assets_dir / "testpack"
    pack_dir.mkdir()

    # Create a test image file (1x1 PNG)
    image_file = pack_dir / "test.png"
    # Minimal valid PNG (1x1 transparent pixel)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,  # 8-bit RGBA
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    image_file.write_bytes(png_data)

    # Update database with relative path (relative to assets folder)
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
        "VALUES (10, 1, 'testpack/test.png', 'test.png', 'png', 'test123', 1, 1)"
    )
    conn.commit()
    conn.close()

    # Set assets path
    set_assets_path(assets_dir)

    response = client.get("/api/image/10")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_asset_frames_returns_frame_data(test_db):
    """Get asset frames returns frame metadata."""
    from api import set_db_path
    set_db_path(test_db)

    # Add sprite frames for asset 1
    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (1, 0, 0, 0, 32, 32)"
    )
    conn.execute(
        "INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (1, 1, 32, 0, 32, 32)"
    )
    conn.commit()
    conn.close()

    response = client.get("/api/asset/1/frames")
    assert response.status_code == 200
    data = response.json()
    assert "frames" in data
    assert len(data["frames"]) == 2
    assert data["frames"][0]["x"] == 0
    assert data["frames"][1]["x"] == 32


def test_asset_frames_not_found(test_db):
    """Get asset frames returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/999/frames")
    assert response.status_code == 404


def test_asset_frames_empty_for_non_spritesheet(test_db):
    """Get asset frames returns empty list for non-spritesheet."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/1/frames")
    assert response.status_code == 200
    data = response.json()
    assert data["frames"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
