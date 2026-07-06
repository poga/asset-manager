<template>
  <div class="search-bar">
    <div class="search-input-wrapper" data-filter="suggest">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <path d="M21 21l-4.35-4.35"/>
      </svg>
      <input
        type="text"
        v-model="query"
        placeholder="Search assets or type a tag..."
        @input="onInput"
        @keydown="onKeydown"
      />
      <div v-if="suggestionsOpen && suggestions.length" class="suggestion-panel">
        <button
          v-for="(s, i) in suggestions"
          :key="s.name"
          type="button"
          class="suggestion"
          :class="{ highlighted: i === highlight }"
          @mousedown.prevent="addTag(s.name)"
        >
          <span class="suggestion-name">{{ s.name }}</span>
          <span class="suggestion-count">{{ s.count }}</span>
        </button>
      </div>
    </div>
    <div v-if="tags.length" class="tags-row">
      <span v-for="t in tags" :key="t" class="tag" :title="t" @click="removeTag(t)">
        <span class="tag-text">{{ t }}</span>
        <svg class="tag-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['search'])

const query = ref('')
const tags = ref([])
const suggestionsOpen = ref(false)
const highlight = ref(-1)

const suggestions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return []
  const chosen = new Set(tags.value)
  const prefix = []
  const substring = []
  for (const t of props.filters.tags || []) {
    if (chosen.has(t.name)) continue
    if (t.name.startsWith(q)) prefix.push(t)
    else if (t.name.includes(q)) substring.push(t)
  }
  const byCount = (a, b) => b.count - a.count
  return [...prefix.sort(byCount), ...substring.sort(byCount)].slice(0, 12)
})

function handleClickOutside(event) {
  if (!event.target.closest('[data-filter="suggest"]')) {
    suggestionsOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

function emitSearch() {
  emit('search', {
    q: query.value || null,
    tag: tags.value
  })
}

function onInput() {
  suggestionsOpen.value = true
  highlight.value = -1
  emitSearch()
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (suggestions.value.length) {
      highlight.value = Math.min(highlight.value + 1, suggestions.value.length - 1)
    }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlight.value = Math.max(highlight.value - 1, -1)
  } else if (event.key === 'Enter') {
    // only a deliberate highlight adds a tag; plain Enter stays a text search
    if (highlight.value >= 0 && suggestions.value[highlight.value]) {
      addTag(suggestions.value[highlight.value].name)
    }
  } else if (event.key === 'Escape') {
    suggestionsOpen.value = false
    highlight.value = -1
  }
}

function addTag(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
  }
  query.value = ''
  suggestionsOpen.value = false
  highlight.value = -1
  emitSearch()
}

function removeTag(tag) {
  tags.value = tags.value.filter(t => t !== tag)
  emitSearch()
}

function addTagExternal(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    emitSearch()
  }
}

function clear() {
  query.value = ''
  tags.value = []
  suggestionsOpen.value = false
  highlight.value = -1
  emitSearch()
}

defineExpose({ addTagExternal, clear })
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 1rem;
}

.search-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 200px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input-wrapper input {
  width: 100%;
  height: 36px;
  padding: 0 0.75rem 0 36px;
  font-size: 0.875rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}

.search-input-wrapper input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.search-input-wrapper input::placeholder {
  color: var(--color-text-muted);
}

.suggestion-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: var(--shadow-elevated);
  z-index: 100;
  max-height: 320px;
  overflow-y: auto;
}

.suggestion {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--color-text-primary);
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}

.suggestion:hover,
.suggestion.highlighted {
  background: var(--color-bg-elevated);
}

.suggestion-count {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.tags-row {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border-radius: 12px;
  font-size: 0.8125rem;
  cursor: pointer;
  max-width: 120px;
}

.tag-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-close {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.tag:hover {
  background: var(--color-border);
}
</style>
