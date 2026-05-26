# 3D Asset Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the asset manager to index, browse, search, and view 3D assets (.glb/.gltf) alongside existing 2D assets, with an interactive viewer and animation playback.

**Architecture:** Additive schema extension on the `assets` table (`asset_kind`, `rig`, `thumbnail_path`) + a new `asset_animations` table. New `model_indexer.py` module handles 3D parsing, sample-matching, and offscreen rendering. Web API gains `/api/asset/{id}/model` and `/api/asset/{id}/animations` endpoints. Frontend branches `AssetDetail.vue` on `asset_kind` to mount a `<model-viewer>`-based component.

**Tech Stack:** Python (FastAPI, SQLite, Pillow, trimesh), Vue 3, `@google/model-viewer` web component.

**Reference spec:** `docs/plans/2026-05-26-3d-asset-support-design.md`

---

## File Structure

**Create:**
- `model_indexer.py` — 3D file parsing, sample matching, thumbnail rendering, animation enumeration
- `test_model_indexer.py` — unit tests for model_indexer
- `tests/fixtures/3d/` — small glTF fixtures (Khronos BoxAnimated.glb + 2–3 KayKit copies)
- `web/frontend/src/components/ModelViewer.vue` — `<model-viewer>` wrapper with clip dropdown
- `web/frontend/public/model-viewer.min.js` — self-hosted Google model-viewer (~600KB, pinned v4)
- `web/frontend/src/components/__tests__/AssetDetail.spec.ts` — frontend branching test

**Modify:**
- `index.py` — extend SCHEMA + migration; scan glb/gltf; dispatch 3D path; pack-level linking pass
- `search.py` — projection includes `asset_kind`, `rig`, `thumbnail_path` (no logic change)
- `test_index.py` — 3D end-to-end tests
- `web/api.py` — serialize new fields; new endpoints; cart includes referenced files
- `web/test_api.py` — 3D API tests
- `web/frontend/src/components/AssetDetail.vue` — branch on `kind`
- `web/frontend/src/components/SearchBar.vue` — "Models only" toggle
- `web/frontend/index.html` — load model-viewer module
- `justfile` — add `test-model-indexer` target

---

## Task 1: Schema migration

**Files:**
- Modify: `index.py:69-130` (SCHEMA constant)
- Modify: `index.py` (add `migrate_schema` function, called from `get_db`)
- Modify: `test_index.py` (add migration tests)

- [ ] **Step 1: Write the failing tests**

Add to `test_index.py` near the existing fixture section:

```python
class TestSchemaMigration:
    def test_existing_db_gets_asset_kind_column(self, tmp_path):
        db_path = tmp_path / "test.db"
        # Create a "legacy" DB without the new columns
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE assets (
                id INTEGER PRIMARY KEY,
                pack_id INTEGER,
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                filetype TEXT NOT NULL,
                file_hash TEXT NOT NULL
            )
        """)
        conn.execute("INSERT INTO assets (pack_id, path, filename, filetype, file_hash) VALUES (1, 'a.png', 'a.png', 'png', 'h')")
        conn.commit()
        conn.close()

        conn = index.get_db(db_path)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(assets)")}
        assert "asset_kind" in cols
        assert "rig" in cols
        assert "thumbnail_path" in cols
        # Existing row defaulted correctly
        row = conn.execute("SELECT asset_kind FROM assets WHERE path='a.png'").fetchone()
        assert row["asset_kind"] == "image"

    def test_asset_animations_table_created(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = index.get_db(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "asset_animations" in tables

    def test_migration_is_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        index.get_db(db_path).close()
        # Second call must not raise
        conn = index.get_db(db_path)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(assets)")}
        assert "asset_kind" in cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py -v -k TestSchemaMigration`
Expected: 3 FAIL with `AssertionError: 'asset_kind' not in ...`

- [ ] **Step 3: Add new columns to SCHEMA and implement migration**

In `index.py`, extend the `SCHEMA` constant (after the existing `CREATE INDEX` lines):

```python
# Append inside the SCHEMA string, before the closing triple-quote:
CREATE TABLE IF NOT EXISTS asset_animations (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    clip_index INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(asset_id, clip_index)
);
CREATE INDEX IF NOT EXISTS idx_asset_animations_asset ON asset_animations(asset_id);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(asset_kind);
CREATE INDEX IF NOT EXISTS idx_assets_rig ON assets(rig);
```

Also extend the inline `assets` CREATE TABLE in `SCHEMA` to include the new columns (matters only for fresh DBs):

```sql
    category TEXT,
    asset_kind TEXT NOT NULL DEFAULT 'image',
    rig TEXT,
    thumbnail_path TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

Add a migration helper:

```python
def migrate_schema(conn: sqlite3.Connection) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(assets)")}
    if "asset_kind" not in existing:
        conn.execute("ALTER TABLE assets ADD COLUMN asset_kind TEXT NOT NULL DEFAULT 'image'")
    if "rig" not in existing:
        conn.execute("ALTER TABLE assets ADD COLUMN rig TEXT")
    if "thumbnail_path" not in existing:
        conn.execute("ALTER TABLE assets ADD COLUMN thumbnail_path TEXT")
    conn.commit()
```

Update `get_db` to call it after `executescript(SCHEMA)`:

```python
def get_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate_schema(conn)
    return conn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_index.py -v -k TestSchemaMigration`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add index.py test_index.py
git commit -m "feat: add 3D asset schema columns and migration"
```

---

## Task 2: glTF JSON parsing

**Files:**
- Create: `model_indexer.py`
- Create: `test_model_indexer.py`
- Create: `tests/fixtures/3d/`
- Modify: `justfile`

- [ ] **Step 1: Set up fixtures**

```bash
mkdir -p tests/fixtures/3d
# Khronos sample (small, known-good, animation present)
curl -L -o tests/fixtures/3d/BoxAnimated.glb \
  https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/BoxAnimated/glTF-Binary/BoxAnimated.glb
# KayKit copies (small): one character, one anim bundle, one .gltf+.bin
cp "/Users/poga/Documents/The Complete KayKit Collection v5/KayKit Adventurers 2.0/Characters/gltf/Knight.glb" tests/fixtures/3d/
cp "/Users/poga/Documents/The Complete KayKit Collection v5/KayKit Adventurers 2.0/Animations/gltf/Rig_Medium/Rig_Medium_General.glb" tests/fixtures/3d/
cp "/Users/poga/Documents/The Complete KayKit Collection v5/KayKit Adventurers 2.0/Assets/gltf/axe_1handed.gltf" tests/fixtures/3d/
cp "/Users/poga/Documents/The Complete KayKit Collection v5/KayKit Adventurers 2.0/Assets/gltf/axe_1handed.bin"  tests/fixtures/3d/
ls -la tests/fixtures/3d/
```

Expected: 5 files totaling well under 5MB.

- [ ] **Step 2: Write the failing test**

Create `test_model_indexer.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
#     "trimesh[easy]>=4.0",
# ]
# ///
"""Tests for model_indexer."""

from pathlib import Path

import pytest

import model_indexer

FIXTURES = Path(__file__).parent / "tests" / "fixtures" / "3d"


class TestLoadGltfJson:
    def test_loads_glb(self):
        data = model_indexer.load_gltf_json(FIXTURES / "BoxAnimated.glb")
        assert "asset" in data
        assert "animations" in data
        assert len(data["animations"]) >= 1

    def test_loads_gltf(self):
        data = model_indexer.load_gltf_json(FIXTURES / "axe_1handed.gltf")
        assert "asset" in data
        assert "buffers" in data

    def test_glb_magic_validated(self, tmp_path):
        bogus = tmp_path / "fake.glb"
        bogus.write_bytes(b"NOPE" + b"\x00" * 100)
        with pytest.raises(ValueError, match="not a glTF binary"):
            model_indexer.load_gltf_json(bogus)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --script test_model_indexer.py -v -k TestLoadGltfJson`
Expected: FAIL — `ModuleNotFoundError: No module named 'model_indexer'`

- [ ] **Step 4: Implement `load_gltf_json`**

Create `model_indexer.py`:

```python
"""3D asset indexing helpers: glTF/GLB parsing, sample matching, thumbnail rendering."""

import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


GLB_MAGIC = 0x46546C67  # 'glTF'
CHUNK_JSON = 0x4E4F534A  # 'JSON'


def load_gltf_json(path: Path) -> dict:
    """Read a .gltf or .glb file and return its JSON dictionary."""
    suffix = path.suffix.lower()
    if suffix == ".gltf":
        with open(path) as f:
            return json.load(f)
    if suffix == ".glb":
        with open(path, "rb") as f:
            magic, version, _ = struct.unpack("<III", f.read(12))
            if magic != GLB_MAGIC:
                raise ValueError(f"not a glTF binary: {path}")
            chunk_len, chunk_type = struct.unpack("<II", f.read(8))
            if chunk_type != CHUNK_JSON:
                raise ValueError(f"first chunk is not JSON: {path}")
            return json.loads(f.read(chunk_len).decode("utf-8"))
    raise ValueError(f"unsupported extension: {path}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --script test_model_indexer.py -v -k TestLoadGltfJson`
Expected: 3 PASS

- [ ] **Step 6: Add justfile target**

Append to `justfile`:

```
# Run model indexer tests only
test-model:
    uv run --script test_model_indexer.py
```

Update the main `test` target to include it:

```
test:
    uv run --script test_index.py
    uv run --script test_model_indexer.py
    uv run --script web/test_api.py
```

- [ ] **Step 7: Commit**

```bash
git add model_indexer.py test_model_indexer.py tests/fixtures/3d justfile
git commit -m "feat: add glTF/GLB JSON loader"
```

---

## Task 3: Extract ModelInfo (rig, animations, has_mesh, referenced_files)

**Files:**
- Modify: `model_indexer.py`
- Modify: `test_model_indexer.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_model_indexer.py`:

```python
class TestExtractModelInfo:
    def test_character_has_mesh_and_rig(self):
        info = model_indexer.extract_model_info(FIXTURES / "Knight.glb")
        assert info.has_mesh is True
        assert info.rig == "Rig_Medium"
        # Knight.glb itself ships with no embedded clips
        assert info.animations == []

    def test_animation_bundle_no_mesh(self):
        info = model_indexer.extract_model_info(FIXTURES / "Rig_Medium_General.glb")
        assert info.has_mesh is False
        assert info.rig == "Rig_Medium"
        assert len(info.animations) >= 1
        # Common KayKit clip naming — at least one Idle-ish entry
        assert any("idle" in n.lower() for n in info.animations)

    def test_gltf_lists_referenced_bin(self):
        info = model_indexer.extract_model_info(FIXTURES / "axe_1handed.gltf")
        assert "axe_1handed.bin" in info.referenced_files

    def test_glb_has_no_external_references(self):
        info = model_indexer.extract_model_info(FIXTURES / "Knight.glb")
        # .glb is self-contained; data-URIs and embedded chunks aren't external files
        assert info.referenced_files == []

    def test_rig_unknown_returns_none(self, tmp_path):
        # Build a tiny GLB with no rig hint in name
        src = FIXTURES / "BoxAnimated.glb"
        dst = tmp_path / "anonymous.glb"
        dst.write_bytes(src.read_bytes())
        info = model_indexer.extract_model_info(dst)
        assert info.rig is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_model_indexer.py -v -k TestExtractModelInfo`
Expected: 5 FAIL — `AttributeError: module ... has no attribute 'extract_model_info'`

- [ ] **Step 3: Implement `extract_model_info`**

Append to `model_indexer.py`:

```python
RIG_PATTERN = re.compile(r"Rig_(Large|Medium|Small)", re.IGNORECASE)


@dataclass
class ModelInfo:
    rig: Optional[str]
    animations: list[str]
    has_mesh: bool
    referenced_files: list[str]


def _infer_rig(path: Path, gltf: dict) -> Optional[str]:
    m = RIG_PATTERN.search(path.stem)
    if m:
        return f"Rig_{m.group(1).capitalize()}"
    for node in gltf.get("nodes") or []:
        name = node.get("name", "")
        m = RIG_PATTERN.search(name)
        if m:
            return f"Rig_{m.group(1).capitalize()}"
    return None


def _collect_referenced_files(gltf: dict) -> list[str]:
    out: list[str] = []
    for buf in gltf.get("buffers") or []:
        uri = buf.get("uri")
        if uri and not uri.startswith("data:"):
            out.append(uri)
    for img in gltf.get("images") or []:
        uri = img.get("uri")
        if uri and not uri.startswith("data:"):
            out.append(uri)
    return out


def extract_model_info(path: Path) -> ModelInfo:
    gltf = load_gltf_json(path)
    animations = [
        a.get("name", f"clip_{i}")
        for i, a in enumerate(gltf.get("animations") or [])
    ]
    has_mesh = bool(gltf.get("meshes"))
    return ModelInfo(
        rig=_infer_rig(path, gltf),
        animations=animations,
        has_mesh=has_mesh,
        referenced_files=_collect_referenced_files(gltf),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_model_indexer.py -v -k TestExtractModelInfo`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add model_indexer.py test_model_indexer.py
git commit -m "feat: extract rig, animations, and referenced files from glTF"
```

---

## Task 4: Canonical-format filter

**Files:**
- Modify: `model_indexer.py`
- Modify: `test_model_indexer.py`

- [ ] **Step 1: Write the failing test**

Append to `test_model_indexer.py`:

```python
class TestCanonicalFormatFilter:
    def test_glb_wins_over_gltf_same_stem(self, tmp_path):
        (tmp_path / "Knight.glb").write_bytes(b"glTF\x02\x00\x00\x00\x10\x00\x00\x00")
        (tmp_path / "Knight.gltf").write_text("{}")
        (tmp_path / "Knight.bin").write_bytes(b"")
        files = [tmp_path / "Knight.glb", tmp_path / "Knight.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert tmp_path / "Knight.glb" in kept
        assert tmp_path / "Knight.gltf" not in kept

    def test_keeps_gltf_when_no_glb_sibling(self, tmp_path):
        files = [tmp_path / "axe.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert files == kept

    def test_different_directories_independent(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir(); b.mkdir()
        files = [a / "Knight.glb", b / "Knight.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert set(kept) == set(files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_model_indexer.py -v -k TestCanonicalFormatFilter`
Expected: 3 FAIL — `AttributeError: ... 'filter_canonical_models'`

- [ ] **Step 3: Implement filter**

Append to `model_indexer.py`:

```python
def filter_canonical_models(paths: list[Path]) -> list[Path]:
    """Drop .gltf entries that have a sibling .glb with the same stem."""
    by_key: dict[tuple[Path, str], list[Path]] = {}
    for p in paths:
        by_key.setdefault((p.parent, p.stem), []).append(p)

    keep: list[Path] = []
    for group in by_key.values():
        if len(group) == 1:
            keep.append(group[0])
            continue
        glb = next((p for p in group if p.suffix.lower() == ".glb"), None)
        keep.append(glb if glb else group[0])
    return [p for p in paths if p in set(keep)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_model_indexer.py -v -k TestCanonicalFormatFilter`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add model_indexer.py test_model_indexer.py
git commit -m "feat: prefer .glb over .gltf when both exist"
```

---

## Task 5: Thumbnail resolution (sample match + render fallback)

**Files:**
- Modify: `model_indexer.py`
- Modify: `test_model_indexer.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_model_indexer.py`:

```python
class TestFindSampleThumbnail:
    def test_finds_sample_one_level_up(self, tmp_path):
        # pack/Characters/gltf/Knight.glb  ←  pack/Samples/knight.png
        pack = tmp_path / "pack"
        models = pack / "Characters" / "gltf"
        samples = pack / "Samples"
        models.mkdir(parents=True); samples.mkdir()
        model = models / "Knight.glb"; model.write_bytes(b"")
        sample = samples / "knight.png"; sample.write_bytes(b"\x89PNG")
        assert model_indexer.find_sample_thumbnail(model, pack) == sample

    def test_returns_none_when_no_match(self, tmp_path):
        pack = tmp_path / "pack"; (pack / "Samples").mkdir(parents=True)
        model = pack / "Mage.glb"; model.write_bytes(b"")
        assert model_indexer.find_sample_thumbnail(model, pack) is None


class TestRenderModelThumbnail:
    def test_renders_png(self, tmp_path):
        out = tmp_path / "thumb.png"
        ok = model_indexer.render_model_thumbnail(FIXTURES / "BoxAnimated.glb", out, size=128)
        if not ok:
            pytest.skip("trimesh offscreen render unavailable on this host")
        from PIL import Image
        with Image.open(out) as img:
            assert img.size == (128, 128)

    def test_returns_false_on_garbage(self, tmp_path):
        bad = tmp_path / "bad.glb"; bad.write_bytes(b"not a glb")
        ok = model_indexer.render_model_thumbnail(bad, tmp_path / "out.png", size=128)
        assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_model_indexer.py -v -k "TestFindSample or TestRender"`
Expected: FAIL on missing attributes.

- [ ] **Step 3: Implement sample lookup and rendering**

Append to `model_indexer.py`:

```python
def find_sample_thumbnail(model_path: Path, pack_root: Path) -> Optional[Path]:
    """Walk up from model_path toward pack_root, looking for Samples/<stem>.png (case-insensitive)."""
    target = model_path.stem.lower() + ".png"
    cur = model_path.parent
    while True:
        samples = cur / "Samples"
        if samples.is_dir():
            for f in samples.iterdir():
                if f.is_file() and f.name.lower() == target:
                    return f
        if cur == pack_root or cur.parent == cur:
            return None
        cur = cur.parent


def render_model_thumbnail(model_path: Path, out_path: Path, size: int = 256) -> bool:
    """Render an offscreen thumbnail. Returns True on success, False otherwise."""
    try:
        import trimesh  # heavy import; keep local
        scene = trimesh.load(str(model_path), force="scene")
        png = scene.save_image(resolution=(size, size), visible=False)
        if not png:
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_model_indexer.py -v -k "TestFindSample or TestRender"`
Expected: PASS (TestRenderModelThumbnail.test_renders_png may SKIP on macOS if pyglet's hidden window fails — that's the documented fallback path)

- [ ] **Step 5: Add `resolve_thumbnail` orchestrator + test**

Append to `model_indexer.py`:

```python
def resolve_thumbnail(
    model_path: Path,
    pack_root: Path,
    cache_dir: Path,
    cache_key: str,
) -> Optional[Path]:
    """Resolve a thumbnail for a 3D asset.

    1. Sample match in pack/Samples (returns its absolute path).
    2. Rendered fallback into cache_dir/<cache_key>.png.
    3. None.
    """
    sample = find_sample_thumbnail(model_path, pack_root)
    if sample:
        return sample
    rendered = cache_dir / f"{cache_key}.png"
    if rendered.exists():
        return rendered
    if render_model_thumbnail(model_path, rendered):
        return rendered
    return None
```

Append test:

```python
class TestResolveThumbnail:
    def test_prefers_sample_over_render(self, tmp_path):
        pack = tmp_path / "p"; (pack / "Samples").mkdir(parents=True)
        sample = pack / "Samples" / "box.png"; sample.write_bytes(b"\x89PNG")
        model = pack / "Box.glb"; model.write_bytes(b"")
        cache = tmp_path / "cache"
        result = model_indexer.resolve_thumbnail(model, pack, cache, "k")
        assert result == sample

    def test_uses_cache_when_present(self, tmp_path):
        pack = tmp_path / "p"; pack.mkdir()
        model = pack / "Box.glb"; model.write_bytes(b"")
        cache = tmp_path / "cache"; cache.mkdir()
        cached = cache / "k.png"; cached.write_bytes(b"\x89PNG")
        result = model_indexer.resolve_thumbnail(model, pack, cache, "k")
        assert result == cached
```

Run: `uv run --script test_model_indexer.py -v -k TestResolveThumbnail`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add model_indexer.py test_model_indexer.py
git commit -m "feat: resolve 3D thumbnails via sample lookup with render fallback"
```

---

## Task 6: Indexer integration — scan and dispatch 3D path

**Files:**
- Modify: `index.py:33-35` (extension constants) and `scan_assets`
- Modify: `index.py` indexing loop in `index()` command
- Modify: `test_index.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_index.py`:

```python
import shutil

FIXTURES_3D = Path(__file__).parent / "tests" / "fixtures" / "3d"


@pytest.fixture
def kaykit_like_pack(tmp_path):
    """Build a fake pack that mirrors KayKit Adventurers structure."""
    pack = tmp_path / "assets" / "KayKit Test 1.0"
    chars = pack / "Characters" / "gltf"
    anims = pack / "Animations" / "gltf" / "Rig_Medium"
    samples = pack / "Samples"
    chars.mkdir(parents=True)
    anims.mkdir(parents=True)
    samples.mkdir(parents=True)
    shutil.copy(FIXTURES_3D / "Knight.glb", chars / "Knight.glb")
    shutil.copy(FIXTURES_3D / "Rig_Medium_General.glb", anims / "Rig_Medium_General.glb")
    # Matching sample for Knight
    (samples / "knight.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return tmp_path / "assets"


class Test3DEndToEnd:
    def test_index_3d_pack_creates_correct_rows(self, kaykit_like_pack, tmp_path):
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        result = runner.invoke(app, ["index", str(kaykit_like_pack), "--db", str(db_path)])
        assert result.exit_code == 0, result.stdout

        conn = index.get_db(db_path)
        rows = conn.execute(
            "SELECT path, asset_kind, rig, thumbnail_path FROM assets ORDER BY path"
        ).fetchall()
        kinds = {r["path"]: r["asset_kind"] for r in rows}
        # Knight should be 'model'
        knight = next(r for r in rows if r["path"].endswith("Knight.glb"))
        assert knight["asset_kind"] == "model"
        assert knight["rig"] == "Rig_Medium"
        assert knight["thumbnail_path"] is not None
        # Animation bundle classified
        bundle = next(r for r in rows if r["path"].endswith("Rig_Medium_General.glb"))
        assert bundle["asset_kind"] == "animation_bundle"

    def test_animation_clips_populated(self, kaykit_like_pack, tmp_path):
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        runner.invoke(app, ["index", str(kaykit_like_pack), "--db", str(db_path)])
        conn = index.get_db(db_path)
        clips = conn.execute("""
            SELECT name FROM asset_animations aa
            JOIN assets a ON a.id = aa.asset_id
            WHERE a.path LIKE '%Rig_Medium_General.glb'
        """).fetchall()
        assert len(clips) >= 1

    def test_3d_assets_get_3d_tag(self, kaykit_like_pack, tmp_path):
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        runner.invoke(app, ["index", str(kaykit_like_pack), "--db", str(db_path)])
        conn = index.get_db(db_path)
        rows = conn.execute("""
            SELECT a.path FROM assets a
            JOIN asset_tags at ON at.asset_id = a.id
            JOIN tags t ON t.id = at.tag_id
            WHERE t.name = '3d'
        """).fetchall()
        assert len(rows) == 2  # Knight + bundle
```

Add the import at top of `test_index.py` if missing:
```python
import typer.testing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py -v -k Test3DEndToEnd`
Expected: 3 FAIL (3D files not scanned; rows have `asset_kind='image'` or are missing).

- [ ] **Step 3: Extend extension constants and `scan_assets`**

In `index.py`, near the existing `IMAGE_EXTENSIONS` constant:

```python
IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
ASEPRITE_EXTENSIONS = {".aseprite", ".ase"}
MODEL_EXTENSIONS = {".glb", ".gltf"}
```

Update `scan_assets` to include MODEL_EXTENSIONS and apply the canonical filter:

```python
def scan_assets(asset_root: Path) -> list[Path]:
    """Scan directory for image, Aseprite, and 3D model files."""
    import model_indexer
    image_assets: list[Path] = []
    model_assets: list[Path] = []
    for ext in IMAGE_EXTENSIONS | ASEPRITE_EXTENSIONS:
        image_assets.extend(asset_root.rglob(f"*{ext}"))
    for ext in MODEL_EXTENSIONS:
        model_assets.extend(asset_root.rglob(f"*{ext}"))
    model_assets = model_indexer.filter_canonical_models(sorted(model_assets))
    return sorted(image_assets + model_assets)
```

- [ ] **Step 4: Dispatch 3D path inside the indexing loop**

Inside `index()` (the typer command, around `index.py:600-680`), refactor the inner per-file block so that 3D files take a separate path. Add an import at the top of `index.py`:

```python
import model_indexer
```

Then inside the file loop, replace the `# Get image info` block with:

```python
suffix = file_path.suffix.lower()
is_model = suffix in MODEL_EXTENSIONS
is_image = suffix in IMAGE_EXTENSIONS

img_info: dict = {}
preview_bounds = None
asset_kind = "image"
rig: Optional[str] = None
thumbnail_path: Optional[str] = None
clip_names: list[str] = []

if is_image:
    img_info = get_image_info(file_path)
    preview_bounds = detect_first_sprite_bounds(file_path)
elif is_model:
    info = model_indexer.extract_model_info(file_path)
    asset_kind = "model" if info.has_mesh else "animation_bundle"
    rig = info.rig
    clip_names = info.animations
    pack_root = asset_root / pack_path if pack_name else asset_root
    cache_dir = db.parent / ".index" / "thumbs"
    thumb_key = hashlib.sha256(rel_path.encode()).hexdigest()[:16]
    thumb = model_indexer.resolve_thumbnail(file_path, pack_root, cache_dir, thumb_key)
    if thumb:
        # Make path relative to db.parent so the API can resolve it
        try:
            thumbnail_path = str(thumb.relative_to(db.parent))
        except ValueError:
            thumbnail_path = str(thumb)
elif suffix in ASEPRITE_EXTENSIONS:
    ase_info = aseprite_parser.parse_aseprite(file_path)
    img_info = {"width": ase_info["width"], "height": ase_info["height"]}
```

Then replace the `INSERT OR REPLACE INTO assets` to include the new columns:

```python
conn.execute(
    """INSERT OR REPLACE INTO assets
       (pack_id, path, filename, filetype, file_hash, file_size,
        width, height, preview_x, preview_y, preview_width, preview_height,
        category, asset_kind, rig, thumbnail_path, indexed_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    [
        pack_id, rel_path, file_path.name, suffix.lstrip("."),
        current_hash, file_path.stat().st_size,
        img_info.get("width"), img_info.get("height"),
        preview_bounds[0] if preview_bounds else None,
        preview_bounds[1] if preview_bounds else None,
        preview_bounds[2] if preview_bounds else None,
        preview_bounds[3] if preview_bounds else None,
        category, asset_kind, rig, thumbnail_path,
        datetime.now().isoformat(),
    ]
)
asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]
```

After tag extraction, inject the `'3d'` tag for 3D rows and skip color/phash:

```python
tags = extract_tags_from_path(file_path, asset_root)
add_tags(conn, asset_id, tags, "path")
if is_model:
    add_tags(conn, asset_id, ["3d"], "kind")
    # Persist animation clips
    for i, name in enumerate(clip_names):
        conn.execute(
            "INSERT OR REPLACE INTO asset_animations (asset_id, clip_index, name) VALUES (?, ?, ?)",
            [asset_id, i, name]
        )
elif is_image:
    colors = extract_colors(file_path)
    for hex_color, percentage in colors:
        conn.execute(
            "INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage) VALUES (?, ?, ?)",
            [asset_id, hex_color, percentage]
        )
    phash = compute_phash(file_path)
    if phash:
        conn.execute(
            "INSERT OR REPLACE INTO asset_phash (asset_id, phash) VALUES (?, ?)",
            [asset_id, phash]
        )
```

Also extend the inline-dep block at the top of `index.py` to include `trimesh`:

```python
# dependencies = [
#     "pillow>=10.0",
#     "imagehash>=4.3",
#     "rich>=13.0",
#     "typer>=0.9",
#     "python-dotenv>=1.0",
#     "trimesh[easy]>=4.0",
# ]
```

- [ ] **Step 5: Run tests**

Run: `uv run --script test_index.py -v -k Test3DEndToEnd`
Expected: 3 PASS. (If `test_animation_clips_populated` is empty, the bundle's `animations` came back empty — re-read fixture; KayKit `Rig_Medium_General.glb` ships clips.)

- [ ] **Step 6: Verify existing 2D tests still pass**

Run: `uv run --script test_index.py -v`
Expected: all PASS — existing 2D tests untouched.

- [ ] **Step 7: Commit**

```bash
git add index.py test_index.py
git commit -m "feat: index .glb/.gltf files with 3D-specific metadata"
```

---

## Task 7: Animation-bundle linking post-pass

**Files:**
- Modify: `index.py` (`index()` command, after the per-file loop)
- Modify: `test_index.py`

- [ ] **Step 1: Write the failing test**

Append to `test_index.py`:

```python
class TestAnimationBundleLinking:
    def test_character_linked_to_matching_bundle(self, kaykit_like_pack, tmp_path):
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        runner.invoke(app, ["index", str(kaykit_like_pack), "--db", str(db_path)])
        conn = index.get_db(db_path)
        rels = conn.execute("""
            SELECT a.path AS from_path, b.path AS to_path
            FROM asset_relations r
            JOIN assets a ON a.id = r.from_asset_id
            JOIN assets b ON b.id = r.to_asset_id
            WHERE r.relation_type = 'animation_for_rig'
        """).fetchall()
        assert any(
            r["from_path"].endswith("Knight.glb") and r["to_path"].endswith("Rig_Medium_General.glb")
            for r in rels
        )

    def test_no_cross_pack_links(self, tmp_path):
        # Two packs with the same rig should NOT link across packs
        a = tmp_path / "assets" / "PackA"
        b = tmp_path / "assets" / "PackB"
        (a / "Characters" / "gltf").mkdir(parents=True)
        (b / "Animations" / "gltf" / "Rig_Medium").mkdir(parents=True)
        shutil.copy(FIXTURES_3D / "Knight.glb", a / "Characters" / "gltf" / "Knight.glb")
        shutil.copy(FIXTURES_3D / "Rig_Medium_General.glb", b / "Animations" / "gltf" / "Rig_Medium" / "Rig_Medium_General.glb")
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        runner.invoke(app, ["index", str(tmp_path / "assets"), "--db", str(db_path)])
        conn = index.get_db(db_path)
        cross = conn.execute("""
            SELECT COUNT(*) AS n FROM asset_relations r
            JOIN assets a ON a.id = r.from_asset_id
            JOIN assets b ON b.id = r.to_asset_id
            WHERE a.pack_id != b.pack_id AND r.relation_type='animation_for_rig'
        """).fetchone()
        assert cross["n"] == 0
```

Confirm `asset_relations` table exists in current schema. If not, add it to `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS asset_relations (
    from_asset_id INTEGER REFERENCES assets(id),
    to_asset_id INTEGER REFERENCES assets(id),
    relation_type TEXT,
    PRIMARY KEY (from_asset_id, to_asset_id, relation_type)
);
```
(Check `index.py` first; the spec says it exists. If it doesn't, the schema addition is part of this task.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py -v -k TestAnimationBundleLinking`
Expected: 2 FAIL.

- [ ] **Step 3: Implement post-pass**

After the per-file loop in `index()` (right before "Update pack asset counts"):

```python
# Link character meshes to animation bundles within each pack
for pack_id_seen in set(packs_seen.values()):
    chars = conn.execute(
        "SELECT id, rig FROM assets WHERE pack_id = ? AND asset_kind='model' AND rig IS NOT NULL",
        [pack_id_seen]
    ).fetchall()
    bundles = conn.execute(
        "SELECT id, rig FROM assets WHERE pack_id = ? AND asset_kind='animation_bundle' AND rig IS NOT NULL",
        [pack_id_seen]
    ).fetchall()
    for c in chars:
        for b in bundles:
            if c["rig"] == b["rig"]:
                conn.execute(
                    "INSERT OR IGNORE INTO asset_relations (from_asset_id, to_asset_id, relation_type) VALUES (?, ?, 'animation_for_rig')",
                    [c["id"], b["id"]]
                )
conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_index.py -v -k TestAnimationBundleLinking`
Expected: 2 PASS.

- [ ] **Step 5: Run full test suite — no regressions**

Run: `just test`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add index.py test_index.py
git commit -m "feat: link characters to rig-compatible animation bundles per pack"
```

---

## Task 8: API serialization + kind filter

**Files:**
- Modify: `web/api.py:133-247` (search endpoint) and `web/api.py:307-360` (asset_detail)
- Modify: `web/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `web/test_api.py`:

```python
class Test3DSerialization:
    def test_search_returns_asset_kind(self, test_db):
        # Insert a 3D asset directly
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash, asset_kind, rig, thumbnail_path) "
            "VALUES ('Knight.glb', 'Knight.glb', 'glb', 'h1', 'model', 'Rig_Medium', 'Samples/knight.png')"
        )
        conn.commit(); conn.close()
        r = _client.get("/api/search")
        assert r.status_code == 200
        knight = next(a for a in r.json()["assets"] if a["filename"] == "Knight.glb")
        assert knight["kind"] == "model"
        assert knight["rig"] == "Rig_Medium"
        assert knight["thumbnail_path"] == "Samples/knight.png"

    def test_asset_detail_returns_asset_kind(self, test_db):
        conn = sqlite3.connect(test_db)
        cur = conn.execute(
            "INSERT INTO assets (path, filename, filetype, file_hash, asset_kind, rig) "
            "VALUES ('M.glb', 'M.glb', 'glb', 'h2', 'model', 'Rig_Large')"
        )
        aid = cur.lastrowid; conn.commit(); conn.close()
        r = _client.get(f"/api/asset/{aid}")
        body = r.json()
        assert body["kind"] == "model"
        assert body["rig"] == "Rig_Large"

    def test_search_kind_filter(self, test_db):
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO assets (path, filename, filetype, file_hash, asset_kind) VALUES ('a.png','a.png','png','h3','image')")
        conn.execute("INSERT INTO assets (path, filename, filetype, file_hash, asset_kind) VALUES ('b.glb','b.glb','glb','h4','model')")
        conn.commit(); conn.close()
        r = _client.get("/api/search?kind=model")
        kinds = {a["filename"]: a["kind"] for a in r.json()["assets"]}
        assert "b.glb" in kinds and "a.png" not in kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -v -k Test3DSerialization`
Expected: 3 FAIL — fields missing / filter ignored.

- [ ] **Step 3: Update search and detail endpoints**

In `web/api.py` `search` function:
- Add `kind: Optional[str] = None` to the params
- Add a condition:
  ```python
  if kind:
      conditions.append("a.asset_kind = ?")
      params.append(kind)
  ```
- Add columns to SELECT: `a.asset_kind, a.rig, a.thumbnail_path`
- Add to each returned asset dict: `"kind": row["asset_kind"], "rig": row["rig"], "thumbnail_path": row["thumbnail_path"]`

In `web/api.py` `asset_detail` function:
- Add to returned dict: `"kind": row["asset_kind"], "rig": row["rig"], "thumbnail_path": row["thumbnail_path"]`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py -v -k Test3DSerialization`
Expected: 3 PASS.

- [ ] **Step 5: Run full API tests**

Run: `uv run --script web/test_api.py -v`
Expected: all PASS — no regressions.

- [ ] **Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: serialize asset_kind/rig/thumbnail_path in API; add kind filter"
```

---

## Task 9: `/api/asset/{id}/model` endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `web/test_api.py`:

```python
class TestModelEndpoint:
    def test_serves_glb(self, test_db, tmp_path):
        # Set up an assets dir and copy a fixture
        from pathlib import Path
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        src = Path(__file__).parent.parent / "tests" / "fixtures" / "3d" / "Knight.glb"
        (assets_dir / "Knight.glb").write_bytes(src.read_bytes())
        api.set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('Knight.glb','Knight.glb','glb','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/asset/{aid}/model")
        assert r.status_code == 200
        assert r.headers["content-type"] == "model/gltf-binary"
        assert r.content[:4] == b"glTF"

    def test_serves_gltf_and_sibling_bin(self, test_db, tmp_path):
        from pathlib import Path
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        fx = Path(__file__).parent.parent / "tests" / "fixtures" / "3d"
        (assets_dir / "axe_1handed.gltf").write_bytes((fx / "axe_1handed.gltf").read_bytes())
        (assets_dir / "axe_1handed.bin").write_bytes((fx / "axe_1handed.bin").read_bytes())
        api.set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('axe_1handed.gltf','axe_1handed.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = _client.get(f"/api/asset/{aid}/model")
        assert r.status_code == 200
        assert r.headers["content-type"] == "model/gltf+json"
        r2 = _client.get(f"/api/asset/{aid}/model/axe_1handed.bin")
        assert r2.status_code == 200

    def test_rejects_path_traversal(self, test_db, tmp_path):
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        (assets_dir / "a.gltf").write_text("{}")
        api.set_assets_path(assets_dir)
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('a.gltf','a.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()
        r = _client.get(f"/api/asset/{aid}/model/../../../etc/passwd")
        assert r.status_code in (400, 404)
```

Also at the top of `web/test_api.py`, ensure `import web.api as api` (or however the existing tests import it — match the pattern).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -v -k TestModelEndpoint`
Expected: 3 FAIL — endpoint not defined.

- [ ] **Step 3: Implement the endpoint**

In `web/api.py`, after the `/api/image/{asset_id}` route:

```python
MODEL_CONTENT_TYPES = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
}


@app.get("/api/asset/{asset_id}/model")
def asset_model(asset_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT path, asset_kind FROM assets WHERE id = ?", [asset_id]
    ).fetchone()
    conn.close()
    if not row or row["asset_kind"] not in ("model", "animation_bundle"):
        raise HTTPException(404, "Model not found")
    p = (get_assets_path() / row["path"]).resolve()
    if not p.exists():
        raise HTTPException(404, "Model file missing")
    ct = MODEL_CONTENT_TYPES.get(p.suffix.lower(), "application/octet-stream")
    return FileResponse(p, media_type=ct)


@app.get("/api/asset/{asset_id}/model/{filename}")
def asset_model_sibling(asset_id: int, filename: str):
    if "/" in filename or filename.startswith(".."):
        raise HTTPException(400, "Invalid filename")
    conn = get_db()
    row = conn.execute(
        "SELECT path, asset_kind FROM assets WHERE id = ?", [asset_id]
    ).fetchone()
    conn.close()
    if not row or row["asset_kind"] not in ("model", "animation_bundle"):
        raise HTTPException(404)
    assets_dir = get_assets_path().resolve()
    asset_dir = (assets_dir / row["path"]).parent.resolve()
    target = (asset_dir / filename).resolve()
    # Ensure the resolved path stays inside the asset's directory
    if asset_dir not in target.parents and target.parent != asset_dir:
        raise HTTPException(400, "Path traversal")
    if not target.exists():
        raise HTTPException(404)
    return FileResponse(target)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py -v -k TestModelEndpoint`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: serve 3D model files and sibling assets via API"
```

---

## Task 10: `/api/asset/{id}/animations` endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `web/test_api.py`:

```python
class TestAnimationsEndpoint:
    def _setup(self, test_db):
        conn = sqlite3.connect(test_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,rig) VALUES ('Knight.glb','Knight.glb','glb','h1','model','Rig_Medium')")
        char_id = cur.lastrowid
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind,rig) VALUES ('Rig_Medium_General.glb','Rig_Medium_General.glb','glb','h2','animation_bundle','Rig_Medium')")
        bundle_id = cur.lastrowid
        conn.execute("INSERT INTO asset_animations (asset_id, clip_index, name) VALUES (?,0,'Idle')", [bundle_id])
        conn.execute("INSERT INTO asset_animations (asset_id, clip_index, name) VALUES (?,1,'Walk')", [bundle_id])
        conn.execute("INSERT INTO asset_relations (from_asset_id,to_asset_id,relation_type) VALUES (?,?,'animation_for_rig')", [char_id, bundle_id])
        conn.commit(); conn.close()
        return char_id, bundle_id

    def test_returns_clips_from_linked_bundles(self, test_db):
        char_id, bundle_id = self._setup(test_db)
        r = _client.get(f"/api/asset/{char_id}/animations")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["bundle_id"] == bundle_id
        assert body[0]["bundle_name"] == "Rig_Medium_General.glb"
        clip_names = [c["name"] for c in body[0]["clips"]]
        assert clip_names == ["Idle", "Walk"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_api.py -v -k TestAnimationsEndpoint`
Expected: FAIL — endpoint not defined.

- [ ] **Step 3: Implement endpoint**

In `web/api.py`:

```python
@app.get("/api/asset/{asset_id}/animations")
def asset_animations(asset_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close(); raise HTTPException(404)

    # Bundle list: the asset itself (for embedded clips), plus linked bundles
    bundle_ids: list[int] = []
    self_clips = conn.execute(
        "SELECT clip_index, name FROM asset_animations WHERE asset_id = ? ORDER BY clip_index",
        [asset_id]
    ).fetchall()
    if self_clips:
        bundle_ids.append(asset_id)
    linked = conn.execute(
        "SELECT to_asset_id FROM asset_relations WHERE from_asset_id = ? AND relation_type='animation_for_rig'",
        [asset_id]
    ).fetchall()
    bundle_ids.extend(r["to_asset_id"] for r in linked)

    out = []
    for bid in bundle_ids:
        b = conn.execute("SELECT filename FROM assets WHERE id = ?", [bid]).fetchone()
        clips = conn.execute(
            "SELECT clip_index, name FROM asset_animations WHERE asset_id = ? ORDER BY clip_index",
            [bid]
        ).fetchall()
        out.append({
            "bundle_id": bid,
            "bundle_name": b["filename"],
            "clips": [{"name": c["name"], "gltf_name": c["name"]} for c in clips],
        })
    conn.close()
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --script web/test_api.py -v -k TestAnimationsEndpoint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: animation clip listing endpoint for 3D characters"
```

---

## Task 11: Cart export includes referenced files for 3D

**Files:**
- Modify: `web/api.py` (`download_cart`)
- Modify: `web/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `web/test_api.py`:

```python
class TestCart3D:
    def test_cart_zip_includes_gltf_bin(self, test_client, sample_db, tmp_path):
        # sample_db should be reused; add a gltf asset to it
        from pathlib import Path
        fx = Path(__file__).parent.parent / "tests" / "fixtures" / "3d"
        assets_dir = tmp_path / "assets"; assets_dir.mkdir()
        (assets_dir / "axe.gltf").write_bytes((fx / "axe_1handed.gltf").read_bytes())
        (assets_dir / "axe.bin").write_bytes((fx / "axe_1handed.bin").read_bytes())
        api.set_assets_path(assets_dir)

        conn = sqlite3.connect(sample_db)
        cur = conn.execute("INSERT INTO assets (path,filename,filetype,file_hash,asset_kind) VALUES ('axe.gltf','axe.gltf','gltf','h','model')")
        aid = cur.lastrowid; conn.commit(); conn.close()

        r = test_client.post("/api/download-cart", json={"asset_ids": [aid]})
        assert r.status_code == 200
        import zipfile, io
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            assert "axe.gltf" in names
            assert "axe.bin" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_api.py -v -k TestCart3D`
Expected: FAIL — `axe.bin` not in zip.

- [ ] **Step 3: Extend `download_cart` to bundle siblings for 3D**

Add an import in `web/api.py`:
```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import model_indexer
```
(Match the existing aseprite_parser import pattern.)

Inside `download_cart`, fetch each row's `asset_kind` (extend the SELECT to include `a.asset_kind`). Then, in the zip-building loop:

```python
for row in rows:
    file_path = assets_dir / row["path"]
    if not file_path.exists():
        continue
    zf.write(file_path, row["filename"])
    if row["asset_kind"] in ("model", "animation_bundle") and file_path.suffix.lower() == ".gltf":
        try:
            info = model_indexer.extract_model_info(file_path)
            for ref in info.referenced_files:
                ref_path = (file_path.parent / ref).resolve()
                if ref_path.exists() and ref_path.is_relative_to(assets_dir.resolve()):
                    zf.write(ref_path, ref_path.name)
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py -v -k TestCart3D`
Expected: PASS.

Run full API tests: `uv run --script web/test_api.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: include .bin/texture siblings when exporting 3D assets in cart"
```

---

## Task 12: Frontend — self-hosted model-viewer + ModelViewer.vue

**Files:**
- Create: `web/frontend/public/model-viewer.min.js`
- Create: `web/frontend/src/components/ModelViewer.vue`
- Modify: `web/frontend/index.html`

- [ ] **Step 1: Self-host the model-viewer bundle**

```bash
mkdir -p web/frontend/public
curl -L -o web/frontend/public/model-viewer.min.js \
  https://unpkg.com/@google/model-viewer@4/dist/model-viewer.min.js
ls -la web/frontend/public/model-viewer.min.js
```
Expected: file present, ~500-700KB.

- [ ] **Step 2: Add module tag to `index.html`**

In `web/frontend/index.html`, inside `<head>`, add:

```html
<script type="module" src="/model-viewer.min.js"></script>
```

(Use the Vite `BASE_URL` path if the project sets one — check `vite.config.js`.)

- [ ] **Step 3: Create `ModelViewer.vue`**

Create `web/frontend/src/components/ModelViewer.vue`:

```vue
<template>
  <div class="model-viewer-wrap">
    <model-viewer
      ref="viewer"
      :src="modelUrl"
      camera-controls
      auto-rotate
      shadow-intensity="1"
      exposure="1"
      :animation-name="selectedClip?.name"
      :autoplay="isPlaying || undefined"
    />
    <div v-if="clips.length" class="anim-controls">
      <select v-model="selectedClip">
        <option :value="null">— no animation —</option>
        <option v-for="c in clips" :key="`${c.bundleId}:${c.name}`" :value="c">
          {{ c.bundleName }} › {{ c.name }}
        </option>
      </select>
      <button @click="isPlaying = !isPlaying">{{ isPlaying ? '⏸' : '▶' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  assetId: { type: Number, required: true },
  apiBase: { type: String, default: '/api' },
})

const modelUrl = computed(() => `${props.apiBase}/asset/${props.assetId}/model`)
const clips = ref([])
const selectedClip = ref(null)
const isPlaying = ref(false)

onMounted(async () => {
  const r = await fetch(`${props.apiBase}/asset/${props.assetId}/animations`)
  if (!r.ok) return
  const bundles = await r.json()
  clips.value = bundles.flatMap(b =>
    b.clips.map(c => ({ bundleId: b.bundle_id, bundleName: b.bundle_name, name: c.gltf_name }))
  )
})
</script>

<style scoped>
.model-viewer-wrap { display: flex; flex-direction: column; gap: 8px; }
model-viewer { width: 100%; height: 480px; background: #1a1a1a; border-radius: 8px; }
.anim-controls { display: flex; gap: 8px; align-items: center; }
</style>
```

- [ ] **Step 4: Manual smoke**

Browser at http://localhost:5173. The component isn't mounted anywhere yet (next task), but verify there are no console errors importing it. (Quick sanity check.)

- [ ] **Step 5: Commit**

```bash
git add web/frontend/public/model-viewer.min.js web/frontend/index.html web/frontend/src/components/ModelViewer.vue
git commit -m "feat: add ModelViewer.vue with self-hosted <model-viewer>"
```

---

## Task 13: Frontend — branch `AssetDetail.vue` on `kind`

**Files:**
- Modify: `web/frontend/src/components/AssetDetail.vue`
- Create: `web/frontend/src/components/__tests__/AssetDetail.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `web/frontend/src/components/__tests__/AssetDetail.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import AssetDetail from '../AssetDetail.vue'

const baseAsset = { id: 1, filename: 'x', path: 'x', tags: [], colors: [], width: 64, height: 64 }

describe('AssetDetail', () => {
  it('renders <img> for image asset', () => {
    const w = mount(AssetDetail, { props: { asset: { ...baseAsset, kind: 'image' } } })
    expect(w.find('img.asset-image').exists()).toBe(true)
    expect(w.find('model-viewer').exists()).toBe(false)
  })

  it('renders <model-viewer> for model asset', () => {
    const w = mount(AssetDetail, { props: { asset: { ...baseAsset, kind: 'model' } } })
    expect(w.find('model-viewer').exists()).toBe(true)
    expect(w.find('img.asset-image').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- AssetDetail.spec`
Expected: 2 FAIL — both branches render `<img>`.

- [ ] **Step 3: Update `AssetDetail.vue`**

In `web/frontend/src/components/AssetDetail.vue`, import the new component and branch on kind. Replace the existing `<img>` element with:

```vue
<ModelViewer v-if="asset.kind === 'model' || asset.kind === 'animation_bundle'"
             :asset-id="asset.id" :api-base="API_BASE" />
<img v-else
     :src="`${API_BASE}/image/${asset.id}`"
     :alt="asset.filename"
     class="asset-image"
     :style="{ minWidth: '300px', minHeight: '300px' }" />
```

Add the import to the `<script setup>` block (or `<script>` if the file uses options API — match the existing style):

```js
import ModelViewer from './ModelViewer.vue'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- AssetDetail.spec`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue web/frontend/src/components/__tests__/AssetDetail.spec.ts
git commit -m "feat: AssetDetail branches on asset_kind to render 3D viewer"
```

---

## Task 14: Frontend — "Models only" filter toggle

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`
- Modify: `web/frontend/src/App.vue` (filter state and query construction)

- [ ] **Step 1: Add the toggle**

In `SearchBar.vue`, add (near other filter chips):

```vue
<label class="filter-chip">
  <input type="checkbox" v-model="modelOnly" />
  Models only
</label>
```

Bind `modelOnly` so it emits the kind filter to the parent search handler. In `App.vue`, when constructing the search URL, append `&kind=model` if `modelOnly` is true. Match the existing pack/color filter wiring.

- [ ] **Step 2: Manual verification**

1. Open the frontend
2. Click "Models only" → grid shows only 3D assets
3. Click again → grid shows all

(No automated test — the existing search-filter chips are also tested manually; we follow that precedent.)

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue web/frontend/src/App.vue
git commit -m "feat: 'Models only' filter toggle in SearchBar"
```

---

## Task 15: End-to-end verification on real KayKit

**Files:** none (operational)

- [ ] **Step 1: Move KayKit into assets/**

```bash
cd /Users/poga/projects/asset-manager
mkdir -p assets
mv ~/Documents/The\ Complete\ KayKit\ Collection\ v5/KayKit\ * assets/
ls assets/ | grep KayKit | head -5
```
Expected: 23 KayKit sub-pack directories under `assets/`.

- [ ] **Step 2: Full reindex**

```bash
just reindex-assets
```
Expected: completes without error; rich progress bar shows hundreds of new 3D rows; pack previews regenerated.

- [ ] **Step 3: Spot-check DB**

```bash
sqlite3 assets.db "SELECT asset_kind, COUNT(*) FROM assets GROUP BY asset_kind"
```
Expected: `image`, `model`, and `animation_bundle` rows all present, with `model` count well over 1000.

```bash
sqlite3 assets.db "SELECT COUNT(*) FROM asset_relations WHERE relation_type='animation_for_rig'"
```
Expected: at least 1 (Adventurers links Knight/etc → Rig_Medium_General).

- [ ] **Step 4: Browser smoke — 3D**

(Assumes API on :8000 and frontend on :5173 already running — per project CLAUDE.md.)

1. Open http://localhost:5173
2. Search "knight" → grid shows Knight thumbnail (from Samples/knight.png)
3. Click the Knight card → detail view loads, `<model-viewer>` rotates the mesh, animation dropdown lists clips, click ▶ to play
4. Take a screenshot if anything looks off and stop

- [ ] **Step 5: Browser smoke — 2D regression**

1. Search for an existing 2D asset (e.g. "goblin")
2. Open it — `<img>` rendering still works
3. Add to cart, export — zip contains the 2D file

- [ ] **Step 6: Browser smoke — cart with 3D**

1. Add a `.gltf` asset (e.g. an axe) to cart
2. Export
3. Unzip → confirm both `.gltf` and its `.bin` are present

- [ ] **Step 7: Run full test suite one more time**

```bash
just test
```
Expected: all PASS.

- [ ] **Step 8: Commit any final fixes, then finish up**

Use `superpowers:finishing-a-development-branch` to decide how to land the work.

---

## Self-review notes

- **Spec coverage:** every section of the spec (schema, indexing pipeline, web API, frontend, pack setup, testing) maps to at least one task above.
- **Placeholder scan:** no TBD, no "implement appropriately." Every code step is concrete.
- **Type consistency:** `asset_kind` literals (`'image'`, `'model'`, `'animation_bundle'`) used identically across schema, indexer, API, and frontend. `rig` strings (`Rig_Medium`/`Rig_Large`/`Rig_Small`) match between extraction and linking.
- **Risk areas flagged in the plan:**
  - Task 5 `test_renders_png` may SKIP on macOS — that's intentional (fallback chain).
  - Task 6 assumes `asset_relations` exists in current schema; the task includes a check to add it if missing.
  - Task 12 `index.html` script path may need the Vite `BASE_URL` prefix; the task says to check `vite.config.js`.
