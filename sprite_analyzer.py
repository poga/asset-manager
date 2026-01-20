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
