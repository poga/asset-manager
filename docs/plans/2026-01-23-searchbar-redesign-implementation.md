# SearchBar Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign SearchBar with minimal, clean aesthetic - custom dropdowns, pill-shaped tags, and refined search input with icon.

**Architecture:** Replace native `<select>` elements with custom dropdown components (button + panel). Add search icon inside input wrapper. Restyle tags as subtle pills with hover-revealed close icon. All changes contained in SearchBar.vue.

**Tech Stack:** Vue 3 (composition API), scoped CSS, inline SVGs for icons

---

### Task 1: Update tests for new dropdown structure

**Files:**
- Modify: `web/frontend/tests/SearchBar.test.js`

**Step 1: Update test for color dropdown**

Replace the test that checks for `select[data-filter="color"]` with one that checks for the custom dropdown button:

```javascript
it('renders color dropdown', () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  expect(wrapper.find('[data-filter="color"]').exists()).toBe(true)
  expect(wrapper.find('[data-filter="color"]').text()).toContain('Any color')
})
```

**Step 2: Update test for tag dropdown**

Replace the test that checks for `select[data-filter="tag"]`:

```javascript
it('renders tag dropdown', () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  expect(wrapper.find('[data-filter="tag"]').exists()).toBe(true)
  expect(wrapper.find('[data-filter="tag"]').text()).toContain('Add tag')
})
```

**Step 3: Update test for adding tags via dropdown**

Replace the test that uses `setValue` on select with clicking dropdown option:

```javascript
it('adds and displays tags', async () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  // Open tag dropdown
  await wrapper.find('[data-filter="tag"]').trigger('click')
  // Click first tag option
  await wrapper.find('[data-filter="tag"] .dropdown-option').trigger('click')
  expect(wrapper.find('.tag').exists()).toBe(true)
})
```

**Step 4: Update test for removing tags**

Update to work with new tag structure where × is inside the tag:

```javascript
it('removes tag when clicked', async () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  // Add a tag via exposed method
  wrapper.vm.addTagExternal('character')
  await wrapper.vm.$nextTick()
  expect(wrapper.find('.tag').exists()).toBe(true)
  // Click the tag to remove
  await wrapper.find('.tag').trigger('click')
  expect(wrapper.find('.tag').exists()).toBe(false)
})
```

**Step 5: Add test for dropdown open/close**

```javascript
it('opens and closes dropdown on click', async () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  const dropdown = wrapper.find('[data-filter="color"]')
  // Initially closed
  expect(wrapper.find('[data-filter="color"] .dropdown-panel').exists()).toBe(false)
  // Click to open
  await dropdown.trigger('click')
  expect(wrapper.find('.dropdown-panel').exists()).toBe(true)
  // Click again to close
  await dropdown.trigger('click')
  expect(wrapper.find('[data-filter="color"] .dropdown-panel').exists()).toBe(false)
})
```

**Step 6: Add test for pack dropdown not rendered**

Update the pack dropdown test:

```javascript
it('does not render pack dropdown', () => {
  const wrapper = mount(SearchBar, {
    props: { filters: mockFilters }
  })
  expect(wrapper.find('[data-filter="pack"]').exists()).toBe(false)
})
```

**Step 7: Run tests to verify they fail**

Run: `cd web/frontend && uv run npm test`
Expected: Tests fail because component still uses native selects

**Step 8: Commit test changes**

```bash
git add web/frontend/tests/SearchBar.test.js
git commit -m "test: update SearchBar tests for custom dropdown structure"
```

---

### Task 2: Add search input wrapper with icon

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Update template - wrap input with icon container**

Replace the plain `<input>` in template (lines 3-8) with:

```vue
<div class="search-input-wrapper">
  <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="11" cy="11" r="8"/>
    <path d="M21 21l-4.35-4.35"/>
  </svg>
  <input
    type="text"
    v-model="query"
    placeholder="Search assets..."
    @input="emitSearch"
  />
</div>
```

**Step 2: Add CSS for search input wrapper and icon**

Add new styles (replace `.search-bar input[type="text"]` section):

```css
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
```

**Step 3: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: Input-related tests pass, dropdown tests still fail

**Step 4: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): add search icon inside input"
```

---

### Task 3: Replace color select with custom dropdown

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Add dropdown state refs**

Add to script setup section after existing refs:

```javascript
const colorDropdownOpen = ref(false)
```

**Step 2: Replace color select in template**

Replace the color `<select>` (lines 9-12 originally) with:

```vue
<div class="dropdown" data-filter="color">
  <button type="button" class="dropdown-trigger" @click="colorDropdownOpen = !colorDropdownOpen">
    <span>{{ color || 'Any color' }}</span>
    <svg class="dropdown-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6 9l6 6 6-6"/>
    </svg>
  </button>
  <div v-if="colorDropdownOpen" class="dropdown-panel">
    <button type="button" class="dropdown-option" @click="selectColor('')">Any color</button>
    <button
      v-for="c in filters.colors"
      :key="c"
      type="button"
      class="dropdown-option"
      @click="selectColor(c)"
    >
      {{ c }}
    </button>
  </div>
</div>
```

**Step 3: Add selectColor function**

Add to script section:

```javascript
function selectColor(c) {
  color.value = c
  colorDropdownOpen.value = false
  emitSearch()
}
```

**Step 4: Add dropdown CSS**

Add to style section:

```css
.dropdown {
  position: relative;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 10px;
  min-width: 100px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.875rem;
  cursor: pointer;
}

.dropdown-trigger:focus {
  outline: none;
  border-color: var(--color-accent);
}

.dropdown-chevron {
  width: 12px;
  height: 12px;
  color: var(--color-text-muted);
  margin-left: auto;
}

.dropdown-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 100%;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: var(--shadow-elevated);
  z-index: 100;
  max-height: 240px;
  overflow-y: auto;
}

.dropdown-option {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--color-text-primary);
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}

.dropdown-option:hover {
  background: var(--color-bg-elevated);
}
```

**Step 5: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: Color dropdown tests pass

**Step 6: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): replace color select with custom dropdown"
```

---

### Task 4: Replace tag select with custom dropdown

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Add tag dropdown state**

Add ref:

```javascript
const tagDropdownOpen = ref(false)
```

**Step 2: Replace tag select in template**

Replace the tag `<select>` with:

```vue
<div class="dropdown" data-filter="tag">
  <button type="button" class="dropdown-trigger" @click="tagDropdownOpen = !tagDropdownOpen">
    <span>Add tag...</span>
    <svg class="dropdown-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6 9l6 6 6-6"/>
    </svg>
  </button>
  <div v-if="tagDropdownOpen" class="dropdown-panel">
    <button
      v-for="t in filters.tags"
      :key="t"
      type="button"
      class="dropdown-option"
      @click="selectTag(t)"
    >
      {{ t }}
    </button>
  </div>
</div>
```

**Step 3: Add selectTag function**

Replace the existing `addTag` function with:

```javascript
function selectTag(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    emitSearch()
  }
  tagDropdownOpen.value = false
}
```

**Step 4: Remove unused selectedTag ref**

Remove:

```javascript
const selectedTag = ref('')
```

**Step 5: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: Tag dropdown tests pass

**Step 6: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): replace tag select with custom dropdown"
```

---

### Task 5: Update tag pill styling

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Update tag template markup**

Replace the tag `<span>` with:

```vue
<span v-for="t in tags" :key="t" class="tag" :title="t" @click="removeTag(t)">
  <span class="tag-text">{{ t }}</span>
  <svg class="tag-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M18 6L6 18M6 6l12 12"/>
  </svg>
</span>
```

**Step 2: Update tag CSS**

Replace the existing `.tag` and `.tag:hover` styles with:

```css
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
  opacity: 0;
  color: var(--color-text-muted);
}

.tag:hover .tag-close {
  opacity: 1;
}

.tag:hover {
  background: var(--color-border);
}
```

**Step 3: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): restyle tags as subtle pills with hover close"
```

---

### Task 6: Add click-outside to close dropdowns

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Import onMounted and onUnmounted**

Update import:

```javascript
import { ref, onMounted, onUnmounted } from 'vue'
```

**Step 2: Add click-outside handler**

Add after the refs:

```javascript
function handleClickOutside(event) {
  const target = event.target
  if (!target.closest('[data-filter="color"]')) {
    colorDropdownOpen.value = false
  }
  if (!target.closest('[data-filter="tag"]')) {
    tagDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
```

**Step 3: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): close dropdowns on click outside"
```

---

### Task 7: Update container styling and final cleanup

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Update container CSS**

Update `.search-bar` to use 12px gaps:

```css
.search-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 1rem;
}
```

**Step 2: Remove old select styles**

Delete these CSS rules that are no longer needed:

```css
.search-bar select { ... }
.search-bar select:focus { ... }
```

Also delete the old input styles:

```css
.search-bar input[type="text"] { ... }
.search-bar input[type="text"]:focus { ... }
.search-bar input[type="text"]::placeholder { ... }
```

**Step 3: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: All tests pass

**Step 4: Verify in browser**

Open http://localhost:5173 and verify:
- Search icon appears inside input
- Custom dropdowns open/close properly
- Tags display as pills with hover close icon
- Overall spacing looks clean and minimal

**Step 5: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): finalize minimal styling and cleanup"
```

---

### Task 8: Add keyboard support for dropdowns

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Add Escape key handler**

Add to script:

```javascript
function handleKeydown(event) {
  if (event.key === 'Escape') {
    colorDropdownOpen.value = false
    tagDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
```

**Step 2: Run tests**

Run: `cd web/frontend && uv run npm test`
Expected: All tests pass

**Step 3: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "feat(SearchBar): add Escape key to close dropdowns"
```

---

### Summary

After completing all tasks, the SearchBar will have:
- Search icon inside the input field
- Custom dropdown menus (not native selects)
- Pill-shaped tags with hover-revealed close icons
- Clean, minimal styling with proper spacing
- Click-outside and Escape key to close dropdowns
- All existing functionality preserved
