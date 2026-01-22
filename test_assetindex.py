#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
#     "imagehash>=4.3",
#     "rich>=13.0",
#     "typer>=0.9",
#     "python-dotenv>=1.0",
# ]
# ///
"""Test suite for asset index system."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Import modules under test
import assetindex
import assetsearch


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary database."""
    db_path = temp_dir / "test.db"
    conn = assetindex.get_db(db_path)
    conn.close()
    return db_path


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample PNG image."""
    img_path = temp_dir / "test_sprite.png"
    # Create a simple 64x32 image (2 frames of 32x32)
    img = Image.new("RGBA", (64, 32), (100, 150, 50, 255))
    # Add some variation
    for x in range(32):
        for y in range(32):
            img.putpixel((x, y), (100, 150, 50, 255))  # Green-ish
    for x in range(32, 64):
        for y in range(32):
            img.putpixel((x, y), (50, 50, 150, 255))  # Blue-ish
    img.save(img_path)
    return img_path


@pytest.fixture
def sample_asset_pack(temp_dir):
    """Create a sample asset pack structure."""
    pack_dir = temp_dir / "TestPack_v1.0"
    pack_dir.mkdir()

    # Create asset structure
    creatures_dir = pack_dir / "Creatures" / "Goblin"
    creatures_dir.mkdir(parents=True)

    shadows_dir = creatures_dir / "_Shadows"
    shadows_dir.mkdir()

    gifs_dir = creatures_dir / "_GIFs"
    gifs_dir.mkdir()

    # Create main sprite
    main_sprite = creatures_dir / "GoblinIdle.png"
    img = Image.new("RGBA", (128, 32), (50, 120, 50, 255))
    img.save(main_sprite)

    # Create shadow
    shadow_sprite = shadows_dir / "GoblinIdle.png"
    shadow_img = Image.new("RGBA", (128, 32), (0, 0, 0, 128))
    shadow_img.save(shadow_sprite)

    # Create GIF preview
    gif_preview = gifs_dir / "GoblinIdle.gif"
    gif_img = Image.new("RGBA", (32, 32), (50, 120, 50, 255))
    gif_img.save(gif_preview)

    # Create animation info
    anim_info = creatures_dir / "_AnimationInfo.txt"
    anim_info.write_text("""*Frame size*
- 32x32px: For all the animations.

*Frame Duration*
- 100ms: Attack, Die and Dmg.
- 200ms: Idle and Walk.
""")

    # Create another sprite for testing
    attack_sprite = creatures_dir / "GoblinAttack.png"
    attack_img = Image.new("RGBA", (192, 32), (80, 100, 50, 255))
    attack_img.save(attack_sprite)

    return temp_dir


# =============================================================================
# Unit Tests: assetindex.py
# =============================================================================


class TestFileHash:
    """Tests for file_hash function."""

    def test_hash_produces_hex_string(self, sample_image):
        result = assetindex.file_hash(sample_image)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex length

    def test_same_file_same_hash(self, sample_image):
        hash1 = assetindex.file_hash(sample_image)
        hash2 = assetindex.file_hash(sample_image)
        assert hash1 == hash2

    def test_different_files_different_hash(self, temp_dir):
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        assert assetindex.file_hash(file1) != assetindex.file_hash(file2)


class TestExtractVersion:
    """Tests for extract_version function."""

    def test_extracts_simple_version(self):
        assert assetindex.extract_version("Pack_v1.0") == "1.0"

    def test_extracts_complex_version(self):
        assert assetindex.extract_version("Minifantasy_Creatures_v3.3_Commercial") == "3.3"

    def test_returns_none_for_no_version(self):
        assert assetindex.extract_version("PackWithoutVersion") is None

    def test_case_insensitive(self):
        assert assetindex.extract_version("Pack_V2.5") == "2.5"


class TestGetImageInfo:
    """Tests for get_image_info function."""

    def test_extracts_dimensions(self, sample_image):
        info = assetindex.get_image_info(sample_image)
        assert info["width"] == 64
        assert info["height"] == 32

    def test_handles_invalid_file(self, temp_dir):
        bad_file = temp_dir / "not_an_image.txt"
        bad_file.write_text("not an image")
        info = assetindex.get_image_info(bad_file)
        assert info == {}


class TestExtractTagsFromPath:
    """Tests for extract_tags_from_path function."""

    def test_extracts_path_components(self, temp_dir):
        asset_path = temp_dir / "Pack" / "Creatures" / "Goblin" / "GoblinIdle.png"
        asset_path.parent.mkdir(parents=True)
        asset_path.touch()

        tags = assetindex.extract_tags_from_path(asset_path, temp_dir)

        assert "pack" in tags
        assert "creatures" in tags
        assert "goblin" in tags
        assert "idle" in tags

    def test_filters_noise_words(self, temp_dir):
        asset_path = temp_dir / "Pack_Assets" / "Commercial_Version" / "sprite.png"
        asset_path.parent.mkdir(parents=True)
        asset_path.touch()

        tags = assetindex.extract_tags_from_path(asset_path, temp_dir)

        assert "assets" not in tags
        assert "commercial" not in tags
        assert "version" not in tags

    def test_applies_aliases(self, temp_dir):
        asset_path = temp_dir / "Char_Dmg.png"  # Use underscore separator
        asset_path.touch()

        tags = assetindex.extract_tags_from_path(asset_path, temp_dir)

        # "dmg" should be aliased to "damage"
        assert "damage" in tags
        assert "character" in tags  # "char" aliased to "character"


class TestExtractColors:
    """Tests for extract_colors function."""

    def test_extracts_dominant_color(self, temp_dir):
        # Create solid color image
        img_path = temp_dir / "solid.png"
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        img.save(img_path)

        colors = assetindex.extract_colors(img_path)

        assert len(colors) >= 1
        assert colors[0][0] == "#ff0000"
        assert colors[0][1] > 0.9  # Should be nearly 100%

    def test_handles_invalid_file(self, temp_dir):
        bad_file = temp_dir / "not_an_image.txt"
        bad_file.write_text("not an image")

        colors = assetindex.extract_colors(bad_file)
        assert colors == []


class TestDetectFirstSpriteBounds:
    """Tests for detect_first_sprite_bounds function."""

    def test_detects_first_frame_in_grid_spritesheet(self, temp_dir):
        """Detects first frame in a grid-based spritesheet with transparent gaps."""
        img_path = temp_dir / "grid.png"
        # Create 65x33 image: 2x2 grid of 32x16 frames with 1px transparent gap between
        # Frame layout: [32px frame][1px gap][32px frame] x [16px frame][1px gap][16px frame]
        img = Image.new("RGBA", (65, 33), (0, 0, 0, 0))

        # Fill first frame cell (0-31, 0-15) with red sprite at (2,2) to (29,13)
        for x in range(2, 30):
            for y in range(2, 14):
                img.putpixel((x, y), (255, 0, 0, 255))

        # Column 32 is transparent gap (already transparent)

        # Fill second frame cell (33-64, 0-15) with blue sprite
        for x in range(35, 60):
            for y in range(2, 14):
                img.putpixel((x, y), (0, 0, 255, 255))

        # Row 16 is transparent gap (already transparent)

        # Fill third frame cell (0-31, 17-32) with green sprite
        for x in range(2, 30):
            for y in range(19, 31):
                img.putpixel((x, y), (0, 255, 0, 255))

        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        # Should return bounds of content in FIRST frame cell only: (2, 2, 28, 12)
        assert bounds == (2, 2, 28, 12)

    def test_finds_first_sprite_in_horizontal_strip(self, temp_dir):
        """Detects first sprite in a horizontal spritesheet."""
        img_path = temp_dir / "strip.png"
        img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        for x in range(32):
            for y in range(32):
                img.putpixel((x, y), (255, 0, 0, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds == (0, 0, 32, 32)

    def test_finds_sprite_with_internal_transparency(self, temp_dir):
        """Detects sprite that has transparent pixels inside (like a donut)."""
        img_path = temp_dir / "donut.png"
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        for x in range(32):
            for y in range(32):
                dist_from_center = ((x - 16) ** 2 + (y - 16) ** 2) ** 0.5
                if 8 <= dist_from_center <= 14:
                    img.putpixel((x, y), (0, 255, 0, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds is not None
        x, y, w, h = bounds
        assert w >= 28 and h >= 28

    def test_returns_none_for_fully_transparent(self, temp_dir):
        """Returns None for fully transparent image."""
        img_path = temp_dir / "transparent.png"
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds is None

    def test_returns_none_for_no_alpha_channel(self, temp_dir):
        """Returns None for images without alpha channel."""
        img_path = temp_dir / "rgb.png"
        img = Image.new("RGB", (32, 32), (255, 0, 0))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds is None

    def test_handles_sprite_not_at_origin(self, temp_dir):
        """Finds sprite that doesn't start at (0,0)."""
        img_path = temp_dir / "offset.png"
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        for x in range(16, 36):
            for y in range(16, 36):
                img.putpixel((x, y), (0, 0, 255, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds == (16, 16, 20, 20)

    def test_fallback_for_image_without_gaps(self, temp_dir):
        """Falls back to full content bounds when no transparent gaps exist."""
        img_path = temp_dir / "no_gaps.png"
        # Create image where all columns/rows have some content (no full gaps)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        # Draw diagonal line so no column or row is fully transparent
        for i in range(64):
            img.putpixel((i, i), (255, 0, 0, 255))
        # Add a blob
        for x in range(10, 30):
            for y in range(10, 30):
                img.putpixel((x, y), (0, 255, 0, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        # Should return bounding box of all content (the diagonal + blob)
        assert bounds == (0, 0, 64, 64)


class TestComputePhash:
    """Tests for compute_phash function."""

    def test_returns_bytes(self, sample_image):
        phash = assetindex.compute_phash(sample_image)
        assert isinstance(phash, bytes)

    def test_similar_images_similar_hash(self, temp_dir):
        # Create two similar images
        img1_path = temp_dir / "img1.png"
        img2_path = temp_dir / "img2.png"

        img1 = Image.new("RGB", (64, 64), (100, 100, 100))
        img2 = Image.new("RGB", (64, 64), (100, 100, 105))  # Slightly different

        img1.save(img1_path)
        img2.save(img2_path)

        hash1 = assetindex.compute_phash(img1_path)
        hash2 = assetindex.compute_phash(img2_path)

        distance = assetsearch.hamming_distance(hash1, hash2)
        assert distance < 5  # Very similar

    def test_handles_invalid_file(self, temp_dir):
        bad_file = temp_dir / "not_an_image.txt"
        bad_file.write_text("not an image")

        phash = assetindex.compute_phash(bad_file)
        assert phash is None


class TestDetectPack:
    """Tests for detect_pack function."""

    def test_detects_pack_from_path(self, temp_dir):
        pack_dir = temp_dir / "MyPack_v1.0" / "Assets"
        pack_dir.mkdir(parents=True)
        asset = pack_dir / "sprite.png"
        asset.touch()

        name, path = assetindex.detect_pack(asset, temp_dir)
        assert name == "MyPack_v1.0"
        assert path == temp_dir / "MyPack_v1.0"


class TestScanAssets:
    """Tests for scan_assets function."""

    def test_scans_image_and_aseprite_files(self, temp_dir):
        """scan_assets should return both image and aseprite files."""
        pack_dir = temp_dir / "TestPack"
        pack_dir.mkdir()

        # Create various files
        (pack_dir / "sprite.png").touch()
        (pack_dir / "animation.gif").touch()
        (pack_dir / "source.aseprite").touch()
        (pack_dir / "source2.ase").touch()
        (pack_dir / "readme.txt").touch()

        files = assetindex.scan_assets(temp_dir)
        filenames = {f.name for f in files}

        assert "sprite.png" in filenames
        assert "animation.gif" in filenames
        assert "source.aseprite" in filenames
        assert "source2.ase" in filenames
        assert "readme.txt" not in filenames


# =============================================================================
# Unit Tests: assetsearch.py
# =============================================================================


class TestHammingDistance:
    """Tests for hamming_distance function."""

    def test_identical_hashes(self):
        h = b"\x00\x00\x00\x00"
        assert assetsearch.hamming_distance(h, h) == 0

    def test_one_bit_difference(self):
        h1 = b"\x00"
        h2 = b"\x01"
        assert assetsearch.hamming_distance(h1, h2) == 1

    def test_all_bits_different(self):
        h1 = b"\x00"
        h2 = b"\xff"
        assert assetsearch.hamming_distance(h1, h2) == 8


class TestHexToRgb:
    """Tests for hex_to_rgb function."""

    def test_parses_with_hash(self):
        result = assetsearch.hex_to_rgb("#ff0000")
        assert result == (255, 0, 0)

    def test_parses_without_hash(self):
        result = assetsearch.hex_to_rgb("00ff00")
        assert result == (0, 255, 0)

    def test_mixed_case(self):
        result = assetsearch.hex_to_rgb("#FfAa00")
        assert result == (255, 170, 0)


class TestColorDistance:
    """Tests for color_distance function."""

    def test_same_color_zero_distance(self):
        assert assetsearch.color_distance("#ff0000", "#ff0000") == 0

    def test_different_colors_positive_distance(self):
        dist = assetsearch.color_distance("#ff0000", "#00ff00")
        assert dist > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestIndexingIntegration:
    """Integration tests for the indexing workflow."""

    def test_full_indexing_workflow(self, sample_asset_pack, temp_dir):
        """Test complete indexing of a sample pack."""
        db_path = temp_dir / "test.db"

        # Index the pack
        conn = assetindex.get_db(db_path)

        # Scan assets
        files = assetindex.scan_assets(sample_asset_pack)
        assert len(files) >= 3  # At least main, shadow, and gif

        # Index manually (simplified)
        for file_path in files:
            if file_path.suffix.lower() not in assetindex.IMAGE_EXTENSIONS:
                continue

            rel_path = str(file_path.relative_to(sample_asset_pack))
            pack_name, pack_path = assetindex.detect_pack(file_path, sample_asset_pack)

            # Insert pack
            if pack_name:
                conn.execute(
                    "INSERT OR IGNORE INTO packs (name, path) VALUES (?, ?)",
                    [pack_name, str(pack_path.relative_to(sample_asset_pack))]
                )

            # Get image info
            img_info = assetindex.get_image_info(file_path)

            # Insert asset
            conn.execute(
                """INSERT OR REPLACE INTO assets
                   (path, filename, filetype, file_hash, file_size, width, height)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    rel_path,
                    file_path.name,
                    file_path.suffix.lower().lstrip("."),
                    assetindex.file_hash(file_path),
                    file_path.stat().st_size,
                    img_info.get("width"),
                    img_info.get("height"),
                ]
            )

        conn.commit()

        # Verify
        pack_count = conn.execute("SELECT COUNT(*) FROM packs").fetchone()[0]
        asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]

        assert pack_count >= 1
        assert asset_count >= 3

        conn.close()

    def test_incremental_update(self, sample_asset_pack, temp_dir):
        """Test that unchanged files are skipped on re-index."""
        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)

        # First index
        files = assetindex.scan_assets(sample_asset_pack)
        first_count = len([f for f in files if f.suffix.lower() in assetindex.IMAGE_EXTENSIONS])

        # Insert with hashes
        existing_hashes = {}
        for file_path in files:
            if file_path.suffix.lower() not in assetindex.IMAGE_EXTENSIONS:
                continue
            rel_path = str(file_path.relative_to(sample_asset_pack))
            file_hash = assetindex.file_hash(file_path)
            existing_hashes[rel_path] = file_hash

            conn.execute(
                "INSERT OR REPLACE INTO assets (path, filename, filetype, file_hash) VALUES (?, ?, ?, ?)",
                [rel_path, file_path.name, file_path.suffix.lower().lstrip("."), file_hash]
            )
        conn.commit()

        # Simulate second index - count skipped
        skipped = 0
        for file_path in files:
            if file_path.suffix.lower() not in assetindex.IMAGE_EXTENSIONS:
                continue
            rel_path = str(file_path.relative_to(sample_asset_pack))
            current_hash = assetindex.file_hash(file_path)
            if rel_path in existing_hashes and existing_hashes[rel_path] == current_hash:
                skipped += 1

        assert skipped == first_count  # All should be skipped

        conn.close()


class TestSearchIntegration:
    """Integration tests for search functionality."""

    def test_search_by_filename(self, temp_dir):
        """Test searching by filename."""
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)

        # Insert test data
        conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash) VALUES (?, ?, ?, ?)",
            ["pack/GoblinIdle.png", "GoblinIdle.png", "png", "abc123"]
        )
        conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash) VALUES (?, ?, ?, ?)",
            ["pack/SkeletonIdle.png", "SkeletonIdle.png", "png", "def456"]
        )
        conn.commit()

        # Search
        rows = conn.execute(
            "SELECT * FROM assets WHERE filename LIKE ?",
            ["%Goblin%"]
        ).fetchall()

        assert len(rows) == 1
        assert rows[0]["filename"] == "GoblinIdle.png"

        conn.close()

    def test_search_by_tag(self, temp_dir):
        """Test searching by tag."""
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)

        # Insert test data
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [1, "pack/GoblinIdle.png", "GoblinIdle.png", "png", "abc123"]
        )
        conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", [1, "goblin"])
        conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", [2, "idle"])
        conn.execute("INSERT INTO asset_tags (asset_id, tag_id, source) VALUES (?, ?, ?)", [1, 1, "path"])
        conn.execute("INSERT INTO asset_tags (asset_id, tag_id, source) VALUES (?, ?, ?)", [1, 2, "path"])
        conn.commit()

        # Search by tag
        rows = conn.execute("""
            SELECT a.* FROM assets a
            JOIN asset_tags at ON a.id = at.asset_id
            JOIN tags t ON at.tag_id = t.id
            WHERE t.name = ?
        """, ["goblin"]).fetchall()

        assert len(rows) == 1
        assert rows[0]["filename"] == "GoblinIdle.png"

        conn.close()

    def test_search_by_color(self, temp_dir):
        """Test searching by color."""
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)

        # Insert test data
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [1, "pack/sprite.png", "sprite.png", "png", "abc123"]
        )
        conn.execute(
            "INSERT INTO asset_colors (asset_id, color_hex, percentage) VALUES (?, ?, ?)",
            [1, "#ff0000", 0.8]
        )
        conn.commit()

        # Search by color
        rows = conn.execute("""
            SELECT a.* FROM assets a
            JOIN asset_colors ac ON a.id = ac.asset_id
            WHERE ac.color_hex = ? AND ac.percentage >= 0.1
        """, ["#ff0000"]).fetchall()

        assert len(rows) == 1

        conn.close()


class TestRelationshipDetection:
    """Tests for asset relationship detection."""

    def test_detects_gif_preview(self, temp_dir):
        """Test GIF preview relationship detection."""
        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)

        # Insert test data - main sprite and GIF preview
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [1, "pack/Goblin/GoblinIdle.png", "GoblinIdle.png", "png", "abc"]
        )
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [2, "pack/Goblin/_GIFs/GoblinIdle.gif", "GoblinIdle.gif", "gif", "def"]
        )
        conn.commit()

        # Detect relationships
        assetindex.detect_relationships(conn)

        # Check
        rels = conn.execute(
            "SELECT * FROM asset_relations WHERE asset_id = 1 AND relation_type = 'gif_preview'"
        ).fetchall()

        assert len(rels) == 1
        assert rels[0]["related_id"] == 2

        conn.close()

    def test_detects_shadow(self, temp_dir):
        """Test shadow relationship detection."""
        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)

        # Insert test data - main sprite and shadow
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [1, "pack/Goblin/GoblinIdle.png", "GoblinIdle.png", "png", "abc"]
        )
        conn.execute(
            "INSERT INTO assets (id, path, filename, filetype, file_hash) VALUES (?, ?, ?, ?, ?)",
            [2, "pack/Goblin/_Shadows/GoblinIdle.png", "GoblinIdle.png", "png", "def"]
        )
        conn.commit()

        # Detect relationships
        assetindex.detect_relationships(conn)

        # Check
        rels = conn.execute(
            "SELECT * FROM asset_relations WHERE asset_id = 1 AND relation_type = 'shadow'"
        ).fetchall()

        assert len(rels) == 1
        assert rels[0]["related_id"] == 2

        conn.close()


# =============================================================================
# CLI Tests
# =============================================================================


class TestCLI:
    """Tests for CLI commands."""

    def test_assetsearch_help(self):
        """Test that help works."""
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(assetsearch.app, ["--help"])
        assert result.exit_code == 0
        assert "Search your game asset index" in result.stdout

    def test_assetsearch_stats_empty_db(self, temp_dir):
        """Test stats on empty database."""
        from typer.testing import CliRunner
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)
        conn.close()

        runner = CliRunner()
        result = runner.invoke(assetsearch.app, ["stats", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "packs\t0" in result.stdout

    def test_assetsearch_packs_empty(self, temp_dir):
        """Test packs command with empty database."""
        from typer.testing import CliRunner
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)
        conn.close()

        runner = CliRunner()
        result = runner.invoke(assetsearch.app, ["packs", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "No packs indexed" in result.output

    def test_assetsearch_tags_empty(self, temp_dir):
        """Test tags command with empty database."""
        from typer.testing import CliRunner
        db_path = temp_dir / "test.db"
        conn = assetsearch.get_db(db_path)
        conn.close()

        runner = CliRunner()
        result = runner.invoke(assetsearch.app, ["tags", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "No tags found" in result.output


# =============================================================================
# Sprite Frames Schema Tests
# =============================================================================


class TestIndexAssetPreviewBounds:
    """Tests for preview bounds storage during indexing."""

    def test_stores_preview_bounds_for_spritesheet(self, temp_dir):
        """Indexing stores preview bounds for image with alpha."""
        img_path = temp_dir / "TestPack" / "sprite.png"
        img_path.parent.mkdir(parents=True)
        # Create 64x32 spritesheet with first sprite at (0,0) size 32x32
        img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        for x in range(32):
            for y in range(32):
                img.putpixel((x, y), (255, 0, 0, 255))
        img.save(img_path)

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)
        assetindex.index_asset(conn, img_path, temp_dir)
        conn.commit()

        row = conn.execute(
            "SELECT preview_x, preview_y, preview_width, preview_height FROM assets WHERE filename = 'sprite.png'"
        ).fetchone()

        assert row["preview_x"] == 0
        assert row["preview_y"] == 0
        assert row["preview_width"] == 32
        assert row["preview_height"] == 32
        conn.close()

    def test_stores_null_for_no_alpha(self, temp_dir):
        """Indexing stores NULL preview bounds for RGB image."""
        img_path = temp_dir / "TestPack" / "solid.png"
        img_path.parent.mkdir(parents=True)
        img = Image.new("RGB", (64, 64), (255, 0, 0))
        img.save(img_path)

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)
        assetindex.index_asset(conn, img_path, temp_dir)
        conn.commit()

        row = conn.execute(
            "SELECT preview_x, preview_y, preview_width, preview_height FROM assets WHERE filename = 'solid.png'"
        ).fetchone()

        assert row["preview_x"] is None
        assert row["preview_y"] is None
        conn.close()


class TestAsepriteIndexing:
    """Tests for indexing Aseprite files."""

    def test_indexes_aseprite_dimensions(self, temp_dir):
        """Indexing stores width/height from Aseprite file."""
        from test_aseprite_parser import create_minimal_aseprite

        ase_path = temp_dir / "TestPack" / "sprite.aseprite"
        ase_path.parent.mkdir(parents=True)
        ase_path.write_bytes(create_minimal_aseprite(48, 32))

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)
        assetindex.index_asset(conn, ase_path, temp_dir)
        conn.commit()

        row = conn.execute(
            "SELECT width, height, filetype FROM assets WHERE filename = 'sprite.aseprite'"
        ).fetchone()

        assert row["width"] == 48
        assert row["height"] == 32
        assert row["filetype"] == "aseprite"
        conn.close()

    def test_indexes_aseprite_tags(self, temp_dir):
        """Indexing extracts animation tags from Aseprite file."""
        from test_aseprite_parser import create_minimal_aseprite

        ase_path = temp_dir / "TestPack" / "character.aseprite"
        ase_path.parent.mkdir(parents=True)
        ase_path.write_bytes(create_minimal_aseprite(
            32, 32,
            tags=[("idle", 0, 0), ("walk", 0, 0)]
        ))

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)
        assetindex.index_asset(conn, ase_path, temp_dir)
        conn.commit()

        # Check tags were added
        tags = conn.execute("""
            SELECT t.name FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            JOIN assets a ON a.id = at.asset_id
            WHERE a.filename = 'character.aseprite' AND at.source = 'aseprite'
        """).fetchall()
        tag_names = {row[0] for row in tags}

        assert "idle" in tag_names
        assert "walk" in tag_names
        conn.close()

    def test_indexes_ase_extension(self, temp_dir):
        """Indexing works with .ase extension too."""
        from test_aseprite_parser import create_minimal_aseprite

        ase_path = temp_dir / "TestPack" / "sprite.ase"
        ase_path.parent.mkdir(parents=True)
        ase_path.write_bytes(create_minimal_aseprite(16, 16))

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)
        assetindex.index_asset(conn, ase_path, temp_dir)
        conn.commit()

        row = conn.execute(
            "SELECT width, height, filetype FROM assets WHERE filename = 'sprite.ase'"
        ).fetchone()

        assert row["width"] == 16
        assert row["height"] == 16
        assert row["filetype"] == "ase"
        conn.close()


class TestPreviewBoundsSchema:
    """Tests for preview bounds columns in assets table."""

    def test_assets_table_has_preview_columns(self, temp_db):
        """Verify assets table has preview_x, preview_y, preview_width, preview_height."""
        conn = assetindex.get_db(temp_db)
        cursor = conn.execute("PRAGMA table_info(assets)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "preview_x" in columns
        assert "preview_y" in columns
        assert "preview_width" in columns
        assert "preview_height" in columns
        conn.close()

    def test_sprite_frames_table_removed(self, temp_db):
        """Verify sprite_frames table no longer exists."""
        conn = assetindex.get_db(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sprite_frames'"
        )
        assert cursor.fetchone() is None
        conn.close()


# =============================================================================
# Entry point
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
