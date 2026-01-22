# Remove AI Analysis and Index Frames Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove AI-powered sprite analysis and replace with metadata-based frame detection.

**Architecture:** Parse `_AnimationInfo.txt` for frame dimensions when available, fall back to dimension-based heuristics. No external API dependencies.

**Tech Stack:** Python, SQLite, Pillow, Typer

---

## Task 1: Delete AI-Related Files

**Files:**
- Delete: `sprite_analyzer.py`
- Delete: `test_sprite_analyzer.py`
- Delete: `tests/benchmark/` (entire directory)

**Step 1: Delete the files**

```bash
rm sprite_analyzer.py
rm test_sprite_analyzer.py
rm -rf tests/benchmark
```

**Step 2: Verify deletion**

Run: `ls sprite_analyzer.py test_sprite_analyzer.py tests/benchmark 2>&1`
Expected: "No such file or directory" for each

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove AI sprite analyzer and benchmark system"
```

---

## Task 2: Remove AI Commands from index.py

**Files:**
- Modify: `index.py`

**Step 1: Remove anthropic from dependencies (line 10)**

Change line 10 from:
```python
#     "anthropic>=0.40",
```
To: (delete the line entirely)

**Step 2: Remove the `analyze` command (lines 745-821)**

Delete the entire `@app.command() def analyze(...)` function.

**Step 3: Remove the `extract` command (lines 823-851)**

Delete the entire `@app.command() def extract(...)` function.

**Step 4: Remove the `analyze-all` command (lines 854-956)**

Delete the entire `@app.command("analyze-all") def analyze_all(...)` function.

**Step 5: Verify removal**

Run: `uv run index.py --help`
Expected: No `analyze`, `extract`, or `analyze-all` commands listed

**Step 6: Commit**

```bash
git add index.py
git commit -m "feat: remove analyze, extract, analyze-all CLI commands"
```

---

## Task 3: Simplify Schema and Remove AI Columns

**Files:**
- Modify: `index.py`

**Step 1: Remove analysis_method and animation_type from assets table in SCHEMA (lines 83-84)**

In the SCHEMA constant, remove these two lines from the assets table definition:
```python
    analysis_method TEXT,
    animation_type TEXT,
```

**Step 2: Add duration_ms column to sprite_frames table in SCHEMA (line 124-133)**

Change the sprite_frames table definition to:
```python
CREATE TABLE IF NOT EXISTS sprite_frames (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    frame_index INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    duration_ms INTEGER,
    UNIQUE(asset_id, frame_index)
);
```

**Step 3: Update store_sprite_frames function (lines 367-397)**

Replace the function with:
```python
def store_sprite_frames(conn: sqlite3.Connection, asset_id: int, frames: list[dict]):
    """Store sprite frame data for an asset."""
    # Clear existing frames
    conn.execute("DELETE FROM sprite_frames WHERE asset_id = ?", [asset_id])

    # Insert new frames
    for frame in frames:
        conn.execute("""
            INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            asset_id,
            frame["index"],
            frame["x"],
            frame["y"],
            frame["width"],
            frame["height"],
            frame.get("duration_ms"),
        ])
```

**Step 4: Commit**

```bash
git add index.py
git commit -m "feat: simplify schema, remove AI columns, add duration_ms"
```

---

## Task 4: Implement Frame Detection from Metadata

**Files:**
- Modify: `index.py`

**Step 1: Add detect_frames_from_info function after parse_animation_info**

Add this new function after line 309:
```python
def detect_frames(image_path: Path, anim_info: dict) -> list[dict]:
    """
    Detect frames using animation info or heuristics.

    Priority:
    1. Use _AnimationInfo.txt frame size if available
    2. Fall back to dimension-based heuristics
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception:
        return []

    # Get frame size from animation info
    frame_size = anim_info.get("frame_size")
    if frame_size:
        match = re.match(r"(\d+)x(\d+)", frame_size)
        if match:
            fw, fh = int(match.group(1)), int(match.group(2))
            if width % fw == 0 and height % fh == 0:
                cols = width // fw
                rows = height // fh
                frames = []
                for row in range(rows):
                    for col in range(cols):
                        frames.append({
                            "index": row * cols + col,
                            "x": col * fw,
                            "y": row * fh,
                            "width": fw,
                            "height": fh,
                        })
                return frames

    # Heuristic: horizontal strip of square frames
    if width > height and height > 0 and width % height == 0:
        frame_count = width // height
        return [
            {"index": i, "x": i * height, "y": 0, "width": height, "height": height}
            for i in range(frame_count)
        ]

    # Heuristic: vertical strip of square frames
    if height > width and width > 0 and height % width == 0:
        frame_count = height // width
        return [
            {"index": i, "x": 0, "y": i * width, "width": width, "height": width}
            for i in range(frame_count)
        ]

    # Single frame
    return [{"index": 0, "x": 0, "y": 0, "width": width, "height": height}]
```

**Step 2: Commit**

```bash
git add index.py
git commit -m "feat: add detect_frames function using metadata and heuristics"
```

---

## Task 5: Update index_asset to Use New Frame Detection

**Files:**
- Modify: `index.py`

**Step 1: Remove AI analysis from index_asset function (lines 400-500)**

Find and remove these lines from index_asset:
- Remove the `analyze_sprites` parameter
- Remove the entire AI analysis block (lines 429-442)
- Remove `analysis_method` and `animation_type` from the INSERT statement

**Step 2: Rewrite index_asset function**

Replace the function starting at line 400:
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

    # Check for animation info
    anim_info = {}
    for info_name in ["_AnimationInfo.txt", "AnimationInfo.txt"]:
        info_path = file_path.parent / info_name
        if info_path.exists():
            anim_info = parse_animation_info(info_path)
            break

    # Detect frames
    frames = []
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        frames = detect_frames(file_path, anim_info)

    # Insert or update asset
    conn.execute(
        """INSERT OR REPLACE INTO assets
           (pack_id, path, filename, filetype, file_hash, file_size,
            width, height, frame_count, frame_width, frame_height,
            category, indexed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            pack_id,
            rel_path,
            file_path.name,
            file_path.suffix.lower().lstrip("."),
            current_hash,
            file_path.stat().st_size,
            img_info.get("width"),
            img_info.get("height"),
            len(frames) if frames else img_info.get("frame_count"),
            frames[0]["width"] if frames else img_info.get("frame_width"),
            frames[0]["height"] if frames else img_info.get("frame_height"),
            category,
            datetime.now(),
        ]
    )

    asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]

    # Store sprite frames (if more than 1 frame)
    if len(frames) > 1:
        store_sprite_frames(conn, asset_id, frames)

    # Extract and add tags
    tags = extract_tags_from_path(file_path, asset_root)
    add_tags(conn, asset_id, tags, "path")

    # Add frame size as tag if found in metadata
    if anim_info.get("frame_size"):
        add_tags(conn, asset_id, [anim_info["frame_size"]], "metadata")

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

**Step 3: Run tests to verify**

Run: `uv run --script test_index.py -k "not SpriteCLI and not test_stores_sprite_frames" -v 2>&1 | tail -20`
Expected: All tests pass

**Step 4: Commit**

```bash
git add index.py
git commit -m "feat: integrate frame detection into index_asset"
```

---

## Task 6: Update index Command to Detect Frames

**Files:**
- Modify: `index.py`

**Step 1: Update the index command to store frames during indexing**

In the `index` function (starting around line 547), after the asset is inserted and before `new_count += 1`, add frame detection. Find the section that inserts assets (around lines 618-640) and add frame storage:

After line 640 (`asset_id = conn.execute(...).fetchone()[0]`), add:
```python
            # Detect and store frames
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                frames = detect_frames(file_path, anim_info)
                if len(frames) > 1:
                    store_sprite_frames(conn, asset_id, frames)
```

**Step 2: Run tests**

Run: `uv run --script test_index.py -v 2>&1 | tail -30`
Expected: Tests pass (excluding removed CLI tests)

**Step 3: Commit**

```bash
git add index.py
git commit -m "feat: store frames during index command"
```

---

## Task 7: Update Tests

**Files:**
- Modify: `test_index.py`

**Step 1: Remove anthropic from test dependencies (line 11)**

Delete line 11:
```python
#     "anthropic>=0.40",
```

**Step 2: Remove TestSpriteCLI class (lines 730-840)**

Delete the entire `class TestSpriteCLI` and all its methods.

**Step 3: Update TestSpriteAnalysisIntegration.test_stores_sprite_frames (lines 668-700)**

Replace the test:
```python
class TestSpriteAnalysisIntegration:
    """Tests for sprite frame detection during indexing."""

    def test_stores_sprite_frames(self, temp_dir):
        """Indexing stores sprite frames for detected spritesheets."""
        # Create a simple 64x32 spritesheet (2 frames)
        img_path = temp_dir / "TestPack" / "sprite.png"
        img_path.parent.mkdir(parents=True)
        img = Image.new("RGBA", (64, 32), (100, 100, 100, 255))
        img.save(img_path)

        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)

        # Index the file
        index.index_asset(conn, img_path, temp_dir)
        conn.commit()

        # Check frames were stored
        asset_id = conn.execute(
            "SELECT id FROM assets WHERE filename = 'sprite.png'"
        ).fetchone()[0]

        frames = conn.execute(
            "SELECT * FROM sprite_frames WHERE asset_id = ? ORDER BY frame_index",
            [asset_id]
        ).fetchall()

        assert len(frames) == 2
        assert frames[0]["width"] == 32
        assert frames[1]["x"] == 32

        conn.close()
```

**Step 4: Add test for _AnimationInfo.txt frame detection**

Add a new test after the existing one:
```python
    def test_uses_animation_info_for_frame_detection(self, temp_dir):
        """Frame detection uses _AnimationInfo.txt when available."""
        # Create a 128x64 image (could be 4x2 grid of 32x32 or 2x1 of 64x64)
        pack_dir = temp_dir / "TestPack"
        pack_dir.mkdir()
        img_path = pack_dir / "sprite.png"
        img = Image.new("RGBA", (128, 64), (100, 100, 100, 255))
        img.save(img_path)

        # Create animation info specifying 32x32 frames
        info_path = pack_dir / "_AnimationInfo.txt"
        info_path.write_text("Frame size: 32x32px")

        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)

        index.index_asset(conn, img_path, temp_dir)
        conn.commit()

        asset_id = conn.execute(
            "SELECT id FROM assets WHERE filename = 'sprite.png'"
        ).fetchone()[0]

        frames = conn.execute(
            "SELECT * FROM sprite_frames WHERE asset_id = ? ORDER BY frame_index",
            [asset_id]
        ).fetchall()

        # Should detect 4x2 = 8 frames of 32x32
        assert len(frames) == 8
        assert frames[0]["width"] == 32
        assert frames[0]["height"] == 32

        conn.close()
```

**Step 5: Run all tests**

Run: `uv run --script test_index.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add test_index.py
git commit -m "test: update tests for metadata-based frame detection"
```

---

## Task 8: Update Web API

**Files:**
- Modify: `web/api.py`

**Step 1: Remove animation_type from asset_frames response (lines 374-410)**

In the `asset_frames` function, remove the `animation_type` query and response field:

Replace lines 380-410:
```python
@app.get("/api/asset/{asset_id}/frames")
def asset_frames(asset_id: int):
    """Get sprite frame metadata for an asset."""
    conn = get_db()

    # Verify asset exists
    asset = conn.execute(
        "SELECT id FROM assets WHERE id = ?", [asset_id]
    ).fetchone()

    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get frames
    frames = conn.execute("""
        SELECT frame_index, x, y, width, height, duration_ms
        FROM sprite_frames
        WHERE asset_id = ?
        ORDER BY frame_index
    """, [asset_id]).fetchall()

    conn.close()

    return {
        "frames": [
            {
                "index": f["frame_index"],
                "x": f["x"],
                "y": f["y"],
                "width": f["width"],
                "height": f["height"],
                "duration_ms": f["duration_ms"],
            }
            for f in frames
        ],
    }
```

**Step 2: Run API tests**

Run: `uv run --script web/test_api.py -v 2>&1 | tail -20`
Expected: All tests pass

**Step 3: Commit**

```bash
git add web/api.py
git commit -m "feat: remove animation_type from API, add duration_ms"
```

---

## Task 9: Clean Up and Final Verification

**Files:**
- Delete: `assets.db` (will be rebuilt)

**Step 1: Delete old database**

```bash
rm -f assets.db
```

**Step 2: Run full test suite**

Run: `uv run --script test_index.py -v && uv run --script web/test_api.py -v`
Expected: All tests pass

**Step 3: Test indexing real assets**

Run: `uv run index.py index assets --db assets.db`
Expected: Indexing completes without errors

**Step 4: Verify frames were detected**

Run: `sqlite3 assets.db "SELECT COUNT(*) FROM sprite_frames"`
Expected: Non-zero count showing frames were detected

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: clean up and verify new indexing"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Delete AI-related files |
| 2 | Remove AI commands from CLI |
| 3 | Simplify schema |
| 4 | Implement frame detection |
| 5 | Update index_asset function |
| 6 | Update index command |
| 7 | Update tests |
| 8 | Update web API |
| 9 | Clean up and verify |
