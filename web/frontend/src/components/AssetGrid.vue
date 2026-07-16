<template>
  <div class="asset-grid-container" @scroll="onScroll">
    <div class="grid-toolbar">
      <button class="select-toggle" :class="{ active: selectMode }" @click="toggleSelectMode">
        {{ selectMode ? 'Done' : 'Select' }}
      </button>
    </div>
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
          :class="{ selected: selectedIds.includes(asset.id) }"
          :style="containerStyle(asset)"
          @click="onCardClick(asset)"
        >
          <span v-if="selectMode" class="select-check">
            {{ selectedIds.includes(asset.id) ? '☑' : '☐' }}
          </span>
          <div v-if="asset.kind === 'file'" class="file-badge">
            <span class="file-ext">.{{ fileExt(asset) }}</span>
            <span class="file-size" v-if="asset.file_size != null">{{ formatSize(asset.file_size) }}</span>
          </div>
          <span
            v-else-if="asset.kind === 'font' && thumbFailed[asset.id]"
            class="font-fallback"
          >Aa</span>
          <SpritePreview
            v-else-if="asset.preview_x !== null && !asset.use_full_image"
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
            :src="`${API_BASE}/image/${asset.id}`"
            :alt="asset.filename"
            @error="asset.kind === 'font' ? (thumbFailed[asset.id] = true) : null"
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
          <span class="filename" :title="asset.filename">{{ asset.filename }}</span>
        </div>
      </div>
    </div>
    <div v-if="loading" class="loading-more">
      Loading…
    </div>
    <div v-if="assets.length === 0 && !loading" class="no-results">
      No results
    </div>
    <BatchTagBar
      v-if="selectMode && selectedIds.length"
      :count="selectedIds.length"
      :union-tags="selectionUnion"
      @add="batchAdd"
      @remove="batchRemove"
      @clear="clearSelection"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import SpritePreview from './SpritePreview.vue'
import BatchTagBar from './BatchTagBar.vue'
import { formatSize } from '../utils/fileSize.js'
import { batchAssetTags } from '../api/boards.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const props = defineProps({
  assets: {
    type: Array,
    required: true
  },
  cartIds: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select', 'view-pack', 'add-to-cart', 'load-more'])

const hoveredId = ref(null)
const thumbFailed = reactive({})

const selectMode = ref(false)
const selectedIds = ref([])
const tagOverrides = reactive({})

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = []
}

function tagsOf(asset) {
  return tagOverrides[asset.id] ?? asset.tags ?? []
}

function onCardClick(asset) {
  if (!selectMode.value) { emit('select', asset.id); return }
  const i = selectedIds.value.indexOf(asset.id)
  if (i === -1) selectedIds.value.push(asset.id)
  else selectedIds.value.splice(i, 1)
}

const selectionUnion = computed(() => {
  const set = new Set()
  for (const a of props.assets)
    if (selectedIds.value.includes(a.id)) tagsOf(a).forEach(t => set.add(t))
  return [...set].sort(collator.compare)
})

function applyResults(results) {
  for (const r of results) tagOverrides[r.id] = r.tags
}

async function batchAdd(tag) {
  applyResults((await batchAssetTags(selectedIds.value, tag, 'add')).results)
}

async function batchRemove(tag) {
  applyResults((await batchAssetTags(selectedIds.value, tag, 'remove')).results)
}

function clearSelection() { selectedIds.value = [] }

// keep selection for assets still shown; a disjoint new search drops them
watch(() => props.assets, (newAssets) => {
  const ids = new Set(newAssets.map(a => a.id))
  selectedIds.value = selectedIds.value.filter(id => ids.has(id))
  for (const k of Object.keys(tagOverrides)) {
    if (!ids.has(Number(k))) delete tagOverrides[k]
  }
})

function fileExt(asset) {
  const parts = asset.filename.split('.')
  return parts.length > 1 ? parts.pop().toUpperCase() : ''
}

// specimen/file cards have no intrinsic dimensions; fix a wide ratio
function containerStyle(asset) {
  if (asset.kind === 'file' || asset.kind === 'font') return { aspectRatio: '2 / 1' }
  return {
    aspectRatio: (asset.preview_x != null && !asset.use_full_image)
      ? `${asset.preview_width} / ${asset.preview_height}`
      : `${asset.width} / ${asset.height}`
  }
}

// fire before the user hits the bottom so the next page streams in seamlessly
function onScroll(e) {
  const el = e.currentTarget
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 400) {
    emit('load-more')
  }
}
</script>

<style scoped>
.asset-grid-container {
  padding: 1rem 1.25rem 2rem;
}

.result-count {
  margin-bottom: 0.5rem;
  color: var(--color-text-muted);
}

/* grid, not multicol, so appended items don't reflow existing columns */
.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
  gap: 0.75rem 1rem;
  align-items: start;
}

.asset-item {
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
  max-height: 200px;
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

.loading-more {
  color: var(--color-text-muted);
  text-align: center;
  padding: 1rem;
}

.file-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.file-ext {
  font-weight: 700;
  font-size: 1.125rem;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}

.file-size {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

.font-fallback {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-secondary);
}

.grid-toolbar { display: flex; justify-content: flex-end; padding: 0.25rem 0.5rem; }
.select-toggle { padding: 0.3rem 0.75rem; border: 1px solid var(--color-border);
  border-radius: 0.35rem; background: transparent; color: inherit; cursor: pointer; }
.select-toggle.active { background: var(--color-accent); color: #fff; }
.asset-image-container.selected { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.select-check { position: absolute; top: 0.4rem; left: 0.4rem; font-size: 1.1rem; z-index: 2; }
</style>
