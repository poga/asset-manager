<template>
  <div class="search-bar">
    <input
      type="text"
      v-model="query"
      placeholder="Search assets..."
      @input="emitSearch"
    />
    <select data-filter="pack" v-model="pack" @change="emitSearch">
      <option value="">All packs</option>
      <option v-for="p in filters.packs" :key="p" :value="p">{{ p }}</option>
    </select>
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
const pack = ref('')
const color = ref('')
const tags = ref([])
const selectedTag = ref('')

function emitSearch() {
  emit('search', {
    q: query.value || null,
    tag: tags.value,
    color: color.value || null,
    pack: pack.value || null,
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
  margin-bottom: 1rem;
}

.search-bar input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem;
  font-size: 1rem;
}

.search-bar select {
  padding: 0.5rem;
}

.tag {
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}

.tag:hover {
  background: #ccc;
}
</style>
