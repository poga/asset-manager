# Font + Anyfile Asset Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `font` and `file` (catch-all) asset kinds — indexed, browsable, downloadable — on top of a kind-handler registry refactor of the indexing pipeline.

**Architecture:** New `asset_kinds.py` module holds an ordered registry of kind handlers (aseprite, image, model, font, catch-all file); `index.py`'s scan + per-suffix dispatch delegate to it. API gains a raw-file endpoint and a per-pack `section` field; frontend gains file cards, a font type tester, and Fonts/Files sidebar sections.

**Tech Stack:** Python 3.11 + uv inline-deps scripts, SQLite, FastAPI, Pillow, Vue 3 + Vitest.

**Spec:** `docs/superpowers/specs/2026-07-11-font-anyfile-assets-design.md`

## Global Constraints

- Run everything with `uv run` (never bare `python`). Test files are uv scripts: `uv run --script test_index.py`, `uv run --script web/test_api.py`. Frontend: `cd web/frontend && npm test`.
- NO MOCKS. Real files, real CLI (`typer.testing.CliRunner`), real `TestClient`, real temp SQLite. The only permitted monkeypatching is environmental absence (existing Blender pattern).
- Comments: max 1 line, 80 chars, explain why/what, no ticket/branch references.
- Do NOT start the dev servers (API 8000 / frontend 5173 are already running).
- **No schema change.** `asset_kind` gains values `'font'` and `'file'` only.
- `index_asset()` in index.py is legacy but referenced by tests (test_index.py:719-818) — do NOT delete or modify it.
- `index.IMAGE_EXTENSIONS` / `ASEPRITE_EXTENSIONS` / `MODEL_EXTENSIONS` are referenced by tests — they must remain importable from `index` (re-export from `asset_kinds`).
- Commit after every task on the current branch (`worktree-font-anyfile-assets`). Never commit to main.

## File Structure

- Create: `asset_kinds.py` — kind handlers + registry + font specimen renderer (single new module; handlers are ~10 lines each).
- Create: `tests/fixtures/fonts/PressStart2P-Regular.ttf` + `OFL.txt` — real font fixture.
- Create: `web/frontend/src/components/FontTester.vue`, `web/frontend/src/utils/fileSize.js`.
- Modify: `index.py` (scan + dispatch + montage), `web/api.py` (file endpoint, image branch, search, filters), `web/frontend/src/components/{AssetGrid,AssetDetail,PackGallery}.vue`.
- Test: `test_index.py`, `web/test_api.py`, `web/frontend/tests/*`.

---

### Task 1: Kind-handler registry (behavior-preserving refactor)

**Files:**
- Create: `asset_kinds.py`
- Modify: `index.py` (lines 41-44 extension sets, 511-523 `scan_assets`, 665-755 dispatch inside `index()`)
- Test: `test_index.py` (new `TestKindRegistry` class; entire existing suite is the regression net)

**Interfaces:**
- Consumes: `aseprite_parser.parse_aseprite`, `frame_detect.detect_preview_bounds`, `model_indexer.extract_model_info/resolve_thumbnail/filter_canonical_models` (all existing).
- Produces: `asset_kinds.find_handler(path) -> handler | None`; `asset_kinds.IndexContext(asset_root, pack_root, db_root, rel_path)`; `asset_kinds.AssetMeta` with fields `asset_kind, width, height, preview_bounds, rig, thumbnail_path, extra_tags, clip_names, wants_colors`; classes `AsepriteHandler, ImageHandler, ModelHandler`; module constants `IMAGE_EXTENSIONS, ASEPRITE_EXTENSIONS, MODEL_EXTENSIONS`; `HANDLERS` list. Tasks 2-3 append handlers to `HANDLERS`.

- [ ] **Step 1: Write the failing test**

Append to `test_index.py` (top-level, after the existing imports add `import asset_kinds`):

```python
class TestKindRegistry:
    def test_handlers_match_by_extension(self):
        assert isinstance(asset_kinds.find_handler(Path("a/b.png")), asset_kinds.ImageHandler)
        assert isinstance(asset_kinds.find_handler(Path("a/b.ASE")), asset_kinds.AsepriteHandler)
        assert isinstance(asset_kinds.find_handler(Path("a/b.glb")), asset_kinds.ModelHandler)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script test_index.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'asset_kinds'` (import error fails collection).

- [ ] **Step 3: Create `asset_kinds.py`**

```python
"""Asset kind handlers: match files to kinds, extract per-kind metadata."""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

import aseprite_parser
import frame_detect
import model_indexer

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
ASEPRITE_EXTENSIONS = {".aseprite", ".ase"}
MODEL_EXTENSIONS = {".glb", ".gltf"}


@dataclass
class IndexContext:
    asset_root: Path
    pack_root: Path  # pack dir, or asset_root for packless files
    db_root: Path  # thumbnail_path is stored relative to this
    rel_path: str  # asset path relative to asset_root


@dataclass
class AssetMeta:
    asset_kind: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None
    preview_bounds: Optional[tuple] = None
    rig: Optional[str] = None
    thumbnail_path: Optional[str] = None
    extra_tags: list[str] = field(default_factory=list)
    clip_names: list[str] = field(default_factory=list)
    wants_colors: bool = False  # image-only post steps: colors + phash


def _thumb_key(rel_path: str) -> str:
    return hashlib.sha256(rel_path.encode()).hexdigest()[:16]


def _rel_to_db_root(thumb: Path, db_root: Path) -> str:
    try:
        return str(thumb.relative_to(db_root))
    except ValueError:
        return str(thumb)


class ExtensionHandler:
    extensions: set[str] = set()

    def match(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions


class ImageHandler(ExtensionHandler):
    extensions = IMAGE_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        meta = AssetMeta(wants_colors=True)
        try:
            with Image.open(path) as img:
                meta.width, meta.height = img.size
        except Exception:
            pass
        meta.preview_bounds = frame_detect.detect_preview_bounds(path, ctx.pack_root)
        return meta


class AsepriteHandler(ExtensionHandler):
    extensions = ASEPRITE_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        info = aseprite_parser.parse_aseprite(path)
        return AssetMeta(width=info["width"], height=info["height"])


class ModelHandler(ExtensionHandler):
    extensions = MODEL_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        info = model_indexer.extract_model_info(path)
        # KayKit animation bundles ship mannequin meshes, so has_mesh
        # is unreliable. Use filename prefix + animations instead.
        is_bundle = path.stem.startswith("Rig_") and bool(info.animations)
        meta = AssetMeta(
            asset_kind="animation_bundle" if is_bundle else "model",
            rig=info.rig,
            clip_names=info.animations,
            extra_tags=["3d"],
        )
        cache_dir = ctx.db_root / ".index" / "thumbs"
        thumb = model_indexer.resolve_thumbnail(
            path, ctx.pack_root, cache_dir, _thumb_key(ctx.rel_path)
        )
        if thumb:
            meta.thumbnail_path = _rel_to_db_root(thumb, ctx.db_root)
        return meta


HANDLERS = [AsepriteHandler(), ImageHandler(), ModelHandler()]


def find_handler(path: Path):
    """First handler claiming the file, or None (file is not indexed)."""
    for handler in HANDLERS:
        if handler.match(path):
            return handler
    return None
```

- [ ] **Step 4: Refactor `index.py` to use the registry**

4a. Replace the extension-set definitions (`index.py:41-44`) with a re-export (tests and `index_asset` reference `index.IMAGE_EXTENSIONS`):

```python
import asset_kinds
from asset_kinds import ASEPRITE_EXTENSIONS, IMAGE_EXTENSIONS, MODEL_EXTENSIONS
```

(Place `import asset_kinds` with the other local imports next to `import aseprite_parser`; remove the old `IMAGE_EXTENSIONS = {...}` etc. lines and the `# Supported image types for indexing` comment.)

4b. Replace `scan_assets` (`index.py:511-523`) with:

```python
def scan_assets(asset_root: Path) -> list[Path]:
    """Scan directory for files claimed by a kind handler."""
    def visible(p: Path) -> bool:
        return not any(part.startswith(".") for part in p.relative_to(asset_root).parts)

    regular: list[Path] = []
    models: list[Path] = []
    for p in asset_root.rglob("*"):
        if not p.is_file() or not visible(p):
            continue
        handler = asset_kinds.find_handler(p)
        if handler is None:
            continue
        if isinstance(handler, asset_kinds.ModelHandler):
            models.append(p)
        else:
            regular.append(p)
    models = model_indexer.filter_canonical_models(sorted(models))
    return sorted(regular + models)
```

4c. In the `index()` loop, replace the dispatch block (`index.py:665-698`, from `suffix = file_path.suffix.lower()` through the `elif suffix in ASEPRITE_EXTENSIONS:` branch) with:

```python
            handler = asset_kinds.find_handler(file_path)
            ctx = asset_kinds.IndexContext(
                asset_root=asset_root,
                pack_root=pack_path if pack_name else asset_root,
                db_root=db.parent,
                rel_path=rel_path,
            )
            meta = handler.index_file(file_path, ctx)
            preview_bounds = meta.preview_bounds
```

4d. Update the INSERT parameter list (`index.py:710-725`) to read from `meta` (the SQL text is unchanged):

```python
                [
                    pack_id,
                    rel_path,
                    file_path.name,
                    file_path.suffix.lower().lstrip("."),
                    current_hash,
                    file_path.stat().st_size,
                    meta.width,
                    meta.height,
                    preview_bounds[0] if preview_bounds else None,
                    preview_bounds[1] if preview_bounds else None,
                    preview_bounds[2] if preview_bounds else None,
                    preview_bounds[3] if preview_bounds else None,
                    category, meta.asset_kind, meta.rig, meta.thumbnail_path,
                    datetime.now().isoformat(),
                ]
```

4e. Replace the post-insert `if is_model: ... elif is_image: ...` block (`index.py:733-755`) with:

```python
            if meta.extra_tags:
                add_tags(conn, asset_id, meta.extra_tags, "kind")
            for i, name in enumerate(meta.clip_names):
                conn.execute(
                    "INSERT OR REPLACE INTO asset_animations (asset_id, clip_index, name) VALUES (?, ?, ?)",
                    [asset_id, i, name]
                )
            if meta.wants_colors:
                colors = extract_colors(file_path)
                for hex_color, percentage in colors:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage)
                           VALUES (?, ?, ?)""",
                        [asset_id, hex_color, percentage]
                    )
                # Compute perceptual hash
                phash = compute_phash(file_path)
                if phash:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_phash (asset_id, phash)
                           VALUES (?, ?)""",
                        [asset_id, phash]
                    )
```

(The `tags = extract_tags_from_path(...)` / `add_tags(conn, asset_id, tags, "path")` lines directly above stay as they are. The variables `suffix`, `is_model`, `is_image`, `img_info`, `asset_kind`, `rig`, `thumbnail_path`, `clip_names` from the old block are gone — make sure no stale references remain in the loop.)

Behavioral notes (must hold): aseprite files do NOT get aseprite-embedded tags in the CLI loop (only legacy `index_asset` does that) — preserve this; `filter_canonical_models` still applies to models only; `frame_detect.detect_preview_bounds` still receives the pack dir (or asset_root when packless).

- [ ] **Step 5: Run the full Python suite**

Run: `uv run --script test_index.py && uv run --script test_frame_detect.py && uv run --script test_model_indexer.py && uv run --script web/test_api.py`
Expected: ALL PASS (including new `TestKindRegistry`). Blender-dependent tests may skip — skips are fine, failures are not.

- [ ] **Step 6: Commit**

```bash
git add asset_kinds.py index.py test_index.py
git commit -m "refactor: kind-handler registry for asset indexing"
```

---

### Task 2: FontHandler — font kind + specimen thumbnails

**Files:**
- Create: `tests/fixtures/fonts/PressStart2P-Regular.ttf`, `tests/fixtures/fonts/OFL.txt`
- Modify: `asset_kinds.py` (add `FONT_EXTENSIONS`, `render_font_specimen`, `FontHandler`; register)
- Test: `test_index.py` (new `TestFontIndexing` class)

**Interfaces:**
- Consumes: `AssetMeta`, `IndexContext`, `_thumb_key`, `_rel_to_db_root`, `ExtensionHandler` from Task 1.
- Produces: `asset_kinds.FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}`; `asset_kinds.render_font_specimen(font_path: Path, out_path: Path) -> bool`; `asset_kinds.FontHandler` appended to `HANDLERS`. Font rows: `asset_kind='font'`, injected tag `font`, `thumbnail_path` set (or NULL when unloadable). Task 4 reads font `thumbnail_path` for montages; Task 5 serves it.

- [ ] **Step 1: Vendor the font fixture (OFL-licensed, small)**

```bash
mkdir -p tests/fixtures/fonts
curl -fsSL -o tests/fixtures/fonts/PressStart2P-Regular.ttf \
  https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/PressStart2P-Regular.ttf
curl -fsSL -o tests/fixtures/fonts/OFL.txt \
  https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/OFL.txt
```

Verify it loads: `uv run --with pillow python -c "from PIL import ImageFont; f = ImageFont.truetype('tests/fixtures/fonts/PressStart2P-Regular.ttf', 24); print(f.getname())"`
Expected output: `('Press Start 2P', 'Regular')`. If the URL is unavailable, use any other small OFL font from github.com/google/fonts/tree/main/ofl (adjust the filename everywhere in this task) and include its OFL.txt.

- [ ] **Step 2: Write the failing tests**

Append to `test_index.py`:

```python
FIXTURES_FONTS = Path(__file__).parent / "tests" / "fixtures" / "fonts"
FIXTURE_TTF = FIXTURES_FONTS / "PressStart2P-Regular.ttf"


class TestFontIndexing:
    def test_render_font_specimen_creates_png(self, tmp_path):
        out = tmp_path / "specimen.png"
        assert asset_kinds.render_font_specimen(FIXTURE_TTF, out) is True
        with Image.open(out) as img:
            assert img.size == (512, 256)
            # opaque glyph pixels prove text actually rendered
            assert img.getextrema()[3][1] == 255

    def test_render_specimen_rejects_corrupt_font(self, tmp_path):
        bad = tmp_path / "bad.ttf"
        bad.write_bytes(b"this is not a font")
        out = tmp_path / "specimen.png"
        assert asset_kinds.render_font_specimen(bad, out) is False
        assert not out.exists()

    def test_index_font_pack_end_to_end(self, tmp_path):
        pack = tmp_path / "assets" / "FontPack"
        pack.mkdir(parents=True)
        shutil.copy(FIXTURE_TTF, pack / "PressStart2P-Regular.ttf")
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        result = runner.invoke(app, ["index", str(tmp_path / "assets"), "--db", str(db_path)])
        assert result.exit_code == 0, result.stdout
        conn = index.get_db(db_path)
        row = conn.execute(
            "SELECT * FROM assets WHERE filename = 'PressStart2P-Regular.ttf'"
        ).fetchone()
        assert row["asset_kind"] == "font"
        assert row["filetype"] == "ttf"
        assert row["thumbnail_path"] is not None
        assert (tmp_path / row["thumbnail_path"]).exists()
        tags = {r["name"] for r in conn.execute("""
            SELECT t.name FROM asset_tags at
            JOIN tags t ON t.id = at.tag_id WHERE at.asset_id = ?
        """, [row["id"]])}
        assert "font" in tags

    def test_corrupt_font_indexes_without_thumbnail(self, tmp_path):
        pack = tmp_path / "assets" / "FontPack"
        pack.mkdir(parents=True)
        (pack / "broken.ttf").write_bytes(b"garbage bytes")
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        result = runner.invoke(app, ["index", str(tmp_path / "assets"), "--db", str(db_path)])
        assert result.exit_code == 0, result.stdout
        conn = index.get_db(db_path)
        row = conn.execute("SELECT * FROM assets WHERE filename = 'broken.ttf'").fetchone()
        assert row["asset_kind"] == "font"
        assert row["thumbnail_path"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --script test_index.py`
Expected: `TestFontIndexing` FAILS — `AttributeError: module 'asset_kinds' has no attribute 'render_font_specimen'`, and the end-to-end tests fail because `.ttf` files are never scanned (no row found).

- [ ] **Step 4: Implement FontHandler in `asset_kinds.py`**

Add after the `MODEL_EXTENSIONS` line:

```python
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}

SPECIMEN_SIZE = (512, 256)
SPECIMEN_SAMPLE = "Aa Bb Cc 0123456789"
SPECIMEN_PANGRAM = "The quick brown fox jumps"
```

Add after `ModelHandler`:

```python
def render_font_specimen(font_path: Path, out_path: Path) -> bool:
    """Render a specimen PNG; False when FreeType can't load the font."""
    from PIL import ImageDraw, ImageFont
    try:
        name_font = ImageFont.truetype(str(font_path), 44)
        sample_font = ImageFont.truetype(str(font_path), 26)
        family, style = name_font.getname()
        img = Image.new("RGBA", SPECIMEN_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        title = f"{family} {style}".strip() or font_path.stem
        # light text on transparent bg suits the dark UI
        draw.text((24, 36), title, font=name_font, fill=(238, 238, 238, 255))
        draw.text((24, 128), SPECIMEN_SAMPLE, font=sample_font, fill=(238, 238, 238, 255))
        draw.text((24, 184), SPECIMEN_PANGRAM, font=sample_font, fill=(190, 190, 190, 255))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
        return True
    except Exception:
        logger.warning("Cannot render font specimen: %s", font_path)
        return False


class FontHandler(ExtensionHandler):
    extensions = FONT_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        meta = AssetMeta(asset_kind="font", extra_tags=["font"])
        out = ctx.db_root / ".index" / "thumbs" / f"{_thumb_key(ctx.rel_path)}.png"
        if render_font_specimen(path, out):
            meta.thumbnail_path = _rel_to_db_root(out, ctx.db_root)
        return meta
```

Update the registry line:

```python
HANDLERS = [AsepriteHandler(), ImageHandler(), ModelHandler(), FontHandler()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --script test_index.py`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add asset_kinds.py test_index.py tests/fixtures/fonts/
git commit -m "feat: index fonts with rendered specimen thumbnails"
```

---

### Task 3: FileHandler — catch-all kind with junk denylist

**Files:**
- Modify: `asset_kinds.py` (denylists + `FileHandler`; register last)
- Test: `test_index.py` (new `TestAnyfileIndexing`; update any count assertions broken by newly-indexed files)

**Interfaces:**
- Consumes: `AssetMeta`, `HANDLERS` from Task 1.
- Produces: `asset_kinds.FileHandler` (catch-all, `match()` returns False for denylisted names/extensions); `DENYLIST_NAMES`, `DENYLIST_EXTENSIONS`. File rows: `asset_kind='file'`, injected tag `file`, width/height/thumbnail NULL. Tasks 5-10 render/serve these.

- [ ] **Step 1: Write the failing tests**

Append to `test_index.py`:

```python
class TestAnyfileIndexing:
    def _index(self, root, db_path):
        runner = typer.testing.CliRunner()
        from index import app
        return runner.invoke(app, ["index", str(root), "--db", str(db_path)])

    def test_shader_indexed_as_file(self, tmp_path):
        pack = tmp_path / "assets" / "ShaderPack"
        pack.mkdir(parents=True)
        shader = pack / "blur.glsl"
        shader.write_text("void main() {}\n")
        db_path = tmp_path / "assets.db"
        result = self._index(tmp_path / "assets", db_path)
        assert result.exit_code == 0, result.stdout
        conn = index.get_db(db_path)
        row = conn.execute("SELECT * FROM assets WHERE filename = 'blur.glsl'").fetchone()
        assert row["asset_kind"] == "file"
        assert row["filetype"] == "glsl"
        assert row["file_size"] == shader.stat().st_size
        assert row["width"] is None
        tags = {r["name"] for r in conn.execute("""
            SELECT t.name FROM asset_tags at
            JOIN tags t ON t.id = at.tag_id WHERE at.asset_id = ?
        """, [row["id"]])}
        assert "file" in tags

    def test_junk_files_are_skipped(self, tmp_path):
        pack = tmp_path / "assets" / "ShaderPack"
        pack.mkdir(parents=True)
        (pack / "blur.glsl").write_text("void main() {}\n")
        (pack / ".DS_Store").write_bytes(b"junk")
        (pack / "Thumbs.db").write_bytes(b"junk")
        (pack / "scene.import").write_text("junk")
        (pack / "notes.tmp").write_text("junk")
        db_path = tmp_path / "assets.db"
        result = self._index(tmp_path / "assets", db_path)
        assert result.exit_code == 0, result.stdout
        conn = index.get_db(db_path)
        paths = [r["filename"] for r in conn.execute("SELECT filename FROM assets")]
        assert paths == ["blur.glsl"]

    def test_reindex_skips_unchanged_anyfiles(self, tmp_path):
        pack = tmp_path / "assets" / "ShaderPack"
        pack.mkdir(parents=True)
        (pack / "blur.glsl").write_text("void main() {}\n")
        db_path = tmp_path / "assets.db"
        self._index(tmp_path / "assets", db_path)
        result = self._index(tmp_path / "assets", db_path)
        assert "Indexed 0 new/changed" in strip_ansi(result.stdout)

    def test_catch_all_matches_unknown_extensions(self):
        assert isinstance(asset_kinds.find_handler(Path("a/b.wgsl")), asset_kinds.FileHandler)
        assert isinstance(asset_kinds.find_handler(Path("a/b.blend")), asset_kinds.FileHandler)
        assert asset_kinds.find_handler(Path("a/.DS_Store")) is None
        assert asset_kinds.find_handler(Path("a/b.meta")) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py`
Expected: `TestAnyfileIndexing` FAILS (`.glsl` files never indexed; no `FileHandler` attribute).

- [ ] **Step 3: Implement FileHandler in `asset_kinds.py`**

Add after `FONT_EXTENSIONS`:

```python
# OS/engine junk the catch-all must never index
DENYLIST_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}
DENYLIST_EXTENSIONS = {".db", ".db-journal", ".import", ".meta", ".tmp", ".part"}
```

Add after `FontHandler`:

```python
class FileHandler:
    """Catch-all: any unclaimed file becomes a downloadable 'file' asset."""

    def match(self, path: Path) -> bool:
        if path.name.lower() in DENYLIST_NAMES:
            return False
        return path.suffix.lower() not in DENYLIST_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        return AssetMeta(asset_kind="file", extra_tags=["file"])
```

Update the registry (FileHandler MUST be last — first match wins):

```python
HANDLERS = [AsepriteHandler(), ImageHandler(), ModelHandler(), FontHandler(), FileHandler()]
```

- [ ] **Step 4: Run the full Python suite and repair count assertions**

Run: `uv run --script test_index.py && uv run --script web/test_api.py`

Expected: `TestAnyfileIndexing` passes. Some pre-existing tests MAY now fail because packs in fixtures contain extra files that the catch-all legitimately indexes (e.g. `sample_asset_pack`'s `_AnimationInfo.txt`, the 3D fixtures' `axe_1handed.bin`). For each failure: if it asserts a total asset/row count, update the expected count to include the new `kind='file'` rows; if it asserts something else, stop and investigate — that would be a real regression, not fallout. Do not change queries that filter by `filetype = 'png'` or `asset_kind` — those are unaffected by design.

- [ ] **Step 5: Commit**

```bash
git add asset_kinds.py test_index.py
git commit -m "feat: catch-all file asset kind with junk denylist"
```

---

### Task 4: Pack montage fallback with font specimens

**Files:**
- Modify: `index.py` (`generate_pack_preview` at :256-315; call site at :806)
- Test: `test_index.py` (new `TestFontPackPreview`)

**Interfaces:**
- Consumes: font rows with `thumbnail_path` (Task 2).
- Produces: `generate_pack_preview(conn, pack_id, asset_root, preview_dir, grid_size=4, thumb_size=64, db_root=None)` — signature gains optional `db_root`. Behavior for image packs is unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `test_index.py`:

```python
class TestFontPackPreview:
    def test_fonts_only_pack_gets_montage(self, tmp_path):
        pack = tmp_path / "assets" / "FontPack"
        pack.mkdir(parents=True)
        for i in range(4):
            shutil.copy(FIXTURE_TTF, pack / f"font_{i}.ttf")
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        result = runner.invoke(app, ["index", str(tmp_path / "assets"), "--db", str(db_path)])
        assert result.exit_code == 0, result.stdout
        conn = index.get_db(db_path)
        row = conn.execute("SELECT preview_path FROM packs WHERE name = 'FontPack'").fetchone()
        assert row["preview_path"] is not None
        assert (db_path.parent / ".index" / row["preview_path"]).exists()

    def test_small_image_pack_still_gets_no_montage(self, tmp_path):
        pack = tmp_path / "assets" / "TinyPack"
        pack.mkdir(parents=True)
        for i in range(3):
            Image.new("RGBA", (32, 32), (10 * i, 100, 50, 255)).save(pack / f"s{i}.png")
        db_path = tmp_path / "assets.db"
        runner = typer.testing.CliRunner()
        from index import app
        runner.invoke(app, ["index", str(tmp_path / "assets"), "--db", str(db_path)])
        conn = index.get_db(db_path)
        row = conn.execute("SELECT preview_path FROM packs WHERE name = 'TinyPack'").fetchone()
        assert row["preview_path"] is None
```

Note: `generate_pack_preview` saves montages under `.index/previews/` and returns the path relative to `preview_dir.parent` — hence the `.index /` join in the first assertion.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script test_index.py`
Expected: `test_fonts_only_pack_gets_montage` FAILS (`preview_path` is None — fonts have no PNGs); the second test passes already (guards the invariant).

- [ ] **Step 3: Implement the fallback**

In `generate_pack_preview`, change the signature and the selection logic. New signature:

```python
def generate_pack_preview(
    conn: sqlite3.Connection,
    pack_id: int,
    asset_root: Path,
    preview_dir: Path,
    grid_size: int = 4,
    thumb_size: int = 64,
    db_root: Optional[Path] = None,
) -> Optional[str]:
    """Generate a preview montage for a pack."""
    db_root = db_root or preview_dir.parent.parent
```

After the existing `rows = conn.execute(...)` PNG query, replace the `if len(rows) < 4: return None` block and the montage loop's row handling with an entries list — PNGs first, then font specimens as padding:

```python
    entries: list[tuple[Path, Optional[sqlite3.Row]]] = [
        (asset_root / r["path"], r) for r in rows
    ]
    if len(entries) < grid_size * grid_size:
        font_rows = conn.execute("""
            SELECT thumbnail_path FROM assets
            WHERE pack_id = ? AND asset_kind = 'font' AND thumbnail_path IS NOT NULL
            ORDER BY filename
            LIMIT ?
        """, [pack_id, grid_size * grid_size - len(entries)]).fetchall()
        entries.extend((db_root / r["thumbnail_path"], None) for r in font_rows)

    if len(entries) < 4:
        return None
```

In the montage loop, iterate over `entries` instead of `rows`; specimens have no crop bounds:

```python
        for i, (img_path, row) in enumerate(entries):
            x = (i % grid_size) * thumb_size
            y = (i // grid_size) * thumb_size

            with Image.open(img_path) as img:
                # Use preview bounds if available
                if row is not None and row["preview_x"] is not None:
                    img = img.crop((
                        row["preview_x"],
                        row["preview_y"],
                        row["preview_x"] + row["preview_width"],
                        row["preview_y"] + row["preview_height"]
                    ))

                img.thumbnail((thumb_size, thumb_size), Image.Resampling.NEAREST)
                # Center in cell
                offset_x = (thumb_size - img.width) // 2
                offset_y = (thumb_size - img.height) // 2
                montage.paste(img, (x + offset_x, y + offset_y))
```

(The old `img_path = asset_root / row["path"]` line is replaced by the tuple unpack.)

Update the call site (`index.py:806`):

```python
            preview_path = generate_pack_preview(conn, row["id"], asset_root, preview_dir, db_root=db.parent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script test_index.py`
Expected: ALL PASS (including `TestPackContentsConvention` and existing preview tests — montage behavior for ≥4-PNG packs is unchanged).

- [ ] **Step 5: Commit**

```bash
git add index.py test_index.py
git commit -m "feat: pad pack montages with font specimens"
```

---

### Task 5: API — raw file endpoint, font thumbnails, file_size

**Files:**
- Modify: `web/api.py` (new endpoint after `asset_model_sibling`; `image()` at :578-615; `search()` at :200-302; `asset_detail()` at :365-424)
- Test: `web/test_api.py` (new fixture + tests)

**Interfaces:**
- Consumes: rows written by Tasks 2-3.
- Produces: `GET /api/asset/{id}/file?download=<bool>` (raw bytes; attachment disposition when download=true); `/api/image/{id}` serves font thumbnails and 404s for `kind='file'`; search + asset detail responses gain `"file_size"`; kind-only searches get deterministic ordering. Frontend tasks 7-10 depend on all of these.

- [ ] **Step 1: Write the failing tests**

Append to `web/test_api.py`:

```python
@pytest.fixture
def kinds_db(tmp_path):
    """DB + real files on disk for font/file kind endpoints."""
    assets_dir = tmp_path / "assets"
    pack_dir = assets_dir / "MixedPack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "blur.glsl").write_text("void main() {}\n")
    (pack_dir / "pixel.ttf").write_bytes(b"\x00\x01\x00\x00 fake font bytes")
    thumbs = tmp_path / ".index" / "thumbs"
    thumbs.mkdir(parents=True)
    from PIL import Image
    Image.new("RGBA", (512, 256), (238, 238, 238, 255)).save(thumbs / "pixel.png")

    db_path = tmp_path / "kinds.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
            version TEXT, theme TEXT, preview_path TEXT, asset_count INTEGER DEFAULT 0
        );
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL, filetype TEXT NOT NULL, file_hash TEXT NOT NULL,
            file_size INTEGER, width INTEGER, height INTEGER,
            preview_x INTEGER, preview_y INTEGER, preview_width INTEGER, preview_height INTEGER,
            category TEXT, asset_kind TEXT, rig TEXT, thumbnail_path TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);
        CREATE TABLE asset_preview_overrides (
            path TEXT PRIMARY KEY, use_full_image BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO packs (id, name, path) VALUES (1, 'MixedPack', 'MixedPack');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, file_size, asset_kind, thumbnail_path)
            VALUES (1, 1, 'MixedPack/pixel.ttf', 'pixel.ttf', 'ttf', 'fh1', 20, 'font', '.index/thumbs/pixel.png');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, file_size, asset_kind)
            VALUES (2, 1, 'MixedPack/blur.glsl', 'blur.glsl', 'glsl', 'fh2', 15, 'file');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, file_size, asset_kind) VALUES
            (3, 1, 'MixedPack/a.wgsl', 'a.wgsl', 'wgsl', 'fh3', 5, 'file'),
            (4, 1, 'MixedPack/b.wgsl', 'b.wgsl', 'wgsl', 'fh4', 5, 'file'),
            (5, 1, 'MixedPack/c.wgsl', 'c.wgsl', 'wgsl', 'fh5', 5, 'file'),
            (6, 1, 'MixedPack/d.wgsl', 'd.wgsl', 'wgsl', 'fh6', 5, 'file'),
            (7, 1, 'MixedPack/e.wgsl', 'e.wgsl', 'wgsl', 'fh7', 5, 'file'),
            (8, 1, 'MixedPack/f.wgsl', 'f.wgsl', 'wgsl', 'fh8', 5, 'file');
    """)
    conn.commit()
    conn.close()

    from api import set_assets_path, set_db_path
    set_db_path(db_path)
    set_assets_path(assets_dir)
    yield db_path
    db_path.unlink()


def test_asset_file_serves_raw_bytes(kinds_db):
    r = client.get("/api/asset/2/file")
    assert r.status_code == 200
    assert r.content == b"void main() {}\n"
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert "attachment" not in r.headers.get("content-disposition", "")


def test_asset_file_download_disposition(kinds_db):
    r = client.get("/api/asset/2/file?download=true")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="blur.glsl"'


def test_asset_file_404s(kinds_db):
    assert client.get("/api/asset/999/file").status_code == 404


def test_image_serves_font_thumbnail(kinds_db):
    r = client.get("/api/image/1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_image_404_for_file_kind(kinds_db):
    assert client.get("/api/image/2").status_code == 404


def test_search_returns_file_size(kinds_db):
    r = client.get("/api/search", params={"kind": "font"})
    assets = r.json()["assets"]
    assert [a["filename"] for a in assets] == ["pixel.ttf"]
    assert assets[0]["file_size"] == 20


def test_kind_only_search_is_deterministic(kinds_db):
    # kind-only search must not fall into RANDOM() empty-search ordering
    p1 = [a["path"] for a in client.get("/api/search", params={"kind": "file"}).json()["assets"]]
    p2 = [a["path"] for a in client.get("/api/search", params={"kind": "file"}).json()["assets"]]
    assert p1 == sorted(p1)
    assert p2 == sorted(p2)


def test_asset_detail_includes_file_size(kinds_db):
    r = client.get("/api/asset/2")
    assert r.status_code == 200
    body = r.json()
    assert body["file_size"] == 15
    assert body["kind"] == "file"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py`
Expected: new tests FAIL — `/api/asset/2/file` 404s (route missing; FastAPI matches it as `asset_detail` with a non-int path → 422, either failure is fine), `file_size` KeyError, `/api/image/2` returns 200 raw text, kind-only ordering is random.

- [ ] **Step 3: Implement in `web/api.py`**

3a. Replace `_3D_KINDS = {"model", "animation_bundle"}` (web/api.py:575) and the `image()` branch:

```python
# kinds whose /api/image response is a generated thumbnail, not the raw file
_THUMBNAIL_KINDS = {"model", "animation_bundle", "font"}
```

In `image()` replace `if row["asset_kind"] in _3D_KINDS:` with:

```python
    # 'file' assets have no visual form at all
    if row["asset_kind"] == "file":
        raise HTTPException(status_code=404, detail="No preview")

    # Serve thumbnail PNG for kinds whose raw file isn't an image
    if row["asset_kind"] in _THUMBNAIL_KINDS:
```

(The body of the thumbnail branch is unchanged.)

3b. Add the raw-file endpoint after `asset_model_sibling` (web/api.py:697):

```python
@app.get("/api/asset/{asset_id}/file")
def asset_file(asset_id: int, download: bool = False):
    """Serve the raw asset file; ?download=true forces attachment."""
    import mimetypes
    conn = get_db()
    row = conn.execute(
        "SELECT path, filename FROM assets WHERE id = ?", [asset_id]
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    p = get_assets_path() / row["path"]
    if not p.exists():
        raise HTTPException(status_code=404, detail="File missing")
    media = mimetypes.guess_type(row["filename"])[0] or "application/octet-stream"
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{row["filename"]}"'
    return FileResponse(p, media_type=media, headers=headers)
```

3c. In `search()`: add `a.file_size` to the SELECT projection (after `a.thumbnail_path,` on web/api.py:259) and `"file_size": row["file_size"],` to the asset dict (after the `"thumbnail_path"` entry). Fix the empty-search check (web/api.py:253):

```python
    is_empty_search = not q and not tag and not pack and not type and not kind
```

3d. In `asset_detail()`: add `"file_size": row["file_size"],` to the returned dict (after `"filetype"`; the SELECT is `a.*` so the column is already fetched).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: ALL PASS (existing image/search tests included).

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: raw file endpoint, font thumbs, file_size in API"
```

---

### Task 6: API — per-pack `section` in /api/filters

**Files:**
- Modify: `web/api.py` (`filters()` at :513-569)
- Test: `web/test_api.py`

**Interfaces:**
- Consumes: `asset_kind` values from Tasks 2-3.
- Produces: each pack in `/api/filters` gains `"section": "2d" | "3d" | "fonts" | "files"`. `is_3d` stays for now (removed in Task 8 together with the frontend switch). Helper `_pack_section(n_3d, n_image, n_font, n_file) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `web/test_api.py`:

```python
def test_filters_pack_sections(test_db):
    conn = sqlite3.connect(test_db)
    conn.executescript("""
        INSERT INTO packs (id, name, path, asset_count) VALUES
            (20, 'FontPack', 'FontPack', 5),
            (21, 'ShaderPack', 'ShaderPack', 6),
            (22, 'ModelPack', 'ModelPack', 2);
        INSERT INTO assets (pack_id, path, filename, filetype, file_hash, asset_kind) VALUES
            (20, 'FontPack/a.ttf', 'a.ttf', 'ttf', 's1', 'font'),
            (20, 'FontPack/b.ttf', 'b.ttf', 'ttf', 's2', 'font'),
            (20, 'FontPack/c.ttf', 'c.ttf', 'ttf', 's3', 'font'),
            (20, 'FontPack/p1.png', 'p1.png', 'png', 's4', 'image'),
            (20, 'FontPack/p2.png', 'p2.png', 'png', 's5', 'image'),
            (21, 'ShaderPack/a.glsl', 'a.glsl', 'glsl', 's6', 'file'),
            (21, 'ShaderPack/b.glsl', 'b.glsl', 'glsl', 's7', 'file'),
            (21, 'ShaderPack/c.glsl', 'c.glsl', 'glsl', 's8', 'file'),
            (21, 'ShaderPack/d.glsl', 'd.glsl', 'glsl', 's9', 'file'),
            (21, 'ShaderPack/e.glsl', 'e.glsl', 'glsl', 's10', 'file'),
            (21, 'ShaderPack/prev.png', 'prev.png', 'png', 's11', 'image'),
            (22, 'ModelPack/m.glb', 'm.glb', 'glb', 's12', 'model'),
            (22, 'ModelPack/tex.png', 'tex.png', 'png', 's13', 'image');
    """)
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    packs = {p["name"]: p for p in resp.json()["packs"]}
    # fonts outnumber preview images -> fonts; shaders dominate -> files
    assert packs["FontPack"]["section"] == "fonts"
    assert packs["ShaderPack"]["section"] == "files"
    assert packs["ModelPack"]["section"] == "3d"
    # existing image-only pack stays 2d
    assert packs["creatures"]["section"] == "2d"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_api.py`
Expected: FAIL with `KeyError: 'section'`.

- [ ] **Step 3: Implement**

Add above `filters()`:

```python
def _pack_section(n_3d: int, n_image: int, n_font: int, n_file: int) -> str:
    """Sidebar section: any 3D asset wins; else plurality, ties font > file > image."""
    if n_3d:
        return "3d"
    ranked = [("fonts", n_font), ("files", n_file), ("2d", n_image)]
    label, best = max(ranked, key=lambda kv: kv[1])
    return label if best else "2d"
```

Replace the packs query in `filters()` (web/api.py:519-526) with kind counts (the `a.id IS NOT NULL` guard keeps empty packs at zero — a bare LEFT JOIN row would otherwise count as one NULL-kind image):

```python
    packs = conn.execute("""
        SELECT p.id, p.name, p.source, p.asset_count AS count,
               SUM(CASE WHEN a.asset_kind IN ('model', 'animation_bundle') THEN 1 ELSE 0 END) AS n_3d,
               SUM(CASE WHEN a.asset_kind = 'font' THEN 1 ELSE 0 END) AS n_font,
               SUM(CASE WHEN a.asset_kind = 'file' THEN 1 ELSE 0 END) AS n_file,
               SUM(CASE WHEN a.id IS NOT NULL
                         AND (a.asset_kind = 'image' OR a.asset_kind IS NULL)
                    THEN 1 ELSE 0 END) AS n_image
        FROM packs p
        LEFT JOIN assets a ON a.pack_id = p.id
        GROUP BY p.id
        ORDER BY p.name
    """).fetchall()
```

Update the response pack dict (web/api.py:557-566):

```python
            {
                "id": p["id"],
                "name": p["name"],
                "count": p["count"],
                "is_3d": bool(p["n_3d"]),
                "section": _pack_section(p["n_3d"], p["n_image"], p["n_font"], p["n_file"]),
                "is_board": p["source"] == "user",
                "tags": pack_tag_map.get(p["id"], []),
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: ALL PASS — including `test_filters_include_is_3d` (is_3d still present) and `test_filters_tolerate_db_without_theme_column` (the legacy DB there has an `assets` table with `asset_kind`; the new SQL must not touch other columns).

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: per-pack section classification in filters API"
```

---

### Task 7: Frontend — AssetGrid cards for file and font kinds

**Files:**
- Create: `web/frontend/src/utils/fileSize.js`
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Test: `web/frontend/tests/AssetGrid.test.js`, `web/frontend/tests/fileSize.test.js`

**Interfaces:**
- Consumes: `asset.kind`, `asset.file_size` from search API (Task 5).
- Produces: `formatSize(bytes) -> string` in `src/utils/fileSize.js` (also used by Task 9). Grid renders `.file-badge` (ext + size) for `kind='file'`, specimen `<img>` for `kind='font'` with `.font-fallback` on load error.

- [ ] **Step 1: Write the failing tests**

Create `web/frontend/tests/fileSize.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { formatSize } from '../src/utils/fileSize.js'

describe('formatSize', () => {
  it('scales through units and rounds sensibly', () => {
    expect(formatSize(512)).toBe('512 B')
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(15 * 1024 * 1024)).toBe('15 MB')
    expect(formatSize(null)).toBe('')
  })
})
```

Append to `web/frontend/tests/AssetGrid.test.js` (reuse the file's existing `mount`/`AssetGrid` imports):

```js
describe('AssetGrid file/font kinds', () => {
  const fileAsset = {
    id: 10, filename: 'blur.glsl', pack: 'Shaders', kind: 'file',
    file_size: 2048, tags: [], preview_x: null, width: null, height: null,
  }
  const fontAsset = {
    id: 11, filename: 'pixel.ttf', pack: 'Fonts', kind: 'font',
    tags: [], preview_x: null, width: null, height: null,
  }

  it('renders extension badge instead of image for file assets', () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fileAsset] } })
    expect(wrapper.find('.file-ext').text()).toBe('.GLSL')
    expect(wrapper.find('.file-size').text()).toBe('2.0 KB')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('renders thumbnail image for font assets', () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fontAsset] } })
    expect(wrapper.find('img').attributes('src')).toContain('/image/11')
  })

  it('falls back to Aa placeholder when a font thumbnail fails', async () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fontAsset] } })
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('.font-fallback').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: FAIL — `fileSize.js` missing; `.file-ext` not found.

- [ ] **Step 3: Implement**

Create `web/frontend/src/utils/fileSize.js`:

```js
export function formatSize(bytes) {
  if (bytes == null) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n >= 10 || i === 0 ? Math.round(n) : n.toFixed(1)} ${units[i]}`
}
```

In `AssetGrid.vue`, replace the `asset-image-container` div (template lines 15-41) with:

```html
        <div
          class="asset-image-container"
          :style="containerStyle(asset)"
          @click="$emit('select', asset.id)"
        >
          <div v-if="asset.kind === 'file'" class="file-badge">
            <span class="file-ext">.{{ fileExt(asset) }}</span>
            <span class="file-size" v-if="asset.file_size != null">{{ formatSize(asset.file_size) }}</span>
          </div>
          <span
            v-else-if="asset.kind === 'font' && thumbFailed[asset.id]"
            class="font-fallback"
          >Aa</span>
          <SpritePreview
            v-else-if="asset.preview_x !== null && !asset.use_full_image"
            :asset-id="asset.id"
            :preview-x="asset.preview_x"
            :preview-y="asset.preview_y"
            :preview-width="asset.preview_width"
            :preview-height="asset.preview_height"
            :width="asset.width"
            :height="asset.height"
          />
          <img
            v-else
            :src="`${API_BASE}/image/${asset.id}`"
            :alt="asset.filename"
            @error="asset.kind === 'font' ? (thumbFailed[asset.id] = true) : null"
          />
          <button
            v-if="hoveredId === asset.id && !cartIds.includes(asset.id)"
            class="add-cart-btn"
            @click.stop="$emit('add-to-cart', asset)"
          >+</button>
          <span v-if="cartIds.includes(asset.id)" class="cart-indicator">✓</span>
        </div>
```

In the script block, add to the imports/refs:

```js
import { reactive, ref } from 'vue'
import { formatSize } from '../utils/fileSize.js'
```

and below `const hoveredId = ref(null)`:

```js
const thumbFailed = reactive({})

function fileExt(asset) {
  const parts = asset.filename.split('.')
  return parts.length > 1 ? parts.pop().toUpperCase() : ''
}

// specimen/file cards have no intrinsic dimensions; fix a wide ratio
function containerStyle(asset) {
  if (asset.kind === 'file' || asset.kind === 'font') return { aspectRatio: '2 / 1' }
  return {
    aspectRatio: (asset.preview_x != null && !asset.use_full_image)
      ? `${asset.preview_width} / ${asset.preview_height}`
      : `${asset.width} / ${asset.height}`
  }
}
```

Append to the style block:

```css
.file-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.file-ext {
  font-weight: 700;
  font-size: 1.125rem;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}

.file-size {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.font-fallback {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-secondary);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: ALL PASS (existing AssetGrid specs unchanged — image/sprite branches behave identically).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/utils/fileSize.js web/frontend/src/components/AssetGrid.vue web/frontend/tests/AssetGrid.test.js web/frontend/tests/fileSize.test.js
git commit -m "feat: grid cards for file and font asset kinds"
```

---

### Task 8: Frontend — Fonts/Files sidebar sections (switch to `section`)

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue` (sections computed at :131-139), `web/api.py` (drop `is_3d`), `web/test_api.py` (`test_filters_include_is_3d` at :366)
- Test: `web/frontend/tests/PackGallery.test.js`, `web/frontend/tests/App.test.js`

**Interfaces:**
- Consumes: `pack.section` from Task 6.
- Produces: gallery renders up to four sections in order 2D, 3D, Fonts, Files (empty hidden). `is_3d` is removed from the `/api/filters` response and all fixtures/tests — after this task, grep for `is_3d` returns nothing.

- [ ] **Step 1: Write the failing test**

Append to `web/frontend/tests/PackGallery.test.js`:

```js
describe('PackGallery kind sections', () => {
  it('groups packs into Fonts and Files sections', () => {
    const wrapper = mount(PackGallery, { props: { packs: [
      { name: 'PixelFonts', count: 10, section: 'fonts', tags: [] },
      { name: 'ShaderLib', count: 5, section: 'files', tags: [] },
      { name: 'Sprites', count: 5, section: '2d', tags: [] },
    ] } })
    const titles = wrapper.findAll('.dim-title').map(t => t.text())
    expect(titles).toEqual(['2D', 'Fonts', 'Files'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test`
Expected: new test FAILS (all three packs land in '2D' — `is_3d` is undefined/falsy).

- [ ] **Step 3: Implement**

In `PackGallery.vue`, replace the `sections` computed (:131-139):

```js
const SECTIONS = [
  { key: '2d', label: '2D' },
  { key: '3d', label: '3D' },
  { key: 'fonts', label: 'Fonts' },
  { key: 'files', label: 'Files' },
]

const sections = computed(() => {
  const visible = activeTag.value
    ? props.packs.filter(p => tagsOf(p).includes(activeTag.value))
    : props.packs
  return SECTIONS
    .map(s => ({ label: s.label, packs: visible.filter(p => (p.section || '2d') === s.key) }))
    .filter(s => s.packs.length)
})
```

In `web/api.py` `filters()`, delete the `"is_3d": bool(p["n_3d"]),` line from the pack dict (`section` fully replaces it).

Update the fixtures/tests that still use `is_3d`:
- `web/test_api.py:366` — rename `test_filters_include_is_3d` to `test_filters_model_pack_is_3d_section` and replace the two assertions at :402-403 with `assert packs["Forest3D"]["section"] == "3d"` and `assert packs["Sprites2D"]["section"] == "2d"`.
- `web/frontend/tests/PackGallery.test.js` — replace every `is_3d: false` with `section: '2d'` and `is_3d: true` with `section: '3d'` in fixtures (:9-11, :126-127, :140); the filter at :32 becomes `packs.filter(p => p.section !== '3d')`.
- `web/frontend/tests/App.test.js:676` — `is_3d: false` → `section: '2d'`.
- Then verify nothing is left: `grep -rn "is_3d" web/ && echo LEFTOVERS || echo CLEAN` must print CLEAN.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test` and `uv run --script web/test_api.py`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js web/frontend/tests/App.test.js
git commit -m "feat: Fonts/Files sidebar sections via pack section field"
```

---

### Task 9: Frontend — AssetDetail download button + file panel

**Files:**
- Modify: `web/frontend/src/components/AssetDetail.vue`
- Test: `web/frontend/tests/AssetDetail.test.js`

**Interfaces:**
- Consumes: `/api/asset/{id}/file?download=true` (Task 5), `asset.kind`, `asset.file_size`, `formatSize` (Task 7).
- Produces: `.download-btn` anchor for font/file kinds; `.file-panel` replaces the image for `kind='file'`; metadata rows guard against null width. Task 10 adds the font branch alongside.

- [ ] **Step 1: Write the failing tests**

Append to `web/frontend/tests/AssetDetail.test.js`:

```js
describe('AssetDetail file kind', () => {
  const fileAsset = {
    id: 5, filename: 'blur.glsl', path: 'Shaders/blur.glsl', pack: 'Shaders',
    kind: 'file', file_size: 2048, width: null, height: null, tags: ['file'], colors: [],
  }

  it('shows a download link with attachment url', () => {
    const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
    const link = wrapper.find('.download-btn')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toContain('/asset/5/file?download=true')
  })

  it('renders a file panel instead of an image', () => {
    const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
    expect(wrapper.find('.file-panel').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('2.0 KB')
  })

  it('hides pixel dimensions and Full Size for file assets', () => {
    const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
    expect(wrapper.text()).not.toContain('nullxnull')
    expect(wrapper.find('.full-size-btn').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: FAIL — no `.download-btn`, `<img>` rendered for file kind, text contains `nullxnull`.

- [ ] **Step 3: Implement in `AssetDetail.vue`**

3a. Template — add a file branch between `ModelViewer` and the `v-else` img (:9-22):

```html
      <div v-else-if="asset.kind === 'file'" class="file-panel">
        <span class="file-ext-big">.{{ fileExt }}</span>
        <span class="file-panel-name">{{ asset.filename }}</span>
        <span class="file-panel-size" v-if="asset.file_size != null">{{ formatSize(asset.file_size) }}</span>
      </div>
```

3b. Metadata — replace the Size div (:44-46) with:

```html
          <div v-if="asset.width != null">
            <strong>Size:</strong> {{ asset.width }}x{{ asset.height }}
          </div>
          <div v-if="asset.file_size != null">
            <strong>File size:</strong> {{ formatSize(asset.file_size) }}
          </div>
```

3c. Actions — guard Full Size and add Download (replace the Full Size anchor at :81-88):

```html
          <a
            v-if="asset.kind !== 'file'"
            :href="`${API_BASE}/image/${asset.id}`"
            target="_blank"
            rel="noopener noreferrer"
            class="full-size-btn"
          >
            Full Size
          </a>
          <a
            v-if="asset.kind === 'font' || asset.kind === 'file'"
            :href="`${API_BASE}/asset/${asset.id}/file?download=true`"
            class="download-btn"
          >
            Download
          </a>
```

3d. Script — add:

```js
import { computed, ref, watch } from 'vue'
import { formatSize } from '../utils/fileSize.js'
```

(extend the existing `import { ref, watch } from 'vue'`), and below `newTag`:

```js
const fileExt = computed(() => {
  const parts = props.asset.filename.split('.')
  return parts.length > 1 ? parts.pop().toUpperCase() : ''
})
```

3e. Style — append:

```css
.file-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-width: 300px;
  min-height: 200px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 2rem 3rem;
}

.file-ext-big {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}

.file-panel-name {
  color: var(--color-text-primary);
  word-break: break-all;
}

.file-panel-size {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.download-btn {
  display: inline-block;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-size: 0.875rem;
  text-decoration: none;
  background: var(--color-accent);
  color: white;
  cursor: pointer;
  transition: background-color 150ms;
}

.download-btn:hover {
  background: var(--color-accent-hover);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: ALL PASS (existing AssetDetail specs use image assets — `asset.width` set — so the guarded Size row still renders for them).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue web/frontend/tests/AssetDetail.test.js
git commit -m "feat: download button and file panel in asset detail"
```

---

### Task 10: Frontend — FontTester (live type tester)

**Files:**
- Create: `web/frontend/src/components/FontTester.vue`
- Modify: `web/frontend/src/components/AssetDetail.vue` (font branch)
- Test: `web/frontend/tests/FontTester.test.js`, `web/frontend/tests/AssetDetail.test.js`

**Interfaces:**
- Consumes: `/api/asset/{id}/file` (Task 5) via the browser `FontFace` API.
- Produces: `<FontTester :asset-id :api-base>` — editable sample text rendered at 16/32/64px in the loaded font; error state when the font can't load.

- [ ] **Step 1: Write the failing tests**

Create `web/frontend/tests/FontTester.test.js`:

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FontTester from '../src/components/FontTester.vue'

describe('FontTester', () => {
  beforeEach(() => {
    vi.stubGlobal('FontFace', class {
      constructor(family, source) {
        this.family = family
        this.source = source
      }
      load() { return Promise.resolve(this) }
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('loads the font and renders the sample at three sizes', async () => {
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    const specimens = wrapper.findAll('.specimen')
    expect(specimens).toHaveLength(3)
    expect(specimens[0].attributes('style')).toContain('font-size: 16px')
    expect(specimens[2].attributes('style')).toContain('font-size: 64px')
    expect(specimens[0].attributes('style')).toContain('asset-font-7')
  })

  it('re-renders specimens when the sample text is edited', async () => {
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    await wrapper.find('.sample-input').setValue('Hello 123')
    expect(wrapper.find('.specimen').text()).toBe('Hello 123')
  })

  it('shows an error state when the font fails to load', async () => {
    vi.stubGlobal('FontFace', class {
      load() { return Promise.reject(new Error('bad font')) }
    })
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    expect(wrapper.find('.tester-error').exists()).toBe(true)
    expect(wrapper.findAll('.specimen')).toHaveLength(0)
  })
})
```

Append to `web/frontend/tests/AssetDetail.test.js` (inside a new describe; FontFace stub as above):

```js
describe('AssetDetail font kind', () => {
  beforeEach(() => {
    vi.stubGlobal('FontFace', class {
      load() { return Promise.resolve(this) }
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders the type tester for fonts', () => {
    const fontAsset = {
      id: 6, filename: 'pixel.ttf', path: 'Fonts/pixel.ttf', pack: 'Fonts',
      kind: 'font', file_size: 900, width: null, height: null, tags: ['font'], colors: [],
    }
    const wrapper = mount(AssetDetail, { props: { asset: fontAsset } })
    expect(wrapper.findComponent({ name: 'FontTester' }).exists()).toBe(true)
    expect(wrapper.find('.download-btn').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: FAIL — `FontTester.vue` doesn't exist.

- [ ] **Step 3: Create `web/frontend/src/components/FontTester.vue`**

```vue
<!-- web/frontend/src/components/FontTester.vue -->
<template>
  <div class="font-tester">
    <input
      v-model="sample"
      class="sample-input"
      placeholder="Type to preview…"
    />
    <div v-if="error" class="tester-error">Couldn't load font preview</div>
    <div v-else-if="loaded" class="specimens">
      <p
        v-for="size in SIZES"
        :key="size"
        class="specimen"
        :style="{ fontFamily: family, fontSize: size + 'px' }"
      >{{ sample }}</p>
    </div>
    <div v-else class="tester-loading">Loading font…</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  assetId: { type: Number, required: true },
  apiBase: { type: String, required: true },
})

const SIZES = [16, 32, 64]
const sample = ref('The quick brown fox 0123456789')
const loaded = ref(false)
const error = ref(false)
const family = `asset-font-${props.assetId}`

onMounted(async () => {
  try {
    const face = new FontFace(family, `url(${props.apiBase}/asset/${props.assetId}/file)`)
    await face.load()
    document.fonts?.add(face)
    loaded.value = true
  } catch {
    error.value = true
  }
})
</script>

<style scoped>
.font-tester {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.5rem;
}

.sample-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.875rem;
}

.specimens {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-x: auto;
}

.specimen {
  margin: 0;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.tester-loading,
.tester-error {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.tester-error {
  color: var(--color-danger);
}
</style>
```

- [ ] **Step 4: Wire into `AssetDetail.vue`**

Add the branch between `ModelViewer` and the file panel:

```html
      <FontTester
        v-else-if="asset.kind === 'font'"
        :asset-id="asset.id"
        :api-base="API_BASE"
      />
```

Add the import next to `ModelViewer`:

```js
import FontTester from './FontTester.vue'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/FontTester.vue web/frontend/src/components/AssetDetail.vue web/frontend/tests/FontTester.test.js web/frontend/tests/AssetDetail.test.js
git commit -m "feat: live font type tester in asset detail"
```

---

### Task 11: Docs + full verification

**Files:**
- Modify: `README.md` (Supported Formats + API Endpoints sections)

**Interfaces:** none (documentation + verification only).

- [ ] **Step 1: Update README.md**

Replace the Supported Formats section:

```markdown
## Supported Formats

- **Images:** PNG, GIF, JPG, WEBP, Aseprite (.ase, .aseprite)
- **3D models:** glTF (.glb, .gltf)
- **Fonts:** TTF, OTF, WOFF, WOFF2 (specimen previews + live type tester)
- **Anything else** is indexed as a downloadable file asset (shaders,
  .blend files, archives, ...). OS/engine junk (.DS_Store, *.import,
  *.meta, ...) is skipped.
```

Add to the API Endpoints list:

```markdown
- `GET /api/asset/{id}/file` - Raw asset file (`?download=true` forces attachment)
```

- [ ] **Step 2: Run the complete verification suite**

```bash
just test
cd web/frontend && npm test
```

Expected: everything passes (Blender-dependent tests may skip).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: font and anyfile support in README"
```

---

## Self-Review Notes (resolved during planning)

- Spec said to delete `index_asset()` if unreferenced — it IS referenced by `test_index.py:719-818`, so it stays untouched (Global Constraints).
- Spec's "montage falls back to font specimens" is implemented as padding: PNGs first, then specimens, threshold ≥4 combined (Task 4).
- The catch-all changes what existing fixtures index (`_AnimationInfo.txt`, `.bin` siblings) — Task 3 Step 4 handles the count-assertion fallout explicitly.
- `is_3d` removal is deferred to Task 8 so Tasks 6-7 land green independently.
