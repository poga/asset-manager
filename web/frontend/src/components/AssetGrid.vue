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
      >
        <div
          class="asset-image-container"
          :style="{ aspectRatio: `${asset.width} / ${asset.height}` }"
          @click="$emit('select', asset.id)"
        >
          <SpritePreview
            v-if="asset.preview_x !== null"
            :asset-id="asset.id"
            :preview-x="asset.preview_x"
            :preview-y="asset.preview_y"
            :preview-width="asset.preview_width"
            :preview-height="asset.preview_height"
            :width="asset.width"
            :height="asset.height"
          />
          <img
            v-else
            :src="`/api/image/${asset.id}`"
            :alt="asset.filename"
          />
        </div>
        <div class="asset-info">
          <span
            class="asset-pack"
            v-if="asset.pack"
            @click.stop="$emit('view-pack', asset.pack)"
          >{{ asset.pack }}</span>
          <span class="filename">{{ asset.filename }}</span>
        </div>
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

defineEmits(['select', 'view-pack'])
</script>

<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: #666;
}

.asset-grid {
  column-width: 220px;
  column-gap: 1rem;
}

.asset-item {
  break-inside: avoid;
  margin-bottom: 1rem;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.asset-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.asset-image-container {
  width: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f8f8;
}

.asset-image-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

.asset-info {
  padding: 0.5rem;
}

.asset-pack {
  display: block;
  font-size: 0.75rem;
  color: #666;
  cursor: pointer;
  margin-bottom: 0.25rem;
}

.asset-pack:hover {
  text-decoration: underline;
  color: #007bff;
}

.filename {
  display: block;
  font-size: 0.875rem;
  word-break: break-all;
}

.no-results {
  color: #666;
  text-align: center;
  padding: 2rem;
}
</style>
