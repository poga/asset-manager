# Spritesheet Preview Simplification Design

**Date:** 2026-01-22
**Status:** Approved

## Overview

Replace complex heuristic-based spritesheet frame detection with a simple "find first sprite" approach for preview generation. Remove all animation-related features.

## Problem

The current frame detection uses dimension-based heuristics (e.g., "width % height == 0") that fail for:
- Grid layouts (4x4, 3x2, etc.)
- Non-square frames
- Images with padding/margins
- Many common spritesheet arrangements

This causes incorrect previews and wasted complexity.

## Solution

Simplify to: find the minimal bounding rectangle of the first sprite in the image and use that as the preview.

## Database Changes

### Remove

Drop `sprite_frames` table entirely.

### Add

Add preview bounds columns to `assets` table:

```sql
ALTER TABLE assets ADD COLUMN preview_x INTEGER;
ALTER TABLE assets ADD COLUMN preview_y INTEGER;
ALTER TABLE assets ADD COLUMN preview_width INTEGER;
ALTER TABLE assets ADD COLUMN preview_height INTEGER;
```

When `NULL`, the full image is used as preview.

## First Sprite Detection Algorithm

**Function:** `detect_first_sprite_bounds(image_path) -> tuple[int, int, int, int] | None`

1. Open image, convert to RGBA if needed
2. Scan pixels left-to-right, top-to-bottom until finding first non-transparent pixel (alpha > 0)
3. Flood-fill from that pixel to find all connected non-transparent pixels (8-directional connectivity)
4. Return bounding box (x, y, width, height) of the connected region
5. Return `None` if image is fully transparent or has no alpha channel

### Edge Cases

- Images without alpha channel: return `None`, use full image
- Fully transparent images: return `None`
- Very small sprites (< 4px): valid, use as-is

## Code Removal

### From `index.py`

- Delete `sprite_frames` table from schema
- Delete `detect_frames()` function
- Delete `store_frames()` function
- Delete `parse_animation_info()` function
- Simplify `get_image_info()` to only return basic width/height/format
- Update `generate_pack_preview()` to use stored preview bounds

### From `web/api.py`

- Delete `/api/asset/{id}/frames` endpoint
- Delete `/api/asset/{id}/frame/{index}` endpoint
- Delete `/api/asset/{id}/animation` endpoint
- Remove frame fetching from search results

### From Frontend

- Simplify `SpritePreview.vue` - static preview only, no animation
- Update components that pass frame data

## Preview Generation Flow

### During Indexing

1. Extract basic image info
2. Call `detect_first_sprite_bounds()`
3. Store bounds in assets table (or `NULL` if detection fails)

### Pack Preview Montage

1. Query assets with preview bounds
2. Crop each image to bounds (or use full image if `NULL`)
3. Scale to 64x64 thumbnail
4. Compose 4x4 montage

### Frontend Display

1. Receive preview bounds from API
2. Draw bounded region to canvas, scaled to fit
3. No animation - static display only

## API Changes

Asset objects include nullable preview bounds:

```json
{
  "id": 1,
  "filename": "hero.png",
  "width": 384,
  "height": 32,
  "preview_x": 0,
  "preview_y": 0,
  "preview_width": 32,
  "preview_height": 32
}
```

## Migration

1. Run schema migration (drop `sprite_frames`, add columns)
2. Re-index all assets to populate preview bounds

## Files Affected

- `index.py` - major simplification
- `web/api.py` - remove 3 endpoints, simplify responses
- `web/frontend/src/components/SpritePreview.vue` - static display only
