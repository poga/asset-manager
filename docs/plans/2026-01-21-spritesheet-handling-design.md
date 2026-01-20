# Spritesheet Handling Improvements

## Problem

- Spritesheets display as tiny unreadable thumbnails in search results (e.g., 384x32 strip squeezed to 100x100px)
- Current detection only handles simple horizontal/vertical strips via divisibility check
- Grid layouts (e.g., 4x4 frames in 128x128 image) aren't detected
- No way to preview animations or extract individual frames

## Solution Overview

1. **AI-powered sprite frame detection** during indexing
2. **Animated thumbnails** in frontend search results
3. **API endpoints** for frame access and animation generation
4. **CLI commands** for pipeline automation

## Detailed Design

### 1. AI-Powered Per-Frame Extraction

Use a vision API (Claude) to analyze each spritesheet and extract per-frame metadata.

**Prompt structure:**

```
Analyze this spritesheet image. Identify each individual sprite frame.

Return JSON only:
{
  "frames": [
    {"index": 0, "x": <left>, "y": <top>, "width": <w>, "height": <h>},
    ...
  ],
  "animation_type": "<idle|walk|run|jump|attack|die|cast|null>"
}

Rules:
- Frames are ordered left-to-right, top-to-bottom unless clearly different
- Include only cells containing visible sprite content
- x, y are pixel coordinates from top-left of image
- width, height are the cell dimensions (include padding for consistency)
```

**Example output for `Figther_Jump.png` (128x128, 4x4 grid):**

```json
{
  "frames": [
    {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32},
    {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32},
    {"index": 2, "x": 64, "y": 0, "width": 32, "height": 32},
    {"index": 3, "x": 96, "y": 0, "width": 32, "height": 32},
    {"index": 4, "x": 0, "y": 32, "width": 32, "height": 32},
    ...
    {"index": 15, "x": 96, "y": 96, "width": 32, "height": 32}
  ],
  "animation_type": "jump"
}
```

**Database schema - new table:**

```sql
CREATE TABLE sprite_frames (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    frame_index INTEGER,      -- 0-based order in animation
    x INTEGER,                -- left position in pixels
    y INTEGER,                -- top position in pixels
    width INTEGER,            -- frame width
    height INTEGER,           -- frame height
    UNIQUE(asset_id, frame_index)
);

-- Add analysis metadata to assets table
ALTER TABLE assets ADD COLUMN analysis_method TEXT;  -- 'ai' | 'legacy' | 'manual'
ALTER TABLE assets ADD COLUMN animation_type TEXT;   -- 'idle', 'walk', 'jump', etc.
```

**Error handling:**

- If API fails, fall back to legacy divisibility detection
- If response is invalid JSON, retry once
- Store `analysis_method` field to track how frames were detected

### 2. Frontend Animated Thumbnails

**Behavior:**

- Search results (AssetGrid.vue) show animated preview for assets with sprite_frames
- All spritesheet thumbnails animate continuously
- Frame cycle at ~100-150ms intervals
- Use `image-rendering: pixelated` for crisp pixel art scaling

**Implementation approach:**

- API returns frame data with search results
- Frontend uses canvas rendering or CSS clip-path to show one frame at a time
- `setInterval` cycles through frames
- Scale frames to fit ~100x100px thumbnail area

**Search response includes frames:**

```json
{
  "results": [
    {
      "id": 123,
      "filename": "Figther_Jump.png",
      "width": 128,
      "height": 128,
      "frames": [
        {"x": 0, "y": 0, "width": 32, "height": 32},
        {"x": 32, "y": 0, "width": 32, "height": 32},
        ...
      ]
    }
  ]
}
```

### 3. API Endpoints

```
GET /api/asset/{id}/frames
  Returns frame metadata for a spritesheet
  Response: { "frames": [...], "animation_type": "jump" }

GET /api/asset/{id}/frame/{index}
  Serves a single cropped frame as PNG
  Query params: ?scale=2 (optional upscaling for pixel art)

GET /api/asset/{id}/animation
  Generates and serves animated GIF/WebP
  Query params: ?fps=10&scale=2&format=gif|webp

GET /api/asset/{id}/extract
  Returns ZIP of all frames as individual PNGs
  Query params: ?scale=1&format=png
```

### 4. CLI Commands

```bash
# Analyze a spritesheet (standalone, without full index)
assetindex analyze <image_path>
  Output: JSON with detected frame metadata

# Preview animation in terminal or viewer window
assetindex preview <image_path_or_asset_id>
  Options: --fps=10, --scale=2

# Extract frames to files
assetindex extract <image_path_or_asset_id> <output_dir>
  Output: frame_000.png, frame_001.png, etc.
  Options: --scale=1, --format=png

# Re-analyze existing indexed assets
assetindex reindex --frames-only
  Runs AI analysis on all spritesheets, updates sprite_frames table
```

### 5. Integration with Existing Indexing

During `assetindex build`:

1. After basic image info extraction
2. Detect if image is potential spritesheet (PNG with multiple pixels)
3. Call vision API via `sprite_analyzer.py`
4. Parse response, validate coordinates within image bounds
5. Store frames in `sprite_frames` table
6. Store `analysis_method` and `animation_type` in `assets` table

## Files to Create/Modify

| File | Change |
|------|--------|
| `sprite_analyzer.py` | New - AI vision integration module |
| `test_sprite_analyzer.py` | New - Tests for frame detection |
| `assetindex.py` | Add frame analysis during indexing, new CLI commands |
| `test_assetindex.py` | Add tests for new CLI commands |
| `web/api.py` | Add frame/animation endpoints |
| `web/test_api.py` | Add tests for new endpoints |
| `web/frontend/src/components/AssetGrid.vue` | Animated sprite rendering |
| `web/frontend/src/components/AssetGrid.test.js` | Frontend tests |

## Implementation Notes

- Use TDD approach throughout
- Keep cell boundaries when extracting (preserve positioning for game engines)
- Search remains at spritesheet level; frames are for preview/extraction only
- Vision API: Claude with image support
