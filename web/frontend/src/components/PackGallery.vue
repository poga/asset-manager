<template>
  <div class="pack-gallery">
    <div class="gallery-toolbar">
      <button class="select-toggle" :class="{ active: selectMode }" @click="toggleSelectMode">
        {{ selectMode ? 'Done' : 'Select' }}
      </button>
    </div>

    <div v-if="allTags.length" class="tag-chips">
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
    </div>

    <div class="new-board-block">
      <div v-if="!creating" class="new-board-card" @click="creating = true">+ New board</div>
      <input
        v-else
        class="new-board-input"
        v-model="boardName"
        placeholder="Board name"
        @keyup.enter="submitBoard"
        @keyup.escape="cancelBoard"
        @blur="cancelBoard"
        v-focus
      />
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
          :class="{ selectable: selectMode, selected: selectedNames.includes(pack.name) }"
          @click="onCardClick(pack)"
        >
          <span v-if="selectMode" class="select-check">
            {{ selectedNames.includes(pack.name) ? '☑' : '☐' }}
          </span>
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
            <span v-if="pack.is_board" class="board-badge">BOARD</span>
          </div>
          <div class="card-meta">
            <span class="card-name" :title="formatPackName(pack.name)">{{ formatPackName(pack.name) }}</span>
            <span class="card-count">{{ pack.count }}</span>
          </div>
          <div class="card-tags" @click.stop>
            <span
              v-for="tag in tagsOf(pack)"
              :key="tag"
              class="tag-chip"
              :style="{ '--tag-hue': tagHue(tag) }"
            >
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

    <BatchTagBar
      v-if="selectMode && selectedNames.length"
      :count="selectedNames.length"
      :union-tags="selectionUnion"
      @add="batchAdd"
      @remove="batchRemove"
      @clear="clearSelection"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { formatPackName } from '../utils/packName.js'
import { tagHue } from '../utils/tagColor.js'
import BatchTagBar from './BatchTagBar.vue'
import { batchPackTags } from '../api/boards.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

const props = defineProps({
  packs: { type: Array, required: true }
})

const emit = defineEmits(['view-pack', 'create-board'])
const creating = ref(false)
const boardName = ref('')

const failedCovers = reactive({})
// sprites below this width are upscaled; pixelated keeps them crisp
const smallCovers = reactive({})
// overrides pack.tags after edits; tagsOf() falls back to props
const tagOverrides = reactive({})
const activeTag = ref(null)
const editingPack = ref(null)
const newTag = ref('')
const selectMode = ref(false)
const selectedNames = ref([])

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

const SECTIONS = [
  { key: '2d', label: '2D' },
  { key: '3d', label: '3D' },
  { key: 'fonts', label: 'Fonts' },
  { key: 'files', label: 'Files' },
]

// natural order: case-insensitive, "Series 5" before "Series 10"
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

// groups tagged packs together; untagged sink below, alphabetical throughout
function firstTag(pack) {
  const tags = tagsOf(pack)
  return tags.length ? [...tags].sort(collator.compare)[0] : null
}

function byTag(a, b) {
  const ta = firstTag(a)
  const tb = firstTag(b)
  if (ta !== tb) {
    if (ta === null) return 1
    if (tb === null) return -1
    return collator.compare(ta, tb)
  }
  return collator.compare(a.name, b.name)
}

function byName(a, b) {
  return collator.compare(a.name, b.name)
}

const sections = computed(() => {
  const visible = activeTag.value
    ? props.packs.filter(p => tagsOf(p).includes(activeTag.value))
    : props.packs
  // an active filter is the grouping, so other tags stop steering the order
  const cmp = activeTag.value ? byName : byTag
  return SECTIONS
    .map(s => ({
      label: s.label,
      packs: visible.filter(p => (p.section || '2d') === s.key).sort(cmp),
    }))
    .filter(s => s.packs.length)
})

function toggleTag(tag) {
  activeTag.value = activeTag.value === tag ? null : tag
}

function submitBoard() {
  const name = boardName.value.trim()
  if (name) emit('create-board', name)
  cancelBoard()
}

function cancelBoard() {
  creating.value = false
  boardName.value = ''
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

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedNames.value = []
}

function onCardClick(pack) {
  if (!selectMode.value) { emit('view-pack', pack.name); return }
  const i = selectedNames.value.indexOf(pack.name)
  if (i === -1) selectedNames.value.push(pack.name)
  else selectedNames.value.splice(i, 1)
}

const selectionUnion = computed(() => {
  const set = new Set()
  for (const p of props.packs)
    if (selectedNames.value.includes(p.name)) tagsOf(p).forEach(t => set.add(t))
  return [...set].sort(collator.compare)
})

function applyResults(results) {
  for (const r of results) tagOverrides[r.name] = r.tags
}

async function batchAdd(tag) {
  applyResults((await batchPackTags(selectedNames.value, tag, 'add')).results)
}

async function batchRemove(tag) {
  applyResults((await batchPackTags(selectedNames.value, tag, 'remove')).results)
}

function clearSelection() { selectedNames.value = [] }
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
  font-size: 1.375rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
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
  position: relative;
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

.new-board-block { padding: 1rem 0 0; }
.new-board-card {
  display: inline-flex; align-items: center; gap: 0.375rem;
  padding: 0.5rem 0.875rem; border: 1px dashed var(--color-border-emphasis);
  border-radius: 8px; cursor: pointer; color: var(--color-text-secondary);
  font-size: 0.875rem;
}
.new-board-card:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
.new-board-input {
  padding: 0.5rem 0.75rem; border: 1px solid var(--color-accent);
  border-radius: 8px; background: var(--color-bg-surface); color: var(--color-text-primary);
}

.card-cover {
  aspect-ratio: 5 / 3;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0.5rem;
  position: relative;
}

.board-badge {
  position: absolute; top: 0.5rem; left: 0.5rem;
  background: var(--color-accent); color: #fff; font-size: 0.625rem;
  font-weight: 700; letter-spacing: 0.04em; padding: 0.125rem 0.375rem; border-radius: 4px;
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
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem 0;
}

.card-name {
  flex: 1;
  min-width: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-count {
  flex-shrink: 0;
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
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  border-radius: 999px;
  background: hsl(var(--tag-hue, 0), 50%, 92%);
  color: hsl(var(--tag-hue, 0), 40%, 30%);
}

[data-theme='dark'] .tag-chip {
  background: hsl(var(--tag-hue, 0), 30%, 24%);
  color: hsl(var(--tag-hue, 0), 55%, 78%);
}

/* collapsed until revealed so the chip carries no phantom right padding */
.tag-remove {
  border: none;
  background: none;
  color: inherit;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
  line-height: 1;
  width: 0;
  overflow: hidden;
  opacity: 0;
  transition: opacity 120ms;
}

.tag-chip:hover .tag-remove,
.tag-remove:focus-visible {
  width: auto;
  margin-left: 0.25rem;
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

.gallery-toolbar { display: flex; justify-content: flex-end; margin-bottom: 0.5rem; }
.select-toggle { padding: 0.3rem 0.75rem; border: 1px solid var(--color-border);
  border-radius: 0.35rem; background: transparent; color: inherit; cursor: pointer; }
.select-toggle.active { background: var(--color-accent); color: #fff; }
.gallery-card.selectable { cursor: pointer; }
.gallery-card.selected { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.select-check {
  position: absolute; top: 0.4rem; right: 0.4rem; font-size: 1.1rem;
  background: var(--color-bg-elevated); border-radius: 3px; padding: 0 2px;
}
</style>
