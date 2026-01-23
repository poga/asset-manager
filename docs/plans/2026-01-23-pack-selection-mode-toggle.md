# Pack Selection Mode Toggle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Change pack selection from multi-select default to single-select default with a toggle button to switch modes.

**Architecture:** Add `selectionMode` state to App.vue, persist to localStorage with existing panel state. Modify PackList.vue to accept the mode as a prop and change click behavior accordingly. Add a toggle button in the header actions area.

**Tech Stack:** Vue 3 Composition API, Vitest for testing

---

### Task 1: Test single-select mode click behavior

**Files:**
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the failing test for single-select replacing selection**

Add to `PackList.test.js`:

```javascript
it('single mode: clicking a pack replaces selection', async () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'single' }
  })
  const spritesCard = wrapper.findAll('.pack-card').find(card => card.text().includes('sprites'))
  await spritesCard.trigger('click')
  const emitted = wrapper.emitted('update:selectedPacks')
  expect(emitted[0][0]).toEqual(['sprites'])
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL (selectionMode prop not recognized, behavior unchanged)

---

### Task 2: Test single-select mode deselect behavior

**Files:**
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the failing test for deselecting in single mode**

Add to `PackList.test.js`:

```javascript
it('single mode: clicking selected pack deselects it', async () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'single' }
  })
  const iconsCard = wrapper.findAll('.pack-card').find(card => card.text().includes('icons'))
  await iconsCard.trigger('click')
  const emitted = wrapper.emitted('update:selectedPacks')
  expect(emitted[0][0]).toEqual([])
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL

---

### Task 3: Test multi-select mode preserves existing behavior

**Files:**
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the test for multi-select toggle behavior**

Add to `PackList.test.js`:

```javascript
it('multi mode: clicking toggles pack in/out of selection', async () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'multi' }
  })
  const spritesCard = wrapper.findAll('.pack-card').find(card => card.text().includes('sprites'))
  await spritesCard.trigger('click')
  const emitted = wrapper.emitted('update:selectedPacks')
  expect(emitted[0][0]).toEqual(['icons', 'sprites'])
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL (selectionMode prop not recognized)

---

### Task 4: Implement selectionMode prop and click behavior in PackList

**Files:**
- Modify: `web/frontend/src/components/PackList.vue`

**Step 1: Add selectionMode prop**

In the `defineProps` section (around line 59), add the new prop:

```javascript
const props = defineProps({
  packs: { type: Array, required: true },
  selectedPacks: { type: Array, required: true },
  panelState: { type: String, default: 'normal' },
  selectionMode: { type: String, default: 'single' }
})
```

**Step 2: Update togglePack function**

Replace the `togglePack` function (lines 82-87) with:

```javascript
function togglePack(name) {
  if (props.selectionMode === 'single') {
    // Single mode: clicking selected pack deselects, otherwise replace selection
    const newSelected = props.selectedPacks.includes(name) ? [] : [name]
    emit('update:selectedPacks', newSelected)
  } else {
    // Multi mode: toggle pack in/out of selection
    const newSelected = props.selectedPacks.includes(name)
      ? props.selectedPacks.filter(n => n !== name)
      : [...props.selectedPacks, name]
    emit('update:selectedPacks', newSelected)
  }
}
```

**Step 3: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
git commit -m "$(cat <<'EOF'
feat: add selectionMode prop to PackList with single/multi behavior

- Single mode: clicking replaces selection, clicking selected deselects
- Multi mode: clicking toggles pack in/out of selection array
- Default to single mode

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Test mode toggle button emits update

**Files:**
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the failing test for mode toggle button**

Add to `PackList.test.js`:

```javascript
it('mode toggle button switches between single and multi', async () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: [], selectionMode: 'single' }
  })
  const modeBtn = wrapper.find('[data-testid="mode-toggle"]')
  expect(modeBtn.exists()).toBe(true)
  await modeBtn.trigger('click')
  const emitted = wrapper.emitted('update:selectionMode')
  expect(emitted[0][0]).toBe('multi')
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL (button doesn't exist)

---

### Task 6: Test Select all button hidden in single mode

**Files:**
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the failing test for hidden Select all button**

Add to `PackList.test.js`:

```javascript
it('single mode: hides Select all button', () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: [], selectionMode: 'single' }
  })
  const selectAllBtn = wrapper.findAll('.action-btn').find(btn => btn.text() === 'Select all')
  expect(selectAllBtn).toBeUndefined()
})

it('multi mode: shows Select all button', () => {
  const wrapper = mount(PackList, {
    props: { packs: mockPacks, selectedPacks: [], selectionMode: 'multi' }
  })
  const selectAllBtn = wrapper.findAll('.action-btn').find(btn => btn.text() === 'Select all')
  expect(selectAllBtn).toBeDefined()
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL (Select all button always visible)

---

### Task 7: Implement mode toggle button and conditional Select all

**Files:**
- Modify: `web/frontend/src/components/PackList.vue`

**Step 1: Add emit for selectionMode update**

Update the emits (around line 65):

```javascript
const emit = defineEmits(['update:selectedPacks', 'update:selectionMode', 'toggle-panel'])
```

**Step 2: Add mode toggle function**

Add after the `clearAll` function:

```javascript
function toggleMode() {
  const newMode = props.selectionMode === 'single' ? 'multi' : 'single'
  emit('update:selectionMode', newMode)
}
```

**Step 3: Update template - add mode toggle button**

Replace the header-actions div (lines 5-12) with:

```vue
      <div class="header-actions">
        <button class="icon-btn" @click="showSearch = !showSearch" title="Search packs">
          <span>&#x1F50D;</span>
        </button>
        <button
          class="icon-btn"
          data-testid="mode-toggle"
          @click="toggleMode"
          :title="selectionMode === 'single' ? 'Single select mode' : 'Multi select mode'"
        >
          <span v-if="selectionMode === 'single'">1️⃣</span>
          <span v-else>🔢</span>
        </button>
        <button class="icon-btn" @click="$emit('toggle-panel')" :title="panelState === 'normal' ? 'Expand panel' : 'Collapse panel'">
          <span v-if="panelState === 'normal'">➡️</span>
          <span v-else>⬅️</span>
        </button>
      </div>
```

**Step 4: Update template - conditional Select all button**

Replace the pack-actions div (lines 24-27) with:

```vue
    <div class="pack-actions">
      <button v-if="selectionMode === 'multi'" class="action-btn" @click="selectAll" :disabled="allSelected">Select all</button>
      <button class="action-btn" @click="clearAll" :disabled="noneSelected">Clear</button>
    </div>
```

**Step 5: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
git commit -m "$(cat <<'EOF'
feat: add selection mode toggle button to PackList header

- Mode toggle button shows 1️⃣ for single, 🔢 for multi
- Select all button hidden in single mode
- Emits update:selectionMode when toggled

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Test mode switching keeps first selected pack

**Files:**
- Test: `web/frontend/tests/App.test.js`

**Step 1: Write the failing test**

Add to `App.test.js` (create if needed, or add to existing):

```javascript
it('switching from multi to single keeps first selected pack', async () => {
  // This tests the App.vue watcher behavior
  const wrapper = mount(App, {
    global: {
      stubs: {
        SearchBar: true,
        AssetGrid: true,
        AssetDetail: true,
        Cart: true
      }
    }
  })
  // Wait for component to mount and fetch data
  await wrapper.vm.$nextTick()

  // Set up multi-select state with multiple packs
  wrapper.vm.selectionMode = 'multi'
  wrapper.vm.selectedPacks = ['pack1', 'pack2', 'pack3']
  await wrapper.vm.$nextTick()

  // Switch to single mode
  wrapper.vm.selectionMode = 'single'
  await wrapper.vm.$nextTick()

  expect(wrapper.vm.selectedPacks).toEqual(['pack1'])
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run`
Expected: FAIL (selectionMode doesn't exist in App.vue yet)

---

### Task 9: Add selectionMode state and watcher to App.vue

**Files:**
- Modify: `web/frontend/src/App.vue`

**Step 1: Add selectionMode ref**

After line 91 (`const selectedPacks = ref([])`), add:

```javascript
const selectionMode = ref('single')
```

**Step 2: Update loadPanelState to load selectionMode**

Replace the `loadPanelState` function (lines 101-113) with:

```javascript
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

**Step 3: Update savePanelState to save selectionMode**

Replace the `savePanelState` function (lines 115-120) with:

```javascript
function savePanelState() {
  localStorage.setItem('panelState', JSON.stringify({
    pack: packPanelState.value,
    cart: cartPanelExpanded.value,
    selectionMode: selectionMode.value
  }))
}
```

**Step 4: Add watcher for selectionMode changes**

After the `watch(selectedPacks, ...)` watcher (around line 294), add:

```javascript
watch(selectionMode, (newMode, oldMode) => {
  // When switching from multi to single, keep only first selected pack
  if (oldMode === 'multi' && newMode === 'single' && selectedPacks.value.length > 1) {
    selectedPacks.value = [selectedPacks.value[0]]
  }
  savePanelState()
})
```

**Step 5: Update PackList binding in template**

Replace the PackList component (lines 27-33) with:

```vue
        <PackList
          v-else
          :packs="packList"
          v-model:selectedPacks="selectedPacks"
          v-model:selectionMode="selectionMode"
          :panelState="packPanelState"
          @toggle-panel="togglePackPanel"
        />
```

**Step 6: Run tests to verify they pass**

Run: `cd web/frontend && npm test -- --run`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "$(cat <<'EOF'
feat: add selectionMode state to App.vue with localStorage persistence

- Default to single select mode
- Persist mode to localStorage with panel state
- When switching multi→single, keep only first selected pack

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Manual verification and final cleanup

**Step 1: Start the app and verify behavior**

Open browser at http://localhost:5173 (assuming dev server is running)

Verify:
1. Default mode is single-select (1️⃣ icon shown)
2. Clicking a pack selects it, clicking another pack replaces selection
3. Clicking selected pack deselects it
4. Toggle button switches to multi mode (🔢 icon)
5. In multi mode, Select all button appears
6. In multi mode, clicking adds packs to selection
7. Switching back to single mode keeps first pack only
8. Refresh page - mode is remembered

**Step 2: Final commit if any fixes needed**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: address any issues found during manual testing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```
