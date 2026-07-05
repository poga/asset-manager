#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
# ]
# ///
"""Tests for frame-aware preview bounds detection."""

import sys
from pathlib import Path

import pytest
from PIL import Image

import frame_detect


class TestAnimationInfoSizes:
    def test_reads_frame_size_from_info_file(self, tmp_path):
        (tmp_path / "_AnimationInfo.txt").write_text(
            "*Frame size*\n\n- 32x32px: For all the animations.\n"
        )
        assert frame_detect.animation_info_sizes(tmp_path, tmp_path) == [(32, 32)]

    def test_matches_naming_variants(self, tmp_path):
        variants = [
            "Animation Info.txt",
            "Animation_Info.txt",
            "AnimationInfo.txt",
            "WorkingAnimationsInfo.txt",
        ]
        for i, name in enumerate(variants):
            d = tmp_path / f"v{i}"
            d.mkdir()
            (d / name).write_text("Frame size: 16x24px")
            assert frame_detect.animation_info_sizes(d, d) == [(16, 24)], name

    def test_collects_multiple_sizes_in_order(self, tmp_path):
        (tmp_path / "_AnimationInfo.txt").write_text(
            "- 32x32px: Idle and Walk.\n- 64x64px: Charged Attack.\n"
        )
        assert frame_detect.animation_info_sizes(tmp_path, tmp_path) == [
            (32, 32),
            (64, 64),
        ]

    def test_nearest_ancestor_wins_and_search_stops_at_stop_dir(self, tmp_path):
        pack = tmp_path / "pack"
        sub = pack / "a" / "b"
        sub.mkdir(parents=True)
        (pack / "_AnimationInfo.txt").write_text("8x8px")
        (pack / "a" / "AnimationInfo.txt").write_text("16x16px")
        # nearest ancestor with an info file wins
        assert frame_detect.animation_info_sizes(sub, pack) == [(16, 16)]
        # directories above stop_dir are never searched
        (tmp_path / "_AnimationInfo.txt").write_text("64x64px")
        assert frame_detect.animation_info_sizes(pack / "a", pack) == [(16, 16)]

    def test_no_info_returns_empty(self, tmp_path):
        assert frame_detect.animation_info_sizes(tmp_path, tmp_path) == []

    def test_ignores_non_matching_txt_files(self, tmp_path):
        (tmp_path / "CommercialLicense.txt").write_text("32x32px somewhere")
        assert frame_detect.animation_info_sizes(tmp_path, tmp_path) == []


class TestFilenameHint:
    def test_extracts_hint(self):
        assert frame_detect.filename_hint("32x32Fire6.png") == (32, 32)

    def test_case_insensitive_x(self):
        assert frame_detect.filename_hint("Tiles16X24.png") == (16, 24)

    def test_no_hint_returns_none(self):
        assert frame_detect.filename_hint("GoblinIdle.png") is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
