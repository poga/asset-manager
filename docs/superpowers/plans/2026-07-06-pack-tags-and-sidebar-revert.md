# Pack Tags + Sidebar Revert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace auto-derived pack themes with 2D/3D sections + user-assigned pack tags, restore the preview-card sidebar, remove the "Models only" checkbox, and return to the gallery when a pack selection is cleared.

**Architecture:** Backend loses `pack_themes.py` and the theme pass; a new `pack_tags` table (created lazily by the API, so no reindex) feeds `/api/filters` and two tiny write endpoints. `PackGallery.vue` regroups by 2D/3D with a user-tag chip filter and inline tag editing; `PackList.vue` reverts to the original preview cards; `SearchBar.vue`/`App.vue` drop `modelOnly`; App gains one shared active-search predicate driving both "clear search" and "clear packs" returns to the gallery.

**Tech Stack:** Python 3.11+ (uv single-file scripts, FastAPI, SQLite, pytest), Vue 3 + Vitest.

**Spec:** `docs/superpowers/specs/2026-07-06-pack-tags-and-sidebar-revert-design.md`

## Global Constraints

- Run all Python via `uv run` (`uv run --script <file>` for test files); full Python suite via `just test`; frontend via `cd web/frontend && npm test`.
- NO MOCKS in Python tests (real files, real SQLite). Frontend tests follow existing Vitest fetch-stub conventions.
- Comments: max 1 line, 80 chars, why/what, no ticket refs. TDD every behavior change: failing test first.
- Do NOT start/stop the user's servers (ports 8000, 5173, 38471, 38472). Verification uses port 8010.
- Never push to main; work stays on branch `worktree-preview-and-pack-gallery`.
- `/api/filters` pack shape after this plan: `{"name": str, "count": int, "is_3d": bool, "tags": [str, ...]}` — no `theme` key. `is_3d` keeps the any-model EXISTS rule.
- Tag normalization everywhere: `tag.strip().lower()`; empty after strip → HTTP 400.
- `packs.theme` column STAYS in SCHEMA and in `migrate_schema` (existing DBs keep working); only its writers/readers are removed.
- App.vue is a CRLF file — never round-trip it through tools that rewrite line endings; verify with `git diff --stat` that edits touch only intended lines.

---

### Task 1: Remove auto-themes

**Files:**
- Delete: `pack_themes.py`, `test_pack_themes.py`
- Modify: `justfile` (drop the test_pack_themes line)
- Modify: `index.py` (remove `import pack_themes` and the theme-assignment loop in `index()`)
- Modify: `web/api.py` (`filters()` — remove theme probe/column)
- Modify: `test_index.py`, `web/test_api.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `/api/filters` packs = `{name, count, is_3d}` (Task 2 adds `tags`). `packs.theme` column still exists but nothing writes/reads it.

- [ ] **Step 1: Update tests to pin the new shape (failing first)**

In `web/test_api.py`:
- In `test_filters_include_theme_and_is_3d`: rename to `test_filters_include_is_3d`; in the two `INSERT INTO packs` statements drop the `theme` column and its value (`"INSERT INTO packs (id, name, path, asset_count) VALUES (10, 'Forest3D', 'Forest3D', 3)"`); replace the two theme assertions with:

```python
    assert "theme" not in packs["Forest3D"]
```

  (keep both `is_3d` assertions unchanged).
- In `test_filters_tolerate_db_without_theme_column`: keep the legacy schema as is, but replace `assert resp.json()["packs"][0]["theme"] == "Other"` with:

```python
    assert resp.json()["packs"][0]["name"] == "Old"
    assert "theme" not in resp.json()["packs"][0]
```

In `test_index.py`: delete the `test_index_assigns_theme_to_packs` test from `TestPackThemes` (keep `test_migrate_adds_theme_column_to_legacy_db` — the migration stays). If that leaves the class with one test, rename the class to `TestSchemaMigrationTheme` for accuracy (optional, keep simple).

- [ ] **Step 2: Run tests to verify failures**

Run: `uv run --script web/test_api.py -k "filters"`
Expected: FAIL — response still contains `"theme"`.

- [ ] **Step 3: Implement removals**

1. `web/api.py` `filters()`: delete the `has_theme` PRAGMA probe and `theme_col` lines; the packs query becomes:

```python
    packs = conn.execute("""
        SELECT p.id, p.name, p.asset_count AS count,
               EXISTS (SELECT 1 FROM assets a
                       WHERE a.pack_id = p.id
                         AND a.asset_kind IN ('model', 'animation_bundle')) AS is_3d
        FROM packs p
        ORDER BY p.name
    """).fetchall()
```

   (note `p.id` is added now — Task 2 needs it) and the return entry becomes:

```python
        "packs": [
            {"name": p["name"], "count": p["count"], "is_3d": bool(p["is_3d"])}
            for p in packs
        ],
```

2. `index.py`: remove `import pack_themes` and this whole block in `index()`:

```python
    # Reassign themes every run so mapping edits apply without --force
    for row in conn.execute("SELECT id, name FROM packs").fetchall():
        conn.execute(
            "UPDATE packs SET theme = ? WHERE id = ?",
            [pack_themes.assign_theme(row["name"]), row["id"]],
        )
    conn.commit()
```

3. `git rm pack_themes.py test_pack_themes.py`
4. `justfile`: remove the `uv run --script test_pack_themes.py` line from the `test` recipe.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py && uv run --script test_index.py`
Expected: PASS. Then `grep -rn pack_themes --include="*.py" --include="*.vue" --include="justfile" .` returns nothing.

- [ ] **Step 5: Full suite and commit**

Run: `just test`
Expected: all green.

```bash
git add -A
git commit -m "feat: drop auto-derived pack themes"
```

---

### Task 2: pack_tags storage + tag API

**Files:**
- Modify: `index.py` (SCHEMA gains pack_tags table)
- Modify: `web/api.py` (`filters()` tags; new POST/DELETE endpoints; `_ensure_pack_tags` helper)
- Test: `web/test_api.py`

**Interfaces:**
- Consumes: `p.id` in the filters query (Task 1).
- Produces (Task 6 relies on):
  - `/api/filters` packs: `{name, count, is_3d, tags: [str, ...]}` (tags sorted, `[]` default)
  - `POST /api/pack/{pack_name}/tags` body `{"tag": str}` → `{"tags": [...]}` (400 empty tag, 404 unknown pack, idempotent)
  - `DELETE /api/pack/{pack_name}/tags/{tag}` → `{"tags": [...]}` (404 unknown pack; absent tag is no-op success)

- [ ] **Step 1: Write the failing tests**

Add to `web/test_api.py` (after the filters tests; reuse the `test_db` fixture and the module-level `client`, binding via `api.set_db_path` like neighbors):

```python
def _insert_pack(db_path, pack_id, name):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO packs (id, name, path, asset_count) VALUES (?, ?, ?, 1)",
        [pack_id, name, name],
    )
    conn.commit()
    conn.close()


def test_add_and_list_pack_tags(test_db):
    _insert_pack(test_db, 20, "My Pack 1.0")
    import api
    api.set_db_path(test_db)

    resp = client.post("/api/pack/My%20Pack%201.0/tags", json={"tag": " Forest "})
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["forest"]  # trimmed + lowercased

    # idempotent add
    resp = client.post("/api/pack/My%20Pack%201.0/tags", json={"tag": "forest"})
    assert resp.json()["tags"] == ["forest"]

    resp = client.post("/api/pack/My%20Pack%201.0/tags", json={"tag": "b-side"})
    assert resp.json()["tags"] == ["b-side", "forest"]  # sorted

    # tags appear in /api/filters
    resp = client.get("/api/filters")
    packs = {p["name"]: p for p in resp.json()["packs"]}
    assert packs["My Pack 1.0"]["tags"] == ["b-side", "forest"]


def test_remove_pack_tag(test_db):
    _insert_pack(test_db, 21, "TagPack")
    import api
    api.set_db_path(test_db)
    client.post("/api/pack/TagPack/tags", json={"tag": "keep"})
    client.post("/api/pack/TagPack/tags", json={"tag": "drop"})

    resp = client.delete("/api/pack/TagPack/tags/drop")
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["keep"]

    # removing an absent tag is a no-op success
    resp = client.delete("/api/pack/TagPack/tags/ghost")
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["keep"]


def test_pack_tag_validation(test_db):
    _insert_pack(test_db, 22, "ValidPack")
    import api
    api.set_db_path(test_db)

    resp = client.post("/api/pack/ValidPack/tags", json={"tag": "   "})
    assert resp.status_code == 400

    resp = client.post("/api/pack/NoSuchPack/tags", json={"tag": "x"})
    assert resp.status_code == 404

    resp = client.delete("/api/pack/NoSuchPack/tags/x")
    assert resp.status_code == 404


def test_filters_tags_default_empty_without_table(tmp_path):
    # legacy DB: no pack_tags table; filters must not 500 and default to []
    db_path = tmp_path / "legacy2.db"
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
    assert resp.json()["packs"][0]["tags"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -k "pack_tag or tags_default"`
Expected: FAIL — 404s on the new endpoints, missing `tags` key.

- [ ] **Step 3: Implement**

1. `index.py` SCHEMA — add after the `asset_relations` table:

```sql
CREATE TABLE IF NOT EXISTS pack_tags (
    pack_id INTEGER REFERENCES packs(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (pack_id, tag)
);
```

2. `web/api.py` — helper near the other module functions:

```python
def _ensure_pack_tags(conn: sqlite3.Connection) -> None:
    """Lazily create pack_tags so pre-existing DBs work without a reindex."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pack_tags (
            pack_id INTEGER REFERENCES packs(id),
            tag TEXT NOT NULL,
            PRIMARY KEY (pack_id, tag)
        )"""
    )


def _pack_tag_list(conn: sqlite3.Connection, pack_id: int) -> list[str]:
    return [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM pack_tags WHERE pack_id = ? ORDER BY tag", [pack_id]
        )
    ]
```

3. In `filters()` after the packs query:

```python
    _ensure_pack_tags(conn)
    pack_tag_map: dict[int, list[str]] = {}
    for r in conn.execute("SELECT pack_id, tag FROM pack_tags ORDER BY tag"):
        pack_tag_map.setdefault(r["pack_id"], []).append(r["tag"])
```

   and the pack entries become:

```python
        "packs": [
            {
                "name": p["name"],
                "count": p["count"],
                "is_3d": bool(p["is_3d"]),
                "tags": pack_tag_map.get(p["id"], []),
            }
            for p in packs
        ],
```

   Note: `_ensure_pack_tags` issues a CREATE on the read path; commit it (`conn.commit()`) so the table persists.

4. New endpoints (near `pack_preview`, same unquote pattern; `PackTagRequest` next to the other BaseModels):

```python
class PackTagRequest(BaseModel):
    tag: str


def _pack_id_or_404(conn: sqlite3.Connection, pack_name: str) -> int:
    from urllib.parse import unquote
    row = conn.execute(
        "SELECT id FROM packs WHERE name = ?", [unquote(pack_name)]
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pack not found")
    return row["id"]


@app.post("/api/pack/{pack_name}/tags")
def add_pack_tag(pack_name: str, request: PackTagRequest):
    """Attach a user tag to a pack (idempotent)."""
    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Empty tag")
    conn = get_db()
    _ensure_pack_tags(conn)
    pack_id = _pack_id_or_404(conn, pack_name)
    conn.execute(
        "INSERT OR IGNORE INTO pack_tags (pack_id, tag) VALUES (?, ?)",
        [pack_id, tag],
    )
    conn.commit()
    tags = _pack_tag_list(conn, pack_id)
    conn.close()
    return {"tags": tags}


@app.delete("/api/pack/{pack_name}/tags/{tag}")
def remove_pack_tag(pack_name: str, tag: str):
    """Detach a user tag from a pack (absent tag is a no-op)."""
    conn = get_db()
    _ensure_pack_tags(conn)
    pack_id = _pack_id_or_404(conn, pack_name)
    conn.execute(
        "DELETE FROM pack_tags WHERE pack_id = ? AND tag = ?",
        [pack_id, tag.strip().lower()],
    )
    conn.commit()
    tags = _pack_tag_list(conn, pack_id)
    conn.close()
    return {"tags": tags}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: PASS (all).

- [ ] **Step 5: Full suite and commit**

Run: `just test`

```bash
git add index.py web/api.py web/test_api.py
git commit -m "feat: user-assigned pack tags with lazy table creation"
```

---

### Task 3: Remove "Models only"

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/SearchBar.test.js`, `web/frontend/tests/App.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces: SearchBar emits `{q, tag, color, type}` — no `modelOnly`. App's `search()` no longer sets `kind`.

- [ ] **Step 1: Update tests (failing first)**

In `web/frontend/tests/SearchBar.test.js`: delete any test that checks the Models-only checkbox / `modelOnly` in the emitted payload, and add:

```javascript
  it('does not render a models-only checkbox and emits no modelOnly', async () => {
    const wrapper = mount(SearchBar, { props: { filters: { packs: [], tags: [], colors: [] } } })
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
    await wrapper.find('input[type="text"]').setValue('x')
    const emitted = wrapper.emitted('search')
    expect(emitted.at(-1)[0]).not.toHaveProperty('modelOnly')
  })
```

(Adjust the text-input trigger to how SearchBar actually emits — if the query input emits on `input`/debounce, follow the file's existing test pattern for triggering a search emit.)

In `web/frontend/tests/App.test.js`: update any fetch-assertion that expects `kind=model` from a modelOnly search (delete those cases).

Run: `cd web/frontend && npm test` → new SearchBar test FAILS (checkbox exists / modelOnly present).

- [ ] **Step 2: Implement**

`SearchBar.vue`:
- Delete the template block:

```vue
    <label class="filter-chip">
      <input type="checkbox" v-model="modelOnly" @change="emitSearch" />
      Models only
    </label>
```

- Delete `const modelOnly = ref(false)`; remove `modelOnly: modelOnly.value` from `emitSearch()`'s payload; remove `modelOnly.value = false` from `clear()`.

`App.vue`:
- In `search(params)`: delete `if (params.modelOnly) query.set('kind', 'model')`.
- In `handleSearch(params)`: remove `params.modelOnly` from the `hasActive` expression (Task 4 rewrites this line anyway; if Task 4 already landed, just ensure no `modelOnly` reference remains).

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: all green; `grep -rn modelOnly web/frontend/src web/frontend/tests` returns nothing.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue web/frontend/src/App.vue web/frontend/tests/SearchBar.test.js web/frontend/tests/App.test.js
git commit -m "feat: remove models-only search checkbox"
```

---

### Task 4: Clearing packs returns to the gallery

**Files:**
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/App.test.js`

**Interfaces:**
- Consumes: existing `isDefaultHomeView`, `selectedPacks` watcher, `handleSearch`.
- Produces: `hasActiveSearch(params): boolean` helper used by `handleSearch` and the `selectedPacks` watcher.

- [ ] **Step 1: Write the failing test**

Add to `web/frontend/tests/App.test.js` (same conventions as the existing home/search test — fetch mock, stubs including `'PackGallery'`):

```javascript
  it('returns to the gallery when the pack selection is cleared', async () => {
    const wrapper = mount(App, {
      global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail', 'PackGallery'] }
    })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PackGallery' }).exists()).toBe(true)

    // select a pack (leaves home), then clear it
    wrapper.findComponent(PackList).vm.$emit('update:selectedPacks', ['SomePack'])
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PackGallery' }).exists()).toBe(false)

    wrapper.findComponent(PackList).vm.$emit('update:selectedPacks', [])
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PackGallery' }).exists()).toBe(true)
  })
```

(If stubbed PackList can't emit, use `wrapper.findComponent({ name: 'PackList' })` — stubs created from the real component registry still expose `vm.$emit`. Follow whatever pattern the existing pack-selection tests in this file use to drive `selectedPacks`.)

Run: `cd web/frontend && npm test` → FAILS on the final assertion (gallery does not return).

- [ ] **Step 2: Implement**

`App.vue`:
1. Add the helper next to `handleSearch`:

```javascript
function hasActiveSearch(params) {
  return !!(params.q || (params.tag && params.tag.length) || params.color)
}
```

2. Rewrite `handleSearch`'s active check to use it:

```javascript
function handleSearch(params) {
  currentSearchParams.value = params
  if (hasActiveSearch(params)) {
    isDefaultHomeView.value = false
  } else if (selectedPacks.value.length === 0) {
    isDefaultHomeView.value = true
  }
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(params), 150)
}
```

3. In the `selectedPacks` watcher, inside the `if (!isInitializing)` block, add before the mode-specific URL logic:

```javascript
    if (newPacks.length === 0 && oldPacks && oldPacks.length > 0
        && !hasActiveSearch(currentSearchParams.value)) {
      isDefaultHomeView.value = true
    }
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: all green (including the search-from-home tests from the previous branch work).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: return to pack gallery when selection is cleared"
```

---

### Task 5: Sidebar revert to preview cards

**Files:**
- Modify: `web/frontend/src/components/PackList.vue`
- Test: `web/frontend/tests/PackList.test.js`

**Interfaces:**
- Consumes: `formatPackName` from `../utils/packName.js` (keep the import — do not re-inline).
- Produces: `.pack-card` markup in ALL panel states; `.pack-row` gone. Filter input stays always visible.

- [ ] **Step 1: Update tests (failing first)**

In `web/frontend/tests/PackList.test.js`:
- Change `.pack-row` selectors back to `.pack-card` in the selection/click/count tests.
- Delete the `renders card grid when expanded` test (cards are now the only layout); replace with:

```javascript
  it('renders preview cards with images in the default state', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    expect(wrapper.findAll('.pack-card').length).toBe(3)
    expect(wrapper.findAll('.pack-preview').length).toBe(3)
    expect(wrapper.findAll('.pack-row').length).toBe(0)
  })
```

- Keep the always-visible search-input test.

Run: `cd web/frontend && npm test` → PackList tests FAIL (rows render, no cards).

- [ ] **Step 2: Implement the revert**

`PackList.vue` — replace the `v-if="panelState === 'expanded'"` card grid + `v-else` rows blocks with the single original grid (works for both states; `.expanded` class widens it):

```vue
    <div class="pack-grid" :class="{ expanded: panelState === 'expanded' }">
      <div
        v-for="pack in filteredPacks"
        :key="pack.name"
        class="pack-card"
        :class="{ selected: selectedPacks.includes(pack.name) }"
        @click="togglePack(pack.name)"
      >
        <div class="pack-preview-container">
          <img
            :src="getPreviewUrl(pack.name)"
            :alt="pack.name"
            class="pack-preview"
            loading="lazy"
          />
        </div>
        <div class="pack-info">
          <span class="pack-name">{{ formatPackName(pack.name) }}</span>
          <span class="pack-count">{{ pack.count }}</span>
        </div>
      </div>
    </div>
```

Delete the `.pack-rows`, `.pack-row`, `.row-thumb`, `.row-name`, `.row-count` style rules. The `.pack-grid`, `.pack-card`, `.pack-preview-container`, `.pack-preview`, `.pack-info`, `.pack-name`, `.pack-count` rules already exist (they were kept for the expanded state) — verify they're intact; if any were removed, restore:

```css
.pack-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
  display: grid;
  grid-template-columns: 1fr;
  grid-auto-rows: min-content;
  gap: 0.5rem;
}

.pack-grid.expanded {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.pack-card {
  background: var(--color-bg-surface);
  border: 2px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms;
}

.pack-card:hover {
  border-color: var(--color-border-emphasis);
  box-shadow: var(--shadow-card);
}

.pack-card.selected {
  border-color: var(--color-accent);
  border-left-width: 4px;
  box-shadow: 0 0 0 1px var(--color-accent);
}

.pack-preview-container {
  width: 100%;
  height: 150px;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.pack-preview {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.pack-info {
  padding: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  background: var(--color-bg-surface);
}

.pack-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.3;
  flex: 1;
}

.pack-count {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  background: var(--color-accent-light);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
  flex-shrink: 0;
}
```

Header/actions/search-input blocks stay exactly as they are now (no 🔍 toggle).

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
git commit -m "feat: restore preview-card sidebar"
```

---

### Task 6: PackGallery — 2D/3D sections, tag chips, inline tag editing

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue` (full rework)
- Test: `web/frontend/tests/PackGallery.test.js` (full rework)

**Interfaces:**
- Consumes: filters pack shape `{name, count, is_3d, tags}` (Task 2); `formatPackName` util; `POST /api/pack/{name}/tags` and `DELETE /api/pack/{name}/tags/{tag}` returning `{"tags": [...]}`.
- Produces: `PackGallery.vue` with prop `packs: Array`, emits `view-pack(name)` (unchanged contract for App.vue).

- [ ] **Step 1: Rewrite the tests (failing first)**

Replace `web/frontend/tests/PackGallery.test.js` with:

```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PackGallery from '../src/components/PackGallery.vue'

const mockFetch = vi.fn()
global.fetch = mockFetch

const packs = [
  { name: 'Minifantasy_Ancient_Forests', count: 120, is_3d: false, tags: ['forest'] },
  { name: 'KayKit Forest Nature Pack 1.0', count: 80, is_3d: true, tags: ['forest'] },
  { name: 'Minifantasy_Dungeon_v2.3', count: 300, is_3d: false, tags: [] },
]

beforeEach(() => {
  mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: [] }) })
})

afterEach(() => {
  mockFetch.mockReset()
})

describe('PackGallery', () => {
  it('groups packs into 2D and 3D sections', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const titles = wrapper.findAll('.dim-title').map(t => t.text())
    expect(titles).toEqual(['2D', '3D'])
    const twoD = wrapper.findAll('.dim-section')[0].findAll('.gallery-card')
    expect(twoD.length).toBe(2)
  })

  it('omits an empty dimension section', () => {
    const wrapper = mount(PackGallery, { props: { packs: packs.filter(p => !p.is_3d) } })
    expect(wrapper.findAll('.dim-title').map(t => t.text())).toEqual(['2D'])
  })

  it('renders tag chips with pack counts and filters on click', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const chip = wrapper.findAll('.chip').find(c => c.text().includes('forest'))
    expect(chip.text()).toContain('2')

    await chip.trigger('click')
    expect(wrapper.findAll('.gallery-card').length).toBe(2)

    // clicking the active chip clears the filter
    await chip.trigger('click')
    expect(wrapper.findAll('.gallery-card').length).toBe(3)
  })

  it('hides the chip row when no pack has tags', () => {
    const wrapper = mount(PackGallery, { props: { packs: [packs[2]] } })
    expect(wrapper.find('.tag-chips').exists()).toBe(false)
  })

  it('adds a tag through the API and renders it', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: ['cave'] }) })
    const wrapper = mount(PackGallery, { props: { packs } })
    const dungeonCard = wrapper.findAll('.gallery-card')
      .find(c => c.text().includes('Dungeon'))

    await dungeonCard.find('.tag-add').trigger('click')
    const input = dungeonCard.find('.tag-input')
    await input.setValue('cave')
    await input.trigger('keyup.enter')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pack/Minifantasy_Dungeon_v2.3/tags'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(dungeonCard.text()).toContain('cave')
  })

  it('removes a tag through the API', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: [] }) })
    const wrapper = mount(PackGallery, { props: { packs } })
    const forestCard = wrapper.findAll('.gallery-card')
      .find(c => c.text().includes('Ancient Forests'))

    await forestCard.find('.tag-remove').trigger('click')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/tags/forest'),
      expect.objectContaining({ method: 'DELETE' })
    )
    expect(forestCard.find('.tag-chip').exists()).toBe(false)
  })

  it('tag interactions do not navigate to the pack', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const card = wrapper.findAll('.gallery-card')[0]
    await card.find('.card-tags').trigger('click')
    expect(wrapper.emitted('view-pack')).toBeFalsy()
    await card.trigger('click')
    expect(wrapper.emitted('view-pack')).toBeTruthy()
  })
})
```

Run: `cd web/frontend && npm test` → PackGallery tests FAIL (old theme layout).

- [ ] **Step 2: Rewrite the component**

Replace `web/frontend/src/components/PackGallery.vue` with:

```vue
<template>
  <div class="pack-gallery">
    <div v-if="allTags.length" class="tag-chips">
      <button
        v-for="t in allTags"
        :key="t.tag"
        class="chip"
        :class="{ active: activeTag === t.tag }"
        @click="toggleTag(t.tag)"
      >
        {{ t.tag }} <span class="chip-count">{{ t.count }}</span>
      </button>
    </div>

    <section v-for="s in sections" :key="s.label" class="dim-section">
      <h2 class="dim-title">{{ s.label }}</h2>
      <div class="card-grid">
        <div
          v-for="pack in s.packs"
          :key="pack.name"
          class="gallery-card"
          @click="$emit('view-pack', pack.name)"
        >
          <div class="card-cover">
            <img
              v-if="!failedCovers[pack.name]"
              :src="previewUrl(pack.name)"
              :alt="formatPackName(pack.name)"
              loading="lazy"
              @error="failedCovers[pack.name] = true"
            />
            <span v-else class="cover-placeholder">📦</span>
          </div>
          <div class="card-meta">
            <span class="card-name">{{ formatPackName(pack.name) }}</span>
            <span class="card-count">{{ pack.count }}</span>
          </div>
          <div class="card-tags" @click.stop>
            <span v-for="tag in tagsOf(pack)" :key="tag" class="tag-chip">
              {{ tag }}<button class="tag-remove" @click="removeTag(pack, tag)">×</button>
            </span>
            <input
              v-if="editingPack === pack.name"
              v-model="newTag"
              class="tag-input"
              placeholder="tag"
              @keyup.enter="addTag(pack)"
              @keyup.escape="stopEditing"
              @blur="stopEditing"
              v-focus
            />
            <button v-else class="tag-add" @click="startEditing(pack.name)">+</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { formatPackName } from '../utils/packName.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

const props = defineProps({
  packs: { type: Array, required: true }
})

defineEmits(['view-pack'])

const failedCovers = reactive({})
// local tag state; seeded from props, updated from API responses
const tagOverrides = reactive({})
const activeTag = ref(null)
const editingPack = ref(null)
const newTag = ref('')

const vFocus = { mounted: el => el.focus() }

function tagsOf(pack) {
  return tagOverrides[pack.name] ?? pack.tags ?? []
}

const allTags = computed(() => {
  const counts = {}
  for (const pack of props.packs) {
    for (const tag of tagsOf(pack)) {
      counts[tag] = (counts[tag] || 0) + 1
    }
  }
  return Object.keys(counts).sort().map(tag => ({ tag, count: counts[tag] }))
})

const sections = computed(() => {
  const visible = activeTag.value
    ? props.packs.filter(p => tagsOf(p).includes(activeTag.value))
    : props.packs
  return [
    { label: '2D', packs: visible.filter(p => !p.is_3d) },
    { label: '3D', packs: visible.filter(p => p.is_3d) },
  ].filter(s => s.packs.length)
})

function toggleTag(tag) {
  activeTag.value = activeTag.value === tag ? null : tag
}

function previewUrl(packName) {
  return `${API_BASE}/pack-preview/${encodeURIComponent(packName)}`
}

function startEditing(packName) {
  editingPack.value = packName
  newTag.value = ''
}

function stopEditing() {
  editingPack.value = null
  newTag.value = ''
}

async function addTag(pack) {
  const tag = newTag.value.trim()
  if (!tag) return
  const res = await fetch(`${API_BASE}/pack/${encodeURIComponent(pack.name)}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag })
  })
  if (res.ok) {
    tagOverrides[pack.name] = (await res.json()).tags
  }
  stopEditing()
}

async function removeTag(pack, tag) {
  const res = await fetch(
    `${API_BASE}/pack/${encodeURIComponent(pack.name)}/tags/${encodeURIComponent(tag)}`,
    { method: 'DELETE' }
  )
  if (res.ok) {
    tagOverrides[pack.name] = (await res.json()).tags
  }
}
</script>

<style scoped>
.pack-gallery {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.tag-chips {
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

.chip.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.chip-count {
  color: var(--color-text-secondary);
  margin-left: 0.25rem;
}

.dim-title {
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
  padding: 0.5rem 0.5rem 0.25rem;
}

.card-name {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.25;
}

.card-count {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding: 0 0.5rem 0.5rem;
  cursor: default;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.125rem;
  font-size: 0.625rem;
  padding: 0.0625rem 0.375rem;
  border-radius: 4px;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

.tag-remove {
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 0.6875rem;
  padding: 0;
  line-height: 1;
}

.tag-remove:hover {
  color: var(--color-text-primary);
}

.tag-add {
  border: 1px dashed var(--color-border);
  background: none;
  color: var(--color-text-secondary);
  border-radius: 4px;
  font-size: 0.625rem;
  padding: 0.0625rem 0.375rem;
  cursor: pointer;
  line-height: 1.2;
}

.tag-add:hover {
  border-color: var(--color-accent);
  color: var(--color-text-primary);
}

.tag-input {
  width: 5.5rem;
  font-size: 0.625rem;
  padding: 0.0625rem 0.25rem;
  border: 1px solid var(--color-accent);
  border-radius: 4px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}
</style>
```

Note: `v-focus` is a local custom directive — with `<script setup>`, a `const vFocus = {...}` is auto-registered for `v-focus`. `keyup.enter` fires before `blur`; `stopEditing` after a successful add is safe.

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: all green (App.test.js still stubs PackGallery, so App tests are unaffected).

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js
git commit -m "feat: gallery groups by 2D/3D with user tag chips and inline editing"
```

---

### Task 7: Verification + PR

**Files:**
- None (verification only).

- [ ] **Step 1: Full suites**

```bash
just test
cd web/frontend && npm test && npm run build && cd ../..
```

Expected: all green, build succeeds.

- [ ] **Step 2: Live verification (disposable copy of the real DB)**

```bash
MAIN=/Users/poga/projects/asset-manager
cp "$MAIN/assets.db" ./assets.db
cp -R "$MAIN/.index" ./.index
uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --port 8010
```

Browse `http://localhost:8010/assets/` (the API serves the built frontend) and verify:
- Home: 2D and 3D sections (no theme sections), no chip row yet (no tags).
- Sidebar: preview cards are back (150px covers), filter input visible.
- Search bar: no "Models only" checkbox.
- Add a tag to a pack via the card `+` → tag chip appears on the card and in the top chip row; chip click filters; second click clears; `×` removes the tag.
- Select a pack in the sidebar, then Clear → gallery returns.
- Type a query → results; clear it → gallery returns.
Take a screenshot for the user. Kill the uvicorn process and delete the copied `assets.db`/`.index` when done (tag writes went to the copy, NOT the live DB — note for the user that tags they add before merge won't persist).

- [ ] **Step 3: Push and PR**

```bash
git push
gh pr create --draft --title "Pack tags + sidebar revert" --body "$(cat <<'EOF'
## Summary
- Auto-derived themes are gone; the gallery now has two sections (2D / 3D) plus user-assigned pack tags: add/remove inline on cards, filter via tag chips. Tags live in a new `pack_tags` table the API creates lazily — no reindex needed.
- The sidebar is back to full preview cards (150px covers); the filter input stays always visible.
- "Models only" checkbox removed.
- Clearing a pack selection (with no active search) returns to the gallery, matching the clear-search behavior.

## Rollout
None required — deploy is merge + API restart. `packs.theme` column stays in the DB unused.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01WdYKpvGrkVbX9wExiTMAYN
EOF
)"
```

---

## Self-Review Notes

- Spec coverage: removals (Task 1), tag storage/API (Task 2), Models-only removal (Task 3), clear-packs-returns-home (Task 4), sidebar revert (Task 5), gallery rework (Task 6), live verification + rollout note (Task 7). Error handling embedded: 400/404 + idempotency (Task 2 tests), legacy-DB tolerance (Task 2 last test), empty tag input ignored (Task 6 `addTag` guard), missing covers placeholder (kept in Task 6).
- Task 3 and Task 4 both touch `handleSearch`; they are ordered (3 before 4) and Task 3 carries a guard note for either ordering.
- Frontend tag-editing tests stub `fetch` — consistent with the repo's existing Vitest conventions (App.test.js does the same); Python tests stay mock-free.
- Task 6 removes the 2D/3D badge from cards deliberately: the section headers now carry that information (YAGNI).
