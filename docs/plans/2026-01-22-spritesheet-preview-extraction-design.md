# Spritesheet Preview Extraction Design

## Problem

Current `detect_first_sprite_bounds()` finds the bounding box of ALL non-transparent content in an image. For grid-based spritesheets (like Minifantasy assets), this returns bounds spanning multiple animation frames instead of a single representative frame.

## Goal

Extract just the first frame from grid-based spritesheets for use as a preview. The solution should be hands-off with no configuration required.

## Approach: Transparent Gap Detection

Detect grid layout by finding fully transparent columns and rows, then extract content bounds from the first frame cell.

### Algorithm

1. Load image, extract alpha channel
2. Find first fully transparent column (vertical frame boundary)
3. Find first fully transparent row (horizontal frame boundary)
4. First frame cell = (0, 0) to (first_gap_col, first_gap_row)
5. Within that cell, find content bounds using `getbbox()`
6. Return (x, y, width, height)

### Fallback Behavior

- No grid gaps found: treat whole image as single frame, return full content bounds
- First frame empty: return None

## Implementation

Replace `detect_first_sprite_bounds()` in `index.py`:

```python
def detect_first_sprite_bounds(path: Path) -> Optional[tuple[int, int, int, int]]:
    """
    Find the bounding box of the first frame in a spritesheet.

    Detects grid layout by finding transparent column/row gaps,
    then returns content bounds within the first frame cell.
    """
    try:
        with Image.open(path) as img:
            if img.mode != "RGBA":
                return None

            alpha = img.split()[3]
            width, height = img.size

            # Convert to bytes for fast column/row scanning
            alpha_data = alpha.tobytes()

            # Find first fully transparent column
            first_gap_col = width
            for x in range(width):
                if all(alpha_data[y * width + x] == 0 for y in range(height)):
                    first_gap_col = x
                    break

            # Find first fully transparent row
            first_gap_row = height
            for y in range(height):
                row_start = y * width
                if all(alpha_data[row_start + x] == 0 for x in range(width)):
                    first_gap_row = y
                    break

            # Crop to first frame, get content bounds
            first_frame = img.crop((0, 0, first_gap_col, first_gap_row))
            bbox = first_frame.split()[3].getbbox()

            if bbox is None:
                return None

            return (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        return None
```

## Performance

- Uses `tobytes()` to avoid per-pixel function call overhead
- `all()` short-circuits on first non-zero byte
- For 192x128 image with 32px frames: ~32 column checks before finding gap
- Negligible compared to file I/O
