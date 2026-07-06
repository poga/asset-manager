<template>
  <div class="pack-gallery">
    <div v-if="allTags.length" class="tag-chips">
      <button
        v-for="t in allTags"
        :key="t.tag"
        class="chip"
        :class="{ active: activeTag === t.tag }"
        @click="toggleTag(t.tag)"
      >
        {{ t.tag }} <span class="chip-count">{{ t.count }}</span>
      </button>
    </div>

    <section v-for="s in sections" :key="s.label" class="dim-section">
      <div class="dim-header">
        <h2 class="dim-title">{{ s.label }}</h2>
        <span class="dim-count">{{ s.packs.length }} {{ s.packs.length === 1 ? 'pack' : 'packs' }}</span>
        <span class="dim-rule" aria-hidden="true"></span>
      </div>
      <div class="card-grid">
        <div
          v-for="pack in s.packs"
          :key="pack.name"
          class="gallery-card"
          @click="$emit('view-pack', pack.name)"
        >
          <div class="card-cover">
            <img
              v-if="!failedCovers[pack.name]"
              :src="previewUrl(pack.name)"
              :alt="formatPackName(pack.name)"
              :class="{ pixelated: smallCovers[pack.name] }"
              loading="lazy"
              @load="onCoverLoad(pack.name, $event)"
              @error="failedCovers[pack.name] = true"
            />
            <span v-else class="cover-placeholder">📦</span>
          </div>
          <div class="card-meta">
            <span class="card-name" :title="formatPackName(pack.name)">{{ formatPackName(pack.name) }}</span>
            <span class="card-count">{{ pack.count }} {{ pack.count === 1 ? 'asset' : 'assets' }}</span>
          </div>
          <div class="card-tags" @click.stop>
            <span v-for="tag in tagsOf(pack)" :key="tag" class="tag-chip">
              {{ tag }}<button class="tag-remove" @click="removeTag(pack, tag)">×</button>
            </span>
            <input
              v-if="editingPack === pack.name"
              v-model="newTag"
              class="tag-input"
              placeholder="tag"
              @keyup.enter="addTag(pack)"
              @keyup.escape="stopEditing"
              @blur="stopEditing"
              v-focus
            />
            <button v-else class="tag-add" @click="startEditing(pack.name)">+</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { formatPackName } from '../utils/packName.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

const props = defineProps({
  packs: { type: Array, required: true }
})

defineEmits(['view-pack'])

const failedCovers = reactive({})
// sprites below this width are upscaled; pixelated keeps them crisp
const smallCovers = reactive({})
// overrides pack.tags after edits; tagsOf() falls back to props
const tagOverrides = reactive({})
const activeTag = ref(null)
const editingPack = ref(null)
const newTag = ref('')

const vFocus = { mounted: el => el.focus() }

function onCoverLoad(packName, event) {
  if (event.target.naturalWidth < 200) smallCovers[packName] = true
}

function tagsOf(pack) {
  return tagOverrides[pack.name] ?? pack.tags ?? []
}

const allTags = computed(() => {
  const counts = {}
  for (const pack of props.packs) {
    for (const tag of tagsOf(pack)) {
      counts[tag] = (counts[tag] || 0) + 1
    }
  }
  return Object.keys(counts).sort().map(tag => ({ tag, count: counts[tag] }))
})

const sections = computed(() => {
  const visible = activeTag.value
    ? props.packs.filter(p => tagsOf(p).includes(activeTag.value))
    : props.packs
  return [
    { label: '2D', packs: visible.filter(p => !p.is_3d) },
    { label: '3D', packs: visible.filter(p => p.is_3d) },
  ].filter(s => s.packs.length)
})

function toggleTag(tag) {
  activeTag.value = activeTag.value === tag ? null : tag
}

function previewUrl(packName) {
  return `${API_BASE}/pack-preview/${encodeURIComponent(packName)}`
}

function startEditing(packName) {
  editingPack.value = packName
  newTag.value = ''
}

function stopEditing() {
  editingPack.value = null
  newTag.value = ''
}

async function addTag(pack) {
  const tag = newTag.value.trim()
  if (!tag) return
  try {
    const res = await fetch(`${API_BASE}/pack/${encodeURIComponent(pack.name)}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag })
    })
    if (res.ok) {
      tagOverrides[pack.name] = (await res.json()).tags
    }
  } finally {
    stopEditing()
  }
}

async function removeTag(pack, tag) {
  const res = await fetch(
    `${API_BASE}/pack/${encodeURIComponent(pack.name)}/tags/${encodeURIComponent(tag)}`,
    { method: 'DELETE' }
  )
  if (res.ok) {
    tagOverrides[pack.name] = (await res.json()).tags
    // a filter pointing at a tag that no longer exists would blank the gallery
    if (activeTag.value && !allTags.value.some(t => t.tag === activeTag.value)) {
      activeTag.value = null
    }
  }
}
</script>

<style scoped>
.pack-gallery {
  flex: 1;
  overflow-y: auto;
  padding: 0 1.25rem 2rem;
}

.tag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0 -1.25rem;
  padding: 1rem 1.25rem 0.875rem;
  position: sticky;
  top: 0;
  background: var(--color-bg-surface);
  border-bottom: 1px solid var(--color-border);
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
  transition: border-color 120ms, background-color 120ms;
}

.chip:hover {
  border-color: var(--color-accent);
}

.chip.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.chip-count {
  color: var(--color-text-muted);
  margin-left: 0.25rem;
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin: 1.75rem 0 1rem;
}

.dim-section:first-of-type .dim-header {
  margin-top: 1.25rem;
}

.dim-title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}

.dim-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.dim-rule {
  flex: 1;
  height: 1px;
  background: var(--color-border);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.25rem 1rem;
}

.gallery-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms, transform 150ms;
}

.gallery-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}

@media (prefers-reduced-motion: reduce) {
  .gallery-card {
    transition: none;
  }

  .gallery-card:hover {
    transform: none;
  }
}

.card-cover {
  aspect-ratio: 5 / 3;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0.5rem;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.card-cover img.pixelated {
  image-rendering: pixelated;
}

.cover-placeholder {
  font-size: 2rem;
  opacity: 0.4;
}

.card-meta {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.625rem 0.75rem 0;
}

.card-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem 0.75rem;
  cursor: default;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  border-radius: 999px;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

.tag-remove {
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
  line-height: 1;
  opacity: 0;
  transition: opacity 120ms;
}

.tag-chip:hover .tag-remove,
.tag-remove:focus-visible {
  opacity: 1;
}

.tag-remove:hover {
  color: var(--color-danger);
}

.tag-add {
  border: 1px dashed var(--color-border);
  background: none;
  color: var(--color-text-secondary);
  border-radius: 999px;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  cursor: pointer;
  line-height: 1.2;
  opacity: 0;
  transition: opacity 120ms;
}

.gallery-card:hover .tag-add,
.tag-add:focus-visible {
  opacity: 1;
}

.tag-add:hover {
  border-color: var(--color-accent);
  color: var(--color-text-primary);
}

.tag-input {
  width: 6rem;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  border: 1px solid var(--color-accent);
  border-radius: 999px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}
</style>
