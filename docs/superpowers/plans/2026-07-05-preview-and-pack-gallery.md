# Grid-Aware Sprite Previews + Themed Pack Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix fragment/too-small spritesheet previews by resolving each sheet's real frame grid, and replace sidebar-scrolling with a theme-grouped pack gallery home view.

**Architecture:** A new `frame_detect.py` module resolves a frame size per PNG (AnimationInfo txt → filename hint → transparent-grid-line inference → whole image) and crops the first occupied cell to its content; `index.py` consumes it and both the asset grid and pack montages heal on reindex. A new `pack_themes.py` assigns each pack a theme at index time (`packs.theme` column); `/api/filters` exposes `theme`/`is_3d`; a new `PackGallery.vue` becomes the home view and `PackList.vue` goes compact.

**Tech Stack:** Python 3.11+ (uv single-file scripts, Pillow, pytest), FastAPI, SQLite, Vue 3 + Vitest.

**Spec:** `docs/superpowers/specs/2026-07-05-preview-and-pack-gallery-design.md`

## Global Constraints

- Run all Python via `uv run` (test files are uv scripts: `uv run --script <file>`).
- Python test files live at repo root / `web/` as uv scripts, wired into `justfile` `test` target.
- NO MOCKS in Python tests: real files, real SQLite DBs (tmp dirs are fine). Frontend tests follow the repo's existing Vitest + fetch-stub conventions.
- Comments: max 1 line, 80 chars, explain why/what, no ticket refs.
- TDD every task: write the failing test, watch it fail, implement, watch it pass, commit.
- Do NOT start or stop the user's servers (ports 8000, 5173, 38471). Verification uses port 8010.
- Never push to main. Work stays on branch `worktree-preview-and-pack-gallery`.
- The worktree has no `assets/` or `assets.db`; the real ones are at `/Users/poga/projects/asset-manager/` (read the assets read-only; never modify the main checkout's DB).
- Alpha threshold for "transparent" is `<= 10` everywhere (ghost-pixel tolerance).

---

### Task 1: frame_detect.py — metadata parsers (AnimationInfo + filename hint)

**Files:**
- Create: `frame_detect.py`
- Create: `test_frame_detect.py`
- Modify: `justfile` (add test_frame_detect.py to `test` target)

**Interfaces:**
- Consumes: nothing (new module).
- Produces (later tasks rely on these exact names):
  - `ALPHA_THRESHOLD: int = 10`, `MIN_FRAME_EDGE: int = 8`
  - `animation_info_sizes(asset_dir: Path, stop_dir: Path) -> list[tuple[int, int]]`
  - `filename_hint(filename: str) -> Optional[tuple[int, int]]`

- [ ] **Step 1: Write the failing tests**

Create `test_frame_detect.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_frame_detect.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'frame_detect'`

- [ ] **Step 3: Write the implementation**

Create `frame_detect.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pillow>=10.0",
# ]
# ///
"""Frame-aware preview bounds for spritesheets.

Resolves a sheet's frame grid (pack metadata, filename hint, or
transparent-grid-line inference), then crops the first occupied frame
to its visible content. Replaces first-gap scanning, which mistook
transparent gaps inside a sprite for frame boundaries.
"""

import re
from pathlib import Path
from typing import Optional

from PIL import Image

# Pixels with alpha <= this are treated as transparent (ghost pixels).
ALPHA_THRESHOLD = 10
# Smallest believable frame edge in pixels.
MIN_FRAME_EDGE = 8

_INFO_NAME = re.compile(r"animation.*info", re.IGNORECASE)
_SIZE_DECL = re.compile(r"(\d{1,4})\s*[xX]\s*(\d{1,4})\s*px")
_NAME_HINT = re.compile(r"(\d{1,4})[xX](\d{1,4})")


def animation_info_sizes(asset_dir: Path, stop_dir: Path) -> list[tuple[int, int]]:
    """Frame sizes declared in AnimationInfo-style txt files.

    Searches asset_dir and its ancestors up to and including stop_dir;
    the nearest directory with any declaration wins.
    """
    d = asset_dir
    while True:
        sizes: list[tuple[int, int]] = []
        try:
            for txt in sorted(d.glob("*.txt")):
                if not _INFO_NAME.search(txt.name):
                    continue
                try:
                    text = txt.read_text(errors="ignore")
                except OSError:
                    continue
                for m in _SIZE_DECL.finditer(text):
                    sizes.append((int(m.group(1)), int(m.group(2))))
        except OSError:
            pass
        if sizes:
            return sizes
        if d == stop_dir or d == d.parent:
            return []
        d = d.parent


def filename_hint(filename: str) -> Optional[tuple[int, int]]:
    """Frame size embedded in the filename, e.g. 32x32Fire6.png."""
    m = _NAME_HINT.search(filename)
    return (int(m.group(1)), int(m.group(2))) if m else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_frame_detect.py`
Expected: PASS (10 tests)

- [ ] **Step 5: Add to justfile test target**

Modify the `test` recipe in `justfile`:

```make
# Run all tests
test:
    uv run --script test_index.py
    uv run --script test_frame_detect.py
    uv run --script test_model_indexer.py
    uv run --script web/test_api.py
```

- [ ] **Step 6: Run full suite and commit**

Run: `just test`
Expected: all suites pass.

```bash
git add frame_detect.py test_frame_detect.py justfile
git commit -m "feat: parse frame sizes from AnimationInfo files and filenames"
```

---

### Task 2: frame_detect.py — grid inference + preview bounds

**Files:**
- Modify: `frame_detect.py`
- Modify: `test_frame_detect.py`

**Interfaces:**
- Consumes: Task 1 parsers.
- Produces (Task 3 relies on these exact names):
  - `infer_grid(img: Image.Image) -> tuple[int, int]`
  - `resolve_frame_size(path: Path, img: Image.Image, stop_dir: Path) -> tuple[int, int]`
  - `detect_preview_bounds(path: Path, stop_dir: Optional[Path] = None) -> Optional[tuple[int, int, int, int]]`
    — returns `(x, y, width, height)` in sheet coordinates, or None for
    images without an alpha channel or with no visible content.

- [ ] **Step 1: Write the failing tests**

Append to `test_frame_detect.py` (above the `__main__` block):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_frame_detect.py`
Expected: new tests FAIL with `AttributeError: ... no attribute 'infer_grid'`; Task 1 tests still pass.

- [ ] **Step 3: Write the implementation**

Append to `frame_detect.py`:

```python
def _clear_flags(data: bytes, length: int, count: int) -> list[bool]:
    """flags[i] = line i (contiguous run of `length` bytes) is transparent."""
    return [
        max(data[i * length:(i + 1) * length]) <= ALPHA_THRESHOLD
        for i in range(count)
    ]


def _infer_edge(clear: list[bool], n: int) -> int:
    """Smallest divisor >= MIN_FRAME_EDGE of n whose grid lines are clear."""
    for d in range(MIN_FRAME_EDGE, n // 2 + 1):
        if n % d:
            continue
        if all(clear[k * d - 1] and clear[k * d] for k in range(1, n // d)):
            return d
    return n


def infer_grid(img: Image.Image) -> tuple[int, int]:
    """Infer (frame_w, frame_h) from periodic fully-transparent lines."""
    w, h = img.size
    alpha = img.getchannel("A")
    rows = _clear_flags(alpha.tobytes(), w, h)
    # transposed rows are the original columns
    cols = _clear_flags(alpha.transpose(Image.Transpose.TRANSPOSE).tobytes(), h, w)
    return _infer_edge(cols, w), _infer_edge(rows, h)


def _divides(size: tuple[int, int], sheet: tuple[int, int]) -> bool:
    fw, fh = size
    w, h = sheet
    return 0 < fw <= w and 0 < fh <= h and w % fw == 0 and h % fh == 0


def resolve_frame_size(
    path: Path, img: Image.Image, stop_dir: Path
) -> tuple[int, int]:
    """Frame size via AnimationInfo, filename hint, or grid inference."""
    sheet = img.size
    declared = [
        s for s in animation_info_sizes(path.parent, stop_dir) if _divides(s, sheet)
    ]
    if declared:
        return min(declared, key=lambda s: s[0] * s[1])
    hint = filename_hint(path.name)
    if hint and _divides(hint, sheet):
        return hint
    return infer_grid(img)


def detect_preview_bounds(
    path: Path, stop_dir: Optional[Path] = None
) -> Optional[tuple[int, int, int, int]]:
    """Visible-content crop of the first occupied frame of a sheet.

    Returns (x, y, w, h), or None when the image has no alpha channel
    or no visible content. Crops never cross frame boundaries.
    """
    try:
        with Image.open(path) as img:
            if img.mode != "RGBA":
                return None
            fw, fh = resolve_frame_size(path, img, stop_dir or path.parent)
            w, h = img.size
            for cy in range(0, h - fh + 1, fh):
                for cx in range(0, w - fw + 1, fw):
                    cell = img.crop((cx, cy, cx + fw, cy + fh))
                    mask = cell.getchannel("A").point(
                        lambda p: 255 if p > ALPHA_THRESHOLD else 0
                    )
                    bbox = mask.getbbox()
                    if bbox is None:
                        continue
                    x0 = max(0, bbox[0] - 1)
                    y0 = max(0, bbox[1] - 1)
                    x1 = min(fw, bbox[2] + 1)
                    y1 = min(fh, bbox[3] + 1)
                    return (cx + x0, cy + y0, x1 - x0, y1 - y0)
            return None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_frame_detect.py`
Expected: PASS (21 tests)

- [ ] **Step 5: Commit**

```bash
git add frame_detect.py test_frame_detect.py
git commit -m "feat: grid inference and frame-confined preview bounds"
```

---

### Task 3: Wire frame_detect into the indexer, retire the gap heuristic

**Files:**
- Modify: `index.py` (imports; `index_asset` ~line 482; main loop ~line 720; delete `detect_first_sprite_bounds` lines 218–282; force-clear generated pack previews ~line 832)
- Modify: `test_index.py` (delete `TestDetectFirstSpriteBounds`; add integration tests)

**Interfaces:**
- Consumes: `frame_detect.detect_preview_bounds(path, stop_dir)` from Task 2.
- Produces: `assets.preview_*` columns now hold frame-confined bounds; `index(..., force=True)` regenerates all `preview_generated = TRUE` pack previews.

- [ ] **Step 1: Write the failing tests**

In `test_index.py`, delete the entire `TestDetectFirstSpriteBounds` class (lines ~232–380 — its subject moves to `frame_detect`, covered by `test_frame_detect.py`). Add:

```python
class TestFrameAwareIndexing:
    """Indexing stores frame-confined preview bounds."""

    def _make_pack(self, temp_dir):
        pack = temp_dir / "TestPack_v1.0" / "Goblin"
        pack.mkdir(parents=True)
        (pack / "_AnimationInfo.txt").write_text(
            "*Frame size*\n- 32x32px: For all the animations.\n"
        )
        # 4 frames of 32x32; sprite at (4,4)-(27,27) in every frame
        img = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
        for f in range(4):
            for x in range(4, 28):
                for y in range(4, 28):
                    img.putpixel((f * 32 + x, y), (50, 120, 50, 255))
        img.save(pack / "GoblinIdle.png")
        return pack

    def test_bounds_use_declared_frame_size(self, temp_dir):
        self._make_pack(temp_dir)
        db_path = temp_dir / "t.db"
        index.index(temp_dir, db_path, force=False)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT preview_x, preview_y, preview_width, preview_height "
            "FROM assets WHERE filename = 'GoblinIdle.png'"
        ).fetchone()
        conn.close()
        # content bbox (4,4)-(28,28) padded 1px, confined to first cell
        assert (row["preview_x"], row["preview_y"]) == (3, 3)
        assert (row["preview_width"], row["preview_height"]) == (26, 26)

    def test_force_regenerates_generated_pack_previews(self, temp_dir):
        pack = self._make_pack(temp_dir)
        # montage generation needs at least 4 png assets in the pack
        for name in ["A.png", "B.png", "C.png"]:
            img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            for x in range(8, 24):
                for y in range(8, 24):
                    img.putpixel((x, y), (120, 50, 50, 255))
            img.save(pack / name)
        db_path = temp_dir / "t.db"
        index.index(temp_dir, db_path, force=False)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT preview_path, preview_generated FROM packs"
        ).fetchone()
        assert row["preview_path"] is not None
        assert row["preview_generated"]
        conn.close()
        # deleting the montage file proves force re-creates it
        montage = temp_dir / row["preview_path"].replace("previews/", ".index/previews/")
        montage.unlink()
        index.index(temp_dir, db_path, force=True)
        assert montage.exists()
```

Note: `index.index` is the typer command function, callable directly with `(asset_path, db, force)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py -k TestFrameAwareIndexing`
Expected: FAIL — bounds are `(4, 4, 120, 24)`-style (old whole-content heuristic), and the montage is not re-created on force.

- [ ] **Step 3: Implement the index.py changes**

1. Add import near the other local imports (`import aseprite_parser`):

```python
import frame_detect
```

2. Delete the whole `detect_first_sprite_bounds` function (lines 218–282).

3. In `index_asset` (~line 482), replace

```python
        preview_bounds = detect_first_sprite_bounds(file_path)
```

with

```python
        preview_bounds = frame_detect.detect_preview_bounds(file_path, pack_path)
```

4. In the `index()` main loop (~line 720), replace

```python
                preview_bounds = detect_first_sprite_bounds(file_path)
```

with

```python
                preview_bounds = frame_detect.detect_preview_bounds(file_path, pack_path)
```

(`pack_path` is in scope in both places from `detect_pack`; it equals `asset_root` for packless files, which is the correct search stop.)

5. In `index()`, just after `preview_dir = db.parent / ".index" / "previews"` (~line 832), add:

```python
    if force:
        # stale montages/convention copies were built from old bounds
        conn.execute("UPDATE packs SET preview_path = NULL WHERE preview_generated = TRUE")
        conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_index.py`
Expected: PASS, including both new tests; no references to `detect_first_sprite_bounds` remain (`grep -rn detect_first_sprite_bounds *.py web/` returns nothing).

- [ ] **Step 5: Run full suite and commit**

Run: `just test`
Expected: all pass.

```bash
git add index.py test_index.py
git commit -m "feat: index frame-confined preview bounds; force regenerates pack previews"
```

---

### Task 4: pack_themes.py — theme assignment

**Files:**
- Create: `pack_themes.py`
- Create: `test_pack_themes.py`
- Modify: `justfile` (add test_pack_themes.py to `test` target)

**Interfaces:**
- Consumes: nothing.
- Produces (Tasks 5/6 rely on these exact names):
  - `THEME_ORDER: list[str]` — display order, ends with "Other"
  - `assign_theme(pack_name: str) -> str` — always returns a THEME_ORDER member

- [ ] **Step 1: Write the failing tests**

Create `test_pack_themes.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
# ]
# ///
"""Tests for pack theme assignment."""

import sys

import pytest

import pack_themes


class TestAssignTheme:
    @pytest.mark.parametrize("name,theme", [
        ("Minifantasy_Creatures_v3.3_Commercial_Version", "Characters & Creatures"),
        ("Minifantasy_Ancient_Forests", "Nature"),
        ("Minifantasy_Dungeon_v2.3_Commercial_Version", "Dungeons & Caves"),
        ("Minifantasy_Towns_v3.0", "Towns & Buildings"),
        ("Minifantasy_Towns2_v1.0", "Towns & Buildings"),
        ("Minifantasy_Spell Effects_v1.0", "Magic & Effects"),
        ("Minifantasy_Spell_Effects_II_v1.0", "Magic & Effects"),
        ("Minifantasy_UI _Overhaul_v1.0", "UI"),
        ("Minifantasy_Scifi_SpaceDerelict_v1.0", "Sci-fi"),
        ("Minifantasy_Trains_v1.0", "Vehicles"),
        ("Minifantasy_Weapons_v3.0", "Items & Icons"),
        ("Minifantasy_RTS_Humans_v1.0 2", "Characters & Creatures"),
        ("KayKit Dungeon Remastered 1.1", "Dungeons & Caves"),
        ("KayKit Forest Nature Pack 1.0", "Nature"),
        ("KayKit Space Base Bits 1.0", "Sci-fi"),
        ("KayKit Mystery Monthly Series 4", "Other"),
        ("penusbmic_Sci-fi", "Sci-fi"),
        ("penusbmic_Dungeon", "Dungeons & Caves"),
    ])
    def test_known_packs(self, name, theme):
        assert pack_themes.assign_theme(name) == theme

    def test_version_bump_keeps_theme(self):
        assert pack_themes.assign_theme("Minifantasy_Creatures_v9.9") == \
            "Characters & Creatures"

    def test_token_fallback_for_unknown_pack(self):
        assert pack_themes.assign_theme("SuperVendor_Frozen_Forest_v2.0") == "Nature"

    def test_unmatchable_pack_is_other(self):
        assert pack_themes.assign_theme("Zzz_Unknowable_v1.0") == "Other"

    def test_every_current_pack_gets_a_named_theme(self):
        # every explicit mapping value must be a real theme
        for theme in pack_themes.PACK_THEMES.values():
            assert theme in pack_themes.THEME_ORDER


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_pack_themes.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'pack_themes'`

- [ ] **Step 3: Write the implementation**

Create `pack_themes.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Theme assignment for asset packs.

Names are normalized to a version-free slug so version bumps keep their
theme. Edit PACK_THEMES to recategorize; TOKEN_RULES only catches packs
with no explicit entry.
"""

import re

NATURE = "Nature"
DUNGEONS = "Dungeons & Caves"
TOWNS = "Towns & Buildings"
CHARACTERS = "Characters & Creatures"
MAGIC = "Magic & Effects"
ITEMS = "Items & Icons"
UI = "UI"
SCIFI = "Sci-fi"
VEHICLES = "Vehicles"
OTHER = "Other"

THEME_ORDER = [
    NATURE, DUNGEONS, TOWNS, CHARACTERS, MAGIC, ITEMS, UI, SCIFI, VEHICLES, OTHER,
]

# slug -> theme; slugs come from _slug() (lowercase letters only,
# vendor prefix and version/filler words removed)
PACK_THEMES = {
    # KayKit
    "adventurers": CHARACTERS,
    "block": ITEMS,
    "boardgame": ITEMS,
    "characteranimations": CHARACTERS,
    "citybuilder": TOWNS,
    "dungeonremastered": DUNGEONS,
    "fantasyweapons": ITEMS,
    "forestnature": NATURE,
    "furniture": ITEMS,
    "halloween": ITEMS,
    "holiday": ITEMS,
    "medievalhexagon": TOWNS,
    "mysterymonthlyseries": OTHER,
    "platformer": OTHER,
    "prototype": OTHER,
    "rpgtools": ITEMS,
    "resource": ITEMS,
    "restaurant": TOWNS,
    "skeletons": CHARACTERS,
    "spacebase": SCIFI,
    # Minifantasy
    "amyriadofnpcs": CHARACTERS,
    "ancientforests": NATURE,
    "builders": TOWNS,
    "castlesandstrongholds": TOWNS,
    "craftingandprofessions": ITEMS,
    "creatures": CHARACTERS,
    "cryptoftheforgotten": DUNGEONS,
    "darkbrotherhood": CHARACTERS,
    "deepcaves": DUNGEONS,
    "desolatedesert": NATURE,
    "dungeon": DUNGEONS,
    "dwarvenkingdom": DUNGEONS,
    "dwarvenworkshop": TOWNS,
    "elvenkingdom": TOWNS,
    "enchantedcompanions": CHARACTERS,
    "faedepths": DUNGEONS,
    "farm": TOWNS,
    "forestdwellers": CHARACTERS,
    "forgottenplains": NATURE,
    "gloomhollows": NATURE,
    "hellscape": DUNGEONS,
    "icywilderness": NATURE,
    "lostcivilization": DUNGEONS,
    "lostjungle": NATURE,
    "magicandsorcery": MAGIC,
    "magicweaponsandeffects": MAGIC,
    "maps": UI,
    "medievalcarnival": TOWNS,
    "medievalcity": TOWNS,
    "modernapocalypse": TOWNS,
    "moderntown": TOWNS,
    "monstercreatures": CHARACTERS,
    "mountainstronghold": TOWNS,
    "mounts": CHARACTERS,
    "necropolis": DUNGEONS,
    "nightmarerealm": MAGIC,
    "orckingdom": TOWNS,
    "persianpalace": TOWNS,
    "pharaohtomb": DUNGEONS,
    "plantsfoliage": NATURE,
    "portraitgenerator": UI,
    "rtshumans": CHARACTERS,
    "rtsorcs": CHARACTERS,
    "raidedvillage": TOWNS,
    "scifispacederelict": SCIFI,
    "sewers": DUNGEONS,
    "shipsanddocks": VEHICLES,
    "silentswamp": NATURE,
    "spelleffects": MAGIC,
    "spelleffectsii": MAGIC,
    "templeofthesnakegod": DUNGEONS,
    "templesandshrines": TOWNS,
    "tinyoverworld": NATURE,
    "tinyoverworldii": NATURE,
    "towers": TOWNS,
    "towns": TOWNS,
    "trains": VEHICLES,
    "trueheroes": CHARACTERS,
    "trueheroesii": CHARACTERS,
    "trueheroesiii": CHARACTERS,
    "trueheroesiv": CHARACTERS,
    "truevillainsi": CHARACTERS,
    "uioverhaul": UI,
    "undeadcreatures": CHARACTERS,
    "warplands": NATURE,
    "weapons": ITEMS,
    "wildwesttown": TOWNS,
    "wildlife": CHARACTERS,
    "wizardsacademy": TOWNS,
    # penusbmic
    "alchemist": CHARACTERS,
    "dark": CHARACTERS,
    "scifi": SCIFI,
    "stranded": SCIFI,
    "thrones": ITEMS,
    "fantasycards": UI,
}

# fallback for packs without an explicit entry; first match wins
TOKEN_RULES = [
    (r"forest|jungle|swamp|plain|desert|ic[ey]|winter|nature|plant|foliage|overworld|wild", NATURE),
    (r"dungeon|cave|crypt|sewer|tomb|necropolis|ruin|depth", DUNGEONS),
    (r"town|city|village|castle|stronghold|palace|temple|farm|house|build", TOWNS),
    (r"creature|character|hero|villain|npc|monster|undead|skeleton|companion|mount", CHARACTERS),
    (r"magic|spell|effect|sorcery|enchant", MAGIC),
    (r"weapon|item|icon|prop|furniture|resource|tool|craft", ITEMS),
    (r"\bui\b|interface|portrait|card|menu", UI),
    (r"sci-?fi|space|cyber|derelict", SCIFI),
    (r"train|ship|boat|vehicle|cart", VEHICLES),
]

_VERSION = re.compile(r"v?\.?\d+(\.\d+)*")
_FILLER = re.compile(r"commercial|version|pack|bits|assets|graphical")
_NON_ALPHA = re.compile(r"[^a-z]")


def _slug(name: str) -> str:
    s = name.lower()
    s = _VERSION.sub("", s)
    s = _FILLER.sub("", s)
    s = _NON_ALPHA.sub("", s)
    for prefix in ("minifantasy", "kaykit", "penusbmic"):
        s = s.removeprefix(prefix)
    return s


def assign_theme(pack_name: str) -> str:
    slug = _slug(pack_name)
    if slug in PACK_THEMES:
        return PACK_THEMES[slug]
    lower = pack_name.lower()
    for pattern, theme in TOKEN_RULES:
        if re.search(pattern, lower):
            return theme
    return OTHER
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_pack_themes.py`
Expected: PASS (22 tests)

- [ ] **Step 5: Add to justfile, run suite, commit**

Add `uv run --script test_pack_themes.py` after the test_frame_detect line in the `test` recipe.

Run: `just test`
Expected: all pass.

```bash
git add pack_themes.py test_pack_themes.py justfile
git commit -m "feat: theme assignment for asset packs"
```

---

### Task 5: packs.theme column + assignment during indexing

**Files:**
- Modify: `index.py` (SCHEMA packs table, `migrate_schema`, `index()` after asset-count update ~line 829)
- Modify: `test_index.py`

**Interfaces:**
- Consumes: `pack_themes.assign_theme` from Task 4.
- Produces: `packs.theme TEXT` populated on every `index` run (Task 6 reads it).

- [ ] **Step 1: Write the failing tests**

Add to `test_index.py`:

```python
class TestPackThemes:
    def test_index_assigns_theme_to_packs(self, temp_dir):
        pack = temp_dir / "Frozen_Forest_v1.0"
        pack.mkdir()
        img = Image.new("RGBA", (32, 32), (20, 90, 40, 255))
        img.save(pack / "tree.png")
        db_path = temp_dir / "t.db"
        index.index(temp_dir, db_path, force=False)
        conn = sqlite3.connect(db_path)
        theme = conn.execute("SELECT theme FROM packs").fetchone()[0]
        conn.close()
        assert theme == "Nature"

    def test_migrate_adds_theme_column_to_legacy_db(self, temp_dir):
        db_path = temp_dir / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE packs (id INTEGER PRIMARY KEY, name TEXT, path TEXT)")
        conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
        conn.commit()
        conn.close()
        conn = index.get_db(db_path)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(packs)")}
        conn.close()
        assert "theme" in cols
```

Note: the legacy-db test creates minimal `packs`/`assets` tables; `get_db` runs
`migrate_schema` (ALTERs add `theme`, `asset_kind`, `rig`, `thumbnail_path`)
then applies `SCHEMA`, whose `CREATE TABLE IF NOT EXISTS` leaves existing
tables alone. That is exactly the real legacy-DB path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py -k "TestPackThemes"`
Expected: FAIL — `theme` column missing / NULL.

- [ ] **Step 3: Implement**

1. In `SCHEMA`, add `theme TEXT,` to the packs table after `version TEXT,`:

```sql
CREATE TABLE IF NOT EXISTS packs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    version TEXT,
    theme TEXT,
    preview_path TEXT,
    preview_generated BOOLEAN DEFAULT FALSE,
    asset_count INTEGER DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

2. Replace `migrate_schema` with:

```python
def migrate_schema(conn: sqlite3.Connection) -> None:
    # Only migrate tables that already exist (legacy DBs)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "packs" in tables:
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(packs)")}
        if "theme" not in existing:
            conn.execute("ALTER TABLE packs ADD COLUMN theme TEXT")
    if "assets" in tables:
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(assets)")}
        if "asset_kind" not in existing:
            conn.execute("ALTER TABLE assets ADD COLUMN asset_kind TEXT NOT NULL DEFAULT 'image'")
        if "rig" not in existing:
            conn.execute("ALTER TABLE assets ADD COLUMN rig TEXT")
        if "thumbnail_path" not in existing:
            conn.execute("ALTER TABLE assets ADD COLUMN thumbnail_path TEXT")
    conn.commit()
```

3. Add `import pack_themes` next to `import frame_detect`.

4. In `index()`, right after the asset-count `UPDATE packs SET asset_count ...` commit (~line 829), add:

```python
    # Reassign themes every run so mapping edits apply without --force
    for row in conn.execute("SELECT id, name FROM packs").fetchall():
        conn.execute(
            "UPDATE packs SET theme = ? WHERE id = ?",
            [pack_themes.assign_theme(row["name"]), row["id"]],
        )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_index.py`
Expected: PASS.

- [ ] **Step 5: Run full suite and commit**

Run: `just test`

```bash
git add index.py test_index.py
git commit -m "feat: assign pack themes at index time"
```

---

### Task 6: /api/filters returns theme and is_3d per pack

**Files:**
- Modify: `web/api.py` (`filters()` ~line 432)
- Modify: `web/test_api.py` (fixture schema + new tests)

**Interfaces:**
- Consumes: `packs.theme` from Task 5.
- Produces JSON shape Task 8 consumes:
  `{"packs": [{"name": str, "count": int, "theme": str, "is_3d": bool}], ...}`
  — `theme` is never null (missing/legacy → `"Other"`).

- [ ] **Step 1: Write the failing tests**

In `web/test_api.py`, add `theme TEXT,` to the packs table in the `test_db` fixture's `executescript` (after `version TEXT,`). Then add:

```python
def test_filters_include_theme_and_is_3d(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO packs (id, name, path, theme, asset_count) "
        "VALUES (10, 'Forest3D', 'Forest3D', 'Nature', 2)"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (100, 10, 'Forest3D/a.glb', 'a.glb', 'glb', 'h1', 'model')"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (101, 10, 'Forest3D/b.glb', 'b.glb', 'glb', 'h2', 'model')"
    )
    conn.execute(
        "INSERT INTO packs (id, name, path, asset_count) "
        "VALUES (11, 'Sprites2D', 'Sprites2D', 1)"
    )
    conn.execute(
        "INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, asset_kind) "
        "VALUES (102, 11, 'Sprites2D/s.png', 's.png', 'png', 'h3', 'image')"
    )
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    packs = {p["name"]: p for p in resp.json()["packs"]}
    assert packs["Forest3D"]["theme"] == "Nature"
    assert packs["Forest3D"]["is_3d"] is True
    assert packs["Sprites2D"]["theme"] == "Other"  # NULL theme -> Other
    assert packs["Sprites2D"]["is_3d"] is False


def test_filters_tolerate_db_without_theme_column(tmp_path):
    # live DBs are only migrated by the indexer; the API must not 500
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE packs (id INTEGER PRIMARY KEY, name TEXT, path TEXT, asset_count INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT, asset_kind TEXT)")
    conn.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER)")
    conn.execute("INSERT INTO packs (name, path) VALUES ('Old', 'Old')")
    conn.commit()
    conn.close()

    import api
    api.set_db_path(db_path)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    assert resp.json()["packs"][0]["theme"] == "Other"
```

(Match the surrounding tests' style for setting/restoring the db path — if neighboring tests reset `api.set_db_path` afterwards, do the same.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -k "theme"`
Expected: FAIL — response packs lack `theme`/`is_3d` keys.

- [ ] **Step 3: Implement**

Replace the packs query in `filters()` (web/api.py ~line 437) with:

```python
    has_theme = any(
        r["name"] == "theme" for r in conn.execute("PRAGMA table_info(packs)")
    )
    theme_col = "p.theme" if has_theme else "NULL"
    packs = conn.execute(f"""
        SELECT p.name, p.asset_count AS count, {theme_col} AS theme,
               (SELECT COUNT(*) FROM assets a
                WHERE a.pack_id = p.id
                  AND a.asset_kind IN ('model', 'animation_bundle')) * 2
                 > p.asset_count AS is_3d
        FROM packs p
        ORDER BY p.name
    """).fetchall()
```

and the return entry with:

```python
        "packs": [
            {
                "name": p["name"],
                "count": p["count"],
                "theme": p["theme"] or "Other",
                "is_3d": bool(p["is_3d"]),
            }
            for p in packs
        ],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: PASS (all, including pre-existing filters tests).

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: expose pack theme and is_3d in /api/filters"
```

---

### Task 7: formatPackName util + compact sidebar rows

**Files:**
- Create: `web/frontend/src/utils/packName.js`
- Modify: `web/frontend/src/components/PackList.vue`
- Modify: `web/frontend/tests/PackList.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces: `formatPackName(name: string): string` in `src/utils/packName.js` (Task 8 imports it). PackList compact rows use class `pack-row`; expanded panel keeps `pack-card` grid. The search input is always rendered.

- [ ] **Step 1: Update tests (failing first)**

In `web/frontend/tests/PackList.test.js`:

- Replace `.pack-card` selectors with `.pack-row` in tests that mount without `panelState` (default `normal`).
- In the search test, remove the `await wrapper.find('.icon-btn').trigger('click')` line (input is always visible).
- Add:

```javascript
  it('search input is always visible', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    expect(wrapper.find('.pack-search').exists()).toBe(true)
  })

  it('renders card grid when expanded', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], panelState: 'expanded' }
    })
    expect(wrapper.findAll('.pack-card').length).toBe(3)
    expect(wrapper.findAll('.pack-row').length).toBe(0)
  })
```

Run: `cd web/frontend && npm test`
Expected: PackList tests FAIL (no `.pack-row` yet; search input behind toggle).

- [ ] **Step 2: Create the shared util**

Create `web/frontend/src/utils/packName.js` (moved verbatim from PackList.vue):

```javascript
export function formatPackName(name) {
  return name
    .replace(/^Minifantasy_/, '')
    .replace(/_v\.?\d+\.?\d*(_Commercial_Version)?$/, '')
    .replace(/_/g, ' ')
}
```

- [ ] **Step 3: Rework PackList.vue**

Template — remove the 🔍 toggle button from `.header-actions`, make the search input unconditional, and split normal/expanded rendering:

```vue
<template>
  <div class="pack-list">
    <div class="pack-header">
      <span class="pack-title">Packs<span v-if="selectedPacks.length > 0"> ({{ selectedPacks.length }} selected)</span></span>
      <div class="header-actions">
        <button
          class="icon-btn"
          data-testid="mode-toggle"
          @click="toggleMode"
          :title="selectionMode === 'single' ? 'Single select mode' : 'Multi select mode'"
        >
          <span v-if="selectionMode === 'single'">1️⃣</span>
          <span v-else>🔢</span>
        </button>
        <button class="icon-btn" @click="$emit('toggle-panel')" :title="panelState === 'normal' ? 'Expand panel' : 'Collapse panel'">
          <span v-if="panelState === 'normal'">➡️</span>
          <span v-else>⬅️</span>
        </button>
      </div>
    </div>

    <input
      type="text"
      class="pack-search"
      v-model="searchQuery"
      placeholder="Filter packs..."
    />

    <div class="pack-actions">
      <button v-if="selectionMode === 'multi'" class="action-btn" @click="selectAll" :disabled="allSelected">Select all</button>
      <button class="action-btn" @click="clearAll" :disabled="noneSelected">Clear</button>
    </div>

    <div v-if="panelState === 'expanded'" class="pack-grid expanded">
      <div
        v-for="pack in filteredPacks"
        :key="pack.name"
        class="pack-card"
        :class="{ selected: selectedPacks.includes(pack.name) }"
        @click="togglePack(pack.name)"
      >
        <div class="pack-preview-container">
          <img :src="getPreviewUrl(pack.name)" :alt="pack.name" class="pack-preview" loading="lazy" />
        </div>
        <div class="pack-info">
          <span class="pack-name">{{ formatPackName(pack.name) }}</span>
          <span class="pack-count">{{ pack.count }}</span>
        </div>
      </div>
    </div>

    <div v-else class="pack-rows">
      <div
        v-for="pack in filteredPacks"
        :key="pack.name"
        class="pack-row"
        :class="{ selected: selectedPacks.includes(pack.name) }"
        @click="togglePack(pack.name)"
      >
        <img :src="getPreviewUrl(pack.name)" :alt="pack.name" class="row-thumb" loading="lazy" />
        <span class="row-name">{{ formatPackName(pack.name) }}</span>
        <span class="row-count">{{ pack.count }}</span>
      </div>
    </div>
  </div>
</template>
```

Script changes: delete the local `formatPackName` function and the `showSearch` ref; add `import { formatPackName } from '../utils/packName.js'`.

Style additions (keep existing rules; `.pack-grid` styles remain for expanded):

```css
.pack-rows {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem;
}

.pack-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.375rem;
  border-radius: 4px;
  border-left: 3px solid transparent;
  cursor: pointer;
}

.pack-row:hover {
  background: var(--color-bg-elevated);
}

.pack-row.selected {
  border-left-color: var(--color-accent);
  background: var(--color-accent-light);
}

.row-thumb {
  width: 28px;
  height: 28px;
  object-fit: contain;
  background: #1a1a2e;
  border-radius: 3px;
  flex-shrink: 0;
}

.row-name {
  flex: 1;
  font-size: 0.8125rem;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-count {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: PASS (all suites — App.test.js etc. must stay green).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/utils/packName.js web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
git commit -m "feat: compact sidebar pack rows with always-visible filter"
```

---

### Task 8: PackGallery home view

**Files:**
- Create: `web/frontend/src/components/PackGallery.vue`
- Create: `web/frontend/tests/PackGallery.test.js`
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/tests/App.test.js` (only if runs reveal regressions)

**Interfaces:**
- Consumes: filters pack shape `{name, count, theme, is_3d}` (Task 6); `formatPackName` (Task 7).
- Produces: `PackGallery.vue` with prop `packs: Array`, emits `view-pack(name)`. Rendered in App when `isDefaultHomeView && !selectedAsset`.

- [ ] **Step 1: Write the failing tests**

Create `web/frontend/tests/PackGallery.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PackGallery from '../src/components/PackGallery.vue'

const packs = [
  { name: 'Minifantasy_Ancient_Forests', count: 120, theme: 'Nature', is_3d: false },
  { name: 'KayKit Forest Nature Pack 1.0', count: 80, theme: 'Nature', is_3d: true },
  { name: 'Minifantasy_Dungeon_v2.3', count: 300, theme: 'Dungeons & Caves', is_3d: false },
]

describe('PackGallery', () => {
  it('groups packs into theme sections in canonical order', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const titles = wrapper.findAll('.theme-title').map(t => t.text())
    expect(titles).toEqual(['Nature', 'Dungeons & Caves'])
    const natureCards = wrapper.findAll('.theme-section')[0].findAll('.gallery-card')
    expect(natureCards.length).toBe(2)
  })

  it('omits empty themes', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    expect(wrapper.text()).not.toContain('Sci-fi')
  })

  it('shows 3D badge only for 3d packs', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const badges = wrapper.findAll('.badge-3d')
    expect(badges.length).toBe(1)
  })

  it('emits view-pack with the raw pack name on card click', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    await wrapper.find('.gallery-card').trigger('click')
    expect(wrapper.emitted('view-pack')[0]).toEqual(['Minifantasy_Ancient_Forests'])
  })

  it('renders theme jump chips with counts', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const chips = wrapper.findAll('.chip').map(c => c.text())
    expect(chips[0]).toContain('Nature')
    expect(chips[0]).toContain('2')
  })
})
```

Run: `cd web/frontend && npm test`
Expected: FAIL — component doesn't exist.

- [ ] **Step 2: Implement PackGallery.vue**

Create `web/frontend/src/components/PackGallery.vue`:

```vue
<template>
  <div class="pack-gallery">
    <div class="theme-chips">
      <button v-for="t in activeThemes" :key="t" class="chip" @click="scrollTo(t)">
        {{ t }} <span class="chip-count">{{ grouped[t].length }}</span>
      </button>
    </div>

    <section
      v-for="t in activeThemes"
      :key="t"
      class="theme-section"
      :ref="el => { sectionEls[t] = el }"
    >
      <h2 class="theme-title">{{ t }}</h2>
      <div class="card-grid">
        <div
          v-for="pack in grouped[t]"
          :key="pack.name"
          class="gallery-card"
          @click="$emit('view-pack', pack.name)"
        >
          <div class="card-cover">
            <img
              v-if="!failedCovers[pack.name]"
              :src="previewUrl(pack.name)"
              :alt="pack.name"
              loading="lazy"
              @error="failedCovers[pack.name] = true"
            />
            <span v-else class="cover-placeholder">📦</span>
          </div>
          <div class="card-meta">
            <span class="card-name">{{ formatPackName(pack.name) }}</span>
            <span class="badge" :class="pack.is_3d ? 'badge-3d' : 'badge-2d'">
              {{ pack.is_3d ? '3D' : '2D' }}
            </span>
            <span class="card-count">{{ pack.count }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { formatPackName } from '../utils/packName.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

// mirrors pack_themes.THEME_ORDER on the backend
const THEME_ORDER = [
  'Nature', 'Dungeons & Caves', 'Towns & Buildings', 'Characters & Creatures',
  'Magic & Effects', 'Items & Icons', 'UI', 'Sci-fi', 'Vehicles', 'Other',
]

const props = defineProps({
  packs: { type: Array, required: true }
})

defineEmits(['view-pack'])

const sectionEls = reactive({})
const failedCovers = reactive({})

const grouped = computed(() => {
  const groups = {}
  for (const pack of props.packs) {
    const theme = THEME_ORDER.includes(pack.theme) ? pack.theme : 'Other'
    if (!groups[theme]) groups[theme] = []
    groups[theme].push(pack)
  }
  return groups
})

const activeThemes = computed(() =>
  THEME_ORDER.filter(t => grouped.value[t]?.length)
)

function previewUrl(packName) {
  return `${API_BASE}/pack-preview/${encodeURIComponent(packName)}`
}

function scrollTo(theme) {
  sectionEls[theme]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.pack-gallery {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.theme-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding-bottom: 1rem;
  position: sticky;
  top: 0;
  background: var(--color-bg-base);
  z-index: 1;
}

.chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.75rem;
  cursor: pointer;
}

.chip:hover {
  border-color: var(--color-accent);
}

.chip-count {
  color: var(--color-text-secondary);
  margin-left: 0.25rem;
}

.theme-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 1rem 0 0.5rem;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.gallery-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms;
}

.gallery-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-card);
}

.card-cover {
  height: 110px;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-cover img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.cover-placeholder {
  font-size: 2rem;
  opacity: 0.5;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem;
}

.card-name {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.25;
}

.badge {
  font-size: 0.625rem;
  font-weight: 700;
  padding: 0.0625rem 0.375rem;
  border-radius: 4px;
  flex-shrink: 0;
}

.badge-3d {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.badge-2d {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

.card-count {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 3: Integrate into App.vue**

1. Add import: `import PackGallery from './components/PackGallery.vue'`
2. In the template's `<main class="middle-panel">`, replace the `AssetGrid` block with:

```vue
        <PackGallery
          v-else-if="isDefaultHomeView"
          :packs="packList"
          @view-pack="viewPack"
        />

        <AssetGrid
          v-else
          :assets="assets"
          :cart-ids="cartIds"
          @select="selectAsset"
          @view-pack="viewPack"
          @add-to-cart="addToCart"
        />
```

3. Make the header title a home link. Replace `<h1>Asset Manager</h1>` with:

```vue
      <h1 class="home-link" @click="goHome">Asset Manager</h1>
```

Add to the script (near `viewPack`):

```javascript
function goHome() {
  skipNextPush = true
  selectedAsset.value = null
  selectedPacks.value = []
  isDefaultHomeView.value = true
  window.history.pushState({ route: 'home' }, '', buildUrl({ name: 'home' }))
}
```

Add style (in the global style block near `.app-header` rules):

```css
.home-link {
  cursor: pointer;
}
```

- [ ] **Step 4: Run the frontend suite**

Run: `cd web/frontend && npm test`
Expected: PackGallery tests PASS. If any App.test.js test fails because home no longer renders AssetGrid, fix that test by adding `'PackGallery'` to its stubs array and updating the assertion to expect the PackGallery stub on home view (e.g. `expect(wrapper.findComponent({ name: 'PackGallery' }).exists()).toBe(true)`); navigation tests (asset/similar/pack routes) must otherwise stay green with no source changes.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: themed pack gallery home view"
```

---

### Task 9: Real-data verification + rollout prep

**Files:**
- Modify: `.gitignore` (add `.index/` — the cache is currently untracked noise in git status)

**Interfaces:**
- Consumes: everything above.
- Produces: verified behavior against the real asset library; rollout note.

- [ ] **Step 1: gitignore the index cache**

Append `.index/` to `.gitignore` (under the "Asset index cache" comment, replacing nothing — `.assetindex/` is a stale entry, leave it).

- [ ] **Step 2: Verify real minifantasy bounds (subset, forced)**

```bash
MAIN=/Users/poga/projects/asset-manager
TMP="$CLAUDE_JOB_DIR/tmp"
mkdir -p "$TMP/verify-assets"
cp -R "$MAIN/assets/Minifantasy_Creatures_v3.3_Commercial_Version" "$TMP/verify-assets/"
uv run --script index.py index "$TMP/verify-assets" --db "$TMP/verify.db" --force
sqlite3 "$TMP/verify.db" "SELECT preview_x, preview_y, preview_width, preview_height FROM assets WHERE path LIKE '%Goblin/GoblinIdle.png';"
```

Expected: bounds inside the first 32×32 cell — `preview_x < 32`, `preview_y < 32`, `preview_x + preview_width <= 32`, `preview_height >= 6` (the old code returned width 7/height 6 fragments for other creatures; spot-check a couple more, e.g. `%Green_Mother_Slime%Idle%`: crop height must exceed 8 — the old cut-in-half value).

Also confirm the fragment epidemic is gone:

```bash
sqlite3 "$TMP/verify.db" "SELECT COUNT(*) FROM assets WHERE filetype='png' AND (preview_width < 6 AND preview_height < 6);"
```

Expected: a small number (only genuinely tiny sprites), not ~76% of PNGs.

- [ ] **Step 3: Verify the gallery against the real pack list**

```bash
# copy the live DB + previews (read-only source; copies are disposable)
cp "$MAIN/assets.db" ./assets.db
cp -R "$MAIN/.index" ./.index
# incremental run: hashes match so it only assigns themes (fast)
uv run --script index.py index "$MAIN/assets" --db ./assets.db
sqlite3 ./assets.db "SELECT theme, COUNT(*) FROM packs GROUP BY theme;"
```

Expected: all ~9 themes populated, `Other` small (only Mystery/Platformer/Prototype-style packs).

```bash
cd web/frontend && npm install && npm run build && cd ../..
uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --port 8010
```

Browse `http://localhost:8010/assets/` (claude-in-chrome; the API serves the built frontend):
- Home shows theme sections with pack cards, covers, 2D/3D badges, counts.
- Chips jump to sections; card click opens the pack's assets.
- Sidebar shows compact rows with an always-visible filter.
- Header click returns to the gallery.
Take a screenshot for the user. Kill the uvicorn process when done.

- [ ] **Step 4: Full test suites, commit, PR**

```bash
just test
cd web/frontend && npm test && cd ../..
git add .gitignore
git commit -m "chore: ignore .index cache"
git push -u origin worktree-preview-and-pack-gallery
gh pr create --draft --title "Grid-aware sprite previews + themed pack gallery" --body "$(cat <<'EOF'
## Summary
- Replace the first-transparent-gap crop heuristic with frame-grid-aware
  bounds (AnimationInfo txt → filename hint → grid inference → whole image).
  Fixes the fragment/too-small previews on ~76% of minifantasy spritesheets;
  pack montages heal too since they reuse the same bounds.
- Add a themed pack gallery home view (packs grouped Nature / Dungeons /
  Characters / …, 2D/3D badges, cover art) and a compact sidebar with an
  always-visible filter.

## Rollout
After merge, run `just reindex-assets` in the main checkout (forced reindex).
It recomputes all preview bounds, regenerates generated pack previews, and
assigns pack themes. Manually-set previews (`set-preview`) are preserved.
The running API/frontend pick the changes up automatically.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Notes

- Spec coverage: frame resolver layers (Tasks 1–2), indexer wiring + force regen (Task 3), theme mapping (Task 4), schema + assignment (Task 5), API (Task 6), compact sidebar (Task 7), gallery home (Task 8), real-data verification + rollout (Task 9). Error-handling spec points are embedded: parser/geometry failures fall through (Task 2 try/except + layer validation), missing covers render placeholders (Task 8), unknown packs → Other (Task 4).
- Old `TestDetectFirstSpriteBounds` tests are deliberately deleted, not ported: the gap heuristic they pin down is the bug being removed; `test_frame_detect.py` pins the replacement behavior, including the internal-transparency case with the corrected expectation.
- `detect_preview_bounds` returns None for non-RGBA images — same contract as the old function, so `SpritePreview.vue`'s full-image fallback path is unchanged.
- Deviation from the spec's testing note: unit tests build synthetic sheets in tmp dirs instead of committing real minifantasy PNGs to `tests/fixtures/` (the packs are commercially licensed; committing them to the GitHub remote would redistribute them). Real-file behavior is still verified in Task 9 against the main checkout's library.
