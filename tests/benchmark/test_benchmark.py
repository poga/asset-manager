#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
# ]
# ///
"""Tests for benchmark module."""

import json
import tempfile
from pathlib import Path

import pytest


class TestLoadManifests:
    """Tests for load_manifests function."""

    def test_loads_empty_manifests(self, tmp_path):
        """load_manifests returns empty dict for empty manifests."""
        from benchmark import load_manifests

        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text("{}")
        (irregular_dir / "manifest.json").write_text("{}")

        result = load_manifests(tmp_path)

        assert result == {}

    def test_loads_regular_manifest(self, tmp_path):
        """load_manifests loads regular grid specs."""
        from benchmark import load_manifests

        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text(json.dumps({
            "assets/test.png": {"cols": 4, "rows": 1, "frame_width": 32, "frame_height": 32}
        }))
        (irregular_dir / "manifest.json").write_text("{}")

        result = load_manifests(tmp_path)

        assert "assets/test.png" in result
        assert result["assets/test.png"]["cols"] == 4

    def test_loads_irregular_manifest(self, tmp_path):
        """load_manifests loads irregular frame specs."""
        from benchmark import load_manifests

        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text("{}")
        (irregular_dir / "manifest.json").write_text(json.dumps({
            "assets/irregular.png": {
                "frame_count": 2,
                "frames": [
                    {"index": 0, "x": 0, "y": 0, "width": 64, "height": 64},
                    {"index": 1, "x": 64, "y": 0, "width": 48, "height": 64}
                ]
            }
        }))

        result = load_manifests(tmp_path)

        assert "assets/irregular.png" in result
        assert "frames" in result["assets/irregular.png"]

    def test_merges_both_manifests(self, tmp_path):
        """load_manifests merges regular and irregular."""
        from benchmark import load_manifests

        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text(json.dumps({
            "assets/regular.png": {"cols": 4, "rows": 1, "frame_width": 32, "frame_height": 32}
        }))
        (irregular_dir / "manifest.json").write_text(json.dumps({
            "assets/irregular.png": {"frames": []}
        }))

        result = load_manifests(tmp_path)

        assert "assets/regular.png" in result
        assert "assets/irregular.png" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
