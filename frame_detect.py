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
