# Preview Override Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to mark assets to show the full image instead of the auto-detected first frame preview.

**Architecture:** A separate `asset_preview_overrides` table keyed by file path (survives re-indexing). API endpoints to set/remove overrides. Frontend checkbox in AssetDetail, grid respects the flag.

**Tech Stack:** Python/FastAPI (backend), Vue 3 (frontend), SQLite (database), Vitest (frontend tests), pytest (backend tests)

---

### Task 1: Database Schema - Create Override Table

**Files:**
- Modify: `index.py:58-124` (SCHEMA constant)
- Modify: `web/api.py:90-95` (get_db function)

**Step 1: Write the failing test**

Create `web/test_api.py` test at the end of file:

```python
def test_preview_override_table_exists(test_db):
    """Preview override table should exist in database."""
    import sqlite3
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_preview_overrides'"
    )
    assert cursor.fetchone() is not None
    conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_preview_override_table_exists -v`
Expected: FAIL with "AssertionError: assert None is not None"

**Step 3: Add the table to SCHEMA in index.py**

In `index.py`, add to the SCHEMA constant (around line 116, before the CREATE INDEX statements):

```python
CREATE TABLE IF NOT EXISTS asset_preview_overrides (
    path TEXT PRIMARY KEY,
    use_full_image BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Step 4: Update test_db fixture to include the new table**

In `web/test_api.py`, update the `test_db` fixture schema (around line 68) to add:

```python
        CREATE TABLE asset_preview_overrides (
            path TEXT PRIMARY KEY,
            use_full_image BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_preview_override_table_exists -v`
Expected: PASS

**Step 6: Run all tests to verify no regressions**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add index.py web/test_api.py
git commit -m "feat: add asset_preview_overrides table schema"
```

---

### Task 2: API - POST endpoint to set preview override

**Files:**
- Modify: `web/api.py` (add endpoint and Pydantic model)
- Modify: `web/test_api.py` (add tests)

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_set_preview_override(test_db):
    """POST /api/asset/{id}/preview-override sets the override."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.post("/api/asset/1/preview-override", json={"use_full_image": True})
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify it was saved
    import sqlite3
    conn = sqlite3.connect(test_db)
    row = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = '/assets/creatures/goblin.png'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1  # SQLite stores True as 1


def test_set_preview_override_not_found(test_db):
    """POST /api/asset/{id}/preview-override returns 404 for unknown asset."""
    from api import set_db_path
    set_db_path(test_db)

    response = client.post("/api/asset/999/preview-override", json={"use_full_image": True})
    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_set_preview_override test_api.py::test_set_preview_override_not_found -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Implement the endpoint**

In `web/api.py`, add after the imports (around line 23):

```python
class PreviewOverrideRequest(BaseModel):
    use_full_image: bool
```

Add the endpoint (after the `asset_detail` function, around line 340):

```python
@app.post("/api/asset/{asset_id}/preview-override")
def set_preview_override(asset_id: int, request: PreviewOverrideRequest):
    """Set preview override for an asset."""
    conn = get_db()

    # Get asset path
    row = conn.execute("SELECT path FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_path = row["path"]

    # Insert or replace override
    conn.execute(
        """INSERT OR REPLACE INTO asset_preview_overrides (path, use_full_image, created_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)""",
        [asset_path, request.use_full_image]
    )
    conn.commit()
    conn.close()

    return {"success": True}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_set_preview_override test_api.py::test_set_preview_override_not_found -v`
Expected: PASS

**Step 5: Run all tests to verify no regressions**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: add POST /api/asset/{id}/preview-override endpoint"
```

---

### Task 3: API - DELETE endpoint to remove preview override

**Files:**
- Modify: `web/api.py` (add endpoint)
- Modify: `web/test_api.py` (add test)

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_delete_preview_override(test_db):
    """DELETE /api/asset/{id}/preview-override removes the override."""
    from api import set_db_path
    set_db_path(test_db)

    # First set an override
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    # Then delete it
    response = client.delete("/api/asset/1/preview-override")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify it was removed
    import sqlite3
    conn = sqlite3.connect(test_db)
    row = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = '/assets/creatures/goblin.png'"
    ).fetchone()
    conn.close()
    assert row is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_delete_preview_override -v`
Expected: FAIL with 405 Method Not Allowed

**Step 3: Implement the endpoint**

In `web/api.py`, add after the `set_preview_override` function:

```python
@app.delete("/api/asset/{asset_id}/preview-override")
def delete_preview_override(asset_id: int):
    """Remove preview override for an asset."""
    conn = get_db()

    # Get asset path
    row = conn.execute("SELECT path FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_path = row["path"]

    # Delete override
    conn.execute("DELETE FROM asset_preview_overrides WHERE path = ?", [asset_path])
    conn.commit()
    conn.close()

    return {"success": True}
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_delete_preview_override -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: add DELETE /api/asset/{id}/preview-override endpoint"
```

---

### Task 4: API - Include use_full_image in asset detail response

**Files:**
- Modify: `web/api.py:297-339` (asset_detail function)
- Modify: `web/test_api.py` (add test)

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_asset_detail_includes_use_full_image(test_db):
    """GET /api/asset/{id} includes use_full_image field."""
    from api import set_db_path
    set_db_path(test_db)

    # Without override, should be null/None
    response = client.get("/api/asset/1")
    assert response.status_code == 200
    data = response.json()
    assert "use_full_image" in data
    assert data["use_full_image"] is None

    # Set override
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    # Now should be True
    response = client.get("/api/asset/1")
    data = response.json()
    assert data["use_full_image"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_asset_detail_includes_use_full_image -v`
Expected: FAIL with KeyError or assertion error

**Step 3: Modify asset_detail to include use_full_image**

In `web/api.py`, modify the `asset_detail` function (around line 297-339):

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

    # Get preview override
    override = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = ?",
        [row["path"]]
    ).fetchone()

    conn.close()

    return {
        "id": row["id"],
        "path": row["path"],
        "filename": row["filename"],
        "filetype": row["filetype"],
        "pack": row["pack_name"],
        "width": row["width"],
        "height": row["height"],
        "preview_x": row["preview_x"],
        "preview_y": row["preview_y"],
        "preview_width": row["preview_width"],
        "preview_height": row["preview_height"],
        "tags": [t["name"] for t in tags],
        "colors": [{"hex": c["color_hex"], "percentage": c["percentage"]} for c in colors],
        "use_full_image": bool(override["use_full_image"]) if override else None,
    }
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_asset_detail_includes_use_full_image -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: include use_full_image in asset detail response"
```

---

### Task 5: API - Include use_full_image in search results

**Files:**
- Modify: `web/api.py:129-234` (search function)
- Modify: `web/test_api.py` (add test)

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_search_includes_use_full_image(test_db):
    """GET /api/search includes use_full_image field per asset."""
    from api import set_db_path
    set_db_path(test_db)

    # Set override for one asset
    client.post("/api/asset/1/preview-override", json={"use_full_image": True})

    response = client.get("/api/search")
    assert response.status_code == 200
    data = response.json()

    # Find goblin (id=1) and orc (id=2)
    assets_by_id = {a["id"]: a for a in data["assets"]}

    # Asset 1 should have use_full_image=True
    assert assets_by_id[1]["use_full_image"] is True
    # Asset 2 should have use_full_image=None
    assert assets_by_id[2]["use_full_image"] is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_search_includes_use_full_image -v`
Expected: FAIL with KeyError

**Step 3: Modify search to include use_full_image**

In `web/api.py`, modify the search function SQL query and response (around line 199-234):

Replace the SQL query:
```python
    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.preview_x, a.preview_y, a.preview_width, a.preview_height,
               p.name as pack_name,
               GROUP_CONCAT(DISTINCT tg.name) as tags,
               po.use_full_image
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        LEFT JOIN asset_preview_overrides po ON a.path = po.path
        WHERE {where}
        GROUP BY a.id
        ORDER BY {order_by}
        LIMIT ?
    """
```

Update the response building (around line 218-232):
```python
    assets = []
    for row in rows:
        use_full_image = None
        if row["use_full_image"] is not None:
            use_full_image = bool(row["use_full_image"])
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
            "preview_x": row["preview_x"],
            "preview_y": row["preview_y"],
            "preview_width": row["preview_width"],
            "preview_height": row["preview_height"],
            "use_full_image": use_full_image,
        })
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_search_includes_use_full_image -v`
Expected: PASS

**Step 5: Run all backend tests**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: include use_full_image in search results"
```

---

### Task 6: Frontend - Add checkbox to AssetDetail component

**Files:**
- Modify: `web/frontend/src/components/AssetDetail.vue`
- Modify: `web/frontend/tests/AssetDetail.test.js`

**Step 1: Write the failing test**

Add to `web/frontend/tests/AssetDetail.test.js`:

```javascript
describe('Preview Override', () => {
  const mockAssetWithPreview = {
    id: 1,
    filename: 'sprite.png',
    path: 'sprites/sprite.png',
    pack: 'sprites',
    width: 128,
    height: 64,
    preview_x: 0,
    preview_y: 0,
    preview_width: 32,
    preview_height: 32,
    tags: [],
    colors: [],
    use_full_image: false,
  }

  it('shows checkbox when asset has preview bounds', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAssetWithPreview }
    })
    expect(wrapper.find('.preview-override-checkbox').exists()).toBe(true)
  })

  it('hides checkbox when asset has no preview bounds', () => {
    const assetNoPreview = { ...mockAssetWithPreview, preview_x: null }
    const wrapper = mount(AssetDetail, {
      props: { asset: assetNoPreview }
    })
    expect(wrapper.find('.preview-override-checkbox').exists()).toBe(false)
  })

  it('emits toggle-preview-override when checkbox clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAssetWithPreview }
    })
    await wrapper.find('.preview-override-checkbox input').trigger('change')
    expect(wrapper.emitted('toggle-preview-override')).toBeTruthy()
    expect(wrapper.emitted('toggle-preview-override')[0][0]).toEqual({
      assetId: 1,
      useFullImage: true
    })
  })

  it('checkbox reflects use_full_image state', () => {
    const assetWithOverride = { ...mockAssetWithPreview, use_full_image: true }
    const wrapper = mount(AssetDetail, {
      props: { asset: assetWithOverride }
    })
    const checkbox = wrapper.find('.preview-override-checkbox input')
    expect(checkbox.element.checked).toBe(true)
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run AssetDetail`
Expected: FAIL - checkbox doesn't exist

**Step 3: Add checkbox to AssetDetail.vue template**

In `web/frontend/src/components/AssetDetail.vue`, add after the image tag (around line 15):

```vue
        <label
          v-if="asset.preview_x !== null && asset.preview_x !== undefined"
          class="preview-override-checkbox"
        >
          <input
            type="checkbox"
            :checked="asset.use_full_image"
            @change="$emit('toggle-preview-override', { assetId: asset.id, useFullImage: !asset.use_full_image })"
          />
          Show full image
        </label>
```

Update the emits (around line 74):
```javascript
defineEmits(['back', 'add-to-cart', 'find-similar', 'view-pack', 'tag-click', 'toggle-preview-override'])
```

Add the CSS (in the style section):
```css
.preview-override-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
}

.preview-override-checkbox input {
  cursor: pointer;
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run AssetDetail`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue web/frontend/tests/AssetDetail.test.js
git commit -m "feat: add preview override checkbox to AssetDetail"
```

---

### Task 7: Frontend - Handle toggle event in App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/tests/App.test.js`

**Step 1: Write the failing test**

Add to `web/frontend/tests/App.test.js`:

```javascript
describe('Preview Override', () => {
  it('calls API when toggle-preview-override is emitted', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    })

    const wrapper = mount(App)
    // Simulate the event from AssetDetail
    await wrapper.vm.handleTogglePreviewOverride({ assetId: 1, useFullImage: true })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/asset/1/preview-override'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ use_full_image: true })
      })
    )
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run App`
Expected: FAIL - method doesn't exist

**Step 3: Add handler to App.vue**

In `web/frontend/src/App.vue`, add the handler function (in the script section):

```javascript
async function handleTogglePreviewOverride({ assetId, useFullImage }) {
  const url = `${API_BASE}/asset/${assetId}/preview-override`

  if (useFullImage) {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_full_image: true })
    })
  } else {
    await fetch(url, { method: 'DELETE' })
  }

  // Refresh the selected asset detail
  if (selectedAssetId.value === assetId) {
    await loadAssetDetail(assetId)
  }

  // Refresh search results to update grid
  await doSearch()
}
```

Wire up the event in the template where AssetDetail is used:
```vue
<AssetDetail
  ...
  @toggle-preview-override="handleTogglePreviewOverride"
/>
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run App`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: handle preview override toggle in App"
```

---

### Task 8: Frontend - Respect use_full_image in AssetGrid

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Modify: `web/frontend/tests/AssetGrid.test.js`

**Step 1: Write the failing test**

Add to `web/frontend/tests/AssetGrid.test.js`:

```javascript
describe('Preview Override', () => {
  it('shows full image when use_full_image is true even with preview bounds', () => {
    const assets = [{
      id: 1,
      filename: 'sprite.png',
      pack: 'sprites',
      width: 128,
      height: 64,
      preview_x: 0,
      preview_y: 0,
      preview_width: 32,
      preview_height: 32,
      use_full_image: true,
    }]

    const wrapper = mount(AssetGrid, {
      props: { assets, cartIds: [] }
    })

    // Should use img tag, not SpritePreview
    expect(wrapper.findComponent({ name: 'SpritePreview' }).exists()).toBe(false)
    expect(wrapper.find('.asset-image-container img').exists()).toBe(true)
  })

  it('uses SpritePreview when use_full_image is false with preview bounds', () => {
    const assets = [{
      id: 1,
      filename: 'sprite.png',
      pack: 'sprites',
      width: 128,
      height: 64,
      preview_x: 0,
      preview_y: 0,
      preview_width: 32,
      preview_height: 32,
      use_full_image: false,
    }]

    const wrapper = mount(AssetGrid, {
      props: { assets, cartIds: [] }
    })

    expect(wrapper.findComponent({ name: 'SpritePreview' }).exists()).toBe(true)
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run AssetGrid`
Expected: FAIL

**Step 3: Modify AssetGrid.vue to respect use_full_image**

In `web/frontend/src/components/AssetGrid.vue`, update the template condition (around line 20-34):

Change:
```vue
          <SpritePreview
            v-if="asset.preview_x !== null"
```

To:
```vue
          <SpritePreview
            v-if="asset.preview_x !== null && !asset.use_full_image"
```

Also update the aspect ratio calculation (around line 17):
```vue
          :style="{ aspectRatio: (asset.preview_x != null && !asset.use_full_image) ? `${asset.preview_width} / ${asset.preview_height}` : `${asset.width} / ${asset.height}` }"
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run AssetGrid`
Expected: PASS

**Step 5: Run all frontend tests**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run`
Expected: All tests pass

**Step 6: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue web/frontend/tests/AssetGrid.test.js
git commit -m "feat: respect use_full_image in AssetGrid rendering"
```

---

### Task 9: Integration Test - End-to-end workflow

**Files:**
- Modify: `web/test_api.py` (add integration test)

**Step 1: Write integration test**

Add to `web/test_api.py`:

```python
def test_preview_override_full_workflow(test_db):
    """Test complete preview override workflow."""
    from api import set_db_path
    set_db_path(test_db)

    # 1. Initially, asset has no override
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is None

    # 2. Set override to True
    response = client.post("/api/asset/1/preview-override", json={"use_full_image": True})
    assert response.status_code == 200

    # 3. Verify in detail
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is True

    # 4. Verify in search
    response = client.get("/api/search?q=goblin")
    assert response.json()["assets"][0]["use_full_image"] is True

    # 5. Delete override
    response = client.delete("/api/asset/1/preview-override")
    assert response.status_code == 200

    # 6. Verify removed
    response = client.get("/api/asset/1")
    assert response.json()["use_full_image"] is None
```

**Step 2: Run test**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py::test_preview_override_full_workflow -v`
Expected: PASS

**Step 3: Run all tests**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add web/test_api.py
git commit -m "test: add preview override integration test"
```

---

### Task 10: Final Verification

**Step 1: Run all backend tests**

Run: `cd /Users/poga/projects/asset-manager/web && uv run pytest test_api.py -v`
Expected: All tests pass

**Step 2: Run all frontend tests**

Run: `cd /Users/poga/projects/asset-manager/web/frontend && npm test -- --run`
Expected: All tests pass

**Step 3: Manual test (if servers running)**

1. Open http://localhost:5173
2. Search for an asset with preview bounds
3. Click on it to see detail
4. Check the "Show full image" checkbox
5. Go back to grid - should show full image
6. Click again - uncheck - should show sprite preview again

**Step 4: Final commit with feature flag**

```bash
git add -A
git commit -m "feat: complete preview override feature

Allows users to mark assets to show full image instead of
auto-detected first frame preview. Overrides persist through
re-indexing (keyed by file path).

- New table: asset_preview_overrides
- POST/DELETE /api/asset/{id}/preview-override endpoints
- use_full_image field in asset detail and search responses
- Checkbox in AssetDetail (only shown for assets with preview bounds)
- AssetGrid respects the override flag"
```
