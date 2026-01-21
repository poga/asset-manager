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


class TestGetExpectedFrames:
    """Tests for get_expected_frames function."""

    def test_generates_frames_from_grid_spec(self):
        """get_expected_frames generates frames from cols/rows spec."""
        from benchmark import get_expected_frames

        spec = {"cols": 2, "rows": 2, "frame_width": 32, "frame_height": 32}
        result = get_expected_frames(spec)

        assert len(result) == 4
        assert result[0] == {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32}
        assert result[1] == {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}
        assert result[2] == {"index": 2, "x": 0, "y": 32, "width": 32, "height": 32}
        assert result[3] == {"index": 3, "x": 32, "y": 32, "width": 32, "height": 32}

    def test_generates_horizontal_strip(self):
        """get_expected_frames handles horizontal strip (1 row)."""
        from benchmark import get_expected_frames

        spec = {"cols": 4, "rows": 1, "frame_width": 16, "frame_height": 16}
        result = get_expected_frames(spec)

        assert len(result) == 4
        assert result[3] == {"index": 3, "x": 48, "y": 0, "width": 16, "height": 16}

    def test_returns_manual_frames_directly(self):
        """get_expected_frames returns frames list for irregular spec."""
        from benchmark import get_expected_frames

        frames = [
            {"index": 0, "x": 0, "y": 0, "width": 64, "height": 64},
            {"index": 1, "x": 64, "y": 0, "width": 48, "height": 64}
        ]
        spec = {"frame_count": 2, "frames": frames}
        result = get_expected_frames(spec)

        assert result == frames


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
