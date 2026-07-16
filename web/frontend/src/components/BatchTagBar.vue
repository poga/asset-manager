<template>
  <div class="batch-bar">
    <span class="batch-count">{{ count }} selected</span>
    <input
      v-model="draft"
      class="batch-add-input"
      placeholder="add tag"
      @keyup.enter="submitAdd"
    />
    <div v-if="unionTags.length" class="batch-union">
      <span v-for="tag in unionTags" :key="tag" class="batch-chip">
        {{ tag }}<button class="batch-chip-remove" @click="$emit('remove', tag)">×</button>
      </span>
    </div>
    <button class="batch-clear" @click="$emit('clear')">Clear</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  count: { type: Number, required: true },
  unionTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['add', 'remove', 'clear'])
const draft = ref('')

function submitAdd() {
  const t = draft.value.trim()
  if (!t) return
  emit('add', t)
  draft.value = ''
}
</script>

<style scoped>
.batch-bar {
  position: fixed; left: 50%; bottom: 1.25rem; transform: translateX(-50%);
  display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;
  max-width: min(90vw, 720px); padding: 0.6rem 1rem;
  background: var(--color-bg-elevated); color: var(--color-text-primary);
  border: 1px solid var(--color-border); border-radius: 0.6rem;
  box-shadow: var(--shadow-elevated); z-index: 50;
}
.batch-count { font-weight: 600; white-space: nowrap; }
.batch-add-input {
  padding: 0.3rem 0.5rem; border: 1px solid var(--color-border);
  border-radius: 0.35rem; background: transparent; color: inherit;
}
.batch-union { display: flex; flex-wrap: wrap; gap: 0.375rem; }
.batch-chip {
  display: inline-flex; align-items: center; gap: 0.2rem;
  padding: 0.15rem 0.45rem; border-radius: 0.75rem;
  background: var(--color-accent-light); color: var(--color-text-primary);
  font-size: 0.85rem;
}
.batch-chip-remove {
  border: none; background: none; color: inherit; cursor: pointer;
  font-size: 1rem; line-height: 1; padding: 0;
}
.batch-clear {
  border: none; background: none; color: var(--color-text-muted);
  cursor: pointer; text-decoration: underline;
}
</style>
