# 3-Column Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the frontend to a NotebookLM-style 3-column layout with pack list, search/grid, and cart panels.

**Architecture:** Vue 3 components with session-based cart state. Left panel for multi-select pack filtering, middle panel for search/grid/detail views, right panel for cart with server-side ZIP download.

**Tech Stack:** Vue 3, Vite, FastAPI, Python zipfile

---

### Task 1: Create PackList.vue Component

**Files:**
- Create: `web/frontend/src/components/PackList.vue`
- Test: `web/frontend/tests/PackList.test.js`

**Step 1: Write the failing test**

```javascript
// web/frontend/tests/PackList.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PackList from '../src/components/PackList.vue'

describe('PackList', () => {
  const mockPacks = [
    { name: 'icons', count: 124 },
    { name: 'sprites', count: 89 },
    { name: 'monsters', count: 45 },
  ]

  it('renders pack list with counts', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    expect(wrapper.text()).toContain('icons')
    expect(wrapper.text()).toContain('124')
    expect(wrapper.text()).toContain('sprites')
  })

  it('shows checkbox checked for selected packs', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'] }
    })
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const iconCheckbox = checkboxes.find(cb =>
      cb.element.closest('.pack-item')?.textContent?.includes('icons')
    )
    expect(iconCheckbox.element.checked).toBe(true)
  })

  it('emits update:selectedPacks when checkbox clicked', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(true)
    expect(wrapper.emitted('update:selectedPacks')).toBeTruthy()
  })

  it('select all checkbox selects all packs', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const selectAll = wrapper.find('.select-all input')
    await selectAll.setValue(true)
    const emitted = wrapper.emitted('update:selectedPacks')
    expect(emitted[0][0]).toEqual(['icons', 'sprites', 'monsters'])
  })

  it('filters packs when searching', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const searchInput = wrapper.find('.pack-search')
    await searchInput.setValue('icon')
    expect(wrapper.text()).toContain('icons')
    expect(wrapper.text()).not.toContain('monsters')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/PackList.test.js`
Expected: FAIL with "Cannot find module"

**Step 3: Write minimal implementation**

```vue
<!-- web/frontend/src/components/PackList.vue -->
<template>
  <div class="pack-list">
    <div class="pack-header">
      <span class="pack-title">Packs</span>
      <button class="icon-btn" @click="showSearch = !showSearch">
        <span>🔍</span>
      </button>
    </div>

    <input
      v-if="showSearch"
      type="text"
      class="pack-search"
      v-model="searchQuery"
      placeholder="Filter packs..."
    />

    <label class="select-all">
      <input
        type="checkbox"
        :checked="allSelected"
        :indeterminate="someSelected && !allSelected"
        @change="toggleAll"
      />
      <span>Select all packs</span>
    </label>

    <div class="pack-items">
      <label
        v-for="pack in filteredPacks"
        :key="pack.name"
        class="pack-item"
      >
        <input
          type="checkbox"
          :checked="selectedPacks.includes(pack.name)"
          @change="togglePack(pack.name)"
        />
        <span class="pack-name">{{ pack.name }}</span>
        <span class="pack-count">{{ pack.count }}</span>
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  packs: { type: Array, required: true },
  selectedPacks: { type: Array, required: true }
})

const emit = defineEmits(['update:selectedPacks'])

const showSearch = ref(false)
const searchQuery = ref('')

const filteredPacks = computed(() => {
  if (!searchQuery.value) return props.packs
  const q = searchQuery.value.toLowerCase()
  return props.packs.filter(p => p.name.toLowerCase().includes(q))
})

const allSelected = computed(() =>
  props.packs.length > 0 && props.packs.every(p => props.selectedPacks.includes(p.name))
)

const someSelected = computed(() =>
  props.packs.some(p => props.selectedPacks.includes(p.name))
)

function togglePack(name) {
  const newSelected = props.selectedPacks.includes(name)
    ? props.selectedPacks.filter(n => n !== name)
    : [...props.selectedPacks, name]
  emit('update:selectedPacks', newSelected)
}

function toggleAll(event) {
  if (event.target.checked) {
    emit('update:selectedPacks', props.packs.map(p => p.name))
  } else {
    emit('update:selectedPacks', [])
  }
}
</script>

<style scoped>
.pack-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fafafa;
  border-right: 1px solid #e0e0e0;
}

.pack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.pack-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: #333;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  font-size: 1rem;
}

.pack-search {
  margin: 0.5rem 1rem;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.875rem;
}

.select-all {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  color: #666;
  border-bottom: 1px solid #e0e0e0;
  cursor: pointer;
}

.pack-items {
  flex: 1;
  overflow-y: auto;
}

.pack-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  cursor: pointer;
}

.pack-item:hover {
  background: #f0f0f0;
}

.pack-name {
  flex: 1;
  font-size: 0.875rem;
  color: #333;
}

.pack-count {
  font-size: 0.75rem;
  color: #888;
}
</style>
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/PackList.test.js`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add web/frontend/src/components/PackList.vue web/frontend/tests/PackList.test.js
git commit -m "feat: add PackList component with multi-select filtering"
```

---

### Task 2: Create Cart.vue Component

**Files:**
- Create: `web/frontend/src/components/Cart.vue`
- Test: `web/frontend/tests/Cart.test.js`

**Step 1: Write the failing test**

```javascript
// web/frontend/tests/Cart.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Cart from '../src/components/Cart.vue'

describe('Cart', () => {
  const mockItems = [
    { id: 1, filename: 'button.png', pack: 'ui-kit' },
    { id: 2, filename: 'slime.png', pack: 'monsters' },
  ]

  it('renders cart items', () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    expect(wrapper.text()).toContain('button.png')
    expect(wrapper.text()).toContain('ui-kit')
    expect(wrapper.text()).toContain('slime.png')
  })

  it('shows empty state when no items', () => {
    const wrapper = mount(Cart, {
      props: { items: [] }
    })
    expect(wrapper.text()).toContain('No items in cart')
  })

  it('emits remove when remove button clicked', async () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    await wrapper.find('.remove-btn').trigger('click')
    expect(wrapper.emitted('remove')).toBeTruthy()
    expect(wrapper.emitted('remove')[0][0]).toBe(1)
  })

  it('emits download when download button clicked', async () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    await wrapper.find('.download-btn').trigger('click')
    expect(wrapper.emitted('download')).toBeTruthy()
  })

  it('disables download button when cart is empty', () => {
    const wrapper = mount(Cart, {
      props: { items: [] }
    })
    const downloadBtn = wrapper.find('.download-btn')
    expect(downloadBtn.element.disabled).toBe(true)
  })

  it('shows item count in header', () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    expect(wrapper.text()).toContain('2')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/Cart.test.js`
Expected: FAIL with "Cannot find module"

**Step 3: Write minimal implementation**

```vue
<!-- web/frontend/src/components/Cart.vue -->
<template>
  <div class="cart">
    <div class="cart-header">
      <span class="cart-title">Cart</span>
    </div>

    <button
      class="download-btn"
      :disabled="items.length === 0"
      @click="$emit('download')"
    >
      <span class="download-icon">📥</span>
      <span>Download ZIP</span>
    </button>

    <div class="items-header">
      <span>Items</span>
      <span class="item-count" v-if="items.length > 0">{{ items.length }}</span>
    </div>

    <div class="cart-items" v-if="items.length > 0">
      <div
        v-for="item in items"
        :key="item.id"
        class="cart-item"
      >
        <img
          :src="`/api/image/${item.id}`"
          :alt="item.filename"
          class="item-thumbnail"
        />
        <div class="item-info">
          <span class="item-filename">{{ item.filename }}</span>
          <span class="item-pack">{{ item.pack }}</span>
        </div>
        <button class="remove-btn" @click="$emit('remove', item.id)">×</button>
      </div>
    </div>

    <div class="empty-state" v-else>
      <p>No items in cart</p>
      <p class="hint">Hover over assets and click + to add</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true }
})

defineEmits(['remove', 'download'])
</script>

<style scoped>
.cart {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fafafa;
  border-left: 1px solid #e0e0e0;
}

.cart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #e0e0e0;
}

.cart-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: #333;
}

.download-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin: 1rem;
  padding: 1rem;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s;
}

.download-btn:hover:not(:disabled) {
  background: #e8e8e8;
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
  color: #666;
  border-bottom: 1px solid #e0e0e0;
}

.item-count {
  background: #e0e0e0;
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
  border-bottom: 1px solid #eee;
}

.cart-item:hover {
  background: #f5f5f5;
}

.item-thumbnail {
  width: 40px;
  height: 40px;
  object-fit: contain;
  background: #fff;
  border: 1px solid #ddd;
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
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-pack {
  display: block;
  font-size: 0.75rem;
  color: #888;
}

.remove-btn {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: #999;
  cursor: pointer;
  padding: 0.25rem;
}

.remove-btn:hover {
  color: #666;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  text-align: center;
  padding: 2rem;
}

.empty-state p {
  margin: 0.25rem 0;
}

.hint {
  font-size: 0.75rem;
}
</style>
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/Cart.test.js`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add web/frontend/src/components/Cart.vue web/frontend/tests/Cart.test.js
git commit -m "feat: add Cart component with download and remove"
```

---

### Task 3: Create AssetDetail.vue Component

**Files:**
- Create: `web/frontend/src/components/AssetDetail.vue`
- Test: `web/frontend/tests/AssetDetail.test.js`

**Step 1: Write the failing test**

```javascript
// web/frontend/tests/AssetDetail.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetDetail from '../src/components/AssetDetail.vue'

describe('AssetDetail', () => {
  const mockAsset = {
    id: 1,
    filename: 'hero.png',
    path: 'characters/hero.png',
    pack: 'sprites',
    width: 64,
    height: 64,
    tags: ['character', 'player'],
    colors: [
      { hex: '#ff0000', percentage: 0.3 },
      { hex: '#00ff00', percentage: 0.2 },
    ],
  }

  it('renders asset details', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('hero.png')
    expect(wrapper.text()).toContain('64x64')
    expect(wrapper.text()).toContain('sprites')
  })

  it('shows back button', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('.back-btn').exists()).toBe(true)
  })

  it('emits back when back button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.back-btn').trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()
  })

  it('emits add-to-cart when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.add-cart-btn').trigger('click')
    expect(wrapper.emitted('add-to-cart')).toBeTruthy()
    expect(wrapper.emitted('add-to-cart')[0][0]).toEqual(mockAsset)
  })

  it('emits find-similar when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.similar-btn').trigger('click')
    expect(wrapper.emitted('find-similar')).toBeTruthy()
    expect(wrapper.emitted('find-similar')[0][0]).toBe(1)
  })

  it('emits view-pack when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.pack-btn').trigger('click')
    expect(wrapper.emitted('view-pack')).toBeTruthy()
    expect(wrapper.emitted('view-pack')[0][0]).toBe('sprites')
  })

  it('renders tags', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('character')
    expect(wrapper.text()).toContain('player')
  })

  it('renders color swatches', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    const swatches = wrapper.findAll('.color-swatch')
    expect(swatches.length).toBe(2)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/AssetDetail.test.js`
Expected: FAIL with "Cannot find module"

**Step 3: Write minimal implementation**

```vue
<!-- web/frontend/src/components/AssetDetail.vue -->
<template>
  <div class="asset-detail">
    <button class="back-btn" @click="$emit('back')">
      ← Back to results
    </button>

    <div class="detail-content">
      <img
        :src="`/api/image/${asset.id}`"
        :alt="asset.filename"
        class="asset-image"
      />

      <div class="asset-info">
        <h2>{{ asset.filename }}</h2>
        <p class="path">{{ asset.path }}</p>

        <div class="metadata">
          <div v-if="asset.pack">
            <strong>Pack:</strong> {{ asset.pack }}
          </div>
          <div>
            <strong>Size:</strong> {{ asset.width }}x{{ asset.height }}
          </div>
        </div>

        <div class="tags" v-if="asset.tags && asset.tags.length">
          <strong>Tags:</strong>
          <span v-for="tag in asset.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>

        <div class="colors" v-if="asset.colors && asset.colors.length">
          <strong>Colors:</strong>
          <span
            v-for="color in asset.colors"
            :key="color.hex"
            class="color-swatch"
            :style="{ backgroundColor: color.hex }"
            :title="`${color.hex} (${Math.round(color.percentage * 100)}%)`"
          ></span>
        </div>

        <div class="actions">
          <button class="add-cart-btn" @click="$emit('add-to-cart', asset)">
            Add to Cart
          </button>
          <button class="similar-btn" @click="$emit('find-similar', asset.id)">
            Find Similar
          </button>
          <button class="pack-btn" v-if="asset.pack" @click="$emit('view-pack', asset.pack)">
            View Pack
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  asset: { type: Object, required: true }
})

defineEmits(['back', 'add-to-cart', 'find-similar', 'view-pack'])
</script>

<style scoped>
.asset-detail {
  padding: 1rem;
}

.back-btn {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  padding: 0.5rem 0;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.back-btn:hover {
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
  background: #f8f8f8;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}

.asset-info {
  width: 100%;
  max-width: 500px;
}

h2 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
}

.path {
  color: #666;
  font-size: 0.875rem;
  word-break: break-all;
  margin: 0 0 1rem;
}

.metadata {
  margin-bottom: 1rem;
}

.metadata div {
  margin-bottom: 0.25rem;
}

.tags {
  margin-bottom: 1rem;
}

.tag {
  display: inline-block;
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
}

.colors {
  margin-bottom: 1rem;
}

.color-swatch {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-left: 0.25rem;
  border: 1px solid #ccc;
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
}

.add-cart-btn {
  background: #007bff;
  color: white;
}

.add-cart-btn:hover {
  background: #0056b3;
}

.similar-btn {
  background: #6c757d;
  color: white;
}

.similar-btn:hover {
  background: #545b62;
}

.pack-btn {
  background: #28a745;
  color: white;
}

.pack-btn:hover {
  background: #218838;
}
</style>
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/AssetDetail.test.js`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add web/frontend/src/components/AssetDetail.vue web/frontend/tests/AssetDetail.test.js
git commit -m "feat: add AssetDetail component with actions"
```

---

### Task 4: Update AssetGrid.vue with Cart Button

**Files:**
- Modify: `web/frontend/src/components/AssetGrid.vue`
- Modify: `web/frontend/tests/AssetGrid.test.js`

**Step 1: Write the failing test**

Add to existing `AssetGrid.test.js`:

```javascript
// Add these tests to web/frontend/tests/AssetGrid.test.js

it('shows add-to-cart button on hover', async () => {
  const wrapper = mount(AssetGrid, {
    props: { assets: mockAssets, cartIds: [] }
  })
  const item = wrapper.find('.asset-item')
  await item.trigger('mouseenter')
  expect(wrapper.find('.add-cart-btn').exists()).toBe(true)
})

it('emits add-to-cart when button clicked', async () => {
  const wrapper = mount(AssetGrid, {
    props: { assets: mockAssets, cartIds: [] }
  })
  const item = wrapper.find('.asset-item')
  await item.trigger('mouseenter')
  await wrapper.find('.add-cart-btn').trigger('click')
  expect(wrapper.emitted('add-to-cart')).toBeTruthy()
})

it('shows in-cart indicator for items in cart', () => {
  const wrapper = mount(AssetGrid, {
    props: { assets: mockAssets, cartIds: [1] }
  })
  expect(wrapper.find('.in-cart').exists()).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/AssetGrid.test.js`
Expected: FAIL - new tests fail because cartIds prop and add-cart-btn don't exist

**Step 3: Update implementation**

Update `AssetGrid.vue`:

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
        :class="{ 'in-cart': cartIds.includes(asset.id) }"
        @mouseenter="hoveredId = asset.id"
        @mouseleave="hoveredId = null"
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
          <button
            v-if="hoveredId === asset.id && !cartIds.includes(asset.id)"
            class="add-cart-btn"
            @click.stop="$emit('add-to-cart', asset)"
          >+</button>
          <span v-if="cartIds.includes(asset.id)" class="cart-indicator">✓</span>
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

<script setup>
import { ref } from 'vue'
import SpritePreview from './SpritePreview.vue'

defineProps({
  assets: { type: Array, required: true },
  cartIds: { type: Array, default: () => [] }
})

defineEmits(['select', 'view-pack', 'add-to-cart'])

const hoveredId = ref(null)
</script>

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

.asset-item.in-cart {
  border-color: #007bff;
}

.asset-image-container {
  width: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f8f8;
  position: relative;
}

.asset-image-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

.add-cart-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #007bff;
  color: white;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.add-cart-btn:hover {
  background: #0056b3;
}

.cart-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #28a745;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
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

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/AssetGrid.test.js`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add web/frontend/src/components/AssetGrid.vue web/frontend/tests/AssetGrid.test.js
git commit -m "feat: add cart button on hover to AssetGrid"
```

---

### Task 5: Update SearchBar.vue (Remove Pack Dropdown)

**Files:**
- Modify: `web/frontend/src/components/SearchBar.vue`
- Modify: `web/frontend/tests/SearchBar.test.js`

**Step 1: Update test to not expect pack dropdown**

Update `SearchBar.test.js` - remove pack dropdown tests and update remaining tests:

```javascript
// web/frontend/tests/SearchBar.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

describe('SearchBar', () => {
  const mockFilters = {
    packs: ['icons', 'sprites'],
    tags: ['character', 'ui'],
    colors: ['red', 'blue', 'green'],
  }

  it('renders search input', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('renders color dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="color"]').exists()).toBe(true)
  })

  it('does not render pack dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="pack"]').exists()).toBe(false)
  })

  it('emits search on input', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    await wrapper.find('input[type="text"]').setValue('hero')
    expect(wrapper.emitted('search')).toBeTruthy()
  })

  it('renders tag dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="tag"]').exists()).toBe(true)
  })

  it('adds and displays tags', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    const tagSelect = wrapper.find('select[data-filter="tag"]')
    await tagSelect.setValue('character')
    expect(wrapper.text()).toContain('character')
  })

  it('removes tag when clicked', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    const tagSelect = wrapper.find('select[data-filter="tag"]')
    await tagSelect.setValue('character')
    await wrapper.find('.tag').trigger('click')
    expect(wrapper.text()).not.toContain('character ×')
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/SearchBar.test.js`
Expected: FAIL - test "does not render pack dropdown" fails because pack dropdown still exists

**Step 3: Update implementation**

Update `SearchBar.vue` - remove pack dropdown and pack header:

```vue
<template>
  <div class="search-bar">
    <input
      type="text"
      v-model="query"
      placeholder="Search assets..."
      @input="emitSearch"
    />
    <select data-filter="color" v-model="color" @change="emitSearch">
      <option value="">Any color</option>
      <option v-for="c in filters.colors" :key="c" :value="c">{{ c }}</option>
    </select>
    <select data-filter="tag" v-model="selectedTag" @change="addTag">
      <option value="">Add tag...</option>
      <option v-for="t in filters.tags" :key="t" :value="t">{{ t }}</option>
    </select>
    <span v-for="t in tags" :key="t" class="tag" @click="removeTag(t)">
      {{ t }} ×
    </span>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  filters: { type: Object, required: true }
})

const emit = defineEmits(['search'])

const query = ref('')
const color = ref('')
const tags = ref([])
const selectedTag = ref('')

function emitSearch() {
  emit('search', {
    q: query.value || null,
    tag: tags.value,
    color: color.value || null,
    type: null
  })
}

function addTag() {
  if (selectedTag.value && !tags.value.includes(selectedTag.value)) {
    tags.value.push(selectedTag.value)
    selectedTag.value = ''
    emitSearch()
  }
}

function removeTag(tag) {
  tags.value = tags.value.filter(t => t !== tag)
  emitSearch()
}
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
  padding: 1rem;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.search-bar input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.search-bar select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.tag {
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.tag:hover {
  background: #ccc;
}
</style>
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/SearchBar.test.js`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add web/frontend/src/components/SearchBar.vue web/frontend/tests/SearchBar.test.js
git commit -m "refactor: remove pack dropdown from SearchBar"
```

---

### Task 6: Add Download Cart API Endpoint

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
# Add these tests to web/test_api.py

def test_download_cart_returns_zip(client, sample_db):
    """Test download cart returns a zip file."""
    response = client.post("/api/download-cart", json={"asset_ids": [1, 2]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]


def test_download_cart_empty_returns_400(client, sample_db):
    """Test download cart with empty list returns 400."""
    response = client.post("/api/download-cart", json={"asset_ids": []})
    assert response.status_code == 400


def test_download_cart_invalid_ids_skipped(client, sample_db):
    """Test download cart skips invalid asset IDs."""
    response = client.post("/api/download-cart", json={"asset_ids": [1, 9999]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
```

**Step 2: Run test to verify it fails**

Run: `cd web && uv run pytest test_api.py -k download_cart -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

Add to `web/api.py`:

```python
import zipfile
from datetime import datetime
from pydantic import BaseModel

class DownloadCartRequest(BaseModel):
    asset_ids: list[int]


@app.post("/api/download-cart")
def download_cart(request: DownloadCartRequest):
    """Download selected assets as a ZIP file."""
    if not request.asset_ids:
        raise HTTPException(status_code=400, detail="No assets selected")

    conn = get_db()

    # Get asset paths
    placeholders = ",".join("?" * len(request.asset_ids))
    rows = conn.execute(
        f"SELECT id, path, filename FROM assets WHERE id IN ({placeholders})",
        request.asset_ids
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No valid assets found")

    assets_dir = get_assets_path()

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            file_path = assets_dir / row["path"]
            if file_path.exists():
                # Use filename to avoid path issues
                zf.write(file_path, row["filename"])

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="assets-{timestamp}.zip"'
        }
    )
```

**Step 4: Run test to verify it passes**

Run: `cd web && uv run pytest test_api.py -k download_cart -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: add download-cart API endpoint"
```

---

### Task 7: Update App.vue with 3-Column Layout

**Files:**
- Modify: `web/frontend/src/App.vue`
- Modify: `web/frontend/tests/App.test.js`

**Step 1: Write the failing test**

Update `App.test.js` with new tests for 3-column layout:

```javascript
// Add/update in web/frontend/tests/App.test.js

import PackList from '../src/components/PackList.vue'
import Cart from '../src/components/Cart.vue'
import AssetDetail from '../src/components/AssetDetail.vue'

it('renders 3-column layout', () => {
  const wrapper = mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
  expect(wrapper.find('.left-panel').exists()).toBe(true)
  expect(wrapper.find('.middle-panel').exists()).toBe(true)
  expect(wrapper.find('.right-panel').exists()).toBe(true)
})

it('renders PackList in left panel', () => {
  const wrapper = mount(App, { global: { stubs: ['SearchBar', 'AssetGrid', 'Cart', 'AssetDetail'] } })
  expect(wrapper.findComponent(PackList).exists()).toBe(true)
})

it('renders Cart in right panel', () => {
  const wrapper = mount(App, { global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'AssetDetail'] } })
  expect(wrapper.findComponent(Cart).exists()).toBe(true)
})

it('shows AssetDetail when asset selected', async () => {
  const wrapper = mount(App, {
    global: { stubs: ['PackList', 'SearchBar', 'AssetGrid', 'Cart'] }
  })
  // Simulate selecting an asset
  wrapper.vm.selectedAsset = { id: 1, filename: 'test.png' }
  await wrapper.vm.$nextTick()
  expect(wrapper.findComponent(AssetDetail).exists()).toBe(true)
})

it('hides AssetGrid when asset selected', async () => {
  const wrapper = mount(App, {
    global: { stubs: ['PackList', 'SearchBar', 'Cart', 'AssetDetail'] }
  })
  wrapper.vm.selectedAsset = { id: 1, filename: 'test.png' }
  await wrapper.vm.$nextTick()
  expect(wrapper.findComponent(AssetGrid).exists()).toBe(false)
})
```

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test -- --run tests/App.test.js`
Expected: FAIL - layout classes don't exist

**Step 3: Update implementation**

Rewrite `App.vue`:

```vue
<template>
  <div class="app">
    <header class="app-header">
      <h1>Asset Manager</h1>
    </header>

    <div class="app-layout">
      <aside class="left-panel">
        <PackList
          :packs="packList"
          v-model:selectedPacks="selectedPacks"
        />
      </aside>

      <main class="middle-panel">
        <SearchBar
          :filters="filters"
          @search="handleSearch"
        />

        <AssetDetail
          v-if="selectedAsset"
          :asset="selectedAsset"
          @back="selectedAsset = null"
          @add-to-cart="addToCart"
          @find-similar="findSimilar"
          @view-pack="viewPack"
        />

        <AssetGrid
          v-else
          :assets="assets"
          :cart-ids="cartIds"
          @select="selectAsset"
          @view-pack="viewPack"
          @add-to-cart="addToCart"
        />
      </main>

      <aside class="right-panel">
        <Cart
          :items="cartItems"
          @remove="removeFromCart"
          @download="downloadCart"
        />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PackList from './components/PackList.vue'
import SearchBar from './components/SearchBar.vue'
import AssetGrid from './components/AssetGrid.vue'
import AssetDetail from './components/AssetDetail.vue'
import Cart from './components/Cart.vue'
import { parseRoute } from './router.js'

const filters = ref({ packs: [], tags: [], colors: [] })
const assets = ref([])
const selectedAsset = ref(null)
const selectedPacks = ref([])
const cartItems = ref([])
const currentSearchParams = ref({})

let debounceTimer = null

const packList = computed(() => {
  return filters.value.packs.map(name => ({
    name,
    count: 0  // Will be populated from API
  }))
})

const cartIds = computed(() => cartItems.value.map(item => item.id))

async function fetchFilters() {
  const res = await fetch('/api/filters')
  const data = await res.json()
  filters.value = data
  // Select all packs by default
  selectedPacks.value = data.packs
}

async function search(params) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.color) query.set('color', params.color)
  if (params.type) query.set('type', params.type)
  for (const t of params.tag || []) {
    query.append('tag', t)
  }
  // Filter by selected packs
  for (const p of selectedPacks.value) {
    query.append('pack', p)
  }

  const res = await fetch(`/api/search?${query}`)
  const data = await res.json()
  assets.value = data.assets
}

function handleSearch(params) {
  currentSearchParams.value = params
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(params), 150)
}

// Re-search when selected packs change
watch(selectedPacks, () => {
  search(currentSearchParams.value)
})

async function selectAsset(id) {
  const res = await fetch(`/api/asset/${id}`)
  selectedAsset.value = await res.json()
  window.history.pushState({ route: 'asset', id }, '', `/asset/${id}`)
}

async function findSimilar(id) {
  selectedAsset.value = null
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
  window.history.pushState({ route: 'similar', id }, '', `/similar/${id}`)
}

function viewPack(packName) {
  selectedAsset.value = null
  selectedPacks.value = [packName]
  window.history.pushState({ route: 'pack', name: packName }, '', `/pack/${packName}`)
}

function addToCart(asset) {
  if (!cartItems.value.some(item => item.id === asset.id)) {
    cartItems.value.push({
      id: asset.id,
      filename: asset.filename,
      pack: asset.pack
    })
  }
}

function removeFromCart(id) {
  cartItems.value = cartItems.value.filter(item => item.id !== id)
}

async function downloadCart() {
  if (cartItems.value.length === 0) return

  const response = await fetch('/api/download-cart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_ids: cartIds.value })
  })

  if (response.ok) {
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `assets-${Date.now()}.zip`
    a.click()
    URL.revokeObjectURL(url)
  }
}

function handlePopState() {
  const route = parseRoute(window.location.pathname)
  if (route.name === 'home') {
    selectedAsset.value = null
    selectedPacks.value = filters.value.packs
  } else if (route.name === 'asset') {
    selectAsset(route.params.id)
  } else if (route.name === 'similar') {
    selectedAsset.value = null
    findSimilar(route.params.id)
  } else if (route.name === 'pack') {
    selectedAsset.value = null
    selectedPacks.value = [route.params.name]
  }
}

function handleInitialRoute() {
  const route = parseRoute(window.location.pathname)
  if (route.name === 'asset') {
    selectAsset(route.params.id)
  } else if (route.name === 'similar') {
    findSimilar(route.params.id)
  } else if (route.name === 'pack') {
    selectedPacks.value = [route.params.name]
  }
}

onMounted(async () => {
  await fetchFilters()
  search({})
  handleInitialRoute()
  window.addEventListener('popstate', handlePopState)
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
})
</script>

<style>
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
}

.app-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e0e0e0;
  background: #fff;
}

.app-header h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.app-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel {
  width: 240px;
  flex-shrink: 0;
  overflow-y: auto;
}

.middle-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.middle-panel > :last-child {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.right-panel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
}
</style>
```

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test -- --run tests/App.test.js`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/src/App.vue web/frontend/tests/App.test.js
git commit -m "feat: implement 3-column layout with pack list and cart"
```

---

### Task 8: Update API to Support Multi-Pack Filter

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_search_multiple_packs(client, sample_db):
    """Test search with multiple pack filters."""
    response = client.get("/api/search?pack=icons&pack=sprites")
    assert response.status_code == 200
    data = response.json()
    # Should return assets from both packs
    packs = {a["pack"] for a in data["assets"]}
    assert "icons" in packs or "sprites" in packs or len(packs) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd web && uv run pytest test_api.py -k multiple_packs -v`
Expected: FAIL or PASS depending on current behavior

**Step 3: Update implementation**

Update the search endpoint in `web/api.py`:

```python
@app.get("/api/search")
def search(
    q: Optional[str] = None,
    tag: list[str] = Query(default=[]),
    color: Optional[str] = None,
    pack: list[str] = Query(default=[]),  # Changed from Optional[str] to list[str]
    type: Optional[str] = None,
    limit: int = 100,
):
    """Search assets by name, tags, or filters."""
    conn = get_db()

    conditions = []
    params = []

    if q:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if pack:
        # Support multiple packs with OR
        pack_conditions = []
        for p in pack:
            pack_conditions.append("p.name LIKE ?")
            params.append(f"%{p}%")
        conditions.append(f"({' OR '.join(pack_conditions)})")

    if type:
        conditions.append("a.filetype = ?")
        params.append(type.lower().lstrip("."))

    for t in tag:
        conditions.append("""
            a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
            )
        """)
        params.append(t.lower())

    if color:
        color_lower = color.lower()
        if color_lower in COLOR_NAMES:
            hex_values = COLOR_NAMES[color_lower]
            placeholders = ",".join("?" * len(hex_values))
            conditions.append(f"""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex IN ({placeholders})
                    AND percentage >= 0.1
                )
            """)
            params.extend(hex_values)
        else:
            conditions.append("""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex = ?
                    AND percentage >= 0.1
                )
            """)
            params.append(color if color.startswith("#") else f"#{color}")

    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.preview_x, a.preview_y, a.preview_width, a.preview_height,
               p.name as pack_name,
               GROUP_CONCAT(DISTINCT tg.name) as tags
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.path
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    assets = []
    for row in rows:
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
        })

    return {"assets": assets, "total": len(assets)}
```

**Step 4: Run test to verify it passes**

Run: `cd web && uv run pytest test_api.py -k multiple_packs -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/api.py web/test_api.py
git commit -m "feat: support multiple pack filters in search API"
```

---

### Task 9: Add Pack Counts to Filters API

**Files:**
- Modify: `web/api.py`
- Modify: `web/test_api.py`

**Step 1: Write the failing test**

Add to `web/test_api.py`:

```python
def test_filters_returns_pack_counts(client, sample_db):
    """Test filters endpoint returns pack counts."""
    response = client.get("/api/filters")
    assert response.status_code == 200
    data = response.json()
    assert "packs" in data
    assert len(data["packs"]) > 0
    # Packs should be objects with name and count
    assert "name" in data["packs"][0]
    assert "count" in data["packs"][0]
```

**Step 2: Run test to verify it fails**

Run: `cd web && uv run pytest test_api.py -k pack_counts -v`
Expected: FAIL - packs are strings, not objects

**Step 3: Update implementation**

Update `web/api.py`:

```python
@app.get("/api/filters")
def filters():
    """Get available filter options."""
    conn = get_db()

    packs = conn.execute("""
        SELECT p.name, p.asset_count as count
        FROM packs p
        ORDER BY p.name
    """).fetchall()

    tags = conn.execute("""
        SELECT t.name, COUNT(at.asset_id) as count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY count DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return {
        "packs": [{"name": p["name"], "count": p["count"]} for p in packs],
        "tags": [t["name"] for t in tags],
        "colors": list(COLOR_NAMES.keys()),
    }
```

**Step 4: Run test to verify it passes**

Run: `cd web && uv run pytest test_api.py -k pack_counts -v`
Expected: PASS

**Step 5: Update frontend to handle new pack format**

Update `App.vue` packList computed:

```javascript
const packList = computed(() => {
  return filters.value.packs  // Already has name and count from API
})
```

**Step 6: Commit**

```bash
git add web/api.py web/test_api.py web/frontend/src/App.vue
git commit -m "feat: add pack counts to filters API"
```

---

### Task 10: Remove AssetModal.vue

**Files:**
- Delete: `web/frontend/src/components/AssetModal.vue`
- Delete: `web/frontend/tests/AssetModal.test.js`

**Step 1: Verify no imports remain**

Run: `grep -r "AssetModal" web/frontend/src/`
Expected: No matches (we already removed it from App.vue)

**Step 2: Delete files**

```bash
rm web/frontend/src/components/AssetModal.vue
rm web/frontend/tests/AssetModal.test.js
```

**Step 3: Run all tests**

Run: `cd web/frontend && npm test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove unused AssetModal component"
```

---

### Task 11: Run Full Test Suite and Fix Issues

**Step 1: Run all frontend tests**

Run: `cd web/frontend && npm test`

**Step 2: Run all backend tests**

Run: `cd web && uv run pytest test_api.py -v`

**Step 3: Fix any failing tests**

Address each failure one by one.

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: fix all tests for 3-column layout"
```

---

### Task 12: Manual Testing

**Step 1: Start the backend**

```bash
cd /path/to/asset-manager
uv run web/api.py
```

**Step 2: Start the frontend dev server**

```bash
cd web/frontend
npm run dev
```

**Step 3: Test in browser**

- [ ] Pack list shows with checkboxes and counts
- [ ] Selecting/deselecting packs filters results
- [ ] Search bar filters work (query, color, tags)
- [ ] Clicking asset shows detail view in middle panel
- [ ] Back button returns to grid
- [ ] Add to cart button appears on hover
- [ ] Items appear in cart when added
- [ ] Remove from cart works
- [ ] Download ZIP downloads file with assets
- [ ] URL routing works for direct links

**Step 4: Final commit if needed**

```bash
git add -A
git commit -m "fix: address manual testing issues"
```
