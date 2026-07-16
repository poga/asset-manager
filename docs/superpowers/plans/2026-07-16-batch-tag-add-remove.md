# Batch Tag Add/Remove Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add or remove one user tag across many selected packs or many selected assets at once, from the grid views.

**Architecture:** Two new batch API endpoints (`POST /api/assets/tags`, `POST /api/packs/tags`), each carrying an `op: "add" | "remove"` discriminator and returning each affected item's new tag list. Frontend gains a per-view "Select" mode with per-card checkboxes; each grid owns its own selection and calls the batch endpoint, and both grids share a presentational `BatchTagBar.vue` (type-to-add, click-chip-to-remove).

**Tech Stack:** FastAPI + SQLite (backend), Vue 3 `<script setup>` + Vite (frontend). Backend tests: pytest via `just test-api`. Frontend tests: vitest + `@vue/test-utils` (`npm test` in `web/frontend`).

## Global Constraints

- Run scripts with `uv run`, never bare `python`.
- API server (port 38471) and frontend (port 5173/38472) are already running; do not start them.
- Comments: at most one line, ≤80 chars, minimal, focused on why/what.
- No mocks in backend tests — real SQLite via the `test_db` fixture. Frontend component tests mock only the `fetch` boundary (established repo pattern).
- Tags are stored trimmed + lower-cased, matching existing single-item endpoints.
- All work happens in the current worktree on branch `worktree-batch-tag-add-remove`. Never commit to `main`.

---

### Task 1: Batch asset-tag endpoint

**Files:**
- Modify: `web/api.py` (add `Literal` to the `typing` import; add `BatchAssetTagRequest` near `AssetTagRequest` ~line 79; add endpoint after `remove_asset_tag` ~line 470)
- Test: `web/test_api.py` (append new tests)

**Interfaces:**
- Produces: `POST /api/assets/tags` accepting `{ asset_ids: list[int], tag: str, op: "add"|"remove" }`, returning `{ "results": [ { "id": int, "tags": list[str] }, ... ] }`. Unknown ids are skipped (absent from `results`). Empty tag or empty `asset_ids` → 400.

- [ ] **Step 1: Write the failing tests**

Append to `web/test_api.py`:

```python
def test_batch_asset_tags_add(test_db):
    import api
    api.set_db_path(test_db)
    resp = client.post("/api/assets/tags",
                       json={"asset_ids": [1, 2], "tag": " Dungeon ", "op": "add"})
    assert resp.status_code == 200
    results = {r["id"]: r["tags"] for r in resp.json()["results"]}
    assert "dungeon" in results[1] and "dungeon" in results[2]  # trimmed + lowercased


def test_batch_asset_tags_add_is_idempotent(test_db):
    import api
    api.set_db_path(test_db)
    client.post("/api/assets/tags", json={"asset_ids": [1], "tag": "wip", "op": "add"})
    resp = client.post("/api/assets/tags", json={"asset_ids": [1], "tag": "wip", "op": "add"})
    assert resp.json()["results"][0]["tags"].count("wip") == 1


def test_batch_asset_tags_remove(test_db):
    import api
    api.set_db_path(test_db)
    client.post("/api/assets/tags", json={"asset_ids": [1, 2], "tag": "shared", "op": "add"})
    resp = client.post("/api/assets/tags",
                       json={"asset_ids": [1, 2], "tag": "shared", "op": "remove"})
    for r in resp.json()["results"]:
        assert "shared" not in r["tags"]


def test_batch_asset_tags_remove_absent_is_noop(test_db):
    import api
    api.set_db_path(test_db)
    resp = client.post("/api/assets/tags",
                       json={"asset_ids": [1], "tag": "never-had-it", "op": "remove"})
    assert resp.status_code == 200  # no error, asset unchanged


def test_batch_asset_tags_skips_unknown_ids(test_db):
    import api
    api.set_db_path(test_db)
    resp = client.post("/api/assets/tags",
                       json={"asset_ids": [1, 9999], "tag": "keep", "op": "add"})
    ids = [r["id"] for r in resp.json()["results"]]
    assert ids == [1]  # unknown id skipped, present id still applied


def test_batch_asset_tags_validation(test_db):
    import api
    api.set_db_path(test_db)
    assert client.post("/api/assets/tags",
                       json={"asset_ids": [1], "tag": "  ", "op": "add"}).status_code == 400
    assert client.post("/api/assets/tags",
                       json={"asset_ids": [], "tag": "x", "op": "add"}).status_code == 400
    assert client.post("/api/assets/tags",
                       json={"asset_ids": [1], "tag": "x", "op": "bogus"}).status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/poga/projects/asset-manager/.claude/worktrees/batch-tag-add-remove && just test-api`
Expected: the six `test_batch_asset_tags_*` tests FAIL (404/Not Found — route missing).

- [ ] **Step 3: Implement**

In `web/api.py`, change the typing import:

```python
from typing import Literal, Optional
```

Add the request model near `AssetTagRequest`:

```python
class BatchAssetTagRequest(BaseModel):
    asset_ids: list[int]
    tag: str
    op: Literal["add", "remove"]
```

Add the endpoint after `remove_asset_tag`:

```python
@app.post("/api/assets/tags")
def batch_asset_tags(request: BatchAssetTagRequest):
    """Add or remove one tag across many assets in a single transaction."""
    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Empty tag")
    if not request.asset_ids:
        raise HTTPException(status_code=400, detail="No assets")
    conn = get_db()
    marks = ",".join("?" * len(request.asset_ids))
    ids = [r["id"] for r in conn.execute(
        f"SELECT id FROM assets WHERE id IN ({marks})", request.asset_ids)]
    if request.op == "add":
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", [tag])
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", [tag]).fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO asset_tags (asset_id, tag_id, source) VALUES (?, ?, 'user')",
            [(aid, tag_id) for aid in ids])
    elif ids:
        row = conn.execute("SELECT id FROM tags WHERE name = ?", [tag]).fetchone()
        if row:
            conn.execute(
                f"DELETE FROM asset_tags WHERE tag_id = ? AND asset_id IN ({','.join('?' * len(ids))})",
                [row["id"], *ids])
    conn.commit()
    results = [
        {"id": aid, "tags": [r["name"] for r in conn.execute(
            "SELECT t.name FROM asset_tags at JOIN tags t ON at.tag_id = t.id "
            "WHERE at.asset_id = ? ORDER BY t.name", [aid])]}
        for aid in ids]
    conn.close()
    return {"results": results}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-api`
Expected: all API tests PASS (including the six new ones).

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: batch asset tag add/remove endpoint"
```

---

### Task 2: Batch pack-tag endpoint

**Files:**
- Modify: `web/api.py` (add `BatchPackTagRequest` near `PackTagRequest`; add endpoint after `remove_pack_tag` ~line 817)
- Test: `web/test_api.py` (append)

**Interfaces:**
- Consumes: `_ensure_pack_tags`, `_pack_tag_list` (existing helpers in `web/api.py`).
- Produces: `POST /api/packs/tags` accepting `{ pack_names: list[str], tag: str, op: "add"|"remove" }`, returning `{ "results": [ { "name": str, "tags": list[str] }, ... ] }`. Unknown names skipped. Empty tag or empty `pack_names` → 400.

- [ ] **Step 1: Write the failing tests**

Append to `web/test_api.py`:

```python
def test_batch_pack_tags_add_and_remove(test_db):
    _insert_pack(test_db, 30, "Pack A")
    _insert_pack(test_db, 31, "Pack B")
    import api
    api.set_db_path(test_db)

    resp = client.post("/api/packs/tags",
                       json={"pack_names": ["Pack A", "Pack B"], "tag": " Forest ", "op": "add"})
    assert resp.status_code == 200
    got = {r["name"]: r["tags"] for r in resp.json()["results"]}
    assert got["Pack A"] == ["forest"] and got["Pack B"] == ["forest"]

    resp = client.post("/api/packs/tags",
                       json={"pack_names": ["Pack A", "Pack B"], "tag": "forest", "op": "remove"})
    for r in resp.json()["results"]:
        assert r["tags"] == []


def test_batch_pack_tags_skips_unknown_names(test_db):
    _insert_pack(test_db, 32, "Real Pack")
    import api
    api.set_db_path(test_db)
    resp = client.post("/api/packs/tags",
                       json={"pack_names": ["Real Pack", "Ghost Pack"], "tag": "x", "op": "add"})
    names = [r["name"] for r in resp.json()["results"]]
    assert names == ["Real Pack"]


def test_batch_pack_tags_validation(test_db):
    _insert_pack(test_db, 33, "V Pack")
    import api
    api.set_db_path(test_db)
    assert client.post("/api/packs/tags",
                       json={"pack_names": ["V Pack"], "tag": " ", "op": "add"}).status_code == 400
    assert client.post("/api/packs/tags",
                       json={"pack_names": [], "tag": "x", "op": "add"}).status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-api`
Expected: the three `test_batch_pack_tags_*` tests FAIL (route missing).

- [ ] **Step 3: Implement**

Add the request model near `PackTagRequest`:

```python
class BatchPackTagRequest(BaseModel):
    pack_names: list[str]
    tag: str
    op: Literal["add", "remove"]
```

Add the endpoint after `remove_pack_tag`:

```python
@app.post("/api/packs/tags")
def batch_pack_tags(request: BatchPackTagRequest):
    """Add or remove one tag across many packs in a single transaction."""
    from urllib.parse import unquote
    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Empty tag")
    if not request.pack_names:
        raise HTTPException(status_code=400, detail="No packs")
    conn = get_db()
    _ensure_pack_tags(conn)
    wanted = [unquote(n) for n in request.pack_names]
    marks = ",".join("?" * len(wanted))
    found = [(r["id"], r["name"]) for r in conn.execute(
        f"SELECT id, name FROM packs WHERE name IN ({marks})", wanted)]
    if request.op == "add":
        conn.executemany("INSERT OR IGNORE INTO pack_tags (pack_id, tag) VALUES (?, ?)",
                         [(pid, tag) for pid, _ in found])
    else:
        ids = [pid for pid, _ in found]
        if ids:
            conn.execute(
                f"DELETE FROM pack_tags WHERE tag = ? AND pack_id IN ({','.join('?' * len(ids))})",
                [tag, *ids])
    conn.commit()
    results = [{"name": name, "tags": _pack_tag_list(conn, pid)} for pid, name in found]
    conn.close()
    return {"results": results}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-api`
Expected: all API tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: batch pack tag add/remove endpoint"
```

---

### Task 3: BatchTagBar component + API helpers

**Files:**
- Create: `web/frontend/src/components/BatchTagBar.vue`
- Modify: `web/frontend/src/api/boards.js` (append two helpers)
- Test: `web/frontend/tests/BatchTagBar.test.js`

**Interfaces:**
- Produces `BatchTagBar.vue`: props `count: Number`, `unionTags: Array<string>`; emits `add(tag: string)` (trimmed, non-empty), `remove(tag: string)`, `clear()`.
- Produces in `boards.js`: `batchAssetTags(assetIds, tag, op) -> Promise<{results}>`, `batchPackTags(packNames, tag, op) -> Promise<{results}>`.

- [ ] **Step 1: Write the failing test**

Create `web/frontend/tests/BatchTagBar.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchTagBar from '../src/components/BatchTagBar.vue'

describe('BatchTagBar', () => {
  it('shows the selection count', () => {
    const w = mount(BatchTagBar, { props: { count: 3, unionTags: [] } })
    expect(w.find('.batch-count').text()).toContain('3')
  })

  it('emits add with the trimmed tag then clears the input', async () => {
    const w = mount(BatchTagBar, { props: { count: 2, unionTags: [] } })
    const input = w.find('.batch-add-input')
    await input.setValue('  dungeon ')
    await input.trigger('keyup.enter')
    expect(w.emitted('add')[0]).toEqual(['dungeon'])
    expect(input.element.value).toBe('')
  })

  it('does not emit add for a blank tag', async () => {
    const w = mount(BatchTagBar, { props: { count: 1, unionTags: [] } })
    const input = w.find('.batch-add-input')
    await input.setValue('   ')
    await input.trigger('keyup.enter')
    expect(w.emitted('add')).toBeUndefined()
  })

  it('emits remove when a union chip × is clicked', async () => {
    const w = mount(BatchTagBar, { props: { count: 2, unionTags: ['2d', 'wip'] } })
    await w.findAll('.batch-chip-remove')[1].trigger('click')
    expect(w.emitted('remove')[0]).toEqual(['wip'])
  })

  it('emits clear', async () => {
    const w = mount(BatchTagBar, { props: { count: 1, unionTags: [] } })
    await w.find('.batch-clear').trigger('click')
    expect(w.emitted('clear')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/.claude/worktrees/batch-tag-add-remove/web/frontend && npx vitest run tests/BatchTagBar.test.js`
Expected: FAIL (cannot resolve `../src/components/BatchTagBar.vue`).

- [ ] **Step 3: Implement the component**

Create `web/frontend/src/components/BatchTagBar.vue`:

```vue
<template>
  <div class="batch-bar">
    <span class="batch-count">{{ count }} selected</span>
    <input
      v-model="draft"
      class="batch-add-input"
      placeholder="add tag"
      @keyup.enter="submitAdd"
    />
    <div v-if="unionTags.length" class="batch-union">
      <span v-for="tag in unionTags" :key="tag" class="batch-chip">
        {{ tag }}<button class="batch-chip-remove" @click="$emit('remove', tag)">×</button>
      </span>
    </div>
    <button class="batch-clear" @click="$emit('clear')">Clear</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  count: { type: Number, required: true },
  unionTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['add', 'remove', 'clear'])
const draft = ref('')

function submitAdd() {
  const t = draft.value.trim()
  if (!t) return
  emit('add', t)
  draft.value = ''
}
</script>

<style scoped>
.batch-bar {
  position: fixed; left: 50%; bottom: 1.25rem; transform: translateX(-50%);
  display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;
  max-width: min(90vw, 720px); padding: 0.6rem 1rem;
  background: var(--panel-bg, #1e1e1e); color: var(--text, #eee);
  border: 1px solid var(--border, #333); border-radius: 0.6rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35); z-index: 50;
}
.batch-count { font-weight: 600; white-space: nowrap; }
.batch-add-input {
  padding: 0.3rem 0.5rem; border: 1px solid var(--border, #444);
  border-radius: 0.35rem; background: transparent; color: inherit;
}
.batch-union { display: flex; flex-wrap: wrap; gap: 0.375rem; }
.batch-chip {
  display: inline-flex; align-items: center; gap: 0.2rem;
  padding: 0.15rem 0.45rem; border-radius: 0.75rem;
  background: var(--chip-bg, #333); font-size: 0.85rem;
}
.batch-chip-remove {
  border: none; background: none; color: inherit; cursor: pointer;
  font-size: 1rem; line-height: 1; padding: 0;
}
.batch-clear {
  border: none; background: none; color: var(--muted, #999);
  cursor: pointer; text-decoration: underline;
}
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/BatchTagBar.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Add the API helpers**

Append to `web/frontend/src/api/boards.js`:

```javascript
export function batchAssetTags(assetIds, tag, op) {
  return fetch(`${API_BASE}/assets/tags`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_ids: assetIds, tag, op })
  }).then(json)
}

export function batchPackTags(packNames, tag, op) {
  return fetch(`${API_BASE}/packs/tags`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pack_names: packNames, tag, op })
  }).then(json)
}
```

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/BatchTagBar.vue web/frontend/src/api/boards.js web/frontend/tests/BatchTagBar.test.js
git commit -m "feat: BatchTagBar component and batch tag API helpers"
```

---

### Task 4: PackGallery select mode + batch tagging

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue`
- Test: `web/frontend/tests/PackGallery.test.js` (append a `describe` block)

**Interfaces:**
- Consumes: `BatchTagBar.vue`; `batchPackTags` from `../api/boards.js`; existing `tagOverrides` reactive map and `tagsOf(pack)`.
- Behavior: a "Select" button toggles select mode; in select mode a card click toggles its selection (name added/removed) instead of emitting `view-pack`; a `BatchTagBar` shows when ≥1 pack is selected; add/remove call `batchPackTags` and update `tagOverrides` from the response.

- [ ] **Step 1: Write the failing test**

Append to `web/frontend/tests/PackGallery.test.js`:

```javascript
describe('PackGallery batch tagging', () => {
  it('selects packs in select mode and batch-adds a tag', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ results: [
        { name: 'Minifantasy_Ancient_Forests', tags: ['forest', 'dungeon'] },
      ] }),
    })
    const wrapper = mount(PackGallery, { props: { packs } })

    await wrapper.find('.select-toggle').trigger('click')
    await wrapper.findAll('.gallery-card')[0].trigger('click')

    // selecting must NOT navigate into the pack
    expect(wrapper.emitted('view-pack')).toBeUndefined()
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    expect(wrapper.find('.batch-count').text()).toContain('1')

    await wrapper.find('.batch-add-input').setValue('dungeon')
    await wrapper.find('.batch-add-input').trigger('keyup.enter')
    await flushPromises()

    const [url, opts] = mockFetch.mock.calls.at(-1)
    expect(url).toMatch(/\/packs\/tags$/)
    expect(JSON.parse(opts.body)).toEqual({
      pack_names: ['Minifantasy_Ancient_Forests'], tag: 'dungeon', op: 'add',
    })
    // response applied via tagOverrides -> chip now visible on the card
    expect(wrapper.findAll('.gallery-card')[0].text()).toContain('dungeon')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/PackGallery.test.js`
Expected: FAIL (no `.select-toggle`).

- [ ] **Step 3: Implement — script additions**

In `web/frontend/src/components/PackGallery.vue` `<script setup>`, add the import and `batchPackTags`:

```javascript
import BatchTagBar from './BatchTagBar.vue'
import { batchPackTags } from '../api/boards.js'
```

Add state and handlers (near the other refs):

```javascript
const selectMode = ref(false)
const selectedNames = ref([])

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedNames.value = []
}

function onCardClick(pack) {
  if (!selectMode.value) { emit('view-pack', pack.name); return }
  const i = selectedNames.value.indexOf(pack.name)
  if (i === -1) selectedNames.value.push(pack.name)
  else selectedNames.value.splice(i, 1)
}

const selectionUnion = computed(() => {
  const set = new Set()
  for (const p of props.packs)
    if (selectedNames.value.includes(p.name)) tagsOf(p).forEach(t => set.add(t))
  return [...set].sort(collator.compare)
})

async function applyResults(results) {
  for (const r of results) tagOverrides[r.name] = r.tags
}

async function batchAdd(tag) {
  applyResults((await batchPackTags(selectedNames.value, tag, 'add')).results)
}

async function batchRemove(tag) {
  applyResults((await batchPackTags(selectedNames.value, tag, 'remove')).results)
}

function clearSelection() { selectedNames.value = [] }
```

(`collator` already exists in this file for sorting; reuse it.)

- [ ] **Step 4: Implement — template additions**

Add a Select toggle just inside the root `.pack-gallery`, above `.tag-chips`:

```html
<div class="gallery-toolbar">
  <button class="select-toggle" :class="{ active: selectMode }" @click="toggleSelectMode">
    {{ selectMode ? 'Done' : 'Select' }}
  </button>
</div>
```

Change the card element to route clicks through `onCardClick` and mark selection, and add a checkbox. Replace the opening `<div ... class="gallery-card" @click=...>` with:

```html
<div
  v-for="pack in s.packs"
  :key="pack.name"
  class="gallery-card"
  :class="{ selectable: selectMode, selected: selectedNames.includes(pack.name) }"
  @click="onCardClick(pack)"
>
  <span v-if="selectMode" class="select-check">
    {{ selectedNames.includes(pack.name) ? '☑' : '☐' }}
  </span>
```

Add the batch bar just before the closing `</div>` of `.pack-gallery`:

```html
<BatchTagBar
  v-if="selectMode && selectedNames.length"
  :count="selectedNames.length"
  :union-tags="selectionUnion"
  @add="batchAdd"
  @remove="batchRemove"
  @clear="clearSelection"
/>
```

Add minimal styles in `<style scoped>`:

```css
.gallery-toolbar { display: flex; justify-content: flex-end; margin-bottom: 0.5rem; }
.select-toggle { padding: 0.3rem 0.75rem; border: 1px solid var(--border, #444);
  border-radius: 0.35rem; background: transparent; color: inherit; cursor: pointer; }
.select-toggle.active { background: var(--accent, #4a7); color: #fff; }
.gallery-card.selectable { cursor: pointer; }
.gallery-card.selected { outline: 2px solid var(--accent, #4a7); outline-offset: 2px; }
.select-check { position: absolute; top: 0.4rem; left: 0.4rem; font-size: 1.1rem; }
```

(Ensure `.gallery-card` is `position: relative` so `.select-check` anchors; add it if absent.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run tests/PackGallery.test.js`
Expected: PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js
git commit -m "feat: pack batch tagging via select mode"
```

---

### Task 5: AssetGrid select mode + batch tagging

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Test: `web/frontend/tests/AssetGrid.test.js` (append a `describe` block)

**Interfaces:**
- Consumes: `BatchTagBar.vue`; `batchAssetTags` from `../api/boards.js`; `props.assets` (each asset carries `id` and `tags`).
- Behavior: a "Select" button toggles select mode; in select mode clicking a card's image toggles selection (id added/removed) instead of emitting `select`; a `BatchTagBar` shows when ≥1 asset is selected; add/remove call `batchAssetTags` and store updated tags in a local `tagOverrides` map so the union recomputes. Selection clears when `props.assets` changes (new search).

- [ ] **Step 1: Write the failing test**

First, update the import line at the top of `web/frontend/tests/AssetGrid.test.js` to add `vi` and `flushPromises` (it currently imports `{ describe, it, expect }` and `{ mount }`):

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
```

Then append (asset shape matches the file's existing `mockAssets` plus a `tags` field):

```javascript
describe('AssetGrid batch tagging', () => {
  const assets = [
    { id: 1, filename: 'a.png', path: '/a.png', width: 64, height: 64, pack: 'p', tags: ['wip'] },
    { id: 2, filename: 'b.png', path: '/b.png', width: 64, height: 64, pack: 'p', tags: ['wip', 'hero'] },
  ]

  it('selects assets and batch-removes a tag via a union chip', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ results: [
        { id: 1, tags: [] }, { id: 2, tags: ['hero'] },
      ] }),
    })
    const wrapper = mount(AssetGrid, { props: { assets } })

    await wrapper.find('.select-toggle').trigger('click')
    const cards = wrapper.findAll('.asset-image-container')
    await cards[0].trigger('click')
    await cards[1].trigger('click')

    expect(wrapper.emitted('select')).toBeUndefined()  // selecting != opening
    expect(wrapper.find('.batch-count').text()).toContain('2')
    // union of ['wip'] and ['wip','hero'] = ['hero','wip'] (sorted)
    const chips = wrapper.findAll('.batch-chip').map(c => c.text().replace('×', '').trim())
    expect(chips).toEqual(['hero', 'wip'])

    // 'wip' is the second sorted chip
    await wrapper.findAll('.batch-chip-remove')[1].trigger('click')
    await flushPromises()

    const [url, opts] = global.fetch.mock.calls.at(-1)
    expect(url).toMatch(/\/assets\/tags$/)
    expect(JSON.parse(opts.body)).toEqual({ asset_ids: [1, 2], tag: 'wip', op: 'remove' })
    // overrides applied -> union recomputed to just ['hero']
    expect(wrapper.findAll('.batch-chip').map(c => c.text().replace('×', '').trim())).toEqual(['hero'])
  })

  it('clears selection when the results change', async () => {
    global.fetch = vi.fn()
    const wrapper = mount(AssetGrid, { props: { assets } })
    await wrapper.find('.select-toggle').trigger('click')
    await wrapper.findAll('.asset-image-container')[0].trigger('click')
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    await wrapper.setProps({ assets: [{ id: 3, filename: 'c.png', path: '/c.png', width: 64, height: 64, pack: 'p', tags: [] }] })
    expect(wrapper.find('.batch-bar').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/AssetGrid.test.js`
Expected: FAIL (no `.select-toggle`).

- [ ] **Step 3: Implement — script additions**

In `web/frontend/src/components/AssetGrid.vue` `<script setup>`, add:

```javascript
import { ref, reactive, computed, watch } from 'vue'
import BatchTagBar from './BatchTagBar.vue'
import { batchAssetTags } from '../api/boards.js'
```

(Merge with the existing `vue` import rather than duplicating it.)

```javascript
const selectMode = ref(false)
const selectedIds = ref([])
const tagOverrides = reactive({})

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = []
}

function tagsOf(asset) {
  return tagOverrides[asset.id] ?? asset.tags ?? []
}

function onCardClick(asset) {
  if (!selectMode.value) { emit('select', asset.id); return }
  const i = selectedIds.value.indexOf(asset.id)
  if (i === -1) selectedIds.value.push(asset.id)
  else selectedIds.value.splice(i, 1)
}

const selectionUnion = computed(() => {
  const set = new Set()
  for (const a of props.assets)
    if (selectedIds.value.includes(a.id)) tagsOf(a).forEach(t => set.add(t))
  return [...set].sort()
})

function applyResults(results) {
  for (const r of results) tagOverrides[r.id] = r.tags
}

async function batchAdd(tag) {
  applyResults((await batchAssetTags(selectedIds.value, tag, 'add')).results)
}

async function batchRemove(tag) {
  applyResults((await batchAssetTags(selectedIds.value, tag, 'remove')).results)
}

function clearSelection() { selectedIds.value = [] }

watch(() => props.assets, () => { selectedIds.value = [] })
```

- [ ] **Step 4: Implement — template additions**

Add a toolbar with the Select toggle just inside `.asset-grid-container`, before `.result-count`:

```html
<div class="grid-toolbar">
  <button class="select-toggle" :class="{ active: selectMode }" @click="toggleSelectMode">
    {{ selectMode ? 'Done' : 'Select' }}
  </button>
</div>
```

Change the image container to route clicks through `onCardClick` and show a checkbox. Replace its opening tag / click handler:

```html
<div
  class="asset-image-container"
  :class="{ selected: selectedIds.includes(asset.id) }"
  :style="containerStyle(asset)"
  @click="onCardClick(asset)"
>
  <span v-if="selectMode" class="select-check">
    {{ selectedIds.includes(asset.id) ? '☑' : '☐' }}
  </span>
```

Add the batch bar before the closing `</div>` of `.asset-grid-container`:

```html
<BatchTagBar
  v-if="selectMode && selectedIds.length"
  :count="selectedIds.length"
  :union-tags="selectionUnion"
  @add="batchAdd"
  @remove="batchRemove"
  @clear="clearSelection"
/>
```

Add minimal styles:

```css
.grid-toolbar { display: flex; justify-content: flex-end; padding: 0.25rem 0.5rem; }
.select-toggle { padding: 0.3rem 0.75rem; border: 1px solid var(--color-border);
  border-radius: 0.35rem; background: transparent; color: inherit; cursor: pointer; }
.select-toggle.active { background: var(--color-accent); color: #fff; }
.asset-image-container.selected { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.select-check { position: absolute; top: 0.4rem; left: 0.4rem; font-size: 1.1rem; z-index: 2; }
```

(Use the app's real design tokens — `--color-border`, `--color-accent` — with no hard-coded fallback, matching every other rule in these files. Do not invent tokens like `--border`/`--accent`.)

(Ensure `.asset-image-container` is `position: relative`; it already is for the cart button overlay — confirm and add if missing.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run tests/AssetGrid.test.js`
Expected: PASS.

- [ ] **Step 6: Run the full frontend + backend suites**

Run: `cd /Users/poga/projects/asset-manager/.claude/worktrees/batch-tag-add-remove/web/frontend && npm test`
Then: `cd /Users/poga/projects/asset-manager/.claude/worktrees/batch-tag-add-remove && just test-api`
Expected: all green (except any pre-existing `router.test.js` failure noted in project memory — confirm it is the same failure present on `main`, not a regression).

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue web/frontend/tests/AssetGrid.test.js
git commit -m "feat: asset batch tagging via select mode"
```

---

### Task 6: Browser verification of the end-to-end flow

**Files:** none (verification only).

- [ ] **Step 1: Verify in the running app**

Use the `verify` skill (drive the real app at the frontend dev server). Confirm:
- Pack gallery: click **Select**, checkboxes appear; select 2 packs; the bar shows "2 selected"; type a tag + Enter → both cards show the new chip; click a union chip × → removed from both; **Done** clears select mode.
- Search results: run a search; **Select**; multi-select assets; add a tag; union chips reflect the union; remove via a chip; changing the search clears the selection.

- [ ] **Step 2: Record the result**

Note pass/fail with a short description of what was exercised. If a genuine vitest component test would add value beyond the browser check, add it; otherwise the browser verification stands as the integration check.

- [ ] **Step 3: Finish the branch**

Use `superpowers:finishing-a-development-branch` to push and open a draft PR.
