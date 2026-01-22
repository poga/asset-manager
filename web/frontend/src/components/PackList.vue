<template>
  <div class="pack-list">
    <div class="pack-header">
      <span class="pack-title">Packs</span>
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
