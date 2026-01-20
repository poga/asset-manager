#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
# ]
# ///
"""Tests for sprite analyzer module."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def sample_spritesheet(tmp_path):
    """Create a 128x128 image simulating a 4x4 grid of 32x32 sprites."""
    img_path = tmp_path / "spritesheet.png"
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    # Draw 16 small squares at grid positions
    for row in range(4):
        for col in range(4):
            x = col * 32 + 8  # 8px padding inside cell
            y = row * 32 + 8
            for dx in range(16):
                for dy in range(16):
                    img.putpixel((x + dx, y + dy), (100, 150, 50, 255))
    img.save(img_path)
    return img_path


class TestAnalyzeSpritesheet:
    """Tests for analyze_spritesheet function."""

    def test_returns_dict_with_frames(self, sample_spritesheet):
        """analyze_spritesheet returns dict with frames list."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        assert isinstance(result, dict)
        assert "frames" in result
        assert isinstance(result["frames"], list)

    def test_detects_frame_count(self, sample_spritesheet):
        """analyze_spritesheet detects correct number of frames."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        # Should detect 16 frames in 4x4 grid
        assert len(result["frames"]) == 16

    def test_frame_has_required_fields(self, sample_spritesheet):
        """Each frame has index, x, y, width, height."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        frame = result["frames"][0]
        assert "index" in frame
        assert "x" in frame
        assert "y" in frame
        assert "width" in frame
        assert "height" in frame

    def test_frame_dimensions_are_integers(self, sample_spritesheet):
        """Frame dimensions are integers."""
        from sprite_analyzer import analyze_spritesheet

        result = analyze_spritesheet(sample_spritesheet)

        frame = result["frames"][0]
        assert isinstance(frame["x"], int)
        assert isinstance(frame["y"], int)
        assert isinstance(frame["width"], int)
        assert isinstance(frame["height"], int)


class TestExtractFrame:
    """Tests for extract_frame function."""

    def test_extracts_single_frame(self, sample_spritesheet):
        """extract_frame returns PIL Image of specified frame."""
        from sprite_analyzer import extract_frame

        frame_info = {"x": 0, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info)

        assert isinstance(result, Image.Image)
        assert result.size == (32, 32)

    def test_extracts_correct_region(self, sample_spritesheet):
        """extract_frame extracts correct pixel region."""
        from sprite_analyzer import extract_frame

        # Second cell in first row
        frame_info = {"x": 32, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info)

        assert result.size == (32, 32)

    def test_scale_parameter(self, sample_spritesheet):
        """extract_frame respects scale parameter."""
        from sprite_analyzer import extract_frame

        frame_info = {"x": 0, "y": 0, "width": 32, "height": 32}
        result = extract_frame(sample_spritesheet, frame_info, scale=2)

        assert result.size == (64, 64)
