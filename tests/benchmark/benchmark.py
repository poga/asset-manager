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
