# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pack view navigation and convert asset grid to Pinterest-style masonry layout with larger thumbnails.

**Architecture:** Extend existing router with `/pack/:name` route. Convert AssetGrid from CSS Grid to CSS Columns for masonry effect. Add pack name to asset cards with click-to-navigate. Add "View Pack" button to AssetModal.

**Tech Stack:** Vue 3, CSS Columns, Vitest

---

## Task 1: Add Pack Route to Router

**Files:**
- Modify: `web/frontend/src/router.js`
- Test: `web/frontend/tests/router.test.js`

**Step 1: Write failing tests for pack route parsing**

Add to `tests/router.test.js` inside the `parseRoute` describe block:

```javascript
it('parses /pack/:name as pack route', () => {
  const route = parseRoute('/pack/fantasy-characters')
  expect(route).toEqual({ name: 'pack', params: { name: 'fantasy-characters' } })
})

it('parses /pack/:name with spaces encoded', () => {
  const route = parseRoute('/pack/RPG%20Heroes')
  expect(route).toEqual({ name: 'pack', params: { name: 'RPG%20Heroes' } })
})
```

Add to `buildUrl` describe block:

```javascript
it('builds pack URL with name', () => {
  const url = buildUrl({ name: 'pack', params: { name: 'fantasy-characters' } })
  expect(url).toBe('/pack/fantasy-characters')
})
```

**Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test -- --run`
Expected: 3 failing tests

**Step 3: Implement pack route in router.js**

Replace `router.js` content:

```javascript
export function parseRoute(path) {
  const assetMatch = path.match(/^\/asset\/([^/]+)$/)
  if (assetMatch) {
    return { name: 'asset', params: { id: assetMatch[1] } }
  }
  const similarMatch = path.match(/^\/similar\/([^/]+)$/)
  if (similarMatch) {
    return { name: 'similar', params: { id: similarMatch[1] } }
  }
  const packMatch = path.match(/^\/pack\/([^/]+)$/)
  if (packMatch) {
    return { name: 'pack', params: { name: packMatch[1] } }
  }
  return { name: 'home', params: {} }
}

export function buildUrl(route) {
  if (route.name === 'asset' && route.params?.id) {
    return `/asset/${route.params.id}`
  }
  if (route.name === 'similar' && route.params?.id) {
    return `/similar/${route.params.id}`
  }
  if (route.name === 'pack' && route.params?.name) {
    return `/pack/${route.params.name}`
  }
  return '/'
}
```

**Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/frontend/src/router.js web/frontend/tests/router.test.js
git commit -m "feat: add pack route to router"
```

---

## Task 2: Add View Pack Button to AssetModal

**Files:**
- Modify: `web/frontend/src/components/AssetModal.vue`
- Test: `web/frontend/tests/AssetModal.test.js`

**Step 1: Write failing test for view-pack event**

Add to `tests/AssetModal.test.js`:

```javascript
it('emits view-pack event with pack name when View Pack clicked', async () => {
  const wrapper = mount(AssetModal, {
    props: { asset: mockAsset }
  })
  await wrapper.find('.view-pack-btn').trigger('click')
  expect(wrapper.emitted('view-pack')).toBeTruthy()
  expect(wrapper.emitted('view-pack')[0]).toEqual(['test-pack'])
})
```

Note: Ensure `mockAsset` in the test file includes `pack: 'test-pack'`. Check the existing mock and update if needed.

**Step 2: Run tests to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: 1 failing test (cannot find .view-pack-btn)

**Step 3: Add View Pack button to AssetModal.vue**

In `<template>`, add after the Find Similar button:

```vue
<button @click="$emit('view-pack', asset.pack)" class="view-pack-btn" v-if="asset.pack">
  View Pack
</button>
```

Update `defineEmits`:

```javascript
defineEmits(['close', 'find-similar', 'view-pack'])
```

Add CSS for the button (in `<style scoped>`):

```css
.view-pack-btn {
  background: #28a745;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  margin-left: 0.5rem;
}

.view-pack-btn:hover {
  background: #218838;
}
```

**Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/frontend/src/components/AssetModal.vue web/frontend/tests/AssetModal.test.js
git commit -m "feat: add View Pack button to AssetModal"
```

---

## Task 3: Handle Pack Route in App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/App.test.js`

**Step 1: Write failing test for pack route handling**

Add to `tests/App.test.js`:

```javascript
it('loads pack assets when navigating to /pack/:name', async () => {
  // Mock the route
  delete window.location
  window.location = { pathname: '/pack/fantasy-pack' }

  const wrapper = mount(App, { global: { stubs: ['SearchBar', 'AssetGrid', 'AssetModal'] } })
  await flushPromises()

  // Verify the search API was called with pack filter
  expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('pack=fantasy-pack'))
})
```

Note: Check existing test setup for fetch mocking patterns and adapt accordingly.

**Step 2: Run tests to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: Test fails

**Step 3: Implement pack route handling in App.vue**

Add state for current pack view after `selectedAsset`:

```javascript
const currentPack = ref(null)
```

Add function to load pack:

```javascript
async function loadPack(packName) {
  currentPack.value = packName
  await search({ q: null, tag: [], color: null, pack: packName, type: null })
}
```

Add function for view-pack event:

```javascript
function viewPack(packName) {
  selectedAsset.value = null
  window.history.pushState({ route: 'pack', name: packName }, '', `/pack/${packName}`)
  loadPack(packName)
}
```

Update `handlePopState` to handle pack route:

```javascript
function handlePopState(event) {
  const route = parseRoute(window.location.pathname)
  skipNextPush = true
  if (route.name === 'home') {
    selectedAsset.value = null
    currentPack.value = null
    search({ q: null, tag: [], color: null, pack: null, type: null })
  } else if (route.name === 'asset') {
    selectAssetFromUrl(route.params.id)
  } else if (route.name === 'similar') {
    selectedAsset.value = null
    currentPack.value = null
    loadSimilarFromUrl(route.params.id)
  } else if (route.name === 'pack') {
    selectedAsset.value = null
    loadPack(route.params.name)
  }
}
```

Update `handleInitialRoute`:

```javascript
function handleInitialRoute() {
  const route = parseRoute(window.location.pathname)
  if (route.name === 'asset') {
    selectAssetFromUrl(route.params.id)
  } else if (route.name === 'similar') {
    loadSimilarFromUrl(route.params.id)
  } else if (route.name === 'pack') {
    loadPack(route.params.name)
  }
}
```

Update template to wire up view-pack event on AssetModal:

```vue
<AssetModal
  v-if="selectedAsset"
  :asset="selectedAsset"
  @close="selectedAsset = null"
  @find-similar="findSimilar"
  @view-pack="viewPack"
/>
```

**Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: handle pack route in App.vue"
```

---

## Task 4: Add Pack Header to SearchBar

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/SearchBar.test.js`

**Step 1: Write failing test for pack header display**

Add to `tests/SearchBar.test.js`:

```javascript
it('shows pack header when currentPack is set', () => {
  const wrapper = mount(SearchBar, {
    props: {
      filters: { packs: [], tags: [], colors: [] },
      currentPack: 'fantasy-pack'
    }
  })
  expect(wrapper.text()).toContain('Viewing: fantasy-pack')
})

it('emits clear-pack when clear button clicked', async () => {
  const wrapper = mount(SearchBar, {
    props: {
      filters: { packs: [], tags: [], colors: [] },
      currentPack: 'fantasy-pack'
    }
  })
  await wrapper.find('.clear-pack-btn').trigger('click')
  expect(wrapper.emitted('clear-pack')).toBeTruthy()
})
```

**Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test -- --run`
Expected: 2 failing tests

**Step 3: Add currentPack prop and header to SearchBar.vue**

Update props:

```javascript
const props = defineProps({
  filters: {
    type: Object,
    required: true
  },
  currentPack: {
    type: String,
    default: null
  }
})
```

Update emits:

```javascript
const emit = defineEmits(['search', 'clear-pack'])
```

Add pack header to template (at the start of `.search-bar` div):

```vue
<div class="pack-header" v-if="currentPack">
  <span>Viewing: {{ currentPack }}</span>
  <button class="clear-pack-btn" @click="$emit('clear-pack')">&times; Clear</button>
</div>
```

Add CSS:

```css
.pack-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #e8f4fd;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.clear-pack-btn {
  background: none;
  border: 1px solid #007bff;
  color: #007bff;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.clear-pack-btn:hover {
  background: #007bff;
  color: white;
}
```

**Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 5: Wire up in App.vue**

Update SearchBar in template:

```vue
<SearchBar :filters="filters" :current-pack="currentPack" @search="handleSearch" @clear-pack="clearPack" />
```

Add clearPack function:

```javascript
function clearPack() {
  currentPack.value = null
  window.history.pushState({ route: 'home' }, '', '/')
  search({ q: null, tag: [], color: null, pack: null, type: null })
}
```

**Step 6: Run all tests**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue web/frontend/src/App.vue web/frontend/tests/SearchBar.test.js
git commit -m "feat: add pack header to SearchBar with clear button"
```

---

## Task 5: Convert AssetGrid to Masonry Layout

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Test: `web/frontend/tests/AssetGrid.test.js`

**Step 1: Write failing test for pack name display**

Add to `tests/AssetGrid.test.js`, update mockAssets first:

```javascript
const mockAssets = [
  { id: 1, filename: 'goblin.png', path: '/assets/goblin.png', width: 64, height: 64, pack: 'fantasy-pack' },
  { id: 2, filename: 'orc.png', path: '/assets/orc.png', width: 128, height: 128, pack: 'monster-pack' },
]
```

Add test:

```javascript
it('shows pack name on asset cards', () => {
  const wrapper = mount(AssetGrid, {
    props: { assets: mockAssets }
  })
  expect(wrapper.text()).toContain('fantasy-pack')
  expect(wrapper.text()).toContain('monster-pack')
})

it('emits view-pack event when pack name clicked', async () => {
  const wrapper = mount(AssetGrid, {
    props: { assets: mockAssets }
  })
  await wrapper.find('.asset-pack').trigger('click')
  expect(wrapper.emitted('view-pack')).toBeTruthy()
  expect(wrapper.emitted('view-pack')[0]).toEqual(['fantasy-pack'])
})
```

**Step 2: Run tests to verify they fail**

Run: `cd web/frontend && npm test -- --run`
Expected: 2 failing tests

**Step 3: Update AssetGrid template and styles**

Replace the template:

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
      >
        <div
          class="asset-image-container"
          :style="{ aspectRatio: `${asset.width} / ${asset.height}` }"
          @click="$emit('select', asset.id)"
        >
          <SpritePreview
            v-if="asset.preview_x !== null"
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
            :src="`/api/image/${asset.id}`"
            :alt="asset.filename"
          />
        </div>
        <div class="asset-info">
          <span
            class="asset-pack"
            v-if="asset.pack"
            @click.stop="$emit('view-pack', asset.pack)"
          >{{ asset.pack }}</span>
          <span class="filename">{{ asset.filename }}</span>
        </div>
      </div>
    </div>
    <div v-else class="no-results">
      No results
    </div>
  </div>
</template>
```

Update emits:

```javascript
defineEmits(['select', 'view-pack'])
```

Replace styles:

```css
<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: #666;
}

.asset-grid {
  column-width: 220px;
  column-gap: 1rem;
}

.asset-item {
  break-inside: avoid;
  margin-bottom: 1rem;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.asset-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.asset-image-container {
  width: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f8f8;
}

.asset-image-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

.asset-info {
  padding: 0.5rem;
}

.asset-pack {
  display: block;
  font-size: 0.75rem;
  color: #666;
  cursor: pointer;
  margin-bottom: 0.25rem;
}

.asset-pack:hover {
  text-decoration: underline;
  color: #007bff;
}

.filename {
  display: block;
  font-size: 0.875rem;
  word-break: break-all;
}

.no-results {
  color: #666;
  text-align: center;
  padding: 2rem;
}
</style>
```

**Step 4: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue web/frontend/tests/AssetGrid.test.js
git commit -m "feat: convert AssetGrid to masonry layout with pack names"
```

---

## Task 6: Wire Up view-pack Event from AssetGrid in App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`

**Step 1: Update AssetGrid in template**

```vue
<AssetGrid :assets="assets" @select="selectAsset" @view-pack="viewPack" />
```

**Step 2: Run all tests**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 3: Manual verification**

Start the dev server and verify:
1. Assets display in masonry layout with varying heights
2. Pack names appear on cards and are clickable
3. Clicking pack name navigates to `/pack/:name` and shows pack header
4. "View Pack" button in modal works
5. Clear button returns to home view
6. Back/forward navigation works correctly

Run: `cd web/frontend && npm run dev`

**Step 4: Commit**

```bash
git add web/frontend/src/App.vue
git commit -m "feat: wire up view-pack event from AssetGrid"
```

---

## Task 7: Build and Final Verification

**Step 1: Run production build**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 2: Run all tests one final time**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 3: Commit build artifacts if needed**

If `dist/` is tracked:
```bash
git add web/frontend/dist/
git commit -m "chore: update production build"
```

---

## Summary

After completing all tasks, the frontend will have:
1. `/pack/:name` route for viewing all assets in a pack
2. "View Pack" button in AssetModal
3. Clickable pack names on asset cards
4. Pack header in SearchBar with clear button
5. Pinterest-style masonry layout with ~220px columns
6. Larger thumbnails with natural aspect ratios
