# Tag-Centric Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the color filter and Add-tag dropdown with a single smart search box backed by a unified tag vocabulary in which pack tags flow down to their assets.

**Architecture:** `/api/filters` ships the full merged tag vocabulary (`{name, count}` entries, ~5.7k tags ≈ 120KB) once; `SearchBar.vue` filters it in memory for suggestions. `/api/search` tag clauses match an asset's own tags OR its pack's tags. The color filter is removed from UI and API (extraction and detail-page swatches stay).

**Tech Stack:** FastAPI + SQLite (uv single-file scripts, pytest), Vue 3 + Vitest.

**Spec:** `docs/superpowers/specs/2026-07-06-tag-centric-search-design.md`

## Global Constraints

- Run all Python via `uv run` (`uv run --script <file>`); full Python suite `just test`; frontend `cd web/frontend && npm test`.
- NO MOCKS in Python tests (real files/SQLite). Frontend follows existing Vitest fetch-stub conventions.
- Comments: max 1 line, 80 chars, why/what. TDD every behavior change: failing test first.
- Do NOT start/stop the user's servers (8000, 5173, 38471, 38472). Verification uses port 8010.
- Never push to main; work stays on branch `worktree-preview-and-pack-gallery`.
- `/api/filters` after this plan: `{"packs": [...unchanged, incl. per-pack tags...], "tags": [{"name": str, "count": int}, ...]}` — full vocabulary, count-desc then name-asc, NO `colors` key.
- `/api/search` tag semantics: asset matches a tag if it carries it OR its pack carries it; multiple `tag` params AND; `color` param and `COLOR_NAMES` deleted.
- Both endpoints must not 500 on a legacy DB missing `pack_tags` (use the existing `_ensure_pack_tags(conn)`).
- SearchBar emits exactly `{q, tag}`. Plain Enter with no highlighted suggestion must NOT add a tag.
- Color extraction at index time and detail-page color display are OUT of scope — do not touch `extract_colors`, `asset_colors`, or `/api/asset/{id}`.
- App.vue is a CRLF file — precise Edits only; its diff must be only the intended lines.

---

### Task 1: /api/filters — full unified vocabulary, colors key removed

**Files:**
- Modify: `web/api.py` (`filters()`)
- Test: `web/test_api.py`

**Interfaces:**
- Consumes: existing `_ensure_pack_tags(conn)` helper in web/api.py.
- Produces: `filters()` response `tags: [{"name": str, "count": int}, ...]` (full vocabulary, sorted count desc / name asc, pack tags merged with count = SUM of carrying packs' `asset_count`, name collisions keep the larger count); NO `colors` key. Task 3's SearchBar consumes this shape.

- [ ] **Step 1: Write the failing tests**

In `web/test_api.py`, update the existing `test_filters_returns_available_options`-style test (whatever test currently asserts `tags`/`colors` on `/api/filters` — locate by grepping `filters` tests) so tag assertions use the new object shape and `colors` is asserted absent. Then add:

```python
def test_filters_tags_full_vocabulary_merges_pack_tags(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pack_tags ("
        "pack_id INTEGER REFERENCES packs(id), tag TEXT NOT NULL, "
        "PRIMARY KEY (pack_id, tag))"
    )
    # pack 1 ('creatures') has 2 assets in the fixture
    conn.execute("UPDATE packs SET asset_count = 2 WHERE id = 1")
    conn.execute("INSERT INTO pack_tags (pack_id, tag) VALUES (1, 'forest')")
    # collides with the 1-asset 'goblin' asset tag; pack reach (2) must win
    conn.execute("INSERT INTO pack_tags (pack_id, tag) VALUES (1, 'goblin')")
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    data = resp.json()
    assert "colors" not in data
    vocab = {t["name"]: t["count"] for t in data["tags"]}
    assert vocab["forest"] == 2   # pure pack tag: reach = pack asset_count
    assert vocab["goblin"] == 2   # collision keeps the larger count
    assert vocab["creature"] == 2 # pure asset tag: asset count
    counts = [t["count"] for t in data["tags"]]
    assert counts == sorted(counts, reverse=True)
    # name-asc tiebreak within equal counts
    for a, b in zip(data["tags"], data["tags"][1:]):
        if a["count"] == b["count"]:
            assert a["name"] <= b["name"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -k "filters"`
Expected: FAIL — tags are plain strings, top-100 only, and `colors` present.

- [ ] **Step 3: Implement**

In `filters()` replace the `tags` query (currently `SELECT t.name ... LIMIT 100`) with:

```python
    _ensure_pack_tags(conn)
    # one vocabulary: asset tags plus pack tags (pack tags reach all assets)
    tag_counts: dict[str, int] = {}
    for r in conn.execute("""
        SELECT t.name AS name, COUNT(at.asset_id) AS count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
    """):
        tag_counts[r["name"]] = r["count"]
    for r in conn.execute("""
        SELECT pt.tag AS name, SUM(p.asset_count) AS count
        FROM pack_tags pt
        JOIN packs p ON pt.pack_id = p.id
        GROUP BY pt.tag
    """):
        tag_counts[r["name"]] = max(tag_counts.get(r["name"], 0), r["count"] or 0)
    vocabulary = [
        {"name": name, "count": count}
        for name, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
```

and in the return dict: `"tags": vocabulary,` and DELETE the `"colors": list(COLOR_NAMES.keys()),` line (leave `COLOR_NAMES` itself — Task 2 deletes it with the search clause).

Note: `_ensure_pack_tags` + `conn.commit()` — check whether the existing filters implementation already commits after ensure; keep exactly one commit for the DDL.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: PASS (all).

- [ ] **Step 5: Full suite and commit**

Run: `just test`

```bash
git add web/api.py web/test_api.py
git commit -m "feat: filters serves full unified tag vocabulary, drops colors"
```

---

### Task 2: /api/search — pack-tag inheritance, color removed

**Files:**
- Modify: `web/api.py` (`search()`, delete `COLOR_NAMES`)
- Test: `web/test_api.py`

**Interfaces:**
- Consumes: `_ensure_pack_tags(conn)`.
- Produces: `/api/search?tag=x` matches assets whose own tags OR pack tags include x (multiple tags AND); no `color` param.

- [ ] **Step 1: Write the failing tests**

Delete `test_search_by_color` from `web/test_api.py`. Add:

```python
def _create_pack_tags_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pack_tags ("
        "pack_id INTEGER REFERENCES packs(id), tag TEXT NOT NULL, "
        "PRIMARY KEY (pack_id, tag))"
    )
    conn.commit()
    conn.close()


def test_search_matches_assets_via_pack_tag(test_db):
    _create_pack_tags_table(test_db)
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO pack_tags (pack_id, tag) VALUES (1, 'minifantasy')")
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/search?tag=minifantasy")
    assert resp.status_code == 200
    # both fixture assets belong to pack 1 and inherit its tag
    assert len(resp.json()["assets"]) == 2


def test_search_pack_tag_ands_with_asset_tag(test_db):
    _create_pack_tags_table(test_db)
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO pack_tags (pack_id, tag) VALUES (1, 'minifantasy')")
    conn.commit()
    conn.close()

    import api
    api.set_db_path(test_db)
    resp = client.get("/api/search?tag=minifantasy&tag=goblin")
    data = resp.json()
    assert len(data["assets"]) == 1
    assert data["assets"][0]["filename"] == "goblin.png"


def test_search_tag_tolerates_missing_pack_tags_table(tmp_path):
    # legacy DB without pack_tags: tag search must not 500
    db_path = tmp_path / "legacy3.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE packs (id INTEGER PRIMARY KEY, name TEXT, path TEXT, asset_count INTEGER DEFAULT 0);
        CREATE TABLE assets (id INTEGER PRIMARY KEY, pack_id INTEGER, path TEXT UNIQUE, filename TEXT,
            filetype TEXT, file_hash TEXT, file_size INTEGER, width INTEGER, height INTEGER,
            preview_x INTEGER, preview_y INTEGER, preview_width INTEGER, preview_height INTEGER,
            category TEXT, asset_kind TEXT, rig TEXT, thumbnail_path TEXT);
        CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE asset_tags (asset_id INTEGER, tag_id INTEGER, source TEXT, PRIMARY KEY (asset_id, tag_id));
        CREATE TABLE asset_preview_overrides (path TEXT PRIMARY KEY, use_full_image BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO packs (id, name, path) VALUES (1, 'p', 'p');
        INSERT INTO assets (id, pack_id, path, filename, filetype, file_hash)
            VALUES (1, 1, 'p/a.png', 'a.png', 'png', 'h');
        INSERT INTO tags (id, name) VALUES (1, 'creature');
        INSERT INTO asset_tags VALUES (1, 1, 'path');
    """)
    conn.commit()
    conn.close()

    import api
    api.set_db_path(db_path)
    resp = client.get("/api/search?tag=creature")
    assert resp.status_code == 200
    assert len(resp.json()["assets"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --script web/test_api.py -k "pack_tag or tolerates_missing"`
Expected: pack-tag inheritance tests FAIL (0 matches); legacy test may pass or fail depending on ensure placement — the two inheritance tests are the required RED.

- [ ] **Step 3: Implement**

In `search()`:
1. Remove `color: Optional[str] = None,` from the signature.
2. Right after `conn = get_db()`, add `_ensure_pack_tags(conn)` followed by `conn.commit()` (DDL on the read path must persist; matches the filters pattern).
3. Replace the tag loop with:

```python
    for t in tag:
        conditions.append("""
            (a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
            ) OR a.pack_id IN (
                SELECT pack_id FROM pack_tags WHERE tag = ?
            ))
        """)
        params.extend([t.lower(), t.lower()])
```

4. Delete the whole `if color:` conditions block.
5. Update `is_empty_search = not q and not tag and not color and not pack and not type` → remove `and not color`.
6. Delete the `COLOR_NAMES = {...}` dict (its last consumer is gone; the detail endpoint's color output reads `asset_colors` directly and is untouched).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --script web/test_api.py`
Expected: PASS; `grep -n "COLOR_NAMES\|color" web/api.py` shows only the `asset_colors` usages in the detail endpoint and `download_cart`.

- [ ] **Step 5: Full suite and commit**

Run: `just test`

```bash
git add web/api.py web/test_api.py
git commit -m "feat: search matches pack tags and drops the color filter"
```

---

### Task 3: SearchBar smart box + App plumbing

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue` (full replacement below)
- Modify: `web/frontend/src/App.vue` (two small edits)
- Test: `web/frontend/tests/SearchBar.test.js` (rework), `web/frontend/tests/App.test.js` (only if suite reveals fallout)

**Interfaces:**
- Consumes: `filters.tags` as `[{name, count}, ...]` (Task 1); existing `filters` prop flow from App.
- Produces: SearchBar emits `search` with exactly `{q, tag}`; exposes `addTagExternal(tag)` and `clear()` (unchanged names — App.vue calls both).

- [ ] **Step 1: Rework the tests (failing first)**

Replace `web/frontend/tests/SearchBar.test.js` with:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

const filters = {
  packs: [],
  tags: [
    { name: 'goblin', count: 120 },
    { name: 'gold', count: 40 },
    { name: 'dragon-gold', count: 90 },
    { name: 'idle', count: 300 },
  ],
}

function lastSearch(wrapper) {
  const emitted = wrapper.emitted('search')
  return emitted[emitted.length - 1][0]
}

describe('SearchBar smart box', () => {
  it('emits only q and tag', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('sword')
    const params = lastSearch(wrapper)
    expect(Object.keys(params).sort()).toEqual(['q', 'tag'])
    expect(params.q).toBe('sword')
  })

  it('renders no color or add-tag dropdowns', () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    expect(wrapper.find('[data-filter="color"]').exists()).toBe(false)
    expect(wrapper.find('[data-filter="tag"]').exists()).toBe(false)
  })

  it('suggests prefix matches before substring matches, count-ranked', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('go')
    const names = wrapper.findAll('.suggestion').map(s => s.find('.suggestion-name').text())
    // prefix: goblin(120), gold(40); substring: dragon-gold(90)
    expect(names).toEqual(['goblin', 'gold', 'dragon-gold'])
    expect(wrapper.findAll('.suggestion-count')[0].text()).toBe('120')
  })

  it('click on a suggestion adds a chip and clears the input', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    expect(lastSearch(wrapper)).toEqual({ q: null, tag: ['goblin'] })
    expect(wrapper.find('input').element.value).toBe('')
    expect(wrapper.find('.tag').text()).toContain('goblin')
  })

  it('arrow down + enter adds the highlighted suggestion', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastSearch(wrapper).tag).toEqual(['gold'])
  })

  it('plain enter with no highlight adds no tag', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastSearch(wrapper).tag).toEqual([])
    expect(lastSearch(wrapper).q).toBe('go')
  })

  it('escape closes the suggestion dropdown', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    expect(wrapper.find('.suggestion').exists()).toBe(true)
    await input.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.suggestion').exists()).toBe(false)
  })

  it('already-chosen tags are not suggested again', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    await input.setValue('gob')
    const names = wrapper.findAll('.suggestion').map(s => s.find('.suggestion-name').text())
    expect(names).not.toContain('goblin')
  })

  it('chips remove on click and re-emit', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    await wrapper.find('.tag').trigger('click')
    expect(lastSearch(wrapper).tag).toEqual([])
  })

  it('clear() resets query and tags', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    wrapper.vm.clear()
    await wrapper.vm.$nextTick()
    expect(lastSearch(wrapper)).toEqual({ q: null, tag: [] })
  })

  it('degrades to plain search when vocabulary is empty', async () => {
    const wrapper = mount(SearchBar, { props: { filters: { packs: [], tags: [] } } })
    await wrapper.find('input').setValue('goblin')
    expect(wrapper.find('.suggestion').exists()).toBe(false)
    expect(lastSearch(wrapper).q).toBe('goblin')
  })
})
```

Run: `cd web/frontend && npm test` → SearchBar tests FAIL against the old component.

- [ ] **Step 2: Replace SearchBar.vue**

Replace the whole file with:

```vue
<template>
  <div class="search-bar">
    <div class="search-input-wrapper" data-filter="suggest">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <path d="M21 21l-4.35-4.35"/>
      </svg>
      <input
        type="text"
        v-model="query"
        placeholder="Search assets or type a tag..."
        @input="onInput"
        @keydown="onKeydown"
      />
      <div v-if="suggestionsOpen && suggestions.length" class="suggestion-panel">
        <button
          v-for="(s, i) in suggestions"
          :key="s.name"
          type="button"
          class="suggestion"
          :class="{ highlighted: i === highlight }"
          @mousedown.prevent="addTag(s.name)"
        >
          <span class="suggestion-name">{{ s.name }}</span>
          <span class="suggestion-count">{{ s.count }}</span>
        </button>
      </div>
    </div>
    <div v-if="tags.length" class="tags-row">
      <span v-for="t in tags" :key="t" class="tag" :title="t" @click="removeTag(t)">
        <span class="tag-text">{{ t }}</span>
        <svg class="tag-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['search'])

const query = ref('')
const tags = ref([])
const suggestionsOpen = ref(false)
const highlight = ref(-1)

const suggestions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return []
  const chosen = new Set(tags.value)
  const prefix = []
  const substring = []
  for (const t of props.filters.tags || []) {
    if (chosen.has(t.name)) continue
    if (t.name.startsWith(q)) prefix.push(t)
    else if (t.name.includes(q)) substring.push(t)
  }
  const byCount = (a, b) => b.count - a.count
  return [...prefix.sort(byCount), ...substring.sort(byCount)].slice(0, 12)
})

function handleClickOutside(event) {
  if (!event.target.closest('[data-filter="suggest"]')) {
    suggestionsOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

function emitSearch() {
  emit('search', {
    q: query.value || null,
    tag: tags.value
  })
}

function onInput() {
  suggestionsOpen.value = true
  highlight.value = -1
  emitSearch()
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (suggestions.value.length) {
      highlight.value = Math.min(highlight.value + 1, suggestions.value.length - 1)
    }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlight.value = Math.max(highlight.value - 1, -1)
  } else if (event.key === 'Enter') {
    // only a deliberate highlight adds a tag; plain Enter stays a text search
    if (highlight.value >= 0 && suggestions.value[highlight.value]) {
      addTag(suggestions.value[highlight.value].name)
    }
  } else if (event.key === 'Escape') {
    suggestionsOpen.value = false
    highlight.value = -1
  }
}

function addTag(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
  }
  query.value = ''
  suggestionsOpen.value = false
  highlight.value = -1
  emitSearch()
}

function removeTag(tag) {
  tags.value = tags.value.filter(t => t !== tag)
  emitSearch()
}

function addTagExternal(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    emitSearch()
  }
}

function clear() {
  query.value = ''
  tags.value = []
  suggestionsOpen.value = false
  highlight.value = -1
  emitSearch()
}

defineExpose({ addTagExternal, clear })
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 1rem;
}

.search-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 200px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input-wrapper input {
  width: 100%;
  height: 36px;
  padding: 0 0.75rem 0 36px;
  font-size: 0.875rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}

.search-input-wrapper input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.search-input-wrapper input::placeholder {
  color: var(--color-text-muted);
}

.suggestion-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: var(--shadow-elevated);
  z-index: 100;
  max-height: 320px;
  overflow-y: auto;
}

.suggestion {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--color-text-primary);
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}

.suggestion:hover,
.suggestion.highlighted {
  background: var(--color-bg-elevated);
}

.suggestion-count {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.tags-row {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border-radius: 12px;
  font-size: 0.8125rem;
  cursor: pointer;
  max-width: 120px;
}

.tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-close {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.tag:hover {
  background: var(--color-border);
}
</style>
```

Notes: `@mousedown.prevent` on suggestions (not `@click`) so the input doesn't blur first; the old color/tag dropdown markup, `handleKeydown` document listener, `selectColor`/`selectTag`, and the dead `.filter-chip`/`.dropdown*` CSS are all gone.

- [ ] **Step 3: App.vue edits (precise Edits, CRLF)**

1. In `search(params)`: delete the line `if (params.color) query.set('color', params.color)`.
2. `hasActiveSearch` becomes:

```javascript
function hasActiveSearch(params) {
  return !!(params.q || (params.tag && params.tag.length))
}
```

3. `grep -n "color" web/frontend/src/App.vue` — remaining hits must be unrelated (CSS vars); any `params.color` reference is a missed edit.

- [ ] **Step 4: Run the whole frontend suite**

Run: `cd web/frontend && npm test`
Expected: all green. If App.test.js references `color` in search params or filters mocks, update those mocks to the new shapes (`{ packs: [], tags: [] }`) — navigation tests must pass without source changes beyond Step 3.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue web/frontend/src/App.vue web/frontend/tests/SearchBar.test.js web/frontend/tests/App.test.js
git commit -m "feat: tag-centric smart search box replaces color and tag dropdowns"
```

---

### Task 4: Verification + PR

**Files:** none (verification only).

- [ ] **Step 1: Full suites + build**

```bash
just test
cd web/frontend && npm test && npm run build && cd ../..
```

- [ ] **Step 2: Live verification (disposable copy)**

```bash
MAIN=/Users/poga/projects/asset-manager
cp "$MAIN/assets.db" ./assets.db
cp -R "$MAIN/.index" ./.index
uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --port 8010
```

Browse `http://localhost:8010/assets/` (hard reload):
- Search bar has one input, no color / Add-tag dropdowns.
- Type `gob` → suggestion dropdown with counts; click one → chip + results narrow.
- Arrow-down + Enter adds; plain Enter only text-searches; Escape closes.
- In the gallery, add a pack tag (e.g. `smoketest`) to some pack, then type it in the smart box → suggestion appears (after a reload — vocabulary is fetched at mount) and selecting it returns that pack's assets. Remove the tag afterwards.
- Take a screenshot for the user. Kill uvicorn; delete the copied `assets.db`/`.index`.

- [ ] **Step 3: Push and PR**

```bash
git push
gh pr create --draft --title "Tag-centric search" --body "$(cat <<'EOF'
## Summary
- One smart search box: typing live-searches filenames while suggesting tags from a unified vocabulary (all asset tags + your pack tags, count-ranked, prefix-first). Click or arrow+Enter turns a suggestion into an AND-composed filter chip.
- Pack tags now flow into asset search: tag a pack "forest" and every asset in it matches tag "forest".
- Color filter removed (UI dropdown + /api/search param + COLOR_NAMES). Color extraction and detail-page swatches remain.
- "Add tag..." dropdown removed; /api/filters now ships the full tag vocabulary as {name, count} and no colors key.

## Rollout
Merge + API restart. No reindex — pack tags apply to search immediately.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01WdYKpvGrkVbX9wExiTMAYN
EOF
)"
```

---

## Self-Review Notes

- Spec coverage: vocabulary + colors-key removal (Task 1), inheritance + color param removal + legacy tolerance (Task 2), smart box + params shape + App predicate (Task 3), live verify + rollout (Task 4). Error handling embedded: empty-input → no dropdown (`if (!q) return []`), empty vocabulary degrades (test in Task 3), legacy DB tests (Tasks 1 fixture creates pack_tags itself; Task 2 has the dedicated missing-table test; filters' own missing-table path is already covered by the existing `test_filters_tags_default_empty_without_table`).
- `COLOR_NAMES` deletion deferred to Task 2 so Task 1 commits green on its own.
- SearchBar keeps `addTagExternal`/`clear` exposed names — App.vue's tag-click and goHome flows depend on them.
- The suggestion mousedown-vs-click choice is deliberate (blur ordering); the test triggers `mousedown` accordingly.
