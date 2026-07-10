# Color-Coded Tags + App-Shell Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every tag surface one shared color system and replace the center card with a full-bleed app shell (two sticky top bars + a slide-over cart drawer).

**Architecture:** Extract the existing `tagHue()` hash into a shared util so gallery filter chips, search-bar tags/suggestions, and asset-detail tags all color by the same hue. Strip the card chrome from `.middle-panel` so content is full-bleed; move the cart from a right-docked aside to a header button + right slide-over drawer.

**Tech Stack:** Vue 3 (`<script setup>`), Vite, Vitest + @vue/test-utils (jsdom, globals on). Frontend lives in `web/frontend`; all commands below run from there.

## Global Constraints

- Frontend only. No API, DB, or index changes.
- Comments never exceed one line; keep minimal; explain "why", not "how".
- TDD. Baseline before work: **104 passing, 1 pre-existing unrelated failure**
  in `tests/router.test.js` (`parses /pack/:name with spaces encoded`) — do NOT
  fix it here. Any other failure is yours.
- Do NOT write trivial tests for designer-adjustable values (colors, CSS
  values). Color/layout changes are verified live in the browser; existing tests
  are the regression guard. Only add tests for real behavior/logic.
- Tag chip color formula (reuse everywhere):
  - Light: `background: hsl(H,50%,92%)`, `color: hsl(H,40%,30%)`
  - Dark:  `background: hsl(H,30%,24%)`, `color: hsl(H,55%,78%)`
  where `H = tagHue(tag)`.

---

### Task 1: Shared `tagColor` util

**Files:**
- Create: `web/frontend/src/utils/tagColor.js`
- Test: `web/frontend/tests/tagColor.test.js`
- Modify: `web/frontend/src/components/PackGallery.vue` (import util, drop local copy)

**Interfaces:**
- Produces: `tagHue(tag: string) => number` — a hue in `[0,360)`, snapped to one
  of 12 evenly-spaced steps (0,30,…,330). Deterministic. Later tasks import it.

- [ ] **Step 1: Write the failing test**

Create `web/frontend/tests/tagColor.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { tagHue } from '../src/utils/tagColor.js'

describe('tagHue', () => {
  it('is deterministic for the same tag', () => {
    expect(tagHue('forest')).toBe(tagHue('forest'))
  })

  it('only returns the 12 snapped hues and spreads across them', () => {
    const allowed = new Set(Array.from({ length: 12 }, (_, i) => i * 30))
    const seen = new Set()
    const tags = ['forest', 'weapons', 'ui', 'tileset', 'rpg', 'nature',
                  'sci-fi', 'characters', 'props', 'audio', 'fx', 'terrain']
    for (const t of tags) {
      const h = tagHue(t)
      expect(allowed.has(h)).toBe(true)
      seen.add(h)
    }
    expect(seen.size).toBeGreaterThan(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/tagColor.test.js`
Expected: FAIL — cannot resolve `../src/utils/tagColor.js`.

- [ ] **Step 3: Write minimal implementation**

Create `web/frontend/src/utils/tagColor.js`:

```js
// deterministic hue per tag, snapped to evenly-spaced steps so
// unrelated tags are never a near-identical, hard-to-tell-apart color
const TAG_HUE_STEPS = 12

export function tagHue(tag) {
  let h = 0
  for (let i = 0; i < tag.length; i++) {
    h = (h << 5) - h + tag.charCodeAt(i)
    h |= 0
  }
  const step = ((h % TAG_HUE_STEPS) + TAG_HUE_STEPS) % TAG_HUE_STEPS
  return step * (360 / TAG_HUE_STEPS)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/tagColor.test.js`
Expected: PASS (2 tests).

- [ ] **Step 5: Refactor `PackGallery.vue` to use the util**

In `web/frontend/src/components/PackGallery.vue`:
- Add to the `<script setup>` imports (next to the existing `formatPackName` import):

```js
import { tagHue } from '../utils/tagColor.js'
```

- Delete the now-duplicated local definition (the comment + constant + function):

```js
// deterministic hue per tag, snapped to evenly-spaced steps so
// unrelated tags are never a near-identical, hard-to-tell-apart color
const TAG_HUE_STEPS = 12

function tagHue(tag) {
  let h = 0
  for (let i = 0; i < tag.length; i++) {
    h = (h << 5) - h + tag.charCodeAt(i)
    h |= 0
  }
  const step = ((h % TAG_HUE_STEPS) + TAG_HUE_STEPS) % TAG_HUE_STEPS
  return step * (360 / TAG_HUE_STEPS)
}
```

- [ ] **Step 6: Run the gallery + util tests**

Run: `npx vitest run tests/tagColor.test.js tests/PackGallery.test.js`
Expected: PASS (both files green — the card chips still render, now via the util).

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/utils/tagColor.js web/frontend/tests/tagColor.test.js web/frontend/src/components/PackGallery.vue
git commit -m "feat: extract shared tagHue color util"
```

---

### Task 2: Color-code all remaining tag surfaces

Pure visual change across three files, all using `tagHue` from Task 1. No new
unit tests (designer-adjustable colors) — existing component tests are the
regression guard; final look is verified live in Task 4's browser pass.

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue` (filter-chip row)
- Modify: `web/frontend/src/components/SearchBar.vue` (selected tags + suggestions)
- Modify: `web/frontend/src/components/AssetDetail.vue` (detail tags)

**Interfaces:**
- Consumes: `tagHue` from `../utils/tagColor.js`.

- [ ] **Step 1: Color the gallery filter-chip row**

In `PackGallery.vue` template, add the hue var to the filter chip button:

```html
<button
  v-for="t in allTags"
  :key="t.tag"
  class="chip"
  :class="{ active: activeTag === t.tag }"
  :style="{ '--tag-hue': tagHue(t.tag) }"
  @click="toggleTag(t.tag)"
>
  {{ t.tag }} <span class="chip-count">{{ t.count }}</span>
</button>
```

Replace the `.chip`, `.chip:hover`, `.chip.active`, `.chip-count` style rules with:

```css
.chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: hsl(var(--tag-hue, 0), 50%, 92%);
  color: hsl(var(--tag-hue, 0), 40%, 30%);
  font-size: 0.75rem;
  cursor: pointer;
  transition: filter 120ms, background-color 120ms, color 120ms;
}

.chip:hover {
  filter: brightness(0.97);
}

/* filled so the selected filter stays obvious among tinted-inactive chips */
.chip.active {
  background: hsl(var(--tag-hue, 0), 55%, 45%);
  color: #fff;
}

.chip-count {
  opacity: 0.7;
  margin-left: 0.25rem;
}

[data-theme='dark'] .chip {
  background: hsl(var(--tag-hue, 0), 30%, 24%);
  color: hsl(var(--tag-hue, 0), 55%, 78%);
}

[data-theme='dark'] .chip.active {
  background: hsl(var(--tag-hue, 0), 50%, 55%);
  color: #0f172a;
}
```

- [ ] **Step 2: Color the search-bar selected tags + suggestion dots**

In `SearchBar.vue`, add the import to `<script setup>`:

```js
import { tagHue } from '../utils/tagColor.js'
```

Selected-tag chip — add the hue var:

```html
<span v-for="t in tags" :key="t" class="tag" :title="t"
      :style="{ '--tag-hue': tagHue(t) }" @click="removeTag(t)">
  <span class="tag-text">{{ t }}</span>
  <svg class="tag-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M18 6L6 18M6 6l12 12"/>
  </svg>
</span>
```

Suggestion row — add a leading hue dot:

```html
<button
  v-for="(s, i) in suggestions"
  :key="s.name"
  type="button"
  class="suggestion"
  :class="{ highlighted: i === highlight }"
  @mousedown.prevent="addTag(s.name)"
>
  <span class="suggestion-main">
    <span class="suggestion-dot" :style="{ background: `hsl(${tagHue(s.name)}, 55%, 50%)` }"></span>
    <span class="suggestion-name">{{ s.name }}</span>
  </span>
  <span class="suggestion-count">{{ s.count }}</span>
</button>
```

Replace the `.tag` and `.tag:hover` rules with hue-based versions and add the
suggestion-dot rules:

```css
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  background: hsl(var(--tag-hue, 0), 50%, 92%);
  color: hsl(var(--tag-hue, 0), 40%, 30%);
  border-radius: 12px;
  font-size: 0.8125rem;
  cursor: pointer;
  max-width: 120px;
}

[data-theme='dark'] .tag {
  background: hsl(var(--tag-hue, 0), 30%, 24%);
  color: hsl(var(--tag-hue, 0), 55%, 78%);
}

.tag:hover {
  filter: brightness(0.97);
}

.suggestion-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.suggestion-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  flex-shrink: 0;
}
```

Also update `.tag-close` to inherit the chip color instead of muted grey — change
its `color: var(--color-text-muted);` to `color: inherit; opacity: 0.7;`.

- [ ] **Step 3: Color the asset-detail tags**

In `AssetDetail.vue`, add to `<script setup>` imports (next to the ModelViewer import):

```js
import { tagHue } from '../utils/tagColor.js'
```

Template — add the hue var to the tag span:

```html
<span
  v-for="tag in asset.tags"
  :key="tag"
  class="tag"
  :style="{ '--tag-hue': tagHue(tag) }"
  @click="$emit('tag-click', tag)"
>{{ tag }}</span>
```

Replace the `.tag` and `.tag:hover` rules:

```css
.tag {
  display: inline-block;
  background: hsl(var(--tag-hue, 0), 50%, 92%);
  color: hsl(var(--tag-hue, 0), 40%, 30%);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
  cursor: pointer;
  transition: filter 150ms;
}

[data-theme='dark'] .tag {
  background: hsl(var(--tag-hue, 0), 30%, 24%);
  color: hsl(var(--tag-hue, 0), 55%, 78%);
}

.tag:hover {
  filter: brightness(0.95);
}
```

- [ ] **Step 4: Run the affected component tests**

Run: `npx vitest run tests/PackGallery.test.js tests/SearchBar.test.js tests/AssetDetail.test.js`
Expected: PASS (no behavior changed; only styling/markup).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue web/frontend/src/components/SearchBar.vue web/frontend/src/components/AssetDetail.vue
git commit -m "feat: color-code tag filters, search tags, and detail tags"
```

---

### Task 3: Cart drawer (header button + right slide-over)

Replace the right-docked cart aside with a header button that opens a right
slide-over drawer. Delete the now-unused panel-persistence machinery.

**Files:**
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/tests/App.test.js`

**Interfaces:**
- Consumes: `Cart.vue` unchanged — props `items`, emits `remove` / `download` /
  `toggle-panel`. `App.vue` maps `toggle-panel` to "close drawer".
- Produces: reactive `cartOpen` (bool, default false) driving the drawer.

- [ ] **Step 1: Update the failing tests first**

In `web/frontend/tests/App.test.js`, replace the "renders 3-column layout" test:

```js
it('renders single-column layout with no cart aside', () => {
  const wrapper = mount(App, { global: { stubs: ['SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
  expect(wrapper.find('.left-panel').exists()).toBe(false)
  expect(wrapper.find('.middle-panel').exists()).toBe(true)
  expect(wrapper.find('.right-panel').exists()).toBe(false)
})
```

Replace the "renders Cart in right panel" test with drawer open/close behavior:

```js
it('opens and closes the cart drawer from the header button', async () => {
  const wrapper = mount(App, { global: { stubs: ['SearchBar', 'AssetGrid', 'AssetDetail'] } })
  expect(wrapper.findComponent(Cart).exists()).toBe(false)
  await wrapper.find('[data-testid="cart-button"]').trigger('click')
  expect(wrapper.findComponent(Cart).exists()).toBe(true)
  await wrapper.find('.cart-scrim').trigger('click')
  expect(wrapper.findComponent(Cart).exists()).toBe(false)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run tests/App.test.js -t "cart drawer"`
Expected: FAIL — no `[data-testid="cart-button"]` yet.

- [ ] **Step 3: Add the cart button to the header**

In `App.vue`, replace the header's contents so the theme toggle sits beside a new
cart button:

```html
<header class="app-header">
  <h1 class="home-link" @click="goHome">Asset Manager</h1>
  <div class="header-actions">
    <button
      class="cart-button"
      data-testid="cart-button"
      @click="cartOpen = true"
      title="Open cart"
    >
      <span class="cart-button-icon">🛒</span>
      <span v-if="cartItems.length > 0" class="cart-button-badge">{{ cartItems.length }}</span>
    </button>
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
  </div>
</header>
```

- [ ] **Step 4: Replace the right-panel aside with the drawer**

In `App.vue`, remove the entire `<aside class="right-panel">…</aside>` block and,
after the closing `</div>` of `.app-layout` (still inside `.app`), add the drawer:

```html
<transition name="drawer">
  <div v-if="cartOpen" class="cart-drawer-wrap">
    <div class="cart-scrim" @click="cartOpen = false"></div>
    <aside class="cart-drawer">
      <Cart
        :items="cartItems"
        @remove="removeFromCart"
        @download="downloadCart"
        @toggle-panel="cartOpen = false"
      />
    </aside>
  </div>
</transition>
```

- [ ] **Step 5: Swap the cart state + add Escape-to-close**

In `App.vue` `<script setup>`:

- Replace `const cartPanelExpanded = ref(false)` with:

```js
const cartOpen = ref(false)
```

- Delete `loadPanelState`, `savePanelState`, and `toggleCartPanel` entirely
  (the whole functions and the `// Cart panel state` comment).
- Add a keydown handler:

```js
function handleKeydown(e) {
  if (e.key === 'Escape' && cartOpen.value) cartOpen.value = false
}
```

- In `onMounted`, remove the `loadPanelState()` call and register the listener:

```js
window.addEventListener('keydown', handleKeydown)
```

- In `onUnmounted`, add:

```js
window.removeEventListener('keydown', handleKeydown)
```

- [ ] **Step 6: Swap the CSS**

In `App.vue` `<style>`, delete these rules: `.right-panel`,
`.right-panel.cart-collapsed`, `.right-panel:not(.cart-collapsed)`,
`.collapsed-strip`, `.collapsed-strip:hover`, `.strip-icon`, `.strip-badge`.
Add:

```css
.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.cart-button {
  position: relative;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  line-height: 1;
}

.cart-button:hover {
  border-color: var(--color-border-emphasis);
  background: var(--color-bg-surface);
}

.cart-button-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  font-size: 0.625rem;
  background: var(--color-accent);
  color: #fff;
  padding: 0.05rem 0.3rem;
  border-radius: 999px;
  min-width: 1rem;
  text-align: center;
}

.cart-drawer-wrap {
  position: fixed;
  inset: 0;
  z-index: 200;
}

.cart-scrim {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.cart-drawer {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: 300px;
  max-width: 85vw;
  background: var(--color-bg-surface);
  border-left: 1px solid var(--color-border);
  box-shadow: var(--shadow-elevated);
  overflow-y: auto;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 180ms;
}

.drawer-enter-active .cart-drawer,
.drawer-leave-active .cart-drawer {
  transition: transform 180ms;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .cart-drawer,
.drawer-leave-to .cart-drawer {
  transform: translateX(100%);
}
```

- [ ] **Step 7: Run the App tests**

Run: `npx vitest run tests/App.test.js`
Expected: PASS (all App tests, including the new drawer open/close).

- [ ] **Step 8: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: move cart to header button + slide-over drawer"
```

---

### Task 4: De-card the center into a full-bleed app shell

Strip the card chrome from `.middle-panel`, promote the search bar to a sticky
toolbar, and give the content views their own horizontal padding. Pure visual;
verified live in the browser. Existing tests are the regression guard.

**Files:**
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/src/components/SearchBar.vue`
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Modify: `web/frontend/src/components/AssetDetail.vue`

- [ ] **Step 1: Move SearchBar into a sticky toolbar sibling**

In `App.vue`, move `<SearchBar>` out of `<main class="middle-panel">` so it sits
between the header and `.app-layout` as its own bar. Result structure:

```html
<div class="app">
  <header class="app-header"> … </header>

  <div class="search-toolbar">
    <SearchBar ref="searchBarRef" :filters="filters" @search="handleSearch" />
  </div>

  <div class="app-layout">
    <main class="middle-panel">
      <AssetDetail v-if="selectedAsset" … />
      <PackGallery v-else-if="isDefaultHomeView" … />
      <AssetGrid v-else … />
    </main>
  </div>

  <transition name="drawer"> … cart drawer … </transition>
</div>
```

(The `.middle-panel > :last-child { flex: 1; overflow-y: auto }` rule now targets
the single view child — unchanged behavior.)

- [ ] **Step 2: Strip the card chrome + remove layout padding**

In `App.vue` `<style>`, replace `.middle-panel` and `.app-layout` with:

```css
.app-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  background: var(--color-bg-base);
}

.middle-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
```

Add the search-toolbar rule (frosted, matching the header, so the two bars read
as one stacked toolbar):

```css
.search-toolbar {
  flex-shrink: 0;
  padding: 0.75rem 1.25rem;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--color-border);
}
```

- [ ] **Step 3: Let the toolbar own the search spacing**

In `SearchBar.vue`, change `.search-bar`'s `margin-bottom: 1rem;` to
`margin-bottom: 0;` (the toolbar now owns outer spacing; the input↔tags gap is
handled by the existing `gap: 12px`).

- [ ] **Step 4: Give the content views horizontal padding**

`AssetGrid.vue` — `.asset-grid-container` has no padding today (it relied on the
card). Add a rule (or extend the existing one if present):

```css
.asset-grid-container {
  padding: 1rem 1.25rem 2rem;
}
```

`AssetDetail.vue` — change `.asset-detail`'s `padding: 1rem;` to:

```css
.asset-detail {
  padding: 1rem 1.25rem 2rem;
}
```

`PackGallery.vue` — no change; its `.pack-gallery { padding: 0 1.25rem 2rem }`
and the sticky `.tag-chips` negative-margin bleed are already relative to the
gallery's own `1.25rem`, so they still span full width.

- [ ] **Step 5: Run the full suite**

Run: `npm test`
Expected: all green **except** the one pre-existing `router.test.js` encoding
failure (104 passing + the new drawer/util tests, 1 known fail).

- [ ] **Step 6: Live browser verification (port 5173, already running)**

Confirm, in the running app, in both light and dark mode:
- Home renders full-bleed — no floating card frame; grid/gallery reach near the
  window edges; the two frosted bars (title row + search) stack at the top.
- Gallery filter chips are colored; the active (selected) chip is a filled,
  saturated hue and clearly stands out.
- The same tag is the same hue in the gallery chip, the search-bar chip, the
  suggestion dot, and asset detail.
- The 🛒 header button opens the right drawer; ✕, scrim click, and Escape all
  close it; the count badge shows the item count.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/src/components/SearchBar.vue web/frontend/src/components/AssetGrid.vue web/frontend/src/components/AssetDetail.vue
git commit -m "feat: full-bleed app-shell layout, drop center card"
```

---

## Self-Review

**Spec coverage:**
- Shared `tagColor.js` util → Task 1. ✓
- Gallery filter chips colored + filled active state → Task 2 Step 1. ✓
- Search selected tags colored + suggestion dots → Task 2 Step 2. ✓
- Asset-detail tags colored → Task 2 Step 3. ✓
- Brand bar + cart button + count badge → Task 3 Steps 3. ✓
- Cart slide-over drawer, scrim/✕/Escape close, Cart.vue reused → Task 3. ✓
- Remove right-panel aside + panelState machinery → Task 3 Steps 4–6. ✓
- De-card `.middle-panel`, sticky search toolbar, view paddings, gallery bleed
  preserved → Task 4. ✓
- Tests: new `tagColor.test.js`, updated `App.test.js`, no trivial CSS tests,
  known router failure untouched → Tasks 1 & 3, Global Constraints. ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `tagHue(tag) => number` used identically in Tasks 1–2.
`cartOpen` (bool) introduced in Task 3 and used consistently; `toggle-panel`
emit mapped to `cartOpen = false` in Task 3. `.cart-button` / `[data-testid=
"cart-button"]` / `.cart-scrim` names match between App.vue and App.test.js.
