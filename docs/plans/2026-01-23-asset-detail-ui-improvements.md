# AssetDetail UI Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve AssetDetail UX with minimum image size for pixel art and clickable tags for search.

**Architecture:** CSS-only change for minimum image size. For clickable tags: AssetDetail emits tag-click, SearchBar exposes addTagExternal method via defineExpose, App.vue wires them together.

**Tech Stack:** Vue 3 (Composition API), Vitest, @vue/test-utils

---

### Task 1: Minimum Image Size

**Files:**
- Test: `web/frontend/tests/AssetDetail.test.js`
- Modify: `web/frontend/src/components/AssetDetail.vue:96-105`

**Step 1: Write the failing test**

Add to `AssetDetail.test.js`:

```javascript
it('has minimum image size of 300x300', () => {
  const wrapper = mount(AssetDetail, {
    props: { asset: mockAsset }
  })
  const img = wrapper.find('.asset-image')
  const style = window.getComputedStyle(img.element)
  expect(style.minWidth).toBe('300px')
  expect(style.minHeight).toBe('300px')
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL - minWidth/minHeight are empty or "0px"

**Step 3: Write minimal implementation**

In `AssetDetail.vue`, update `.asset-image` CSS (around line 96):

```css
.asset-image {
  max-width: 100%;
  max-height: 400px;
  min-width: 300px;
  min-height: 300px;
  object-fit: contain;
  image-rendering: pixelated;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
}
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/tests/AssetDetail.test.js web/frontend/src/components/AssetDetail.vue
git commit -m "feat: add minimum 300x300 image size in AssetDetail"
```

---

### Task 2: Clickable Tags - AssetDetail Component

**Files:**
- Test: `web/frontend/tests/AssetDetail.test.js`
- Modify: `web/frontend/src/components/AssetDetail.vue:28-31, 65, 139-147`

**Step 1: Write the failing test**

Add to `AssetDetail.test.js`:

```javascript
it('emits tag-click when tag clicked', async () => {
  const wrapper = mount(AssetDetail, {
    props: { asset: mockAsset }
  })
  const tags = wrapper.findAll('.tag')
  await tags[0].trigger('click')
  expect(wrapper.emitted('tag-click')).toBeTruthy()
  expect(wrapper.emitted('tag-click')[0][0]).toBe('character')
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL - 'tag-click' not emitted

**Step 3: Write minimal implementation**

In `AssetDetail.vue`:

Update template (line 28-31):
```html
<div class="tags" v-if="asset.tags && asset.tags.length">
  <strong>Tags:</strong>
  <span
    v-for="tag in asset.tags"
    :key="tag"
    class="tag"
    @click="$emit('tag-click', tag)"
  >{{ tag }}</span>
</div>
```

Update defineEmits (line 65):
```javascript
defineEmits(['back', 'add-to-cart', 'find-similar', 'view-pack', 'tag-click'])
```

Update `.tag` CSS (line 139-147):
```css
.tag {
  display: inline-block;
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background-color 150ms;
}

.tag:hover {
  background: var(--color-accent);
  color: white;
}
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/tests/AssetDetail.test.js web/frontend/src/components/AssetDetail.vue
git commit -m "feat: make tags clickable in AssetDetail"
```

---

### Task 3: SearchBar - Expose addTag Method

**Files:**
- Test: `web/frontend/tests/SearchBar.test.js` (create if needed)
- Modify: `web/frontend/src/components/SearchBar.vue:23-60`

**Step 1: Write the failing test**

Create or add to `SearchBar.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

describe('SearchBar', () => {
  const mockFilters = { packs: [], tags: ['sword', 'fire'], colors: ['#ff0000'] }

  it('exposes addTagExternal method', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(typeof wrapper.vm.addTagExternal).toBe('function')
  })

  it('addTagExternal adds tag and emits search', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    wrapper.vm.addTagExternal('sword')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('search')).toBeTruthy()
    expect(wrapper.emitted('search')[0][0].tag).toContain('sword')
  })

  it('addTagExternal does not add duplicate tags', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    wrapper.vm.addTagExternal('sword')
    wrapper.vm.addTagExternal('sword')
    await wrapper.vm.$nextTick()
    const lastEmit = wrapper.emitted('search').slice(-1)[0][0]
    expect(lastEmit.tag.filter(t => t === 'sword').length).toBe(1)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL - addTagExternal is undefined

**Step 3: Write minimal implementation**

In `SearchBar.vue`, add after `removeTag` function (around line 60):

```javascript
function addTagExternal(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    emitSearch()
  }
}

defineExpose({ addTagExternal })
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/tests/SearchBar.test.js web/frontend/src/components/SearchBar.vue
git commit -m "feat: expose addTagExternal method in SearchBar"
```

---

### Task 4: Wire Tag Click in App.vue

**Files:**
- Modify: `web/frontend/src/App.vue:27-36, 56, 140-144`

**Step 1: Add ref for SearchBar**

In App.vue script setup (around line 56), add:
```javascript
const searchBarRef = ref(null)
```

**Step 2: Add handleTagClick function**

After `handleSearch` function (around line 144), add:
```javascript
function handleTagClick(tag) {
  selectedAsset.value = null
  if (searchBarRef.value) {
    searchBarRef.value.addTagExternal(tag)
  }
}
```

**Step 3: Update template**

Update SearchBar (line 27):
```html
<SearchBar ref="searchBarRef" :filters="filters" @search="handleSearch" />
```

Update AssetDetail (lines 29-36):
```html
<AssetDetail
  v-if="selectedAsset"
  :asset="selectedAsset"
  @back="selectedAsset = null"
  @add-to-cart="addToCart"
  @find-similar="findSimilar"
  @view-pack="viewPack"
  @tag-click="handleTagClick"
/>
```

**Step 4: Manual verification**

1. Open app at http://localhost:5173
2. Click an asset to open detail view
3. Click a tag
4. Verify: returns to grid view, tag appears in search filters

**Step 5: Commit**

```bash
git add web/frontend/src/App.vue
git commit -m "feat: wire tag click from AssetDetail to SearchBar"
```

---

### Task 5: Final Verification

**Step 1: Run all tests**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests pass

**Step 2: Manual smoke test**

1. Small pixel art shows at minimum 300x300
2. Clicking tag in detail view adds it to search and shows results
3. Multiple tag clicks accumulate (additive search)

**Step 3: Final commit if any cleanup needed**
