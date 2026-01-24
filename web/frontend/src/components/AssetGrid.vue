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
        :class="{ 'in-cart': cartIds.includes(asset.id) }"
        @mouseenter="hoveredId = asset.id"
        @mouseleave="hoveredId = null"
      >
        <div
          class="asset-image-container"
          :style="{ aspectRatio: (asset.preview_x != null && !asset.use_full_image) ? `${asset.preview_width} / ${asset.preview_height}` : `${asset.width} / ${asset.height}` }"
          @click="$emit('select', asset.id)"
        >
          <SpritePreview
            v-if="asset.preview_x !== null && !asset.use_full_image"
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
            :src="`${API_BASE}/image/${asset.id}`"
            :alt="asset.filename"
          />
          <button
            v-if="hoveredId === asset.id && !cartIds.includes(asset.id)"
            class="add-cart-btn"
            @click.stop="$emit('add-to-cart', asset)"
          >+</button>
          <span v-if="cartIds.includes(asset.id)" class="cart-indicator">✓</span>
        </div>
        <div class="asset-info">
          <span
            class="asset-pack"
            v-if="asset.pack"
            @click.stop="$emit('view-pack', asset.pack)"
          >{{ asset.pack }}</span>
          <span class="filename" :title="asset.filename">{{ asset.filename }}</span>
        </div>
      </div>
    </div>
    <div v-else class="no-results">
      No results
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SpritePreview from './SpritePreview.vue'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

defineProps({
  assets: {
    type: Array,
    required: true
  },
  cartIds: {
    type: Array,
    default: () => []
  }
})

defineEmits(['select', 'view-pack', 'add-to-cart'])

const hoveredId = ref(null)
</script>

<style scoped>
.result-count {
  margin-bottom: 0.5rem;
  color: var(--color-text-muted);
}

.asset-grid {
  column-width: 155px;
  column-gap: 1rem;
}

.asset-item {
  break-inside: avoid;
  margin-bottom: 0.75rem;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  transition: box-shadow 150ms, border-color 150ms;
}

.asset-item:hover {
  box-shadow: var(--shadow-card);
  border-color: var(--color-border-emphasis);
}

.asset-image-container {
  width: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-elevated);
  position: relative;
}

.add-cart-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: var(--color-accent);
  color: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 150ms;
}

.add-cart-btn:hover {
  background: var(--color-accent-hover);
}

.cart-indicator {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-success);
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.in-cart {
  border-color: var(--color-success);
}

.asset-image-container img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

.asset-info {
  padding: 0.375rem;
}

.asset-pack {
  display: block;
  font-size: 0.65rem;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-bottom: 0.25rem;
  transition: color 150ms;
}

.asset-pack:hover {
  text-decoration: underline;
  color: var(--color-accent);
}

.filename {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-results {
  color: var(--color-text-muted);
  text-align: center;
  padding: 2rem;
}
</style>
