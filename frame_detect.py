#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pillow>=10.0",
# ]
# ///
"""Frame-aware preview bounds for spritesheets.

Resolves a sheet's frame grid (pack metadata, filename hint, or
transparent-grid-line inference), then crops the first occupied frame
to its visible content. Replaces first-gap scanning, which mistook
transparent gaps inside a sprite for frame boundaries.
"""

import re
from pathlib import Path
from typing import Optional

from PIL import Image

# Pixels with alpha <= this are treated as transparent (ghost pixels).
ALPHA_THRESHOLD = 10
# Smallest believable frame edge in pixels.
MIN_FRAME_EDGE = 8

_INFO_NAME = re.compile(r"animation.*info", re.IGNORECASE)
_SIZE_DECL = re.compile(r"(\d{1,4})\s*[xX]\s*(\d{1,4})\s*px")
_NAME_HINT = re.compile(r"(\d{1,4})[xX](\d{1,4})")


def animation_info_sizes(asset_dir: Path, stop_dir: Path) -> list[tuple[int, int]]:
    """Frame sizes declared in AnimationInfo-style txt files.

    Searches asset_dir and its ancestors up to and including stop_dir;
    the nearest directory with any declaration wins.
    """
    d = asset_dir
    while True:
        sizes: list[tuple[int, int]] = []
        try:
            for txt in sorted(d.glob("*.txt")):
                if not _INFO_NAME.search(txt.name):
                    continue
                try:
                    text = txt.read_text(errors="ignore")
                except OSError:
                    continue
                for m in _SIZE_DECL.finditer(text):
                    sizes.append((int(m.group(1)), int(m.group(2))))
        except OSError:
            pass
        if sizes:
            return sizes
        if d == stop_dir or d == d.parent:
            return []
        d = d.parent


def filename_hint(filename: str) -> Optional[tuple[int, int]]:
    """Frame size embedded in the filename, e.g. 32x32Fire6.png."""
    m = _NAME_HINT.search(filename)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _clear_flags(data: bytes, length: int, count: int) -> list[bool]:
    """flags[i] = line i (contiguous run of `length` bytes) is transparent."""
    return [
        max(data[i * length : (i + 1) * length]) <= ALPHA_THRESHOLD
        for i in range(count)
    ]


def _infer_edge(clear: list[bool], n: int) -> int:
    """Smallest divisor >= MIN_FRAME_EDGE of n whose grid lines are clear."""
    for d in range(MIN_FRAME_EDGE, n // 2 + 1):
        if n % d:
            continue
        if all(clear[k * d - 1] and clear[k * d] for k in range(1, n // d)):
            return d
    return n


def infer_grid(img: Image.Image) -> tuple[int, int]:
    """Infer (frame_w, frame_h) from periodic fully-transparent lines."""
    w, h = img.size
    alpha = img.getchannel("A")
    rows = _clear_flags(alpha.tobytes(), w, h)
    # transposed rows are the original columns
    cols = _clear_flags(
        alpha.transpose(Image.Transpose.TRANSPOSE).tobytes(), h, w
    )
    return _infer_edge(cols, w), _infer_edge(rows, h)


def _divides(size: tuple[int, int], sheet: tuple[int, int]) -> bool:
    fw, fh = size
    w, h = sheet
    return 0 < fw <= w and 0 < fh <= h and w % fw == 0 and h % fh == 0


def resolve_frame_size(
    path: Path, img: Image.Image, stop_dir: Path
) -> tuple[int, int]:
    """Frame size via AnimationInfo, filename hint, or grid inference."""
    sheet = img.size
    declared = [
        s for s in animation_info_sizes(path.parent, stop_dir) if _divides(s, sheet)
    ]
    if declared:
        return min(declared, key=lambda s: s[0] * s[1])
    hint = filename_hint(path.name)
    if hint and _divides(hint, sheet):
        return hint
    return infer_grid(img)


def detect_preview_bounds(
    path: Path, stop_dir: Optional[Path] = None
) -> Optional[tuple[int, int, int, int]]:
    """Visible-content crop of the first occupied frame of a sheet.

    Returns (x, y, w, h), or None when the image has no alpha channel
    or no visible content. Crops never cross frame boundaries.
    """
    try:
        with Image.open(path) as img:
            if img.mode != "RGBA":
                return None
            fw, fh = resolve_frame_size(path, img, stop_dir or path.parent)
            w, h = img.size
            for cy in range(0, h - fh + 1, fh):
                for cx in range(0, w - fw + 1, fw):
                    cell = img.crop((cx, cy, cx + fw, cy + fh))
                    mask = cell.getchannel("A").point(
                        lambda p: 255 if p > ALPHA_THRESHOLD else 0
                    )
                    bbox = mask.getbbox()
                    if bbox is None:
                        continue
                    x0 = max(0, bbox[0] - 1)
                    y0 = max(0, bbox[1] - 1)
                    x1 = min(fw, bbox[2] + 1)
                    y1 = min(fh, bbox[3] + 1)
                    return (cx + x0, cy + y0, x1 - x0, y1 - y0)
            return None
    except Exception:
        return None
