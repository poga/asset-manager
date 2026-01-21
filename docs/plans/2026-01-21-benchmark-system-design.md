# Benchmark System for AI Spritesheet Frame Analysis

## Purpose

Verify correctness of AI-analyzed spritesheet frames by comparing against known ground truth. Checks frame boundaries (x, y, width, height) and frame count.

## Requirements

- Pixel-perfect matching (0 tolerance)
- Pass/fail per spritesheet (strict)
- Uses existing assets from `assets/` folder
- Single CLI command to run

## File Structure

```
tests/benchmark/
├── benchmark.py              # CLI entry point
└── ground_truth/
    ├── regular/
    │   └── manifest.json     # Maps asset paths → grid specs
    └── irregular/
        └── manifest.json     # Maps asset paths → frame data
```

## Ground Truth Format

### Regular Grids (`regular/manifest.json`)

For spritesheets with uniform grid layout. Benchmark computes expected frames from spec.

```json
{
  "assets/creatures/goblin_walk.png": {
    "cols": 4,
    "rows": 1,
    "frame_width": 32,
    "frame_height": 32
  }
}
```

### Irregular Layouts (`irregular/manifest.json`)

For spritesheets with non-uniform frames. Manual annotation required.

```json
{
  "assets/effects/explosion.png": {
    "frame_count": 6,
    "frames": [
      {"index": 0, "x": 0, "y": 0, "width": 64, "height": 64},
      {"index": 1, "x": 64, "y": 0, "width": 48, "height": 64}
    ]
  }
}
```

Asset paths are relative to project root.

## CLI Interface

```bash
uv run tests/benchmark/benchmark.py
```

Runs all benchmarks (regular and irregular).

## Algorithm

1. Load both manifests
2. For each asset:
   - Query database for AI-analyzed frames (`sprite_frames` table)
   - Compute expected frames (from grid spec or manual annotation)
   - Compare frame count: must match exactly
   - Compare each frame: index, x, y, width, height must all match exactly
   - Record pass/fail
3. Print summary
4. Exit code 0 if all pass, 1 if any fail

## Output Format

```
Benchmark Results
=================
PASS  assets/creatures/goblin_walk.png
PASS  assets/creatures/skeleton_idle.png
FAIL  assets/effects/explosion.png
      Expected 6 frames, got 5
      Frame 2: expected (128, 0, 48, 64), got (130, 0, 46, 64)

Summary: 8/9 passed (1 failed)
```

## Implementation

### `tests/benchmark/benchmark.py`

```python
import json
import sqlite3
from pathlib import Path

def load_manifests() -> dict[str, dict]:
    """Load and merge regular + irregular manifests."""

def get_expected_frames(asset_path: str, spec: dict) -> list[dict]:
    """Compute expected frames from grid spec or return manual frames."""

def get_actual_frames(db_path: str, asset_path: str) -> list[dict]:
    """Query sprite_frames table for AI-analyzed frames."""

def compare_frames(expected: list, actual: list) -> tuple[bool, list[str]]:
    """Compare frame lists. Returns (passed, error_messages)."""

def main():
    """Run benchmark and print results."""
```

### Database Query

Joins `assets` and `sprite_frames` tables, matches by relative file path.

### Dependencies

Standard library only (json, sqlite3, pathlib). No new packages.
