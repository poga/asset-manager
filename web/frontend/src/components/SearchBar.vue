<template>
  <div class="search-bar">
    <div class="search-input-wrapper">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <path d="M21 21l-4.35-4.35"/>
      </svg>
      <input
        type="text"
        v-model="query"
        placeholder="Search assets..."
        @input="emitSearch"
      />
    </div>
    <select data-filter="color" v-model="color" @change="emitSearch">
      <option value="">Any color</option>
      <option v-for="c in filters.colors" :key="c" :value="c">{{ c }}</option>
    </select>
    <select data-filter="tag" v-model="selectedTag" @change="addTag">
      <option value="">Add tag...</option>
      <option v-for="t in filters.tags" :key="t" :value="t">{{ t }}</option>
    </select>
    <span v-for="t in tags" :key="t" class="tag" @click="removeTag(t)">
      {{ t }} &times;
    </span>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  filters: {
    type: Object,
    required: true
  }
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

function addTagExternal(tag) {
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    emitSearch()
  }
}

defineExpose({ addTagExternal })
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 0.5rem;
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

.search-bar select {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  cursor: pointer;
  transition: border-color 150ms;
}

.search-bar select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.tag {
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 150ms;
}

.tag:hover {
  background: var(--color-accent);
  color: white;
}
</style>
