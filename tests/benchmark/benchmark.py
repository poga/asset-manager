#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Benchmark system for verifying AI-analyzed spritesheet frames."""

import json
from pathlib import Path


def load_manifests(benchmark_dir: Path) -> dict[str, dict]:
    """Load and merge regular + irregular manifests."""
    regular_path = benchmark_dir / "ground_truth" / "regular" / "manifest.json"
    irregular_path = benchmark_dir / "ground_truth" / "irregular" / "manifest.json"

    result = {}

    if regular_path.exists():
        with open(regular_path) as f:
            result.update(json.load(f))

    if irregular_path.exists():
        with open(irregular_path) as f:
            result.update(json.load(f))

    return result


def get_expected_frames(spec: dict) -> list[dict]:
    """Compute expected frames from grid spec or return manual frames."""
    # If spec has "frames" key, it's irregular - return directly
    if "frames" in spec:
        return spec["frames"]

    # Otherwise, generate from grid spec
    cols = spec["cols"]
    rows = spec["rows"]
    frame_width = spec["frame_width"]
    frame_height = spec["frame_height"]

    frames = []
    index = 0
    for row in range(rows):
        for col in range(cols):
            frames.append({
                "index": index,
                "x": col * frame_width,
                "y": row * frame_height,
                "width": frame_width,
                "height": frame_height
            })
            index += 1

    return frames
