# Spritesheet Handling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable AI-powered sprite frame detection, animated thumbnails in search results, and sprite extraction API/CLI.

**Architecture:** Vision API (Claude) analyzes spritesheets during indexing to extract per-frame positions. Frame data stored in `sprite_frames` table. API serves frame metadata and extracted frames. Frontend renders animated thumbnails using canvas.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Vue 3, Claude API (anthropic SDK), Pillow

---

## Task 1: Add sprite_frames Database Schema

**Files:**
- Modify: `assetindex.py:50-122` (SCHEMA constant)
- Modify: `web/test_api.py:31-68` (test_db fixture schema)

**Step 1: Write test for sprite_frames table existence**

In `test_assetindex.py`, add at end of file before `if __name__`:

```python
class TestSpriteFramesSchema:
    """Tests for sprite_frames table."""

    def test_sprite_frames_table_exists(self, temp_db):
        """Verify sprite_frames table is created."""
        conn = assetindex.get_db(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sprite_frames'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_sprite_frames_columns(self, temp_db):
        """Verify sprite_frames has correct columns."""
        conn = assetindex.get_db(temp_db)
        cursor = conn.execute("PRAGMA table_info(sprite_frames)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"id", "asset_id", "frame_index", "x", "y", "width", "height"}
        assert expected.issubset(columns)
        conn.close()
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteFramesSchema -v
```

Expected: FAIL - sprite_frames table does not exist

**Step 3: Add sprite_frames table to schema**

In `assetindex.py`, add after line 113 (after `asset_embeddings` table):

```python
CREATE TABLE IF NOT EXISTS sprite_frames (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    frame_index INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    UNIQUE(asset_id, frame_index)
);

CREATE INDEX IF NOT EXISTS idx_sprite_frames_asset_id ON sprite_frames(asset_id);
```

Also add columns to assets table (in the CREATE TABLE assets section around line 62-77):

```sql
    analysis_method TEXT,
    animation_type TEXT,
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteFramesSchema -v
```

Expected: PASS

**Step 5: Update test_api.py fixture**

In `web/test_api.py`, update the `test_db` fixture schema (around line 31-68) to add:

```python
        CREATE TABLE sprite_frames (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER,
            frame_index INTEGER,
            x INTEGER,
            y INTEGER,
            width INTEGER,
            height INTEGER
        );
```

**Step 6: Run API tests to verify nothing broke**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All tests pass

**Step 7: Commit**

```bash
git add assetindex.py test_assetindex.py web/test_api.py
git commit -m "feat: add sprite_frames table schema

Adds database table for storing per-frame sprite positions and dimensions.
Includes analysis_method and animation_type columns on assets table.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create Sprite Analyzer Module with Mock

**Files:**
- Create: `sprite_analyzer.py`
- Create: `test_sprite_analyzer.py`

**Step 1: Write failing test for analyze_spritesheet function**

Create `test_sprite_analyzer.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
# ]
# ///
"""Tests for sprite analyzer module."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def sample_spritesheet(tmp_path):
    """Create a 128x128 image simulating a 4x4 grid of 32x32 sprites."""
    img_path = tmp_path / "spritesheet.png"
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    # Draw 16 small squares at grid positions
    for row in range(4):
        for col in range(4):
            x = col * 32 + 8  # 8px padding inside cell
            y = row * 32 + 8
            for dx in range(16):
                for dy in range(16):
                    img.putpixel((x + dx, y + dy), (100, 150, 50, 255))
    img.save(img_path)
    return img_path


class TestAnalyzeSpritesheet:
    """Tests for analyze_spritesheet function."""

    def test_returns_dict_with_frames(self, sample_spritesheet):
        """analyze_spritesheet returns dict with frames list."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        assert isinstance(result, dict)
        assert "frames" in result
        assert isinstance(result["frames"], list)

    def test_detects_frame_count(self, sample_spritesheet):
        """analyze_spritesheet detects correct number of frames."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        # Should detect 16 frames in 4x4 grid
        assert len(result["frames"]) == 16

    def test_frame_has_required_fields(self, sample_spritesheet):
        """Each frame has index, x, y, width, height."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        frame = result["frames"][0]
        assert "index" in frame
        assert "x" in frame
        assert "y" in frame
        assert "width" in frame
        assert "height" in frame

    def test_frame_dimensions_are_integers(self, sample_spritesheet):
        """Frame dimensions are integers."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        frame = result["frames"][0]
        assert isinstance(frame["x"], int)
        assert isinstance(frame["y"], int)
        assert isinstance(frame["width"], int)
        assert isinstance(frame["height"], int)
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_sprite_analyzer.py -v
```

Expected: FAIL - ModuleNotFoundError: No module named 'sprite_analyzer'

**Step 3: Create sprite_analyzer.py with stub implementation**

Create `sprite_analyzer.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pillow>=10.0",
#     "anthropic>=0.40",
# ]
# ///
"""Sprite analyzer using Claude Vision API."""

import base64
import json
import os
from pathlib import Path
from typing import Optional

from PIL import Image


def analyze_spritesheet(
    image_path: Path,
    api_key: Optional[str] = None,
) -> dict:
    """
    Analyze a spritesheet using Claude Vision API.

    Args:
        image_path: Path to the spritesheet image
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Dict with 'frames' list and optional 'animation_type'
    """
    image_path = Path(image_path)

    # For testing without API, use fallback detection
    if not api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback_detection(image_path)

    return _analyze_with_claude(image_path, api_key)


def _fallback_detection(image_path: Path) -> dict:
    """Fallback grid detection when API not available."""
    with Image.open(image_path) as img:
        width, height = img.size

        # Assume square cells if image is square
        if width == height:
            # Try to detect grid by finding common divisors
            for cell_size in [32, 16, 64, 48, 24, 8]:
                if width % cell_size == 0:
                    cols = width // cell_size
                    rows = height // cell_size
                    frames = []
                    for row in range(rows):
                        for col in range(cols):
                            frames.append({
                                "index": row * cols + col,
                                "x": col * cell_size,
                                "y": row * cell_size,
                                "width": cell_size,
                                "height": cell_size,
                            })
                    return {"frames": frames, "animation_type": None}

        # Horizontal strip
        if width > height and width % height == 0:
            frame_count = width // height
            return {
                "frames": [
                    {"index": i, "x": i * height, "y": 0, "width": height, "height": height}
                    for i in range(frame_count)
                ],
                "animation_type": None,
            }

        # Vertical strip
        if height > width and height % width == 0:
            frame_count = height // width
            return {
                "frames": [
                    {"index": i, "x": 0, "y": i * width, "width": width, "height": width}
                    for i in range(frame_count)
                ],
                "animation_type": None,
            }

        # Single frame
        return {
            "frames": [{"index": 0, "x": 0, "y": 0, "width": width, "height": height}],
            "animation_type": None,
        }


def _analyze_with_claude(image_path: Path, api_key: Optional[str] = None) -> dict:
    """Analyze spritesheet using Claude Vision API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # Determine media type
    suffix = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")

    # Get image dimensions for validation
    with Image.open(image_path) as img:
        img_width, img_height = img.size

    prompt = f"""Analyze this spritesheet image ({img_width}x{img_height} pixels). Identify each individual sprite frame.

Return JSON only, no other text:
{{
  "frames": [
    {{"index": 0, "x": <left_pixel>, "y": <top_pixel>, "width": <frame_width>, "height": <frame_height>}},
    ...
  ],
  "animation_type": "<idle|walk|run|jump|attack|die|cast|null>"
}}

Rules:
- Frames ordered left-to-right, top-to-bottom
- Include only cells with visible sprite content
- x, y are pixel coordinates from top-left (0,0)
- width, height are the cell dimensions
- All values must be integers
- Coordinates must be within image bounds (0-{img_width-1} for x, 0-{img_height-1} for y)"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    # Parse response
    response_text = response.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    result = json.loads(response_text.strip())

    # Validate and sanitize
    frames = []
    for frame in result.get("frames", []):
        x = int(frame.get("x", 0))
        y = int(frame.get("y", 0))
        w = int(frame.get("width", 1))
        h = int(frame.get("height", 1))

        # Clamp to image bounds
        x = max(0, min(x, img_width - 1))
        y = max(0, min(y, img_height - 1))
        w = max(1, min(w, img_width - x))
        h = max(1, min(h, img_height - y))

        frames.append({
            "index": int(frame.get("index", len(frames))),
            "x": x,
            "y": y,
            "width": w,
            "height": h,
        })

    return {
        "frames": frames,
        "animation_type": result.get("animation_type"),
    }
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_sprite_analyzer.py -v
```

Expected: PASS (using fallback detection for tests)

**Step 5: Commit**

```bash
git add sprite_analyzer.py test_sprite_analyzer.py
git commit -m "feat: add sprite analyzer module

AI-powered spritesheet analysis using Claude Vision API.
Includes fallback grid detection for testing without API key.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add Frame Extraction Function

**Files:**
- Modify: `sprite_analyzer.py`
- Modify: `test_sprite_analyzer.py`

**Step 1: Write failing test for extract_frame**

Add to `test_sprite_analyzer.py`:

```python
class TestExtractFrame:
    """Tests for extract_frame function."""

    def test_extracts_single_frame(self, sample_spritesheet):
        """extract_frame returns PIL Image of specified frame."""
        from sprite_analyzer import extract_frame

        frame_info = {"x": 0, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info)

        assert isinstance(result, Image.Image)
        assert result.size == (32, 32)

    def test_extracts_correct_region(self, sample_spritesheet):
        """extract_frame extracts correct pixel region."""
        from sprite_analyzer import extract_frame

        # Second cell in first row
        frame_info = {"x": 32, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info)

        assert result.size == (32, 32)

    def test_scale_parameter(self, sample_spritesheet):
        """extract_frame respects scale parameter."""
        from sprite_analyzer import extract_frame

        frame_info = {"x": 0, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info, scale=2)

        assert result.size == (64, 64)
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_sprite_analyzer.py::TestExtractFrame -v
```

Expected: FAIL - ImportError: cannot import name 'extract_frame'

**Step 3: Implement extract_frame**

Add to `sprite_analyzer.py`:

```python
def extract_frame(
    image_path: Path,
    frame: dict,
    scale: int = 1,
) -> Image.Image:
    """
    Extract a single frame from a spritesheet.

    Args:
        image_path: Path to the spritesheet
        frame: Dict with x, y, width, height
        scale: Scale factor for output (default 1)

    Returns:
        PIL Image of the extracted frame
    """
    image_path = Path(image_path)

    with Image.open(image_path) as img:
        # Crop to frame
        box = (
            frame["x"],
            frame["y"],
            frame["x"] + frame["width"],
            frame["y"] + frame["height"],
        )
        cropped = img.crop(box)

        # Scale if requested
        if scale != 1:
            new_size = (cropped.width * scale, cropped.height * scale)
            cropped = cropped.resize(new_size, Image.Resampling.NEAREST)

        return cropped.copy()
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_sprite_analyzer.py::TestExtractFrame -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add sprite_analyzer.py test_sprite_analyzer.py
git commit -m "feat: add extract_frame function

Extracts individual frames from spritesheets with optional scaling.
Uses nearest-neighbor resampling for crisp pixel art.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Add API Endpoint for Frames

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write failing test for /api/asset/{id}/frames**

Add to `web/test_api.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_frames_returns_frame_data -v
```

Expected: FAIL - 404 (endpoint doesn't exist)

**Step 3: Implement /api/asset/{id}/frames endpoint**

Add to `web/api.py` before `if __name__`:

```python
@app.get("/api/asset/{asset_id}/frames")
def asset_frames(asset_id: int):
    """Get sprite frame metadata for an asset."""
    conn = get_db()

    # Verify asset exists
    asset = conn.execute(
        "SELECT id, animation_type FROM assets WHERE id = ?", [asset_id]
    ).fetchone()

    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get frames
    frames = conn.execute("""
        SELECT frame_index, x, y, width, height
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
            }
            for f in frames
        ],
        "animation_type": asset["animation_type"],
    }
```

Also need to add `animation_type` column to the test fixture schema. Update the assets table in `test_db` fixture:

```python
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
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_frames_returns_frame_data test_api.py::test_asset_frames_not_found test_api.py::test_asset_frames_empty_for_non_spritesheet -v
```

Expected: PASS

**Step 5: Run all API tests**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat(api): add /asset/{id}/frames endpoint

Returns sprite frame metadata for animated thumbnails and extraction.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Add Frame Data to Search Results

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write failing test for frames in search results**

Add to `web/test_api.py`:

```python
def test_search_includes_frames(test_db):
    """Search results include frame data for spritesheets."""
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

    response = client.get("/api/search?q=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    asset = data["assets"][0]
    assert "frames" in asset
    assert len(asset["frames"]) == 2
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_search_includes_frames -v
```

Expected: FAIL - KeyError 'frames'

**Step 3: Modify search to include frames**

In `web/api.py`, update the search function. After getting rows, fetch frames for each asset:

Replace the `assets = []` loop (around line 179-190) with:

```python
    assets = []
    asset_ids = [row["id"] for row in rows]

    # Fetch frames for all assets in one query
    frames_by_asset = {}
    if asset_ids:
        placeholders = ",".join("?" * len(asset_ids))
        frame_rows = conn.execute(f"""
            SELECT asset_id, frame_index, x, y, width, height
            FROM sprite_frames
            WHERE asset_id IN ({placeholders})
            ORDER BY asset_id, frame_index
        """, asset_ids).fetchall()

        for f in frame_rows:
            aid = f["asset_id"]
            if aid not in frames_by_asset:
                frames_by_asset[aid] = []
            frames_by_asset[aid].append({
                "x": f["x"],
                "y": f["y"],
                "width": f["width"],
                "height": f["height"],
            })

    for row in rows:
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
            "frames": frames_by_asset.get(row["id"], []),
        })
```

**Step 4: Run test to verify it passes**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_search_includes_frames -v
```

Expected: PASS

**Step 5: Run all API tests**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat(api): include frames in search results

Enables frontend to render animated sprite thumbnails.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Add Single Frame API Endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write failing test for /api/asset/{id}/frame/{index}**

Add to `web/test_api.py`:

```python
def test_asset_frame_serves_cropped_image(test_db, tmp_path):
    """Get single frame serves cropped image."""
    from api import set_db_path, set_assets_path
    set_db_path(test_db)

    # Create a 64x32 spritesheet (2 frames of 32x32)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    pack_dir = assets_dir / "testpack"
    pack_dir.mkdir()

    from PIL import Image
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    # First frame: red
    for x in range(32):
        for y in range(32):
            img.putpixel((x, y), (255, 0, 0, 255))
    # Second frame: blue
    for x in range(32, 64):
        for y in range(32):
            img.putpixel((x, y), (0, 0, 255, 255))
    img.save(pack_dir / "spritesheet.png")

    set_assets_path(assets_dir)

    # Add asset and frames to DB
    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
        "VALUES (20, 1, 'testpack/spritesheet.png', 'spritesheet.png', 'png', 'xyz', 64, 32)"
    )
    conn.execute(
        "INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (20, 0, 0, 0, 32, 32)"
    )
    conn.execute(
        "INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (20, 1, 32, 0, 32, 32)"
    )
    conn.commit()
    conn.close()

    response = client.get("/api/asset/20/frame/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_asset_frame_not_found(test_db):
    """Get frame returns 404 for unknown frame index."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/1/frame/99")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_frame_serves_cropped_image -v
```

Expected: FAIL - 404 (endpoint doesn't exist)

**Step 3: Implement /api/asset/{id}/frame/{index} endpoint**

Add to `web/api.py`:

```python
from io import BytesIO
from fastapi.responses import StreamingResponse
```

Then add the endpoint:

```python
@app.get("/api/asset/{asset_id}/frame/{frame_index}")
def asset_frame(asset_id: int, frame_index: int, scale: int = 1):
    """Serve a single extracted frame as PNG."""
    conn = get_db()

    # Get asset path
    asset = conn.execute(
        "SELECT path FROM assets WHERE id = ?", [asset_id]
    ).fetchone()

    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get frame info
    frame = conn.execute("""
        SELECT x, y, width, height FROM sprite_frames
        WHERE asset_id = ? AND frame_index = ?
    """, [asset_id, frame_index]).fetchone()

    conn.close()

    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")

    # Extract frame
    from PIL import Image

    assets_dir = get_assets_path()
    image_path = assets_dir / asset["path"]

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    with Image.open(image_path) as img:
        box = (frame["x"], frame["y"], frame["x"] + frame["width"], frame["y"] + frame["height"])
        cropped = img.crop(box)

        if scale > 1:
            new_size = (cropped.width * scale, cropped.height * scale)
            cropped = cropped.resize(new_size, Image.Resampling.NEAREST)

        # Save to buffer
        buffer = BytesIO()
        cropped.save(buffer, format="PNG")
        buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_frame_serves_cropped_image test_api.py::test_asset_frame_not_found -v
```

Expected: PASS

**Step 5: Run all API tests**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat(api): add /asset/{id}/frame/{index} endpoint

Serves individual extracted frames as PNG with optional scaling.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Integrate Sprite Analysis into Indexer

**Files:**
- Modify: `assetindex.py`
- Modify: `test_assetindex.py`

**Step 1: Write failing test for frame storage during indexing**

Add to `test_assetindex.py`:

```python
class TestSpriteAnalysisIntegration:
    """Tests for sprite analysis during indexing."""

    def test_stores_sprite_frames(self, temp_dir):
        """Indexing stores sprite frames for detected spritesheets."""
        # Create a simple 64x32 spritesheet (2 frames)
        img_path = temp_dir / "TestPack" / "sprite.png"
        img_path.parent.mkdir(parents=True)
        img = Image.new("RGBA", (64, 32), (100, 100, 100, 255))
        img.save(img_path)

        db_path = temp_dir / "test.db"
        conn = assetindex.get_db(db_path)

        # Index the file
        assetindex.index_asset(conn, img_path, temp_dir)
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

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteAnalysisIntegration -v
```

Expected: FAIL - AttributeError: module 'assetindex' has no attribute 'index_asset'

**Step 3: Add index_asset function and sprite frame storage**

Add to `assetindex.py`:

```python
def store_sprite_frames(conn: sqlite3.Connection, asset_id: int, frames: list[dict]):
    """Store sprite frame data for an asset."""
    # Clear existing frames
    conn.execute("DELETE FROM sprite_frames WHERE asset_id = ?", [asset_id])

    # Insert new frames
    for frame in frames:
        conn.execute("""
            INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            asset_id,
            frame["index"],
            frame["x"],
            frame["y"],
            frame["width"],
            frame["height"],
        ])


def index_asset(
    conn: sqlite3.Connection,
    file_path: Path,
    asset_root: Path,
    analyze_sprites: bool = True,
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

    # Analyze sprites if image
    analysis_method = None
    animation_type = None
    frames = []

    if analyze_sprites and file_path.suffix.lower() in IMAGE_EXTENSIONS:
        try:
            from sprite_analyzer import analyze_spritesheet
            result = analyze_spritesheet(file_path)
            frames = result.get("frames", [])
            animation_type = result.get("animation_type")
            analysis_method = "ai" if len(frames) > 1 else "single"
        except Exception:
            analysis_method = "failed"

    # Insert or update asset
    conn.execute(
        """INSERT OR REPLACE INTO assets
           (pack_id, path, filename, filetype, file_hash, file_size,
            width, height, frame_count, frame_width, frame_height,
            category, analysis_method, animation_type, indexed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            analysis_method,
            animation_type,
            datetime.now(),
        ]
    )

    asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]

    # Store sprite frames
    if frames and len(frames) > 1:
        store_sprite_frames(conn, asset_id, frames)

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

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteAnalysisIntegration -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add assetindex.py test_assetindex.py
git commit -m "feat: integrate sprite analysis into indexer

Automatically analyzes spritesheets during indexing and stores frame data.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Add CLI Commands for Sprite Operations

**Files:**
- Modify: `assetindex.py`
- Modify: `test_assetindex.py`

**Step 1: Write failing test for analyze CLI command**

Add to `test_assetindex.py`:

```python
class TestSpriteCLI:
    """Tests for sprite CLI commands."""

    def test_analyze_command(self, temp_dir):
        """Test analyze command outputs frame data."""
        from typer.testing import CliRunner

        # Create test spritesheet
        img_path = temp_dir / "sprite.png"
        img = Image.new("RGBA", (64, 32), (100, 100, 100, 255))
        img.save(img_path)

        runner = CliRunner()
        result = runner.invoke(assetindex.app, ["analyze", str(img_path)])

        assert result.exit_code == 0
        assert "frames" in result.stdout
        assert '"x":' in result.stdout

    def test_extract_command(self, temp_dir):
        """Test extract command creates frame files."""
        from typer.testing import CliRunner

        # Create test spritesheet
        img_path = temp_dir / "sprite.png"
        img = Image.new("RGBA", (64, 32), (100, 100, 100, 255))
        img.save(img_path)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(assetindex.app, ["extract", str(img_path), str(output_dir)])

        assert result.exit_code == 0
        # Should create frame_000.png, frame_001.png
        assert (output_dir / "frame_000.png").exists()
        assert (output_dir / "frame_001.png").exists()
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteCLI -v
```

Expected: FAIL - No such command 'analyze'

**Step 3: Implement CLI commands**

Add to `assetindex.py`:

```python
import json


@app.command()
def analyze(
    image_path: Path = typer.Argument(..., help="Path to spritesheet image"),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json or table"),
):
    """Analyze a spritesheet and output frame data."""
    if not image_path.exists():
        console.print(f"[red]File not found: {image_path}[/red]")
        raise typer.Exit(1)

    from sprite_analyzer import analyze_spritesheet

    result = analyze_spritesheet(image_path)

    if output_format == "json":
        console.print(json.dumps(result, indent=2))
    else:
        console.print(f"[cyan]Frames:[/cyan] {len(result['frames'])}")
        console.print(f"[cyan]Animation:[/cyan] {result.get('animation_type', 'unknown')}")
        for frame in result["frames"]:
            console.print(f"  [{frame['index']}] x={frame['x']} y={frame['y']} {frame['width']}x{frame['height']}")


@app.command()
def extract(
    image_path: Path = typer.Argument(..., help="Path to spritesheet image"),
    output_dir: Path = typer.Argument(..., help="Output directory for frames"),
    scale: int = typer.Option(1, "--scale", "-s", help="Scale factor"),
):
    """Extract individual frames from a spritesheet."""
    if not image_path.exists():
        console.print(f"[red]File not found: {image_path}[/red]")
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    from sprite_analyzer import analyze_spritesheet, extract_frame

    result = analyze_spritesheet(image_path)
    frames = result.get("frames", [])

    if not frames:
        console.print("[yellow]No frames detected[/yellow]")
        raise typer.Exit(1)

    for frame in frames:
        frame_img = extract_frame(image_path, frame, scale=scale)
        output_path = output_dir / f"frame_{frame['index']:03d}.png"
        frame_img.save(output_path)
        console.print(f"Extracted: {output_path.name}")

    console.print(f"[green]Extracted {len(frames)} frames to {output_dir}[/green]")
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py::TestSpriteCLI -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add assetindex.py test_assetindex.py
git commit -m "feat(cli): add analyze and extract commands

- analyze: Output frame data as JSON or table
- extract: Export individual frames to files

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Frontend Animated Sprite Component

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`

**Step 1: Update AssetGrid to render animated sprites**

Replace `web/frontend/src/components/AssetGrid.vue`:

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
          v-if="asset.frames && asset.frames.length > 1"
          :asset-id="asset.id"
          :frames="asset.frames"
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

**Step 2: Create SpritePreview component**

Create `web/frontend/src/components/SpritePreview.vue`:

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
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  assetId: {
    type: Number,
    required: true
  },
  frames: {
    type: Array,
    required: true
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
let animationInterval = null
let currentFrame = 0
let spriteImage = null

const loadImage = () => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = `/api/image/${props.assetId}`
  })
}

const drawFrame = () => {
  if (!canvas.value || !spriteImage || !props.frames.length) return

  const ctx = canvas.value.getContext('2d')
  const frame = props.frames[currentFrame]

  // Clear canvas
  ctx.clearRect(0, 0, displaySize, displaySize)

  // Calculate scale to fit frame in display area
  const scale = Math.min(displaySize / frame.width, displaySize / frame.height)
  const scaledWidth = frame.width * scale
  const scaledHeight = frame.height * scale
  const offsetX = (displaySize - scaledWidth) / 2
  const offsetY = (displaySize - scaledHeight) / 2

  // Disable smoothing for pixel art
  ctx.imageSmoothingEnabled = false

  // Draw current frame
  ctx.drawImage(
    spriteImage,
    frame.x, frame.y, frame.width, frame.height,
    offsetX, offsetY, scaledWidth, scaledHeight
  )
}

const startAnimation = async () => {
  try {
    spriteImage = await loadImage()
    drawFrame()

    if (props.frames.length > 1) {
      animationInterval = setInterval(() => {
        currentFrame = (currentFrame + 1) % props.frames.length
        drawFrame()
      }, 120)
    }
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

const stopAnimation = () => {
  if (animationInterval) {
    clearInterval(animationInterval)
    animationInterval = null
  }
}

onMounted(startAnimation)
onUnmounted(stopAnimation)

watch(() => props.assetId, () => {
  stopAnimation()
  currentFrame = 0
  startAnimation()
})
</script>

<style scoped>
.sprite-canvas {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
</style>
```

**Step 3: Test manually in browser**

```bash
cd /Users/pogaair/projects/asset-manager/web/frontend && npm run dev
```

Visit http://localhost:5173 and search for spritesheets to verify animation.

**Step 4: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue web/frontend/src/components/SpritePreview.vue
git commit -m "feat(frontend): add animated sprite thumbnails

Renders spritesheets as animated previews in search results using canvas.
Uses pixelated rendering for crisp pixel art display.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Add Animation GIF Generation Endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write failing test for /api/asset/{id}/animation**

Add to `web/test_api.py`:

```python
def test_asset_animation_generates_gif(test_db, tmp_path):
    """Animation endpoint generates animated GIF."""
    from api import set_db_path, set_assets_path
    set_db_path(test_db)

    # Create a 64x32 spritesheet (2 frames of 32x32)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    pack_dir = assets_dir / "testpack"
    pack_dir.mkdir()

    from PIL import Image
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    for x in range(32):
        for y in range(32):
            img.putpixel((x, y), (255, 0, 0, 255))
    for x in range(32, 64):
        for y in range(32):
            img.putpixel((x, y), (0, 0, 255, 255))
    img.save(pack_dir / "anim.png")

    set_assets_path(assets_dir)

    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height) "
        "VALUES (30, 1, 'testpack/anim.png', 'anim.png', 'png', 'anim123', 64, 32)"
    )
    conn.execute("INSERT INTO sprite_frames VALUES (NULL, 30, 0, 0, 0, 32, 32)")
    conn.execute("INSERT INTO sprite_frames VALUES (NULL, 30, 1, 32, 0, 32, 32)")
    conn.commit()
    conn.close()

    response = client.get("/api/asset/30/animation")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_animation_generates_gif -v
```

Expected: FAIL - 404 (endpoint doesn't exist)

**Step 3: Implement animation endpoint**

Add to `web/api.py`:

```python
@app.get("/api/asset/{asset_id}/animation")
def asset_animation(
    asset_id: int,
    fps: int = 10,
    scale: int = 1,
    format: str = "gif",
):
    """Generate animated GIF/WebP from spritesheet frames."""
    conn = get_db()

    asset = conn.execute(
        "SELECT path FROM assets WHERE id = ?", [asset_id]
    ).fetchone()

    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    frames_data = conn.execute("""
        SELECT x, y, width, height FROM sprite_frames
        WHERE asset_id = ? ORDER BY frame_index
    """, [asset_id]).fetchall()

    conn.close()

    if not frames_data:
        raise HTTPException(status_code=404, detail="No frames found")

    from PIL import Image

    assets_dir = get_assets_path()
    image_path = assets_dir / asset["path"]

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    # Extract frames
    pil_frames = []
    with Image.open(image_path) as img:
        for f in frames_data:
            box = (f["x"], f["y"], f["x"] + f["width"], f["y"] + f["height"])
            frame = img.crop(box)

            if scale > 1:
                new_size = (frame.width * scale, frame.height * scale)
                frame = frame.resize(new_size, Image.Resampling.NEAREST)

            # Convert to RGBA for consistency
            if frame.mode != "RGBA":
                frame = frame.convert("RGBA")

            pil_frames.append(frame)

    # Create animated image
    buffer = BytesIO()
    duration = int(1000 / fps)  # ms per frame

    if format == "webp":
        pil_frames[0].save(
            buffer,
            format="WEBP",
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration,
            loop=0,
        )
        media_type = "image/webp"
    else:
        # GIF requires palette mode
        gif_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE) for f in pil_frames]
        gif_frames[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration,
            loop=0,
            disposal=2,
        )
        media_type = "image/gif"

    buffer.seek(0)
    return StreamingResponse(buffer, media_type=media_type)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py::test_asset_animation_generates_gif -v
```

Expected: PASS

**Step 5: Run all tests**

```bash
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat(api): add /asset/{id}/animation endpoint

Generates animated GIF or WebP from spritesheet frames.
Supports fps and scale parameters.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Run Full Test Suite and Final Verification

**Step 1: Run all Python tests**

```bash
cd /Users/pogaair/projects/asset-manager && uv run pytest test_assetindex.py test_sprite_analyzer.py -v
cd /Users/pogaair/projects/asset-manager/web && uv run pytest test_api.py -v
```

Expected: All pass

**Step 2: Manual integration test**

```bash
# Re-index with sprite analysis
cd /Users/pogaair/projects/asset-manager
uv run ./assetindex.py index assets --force

# Test CLI commands
uv run ./assetindex.py analyze "assets/Minifantasy_True_Heroes_III_v1.1/Minifantasy_True_Heroes_III_Assets/Fighter/General_Animations/Figther_Jump.png"

# Start API server
cd web && uv run ./api.py &

# Test API endpoints
curl http://localhost:8000/api/search?q=Jump | jq '.assets[0].frames'
curl http://localhost:8000/api/asset/1/frames | jq

# Start frontend
cd frontend && npm run dev
```

Visit http://localhost:5173 and verify animated thumbnails work.

**Step 3: Commit any fixes**

If any issues found, fix and commit.

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification

All tests passing, sprite analysis integrated.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

This plan implements:
1. **Database schema** for sprite frames (Task 1)
2. **Sprite analyzer module** with Claude Vision API (Tasks 2-3)
3. **API endpoints** for frames, single frame, and animation generation (Tasks 4-6, 10)
4. **Indexer integration** for automatic sprite analysis (Task 7)
5. **CLI commands** for analyze and extract (Task 8)
6. **Frontend animated thumbnails** (Task 9)

Each task follows TDD: write failing test, implement, verify, commit.
