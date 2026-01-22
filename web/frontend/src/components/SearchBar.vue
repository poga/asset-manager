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

.search-bar input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  transition: border-color 150ms, box-shadow 150ms;
}

.search-bar input[type="text"]:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px var(--color-accent-light);
}

.search-bar input[type="text"]::placeholder {
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
