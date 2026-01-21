#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
# ]
# ///
"""Tests for benchmark module."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema and sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE
        );
        CREATE TABLE sprite_frames (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER REFERENCES assets(id),
            frame_index INTEGER NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL
        );
    """)
    conn.execute("INSERT INTO assets (id, path) VALUES (1, 'assets/test.png')")
    conn.execute("INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (1, 0, 0, 0, 32, 32)")
    conn.execute("INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (1, 1, 32, 0, 32, 32)")
    conn.commit()
    conn.close()
    return db_path


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


class TestGetActualFrames:
    """Tests for get_actual_frames function."""

    def test_returns_frames_from_database(self, test_db):
        """get_actual_frames queries sprite_frames table."""
        from benchmark import get_actual_frames

        result = get_actual_frames(test_db, "assets/test.png")

        assert len(result) == 2
        assert result[0] == {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32}
        assert result[1] == {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}

    def test_returns_empty_for_missing_asset(self, test_db):
        """get_actual_frames returns empty list for non-existent asset."""
        from benchmark import get_actual_frames

        result = get_actual_frames(test_db, "assets/nonexistent.png")

        assert result == []

    def test_orders_by_frame_index(self, test_db):
        """get_actual_frames returns frames ordered by index."""
        from benchmark import get_actual_frames

        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO assets (id, path) VALUES (2, 'assets/unordered.png')")
        conn.execute("INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (2, 2, 64, 0, 32, 32)")
        conn.execute("INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (2, 0, 0, 0, 32, 32)")
        conn.execute("INSERT INTO sprite_frames (asset_id, frame_index, x, y, width, height) VALUES (2, 1, 32, 0, 32, 32)")
        conn.commit()
        conn.close()

        result = get_actual_frames(test_db, "assets/unordered.png")

        assert result[0]["index"] == 0
        assert result[1]["index"] == 1
        assert result[2]["index"] == 2


class TestMain:
    """Tests for main CLI function."""

    def test_exits_zero_when_all_pass(self, tmp_path, test_db):
        """main exits 0 when all benchmarks pass."""
        from benchmark import main

        # Set up ground truth that matches database
        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text(json.dumps({
            "assets/test.png": {"cols": 2, "rows": 1, "frame_width": 32, "frame_height": 32}
        }))
        (irregular_dir / "manifest.json").write_text("{}")

        exit_code = main(benchmark_dir=tmp_path, db_path=test_db)

        assert exit_code == 0

    def test_exits_one_when_any_fail(self, tmp_path, test_db):
        """main exits 1 when any benchmark fails."""
        from benchmark import main

        # Set up ground truth that does NOT match database
        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text(json.dumps({
            "assets/test.png": {"cols": 4, "rows": 1, "frame_width": 32, "frame_height": 32}
        }))
        (irregular_dir / "manifest.json").write_text("{}")

        exit_code = main(benchmark_dir=tmp_path, db_path=test_db)

        assert exit_code == 1

    def test_exits_zero_for_empty_manifests(self, tmp_path, test_db):
        """main exits 0 when no benchmarks to run."""
        from benchmark import main

        regular_dir = tmp_path / "ground_truth" / "regular"
        irregular_dir = tmp_path / "ground_truth" / "irregular"
        regular_dir.mkdir(parents=True)
        irregular_dir.mkdir(parents=True)
        (regular_dir / "manifest.json").write_text("{}")
        (irregular_dir / "manifest.json").write_text("{}")

        exit_code = main(benchmark_dir=tmp_path, db_path=test_db)

        assert exit_code == 0


class TestCompareFrames:
    """Tests for compare_frames function."""

    def test_passes_when_frames_match_exactly(self):
        """compare_frames returns True when frames match."""
        from benchmark import compare_frames

        expected = [
            {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32},
            {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}
        ]
        actual = [
            {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32},
            {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}
        ]

        passed, errors = compare_frames(expected, actual)

        assert passed is True
        assert errors == []

    def test_fails_when_frame_count_differs(self):
        """compare_frames fails when frame counts don't match."""
        from benchmark import compare_frames

        expected = [
            {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32},
            {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}
        ]
        actual = [
            {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32}
        ]

        passed, errors = compare_frames(expected, actual)

        assert passed is False
        assert "Expected 2 frames, got 1" in errors[0]

    def test_fails_when_coordinates_differ(self):
        """compare_frames fails when frame coordinates don't match."""
        from benchmark import compare_frames

        expected = [{"index": 0, "x": 0, "y": 0, "width": 32, "height": 32}]
        actual = [{"index": 0, "x": 1, "y": 0, "width": 32, "height": 32}]

        passed, errors = compare_frames(expected, actual)

        assert passed is False
        assert "Frame 0" in errors[0]

    def test_fails_when_dimensions_differ(self):
        """compare_frames fails when frame dimensions don't match."""
        from benchmark import compare_frames

        expected = [{"index": 0, "x": 0, "y": 0, "width": 32, "height": 32}]
        actual = [{"index": 0, "x": 0, "y": 0, "width": 31, "height": 32}]

        passed, errors = compare_frames(expected, actual)

        assert passed is False
        assert "Frame 0" in errors[0]

    def test_reports_all_mismatched_frames(self):
        """compare_frames reports all frame mismatches."""
        from benchmark import compare_frames

        expected = [
            {"index": 0, "x": 0, "y": 0, "width": 32, "height": 32},
            {"index": 1, "x": 32, "y": 0, "width": 32, "height": 32}
        ]
        actual = [
            {"index": 0, "x": 1, "y": 0, "width": 32, "height": 32},
            {"index": 1, "x": 33, "y": 0, "width": 32, "height": 32}
        ]

        passed, errors = compare_frames(expected, actual)

        assert passed is False
        assert len(errors) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
