# Web Interface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Vue 3 web interface with instant search for asset-manager, using FastAPI backend.

**Architecture:** FastAPI wraps existing `assetsearch.py` query logic. Vue 3 SPA with composition API provides instant search with debouncing. Grid of thumbnails, modal for details, "Find Similar" action.

**Tech Stack:** Python 3.11+, FastAPI, pytest. Vue 3, Vite, Vitest, Vue Test Utils.

---

## Task 1: API Project Setup

**Files:**
- Create: `web/api.py`
- Create: `web/test_api.py`

**Step 1: Create web directory and empty files**

```bash
mkdir -p web
touch web/api.py web/test_api.py
```

**Step 2: Write api.py with FastAPI skeleton and inline dependencies**

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "uvicorn>=0.27",
# ]
# ///
"""Web API for asset search."""

from fastapi import FastAPI

app = FastAPI(title="Asset Search API")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
```

**Step 3: Write test_api.py with health check test**

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
# ]
# ///
"""Tests for web API."""

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 4: Run test to verify it passes**

Run: `cd web && uv run --script test_api.py`
Expected: PASS

**Step 5: Commit**

```bash
git add web/
git commit -m "feat(web): add FastAPI skeleton with health endpoint"
```

---

## Task 2: Search Endpoint - Test First

**Files:**
- Modify: `web/test_api.py`

**Step 1: Write failing tests for /api/search endpoint**

Add to `web/test_api.py`:

```python
import sqlite3
import tempfile
from pathlib import Path


@pytest.fixture
def test_db():
    """Create a temporary test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE packs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            version TEXT,
            preview_path TEXT,
            asset_count INTEGER DEFAULT 0
        );
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY,
            pack_id INTEGER,
            path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER,
            width INTEGER,
            height INTEGER,
            frame_count INTEGER,
            frame_width INTEGER,
            frame_height INTEGER
        );
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_colors (asset_id INTEGER, color_hex TEXT, percentage REAL, PRIMARY KEY (asset_id, color_hex));
        CREATE TABLE asset_phash (asset_id INTEGER PRIMARY KEY, phash BLOB);

        INSERT INTO packs (id, name, path) VALUES (1, 'creatures', '/assets/creatures');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (1, 1, '/assets/creatures/goblin.png', 'goblin.png', 'png', 'abc123', 64, 64);
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash, width, height)
            VALUES (2, 1, '/assets/creatures/orc.png', 'orc.png', 'png', 'def456', 128, 128);
        INSERT INTO tags (id, name) VALUES (1, 'creature'), (2, 'goblin'), (3, 'orc');
        INSERT INTO asset_tags VALUES (1, 1), (1, 2), (2, 1), (2, 3);
        INSERT INTO asset_colors VALUES (1, '#00ff00', 0.5), (2, '#ff0000', 0.6);
    """)
    conn.close()

    yield db_path
    db_path.unlink()


def test_search_returns_all_assets(test_db):
    """Search with no filters returns all assets."""
    from api import app, set_db_path
    set_db_path(test_db)

    response = client.get("/api/search")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 2
    assert data["total"] == 2


def test_search_by_query(test_db):
    """Search by filename query."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?q=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert data["assets"][0]["filename"] == "goblin.png"


def test_search_by_tag(test_db):
    """Search by tag filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?tag=goblin")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert "goblin" in data["assets"][0]["tags"]


def test_search_by_color(test_db):
    """Search by color filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?color=green")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert data["assets"][0]["filename"] == "goblin.png"


def test_search_by_pack(test_db):
    """Search by pack filter."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/search?pack=creatures")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd web && uv run --script test_api.py`
Expected: FAIL with "cannot import name 'set_db_path'"

**Step 3: Commit failing tests**

```bash
git add web/test_api.py
git commit -m "test(web): add failing tests for /api/search endpoint"
```

---

## Task 3: Search Endpoint - Implementation

**Files:**
- Modify: `web/api.py`

**Step 1: Implement /api/search endpoint**

Replace `web/api.py` with:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "uvicorn>=0.27",
# ]
# ///
"""Web API for asset search."""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

app = FastAPI(title="Asset Search API")

# Database path - can be overridden for testing
_db_path: Optional[Path] = None

COLOR_NAMES = {
    "red": ("#ff0000", "#cc0000", "#990000", "#ff3333", "#cc3333"),
    "green": ("#00ff00", "#00cc00", "#009900", "#33ff33", "#33cc33", "#336633", "#669966"),
    "blue": ("#0000ff", "#0000cc", "#000099", "#3333ff", "#3333cc", "#333366"),
    "yellow": ("#ffff00", "#cccc00", "#999900", "#ffff33"),
    "orange": ("#ff8800", "#ff6600", "#cc6600", "#ff9933"),
    "purple": ("#ff00ff", "#cc00cc", "#990099", "#9900ff", "#6600cc"),
    "brown": ("#8b4513", "#a0522d", "#cd853f", "#d2691e", "#8b5a2b"),
    "black": ("#000000", "#111111", "#222222", "#333333"),
    "white": ("#ffffff", "#eeeeee", "#dddddd", "#cccccc"),
    "gray": ("#888888", "#999999", "#aaaaaa", "#777777", "#666666"),
    "grey": ("#888888", "#999999", "#aaaaaa", "#777777", "#666666"),
}


def set_db_path(path: Path):
    """Set database path (for testing)."""
    global _db_path
    _db_path = path


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    path = _db_path or find_db()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def find_db() -> Path:
    """Find assets.db in current directory or parent directories."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        db_path = parent / "assets.db"
        if db_path.exists():
            return db_path
    raise FileNotFoundError("No assets.db found")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/search")
def search(
    q: Optional[str] = None,
    tag: list[str] = Query(default=[]),
    color: Optional[str] = None,
    pack: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
):
    """Search assets by name, tags, or filters."""
    conn = get_db()

    conditions = []
    params = []

    if q:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if pack:
        conditions.append("p.name LIKE ?")
        params.append(f"%{pack}%")

    if type:
        conditions.append("a.filetype = ?")
        params.append(type.lower().lstrip("."))

    for t in tag:
        conditions.append("""
            a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
            )
        """)
        params.append(t.lower())

    if color:
        color_lower = color.lower()
        if color_lower in COLOR_NAMES:
            hex_values = COLOR_NAMES[color_lower]
            placeholders = ",".join("?" * len(hex_values))
            conditions.append(f"""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex IN ({placeholders})
                    AND percentage >= 0.1
                )
            """)
            params.extend(hex_values)
        else:
            conditions.append("""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex = ?
                    AND percentage >= 0.1
                )
            """)
            params.append(color if color.startswith("#") else f"#{color}")

    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.frame_count, p.name as pack_name,
               GROUP_CONCAT(DISTINCT tg.name) as tags
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.filename
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    assets = []
    for row in rows:
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
        })

    return {"assets": assets, "total": len(assets)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Step 2: Run tests to verify they pass**

Run: `cd web && uv run --script test_api.py`
Expected: All 6 tests PASS

**Step 3: Commit**

```bash
git add web/api.py
git commit -m "feat(web): implement /api/search endpoint"
```

---

## Task 4: Similar Endpoint - Test First

**Files:**
- Modify: `web/test_api.py`

**Step 1: Add phash data to fixture and write failing tests**

Update the `test_db` fixture to include phash data, then add tests:

```python
# Add to test_db fixture SQL, after asset_colors inserts:
# INSERT INTO asset_phash VALUES (1, X'0000000000000000'), (2, X'0000000000000001');

def test_similar_returns_similar_assets(test_db):
    """Find similar returns assets by visual similarity."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/similar/1")
    assert response.status_code == 200
    data = response.json()
    assert "assets" in data
    # Asset 2 has hamming distance of 1 from asset 1
    assert len(data["assets"]) == 1
    assert data["assets"][0]["id"] == 2


def test_similar_respects_distance(test_db):
    """Find similar respects max distance parameter."""
    from api import set_db_path
    set_db_path(test_db)

    # Distance 0 should return nothing (only exact matches, excluding self)
    response = client.get("/api/similar/1?distance=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 0


def test_similar_not_found(test_db):
    """Find similar returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/similar/999")
    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd web && uv run --script test_api.py`
Expected: FAIL with 404 (endpoint not found)

**Step 3: Commit failing tests**

```bash
git add web/test_api.py
git commit -m "test(web): add failing tests for /api/similar endpoint"
```

---

## Task 5: Similar Endpoint - Implementation

**Files:**
- Modify: `web/api.py`

**Step 1: Add hamming_distance function and /api/similar endpoint**

Add to `web/api.py`:

```python
def hamming_distance(h1: bytes, h2: bytes) -> int:
    """Calculate hamming distance between two hashes."""
    return sum(bin(a ^ b).count("1") for a, b in zip(h1, h2))


@app.get("/api/similar/{asset_id}")
def similar(
    asset_id: int,
    limit: int = 20,
    distance: int = 15,
):
    """Find visually similar assets."""
    conn = get_db()

    # Get reference hash
    row = conn.execute(
        "SELECT phash FROM asset_phash WHERE asset_id = ?", [asset_id]
    ).fetchone()

    if not row:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found or no phash")

    ref_hash = row["phash"]

    # Find similar
    results = []
    for row in conn.execute("""
        SELECT ap.asset_id, ap.phash, a.filename, a.path, p.name as pack_name,
               a.width, a.height
        FROM asset_phash ap
        JOIN assets a ON ap.asset_id = a.id
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE ap.asset_id != ?
    """, [asset_id]):
        dist = hamming_distance(ref_hash, row["phash"])
        if dist <= distance:
            results.append((dist, row))

    conn.close()

    results.sort(key=lambda x: x[0])
    results = results[:limit]

    assets = []
    for dist, row in results:
        assets.append({
            "id": row["asset_id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": [],
            "width": row["width"],
            "height": row["height"],
            "distance": dist,
        })

    return {"assets": assets, "total": len(assets)}
```

**Step 2: Update test_db fixture to include phash data**

In `test_api.py`, update the fixture SQL to add:

```python
INSERT INTO asset_phash VALUES (1, X'0000000000000000'), (2, X'0000000000000001');
```

**Step 3: Run tests to verify they pass**

Run: `cd web && uv run --script test_api.py`
Expected: All 9 tests PASS

**Step 4: Commit**

```bash
git add web/
git commit -m "feat(web): implement /api/similar endpoint"
```

---

## Task 6: Asset Detail and Filters Endpoints - Test First

**Files:**
- Modify: `web/test_api.py`

**Step 1: Write failing tests for /api/asset/{id} and /api/filters**

```python
def test_asset_detail(test_db):
    """Get asset detail returns full info."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["filename"] == "goblin.png"
    assert data["path"] == "/assets/creatures/goblin.png"
    assert data["pack"] == "creatures"
    assert "goblin" in data["tags"]
    assert len(data["colors"]) > 0


def test_asset_detail_not_found(test_db):
    """Get asset detail returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/asset/999")
    assert response.status_code == 404


def test_filters_returns_options(test_db):
    """Get filters returns available filter options."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/filters")
    assert response.status_code == 200
    data = response.json()
    assert "packs" in data
    assert "tags" in data
    assert "colors" in data
    assert "creatures" in data["packs"]
    assert "creature" in data["tags"]
```

**Step 2: Run tests to verify they fail**

Run: `cd web && uv run --script test_api.py`
Expected: FAIL with 404 (endpoints not found)

**Step 3: Commit failing tests**

```bash
git add web/test_api.py
git commit -m "test(web): add failing tests for /api/asset and /api/filters"
```

---

## Task 7: Asset Detail and Filters Endpoints - Implementation

**Files:**
- Modify: `web/api.py`

**Step 1: Implement /api/asset/{asset_id} endpoint**

Add to `web/api.py`:

```python
@app.get("/api/asset/{asset_id}")
def asset_detail(asset_id: int):
    """Get detailed info for an asset."""
    conn = get_db()

    row = conn.execute("""
        SELECT a.*, p.name as pack_name
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE a.id = ?
    """, [asset_id]).fetchone()

    if not row:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get tags
    tags = conn.execute("""
        SELECT t.name FROM asset_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.asset_id = ?
    """, [asset_id]).fetchall()

    # Get colors
    colors = conn.execute("""
        SELECT color_hex, percentage FROM asset_colors
        WHERE asset_id = ?
        ORDER BY percentage DESC
    """, [asset_id]).fetchall()

    # Get related assets
    related = conn.execute("""
        SELECT a.id, a.filename, ar.relation_type
        FROM asset_relations ar
        JOIN assets a ON ar.related_id = a.id
        WHERE ar.asset_id = ?
    """, [asset_id]).fetchall()

    conn.close()

    return {
        "id": row["id"],
        "path": row["path"],
        "filename": row["filename"],
        "filetype": row["filetype"],
        "pack": row["pack_name"],
        "width": row["width"],
        "height": row["height"],
        "frame_count": row["frame_count"],
        "frame_width": row["frame_width"],
        "frame_height": row["frame_height"],
        "tags": [t["name"] for t in tags],
        "colors": [{"hex": c["color_hex"], "percentage": c["percentage"]} for c in colors],
        "related": [{"id": r["id"], "filename": r["filename"], "type": r["relation_type"]} for r in related],
    }
```

**Step 2: Implement /api/filters endpoint**

Add to `web/api.py`:

```python
@app.get("/api/filters")
def filters():
    """Get available filter options."""
    conn = get_db()

    packs = conn.execute("SELECT name FROM packs ORDER BY name").fetchall()
    tags = conn.execute("""
        SELECT t.name, COUNT(at.asset_id) as count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY count DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return {
        "packs": [p["name"] for p in packs],
        "tags": [t["name"] for t in tags],
        "colors": list(COLOR_NAMES.keys()),
    }
```

**Step 3: Run tests to verify they pass**

Run: `cd web && uv run --script test_api.py`
Expected: All 12 tests PASS

**Step 4: Commit**

```bash
git add web/api.py
git commit -m "feat(web): implement /api/asset and /api/filters endpoints"
```

---

## Task 8: Image Serving Endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write test for /api/image/{asset_id}**

```python
def test_image_not_found(test_db):
    """Image endpoint returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.get("/api/image/999")
    assert response.status_code == 404
```

**Step 2: Implement /api/image/{asset_id} endpoint**

Add to `web/api.py`:

```python
@app.get("/api/image/{asset_id}")
def image(asset_id: int):
    """Serve asset image file."""
    conn = get_db()
    row = conn.execute("SELECT path FROM assets WHERE id = ?", [asset_id]).fetchone()
    conn.close()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found")

    image_path = Path(row["path"])
    if not image_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(image_path)
```

**Step 3: Run tests to verify they pass**

Run: `cd web && uv run --script test_api.py`
Expected: All 13 tests PASS

**Step 4: Commit**

```bash
git add web/
git commit -m "feat(web): implement /api/image endpoint"
```

---

## Task 9: Vue Project Setup

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/vite.config.js`
- Create: `web/frontend/index.html`
- Create: `web/frontend/src/main.js`
- Create: `web/frontend/src/App.vue`

**Step 1: Create frontend directory structure**

```bash
mkdir -p web/frontend/src/components web/frontend/tests
```

**Step 2: Create package.json**

```json
{
  "name": "asset-search-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "vue": "^3.4"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "@vue/test-utils": "^2.4",
    "jsdom": "^24.0",
    "vite": "^5.0",
    "vitest": "^1.2"
  }
}
```

**Step 3: Create vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

**Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Asset Search</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

**Step 5: Create src/main.js**

```javascript
import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
```

**Step 6: Create src/App.vue skeleton**

```vue
<template>
  <div class="app">
    <h1>Asset Search</h1>
  </div>
</template>

<script setup>
</script>

<style>
.app {
  font-family: system-ui, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem;
}
</style>
```

**Step 7: Install dependencies and verify setup**

```bash
cd web/frontend && npm install
```

**Step 8: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): add Vue project skeleton"
```

---

## Task 10: SearchBar Component - Test First

**Files:**
- Create: `web/frontend/tests/SearchBar.test.js`
- Create: `web/frontend/src/components/SearchBar.vue`

**Step 1: Write failing tests for SearchBar**

Create `web/frontend/tests/SearchBar.test.js`:

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

describe('SearchBar', () => {
  it('renders search input', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: [] } }
    })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('emits search event on input', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: [] } }
    })
    await wrapper.find('input[type="text"]').setValue('goblin')
    expect(wrapper.emitted('search')).toBeTruthy()
    expect(wrapper.emitted('search')[0]).toEqual([{ q: 'goblin', tag: [], color: null, pack: null, type: null }])
  })

  it('renders pack filter dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: ['creatures', 'items'], tags: [], colors: [] } }
    })
    const select = wrapper.find('select[data-filter="pack"]')
    expect(select.exists()).toBe(true)
    expect(select.findAll('option').length).toBe(3) // empty + 2 packs
  })

  it('emits search with pack filter', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: ['creatures'], tags: [], colors: [] } }
    })
    await wrapper.find('select[data-filter="pack"]').setValue('creatures')
    const events = wrapper.emitted('search')
    const lastEvent = events[events.length - 1][0]
    expect(lastEvent.pack).toBe('creatures')
  })

  it('renders color filter dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: ['red', 'green', 'blue'] } }
    })
    const select = wrapper.find('select[data-filter="color"]')
    expect(select.exists()).toBe(true)
  })
})
```

**Step 2: Create empty SearchBar.vue to make imports work**

```vue
<template>
  <div></div>
</template>

<script setup>
</script>
```

**Step 3: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: FAIL

**Step 4: Commit failing tests**

```bash
git add web/frontend/
git commit -m "test(web): add failing tests for SearchBar component"
```

---

## Task 11: SearchBar Component - Implementation

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Implement SearchBar component**

```vue
<template>
  <div class="search-bar">
    <input
      type="text"
      v-model="query"
      placeholder="Search assets..."
      @input="emitSearch"
    />
    <select data-filter="pack" v-model="pack" @change="emitSearch">
      <option value="">All packs</option>
      <option v-for="p in filters.packs" :key="p" :value="p">{{ p }}</option>
    </select>
    <select data-filter="color" v-model="color" @change="emitSearch">
      <option value="">Any color</option>
      <option v-for="c in filters.colors" :key="c" :value="c">{{ c }}</option>
    </select>
    <select data-filter="tag" v-model="selectedTag" @change="addTag">
      <option value="">Add tag...</option>
      <option v-for="t in filters.tags" :key="t" :value="t">{{ t }}</option>
    </select>
    <span v-for="t in tags" :key="t" class="tag" @click="removeTag(t)">
      {{ t }} &times;
    </span>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['search'])

const query = ref('')
const pack = ref('')
const color = ref('')
const tags = ref([])
const selectedTag = ref('')

function emitSearch() {
  emit('search', {
    q: query.value || null,
    tag: tags.value,
    color: color.value || null,
    pack: pack.value || null,
    type: null
  })
}

function addTag() {
  if (selectedTag.value && !tags.value.includes(selectedTag.value)) {
    tags.value.push(selectedTag.value)
    selectedTag.value = ''
    emitSearch()
  }
}

function removeTag(tag) {
  tags.value = tags.value.filter(t => t !== tag)
  emitSearch()
}
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 1rem;
}

.search-bar input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem;
  font-size: 1rem;
}

.search-bar select {
  padding: 0.5rem;
}

.tag {
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}

.tag:hover {
  background: #ccc;
}
</style>
```

**Step 2: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: All 5 SearchBar tests PASS

**Step 3: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): implement SearchBar component"
```

---

## Task 12: AssetGrid Component - Test First

**Files:**
- Create: `web/frontend/tests/AssetGrid.test.js`
- Create: `web/frontend/src/components/AssetGrid.vue`

**Step 1: Write failing tests for AssetGrid**

Create `web/frontend/tests/AssetGrid.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetGrid from '../src/components/AssetGrid.vue'

const mockAssets = [
  { id: 1, filename: 'goblin.png', path: '/assets/goblin.png', width: 64, height: 64 },
  { id: 2, filename: 'orc.png', path: '/assets/orc.png', width: 128, height: 128 },
]

describe('AssetGrid', () => {
  it('renders grid of assets', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.findAll('.asset-item').length).toBe(2)
  })

  it('shows asset filename', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.text()).toContain('goblin.png')
  })

  it('shows result count', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.text()).toContain('2')
  })

  it('emits select event on click', async () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    await wrapper.find('.asset-item').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0]).toEqual([1])
  })

  it('shows empty message when no assets', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: [] }
    })
    expect(wrapper.text()).toContain('No results')
  })
})
```

**Step 2: Create empty AssetGrid.vue**

```vue
<template>
  <div></div>
</template>

<script setup>
</script>
```

**Step 3: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: AssetGrid tests FAIL

**Step 4: Commit failing tests**

```bash
git add web/frontend/
git commit -m "test(web): add failing tests for AssetGrid component"
```

---

## Task 13: AssetGrid Component - Implementation

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`

**Step 1: Implement AssetGrid component**

```vue
<template>
  <div class="asset-grid-container">
    <div class="result-count" v-if="assets.length > 0">
      {{ assets.length }} results
    </div>
    <div class="asset-grid" v-if="assets.length > 0">
      <div
        v-for="asset in assets"
        :key="asset.id"
        class="asset-item"
        @click="$emit('select', asset.id)"
      >
        <img :src="`/api/image/${asset.id}`" :alt="asset.filename" />
        <span class="filename">{{ asset.filename }}</span>
      </div>
    </div>
    <div v-else class="no-results">
      No results
    </div>
  </div>
</template>

<script setup>
defineProps({
  assets: {
    type: Array,
    required: true
  }
})

defineEmits(['select'])
</script>

<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: #666;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1rem;
}

.asset-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 4px;
}

.asset-item:hover {
  background: #f0f0f0;
}

.asset-item img {
  max-width: 100px;
  max-height: 100px;
  object-fit: contain;
}

.filename {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  text-align: center;
  word-break: break-all;
}

.no-results {
  color: #666;
  text-align: center;
  padding: 2rem;
}
</style>
```

**Step 2: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: All 10 tests PASS

**Step 3: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): implement AssetGrid component"
```

---

## Task 14: AssetModal Component - Test First

**Files:**
- Create: `web/frontend/tests/AssetModal.test.js`
- Create: `web/frontend/src/components/AssetModal.vue`

**Step 1: Write failing tests for AssetModal**

Create `web/frontend/tests/AssetModal.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetModal from '../src/components/AssetModal.vue'

const mockAsset = {
  id: 1,
  filename: 'goblin.png',
  path: '/assets/creatures/goblin.png',
  pack: 'creatures',
  width: 64,
  height: 64,
  tags: ['creature', 'goblin'],
  colors: [{ hex: '#00ff00', percentage: 0.5 }],
  related: []
}

describe('AssetModal', () => {
  it('renders asset details', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('goblin.png')
    expect(wrapper.text()).toContain('/assets/creatures/goblin.png')
    expect(wrapper.text()).toContain('creatures')
    expect(wrapper.text()).toContain('64')
  })

  it('renders tags', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('creature')
    expect(wrapper.text()).toContain('goblin')
  })

  it('renders color swatches', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('.color-swatch').exists()).toBe(true)
  })

  it('has Find Similar button', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('button').text()).toContain('Find Similar')
  })

  it('emits find-similar event on button click', async () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('find-similar')).toBeTruthy()
    expect(wrapper.emitted('find-similar')[0]).toEqual([1])
  })

  it('emits close event on overlay click', async () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.modal-overlay').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
```

**Step 2: Create empty AssetModal.vue**

```vue
<template>
  <div></div>
</template>

<script setup>
</script>
```

**Step 3: Run tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: AssetModal tests FAIL

**Step 4: Commit failing tests**

```bash
git add web/frontend/
git commit -m "test(web): add failing tests for AssetModal component"
```

---

## Task 15: AssetModal Component - Implementation

**Files:**
- Modify: `web/frontend/src/components/AssetModal.vue`

**Step 1: Implement AssetModal component**

```vue
<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <button class="close-btn" @click="$emit('close')">&times;</button>

      <img :src="`/api/image/${asset.id}`" :alt="asset.filename" class="asset-image" />

      <h2>{{ asset.filename }}</h2>
      <p class="path">{{ asset.path }}</p>

      <div class="details">
        <div><strong>Pack:</strong> {{ asset.pack || '-' }}</div>
        <div><strong>Size:</strong> {{ asset.width }}x{{ asset.height }}</div>
        <div v-if="asset.frame_count">
          <strong>Frames:</strong> {{ asset.frame_count }} ({{ asset.frame_width }}x{{ asset.frame_height }})
        </div>
      </div>

      <div class="tags" v-if="asset.tags && asset.tags.length">
        <strong>Tags:</strong>
        <span v-for="tag in asset.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>

      <div class="colors" v-if="asset.colors && asset.colors.length">
        <strong>Colors:</strong>
        <span
          v-for="color in asset.colors"
          :key="color.hex"
          class="color-swatch"
          :style="{ backgroundColor: color.hex }"
          :title="`${color.hex} (${Math.round(color.percentage * 100)}%)`"
        ></span>
      </div>

      <button @click="$emit('find-similar', asset.id)" class="find-similar-btn">
        Find Similar
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  asset: {
    type: Object,
    required: true
  }
})

defineEmits(['close', 'find-similar'])
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
}

.close-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
}

.asset-image {
  max-width: 100%;
  max-height: 300px;
  object-fit: contain;
  display: block;
  margin: 0 auto 1rem;
}

h2 {
  margin: 0 0 0.5rem;
}

.path {
  color: #666;
  font-size: 0.875rem;
  word-break: break-all;
  margin-bottom: 1rem;
}

.details {
  margin-bottom: 1rem;
}

.tags {
  margin-bottom: 1rem;
}

.tag {
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
}

.colors {
  margin-bottom: 1rem;
}

.color-swatch {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-left: 0.25rem;
  border: 1px solid #ccc;
}

.find-similar-btn {
  background: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.find-similar-btn:hover {
  background: #0056b3;
}
</style>
```

**Step 2: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: All 16 tests PASS

**Step 3: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): implement AssetModal component"
```

---

## Task 16: Wire Up App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`

**Step 1: Implement App.vue with API integration**

```vue
<template>
  <div class="app">
    <h1>Asset Search</h1>

    <SearchBar :filters="filters" @search="handleSearch" />

    <AssetGrid :assets="assets" @select="selectAsset" />

    <AssetModal
      v-if="selectedAsset"
      :asset="selectedAsset"
      @close="selectedAsset = null"
      @find-similar="findSimilar"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SearchBar from './components/SearchBar.vue'
import AssetGrid from './components/AssetGrid.vue'
import AssetModal from './components/AssetModal.vue'

const filters = ref({ packs: [], tags: [], colors: [] })
const assets = ref([])
const selectedAsset = ref(null)

let debounceTimer = null

async function fetchFilters() {
  const res = await fetch('/api/filters')
  filters.value = await res.json()
}

async function search(params) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.pack) query.set('pack', params.pack)
  if (params.color) query.set('color', params.color)
  if (params.type) query.set('type', params.type)
  for (const t of params.tag || []) {
    query.append('tag', t)
  }

  const res = await fetch(`/api/search?${query}`)
  const data = await res.json()
  assets.value = data.assets
}

function handleSearch(params) {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(params), 150)
}

async function selectAsset(id) {
  const res = await fetch(`/api/asset/${id}`)
  selectedAsset.value = await res.json()
}

async function findSimilar(id) {
  selectedAsset.value = null
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
}

onMounted(() => {
  fetchFilters()
  search({ q: null, tag: [], color: null, pack: null, type: null })
})
</script>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
}

.app {
  font-family: system-ui, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem;
}

h1 {
  margin-top: 0;
}
</style>
```

**Step 2: Run frontend tests**

Run: `cd web/frontend && npm test`
Expected: All 16 tests PASS

**Step 3: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): wire up App.vue with API integration"
```

---

## Task 17: Add CORS and Final Testing

**Files:**
- Modify: `web/api.py`

**Step 1: Add CORS middleware for development**

Add near the top of `web/api.py`, after FastAPI instantiation:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 2: Run all backend tests**

Run: `cd web && uv run --script test_api.py`
Expected: All 13 tests PASS

**Step 3: Run all frontend tests**

Run: `cd web/frontend && npm test`
Expected: All 16 tests PASS

**Step 4: Commit**

```bash
git add web/
git commit -m "feat(web): add CORS middleware for development"
```

---

## Task 18: Integration Test

**Step 1: Start API server in background**

```bash
cd web && uv run api.py &
```

**Step 2: Start frontend dev server**

```bash
cd web/frontend && npm run dev
```

**Step 3: Manual verification checklist**

- [ ] Open http://localhost:5173
- [ ] Grid shows assets (if assets.db exists with data)
- [ ] Type in search box - results filter instantly
- [ ] Select pack from dropdown - results filter
- [ ] Select color - results filter
- [ ] Click asset - modal opens with details
- [ ] Click "Find Similar" - modal closes, grid shows similar assets
- [ ] Click X or overlay - modal closes

**Step 4: Stop servers and commit final state**

```bash
git add -A
git commit -m "feat(web): complete web interface for asset search"
```

---

## Summary

Total tasks: 18
Total commits: ~15

Key files created:
- `web/api.py` - FastAPI server
- `web/test_api.py` - API tests
- `web/frontend/src/App.vue` - Main app
- `web/frontend/src/components/SearchBar.vue`
- `web/frontend/src/components/AssetGrid.vue`
- `web/frontend/src/components/AssetModal.vue`
- `web/frontend/tests/*.test.js` - Component tests
