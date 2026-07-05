<template>
  <div class="pack-gallery">
    <div class="theme-chips">
      <button v-for="t in activeThemes" :key="t" class="chip" @click="scrollTo(t)">
        {{ t }} <span class="chip-count">{{ grouped[t].length }}</span>
      </button>
    </div>

    <section
      v-for="t in activeThemes"
      :key="t"
      class="theme-section"
      :ref="el => { sectionEls[t] = el }"
    >
      <h2 class="theme-title">{{ t }}</h2>
      <div class="card-grid">
        <div
          v-for="pack in grouped[t]"
          :key="pack.name"
          class="gallery-card"
          @click="$emit('view-pack', pack.name)"
        >
          <div class="card-cover">
            <img
              v-if="!failedCovers[pack.name]"
              :src="previewUrl(pack.name)"
              :alt="pack.name"
              loading="lazy"
              @error="failedCovers[pack.name] = true"
            />
            <span v-else class="cover-placeholder">📦</span>
          </div>
          <div class="card-meta">
            <span class="card-name">{{ formatPackName(pack.name) }}</span>
            <span class="badge" :class="pack.is_3d ? 'badge-3d' : 'badge-2d'">
              {{ pack.is_3d ? '3D' : '2D' }}
            </span>
            <span class="card-count">{{ pack.count }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { formatPackName } from '../utils/packName.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

// mirrors pack_themes.THEME_ORDER on the backend
const THEME_ORDER = [
  'Nature', 'Dungeons & Caves', 'Towns & Buildings', 'Characters & Creatures',
  'Magic & Effects', 'Items & Icons', 'UI', 'Sci-fi', 'Vehicles', 'Other',
]

const props = defineProps({
  packs: { type: Array, required: true }
})

defineEmits(['view-pack'])

const sectionEls = reactive({})
const failedCovers = reactive({})

const grouped = computed(() => {
  const groups = {}
  for (const pack of props.packs) {
    const theme = THEME_ORDER.includes(pack.theme) ? pack.theme : 'Other'
    if (!groups[theme]) groups[theme] = []
    groups[theme].push(pack)
  }
  return groups
})

const activeThemes = computed(() =>
  THEME_ORDER.filter(t => grouped.value[t]?.length)
)

function previewUrl(packName) {
  return `${API_BASE}/pack-preview/${encodeURIComponent(packName)}`
}

function scrollTo(theme) {
  sectionEls[theme]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.pack-gallery {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.theme-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding-bottom: 1rem;
  position: sticky;
  top: 0;
  background: var(--color-bg-base);
  z-index: 1;
}

.chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.75rem;
  cursor: pointer;
}

.chip:hover {
  border-color: var(--color-accent);
}

.chip-count {
  color: var(--color-text-secondary);
  margin-left: 0.25rem;
}

.theme-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 1rem 0 0.5rem;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.gallery-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms;
}

.gallery-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-card);
}

.card-cover {
  height: 110px;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-cover img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.cover-placeholder {
  font-size: 2rem;
  opacity: 0.5;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem;
}

.card-name {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.25;
}

.badge {
  font-size: 0.625rem;
  font-weight: 700;
  padding: 0.0625rem 0.375rem;
  border-radius: 4px;
  flex-shrink: 0;
}

.badge-3d {
  background: var(--color-accent-light);
  color: var(--color-accent);
}

.badge-2d {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

.card-count {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
</style>
