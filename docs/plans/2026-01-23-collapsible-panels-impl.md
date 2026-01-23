# Collapsible Panels Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make pack panel and cart panel collapsible with localStorage persistence.

**Architecture:** Add state management in App.vue for panel states, pass state and toggle functions to child components. Each panel renders either collapsed icon strip or full content based on state.

**Tech Stack:** Vue 3 Composition API, CSS, localStorage

---

## Task 1: Add Panel State Management to App.vue

**Files:**
- Modify: `web/frontend/src/App.vue:56-76` (script setup section)

**Step 1: Add state refs and localStorage functions**

Add after line 75 (`const isDefaultHomeView = ref(true)`):

```javascript
// Panel state management
const packPanelState = ref('normal') // 'collapsed' | 'normal' | 'expanded'
const cartPanelExpanded = ref(false)

function loadPanelState() {
  try {
    const saved = localStorage.getItem('panelState')
    if (saved) {
      const state = JSON.parse(saved)
      if (state.pack) packPanelState.value = state.pack
      if (typeof state.cart === 'boolean') cartPanelExpanded.value = state.cart
    }
  } catch (e) {
    // Ignore invalid localStorage data
  }
}

function savePanelState() {
  localStorage.setItem('panelState', JSON.stringify({
    pack: packPanelState.value,
    cart: cartPanelExpanded.value
  }))
}

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

function toggleCartPanel() {
  cartPanelExpanded.value = !cartPanelExpanded.value
  savePanelState()
}
```

**Step 2: Call loadPanelState in onMounted**

Find `onMounted(async () => {` and add `loadPanelState()` after `initTheme()`:

```javascript
onMounted(async () => {
  initTheme()
  loadPanelState()
  // ... rest unchanged
})
```

**Step 3: Commit**

```bash
git add web/frontend/src/App.vue
git commit -m "feat: add panel state management with localStorage"
```

---

## Task 2: Update App.vue Template for Collapsible Panels

**Files:**
- Modify: `web/frontend/src/App.vue:21-52` (template section)

**Step 1: Update left-panel aside**

Replace lines 22-24:

```vue
<aside class="left-panel" :class="'pack-' + packPanelState">
  <div v-if="packPanelState === 'collapsed'" class="collapsed-strip" @click="togglePackPanel">
    <span class="strip-icon">📦</span>
    <span v-if="selectedPacks.length > 0" class="strip-badge">{{ selectedPacks.length }}</span>
  </div>
  <PackList
    v-else
    :packs="packList"
    v-model:selectedPacks="selectedPacks"
    :panelState="packPanelState"
    @toggle-panel="togglePackPanel"
  />
</aside>
```

**Step 2: Update right-panel aside**

Replace lines 49-51:

```vue
<aside class="right-panel" :class="{ 'cart-collapsed': !cartPanelExpanded }">
  <div v-if="!cartPanelExpanded" class="collapsed-strip" @click="toggleCartPanel">
    <span class="strip-icon">🛒</span>
    <span v-if="cartItems.length > 0" class="strip-badge">{{ cartItems.length }}</span>
  </div>
  <Cart
    v-else
    :items="cartItems"
    @remove="removeFromCart"
    @download="downloadCart"
    @toggle-panel="toggleCartPanel"
  />
</aside>
```

**Step 3: Commit**

```bash
git add web/frontend/src/App.vue
git commit -m "feat: add collapsed strip rendering for panels"
```

---

## Task 3: Add Panel CSS Styles to App.vue

**Files:**
- Modify: `web/frontend/src/App.vue:410-444` (style section)

**Step 1: Update left-panel styles**

Replace `.left-panel` block (lines 410-418) with:

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

**Step 2: Update right-panel styles**

Replace `.right-panel` block (lines 436-444) with:

```css
.right-panel {
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.right-panel.cart-collapsed {
  width: 40px;
  overflow: hidden;
}

.right-panel:not(.cart-collapsed) {
  width: 280px;
}
```

**Step 3: Add collapsed strip styles**

Add at end of style section:

```css
.collapsed-strip {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 1rem;
  gap: 0.5rem;
  cursor: pointer;
  height: 100%;
}

.collapsed-strip:hover {
  background: var(--color-bg-elevated);
}

.strip-icon {
  font-size: 1.25rem;
}

.strip-badge {
  font-size: 0.625rem;
  background: var(--color-accent);
  color: white;
  padding: 0.125rem 0.375rem;
  border-radius: 8px;
  min-width: 1rem;
  text-align: center;
}
```

**Step 4: Commit**

```bash
git add web/frontend/src/App.vue
git commit -m "feat: add CSS for collapsible panel states"
```

---

## Task 4: Add Toggle Button to PackList Component

**Files:**
- Modify: `web/frontend/src/components/PackList.vue`

**Step 1: Add panelState prop and toggle emit**

Update props (line 53-56):

```javascript
const props = defineProps({
  packs: { type: Array, required: true },
  selectedPacks: { type: Array, required: true },
  panelState: { type: String, default: 'normal' }
})

const emit = defineEmits(['update:selectedPacks', 'toggle-panel'])
```

**Step 2: Add toggle button to header**

Update the pack-header div (lines 3-8):

```vue
<div class="pack-header">
  <span class="pack-title">Packs<span v-if="selectedPacks.length > 0"> ({{ selectedPacks.length }} selected)</span></span>
  <div class="header-actions">
    <button class="icon-btn" @click="showSearch = !showSearch">
      <span>&#x1F50D;</span>
    </button>
    <button class="icon-btn" @click="$emit('toggle-panel')" :title="panelState === 'normal' ? 'Expand panel' : 'Collapse panel'">
      <span v-if="panelState === 'normal'">⬅️</span>
      <span v-else>➡️</span>
    </button>
  </div>
</div>
```

**Step 3: Add header-actions CSS**

Add after `.icon-btn:hover` (around line 136):

```css
.header-actions {
  display: flex;
  gap: 0.25rem;
}
```

**Step 4: Update pack-grid for auto-fit when expanded**

Update `.pack-grid` style (lines 185-189):

```css
.pack-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
}

.pack-grid.expanded {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
```

**Step 5: Add expanded class to pack-grid in template**

Update the pack-grid div (line 23):

```vue
<div class="pack-grid" :class="{ expanded: panelState === 'expanded' }">
```

**Step 6: Remove margin-bottom from pack-card**

The pack-card currently has `margin-bottom: 0.5rem` but we're using grid gap now. Update `.pack-card` (line 191-199) to remove `margin-bottom`:

```css
.pack-card {
  background: var(--color-bg-surface);
  border: 2px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms;
}
```

**Step 7: Commit**

```bash
git add web/frontend/src/components/PackList.vue
git commit -m "feat: add toggle button and auto-fit grid to PackList"
```

---

## Task 5: Add Toggle Button to Cart Component

**Files:**
- Modify: `web/frontend/src/components/Cart.vue`

**Step 1: Add toggle emit**

Update defineEmits (line 55):

```javascript
defineEmits(['remove', 'download', 'toggle-panel'])
```

**Step 2: Add toggle button to cart-header**

Update cart-header div (lines 4-6):

```vue
<div class="cart-header">
  <span class="cart-title">Cart</span>
  <button class="icon-btn" @click="$emit('toggle-panel')" title="Collapse panel">
    <span>➡️</span>
  </button>
</div>
```

**Step 3: Add icon-btn CSS**

Add after `.cart-title` style (around line 76):

```css
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
```

**Step 4: Commit**

```bash
git add web/frontend/src/components/Cart.vue
git commit -m "feat: add toggle button to Cart component"
```

---

## Task 6: Manual Testing

**Step 1: Test pack panel**

1. Open the app in browser
2. Click pack panel toggle button - should cycle: normal → expanded → collapsed → normal
3. When expanded, pack grid should show multiple columns
4. When collapsed, should show icon strip with badge (if packs selected)

**Step 2: Test cart panel**

1. Cart should start collapsed (icon strip)
2. Click to expand, should show full cart
3. Click toggle to collapse again

**Step 3: Test auto-collapse**

1. Expand cart panel
2. Cycle pack panel to "expanded" (60%)
3. Cart should auto-collapse

**Step 4: Test persistence**

1. Set pack to expanded, cart to collapsed
2. Refresh page
3. States should be preserved

**Step 5: Commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address issues found in manual testing"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add state management and localStorage to App.vue |
| 2 | Update App.vue template for collapsed strips |
| 3 | Add CSS for panel states |
| 4 | Add toggle button and auto-fit grid to PackList |
| 5 | Add toggle button to Cart |
| 6 | Manual testing |
