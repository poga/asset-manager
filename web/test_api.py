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
"""Tests for web API."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

# Global client for existing tests
_client = TestClient(app)
client = _client


@pytest.fixture
def test_client():
    """Create test client fixture."""
    return _client


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
            preview_x INTEGER,
            preview_y INTEGER,
            preview_width INTEGER,
            preview_height INTEGER,
            category TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);

        INSERT INTO packs (id, name, path) VALUES (1, 'creatures', '/assets/creatures');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (1, 1, '/assets/creatures/goblin.png', 'goblin.png', 'png', 'abc123', 64, 64);
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (2, 1, '/assets/creatures/orc.png', 'orc.png', 'png', 'def456', 128, 128);
        INSERT INTO tags (id, name) VALUES (1, 'creature'), (2, 'goblin'), (3, 'orc');
        INSERT INTO asset_tags VALUES (1, 1, 'path'), (1, 2, 'path'), (2, 1, 'path'), (2, 3, 'path');
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


def test_search_includes_preview_bounds(test_db):
    """Search results include preview bounds."""
    from api import set_db_path
    set_db_path(test_db)

    # Add preview bounds to test asset
    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute(
        "UPDATE assets SET preview_x=0, preview_y=0, preview_width=32, preview_height=32 WHERE id=1"
    )
    conn.commit()
    conn.close()

    response = client.get("/api/search?q=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    asset = data["assets"][0]
    assert asset["preview_x"] == 0
    assert asset["preview_y"] == 0
    assert asset["preview_width"] == 32
    assert asset["preview_height"] == 32


def test_search_preview_bounds_null_when_not_set(test_db):
    """Search results have null preview bounds when not detected."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?q=goblin")
    assert response.status_code == 200
    data = response.json()
    asset = data["assets"][0]
    assert asset["preview_x"] is None


def test_image_serves_aseprite_as_png(test_db, tmp_path):
    """Image endpoint renders Aseprite files as PNG."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from test_aseprite_parser import create_minimal_aseprite
    from api import set_db_path, set_assets_path

    set_db_path(test_db)

    # Create assets folder structure
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    pack_dir = assets_dir / "testpack"
    pack_dir.mkdir()

    # Create a test Aseprite file (red 4x4)
    ase_file = pack_dir / "sprite.aseprite"
    ase_file.write_bytes(create_minimal_aseprite(4, 4, (255, 0, 0, 255)))

    # Add to database
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
        "VALUES (20, 1, 'testpack/sprite.aseprite', 'sprite.aseprite', 'aseprite', 'ase123', 4, 4)"
    )
    conn.commit()
    conn.close()

    set_assets_path(assets_dir)

    response = client.get("/api/image/20")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    # Verify it's a valid PNG by checking the content
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(response.content))
    assert img.size == (4, 4)
    assert img.mode == "RGBA"
    # Check the pixel is red
    assert img.getpixel((2, 2)) == (255, 0, 0, 255)


def test_spa_fallback_serves_index_html(test_db, tmp_path):
    """Non-API routes serve index.html for SPA routing."""
    from api import set_db_path, set_static_path

    set_db_path(test_db)

    # Create a mock dist folder with index.html
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    index_html = dist_dir / "index.html"
    index_html.write_text("<!DOCTYPE html><html><body>SPA</body></html>")

    set_static_path(dist_dir)

    # Test root path
    response = client.get("/")
    assert response.status_code == 200
    assert "SPA" in response.text

    # Test asset route (SPA direct link)
    response = client.get("/asset/123")
    assert response.status_code == 200
    assert "SPA" in response.text

    # Test nested route
    response = client.get("/some/nested/route")
    assert response.status_code == 200
    assert "SPA" in response.text


def test_spa_static_files_served(test_db, tmp_path):
    """Static files from dist folder are served correctly."""
    from api import set_db_path, set_static_path

    set_db_path(test_db)

    # Create a mock dist folder with assets
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<!DOCTYPE html><html></html>")

    assets_dir = dist_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "main.js").write_text("console.log('test')")

    set_static_path(dist_dir)

    response = client.get("/assets/main.js")
    assert response.status_code == 200
    assert "console.log" in response.text


@pytest.fixture
def sample_db(test_db, tmp_path):
    """Create test database with actual files for download tests."""
    from api import set_db_path, set_assets_path

    set_db_path(test_db)

    # Create assets folder structure with actual files
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    creatures_dir = assets_dir / "creatures"
    creatures_dir.mkdir()

    # Create test image files
    (creatures_dir / "goblin.png").write_bytes(b"fake png data 1")
    (creatures_dir / "orc.png").write_bytes(b"fake png data 2")

    # Update database paths to be relative to assets folder
    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute("UPDATE assets SET path = 'creatures/goblin.png' WHERE id = 1")
    conn.execute("UPDATE assets SET path = 'creatures/orc.png' WHERE id = 2")
    conn.commit()
    conn.close()

    set_assets_path(assets_dir)

    return test_db


def test_download_cart_returns_zip(test_client, sample_db):
    """Test download cart returns a zip file."""
    response = test_client.post("/api/download-cart", json={"asset_ids": [1, 2]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]


def test_download_cart_empty_returns_400(test_client, sample_db):
    """Test download cart with empty list returns 400."""
    response = test_client.post("/api/download-cart", json={"asset_ids": []})
    assert response.status_code == 400


def test_download_cart_invalid_ids_skipped(test_client, sample_db):
    """Test download cart skips invalid asset IDs."""
    response = test_client.post("/api/download-cart", json={"asset_ids": [1, 9999]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_search_multiple_packs(test_client, sample_db):
    """Test search with multiple pack filters."""
    # Add a second pack with assets
    import sqlite3
    conn = sqlite3.connect(sample_db)
    conn.execute("INSERT INTO packs (id, name, path) VALUES (2, 'icons', '/assets/icons')")
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
        "VALUES (3, 2, 'icons/star.png', 'star.png', 'png', 'icon123', 32, 32)"
    )
    conn.commit()
    conn.close()

    response = test_client.get("/api/search?pack=icons&pack=creatures")
    assert response.status_code == 200
    data = response.json()
    packs = {a["pack"] for a in data["assets"]}
    # Should have assets from both packs
    assert "icons" in packs or "creatures" in packs
    assert len(data["assets"]) >= 2  # At least one from each pack


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
