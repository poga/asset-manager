# Benchmark System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI benchmark that verifies AI-analyzed spritesheet frames against ground truth with pixel-perfect matching.

**Architecture:** Load ground truth from JSON manifests (regular grids + manual annotations), query database for AI results, compare frame-by-frame, report pass/fail per asset.

**Tech Stack:** Python 3.11+, sqlite3, pytest, standard library only

---

## Task 1: Create Directory Structure and Empty Manifests

**Files:**
- Create: `tests/benchmark/__init__.py`
- Create: `tests/benchmark/ground_truth/regular/manifest.json`
- Create: `tests/benchmark/ground_truth/irregular/manifest.json`

**Step 1: Create directories and files**

```bash
mkdir -p tests/benchmark/ground_truth/regular tests/benchmark/ground_truth/irregular
touch tests/benchmark/__init__.py
```

**Step 2: Create regular manifest with one test entry**

`tests/benchmark/ground_truth/regular/manifest.json`:
```json
{}
```

**Step 3: Create irregular manifest with empty object**

`tests/benchmark/ground_truth/irregular/manifest.json`:
```json
{}
```

**Step 4: Commit**

```bash
git add tests/benchmark/
git commit -m "chore: create benchmark directory structure"
```

---

## Task 2: Implement `load_manifests()`

**Files:**
- Create: `tests/benchmark/test_benchmark.py`
- Create: `tests/benchmark/benchmark.py`

**Step 1: Write failing test for load_manifests**

`tests/benchmark/test_benchmark.py`:
```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestLoadManifests -v
```

Expected: FAIL - cannot import `load_manifests`

**Step 3: Write minimal implementation**

`tests/benchmark/benchmark.py`:
```python
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
```

**Step 4: Run test to verify it passes**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestLoadManifests -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/benchmark/
git commit -m "feat(benchmark): implement load_manifests"
```

---

## Task 3: Implement `get_expected_frames()`

**Files:**
- Modify: `tests/benchmark/test_benchmark.py`
- Modify: `tests/benchmark/benchmark.py`

**Step 1: Write failing tests for get_expected_frames**

Add to `tests/benchmark/test_benchmark.py`:
```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestGetExpectedFrames -v
```

Expected: FAIL - cannot import `get_expected_frames`

**Step 3: Write minimal implementation**

Add to `tests/benchmark/benchmark.py`:
```python
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
```

**Step 4: Run test to verify it passes**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestGetExpectedFrames -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/benchmark/
git commit -m "feat(benchmark): implement get_expected_frames"
```

---

## Task 4: Implement `get_actual_frames()`

**Files:**
- Modify: `tests/benchmark/test_benchmark.py`
- Modify: `tests/benchmark/benchmark.py`

**Step 1: Write failing tests for get_actual_frames**

Add to `tests/benchmark/test_benchmark.py`:
```python
import sqlite3


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
```

**Step 2: Run test to verify it fails**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestGetActualFrames -v
```

Expected: FAIL - cannot import `get_actual_frames`

**Step 3: Write minimal implementation**

Add to `tests/benchmark/benchmark.py`:
```python
import sqlite3


def get_actual_frames(db_path: Path, asset_path: str) -> list[dict]:
    """Query sprite_frames table for AI-analyzed frames."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT sf.frame_index, sf.x, sf.y, sf.width, sf.height
        FROM sprite_frames sf
        JOIN assets a ON sf.asset_id = a.id
        WHERE a.path = ?
        ORDER BY sf.frame_index
    """, [asset_path])

    frames = []
    for row in cursor:
        frames.append({
            "index": row["frame_index"],
            "x": row["x"],
            "y": row["y"],
            "width": row["width"],
            "height": row["height"]
        })

    conn.close()
    return frames
```

**Step 4: Run test to verify it passes**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestGetActualFrames -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/benchmark/
git commit -m "feat(benchmark): implement get_actual_frames"
```

---

## Task 5: Implement `compare_frames()`

**Files:**
- Modify: `tests/benchmark/test_benchmark.py`
- Modify: `tests/benchmark/benchmark.py`

**Step 1: Write failing tests for compare_frames**

Add to `tests/benchmark/test_benchmark.py`:
```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestCompareFrames -v
```

Expected: FAIL - cannot import `compare_frames`

**Step 3: Write minimal implementation**

Add to `tests/benchmark/benchmark.py`:
```python
def compare_frames(expected: list[dict], actual: list[dict]) -> tuple[bool, list[str]]:
    """Compare frame lists. Returns (passed, error_messages)."""
    errors = []

    # Check frame count
    if len(expected) != len(actual):
        errors.append(f"Expected {len(expected)} frames, got {len(actual)}")
        return False, errors

    # Compare each frame
    for i, (exp, act) in enumerate(zip(expected, actual)):
        if (exp["x"] != act["x"] or exp["y"] != act["y"] or
            exp["width"] != act["width"] or exp["height"] != act["height"]):
            errors.append(
                f"Frame {i}: expected ({exp['x']}, {exp['y']}, {exp['width']}, {exp['height']}), "
                f"got ({act['x']}, {act['y']}, {act['width']}, {act['height']})"
            )

    return len(errors) == 0, errors
```

**Step 4: Run test to verify it passes**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestCompareFrames -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/benchmark/
git commit -m "feat(benchmark): implement compare_frames"
```

---

## Task 6: Implement `main()` CLI

**Files:**
- Modify: `tests/benchmark/test_benchmark.py`
- Modify: `tests/benchmark/benchmark.py`

**Step 1: Write failing tests for main**

Add to `tests/benchmark/test_benchmark.py`:
```python
import subprocess
import sys


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
```

**Step 2: Run test to verify it fails**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestMain -v
```

Expected: FAIL - cannot import `main`

**Step 3: Write minimal implementation**

Add to `tests/benchmark/benchmark.py`:
```python
def main(benchmark_dir: Path = None, db_path: Path = None) -> int:
    """Run benchmark and print results."""
    if benchmark_dir is None:
        benchmark_dir = Path(__file__).parent
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "assets.db"

    manifests = load_manifests(benchmark_dir)

    if not manifests:
        print("Benchmark Results")
        print("=================")
        print("No benchmarks configured.")
        print("\nSummary: 0/0 passed")
        return 0

    passed_count = 0
    failed_count = 0
    failed_assets = []

    print("Benchmark Results")
    print("=================")

    for asset_path, spec in manifests.items():
        expected = get_expected_frames(spec)
        actual = get_actual_frames(db_path, asset_path)
        passed, errors = compare_frames(expected, actual)

        if passed:
            print(f"PASS  {asset_path}")
            passed_count += 1
        else:
            print(f"FAIL  {asset_path}")
            for error in errors:
                print(f"      {error}")
            failed_count += 1
            failed_assets.append(asset_path)

    total = passed_count + failed_count
    print(f"\nSummary: {passed_count}/{total} passed", end="")
    if failed_count > 0:
        print(f" ({failed_count} failed)")
    else:
        print()

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

**Step 4: Run test to verify it passes**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py::TestMain -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tests/benchmark/
git commit -m "feat(benchmark): implement main CLI"
```

---

## Task 7: Add Sample Ground Truth Data

**Files:**
- Modify: `tests/benchmark/ground_truth/regular/manifest.json`

**Step 1: Find a spritesheet with known grid layout**

Query database to find an asset with frames:
```bash
sqlite3 assets.db "SELECT a.path, COUNT(sf.id) as frames FROM assets a JOIN sprite_frames sf ON a.id = sf.asset_id GROUP BY a.id LIMIT 5"
```

**Step 2: Add entry to regular manifest**

Based on database query results, add a known regular grid spritesheet to `tests/benchmark/ground_truth/regular/manifest.json`.

**Step 3: Run benchmark to verify**

```bash
uv run tests/benchmark/benchmark.py
```

**Step 4: Commit**

```bash
git add tests/benchmark/ground_truth/
git commit -m "chore(benchmark): add sample ground truth data"
```

---

## Task 8: Run All Tests

**Step 1: Run full test suite**

```bash
cd tests/benchmark && uv run pytest test_benchmark.py -v
```

Expected: All tests pass

**Step 2: Run benchmark against real database**

```bash
uv run tests/benchmark/benchmark.py
```

**Step 3: Final commit if any cleanup needed**

```bash
git status
```
