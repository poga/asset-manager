<template>
  <div class="model-viewer-wrap">
    <model-viewer
      ref="viewer"
      :src="modelUrl"
      camera-controls
      auto-rotate
      shadow-intensity="1"
      exposure="1"
      :animation-name="selectedClip?.name"
      :autoplay="isPlaying || undefined"
    />
    <div v-if="clips.length" class="anim-controls">
      <select v-model="selectedClip">
        <option :value="null">— no animation —</option>
        <option v-for="c in clips" :key="`${c.bundleId}:${c.name}`" :value="c">
          {{ c.bundleName }} › {{ c.name }}
        </option>
      </select>
      <button @click="isPlaying = !isPlaying">{{ isPlaying ? '⏸' : '▶' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  assetId: { type: Number, required: true },
  apiBase: { type: String, default: '/api' },
})

const modelUrl = computed(() => `${props.apiBase}/asset/${props.assetId}/model`)
const clips = ref([])
const selectedClip = ref(null)
const isPlaying = ref(false)

onMounted(async () => {
  const r = await fetch(`${props.apiBase}/asset/${props.assetId}/animations`)
  if (!r.ok) return
  const bundles = await r.json()
  clips.value = bundles.flatMap(b =>
    b.clips.map(c => ({ bundleId: b.bundle_id, bundleName: b.bundle_name, name: c.gltf_name }))
  )
})
</script>

<style scoped>
.model-viewer-wrap { display: flex; flex-direction: column; gap: 8px; }
model-viewer { width: 100%; height: 480px; background: #1a1a1a; border-radius: 8px; }
.anim-controls { display: flex; gap: 8px; align-items: center; }
</style>
