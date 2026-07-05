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


def make_sheet(tmp_path, name, sheet_size, blobs):
    """RGBA sheet with opaque rectangles; blobs are (x0, y0, x1, y1)."""
    img = Image.new("RGBA", sheet_size, (0, 0, 0, 0))
    px = img.load()
    for (x0, y0, x1, y1) in blobs:
        for x in range(x0, x1):
            for y in range(y0, y1):
                px[x, y] = (200, 50, 50, 255)
    path = tmp_path / name
    img.save(path)
    return path


class TestInferGrid:
    def test_recovers_frame_size_from_transparent_grid_lines(self, tmp_path):
        # 4x2 grid of 32x32 frames, an 8x8 sprite centered in every cell
        blobs = [
            (cx + 12, cy + 12, cx + 20, cy + 20)
            for cy in (0, 32)
            for cx in (0, 32, 64, 96)
        ]
        path = make_sheet(tmp_path, "sheet.png", (128, 64), blobs)
        with Image.open(path) as img:
            assert frame_detect.infer_grid(img) == (32, 32)

    def test_content_crossing_a_boundary_rejects_that_cell_size(self, tmp_path):
        # sprite spans x=10..40, so 16px and 32px boundaries are dirty
        path = make_sheet(tmp_path, "wide.png", (64, 32), [(10, 8, 40, 24)])
        with Image.open(path) as img:
            assert frame_detect.infer_grid(img) == (64, 32)


class TestDetectPreviewBounds:
    def test_crop_confined_to_first_frame_content(self, tmp_path):
        blobs = [
            (cx + 12, cy + 12, cx + 20, cy + 20)
            for cy in (0, 32)
            for cx in (0, 32, 64, 96)
        ]
        path = make_sheet(tmp_path, "sheet.png", (128, 64), blobs)
        assert frame_detect.detect_preview_bounds(path) == (11, 11, 10, 10)

    def test_internal_gap_does_not_truncate_single_image(self, tmp_path):
        # two blobs in one 32x32 image; left blob crosses x=16 so no
        # grid divides it — the crop must span both blobs
        path = make_sheet(
            tmp_path, "portrait.png", (32, 32), [(4, 4, 17, 28), (20, 4, 28, 28)]
        )
        x, y, w, h = frame_detect.detect_preview_bounds(path)
        assert x <= 4 and x + w >= 28

    def test_first_occupied_cell_wins_when_first_cell_is_empty(self, tmp_path):
        path = make_sheet(tmp_path, "sparse.png", (64, 32), [(44, 12, 52, 20)])
        x, y, w, h = frame_detect.detect_preview_bounds(path)
        assert x >= 32 and x + w <= 64

    def test_animation_info_beats_inference(self, tmp_path):
        # content fills cells edge-to-edge (no transparent grid lines),
        # but the pack metadata declares the frame size
        (tmp_path / "_AnimationInfo.txt").write_text("- 16x16px: all.\n")
        path = make_sheet(tmp_path, "packed.png", (64, 16), [(0, 0, 64, 16)])
        assert frame_detect.detect_preview_bounds(path, tmp_path) == (0, 0, 16, 16)

    def test_filename_hint_used_when_no_info_file(self, tmp_path):
        path = make_sheet(tmp_path, "16x16Fire.png", (64, 16), [(0, 0, 64, 16)])
        assert frame_detect.detect_preview_bounds(path) == (0, 0, 16, 16)

    def test_non_dividing_declared_size_falls_through_to_inference(self, tmp_path):
        (tmp_path / "_AnimationInfo.txt").write_text("48x48px\n")
        blobs = [(cx + 2, 2, cx + 14, 14) for cx in (0, 16, 32, 48)]
        path = make_sheet(tmp_path, "s.png", (64, 16), blobs)
        # 48 divides neither 64 nor 16; inference finds the 16x16 grid
        assert frame_detect.detect_preview_bounds(path, tmp_path) == (1, 1, 14, 14)

    def test_no_alpha_channel_returns_none(self, tmp_path):
        path = tmp_path / "rgb.png"
        Image.new("RGB", (32, 32), (10, 10, 10)).save(path)
        assert frame_detect.detect_preview_bounds(path) is None

    def test_fully_transparent_returns_none(self, tmp_path):
        path = tmp_path / "empty.png"
        Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(path)
        assert frame_detect.detect_preview_bounds(path) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
