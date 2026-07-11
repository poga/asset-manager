<!-- web/frontend/src/components/FontTester.vue -->
<template>
  <div class="font-tester">
    <input
      v-model="sample"
      class="sample-input"
      placeholder="Type to preview…"
    />
    <div v-if="error" class="tester-error">Couldn't load font preview</div>
    <div v-else-if="loaded" class="specimens">
      <p
        v-for="size in SIZES"
        :key="size"
        class="specimen"
        :style="{ fontFamily: family, fontSize: size + 'px' }"
      >{{ sample }}</p>
    </div>
    <div v-else class="tester-loading">Loading font…</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  assetId: { type: Number, required: true },
  apiBase: { type: String, required: true },
})

const SIZES = [16, 32, 64]
const sample = ref('The quick brown fox 0123456789')
const loaded = ref(false)
const error = ref(false)
const family = ref(`asset-font-${props.assetId}`)

onMounted(async () => {
  try {
    const face = new FontFace(family.value, `url(${props.apiBase}/asset/${props.assetId}/file)`)
    await face.load()
    document.fonts?.add(face)
    loaded.value = true
  } catch {
    error.value = true
  }
})
</script>

<style scoped>
.font-tester {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.5rem;
}

.sample-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.875rem;
}

.specimens {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-x: auto;
}

.specimen {
  margin: 0;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.tester-loading,
.tester-error {
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.tester-error {
  color: var(--color-danger);
}
</style>
