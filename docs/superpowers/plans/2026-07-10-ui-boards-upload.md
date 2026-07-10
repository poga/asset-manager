# UI-Created Boards (Pinterest-style upload) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users create asset packs ("boards") in the web UI and upload images into them, Pinterest-style, without disturbing the disk-indexed asset packs.

**Architecture:** Boards reuse the existing `packs`/`assets` tables, distinguished by a new `packs.source='user'` flag. Board files live under `assets/.boards/<slug>/` (a hidden dir the CLI scanner skips), so `/api/image` serves them unchanged and reindex never touches them. The FastAPI app gains write endpoints (create/upload/rename/cover/delete/tag); the Vue frontend gains a "New board" affordance, a `BoardView` wrapper around the existing `AssetGrid`, and board-image actions in `AssetDetail`.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Pillow (backend); Vue 3, Vite, Vitest (frontend). `uv` runs everything Python.

## Global Constraints

- Run Python via `uv run` (never bare `python`). API (8000) and frontend (5173) are assumed already running — do not start them.
- Backend tests: real FastAPI app + temp DB + temp assets dir + real image bytes. NO MOCKS.
- Frontend tests: follow the existing Vitest pattern (`mount` + assert emitted events / DOM; `vi.fn()` for `fetch` where a component fetches). This mirrors the repo's current tests.
- Comments: at most one line (≤80 chars), minimal, explain "why" not "how".
- Board files: `assets/.boards/<slug>/<uuid>.<ext>`. Board pack rows: `source='user'`, `path='.boards/<slug>'`.
- Uploads: accept `png`, `jpg`, `jpeg`, `gif`, `webp`; reject files larger than 20 MB.
- Reindex isolation: `scan_assets` must skip any path segment starting with `.` (covers `.boards/`).
- Board images get NO color/phash rows (lightweight reference content).
- TDD, DRY, YAGNI, frequent commits.

**Reference spec:** `docs/superpowers/specs/2026-07-10-ui-boards-upload-design.md`

**Test commands (from repo root unless noted):**
- Backend file: `uv run --script web/test_boards.py` (runs `pytest.main([__file__, "-v"])` at file bottom).
- Existing backend: `uv run --script web/test_api.py`, `uv run --script test_index.py`.
- Frontend: `cd web/frontend && npx vitest run tests/<file>` (or `npm run test` for all).

---

### Task 1: Add `source` column and surface `is_board`

Adds the board flag to the schema (fresh + legacy DBs) and exposes it plus the pack `id` through `/api/filters` so the frontend can badge boards and address them.

**Files:**
- Modify: `index.py` — `SCHEMA` packs block (~line 64), `migrate_schema` (~line 169)
- Modify: `web/api.py` — add `_ensure_board_columns` helper near `_ensure_pack_tags` (~line 128); `filters()` (~line 435)
- Test: `web/test_boards.py` (create)

**Interfaces:**
- Produces: `_ensure_board_columns(conn)` — idempotently adds `packs.source TEXT DEFAULT 'indexed'`. `/api/filters` packs items gain `"id": int` and `"is_board": bool`.

- [ ] **Step 1: Write the failing test**

Create `web/test_boards.py`:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
#     "pillow>=10.0",
# ]
# ///
"""Tests for UI-created boards."""

import io
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import api

client = TestClient(api.app)


def _make_db(dir_path: Path) -> Path:
    db_path = dir_path / "assets.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
            version TEXT, theme TEXT, preview_path TEXT, preview_generated BOOLEAN DEFAULT FALSE,
            asset_count INTEGER DEFAULT 0, source TEXT DEFAULT 'indexed'
        );
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL, filetype TEXT NOT NULL, file_hash TEXT NOT NULL,
            file_size INTEGER, width INTEGER, height INTEGER,
            preview_x INTEGER, preview_y INTEGER, preview_width INTEGER, preview_height INTEGER,
            category TEXT, asset_kind TEXT DEFAULT 'image', rig TEXT, thumbnail_path TEXT
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        assets_dir = root / "assets"
        assets_dir.mkdir()
        db_path = _make_db(root)
        api.set_db_path(db_path)
        api.set_assets_path(assets_dir)
        yield {"root": root, "assets": assets_dir, "db": db_path}
        api.set_db_path(None)
        api.set_assets_path(None)


def png_bytes(color=(255, 0, 0), size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_filters_marks_board_packs(env):
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('Indexed Pack', 'p1', 'indexed')")
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('My Board', '.boards/my-board', 'user')")
    conn.commit()
    conn.close()

    data = client.get("/api/filters").json()
    by_name = {p["name"]: p for p in data["packs"]}
    assert by_name["My Board"]["is_board"] is True
    assert by_name["Indexed Pack"]["is_board"] is False
    assert isinstance(by_name["My Board"]["id"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — `test_filters_marks_board_packs` KeyError `is_board` (filters doesn't return it yet).

- [ ] **Step 3: Add the schema/migration + filters changes**

In `index.py` `SCHEMA`, add `source` to the packs block (after `asset_count`):

```python
    asset_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'indexed',
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

In `index.py` `migrate_schema`, inside the `if "packs" in tables:` block after the `theme` check:

```python
        if "source" not in existing:
            conn.execute("ALTER TABLE packs ADD COLUMN source TEXT DEFAULT 'indexed'")
```

In `web/api.py`, add after `_ensure_pack_tags`:

```python
def _ensure_board_columns(conn: sqlite3.Connection) -> None:
    """Lazily add the board flag so pre-existing DBs work without a reindex."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(packs)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE packs ADD COLUMN source TEXT DEFAULT 'indexed'")
```

In `web/api.py` `filters()`, call the ensure and add the columns. Replace the packs query + dict build:

```python
    _ensure_board_columns(conn)
    packs = conn.execute("""
        SELECT p.id, p.name, p.source, p.asset_count AS count,
               EXISTS (SELECT 1 FROM assets a
                       WHERE a.pack_id = p.id
                         AND a.asset_kind IN ('model', 'animation_bundle')) AS is_3d
        FROM packs p
        ORDER BY p.name
    """).fetchall()
```

and in the returned `"packs": [...]` comprehension add the two fields:

```python
            {
                "id": p["id"],
                "name": p["name"],
                "count": p["count"],
                "is_3d": bool(p["is_3d"]),
                "is_board": p["source"] == "user",
                "tags": pack_tag_map.get(p["id"], []),
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.
Run: `uv run --script web/test_api.py`
Expected: PASS (existing filters test still green; `_ensure_board_columns` adds the column to its fixture DB).

- [ ] **Step 5: Commit**

```bash
git add index.py web/api.py web/test_boards.py
git commit -m "feat: add packs.source flag and expose is_board in filters"
```

---

### Task 2: Scanner skips hidden dirs (reindex isolation)

Guarantees the CLI indexer never scans, re-pipelines, or prunes board files.

**Files:**
- Modify: `index.py` — `scan_assets` (~line 508)
- Test: `test_index.py` (add one test)

**Interfaces:**
- Produces: `scan_assets(asset_root)` excludes any file with a `.`-prefixed path segment relative to `asset_root`.

- [ ] **Step 1: Write the failing test**

Add to `test_index.py` (near other `scan_assets`/index tests; use its existing imports of `index` and `tempfile`/`Path`):

```python
def test_scan_assets_skips_hidden_dirs():
    import index
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "pack").mkdir()
        (root / "pack" / "y.png").write_bytes(b"\x89PNG\r\n")
        (root / ".boards" / "b").mkdir(parents=True)
        (root / ".boards" / "b" / "x.png").write_bytes(b"\x89PNG\r\n")
        found = {p.name for p in index.scan_assets(root)}
        assert "y.png" in found
        assert "x.png" not in found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script test_index.py`
Expected: FAIL — `x.png` is currently included.

- [ ] **Step 3: Implement the skip**

Replace `scan_assets` body in `index.py`:

```python
def scan_assets(asset_root: Path) -> list[Path]:
    """Scan directory for image, Aseprite, and 3D model files."""
    def visible(p: Path) -> bool:
        return not any(part.startswith(".") for part in p.relative_to(asset_root).parts)

    image_assets: list[Path] = []
    model_assets: list[Path] = []
    for ext in IMAGE_EXTENSIONS | ASEPRITE_EXTENSIONS:
        image_assets.extend(p for p in asset_root.rglob(f"*{ext}") if visible(p))
    for ext in MODEL_EXTENSIONS:
        model_assets.extend(p for p in asset_root.rglob(f"*{ext}") if visible(p))
    model_assets = model_indexer.filter_canonical_models(sorted(model_assets))
    return sorted(image_assets + model_assets)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --script test_index.py`
Expected: PASS (new test green, existing tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add index.py test_index.py
git commit -m "feat: scanner skips hidden dirs so reindex ignores boards"
```

---

### Task 3: Board domain helpers (`web/boards.py`)

A focused, testable unit for slugs, storage paths, upload validation, file writing, and asset-row insertion. Keeps `api.py` thin.

**Files:**
- Create: `web/boards.py`
- Test: `web/test_boards.py` (add tests)

**Interfaces:**
- Produces:
  - `BOARD_ROOT = ".boards"`, `ALLOWED_EXTS = {"png","jpg","jpeg","gif","webp"}`, `MAX_UPLOAD_BYTES = 20 * 1024 * 1024`
  - `slugify(name: str) -> str`
  - `unique_slug(conn, name: str) -> str` — appends `-2`, `-3`… if `.boards/<slug>` path already taken
  - `board_dir(assets_root: Path, slug: str) -> Path`
  - `validate_upload(filename: str, data: bytes) -> str` — returns lowercased ext (no dot) or raises `ValueError`
  - `save_image(assets_root: Path, slug: str, data: bytes, ext: str) -> tuple[str, int, int]` — returns `(rel_path_posix, width, height)`; writes `<uuid>.<ext>`
  - `insert_board_asset(conn, pack_id, rel_path, filename, ext, size, width, height) -> int` — returns asset id

- [ ] **Step 1: Write the failing tests**

Add to `web/test_boards.py`:

```python
def test_slugify_and_unique(env):
    import boards
    assert boards.slugify("My Cool Board!") == "my-cool-board"
    assert boards.slugify("  A/B  c ") == "a-b-c"
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('x', '.boards/my-board', 'user')")
    conn.commit()
    assert boards.unique_slug(conn, "My Board") == "my-board-2"
    conn.close()


def test_validate_upload(env):
    import boards
    assert boards.validate_upload("a.PNG", png_bytes()) == "png"
    with pytest.raises(ValueError):
        boards.validate_upload("a.svg", b"<svg/>")
    with pytest.raises(ValueError):
        boards.validate_upload("a.png", b"x" * (boards.MAX_UPLOAD_BYTES + 1))


def test_save_image_writes_file_and_dims(env):
    import boards
    rel, w, h = boards.save_image(env["assets"], "my-board", png_bytes(size=(12, 7)), "png")
    assert rel.startswith(".boards/my-board/")
    assert rel.endswith(".png")
    assert (env["assets"] / rel).exists()
    assert (w, h) == (12, 7)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — `import boards` ModuleNotFoundError.

- [ ] **Step 3: Implement `web/boards.py`**

```python
"""Domain helpers for UI-created boards."""

import io
import re
import sqlite3
import uuid
from pathlib import Path

from PIL import Image

BOARD_ROOT = ".boards"
ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def slugify(name: str) -> str:
    """Lowercase, non-alphanumerics to single dashes, trimmed."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return s.strip("-") or "board"


def unique_slug(conn: sqlite3.Connection, name: str) -> str:
    """Slug whose .boards/<slug> path is not already used by a pack."""
    base = slugify(name)
    slug, n = base, 1
    while conn.execute(
        "SELECT 1 FROM packs WHERE path = ?", [f"{BOARD_ROOT}/{slug}"]
    ).fetchone():
        n += 1
        slug = f"{base}-{n}"
    return slug


def board_dir(assets_root: Path, slug: str) -> Path:
    return assets_root / BOARD_ROOT / slug


def validate_upload(filename: str, data: bytes) -> str:
    """Return the lowercased extension or raise ValueError."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported type: {ext}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large")
    return ext


def save_image(assets_root: Path, slug: str, data: bytes, ext: str) -> tuple[str, int, int]:
    """Write bytes under the board dir; return (rel_path, width, height)."""
    d = board_dir(assets_root, slug)
    d.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (d / name).write_bytes(data)
    with Image.open(io.BytesIO(data)) as img:
        w, h = img.size
    return f"{BOARD_ROOT}/{slug}/{name}", w, h


def insert_board_asset(
    conn: sqlite3.Connection, pack_id: int, rel_path: str,
    filename: str, ext: str, size: int, width: int, height: int,
) -> int:
    """Insert an asset row for a board image (full-image preview bounds)."""
    cur = conn.execute(
        """INSERT INTO assets
           (pack_id, path, filename, filetype, file_hash, file_size,
            width, height, preview_x, preview_y, preview_width, preview_height,
            category, asset_kind)
           VALUES (?, ?, ?, ?, '', ?, ?, ?, 0, 0, ?, ?, '', 'image')""",
        [pack_id, rel_path, filename, ext, size, width, height, width, height],
    )
    return cur.lastrowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/boards.py web/test_boards.py
git commit -m "feat: board domain helpers (slug, storage, validation)"
```

---

### Task 4: `POST /api/boards` — create a board

**Files:**
- Modify: `web/api.py` — add request models + endpoint + `_board_or_404` helper
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `web/boards.py` (`unique_slug`, `BOARD_ROOT`), `_ensure_board_columns`.
- Produces: `POST /api/boards` body `{name: str, tags?: list[str]}` → `{id, name, path}` (201). Duplicate name → 409. `_board_or_404(conn, board_id) -> sqlite3.Row`.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def test_create_board(env):
    r = client.post("/api/boards", json={"name": "My Board", "tags": ["inspo"]})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "My Board"
    assert body["path"] == ".boards/my-board"
    conn = sqlite3.connect(env["db"])
    row = conn.execute("SELECT source FROM packs WHERE id = ?", [body["id"]]).fetchone()
    assert row[0] == "user"
    tag = conn.execute(
        "SELECT tag FROM pack_tags WHERE pack_id = ?", [body["id"]]
    ).fetchone()
    conn.close()
    assert tag[0] == "inspo"


def test_create_board_duplicate_name(env):
    client.post("/api/boards", json={"name": "Dup"})
    r = client.post("/api/boards", json={"name": "Dup"})
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — 404/405 (endpoint missing).

- [ ] **Step 3: Implement the endpoint**

In `web/api.py`, add near the top imports:

```python
import boards as boards_mod
```

Add request models near the other `BaseModel`s:

```python
class BoardCreateRequest(BaseModel):
    name: str
    tags: list[str] = []


class BoardPatchRequest(BaseModel):
    name: Optional[str] = None
    cover_asset_id: Optional[int] = None


class AssetTagRequest(BaseModel):
    tag: str
```

Add the helper near `_pack_id_or_404`:

```python
def _board_or_404(conn: sqlite3.Connection, board_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM packs WHERE id = ? AND source = 'user'", [board_id]
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Board not found")
    return row
```

Add the endpoint (place board endpoints together, after the pack-tag endpoints):

```python
@app.post("/api/boards", status_code=201)
def create_board(request: BoardCreateRequest):
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty name")
    conn = get_db()
    _ensure_board_columns(conn)
    _ensure_pack_tags(conn)
    if conn.execute("SELECT 1 FROM packs WHERE name = ?", [name]).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Name already exists")
    slug = boards_mod.unique_slug(conn, name)
    path = f"{boards_mod.BOARD_ROOT}/{slug}"
    cur = conn.execute(
        "INSERT INTO packs (name, path, source, asset_count) VALUES (?, ?, 'user', 0)",
        [name, path],
    )
    board_id = cur.lastrowid
    for tag in request.tags:
        t = tag.strip().lower()
        if t:
            conn.execute(
                "INSERT OR IGNORE INTO pack_tags (pack_id, tag) VALUES (?, ?)",
                [board_id, t],
            )
    conn.commit()
    conn.close()
    return {"id": board_id, "name": name, "path": path}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: POST /api/boards to create a board"
```

---

### Task 5: `POST /api/boards/{id}/images` — upload images

**Files:**
- Modify: `web/api.py` — endpoint; import `UploadFile, File`
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `web/boards.py` (`validate_upload`, `save_image`, `insert_board_asset`, `board_dir`), `_board_or_404`.
- Produces: `POST /api/boards/{id}/images` multipart field `files` (1+). Returns `{"assets": [{id, path, filename, width, height}], "cover_asset_id": int}`. First upload to a coverless board sets `preview_path`. Bad type/size → 400 with no partial rows. Missing board → 404.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def _create(name="Board"):
    return client.post("/api/boards", json={"name": name}).json()


def test_upload_images_creates_rows_and_files(env):
    board = _create("Uploads")
    files = [
        ("files", ("a.png", png_bytes((255, 0, 0)), "image/png")),
        ("files", ("b.png", png_bytes((0, 255, 0)), "image/png")),
    ]
    r = client.post(f"/api/boards/{board['id']}/images", files=files)
    assert r.status_code == 201
    body = r.json()
    assert len(body["assets"]) == 2
    for a in body["assets"]:
        assert (env["assets"] / a["path"]).exists()
    conn = sqlite3.connect(env["db"])
    prev = conn.execute(
        "SELECT preview_path FROM packs WHERE id = ?", [board["id"]]
    ).fetchone()[0]
    conn.close()
    assert prev == body["cover_asset_path"] == body["assets"][0]["path"]


def test_upload_rejects_bad_type(env):
    board = _create("Bad")
    r = client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.svg", b"<svg/>", "image/svg+xml"))],
    )
    assert r.status_code == 400
    conn = sqlite3.connect(env["db"])
    n = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()
    assert n == 0


def test_upload_missing_board_404(env):
    r = client.post("/api/boards/999/images",
                    files=[("files", ("a.png", png_bytes(), "image/png"))])
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement the endpoint**

In `web/api.py`, extend the FastAPI import:

```python
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
```

Add the endpoint:

```python
@app.post("/api/boards/{board_id}/images", status_code=201)
def upload_board_images(board_id: int, files: list[UploadFile] = File(...)):
    conn = get_db()
    _ensure_board_columns(conn)
    board = _board_or_404(conn, board_id)
    slug = board["path"].split("/", 1)[1]
    assets_root = get_assets_path()

    # validate all before writing so a bad file writes nothing
    payloads = []
    for f in files:
        data = f.file.read()
        try:
            ext = boards_mod.validate_upload(f.filename, data)
        except ValueError as e:
            conn.close()
            raise HTTPException(status_code=400, detail=str(e))
        payloads.append((f.filename, data, ext))

    created = []
    for filename, data, ext in payloads:
        rel, w, h = boards_mod.save_image(assets_root, slug, data, ext)
        asset_id = boards_mod.insert_board_asset(
            conn, board_id, rel, filename, ext, len(data), w, h
        )
        created.append({"id": asset_id, "path": rel, "filename": filename,
                        "width": w, "height": h})

    conn.execute(
        "UPDATE packs SET asset_count = (SELECT COUNT(*) FROM assets WHERE pack_id = ?) WHERE id = ?",
        [board_id, board_id],
    )
    cover_id, cover_path = None, None
    if not board["preview_path"] and created:
        cover_path = created[0]["path"]
        cover_id = created[0]["id"]
        conn.execute("UPDATE packs SET preview_path = ? WHERE id = ?", [cover_path, board_id])
    conn.commit()
    conn.close()
    return {"assets": created, "cover_asset_id": cover_id, "cover_asset_path": cover_path}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: POST /api/boards/{id}/images upload endpoint"
```

---

### Task 6: `PATCH /api/boards/{id}` — rename and set cover

**Files:**
- Modify: `web/api.py` — endpoint
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `_board_or_404`, `BoardPatchRequest`.
- Produces: `PATCH /api/boards/{id}` body `{name?, cover_asset_id?}`. Rename updates `packs.name` only (path/slug unchanged); duplicate new name → 409. `cover_asset_id` must belong to the board (else 400); sets `preview_path` to that asset's path. Returns `{id, name, path, preview_path}`.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def test_rename_board(env):
    board = _create("Old Name")
    r = client.patch(f"/api/boards/{board['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"
    assert r.json()["path"] == ".boards/old-name"  # slug fixed


def test_set_cover(env):
    board = _create("Cover")
    up = client.post(
        f"/api/boards/{board['id']}/images",
        files=[
            ("files", ("a.png", png_bytes((1, 1, 1)), "image/png")),
            ("files", ("b.png", png_bytes((2, 2, 2)), "image/png")),
        ],
    ).json()
    second = up["assets"][1]["id"]
    r = client.patch(f"/api/boards/{board['id']}", json={"cover_asset_id": second})
    assert r.status_code == 200
    assert r.json()["preview_path"] == up["assets"][1]["path"]


def test_set_cover_foreign_asset_400(env):
    board = _create("Guard")
    r = client.patch(f"/api/boards/{board['id']}", json={"cover_asset_id": 12345})
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — endpoint missing.

- [ ] **Step 3: Implement the endpoint**

```python
@app.patch("/api/boards/{board_id}")
def patch_board(board_id: int, request: BoardPatchRequest):
    conn = get_db()
    _ensure_board_columns(conn)
    board = _board_or_404(conn, board_id)
    name = board["name"]
    if request.name is not None:
        name = request.name.strip()
        if not name:
            conn.close()
            raise HTTPException(status_code=400, detail="Empty name")
        clash = conn.execute(
            "SELECT 1 FROM packs WHERE name = ? AND id != ?", [name, board_id]
        ).fetchone()
        if clash:
            conn.close()
            raise HTTPException(status_code=409, detail="Name already exists")
        conn.execute("UPDATE packs SET name = ? WHERE id = ?", [name, board_id])
    preview_path = board["preview_path"]
    if request.cover_asset_id is not None:
        row = conn.execute(
            "SELECT path FROM assets WHERE id = ? AND pack_id = ?",
            [request.cover_asset_id, board_id],
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=400, detail="Asset not in board")
        preview_path = row["path"]
        conn.execute("UPDATE packs SET preview_path = ? WHERE id = ?", [preview_path, board_id])
    conn.commit()
    conn.close()
    return {"id": board_id, "name": name, "path": board["path"], "preview_path": preview_path}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: PATCH /api/boards/{id} for rename and cover"
```

---

### Task 7: Board cover serving

Make `/api/pack-preview/{name}` serve a board's chosen cover from `preview_path`.

**Files:**
- Modify: `web/api.py` — `pack_preview` (~line 619)
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `get_assets_path`, `_ensure_board_columns`.
- Produces: `/api/pack-preview/{name}` returns the board cover image bytes when the pack is a board with a `preview_path` file on disk; otherwise unchanged `.index/previews` behavior.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def test_pack_preview_serves_board_cover(env):
    board = _create("Preview Board")
    client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.png", png_bytes((9, 9, 9)), "image/png"))],
    )
    r = client.get("/api/pack-preview/Preview%20Board")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — 404 (falls through to `.index/previews`).

- [ ] **Step 3: Implement the branch**

In `web/api.py` `pack_preview`, after decoding `pack_name` and before the `.index/previews` checks, add:

```python
    conn = get_db()
    _ensure_board_columns(conn)
    row = conn.execute(
        "SELECT preview_path FROM packs WHERE name = ? AND source = 'user'", [pack_name]
    ).fetchone()
    conn.close()
    if row and row["preview_path"]:
        cover = get_assets_path() / row["preview_path"]
        if cover.exists():
            media = "image/gif" if cover.suffix.lower() == ".gif" else "image/png"
            if cover.suffix.lower() in (".jpg", ".jpeg"):
                media = "image/jpeg"
            elif cover.suffix.lower() == ".webp":
                media = "image/webp"
            return FileResponse(cover, media_type=media)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py` then `uv run --script web/test_api.py`
Expected: PASS (existing pack-preview test still green — non-board packs skip the branch).

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: serve board cover via pack-preview"
```

---

### Task 8: Delete image and delete board

**Files:**
- Modify: `web/api.py` — two endpoints
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `_board_or_404`, `board_dir`, `get_assets_path`.
- Produces:
  - `DELETE /api/asset/{id}` — removes a board image (row + tag links + file). Non-board asset → 400. Missing → 404. Returns `{deleted: id}`.
  - `DELETE /api/boards/{id}` — removes board row, its asset rows + tag links, its pack_tags, and its directory. Returns `{deleted: id}`.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def test_delete_board_image(env):
    board = _create("Del")
    up = client.post(
        f"/api/boards/{board['id']}/images",
        files=[("files", ("a.png", png_bytes(), "image/png"))],
    ).json()
    a = up["assets"][0]
    r = client.delete(f"/api/asset/{a['id']}")
    assert r.status_code == 200
    assert not (env["assets"] / a["path"]).exists()
    conn = sqlite3.connect(env["db"])
    n = conn.execute("SELECT COUNT(*) FROM assets WHERE id = ?", [a["id"]]).fetchone()[0]
    conn.close()
    assert n == 0


def test_delete_asset_refuses_indexed(env):
    conn = sqlite3.connect(env["db"])
    conn.execute("INSERT INTO packs (name, path, source) VALUES ('P', 'p', 'indexed')")
    pid = conn.execute("SELECT id FROM packs WHERE path='p'").fetchone()[0]
    conn.execute(
        "INSERT INTO assets (pack_id, path, filename, filetype, file_hash) "
        "VALUES (?, 'p/x.png', 'x.png', 'png', 'h')", [pid])
    aid = conn.execute("SELECT id FROM assets WHERE path='p/x.png'").fetchone()[0]
    conn.commit(); conn.close()
    r = client.delete(f"/api/asset/{aid}")
    assert r.status_code == 400


def test_delete_board(env):
    board = _create("Whole")
    client.post(f"/api/boards/{board['id']}/images",
                files=[("files", ("a.png", png_bytes(), "image/png"))])
    r = client.delete(f"/api/boards/{board['id']}")
    assert r.status_code == 200
    assert not (env["assets"] / ".boards" / "whole").exists()
    conn = sqlite3.connect(env["db"])
    assert conn.execute("SELECT COUNT(*) FROM packs WHERE id = ?", [board["id"]]).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assets WHERE pack_id = ?", [board["id"]]).fetchone()[0] == 0
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — endpoints missing (405/404).

- [ ] **Step 3: Implement the endpoints**

```python
@app.delete("/api/asset/{asset_id}")
def delete_asset(asset_id: int):
    conn = get_db()
    _ensure_board_columns(conn)
    row = conn.execute(
        """SELECT a.path, a.pack_id, p.source FROM assets a
           JOIN packs p ON a.pack_id = p.id WHERE a.id = ?""",
        [asset_id],
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")
    if row["source"] != "user":
        conn.close()
        raise HTTPException(status_code=400, detail="Not a board asset")
    pack_id = row["pack_id"]
    conn.execute("DELETE FROM asset_tags WHERE asset_id = ?", [asset_id])
    conn.execute("DELETE FROM assets WHERE id = ?", [asset_id])
    conn.execute(
        "UPDATE packs SET asset_count = (SELECT COUNT(*) FROM assets WHERE pack_id = ?) WHERE id = ?",
        [pack_id, pack_id],
    )
    conn.commit()
    conn.close()
    f = get_assets_path() / row["path"]
    if f.exists():
        f.unlink()
    return {"deleted": asset_id}


@app.delete("/api/boards/{board_id}")
def delete_board(board_id: int):
    import shutil
    conn = get_db()
    _ensure_board_columns(conn)
    board = _board_or_404(conn, board_id)
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM assets WHERE pack_id = ?", [board_id])]
    for aid in ids:
        conn.execute("DELETE FROM asset_tags WHERE asset_id = ?", [aid])
    conn.execute("DELETE FROM assets WHERE pack_id = ?", [board_id])
    conn.execute("DELETE FROM pack_tags WHERE pack_id = ?", [board_id])
    conn.execute("DELETE FROM packs WHERE id = ?", [board_id])
    conn.commit()
    conn.close()
    slug = board["path"].split("/", 1)[1]
    d = boards_mod.board_dir(get_assets_path(), slug)
    if d.exists():
        shutil.rmtree(d)
    return {"deleted": board_id}
```

Note: `DELETE /api/asset/{id}` uses `_ensure_pack_tags` indirectly only if pack_tags exist; asset_tags always exists in schema. If a board has no images, `_ensure_pack_tags` isn't required for delete_board because pack_tags may be absent on legacy DBs — guard by ensuring pack_tags first:

Add `_ensure_pack_tags(conn)` immediately after `_ensure_board_columns(conn)` in `delete_board`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: delete board image and delete board endpoints"
```

---

### Task 9: Image tags + board fields on asset detail

**Files:**
- Modify: `web/api.py` — two tag endpoints; extend `asset_detail` return
- Test: `web/test_boards.py`

**Interfaces:**
- Consumes: `AssetTagRequest`, `_ensure_board_columns`.
- Produces:
  - `POST /api/asset/{id}/tags` body `{tag}` → `{tags: [...]}` (idempotent, source `'user'`).
  - `DELETE /api/asset/{id}/tags/{tag}` → `{tags: [...]}`.
  - `GET /api/asset/{id}` gains `"is_board": bool` and `"board_id": int|None`.

- [ ] **Step 1: Write the failing test**

Add to `web/test_boards.py`:

```python
def test_image_tags_roundtrip(env):
    board = _create("Tagged")
    up = client.post(f"/api/boards/{board['id']}/images",
                     files=[("files", ("a.png", png_bytes(), "image/png"))]).json()
    aid = up["assets"][0]["id"]
    r = client.post(f"/api/asset/{aid}/tags", json={"tag": "Inspo"})
    assert r.status_code == 200
    assert "inspo" in r.json()["tags"]
    r = client.delete(f"/api/asset/{aid}/tags/inspo")
    assert r.status_code == 200
    assert "inspo" not in r.json()["tags"]


def test_asset_detail_reports_board(env):
    board = _create("Detail")
    up = client.post(f"/api/boards/{board['id']}/images",
                     files=[("files", ("a.png", png_bytes(), "image/png"))]).json()
    d = client.get(f"/api/asset/{up['assets'][0]['id']}").json()
    assert d["is_board"] is True
    assert d["board_id"] == board["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --script web/test_boards.py`
Expected: FAIL — tag endpoints missing / `is_board` key absent.

- [ ] **Step 3: Implement**

Tag endpoints:

```python
@app.post("/api/asset/{asset_id}/tags")
def add_asset_tag(asset_id: int, request: AssetTagRequest):
    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Empty tag")
    conn = get_db()
    if not conn.execute("SELECT 1 FROM assets WHERE id = ?", [asset_id]).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", [tag])
    tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", [tag]).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO asset_tags (asset_id, tag_id, source) VALUES (?, ?, 'user')",
        [asset_id, tag_id],
    )
    conn.commit()
    tags = [r["name"] for r in conn.execute(
        "SELECT t.name FROM asset_tags at JOIN tags t ON at.tag_id = t.id WHERE at.asset_id = ?",
        [asset_id])]
    conn.close()
    return {"tags": tags}


@app.delete("/api/asset/{asset_id}/tags/{tag}")
def remove_asset_tag(asset_id: int, tag: str):
    conn = get_db()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", [tag.strip().lower()]).fetchone()
    if row:
        conn.execute("DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
                     [asset_id, row["id"]])
        conn.commit()
    tags = [r["name"] for r in conn.execute(
        "SELECT t.name FROM asset_tags at JOIN tags t ON at.tag_id = t.id WHERE at.asset_id = ?",
        [asset_id])]
    conn.close()
    return {"tags": tags}
```

Extend `asset_detail`: change the SELECT to include pack source, and add fields to the return. Replace the query's first line and add to the returned dict:

```python
    _ensure_board_columns(conn)
    row = conn.execute("""
        SELECT a.*, p.name as pack_name, p.source as pack_source
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE a.id = ?
    """, [asset_id]).fetchone()
```

and in the returned dict add:

```python
        "is_board": row["pack_source"] == "user",
        "board_id": row["pack_id"] if row["pack_source"] == "user" else None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_boards.py` then `uv run --script web/test_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_boards.py
git commit -m "feat: image tag endpoints and board fields on asset detail"
```

---

### Task 10: Frontend board API client + PackGallery "New board" + badge

**Files:**
- Create: `web/frontend/src/api/boards.js`
- Modify: `web/frontend/src/components/PackGallery.vue`
- Test: `web/frontend/tests/PackGallery.test.js` (extend)

**Interfaces:**
- Produces:
  - `boards.js`: `createBoard(name, tags)`, `uploadImages(boardId, fileList)`, `renameBoard(id, name)`, `setCover(id, assetId)`, `deleteBoard(id)`, `deleteImage(assetId)`, `addImageTag(assetId, tag)`, `removeImageTag(assetId, tag)` — all `async`, return parsed JSON, throw on non-ok.
  - PackGallery emits `create-board` (name string) and renders a `BOARD` badge on cards where `pack.is_board`.

- [ ] **Step 1: Write the failing test**

Add to `web/frontend/tests/PackGallery.test.js` (packs array already imported at top — add a board entry in the new test):

```javascript
  it('renders a BOARD badge on board packs', () => {
    const withBoard = [...packs, { name: 'My Board', count: 3, is_3d: false, is_board: true, tags: [], id: 9 }]
    const wrapper = mount(PackGallery, { props: { packs: withBoard } })
    expect(wrapper.text()).toContain('BOARD')
  })

  it('emits create-board when a name is entered on the new-board card', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    await wrapper.find('.new-board-card').trigger('click')
    const input = wrapper.find('.new-board-input')
    await input.setValue('Fresh Board')
    await input.trigger('keyup.enter')
    expect(wrapper.emitted('create-board')[0]).toEqual(['Fresh Board'])
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web/frontend && npx vitest run tests/PackGallery.test.js`
Expected: FAIL — no badge / no `.new-board-card`.

- [ ] **Step 3: Implement `boards.js`**

Create `web/frontend/src/api/boards.js`:

```javascript
const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

async function json(res) {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
  return res.json()
}

export function createBoard(name, tags = []) {
  return fetch(`${API_BASE}/boards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, tags })
  }).then(json)
}

export function uploadImages(boardId, fileList) {
  const form = new FormData()
  for (const f of fileList) form.append('files', f)
  return fetch(`${API_BASE}/boards/${boardId}/images`, { method: 'POST', body: form }).then(json)
}

export function renameBoard(id, name) {
  return fetch(`${API_BASE}/boards/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }).then(json)
}

export function setCover(id, coverAssetId) {
  return fetch(`${API_BASE}/boards/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cover_asset_id: coverAssetId })
  }).then(json)
}

export function deleteBoard(id) {
  return fetch(`${API_BASE}/boards/${id}`, { method: 'DELETE' }).then(json)
}

export function deleteImage(assetId) {
  return fetch(`${API_BASE}/asset/${assetId}`, { method: 'DELETE' }).then(json)
}

export function addImageTag(assetId, tag) {
  return fetch(`${API_BASE}/asset/${assetId}/tags`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag })
  }).then(json)
}

export function removeImageTag(assetId, tag) {
  return fetch(`${API_BASE}/asset/${assetId}/tags/${encodeURIComponent(tag)}`, {
    method: 'DELETE'
  }).then(json)
}
```

- [ ] **Step 4: Add the badge + new-board card to `PackGallery.vue`**

In the template, add a badge inside `.card-cover` (after the `<img>`/placeholder):

```html
            <span v-if="pack.is_board" class="board-badge">BOARD</span>
```

Add a "new board" card as the first child of the first `.card-grid` (or a standalone block above `sections`). Simplest: add above the `<section v-for>` loop:

```html
    <div class="new-board-block">
      <div v-if="!creating" class="new-board-card" @click="creating = true">+ New board</div>
      <input
        v-else
        class="new-board-input"
        v-model="boardName"
        placeholder="Board name"
        @keyup.enter="submitBoard"
        @keyup.escape="cancelBoard"
        @blur="cancelBoard"
        v-focus
      />
    </div>
```

In `<script setup>`, add state + handlers (reuse the existing `vFocus` directive) and declare the emit:

```javascript
const emit = defineEmits(['view-pack', 'create-board'])
const creating = ref(false)
const boardName = ref('')

function submitBoard() {
  const name = boardName.value.trim()
  if (name) emit('create-board', name)
  cancelBoard()
}

function cancelBoard() {
  creating.value = false
  boardName.value = ''
}
```

(Replace the existing `defineEmits(['view-pack'])` line with the `const emit = defineEmits(...)` above.)

Add styles in `<style scoped>`:

```css
.new-board-block { padding: 1rem 0 0; }
.new-board-card {
  display: inline-flex; align-items: center; gap: 0.375rem;
  padding: 0.5rem 0.875rem; border: 1px dashed var(--color-border-emphasis);
  border-radius: 8px; cursor: pointer; color: var(--color-text-secondary);
  font-size: 0.875rem;
}
.new-board-card:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
.new-board-input {
  padding: 0.5rem 0.75rem; border: 1px solid var(--color-accent);
  border-radius: 8px; background: var(--color-bg-surface); color: var(--color-text-primary);
}
.card-cover { position: relative; }
.board-badge {
  position: absolute; top: 0.5rem; left: 0.5rem;
  background: var(--color-accent); color: #fff; font-size: 0.625rem;
  font-weight: 700; letter-spacing: 0.04em; padding: 0.125rem 0.375rem; border-radius: 4px;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web/frontend && npx vitest run tests/PackGallery.test.js`
Expected: PASS (existing PackGallery tests still green).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/api/boards.js web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js
git commit -m "feat: board API client, New board card, BOARD badge"
```

---

### Task 11: BoardView component + App wiring

Renders a board: header (name, rename, delete), a drop zone + "Add images" button, wrapping the existing `AssetGrid`. Wires App to create boards, detect a board pack, and refresh after mutations.

**Files:**
- Create: `web/frontend/src/components/BoardView.vue`
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/BoardView.test.js` (create)

**Interfaces:**
- Consumes: `AssetGrid.vue`, `boards.js`.
- Produces: `BoardView` props `{ board: {id,name}, assets, cartIds, loading }`; emits `select`, `add-to-cart`, `load-more`, `view-pack`, `changed` (after upload/rename), `deleted` (after board delete). Uploads via `uploadImages`; on success emits `changed`.

- [ ] **Step 1: Write the failing test**

Create `web/frontend/tests/BoardView.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BoardView from '../src/components/BoardView.vue'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ assets: [], cover_asset_id: 1 }) })
})

const board = { id: 7, name: 'My Board' }

describe('BoardView', () => {
  it('shows the board name and an Add images control', () => {
    const wrapper = mount(BoardView, { props: { board, assets: [], cartIds: [], loading: false } })
    expect(wrapper.text()).toContain('My Board')
    expect(wrapper.find('[data-testid="add-images"]').exists()).toBe(true)
  })

  it('uploads dropped files and emits changed', async () => {
    const wrapper = mount(BoardView, { props: { board, assets: [], cartIds: [], loading: false } })
    const file = new File([new Uint8Array([1, 2])], 'a.png', { type: 'image/png' })
    await wrapper.find('[data-testid="dropzone"]').trigger('drop', { dataTransfer: { files: [file] } })
    await flushPromises()
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/boards/7/images'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web/frontend && npx vitest run tests/BoardView.test.js`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement `BoardView.vue`**

```html
<template>
  <div class="board-view">
    <div class="board-header">
      <input
        v-if="renaming"
        class="board-name-input"
        v-model="draftName"
        @keyup.enter="commitRename"
        @keyup.escape="renaming = false"
        v-focus
      />
      <h2 v-else class="board-name">{{ board.name }}</h2>
      <div class="board-actions">
        <button data-testid="add-images" class="board-btn" @click="pick">+ Add images</button>
        <button class="board-btn" @click="startRename">Rename</button>
        <button class="board-btn danger" @click="removeBoard">Delete</button>
      </div>
      <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="onPick" />
    </div>

    <div
      data-testid="dropzone"
      class="dropzone"
      :class="{ over: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <AssetGrid
        :assets="assets"
        :cart-ids="cartIds"
        :loading="loading"
        @select="$emit('select', $event)"
        @view-pack="$emit('view-pack', $event)"
        @add-to-cart="$emit('add-to-cart', $event)"
        @load-more="$emit('load-more')"
      />
      <p v-if="!assets.length" class="empty-hint">Drop images here or use “Add images”.</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AssetGrid from './AssetGrid.vue'
import { uploadImages, renameBoard, deleteBoard } from '../api/boards.js'

const props = defineProps({
  board: { type: Object, required: true },
  assets: { type: Array, required: true },
  cartIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['select', 'add-to-cart', 'load-more', 'view-pack', 'changed', 'deleted'])

const vFocus = { mounted: el => el.focus() }
const fileInput = ref(null)
const dragOver = ref(false)
const renaming = ref(false)
const draftName = ref('')

function pick() { fileInput.value?.click() }

async function upload(files) {
  if (!files || !files.length) return
  await uploadImages(props.board.id, files)
  emit('changed')
}

function onPick(e) { upload(e.target.files) }

function onDrop(e) {
  dragOver.value = false
  upload(e.dataTransfer?.files)
}

function startRename() {
  draftName.value = props.board.name
  renaming.value = true
}

async function commitRename() {
  const name = draftName.value.trim()
  renaming.value = false
  if (name && name !== props.board.name) {
    await renameBoard(props.board.id, name)
    emit('changed')
  }
}

async function removeBoard() {
  await deleteBoard(props.board.id)
  emit('deleted')
}
</script>

<style scoped>
.board-view { display: flex; flex-direction: column; height: 100%; }
.board-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; flex-wrap: wrap;
}
.board-name { margin: 0; font-size: 1.375rem; font-weight: 700; }
.board-name-input {
  font-size: 1.25rem; padding: 0.25rem 0.5rem;
  border: 1px solid var(--color-accent); border-radius: 6px;
  background: var(--color-bg-surface); color: var(--color-text-primary);
}
.board-actions { display: flex; gap: 0.5rem; margin-left: auto; }
.board-btn {
  border: 1px solid var(--color-border); background: var(--color-bg-surface);
  color: var(--color-text-secondary); border-radius: 6px; padding: 0.375rem 0.75rem;
  cursor: pointer; font-size: 0.8125rem;
}
.board-btn:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
.board-btn.danger:hover { border-color: var(--color-danger); color: var(--color-danger); }
.dropzone { flex: 1; overflow-y: auto; position: relative; }
.dropzone.over { outline: 2px dashed var(--color-accent); outline-offset: -6px; }
.empty-hint { text-align: center; color: var(--color-text-muted); padding: 2rem; }
</style>
```

- [ ] **Step 4: Wire `App.vue`**

Import BoardView and the client at the top of `<script setup>`:

```javascript
import BoardView from './components/BoardView.vue'
import { createBoard } from './api/boards.js'
```

Add a computed to detect the current board (after `packList`):

```javascript
const currentBoard = computed(() => {
  if (selectedPacks.value.length !== 1) return null
  return filters.value.packs.find(p => p.name === selectedPacks.value[0] && p.is_board) || null
})
```

In the template, render `BoardView` before the plain `AssetGrid` branch. Change the `middle-panel` content so the grid branch becomes:

```html
        <BoardView
          v-else-if="currentBoard"
          :board="currentBoard"
          :assets="assets"
          :cart-ids="cartIds"
          :loading="loadingMore"
          @select="selectAsset"
          @view-pack="viewPack"
          @add-to-cart="addToCart"
          @load-more="loadMore"
          @changed="refreshAfterBoardChange"
          @deleted="goHomeAfterDelete"
        />

        <AssetGrid
          v-else
          :assets="assets"
          :cart-ids="cartIds"
          :loading="loadingMore"
          @select="selectAsset"
          @view-pack="viewPack"
          @add-to-cart="addToCart"
          @load-more="loadMore"
        />
```

Add handlers in `<script setup>`:

```javascript
async function handleCreateBoard(name) {
  try {
    await createBoard(name)
  } catch (e) {
    return
  }
  await fetchFilters()
  viewPack(name)
}

async function refreshAfterBoardChange() {
  await fetchFilters()
  await search(currentSearchParams.value)
}

async function goHomeAfterDelete() {
  await fetchFilters()
  goHome()
}
```

Wire `@create-board` on `PackGallery`:

```html
        <PackGallery
          v-else-if="isDefaultHomeView"
          :packs="packList"
          @view-pack="viewPack"
          @create-board="handleCreateBoard"
        />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web/frontend && npx vitest run tests/BoardView.test.js tests/App.test.js`
Expected: PASS (App tests still green).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/BoardView.vue web/frontend/src/App.vue web/frontend/tests/BoardView.test.js
git commit -m "feat: BoardView with upload + rename/delete, wired into App"
```

---

### Task 12: Board image actions in AssetDetail

Adds "Set as cover", "Remove", and tag add/remove for board images in the detail view.

**Files:**
- Modify: `web/frontend/src/components/AssetDetail.vue`
- Test: `web/frontend/tests/AssetDetail.test.js` (extend)

**Interfaces:**
- Consumes: `boards.js` (`setCover`, `deleteImage`, `addImageTag`, `removeImageTag`); `asset.is_board`, `asset.board_id`, `asset.id`.
- Produces: AssetDetail emits `board-image-changed` after cover/tag edits and `board-image-removed` after delete (App refetches filters + search; existing `viewPack`/`goHome` reused).

- [ ] **Step 1: Read the component first**

Read `web/frontend/src/components/AssetDetail.vue` fully to find where tags render and where action buttons live. Match its existing markup/emit style.

- [ ] **Step 2: Write the failing test**

Add to `web/frontend/tests/AssetDetail.test.js` (follow the file's existing mount/props helpers; provide a board asset):

```javascript
  it('shows board image actions and emits on set-cover', async () => {
    const asset = {
      id: 5, filename: 'a.png', filetype: 'png', pack: 'My Board',
      is_board: true, board_id: 7, tags: [], colors: [], width: 10, height: 10
    }
    const wrapper = mount(AssetDetail, { props: { asset } })
    const btn = wrapper.find('[data-testid="set-cover"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    await flushPromises()
    expect(wrapper.emitted('board-image-changed')).toBeTruthy()
  })
```

(Ensure `global.fetch` is stubbed `{ ok: true, json: () => Promise.resolve({ tags: [] }) }` as in the file's setup.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web/frontend && npx vitest run tests/AssetDetail.test.js`
Expected: FAIL — no `[data-testid="set-cover"]`.

- [ ] **Step 4: Implement the board-actions block**

In `AssetDetail.vue` template, add a section rendered only for board images (place near the existing action buttons):

```html
      <div v-if="asset.is_board" class="board-image-actions">
        <button data-testid="set-cover" class="board-btn" @click="makeCover">Set as cover</button>
        <button class="board-btn danger" @click="removeImage">Remove</button>
        <div class="image-tags">
          <span v-for="t in localTags" :key="t" class="tag-chip">
            {{ t }}<button class="tag-remove" @click="dropTag(t)">×</button>
          </span>
          <input
            v-model="newTag"
            class="tag-input"
            placeholder="+ tag"
            @keyup.enter="addTag"
          />
        </div>
      </div>
```

In `<script setup>`, import the client and add state/handlers (declare emits alongside the component's existing `defineEmits`):

```javascript
import { setCover, deleteImage, addImageTag, removeImageTag } from '../api/boards.js'
import { ref, watch } from 'vue'

// add 'board-image-changed' and 'board-image-removed' to the existing defineEmits array
const localTags = ref([...(props.asset.tags || [])])
const newTag = ref('')

watch(() => props.asset, a => { localTags.value = [...(a.tags || [])] })

async function makeCover() {
  await setCover(props.asset.board_id, props.asset.id)
  emit('board-image-changed')
}

async function removeImage() {
  await deleteImage(props.asset.id)
  emit('board-image-removed')
}

async function addTag() {
  const t = newTag.value.trim()
  newTag.value = ''
  if (!t) return
  const res = await addImageTag(props.asset.id, t)
  localTags.value = res.tags
  emit('board-image-changed')
}

async function dropTag(t) {
  const res = await removeImageTag(props.asset.id, t)
  localTags.value = res.tags
  emit('board-image-changed')
}
```

(If the component uses `defineProps`/`defineEmits` without a captured `emit`/`props` const, capture them: `const props = defineProps(...)`, `const emit = defineEmits([... , 'board-image-changed', 'board-image-removed'])`.)

Add minimal styles:

```css
.board-image-actions { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.75rem; }
.board-image-actions .board-btn {
  border: 1px solid var(--color-border); background: var(--color-bg-surface);
  color: var(--color-text-secondary); border-radius: 6px; padding: 0.375rem 0.75rem;
  cursor: pointer; font-size: 0.8125rem; align-self: flex-start;
}
.board-image-actions .board-btn.danger:hover { border-color: var(--color-danger); color: var(--color-danger); }
.image-tags { display: flex; flex-wrap: wrap; gap: 0.375rem; align-items: center; }
```

- [ ] **Step 5: Wire App.vue to the new emits**

On the `<AssetDetail>` element in `App.vue`, add:

```html
          @board-image-changed="refreshAfterBoardChange"
          @board-image-removed="onBoardImageRemoved"
```

Add the handler:

```javascript
async function onBoardImageRemoved() {
  selectedAsset.value = null
  await refreshAfterBoardChange()
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd web/frontend && npx vitest run tests/AssetDetail.test.js tests/App.test.js`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue web/frontend/src/App.vue web/frontend/tests/AssetDetail.test.js
git commit -m "feat: board image actions (cover, remove, tags) in AssetDetail"
```

---

### Task 13: Full suite + manual smoke

**Files:** none (verification)

- [ ] **Step 1: Run the whole backend suite**

Run: `just test` (runs `test_index.py`, `test_frame_detect.py`, `test_model_indexer.py`, `web/test_api.py`) then `uv run --script web/test_boards.py`.
Expected: all PASS.

- [ ] **Step 2: Run the whole frontend suite**

Run: `cd web/frontend && npm run test`
Expected: all PASS.

- [ ] **Step 3: Manual smoke (servers already running on 8000/5173)**

Verify end-to-end in the browser: create a board from the gallery → it appears with a BOARD badge → open it → drag-drop 2 images → both render → set the second as cover → gallery cover updates → tag an image → find it via tag search → remove an image → delete the board → gallery no longer lists it. Confirm `assets/.boards/<slug>/` is created and removed accordingly, and that a CLI `just index-assets` run does not add board images as indexed assets.

- [ ] **Step 4: Commit any fixes, then finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to open the PR.

---

## Notes for the implementer

- **One code path, two write surfaces.** The API now writes both the DB and files under `assets/.boards/`. Keep transactions short; commit before filesystem deletes so a failed `unlink`/`rmtree` never leaves the DB rolled back but files gone in an inconsistent way — the chosen order (DB delete → commit → remove files) is deliberate.
- **Legacy DBs.** `_ensure_board_columns` is why board endpoints work against a DB indexed before this feature. Call it in any handler that reads/writes `packs.source`.
- **Board images intentionally appear in search** (by filename and user tags); they carry no color/phash rows so they never affect color or similarity results. This is per the approved spec — do not add exclusion logic.
- **Frontend image-level actions live in `AssetDetail`, not as `AssetGrid` hover menus**, to avoid modifying the shared grid. This is a deliberate simplification of the spec's "hover menu" sketch; the actions and outcomes are identical.
