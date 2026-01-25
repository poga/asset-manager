<!-- web/frontend/src/components/AssetDetail.vue -->
<template>
  <div class="asset-detail">
    <button class="back-btn" @click="$emit('back')">
      ← Back to results
    </button>

    <div class="detail-content">
      <!-- inline style needed for jsdom test compatibility (scoped CSS not processed) -->
      <img
        :src="`${API_BASE}/image/${asset.id}`"
        :alt="asset.filename"
        class="asset-image"
        :style="{ minWidth: '300px', minHeight: '300px' }"
      />
        <label
          v-if="asset.preview_x !== null && asset.preview_x !== undefined"
          class="preview-override-checkbox"
        >
          <input
            type="checkbox"
            :checked="asset.use_full_image"
            @change="$emit('toggle-preview-override', { assetId: asset.id, useFullImage: !asset.use_full_image })"
          />
          Show full image
        </label>

      <div class="asset-info">
        <h2>{{ asset.filename }}</h2>
        <p class="path">{{ asset.path }}</p>

        <div class="metadata">
          <div v-if="asset.pack">
            <strong>Pack:</strong>
            <span class="pack-link" @click="$emit('view-pack', asset.pack)">{{ asset.pack }}</span>
          </div>
          <div>
            <strong>Size:</strong> {{ asset.width }}x{{ asset.height }}
          </div>
        </div>

        <div class="tags" v-if="asset.tags && asset.tags.length">
          <strong>Tags:</strong>
          <span
            v-for="tag in asset.tags"
            :key="tag"
            class="tag"
            @click="$emit('tag-click', tag)"
          >{{ tag }}</span>
        </div>

        <div class="colors" v-if="asset.colors && asset.colors.length">
          <strong>Colors:</strong>
          <span
            v-for="color in asset.colors"
            :key="color.hex"
            class="color-swatch"
            :style="{ backgroundColor: color.hex }"
            :title="`${color.hex} (${Math.round(color.percentage * 100)}%)`"
          ></span>
        </div>

        <div class="actions">
          <button class="add-cart-btn" @click="$emit('add-to-cart', asset)">
            Add to Cart
          </button>
          <button class="similar-btn" @click="$emit('find-similar', asset.id)">
            Find Similar
          </button>
          <button class="pack-btn" v-if="asset.pack" @click="$emit('view-pack', asset.pack)">
            View Pack
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

defineProps({
  asset: { type: Object, required: true }
})

defineEmits(['back', 'add-to-cart', 'find-similar', 'view-pack', 'tag-click', 'toggle-preview-override'])
</script>

<style scoped>
.asset-detail {
  padding: 1rem;
}

.back-btn {
  background: none;
  border: none;
  color: var(--color-accent);
  cursor: pointer;
  padding: 0.5rem 0;
  font-size: 0.875rem;
  margin-bottom: 1rem;
  transition: color 150ms;
}

.back-btn:hover {
  color: var(--color-accent-hover);
  text-decoration: underline;
}

.detail-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

.asset-image {
  max-width: 100%;
  max-height: 400px;
  min-width: 300px;
  min-height: 300px;
  object-fit: contain;
  image-rendering: pixelated;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
}

.asset-info {
  width: 100%;
  max-width: 500px;
}

h2 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
  color: var(--color-text-primary);
}

.path {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  word-break: break-all;
  margin: 0 0 1rem;
}

.metadata {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.metadata div {
  margin-bottom: 0.25rem;
}

.pack-link {
  color: var(--color-accent);
  cursor: pointer;
  transition: color 150ms;
}

.pack-link:hover {
  color: var(--color-accent-hover);
  text-decoration: underline;
}

.tags {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.tag {
  display: inline-block;
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background-color 150ms;
}

.tag:hover {
  background: var(--color-accent);
  color: white;
}

.colors {
  margin-bottom: 1rem;
  color: var(--color-text-secondary);
}

.color-swatch {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-left: 0.25rem;
  border: 1px solid var(--color-border);
  vertical-align: middle;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.actions button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 150ms;
}

.add-cart-btn {
  background: var(--color-accent);
  color: white;
}

.add-cart-btn:hover {
  background: var(--color-accent-hover);
}

.similar-btn {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}

.similar-btn:hover {
  background: var(--color-border);
}

.pack-btn {
  background: var(--color-success);
  color: white;
}

.pack-btn:hover {
  background: var(--color-success-hover);
}

.preview-override-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
}

.preview-override-checkbox input {
  cursor: pointer;
}
</style>
