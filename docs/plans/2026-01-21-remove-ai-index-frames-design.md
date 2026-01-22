# Remove AI Analysis and Index Frames from Metadata

## Summary

Remove all AI-powered sprite analysis features and replace with simpler frame detection using `_AnimationInfo.txt` files and dimension-based heuristics.

## What Gets Removed

**Files to delete:**
- `sprite_analyzer.py` - AI analysis module
- `tests/benchmark/` - Benchmark directory and contents
- `tests/test_sprite_analyzer.py` - Tests for removed module
- `tests/test_benchmark.py` - Tests for removed benchmark

**Code to remove from `index.py`:**
- `analyze` command
- `extract` command
- `analyze-all` command
- Import of `sprite_analyzer`
- All calls to `analyze_spritesheet()`

**Dependencies to remove:**
- `anthropic` package

**Database columns to remove:**
- `sprite_frames.analysis_method`
- `sprite_frames.animation_type`

## New Frame Indexing Logic

**Frame detection priority:**

1. `_AnimationInfo.txt` files - Parse frame size and durations when present
2. Heuristic detection when no txt file:
   - `width > height` and `width % height == 0` → horizontal strip of square frames
   - `height > width` and `height % width == 0` → vertical strip of square frames
   - Otherwise → single frame

**Simplified `sprite_frames` table:**
```sql
CREATE TABLE sprite_frames (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    frame_index INTEGER NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    duration_ms INTEGER,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

Frame detection runs during the `index` command - no separate commands needed.

## Web API Changes

**Endpoints kept (simplified):**
- `GET /api/asset/{id}/frames` - Returns frame metadata
- `GET /api/asset/{id}/frame/{index}` - Extracts single frame
- `GET /api/asset/{id}/animation` - Generates animated GIF/WebP

**Changes:**
- Remove `animation_type` from responses
- Move `extract_frame()` inline to `api.py` (simple PIL crop)

## Implementation Steps

1. Delete files: `sprite_analyzer.py`, `tests/benchmark/`, `tests/test_sprite_analyzer.py`, `tests/test_benchmark.py`

2. Update `index.py`:
   - Remove `analyze`, `extract`, `analyze-all` commands
   - Remove `sprite_analyzer` import and `anthropic` dependency
   - Update schema: drop `analysis_method` and `animation_type` columns
   - Integrate frame detection into `index` command

3. Update `web/api.py`:
   - Add inline `extract_frame()` function
   - Remove `animation_type` references

4. Update tests:
   - Remove tests for removed functionality
   - Add tests for txt-based and heuristic frame detection

5. Delete and rebuild database:
   - Delete `assets.db`
   - Run `uv run index.py index`

6. Clean up:
   - Remove `anthropic` from inline dependencies
