# Remove Left Pack Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the redundant left `PackList` rail and its now-dead selection-mode / panel-state machinery, leaving the center `PackGallery` as the single pack surface.

**Architecture:** Pure subtraction in `web/frontend`. Remove the `<aside class="left-panel">` block, the `PackList` component, and the `selectionMode` + `packPanelState` state from `App.vue`. Preserve `selectedPacks` (still drives pack-scoped search and `/pack/:name` routing) and simplify its watcher. `.middle-panel` is already `flex: 1`, so the workspace widens with no new layout code.

**Tech Stack:** Vue 3 (`<script setup>`), Vite, Vitest + @vue/test-utils (jsdom).

## Global Constraints

- Run the tests first; all must pass except one pre-existing, unrelated failure.
- Pre-existing baseline (do NOT fix here): `tests/router.test.js` › `parses /pack/:name with spaces encoded` fails (expects `RPG Heroes`, `parseRoute` returns `RPG%20Heroes`). Baseline before work: 119 passing, 1 failing.
- No API, DB, or index changes. Frontend only.
- Comments: max one line; state the "why/what", never reference removed code, tickets, or branch names.
- Use `npm test` (vitest) from `web/frontend`. Assume dev servers on ports 5173 (frontend) and 8000 (API) are already running — do not start them.
- No new components or abstractions. This is a removal.

---

### Task 1: Remove the left pack rail

**Files:**
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/tests/App.test.js`
- Delete: `web/frontend/src/components/PackList.vue`
- Delete: `web/frontend/tests/PackList.test.js`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new. `selectedPacks`, `viewPack`, and `/pack/:name` routing keep their current behavior; multi-select and the `selectionMode`/`packPanelState` refs cease to exist.

- [ ] **Step 1: Write the failing test — the rail should be gone**

In `web/frontend/tests/App.test.js`, the "renders 3-column layout" test currently asserts the left panel exists. Flip it. Change:

```js
    expect(wrapper.find('.left-panel').exists()).toBe(true)
```

to:

```js
    expect(wrapper.find('.left-panel').exists()).toBe(false)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd web/frontend && npm test -- App.test.js`
Expected: FAIL — "renders 3-column layout" fails because `App.vue` still renders `.left-panel`. Other tests still pass.

- [ ] **Step 3: Remove the rail markup from `App.vue`**

Delete the entire left-panel `<aside>` block from the template (the block between `<div class="app-layout">` and `<main class="middle-panel">`):

```html
      <aside class="left-panel" :class="'pack-' + packPanelState">
        <div v-if="packPanelState === 'collapsed'" class="collapsed-strip" @click="togglePackPanel">
          <span class="strip-icon">📦</span>
          <span v-if="selectedPacks.length > 0" class="strip-badge">{{ selectedPacks.length }}</span>
        </div>
        <PackList
          v-else
          :packs="packList"
          v-model:selectedPacks="selectedPacks"
          v-model:selectionMode="selectionMode"
          :panelState="packPanelState"
          @toggle-panel="togglePackPanel"
          @view-pack="viewPack"
        />
      </aside>
```

Leave `<main class="middle-panel">` and the right-panel `<aside>` untouched.

- [ ] **Step 4: Remove the rail's script state and functions from `App.vue`**

4a. Delete the import:

```js
import PackList from './components/PackList.vue'
```

4b. Delete these two refs:

```js
const selectionMode = ref('single')
```
```js
const packPanelState = ref('normal') // 'collapsed' | 'normal' | 'expanded'
```

4c. Replace `loadPanelState`. From:

```js
function loadPanelState() {
  try {
    const saved = localStorage.getItem('panelState')
    if (saved) {
      const state = JSON.parse(saved)
      const validPackStates = ['collapsed', 'normal', 'expanded']
      if (validPackStates.includes(state.pack)) packPanelState.value = state.pack
      if (typeof state.cart === 'boolean') cartPanelExpanded.value = state.cart
      if (state.selectionMode === 'single' || state.selectionMode === 'multi') {
        selectionMode.value = state.selectionMode
      }
    }
  } catch (e) {
    // Ignore invalid localStorage data
  }
}
```

to:

```js
function loadPanelState() {
  try {
    const saved = localStorage.getItem('panelState')
    if (saved) {
      const state = JSON.parse(saved)
      if (typeof state.cart === 'boolean') cartPanelExpanded.value = state.cart
    }
  } catch (e) {
    // Ignore invalid localStorage data
  }
}
```

4d. Replace `savePanelState`. From:

```js
function savePanelState() {
  localStorage.setItem('panelState', JSON.stringify({
    pack: packPanelState.value,
    cart: cartPanelExpanded.value,
    selectionMode: selectionMode.value
  }))
}
```

to:

```js
function savePanelState() {
  localStorage.setItem('panelState', JSON.stringify({
    cart: cartPanelExpanded.value
  }))
}
```

4e. Delete `togglePackPanel` entirely:

```js
function togglePackPanel() {
  const states = ['collapsed', 'normal', 'expanded']
  const currentIndex = states.indexOf(packPanelState.value)
  packPanelState.value = states[(currentIndex + 1) % 3]
  // Auto-collapse cart when pack expands to 60%
  if (packPanelState.value === 'expanded' && cartPanelExpanded.value) {
    cartPanelExpanded.value = false
  }
  savePanelState()
}
```

4f. Simplify the `selectedPacks` watcher — drop the `selectionMode.value === 'single' &&` guard. From:

```js
    // In single mode, update URL to reflect pack selection
    if (selectionMode.value === 'single' && !skipNextPush) {
```

to:

```js
    // update URL to reflect pack selection
    if (!skipNextPush) {
```

(Leave the rest of that watcher's body unchanged.)

4g. Delete the `selectionMode` watcher entirely:

```js
watch(selectionMode, (newMode, oldMode) => {
  // When switching from multi to single, keep only first selected pack
  if (oldMode === 'multi' && newMode === 'single' && selectedPacks.value.length > 1) {
    selectedPacks.value = [selectedPacks.value[0]]
  }
  savePanelState()
})
```

(Do NOT touch `packList` — it is still consumed by `PackGallery`. Do NOT touch the `.collapsed-strip` / `.strip-icon` / `.strip-badge` CSS — the cart's collapsed strip still uses it.)

- [ ] **Step 5: Remove the left-panel CSS from `App.vue`**

Delete these four rules from the `<style>` block:

```css
.left-panel {
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.left-panel.pack-collapsed {
  width: 40px;
  overflow: hidden;
}

.left-panel.pack-normal {
  width: 320px;
}

.left-panel.pack-expanded {
  width: 60%;
}
```

- [ ] **Step 6: Update `App.test.js` for the removed component**

6a. Delete the import (line near the top):

```js
import PackList from '../src/components/PackList.vue'
```

6b. Remove the `PackList` stub from every `stubs` array. Every occurrence is the literal `'PackList', ` (always followed by another stub name), so a replace-all of the exact string `'PackList', ` → `` (empty) is safe and touches only stub arrays.

6c. Delete the "renders PackList in left panel" test entirely:

```js
  it('renders PackList in left panel', () => {
    const wrapper = mount(App, { global: { stubs: ['SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
    expect(wrapper.findComponent(PackList).exists()).toBe(true)
  })
```

6d. In the "calls pushState with /pack/:name..." test, delete the now-dead mode setup and de-reference `PackList` in the comment. Change:

```js
  it('calls pushState with /pack/:name when selecting a pack in single mode', async () => {
    const wrapper = mount(App)
    await flushPromises()
    pushStateSpy.mockClear()

    // Ensure single selection mode
    wrapper.vm.selectionMode = 'single'
    await flushPromises()

    // Simulate pack selection via v-model update (as PackList would do)
    wrapper.vm.selectedPacks = ['fantasy-pack']
```

to:

```js
  it('calls pushState with /pack/:name when a pack is selected', async () => {
    const wrapper = mount(App)
    await flushPromises()
    pushStateSpy.mockClear()

    // Simulate pack selection
    wrapper.vm.selectedPacks = ['fantasy-pack']
```

6e. In the "...deselecting the last pack..." test, delete the mode setup and rename. Change:

```js
  it('calls pushState with / when deselecting the last pack in single mode', async () => {
    // Start at /pack/test-pack
    window.history.replaceState({}, '', '/assets/pack/test-pack')

    const wrapper = mount(App)
    await flushPromises()
    pushStateSpy.mockClear()

    // Ensure single selection mode
    wrapper.vm.selectionMode = 'single'
    expect(wrapper.vm.selectedPacks).toContain('test-pack')
```

to:

```js
  it('calls pushState with / when the last pack is deselected', async () => {
    // Start at /pack/test-pack
    window.history.replaceState({}, '', '/assets/pack/test-pack')

    const wrapper = mount(App)
    await flushPromises()
    pushStateSpy.mockClear()

    expect(wrapper.vm.selectedPacks).toContain('test-pack')
```

6f. In the "returns to the gallery when the pack selection is cleared" test, drive `selectedPacks` directly instead of through the deleted component. Change:

```js
    wrapper.findComponent(PackList).vm.$emit('update:selectedPacks', ['SomePack'])
```
to:
```js
    wrapper.vm.selectedPacks = ['SomePack']
```

and change:

```js
    wrapper.findComponent(PackList).vm.$emit('update:selectedPacks', [])
```
to:
```js
    wrapper.vm.selectedPacks = []
```

- [ ] **Step 7: Delete the component and its test**

Run:

```bash
git rm web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
```

- [ ] **Step 8: Run the full suite to verify green**

Run: `cd web/frontend && npm test`
Expected: PASS for every test EXCEPT the known pre-existing `tests/router.test.js` › "parses /pack/:name with spaces encoded" failure. Net: 118 passing + that 1 pre-existing failure, 0 new failures. (Count drops from 119 because the "renders PackList" test was deleted.)

- [ ] **Step 9: Live browser verification**

With the frontend on port 5173, load the app and confirm:
- Home shows the full-width `PackGallery` with NO left rail.
- Clicking a pack card opens its `AssetGrid`.
- Clicking "Asset Manager" (Home) returns to the gallery.
- The cart on the right still expands and collapses.

- [ ] **Step 10: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: remove redundant left pack rail"
```

(The `git rm` from Step 7 is already staged; this commit includes the deletions.)

## Self-Review

**Spec coverage:**
- Remove `<aside class="left-panel">` block → Step 3. ✓
- Remove `PackList.vue` + `PackList.test.js` → Step 7. ✓
- Remove left-panel CSS → Step 5. ✓
- Remove `packPanelState` / `togglePackPanel` → Steps 4b, 4e. ✓
- Remove `selectionMode` + its watcher → Steps 4b, 4g. ✓
- Keep `selectedPacks`, simplify its watcher (drop single-mode guard) → Step 4f. ✓
- Shrink `save/loadPanelState` to cart-only → Steps 4c, 4d. ✓
- Keep `PackGallery`, `Cart`, `.collapsed-strip` CSS → noted in Step 4g. ✓
- Test updates (delete PackList test, flip `.left-panel`, keep selectedPacks→URL tests driven directly) → Steps 1, 6. ✓
- Pre-existing router failure flagged, not fixed → Global Constraints, Step 8. ✓

**Placeholder scan:** No TBD/TODO; every edit shows exact old→new code. ✓

**Type consistency:** `selectedPacks` stays an array of pack-name strings throughout; `savePanelState` writes `{ cart }` and `loadPanelState` reads only `state.cart`, consistent. No dangling references to `selectionMode` or `packPanelState` after removal. ✓
