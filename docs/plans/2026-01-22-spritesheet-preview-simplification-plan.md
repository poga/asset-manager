# Spritesheet Preview Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace heuristic-based frame detection with first-sprite bounding box detection, remove all animation features.

**Architecture:** Remove `sprite_frames` table and all animation endpoints. Add `preview_x/y/width/height` columns to assets table. Implement connected-component flood-fill to find first sprite bounding box during indexing.

**Tech Stack:** Python 3.11+, Pillow, SQLite, FastAPI, Vue 3

---

## Task 1: Add First Sprite Detection Function

**Files:**
- Create: `test_assetindex.py` (add tests)
- Modify: `assetindex.py`

**Step 1: Write the failing test for detect_first_sprite_bounds**

Add to `test_assetindex.py`:

```python
class TestDetectFirstSpriteBounds:
    """Tests for detect_first_sprite_bounds function."""

    def test_finds_first_sprite_in_horizontal_strip(self, temp_dir):
        """Detects first sprite in a horizontal spritesheet."""
        img_path = temp_dir / "strip.png"
        # Create 64x32 image with two 32x32 sprites separated by transparency
        img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        # First sprite at (0,0) - 32x32 red square
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
        # Draw a ring (outer pixels solid, center transparent)
        for x in range(32):
            for y in range(32):
                dist_from_center = ((x - 16) ** 2 + (y - 16) ** 2) ** 0.5
                if 8 <= dist_from_center <= 14:
                    img.putpixel((x, y), (0, 255, 0, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        # Should encompass the entire ring
        assert bounds is not None
        x, y, w, h = bounds
        assert w >= 28 and h >= 28  # Ring spans most of the image

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
        # Sprite at (16, 16) with size 20x20
        for x in range(16, 36):
            for y in range(16, 36):
                img.putpixel((x, y), (0, 0, 255, 255))
        img.save(img_path)

        bounds = assetindex.detect_first_sprite_bounds(img_path)
        assert bounds == (16, 16, 20, 20)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest test_assetindex.py::TestDetectFirstSpriteBounds -v`
Expected: FAIL with "AttributeError: module 'assetindex' has no attribute 'detect_first_sprite_bounds'"

**Step 3: Write minimal implementation**

Add to `assetindex.py` after the `compute_phash` function (around line 202):

```python
def detect_first_sprite_bounds(path: Path) -> Optional[tuple[int, int, int, int]]:
    """
    Find the bounding box of the first sprite in an image using flood-fill.

    Returns (x, y, width, height) or None if no sprite found or no alpha channel.
    """
    try:
        with Image.open(path) as img:
            # Must have alpha channel
            if img.mode != "RGBA":
                try:
                    img = img.convert("RGBA")
                except Exception:
                    return None

            width, height = img.size
            pixels = img.load()

            # Find first non-transparent pixel (scanning top-to-bottom, left-to-right)
            start_x, start_y = None, None
            for y in range(height):
                for x in range(width):
                    if pixels[x, y][3] > 0:  # Alpha > 0
                        start_x, start_y = x, y
                        break
                if start_x is not None:
                    break

            if start_x is None:
                return None  # Fully transparent

            # Flood-fill to find all connected non-transparent pixels (8-directional)
            visited = set()
            stack = [(start_x, start_y)]
            min_x, min_y = start_x, start_y
            max_x, max_y = start_x, start_y

            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                if cx < 0 or cx >= width or cy < 0 or cy >= height:
                    continue
                if pixels[cx, cy][3] == 0:  # Transparent
                    continue

                visited.add((cx, cy))
                min_x = min(min_x, cx)
                min_y = min(min_y, cy)
                max_x = max(max_x, cx)
                max_y = max(max_y, cy)

                # 8-directional neighbors
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        stack.append((cx + dx, cy + dy))

            return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
    except Exception:
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest test_assetindex.py::TestDetectFirstSpriteBounds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add test_assetindex.py assetindex.py
git commit -m "feat: add detect_first_sprite_bounds function

Implements connected-component flood-fill to find first sprite bounding box.
Returns (x, y, width, height) for preview cropping.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Update Database Schema

**Files:**
- Modify: `assetindex.py` (schema)
- Modify: `test_assetindex.py` (add schema tests)

**Step 1: Write failing test for new schema**

Add to `test_assetindex.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest test_assetindex.py::TestPreviewBoundsSchema -v`
Expected: FAIL (preview columns missing, sprite_frames still exists)

**Step 3: Update schema in assetindex.py**

Replace the SCHEMA constant (around line 56-142). Remove `sprite_frames` table and its index, add preview columns to assets:

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS packs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    version TEXT,
    preview_path TEXT,
    preview_generated BOOLEAN DEFAULT FALSE,
    asset_count INTEGER DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    pack_id INTEGER REFERENCES packs(id),
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
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset_relations (
    asset_id INTEGER REFERENCES assets(id),
    related_id INTEGER REFERENCES assets(id),
    relation_type TEXT,
    PRIMARY KEY (asset_id, related_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER REFERENCES assets(id),
    tag_id INTEGER REFERENCES tags(id),
    source TEXT,
    PRIMARY KEY (asset_id, tag_id)
);

CREATE TABLE IF NOT EXISTS asset_colors (
    asset_id INTEGER REFERENCES assets(id),
    color_hex TEXT,
    percentage REAL,
    PRIMARY KEY (asset_id, color_hex)
);

CREATE TABLE IF NOT EXISTS asset_phash (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    phash BLOB
);

CREATE TABLE IF NOT EXISTS asset_embeddings (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_assets_filename ON assets(filename);
CREATE INDEX IF NOT EXISTS idx_assets_filetype ON assets(filetype);
CREATE INDEX IF NOT EXISTS idx_assets_pack_id ON assets(pack_id);
CREATE INDEX IF NOT EXISTS idx_assets_file_hash ON assets(file_hash);
CREATE INDEX IF NOT EXISTS idx_asset_tags_asset_id ON asset_tags(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id ON asset_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_asset_colors_color ON asset_colors(color_hex);
"""
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest test_assetindex.py::TestPreviewBoundsSchema -v`
Expected: PASS

**Step 5: Commit**

```bash
git add assetindex.py test_assetindex.py
git commit -m "feat: update schema - add preview bounds, remove sprite_frames

- Add preview_x, preview_y, preview_width, preview_height to assets
- Remove sprite_frames table and index
- Remove frame_count, frame_width, frame_height columns

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Remove Frame Detection Functions

**Files:**
- Modify: `assetindex.py`
- Modify: `test_assetindex.py`

**Step 1: Remove old tests that reference removed functions**

Delete these test classes from `test_assetindex.py`:
- `TestParseAnimationInfo` (lines 270-290)
- `TestSpriteAnalysisIntegration` (lines 667-734)
- `TestSpriteFramesSchema` (lines 737-756)

Also update `TestGetImageInfo` to not test frame detection:

```python
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
```

**Step 2: Run tests to see current state**

Run: `uv run pytest test_assetindex.py -v`
Expected: Some failures due to missing functions

**Step 3: Remove functions from assetindex.py**

Delete these functions:
- `parse_animation_info` (lines 291-307)
- `detect_frames` (lines 310-362)
- `store_sprite_frames` (lines 420-438)

Simplify `get_image_info` to only return dimensions:

```python
def get_image_info(path: Path) -> dict:
    """Extract image dimensions."""
    try:
        with Image.open(path) as img:
            width, height = img.size
            return {"width": width, "height": height}
    except Exception:
        return {}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest test_assetindex.py -v`
Expected: PASS (after removing tests for deleted functions)

**Step 5: Commit**

```bash
git add assetindex.py test_assetindex.py
git commit -m "refactor: remove frame detection functions

- Remove parse_animation_info, detect_frames, store_sprite_frames
- Simplify get_image_info to only return dimensions
- Remove related tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Update index_asset to Store Preview Bounds

**Files:**
- Modify: `assetindex.py`
- Modify: `test_assetindex.py`

**Step 1: Write failing test**

Add to `test_assetindex.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest test_assetindex.py::TestIndexAssetPreviewBounds -v`
Expected: FAIL (preview bounds not being stored)

**Step 3: Update index_asset function**

Modify `index_asset` function (around line 441) to detect and store preview bounds:

```python
def index_asset(
    conn: sqlite3.Connection,
    file_path: Path,
    asset_root: Path,
) -> int:
    """Index a single asset file. Returns asset ID."""
    rel_path = str(file_path.relative_to(asset_root))
    current_hash = file_hash(file_path)

    # Detect pack
    pack_name, pack_path = detect_pack(file_path, asset_root)
    pack_id = None
    if pack_name:
        pack_rel = str(pack_path.relative_to(asset_root))
        version = extract_version(pack_name)
        conn.execute(
            """INSERT OR REPLACE INTO packs (name, path, version, indexed_at)
               VALUES (?, ?, ?, ?)""",
            [pack_name, pack_rel, version, datetime.now()]
        )
        pack_id = conn.execute("SELECT id FROM packs WHERE path = ?", [pack_rel]).fetchone()[0]

    # Get image info
    img_info = get_image_info(file_path) if file_path.suffix.lower() in IMAGE_EXTENSIONS else {}

    # Category
    category = get_category(file_path, pack_path) if pack_name else ""

    # Detect preview bounds
    preview_bounds = None
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        preview_bounds = detect_first_sprite_bounds(file_path)

    preview_x = preview_bounds[0] if preview_bounds else None
    preview_y = preview_bounds[1] if preview_bounds else None
    preview_width = preview_bounds[2] if preview_bounds else None
    preview_height = preview_bounds[3] if preview_bounds else None

    # Insert or update asset
    conn.execute(
        """INSERT OR REPLACE INTO assets
           (pack_id, path, filename, filetype, file_hash, file_size,
            width, height, preview_x, preview_y, preview_width, preview_height,
            category, indexed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            pack_id,
            rel_path,
            file_path.name,
            file_path.suffix.lower().lstrip("."),
            current_hash,
            file_path.stat().st_size,
            img_info.get("width"),
            img_info.get("height"),
            preview_x,
            preview_y,
            preview_width,
            preview_height,
            category,
            datetime.now(),
        ]
    )

    asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]

    # Extract and add tags
    tags = extract_tags_from_path(file_path, asset_root)
    add_tags(conn, asset_id, tags, "path")

    # Extract colors
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        colors = extract_colors(file_path)
        for hex_color, percentage in colors:
            conn.execute(
                """INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage)
                   VALUES (?, ?, ?)""",
                [asset_id, hex_color, percentage]
            )

        # Compute perceptual hash
        phash = compute_phash(file_path)
        if phash:
            conn.execute(
                """INSERT OR REPLACE INTO asset_phash (asset_id, phash)
                   VALUES (?, ?)""",
                [asset_id, phash]
            )

    return asset_id
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest test_assetindex.py::TestIndexAssetPreviewBounds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add assetindex.py test_assetindex.py
git commit -m "feat: store preview bounds during indexing

index_asset now calls detect_first_sprite_bounds and stores
preview_x, preview_y, preview_width, preview_height in assets table.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Update index Command

**Files:**
- Modify: `assetindex.py`

**Step 1: Update the index command loop**

The `index` command (around line 587) has duplicated indexing logic. Update it to also store preview bounds. Find the section that inserts assets (around line 658-679) and update it:

```python
            # Get image info
            img_info = get_image_info(file_path) if file_path.suffix.lower() in IMAGE_EXTENSIONS else {}

            # Category
            category = get_category(file_path, pack_path) if pack_name else ""

            # Detect preview bounds
            preview_bounds = None
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                preview_bounds = detect_first_sprite_bounds(file_path)

            preview_x = preview_bounds[0] if preview_bounds else None
            preview_y = preview_bounds[1] if preview_bounds else None
            preview_width = preview_bounds[2] if preview_bounds else None
            preview_height = preview_bounds[3] if preview_bounds else None

            # Insert or update asset
            conn.execute(
                """INSERT OR REPLACE INTO assets
                   (pack_id, path, filename, filetype, file_hash, file_size,
                    width, height, preview_x, preview_y, preview_width, preview_height,
                    category, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    pack_id,
                    rel_path,
                    file_path.name,
                    file_path.suffix.lower().lstrip("."),
                    current_hash,
                    file_path.stat().st_size,
                    img_info.get("width"),
                    img_info.get("height"),
                    preview_x,
                    preview_y,
                    preview_width,
                    preview_height,
                    category,
                    datetime.now(),
                ]
            )
            asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]

            # Extract and add tags
            tags = extract_tags_from_path(file_path, asset_root)
            add_tags(conn, asset_id, tags, "path")

            # Extract colors for images
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                colors = extract_colors(file_path)
                for hex_color, percentage in colors:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage)
                           VALUES (?, ?, ?)""",
                        [asset_id, hex_color, percentage]
                    )

                # Compute perceptual hash
                phash = compute_phash(file_path)
                if phash:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_phash (asset_id, phash)
                           VALUES (?, ?)""",
                        [asset_id, phash]
                    )
```

Also remove the animation info and frame detection code block (around lines 686-702).

**Step 2: Run full test suite**

Run: `uv run pytest test_assetindex.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add assetindex.py
git commit -m "refactor: update index command to store preview bounds

- Remove frame detection from index loop
- Add preview bounds detection and storage
- Remove animation info parsing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Update generate_pack_preview

**Files:**
- Modify: `assetindex.py`

**Step 1: Update the function to use preview bounds**

Replace `generate_pack_preview` function (around line 204):

```python
def generate_pack_preview(
    conn: sqlite3.Connection,
    pack_id: int,
    asset_root: Path,
    preview_dir: Path,
    grid_size: int = 4,
    thumb_size: int = 64,
) -> Optional[str]:
    """Generate a preview montage for a pack."""
    # Get representative assets (prefer idle animations)
    rows = conn.execute("""
        SELECT path, filename, preview_x, preview_y, preview_width, preview_height
        FROM assets
        WHERE pack_id = ?
        AND filetype = 'png'
        ORDER BY
            CASE WHEN filename LIKE '%Idle%' THEN 0 ELSE 1 END,
            category,
            filename
        LIMIT ?
    """, [pack_id, grid_size * grid_size]).fetchall()

    if len(rows) < 4:
        return None

    # Create montage
    preview_dir.mkdir(parents=True, exist_ok=True)
    pack_row = conn.execute("SELECT name FROM packs WHERE id = ?", [pack_id]).fetchone()
    preview_name = f"{pack_row['name']}.png"
    preview_path = preview_dir / preview_name

    try:
        montage = Image.new("RGBA", (grid_size * thumb_size, grid_size * thumb_size), (0, 0, 0, 0))

        for i, row in enumerate(rows):
            x = (i % grid_size) * thumb_size
            y = (i // grid_size) * thumb_size

            img_path = asset_root / row["path"]
            with Image.open(img_path) as img:
                # Use preview bounds if available
                if row["preview_x"] is not None:
                    img = img.crop((
                        row["preview_x"],
                        row["preview_y"],
                        row["preview_x"] + row["preview_width"],
                        row["preview_y"] + row["preview_height"]
                    ))

                img.thumbnail((thumb_size, thumb_size), Image.Resampling.NEAREST)
                # Center in cell
                offset_x = (thumb_size - img.width) // 2
                offset_y = (thumb_size - img.height) // 2
                montage.paste(img, (x + offset_x, y + offset_y))

        montage.save(preview_path)
        return str(preview_path.relative_to(preview_dir.parent))
    except Exception as e:
        console.print(f"[yellow]Preview generation failed: {e}[/yellow]")
        return None
```

**Step 2: Run tests**

Run: `uv run pytest test_assetindex.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add assetindex.py
git commit -m "refactor: use preview bounds in generate_pack_preview

Pack preview montage now uses stored preview bounds to crop sprites
instead of heuristic-based cropping.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Remove Animation Endpoints from API

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Remove animation-related tests**

Delete these tests from `web/test_api.py`:
- `test_asset_frames_returns_frame_data` (lines 281-304)
- `test_asset_frames_not_found` (lines 307-313)
- `test_asset_frames_empty_for_non_spritesheet` (lines 316-324)
- `test_search_includes_frames` (lines 327-350)
- `test_asset_frame_serves_cropped_image` (lines 353-396)
- `test_asset_frame_not_found` (lines 399-405)
- `test_asset_animation_generates_gif` (lines 408-444)

Also update `test_db` fixture to remove `sprite_frames` table.

**Step 2: Remove endpoints from api.py**

Delete these endpoints from `web/api.py`:
- `/api/asset/{asset_id}/frames` (lines 374-410)
- `/api/asset/{asset_id}/frame/{frame_index}` (lines 413-460)
- `/api/asset/{asset_id}/animation` (lines 463-545)

Remove the frame fetching from search endpoint (lines 184-204). The search function should be simplified to not include frames.

**Step 3: Run API tests**

Run: `cd web && uv run pytest test_api.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "refactor: remove animation endpoints from API

- Remove /api/asset/{id}/frames endpoint
- Remove /api/asset/{id}/frame/{index} endpoint
- Remove /api/asset/{id}/animation endpoint
- Remove frame data from search results

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Update Search API to Return Preview Bounds

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write failing test**

Add to `web/test_api.py`:

```python
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
```

Also update `test_db` fixture to include preview columns:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd web && uv run pytest test_api.py::test_search_includes_preview_bounds -v`
Expected: FAIL (preview bounds not in response)

**Step 3: Update search endpoint**

Modify the search function in `web/api.py` to include preview bounds:

```python
@app.get("/api/search")
def search(
    q: Optional[str] = None,
    tag: list[str] = Query(default=[]),
    color: Optional[str] = None,
    pack: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
):
    """Search assets by name, tags, or filters."""
    conn = get_db()

    conditions = []
    params = []

    if q:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if pack:
        conditions.append("p.name LIKE ?")
        params.append(f"%{pack}%")

    if type:
        conditions.append("a.filetype = ?")
        params.append(type.lower().lstrip("."))

    for t in tag:
        conditions.append("""
            a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
            )
        """)
        params.append(t.lower())

    if color:
        color_lower = color.lower()
        if color_lower in COLOR_NAMES:
            hex_values = COLOR_NAMES[color_lower]
            placeholders = ",".join("?" * len(hex_values))
            conditions.append(f"""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex IN ({placeholders})
                    AND percentage >= 0.1
                )
            """)
            params.extend(hex_values)
        else:
            conditions.append("""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex = ?
                    AND percentage >= 0.1
                )
            """)
            params.append(color if color.startswith("#") else f"#{color}")

    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.preview_x, a.preview_y, a.preview_width, a.preview_height,
               p.name as pack_name,
               GROUP_CONCAT(DISTINCT tg.name) as tags
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.filename
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    assets = []
    for row in rows:
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
            "preview_x": row["preview_x"],
            "preview_y": row["preview_y"],
            "preview_width": row["preview_width"],
            "preview_height": row["preview_height"],
        })

    return {"assets": assets, "total": len(assets)}
```

**Step 4: Run test to verify it passes**

Run: `cd web && uv run pytest test_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: include preview bounds in search API response

Search results now include preview_x, preview_y, preview_width,
preview_height for each asset.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Simplify SpritePreview.vue

**Files:**
- Modify: `web/frontend/src/components/SpritePreview.vue`
- Modify: `web/frontend/src/components/AssetGrid.vue`

**Step 1: Rewrite SpritePreview.vue for static preview**

Replace entire file:

```vue
<template>
  <canvas
    ref="canvas"
    :width="displaySize"
    :height="displaySize"
    class="sprite-canvas"
  />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  assetId: {
    type: Number,
    required: true
  },
  previewX: {
    type: Number,
    default: null
  },
  previewY: {
    type: Number,
    default: null
  },
  previewWidth: {
    type: Number,
    default: null
  },
  previewHeight: {
    type: Number,
    default: null
  },
  width: {
    type: Number,
    required: true
  },
  height: {
    type: Number,
    required: true
  }
})

const canvas = ref(null)
const displaySize = 100

const loadImage = () => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = `/api/image/${props.assetId}`
  })
}

const drawPreview = async () => {
  if (!canvas.value) return

  try {
    const img = await loadImage()
    const ctx = canvas.value.getContext('2d')

    // Clear canvas
    ctx.clearRect(0, 0, displaySize, displaySize)

    // Determine source region
    const sx = props.previewX ?? 0
    const sy = props.previewY ?? 0
    const sw = props.previewWidth ?? props.width
    const sh = props.previewHeight ?? props.height

    // Calculate scale to fit in display area
    const scale = Math.min(displaySize / sw, displaySize / sh)
    const scaledWidth = sw * scale
    const scaledHeight = sh * scale
    const offsetX = (displaySize - scaledWidth) / 2
    const offsetY = (displaySize - scaledHeight) / 2

    // Disable smoothing for pixel art
    ctx.imageSmoothingEnabled = false

    // Draw preview region
    ctx.drawImage(
      img,
      sx, sy, sw, sh,
      offsetX, offsetY, scaledWidth, scaledHeight
    )
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

onMounted(drawPreview)

watch(() => props.assetId, drawPreview)
</script>

<style scoped>
.sprite-canvas {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
</style>
```

**Step 2: Update AssetGrid.vue**

Replace the file:

```vue
<template>
  <div class="asset-grid-container">
    <div class="result-count" v-if="assets.length > 0">
      {{ assets.length }} results
    </div>
    <div class="asset-grid" v-if="assets.length > 0">
      <div
        v-for="asset in assets"
        :key="asset.id"
        class="asset-item"
        @click="$emit('select', asset.id)"
      >
        <SpritePreview
          v-if="asset.preview_x !== null"
          :asset-id="asset.id"
          :preview-x="asset.preview_x"
          :preview-y="asset.preview_y"
          :preview-width="asset.preview_width"
          :preview-height="asset.preview_height"
          :width="asset.width"
          :height="asset.height"
        />
        <img
          v-else
          :src="`/api/image/${asset.id}`"
          :alt="asset.filename"
        />
        <span class="filename">{{ asset.filename }}</span>
      </div>
    </div>
    <div v-else class="no-results">
      No results
    </div>
  </div>
</template>

<script setup>
import SpritePreview from './SpritePreview.vue'

defineProps({
  assets: {
    type: Array,
    required: true
  }
})

defineEmits(['select'])
</script>

<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: #666;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1rem;
}

.asset-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 4px;
}

.asset-item:hover {
  background: #f0f0f0;
}

.asset-item img {
  max-width: 100px;
  max-height: 100px;
  object-fit: contain;
  image-rendering: pixelated;
}

.filename {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  text-align: center;
  word-break: break-all;
}

.no-results {
  color: #666;
  text-align: center;
  padding: 2rem;
}
</style>
```

**Step 3: Build frontend to verify no errors**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add web/frontend/src/components/SpritePreview.vue web/frontend/src/components/AssetGrid.vue
git commit -m "refactor: simplify SpritePreview to static display

- Remove animation loop
- Use preview bounds props instead of frames array
- Update AssetGrid to pass preview bounds

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Run Full Test Suite and Manual Verification

**Step 1: Run all backend tests**

Run: `uv run pytest test_assetindex.py -v`
Expected: PASS

**Step 2: Run all API tests**

Run: `cd web && uv run pytest test_api.py -v`
Expected: PASS

**Step 3: Build frontend**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: complete spritesheet preview simplification

All tests pass, frontend builds successfully.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

**Tasks completed:**
1. Added `detect_first_sprite_bounds` function with flood-fill algorithm
2. Updated database schema (removed `sprite_frames`, added preview columns)
3. Removed frame detection functions
4. Updated `index_asset` to store preview bounds
5. Updated `index` command
6. Updated `generate_pack_preview` to use preview bounds
7. Removed animation endpoints from API
8. Updated search API to return preview bounds
9. Simplified frontend to static preview
10. Verified all tests pass

**Migration notes:**
- Existing databases need to be re-created (schema changed)
- Run `uv run assetindex.py index <path> --force` to re-index assets
