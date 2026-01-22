# UI Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh the frontend with a modern teal/cyan theme, better visual depth, and dark mode support.

**Architecture:** CSS custom properties define all colors in App.vue. Theme toggle reads/writes localStorage and respects system preference. Each component replaces hardcoded colors with variable references.

**Tech Stack:** Vue 3, vanilla CSS with custom properties, no external dependencies.

---

## Task 1: Add CSS Variables and Theme Toggle Logic to App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`
- Test: `web/frontend/tests/App.test.js`

**Step 1: Write failing test for theme toggle**

Add to `tests/App.test.js`:

```javascript
describe('Theme toggle', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('renders theme toggle button', async () => {
    const wrapper = mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="theme-toggle"]').exists()).toBe(true)
  })

  it('toggles theme on click', async () => {
    const wrapper = mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
    await flushPromises()

    const toggle = wrapper.find('[data-testid="theme-toggle"]')
    await toggle.trigger('click')

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('persists theme to localStorage', async () => {
    const wrapper = mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
    await flushPromises()

    const toggle = wrapper.find('[data-testid="theme-toggle"]')
    await toggle.trigger('click')

    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('loads theme from localStorage on mount', async () => {
    localStorage.setItem('theme', 'dark')

    mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
    await flushPromises()

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/App.test.js`
Expected: FAIL with "theme-toggle" not found

**Step 3: Add CSS variables to App.vue style block**

Replace the existing `<style>` block in `App.vue` with:

```css
<style>
:root {
  /* Light mode colors */
  --color-bg-base: #f8fafc;
  --color-bg-surface: #ffffff;
  --color-bg-elevated: #ffffff;
  --color-border: #e2e8f0;
  --color-border-emphasis: #cbd5e1;
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #94a3b8;

  /* Accent colors */
  --color-accent: #0d9488;
  --color-accent-hover: #0f766e;
  --color-accent-light: #ccfbf1;
  --color-success: #10b981;
  --color-danger: #ef4444;

  /* Shadows */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.08);
  --shadow-elevated: 0 4px 6px rgba(0,0,0,0.07), 0 12px 28px rgba(0,0,0,0.12);

  /* Glass effect */
  --glass-bg: rgba(255,255,255,0.8);
}

[data-theme="dark"] {
  --color-bg-base: #0f172a;
  --color-bg-surface: #1e293b;
  --color-bg-elevated: #334155;
  --color-border: #334155;
  --color-border-emphasis: #475569;
  --color-text-primary: #f8fafc;
  --color-text-secondary: #cbd5e1;
  --color-text-muted: #64748b;

  --color-accent-light: #134e4a;

  --shadow-card: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.3);
  --shadow-elevated: 0 4px 6px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.5);

  --glass-bg: rgba(30,41,59,0.8);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
}

.app {
  font-family: system-ui, sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  transition: background-color 200ms, color 200ms;
}

.app-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-header h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.theme-toggle {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 150ms, background-color 150ms;
}

.theme-toggle:hover {
  border-color: var(--color-border-emphasis);
  background: var(--color-bg-surface);
}

.theme-toggle svg {
  width: 18px;
  height: 18px;
}

.app-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 1rem;
  padding: 1rem;
  background: var(--color-bg-base);
}

.left-panel {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.middle-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-surface);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
  padding: 1rem;
}

.middle-panel > :last-child {
  flex: 1;
  overflow-y: auto;
}

.right-panel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}
</style>
```

**Step 4: Add theme toggle button and logic to App.vue**

Update the template header:

```html
<header class="app-header">
  <h1>Asset Manager</h1>
  <button
    class="theme-toggle"
    data-testid="theme-toggle"
    @click="toggleTheme"
    :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
  >
    <svg v-if="isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="5"/>
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  </button>
</header>
```

Add to script setup:

```javascript
const isDark = ref(false)

function getSystemTheme() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme) {
  isDark.value = theme === 'dark'
  document.documentElement.setAttribute('data-theme', theme)
}

function toggleTheme() {
  const newTheme = isDark.value ? 'light' : 'dark'
  localStorage.setItem('theme', newTheme)
  applyTheme(newTheme)
}

function initTheme() {
  const saved = localStorage.getItem('theme')
  const theme = saved || getSystemTheme()
  applyTheme(theme)
}

// Listen for system theme changes
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
function handleSystemThemeChange(e) {
  if (!localStorage.getItem('theme')) {
    applyTheme(e.matches ? 'dark' : 'light')
  }
}
```

Update onMounted:

```javascript
onMounted(async () => {
  initTheme()
  mediaQuery.addEventListener('change', handleSystemThemeChange)
  await fetchFilters()
  search({ q: null, tag: [], color: null, type: null })
  handleInitialRoute()
  window.addEventListener('popstate', handlePopState)
  isInitializing = false
})
```

Update onUnmounted:

```javascript
onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
  mediaQuery.removeEventListener('change', handleSystemThemeChange)
  clearTimeout(debounceTimer)
})
```

**Step 5: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/App.test.js`
Expected: PASS

**Step 6: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: add CSS variables and theme toggle"
```

---

## Task 2: Update PackList.vue to use CSS variables

**Files:**
- Modify: `web/frontend/src/components/PackList.vue`

**Step 1: Replace hardcoded colors with CSS variables**

Replace the `<style scoped>` block:

```css
<style scoped>
.pack-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.pack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.pack-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text-primary);
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  font-size: 1rem;
  color: var(--color-text-secondary);
}

.icon-btn:hover {
  color: var(--color-text-primary);
}

.pack-search {
  margin: 0.5rem;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.875rem;
  flex-shrink: 0;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}

.pack-search:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.pack-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.action-btn {
  flex: 1;
  padding: 0.375rem 0.5rem;
  font-size: 0.75rem;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-primary);
  transition: background-color 150ms, border-color 150ms;
}

.action-btn:hover:not(:disabled) {
  background: var(--color-bg-elevated);
  border-color: var(--color-border-emphasis);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pack-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.pack-card {
  background: var(--color-bg-surface);
  border: 2px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  margin-bottom: 0.5rem;
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
</style>
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add web/frontend/src/components/PackList.vue
git commit -m "style: update PackList to use CSS variables"
```

---

## Task 3: Update SearchBar.vue to use CSS variables

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`

**Step 1: Replace hardcoded colors with CSS variables**

Replace the `<style scoped>` block:

```css
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
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  transition: border-color 150ms, box-shadow 150ms;
}

.search-bar input[type="text"]:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.search-bar input[type="text"]::placeholder {
  color: var(--color-text-muted);
}

.search-bar select {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  cursor: pointer;
  transition: border-color 150ms;
}

.search-bar select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.tag {
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 150ms;
}

.tag:hover {
  background: var(--color-accent);
  color: white;
}
</style>
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue
git commit -m "style: update SearchBar to use CSS variables"
```

---

## Task 4: Update AssetGrid.vue to use CSS variables

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`

**Step 1: Replace hardcoded colors with CSS variables**

Replace the `<style scoped>` block:

```css
<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: var(--color-text-muted);
}

.asset-grid {
  column-width: 155px;
  column-gap: 1rem;
}

.asset-item {
  break-inside: avoid;
  margin-bottom: 0.75rem;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  transition: box-shadow 150ms, border-color 150ms;
}

.asset-item:hover {
  box-shadow: var(--shadow-card);
  border-color: var(--color-border-emphasis);
}

.asset-image-container {
  width: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-elevated);
  position: relative;
}

.add-cart-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: var(--color-accent);
  color: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 150ms;
}

.add-cart-btn:hover {
  background: var(--color-accent-hover);
}

.cart-indicator {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-success);
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.in-cart {
  border-color: var(--color-success);
}

.asset-image-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

.asset-info {
  padding: 0.375rem;
}

.asset-pack {
  display: block;
  font-size: 0.65rem;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-bottom: 0.25rem;
  transition: color 150ms;
}

.asset-pack:hover {
  text-decoration: underline;
  color: var(--color-accent);
}

.filename {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-results {
  color: var(--color-text-muted);
  text-align: center;
  padding: 2rem;
}
</style>
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue
git commit -m "style: update AssetGrid to use CSS variables"
```

---

## Task 5: Update AssetDetail.vue to use CSS variables

**Files:**
- Modify: `web/frontend/src/components/AssetDetail.vue`

**Step 1: Replace hardcoded colors with CSS variables**

Replace the `<style scoped>` block:

```css
<style scoped>
.asset-detail {
  padding: 1rem;
}

.back-btn {
  background: none;
  border: none;
  color: var(--color-accent);
  cursor: pointer;
  padding: 0.5rem 0;
  font-size: 0.875rem;
  margin-bottom: 1rem;
  transition: color 150ms;
}

.back-btn:hover {
  color: var(--color-accent-hover);
  text-decoration: underline;
}

.detail-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

.asset-image {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
  image-rendering: pixelated;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
}

.asset-info {
  width: 100%;
  max-width: 500px;
}

h2 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
  color: var(--color-text-primary);
}

.path {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  word-break: break-all;
  margin: 0 0 1rem;
}

.metadata {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.metadata div {
  margin-bottom: 0.25rem;
}

.tags {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.tag {
  display: inline-block;
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
}

.colors {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.color-swatch {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-left: 0.25rem;
  border: 1px solid var(--color-border);
  vertical-align: middle;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.actions button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 150ms;
}

.add-cart-btn {
  background: var(--color-accent);
  color: white;
}

.add-cart-btn:hover {
  background: var(--color-accent-hover);
}

.similar-btn {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.similar-btn:hover {
  background: var(--color-border);
}

.pack-btn {
  background: var(--color-success);
  color: white;
}

.pack-btn:hover {
  background: #0a9b6e;
}
</style>
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue
git commit -m "style: update AssetDetail to use CSS variables"
```

---

## Task 6: Update Cart.vue to use CSS variables

**Files:**
- Modify: `web/frontend/src/components/Cart.vue`

**Step 1: Replace hardcoded colors with CSS variables**

Replace the `<style scoped>` block:

```css
<style scoped>
.cart {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.cart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.cart-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text-primary);
}

.download-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin: 1rem;
  padding: 1rem;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background-color 150ms;
}

.download-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.download-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.download-icon {
  font-size: 1.25rem;
}

.items-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
}

.item-count {
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
  font-size: 0.75rem;
}

.cart-items {
  flex: 1;
  overflow-y: auto;
}

.cart-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  transition: background-color 150ms;
}

.cart-item:hover {
  background: var(--color-bg-elevated);
}

.item-thumbnail {
  width: 40px;
  height: 40px;
  object-fit: contain;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  image-rendering: pixelated;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-filename {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-pack {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.remove-btn {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0.25rem;
  transition: color 150ms;
}

.remove-btn:hover {
  color: var(--color-danger);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  text-align: center;
  padding: 2rem;
}

.empty-state p {
  margin: 0.25rem 0;
}

.hint {
  font-size: 0.75rem;
  color: var(--color-accent);
}
</style>
```

**Step 2: Run all tests to verify nothing broke**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add web/frontend/src/components/Cart.vue
git commit -m "style: update Cart to use CSS variables"
```

---

## Task 7: Final verification and merge preparation

**Step 1: Run full test suite**

Run: `cd web/frontend && npm test -- --run`
Expected: All 69+ tests PASS

**Step 2: Visual verification**

Run: `cd web/frontend && npm run dev`

Manual checks:
- Light mode looks correct (teal accents, slate borders, layered shadows)
- Click theme toggle - dark mode applies smoothly
- Click theme toggle again - light mode returns
- Refresh page - theme persists
- All components render correctly in both modes

**Step 3: Final commit if any fixes needed**

If adjustments were made:
```bash
git add -A
git commit -m "fix: polish theme implementation"
```
