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
            theme TEXT,
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
            category TEXT,
            asset_kind TEXT,
            rig TEXT,
            thumbnail_path TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);
        CREATE TABLE asset_preview_overrides (
            path TEXT PRIMARY KEY,
            use_full_image BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE asset_relations (
            asset_id INTEGER NOT NULL,
            related_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            PRIMARY KEY (asset_id, related_id)
        );
        CREATE TABLE asset_animations (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER NOT NULL,
            clip_index INTEGER NOT NULL,
            name TEXT NOT NULL
        );

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


def test_health_check_under_vite_base():
    """Frontend calls /assets/api/... because of Vite's base config; the API
    must respond there too, not fall through to the SPA fallback (which
    returns HTML and breaks JSON parsing in the browser)."""
    response = client.get("/assets/api/health")
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
    pack_names = [p["name"] for p in data["packs"]]
    assert "creatures" in pack_names
    assert "creature" in data["tags"]


def test_filters_include_theme_and_is_3d(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO packs (id, name, path, theme, asset_count) "
        "VALUES (10, 'Forest3D', 'Forest3D', 'Nature', 2)"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (100, 10, 'Forest3D/a.glb', 'a.glb', 'glb', 'h1', 'model')"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (101, 10, 'Forest3D/b.glb', 'b.glb', 'glb', 'h2', 'model')"
    )
    conn.execute(
        "INSERT INTO packs (id, name, path, asset_count) "
        "VALUES (11, 'Sprites2D', 'Sprites2D', 1)"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (102, 11, 'Sprites2D/s.png', 's.png', 'png', 'h3', 'image')"
    )
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    packs = {p["name"]: p for p in resp.json()["packs"]}
    assert packs["Forest3D"]["theme"] == "Nature"
    assert packs["Forest3D"]["is_3d"] is True
    assert packs["Sprites2D"]["theme"] == "Other"  # NULL theme -> Other
    assert packs["Sprites2D"]["is_3d"] is False


def test_filters_tolerate_db_without_theme_column(tmp_path):
    # live DBs are only migrated by the indexer; the API must not 500
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE packs (id INTEGER PRIMARY KEY, name TEXT, path TEXT, asset_count INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT, asset_kind TEXT)")
    conn.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER)")
    conn.execute("INSERT INTO packs (name, path) VALUES ('Old', 'Old')")
    conn.commit()
    conn.close()

    import api
    api.set_db_path(db_path)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    assert resp.json()["packs"][0]["theme"] == "Other"


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


def test_spa_serves_public_file_at_base_prefixed_url(test_db, tmp_path):
    """A file at dist/foo.js (e.g. from public/) must be reachable at /assets/foo.js."""
    from api import set_db_path, set_static_path

    set_db_path(test_db)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<!DOCTYPE html><html></html>")
    (dist_dir / "model-viewer.min.js").write_text("// model-viewer code")
    set_static_path(dist_dir)

    r = client.get("/assets/model-viewer.min.js")
    assert r.status_code == 200
    assert "model-viewer code" in r.text


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


def test_download_cart_includes_metadata_txt(test_client, sample_db):
    """Test download cart includes metadata.txt with asset info."""
    import zipfile
    import io

    # Fixture already has: asset 1 with tags 'creature', 'goblin' and color '#00ff00'
    response = test_client.post("/api/download-cart", json={"asset_ids": [1]})
    assert response.status_code == 200

    # Extract ZIP and check for metadata.txt
    zip_buffer = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        assert "metadata.txt" in zf.namelist()
        metadata = zf.read("metadata.txt").decode("utf-8")

        # Check that asset info is included
        assert "goblin.png" in metadata
        assert "creature" in metadata
        assert "goblin" in metadata
        assert "#00ff00" in metadata
        assert "64x64" in metadata or "64 x 64" in metadata


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


def test_filters_returns_pack_counts(test_client, sample_db):
    """Test filters endpoint returns pack counts."""
    # Update pack asset_count to reflect actual counts
    import sqlite3
    conn = sqlite3.connect(sample_db)
    conn.execute("UPDATE packs SET asset_count = 2 WHERE name = 'creatures'")
    conn.commit()
    conn.close()

    response = test_client.get("/api/filters")
    assert response.status_code == 200
    data = response.json()
    assert "packs" in data
    assert len(data["packs"]) > 0
    assert "name" in data["packs"][0]
    assert "count" in data["packs"][0]


def test_empty_search_returns_random_order(test_db):
    """Empty search (no filters) returns randomly ordered results."""
    from api import set_db_path
    set_db_path(test_db)

    # Add more assets to make randomness detectable
    import sqlite3
    conn = sqlite3.connect(test_db)
    for i in range(3, 20):
        conn.execute(
            "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
            f"VALUES ({i}, 1, '/assets/creatures/asset{i}.png', 'asset{i}.png', 'png', 'hash{i}', 64, 64)"
        )
    conn.commit()
    conn.close()

    # Make multiple requests and check if order varies
    orders = []
    for _ in range(5):
        response = client.get("/api/search")
        assert response.status_code == 200
        data = response.json()
        order = [a["id"] for a in data["assets"]]
        orders.append(tuple(order))

    # At least one pair should have different order (random)
    unique_orders = set(orders)
    assert len(unique_orders) > 1, "Empty search should return randomly ordered results"


def test_filtered_search_returns_deterministic_order(test_db):
    """Search with filters returns deterministic (path-based) order."""
    from api import set_db_path
    set_db_path(test_db)

    # Add more assets to make ordering detectable
    import sqlite3
    conn = sqlite3.connect(test_db)
    for i in range(3, 10):
        conn.execute(
            "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
            f"VALUES ({i}, 1, '/assets/creatures/asset{i:02d}.png', 'asset{i:02d}.png', 'png', 'hash{i}', 64, 64)"
        )
    conn.commit()
    conn.close()

    # Make multiple requests with a filter - should always get same order
    orders = []
    for _ in range(3):
        response = client.get("/api/search?pack=creatures")
        assert response.status_code == 200
        data = response.json()
        order = [a["id"] for a in data["assets"]]
        orders.append(tuple(order))

    # All orders should be the same (deterministic)
    unique_orders = set(orders)
    assert len(unique_orders) == 1, "Filtered search should return deterministic order"


def test_preview_override_table_exists(test_db):
    """Preview override table should exist in database."""
    import sqlite3
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_preview_overrides'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_set_preview_override(test_db):
    """POST /api/asset/{id}/preview-override sets the override."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.post("/api/asset/1/preview-override", json={"use_full_image": True})
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify it was saved
    import sqlite3
    conn = sqlite3.connect(test_db)
    row = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = '/assets/creatures/goblin.png'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1  # SQLite stores True as 1


def test_set_preview_override_not_found(test_db):
    """POST /api/asset/{id}/preview-override returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.post("/api/asset/999/preview-override", json={"use_full_image": True})
    assert response.status_code == 404


def test_delete_preview_override(test_db):
    """DELETE /api/asset/{id}/preview-override removes the override."""
    from api import set_db_path
    set_db_path(test_db)

    # First set an override
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    # Then delete it
    response = client.delete("/api/asset/1/preview-override")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify it was removed
    import sqlite3
    conn = sqlite3.connect(test_db)
    row = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = '/assets/creatures/goblin.png'"
    ).fetchone()
    conn.close()
    assert row is None


def test_asset_detail_includes_use_full_image(test_db):
    """GET /api/asset/{id} includes use_full_image field."""
    from api import set_db_path
    set_db_path(test_db)

    # Without override, should be null/None
    response = client.get("/api/asset/1")
    assert response.status_code == 200
    data = response.json()
    assert "use_full_image" in data
    assert data["use_full_image"] is None

    # Set override
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    # Now should be True
    response = client.get("/api/asset/1")
    data = response.json()
    assert data["use_full_image"] is True


def test_search_includes_use_full_image(test_db):
    """GET /api/search includes use_full_image field per asset."""
    from api import set_db_path
    set_db_path(test_db)

    # Set override for one asset
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    response = client.get("/api/search")
    assert response.status_code == 200
    data = response.json()

    # Find goblin (id=1) and orc (id=2)
    assets_by_id = {a["id"]: a for a in data["assets"]}

    # Asset 1 should have use_full_image=True
    assert assets_by_id[1]["use_full_image"] is True
    # Asset 2 should have use_full_image=None
    assert assets_by_id[2]["use_full_image"] is None


def test_preview_override_full_workflow(test_db):
    """Test complete preview override workflow."""
    from api import set_db_path
    set_db_path(test_db)

    # 1. Initially, asset has no override
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is None

    # 2. Set override to True
    response = client.post("/api/asset/1/preview-override", json={"use_full_image": True})
    assert response.status_code == 200

    # 3. Verify in detail
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is True

    # 4. Verify in search
    response = client.get("/api/search?q=goblin")
    assert response.json()["assets"][0]["use_full_image"] is True

    # 5. Delete override
    response = client.delete("/api/asset/1/preview-override")
    assert response.status_code == 200

    # 6. Verify removed
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is None


class Test3DSerialization:
    def test_search_returns_asset_kind(self, test_db):
        from api import set_db_path
        set_db_path(test_db)
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash, asset_kind, rig, thumbnail_path) "
            "VALUES ('Knight.glb', 'Knight.glb', 'glb', 'h1', 'model', 'Rig_Medium', 'Samples/knight.png')"
        )
        conn.commit(); conn.close()
        r = _client.get("/api/search")
        assert r.status_code == 200
        knight = next(a for a in r.json()["assets"] if a["filename"] == "Knight.glb")
        assert knight["kind"] == "model"
        assert knight["rig"] == "Rig_Medium"
        assert knight["thumbnail_path"] == "Samples/knight.png"

    def test_asset_detail_returns_asset_kind(self, test_db):
        from api import set_db_path
        set_db_path(test_db)
        conn = sqlite3.connect(test_db)
        cur = conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash, asset_kind, rig) "
            "VALUES ('M.glb', 'M.glb', 'glb', 'h2', 'model', 'Rig_Large')"
        )
        aid = cur.lastrowid; conn.commit(); conn.close()
        r = _client.get(f"/api/asset/{aid}")
        body = r.json()
        assert body["kind"] == "model"
        assert body["rig"] == "Rig_Large"

    def test_search_kind_filter(self, test_db):
        from api import set_db_path
        set_db_path(test_db)
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO assets (path, filename, filetype, file_hash, asset_kind) VALUES ('a.png','a.png','png','h3','image')")
        conn.execute("INSERT INTO assets (path, filename, filetype, file_hash, asset_kind) VALUES ('b.glb','b.glb','glb','h4','model')")
        conn.commit(); conn.close()
        r = _client.get("/api/search?kind=model")
        kinds = {a["filename"]: a["kind"] for a in r.json()["assets"]}
        assert "b.glb" in kinds and "a.png" not in kinds


class TestModelEndpoint:
    def test_serves_glb(self, test_db, tmp_path):
        from api import set_db_path, set_assets_path
        set_db_path(test_db)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        src = Path(__file__).parent.parent / "tests" / "fixtures" / "3d" / "Knight.glb"
        (assets_dir / "Knight.glb").write_bytes(src.read_bytes())
        set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('Knight.glb','Knight.glb','glb','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/asset/{aid}/model")
        assert r.status_code == 200
        assert r.headers["content-type"] == "model/gltf-binary"
        assert r.content[:4] == b"glTF"

    def test_serves_gltf_and_sibling_bin(self, test_db, tmp_path):
        from api import set_db_path, set_assets_path
        set_db_path(test_db)
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        fx = Path(__file__).parent.parent / "tests" / "fixtures" / "3d"
        (assets_dir / "axe_1handed.gltf").write_bytes((fx / "axe_1handed.gltf").read_bytes())
        (assets_dir / "axe_1handed.bin").write_bytes((fx / "axe_1handed.bin").read_bytes())
        set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('axe_1handed.gltf','axe_1handed.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/asset/{aid}/model")
        assert r.status_code == 200
        assert r.headers["content-type"] == "model/gltf+json"
        r2 = _client.get(f"/api/asset/{aid}/model/axe_1handed.bin")
        assert r2.status_code == 200

    def test_sibling_endpoint_serves_gltf_with_correct_content_type(self, test_db, tmp_path):
        """The sibling endpoint serves the asset's own .gltf with model/gltf+json type
        — this URL form (with the filename) is what the frontend uses so that the
        browser resolves relative buffer URIs against /api/asset/{id}/model/."""
        from api import set_db_path, set_assets_path
        set_db_path(test_db)
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        fx = Path(__file__).parent.parent / "tests" / "fixtures" / "3d"
        (assets_dir / "axe_1handed.gltf").write_bytes((fx / "axe_1handed.gltf").read_bytes())
        set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('axe_1handed.gltf','axe_1handed.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()
        r = _client.get(f"/api/asset/{aid}/model/axe_1handed.gltf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "model/gltf+json"

    def test_rejects_path_traversal(self, test_db, tmp_path):
        from api import set_db_path, set_assets_path
        set_db_path(test_db)
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        (assets_dir / "a.gltf").write_text("{}")
        set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('a.gltf','a.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()
        r = _client.get(f"/api/asset/{aid}/model/../../../etc/passwd")
        assert r.status_code in (400, 404)


class TestAnimationsEndpoint:
    def _setup(self, test_db):
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,rig) VALUES ('Knight.glb','Knight.glb','glb','h1','model','Rig_Medium')")
        char_id = cur.lastrowid
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,rig) VALUES ('Rig_Medium_General.glb','Rig_Medium_General.glb','glb','h2','animation_bundle','Rig_Medium')")
        bundle_id = cur.lastrowid
        conn.execute("INSERT INTO asset_animations (asset_id, clip_index, name) VALUES (?,0,'Idle')", [bundle_id])
        conn.execute("INSERT INTO asset_animations (asset_id, clip_index, name) VALUES (?,1,'Walk')", [bundle_id])
        conn.execute("INSERT INTO asset_relations (asset_id,related_id,relation_type) VALUES (?,?,'animation_for_rig')", [char_id, bundle_id])
        conn.commit(); conn.close()
        return char_id, bundle_id

    def test_returns_clips_from_linked_bundles(self, test_db):
        from api import set_db_path
        set_db_path(test_db)
        char_id, bundle_id = self._setup(test_db)
        r = _client.get(f"/api/asset/{char_id}/animations")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["bundle_id"] == bundle_id
        assert body[0]["bundle_name"] == "Rig_Medium_General.glb"
        clip_names = [c["name"] for c in body[0]["clips"]]
        assert clip_names == ["Idle", "Walk"]


class TestCart3D:
    def test_cart_zip_includes_gltf_bin(self, test_client, sample_db, tmp_path):
        from pathlib import Path
        fx = Path(__file__).parent.parent / "tests" / "fixtures" / "3d"
        assets_dir = tmp_path / "assets3d"; assets_dir.mkdir()
        (assets_dir / "axe_1handed.gltf").write_bytes((fx / "axe_1handed.gltf").read_bytes())
        (assets_dir / "axe_1handed.bin").write_bytes((fx / "axe_1handed.bin").read_bytes())
        import api
        api.set_assets_path(assets_dir)

        conn = sqlite3.connect(sample_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('axe_1handed.gltf','axe_1handed.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = test_client.post("/api/download-cart", json={"asset_ids": [aid]})
        assert r.status_code == 200
        import zipfile, io
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            assert "axe_1handed.gltf" in names
            assert "axe_1handed.bin" in names


class TestImageEndpointFor3D:
    def test_serves_thumbnail_png_for_model(self, test_db, tmp_path):
        from pathlib import Path
        import api
        api.set_db_path(test_db)
        assets_dir = tmp_path / "assets"
        samples_dir = assets_dir / "pack" / "Samples"
        samples_dir.mkdir(parents=True)
        sample_png = samples_dir / "knight.png"
        sample_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        api.set_assets_path(assets_dir)

        # thumbnail_path stored relative to assets_dir.parent (db_dir)
        thumb_rel = str(sample_png.relative_to(tmp_path))

        conn = sqlite3.connect(test_db)
        cur = conn.execute(
            "INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,thumbnail_path) "
            "VALUES ('pack/Knight.glb','Knight.glb','glb','h','model',?)",
            [thumb_rel]
        )
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/image/{aid}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content.startswith(b"\x89PNG")

    def test_returns_404_when_3d_has_no_thumbnail(self, test_db, tmp_path):
        import api
        api.set_db_path(test_db)
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        api.set_assets_path(assets_dir)

        conn = sqlite3.connect(test_db)
        cur = conn.execute(
            "INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,thumbnail_path) "
            "VALUES ('Mage.glb','Mage.glb','glb','h2','model', NULL)"
        )
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/image/{aid}")
        assert r.status_code == 404

    def test_2d_image_unchanged(self, test_db, tmp_path):
        import api
        from PIL import Image
        api.set_db_path(test_db)
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        png = assets_dir / "sprite.png"
        Image.new("RGBA", (16, 16), (255, 0, 0)).save(png)
        api.set_assets_path(assets_dir)

        conn = sqlite3.connect(test_db)
        cur = conn.execute(
            "INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) "
            "VALUES ('sprite.png','sprite.png','png','h3','image')"
        )
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/image/{aid}")
        assert r.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
