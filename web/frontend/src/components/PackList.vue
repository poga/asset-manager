<template>
  <div class="pack-list">
    <div class="pack-header">
      <span class="pack-title">Packs<span v-if="selectedPacks.length > 0"> ({{ selectedPacks.length }} selected)</span></span>
      <button class="icon-btn" @click="showSearch = !showSearch">
        <span>&#x1F50D;</span>
      </button>
    </div>

    <input
      v-if="showSearch"
      type="text"
      class="pack-search"
      v-model="searchQuery"
      placeholder="Filter packs..."
    />

    <div class="pack-actions">
      <button class="action-btn" @click="selectAll" :disabled="allSelected">Select all</button>
      <button class="action-btn" @click="clearAll" :disabled="noneSelected">Clear</button>
    </div>

    <div class="pack-grid">
      <div
        v-for="pack in filteredPacks"
        :key="pack.name"
        class="pack-card"
        :class="{ selected: selectedPacks.includes(pack.name) }"
        @click="togglePack(pack.name)"
      >
        <div class="pack-preview-container">
          <img
            :src="getPreviewUrl(pack.name)"
            :alt="pack.name"
            class="pack-preview"
            loading="lazy"
          />
        </div>
        <div class="pack-info">
          <span class="pack-name">{{ formatPackName(pack.name) }}</span>
          <span class="pack-count">{{ pack.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

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

const noneSelected = computed(() => props.selectedPacks.length === 0)

function togglePack(name) {
  const newSelected = props.selectedPacks.includes(name)
    ? props.selectedPacks.filter(n => n !== name)
    : [...props.selectedPacks, name]
  emit('update:selectedPacks', newSelected)
}

function selectAll() {
  emit('update:selectedPacks', props.packs.map(p => p.name))
}

function clearAll() {
  emit('update:selectedPacks', [])
}

function getPreviewUrl(packName) {
  return `${API_BASE}/pack-preview/${encodeURIComponent(packName)}`
}

function formatPackName(name) {
  let formatted = name
    .replace(/^Minifantasy_/, '')
    .replace(/_v\.?\d+\.?\d*(_Commercial_Version)?$/, '')
    .replace(/_/g, ' ')
  return formatted
}
</script>

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
