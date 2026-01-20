<template>
  <div class="asset-grid-container">
    <div class="result-count" v-if="assets.length > 0">
      {{ assets.length }} results
    </div>
    <div class="asset-grid" v-if="assets.length > 0">
      <div
        v-for="asset in assets"
        :key="asset.id"
        class="asset-item"
        @click="$emit('select', asset.id)"
      >
        <SpritePreview
          v-if="asset.frames && asset.frames.length > 1"
          :asset-id="asset.id"
          :frames="asset.frames"
          :width="asset.width"
          :height="asset.height"
        />
        <img
          v-else
          :src="`/api/image/${asset.id}`"
          :alt="asset.filename"
        />
        <span class="filename">{{ asset.filename }}</span>
      </div>
    </div>
    <div v-else class="no-results">
      No results
    </div>
  </div>
</template>

<script setup>
import SpritePreview from './SpritePreview.vue'

defineProps({
  assets: {
    type: Array,
    required: true
  }
})

defineEmits(['select'])
</script>

<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: #666;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1rem;
}

.asset-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 4px;
}

.asset-item:hover {
  background: #f0f0f0;
}

.asset-item img {
  max-width: 100px;
  max-height: 100px;
  object-fit: contain;
  image-rendering: pixelated;
}

.filename {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  text-align: center;
  word-break: break-all;
}

.no-results {
  color: #666;
  text-align: center;
  padding: 2rem;
}
</style>
