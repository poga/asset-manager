<!-- web/frontend/src/components/AssetDetail.vue -->
<template>
  <div class="asset-detail">
    <button class="back-btn" @click="$emit('back')">
      ← Back to results
    </button>

    <div class="detail-content">
      <img
        :src="`/api/image/${asset.id}`"
        :alt="asset.filename"
        class="asset-image"
      />

      <div class="asset-info">
        <h2>{{ asset.filename }}</h2>
        <p class="path">{{ asset.path }}</p>

        <div class="metadata">
          <div v-if="asset.pack">
            <strong>Pack:</strong> {{ asset.pack }}
          </div>
          <div>
            <strong>Size:</strong> {{ asset.width }}x{{ asset.height }}
          </div>
        </div>

        <div class="tags" v-if="asset.tags && asset.tags.length">
          <strong>Tags:</strong>
          <span v-for="tag in asset.tags" :key="tag" class="tag">{{ tag }}</span>
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
defineProps({
  asset: { type: Object, required: true }
})

defineEmits(['back', 'add-to-cart', 'find-similar', 'view-pack'])
</script>

<style scoped>
.asset-detail {
  padding: 1rem;
}

.back-btn {
  background: none;
  border: none;
  color: #007bff;
  cursor: pointer;
  padding: 0.5rem 0;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.back-btn:hover {
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
  object-fit: contain;
  image-rendering: pixelated;
  background: #f8f8f8;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}

.asset-info {
  width: 100%;
  max-width: 500px;
}

h2 {
  margin: 0 0 0.5rem;
  font-size: 1.25rem;
}

.path {
  color: #666;
  font-size: 0.875rem;
  word-break: break-all;
  margin: 0 0 1rem;
}

.metadata {
  margin-bottom: 1rem;
}

.metadata div {
  margin-bottom: 0.25rem;
}

.tags {
  margin-bottom: 1rem;
}

.tag {
  display: inline-block;
  background: #e0e0e0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
}

.colors {
  margin-bottom: 1rem;
}

.color-swatch {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-left: 0.25rem;
  border: 1px solid #ccc;
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
}

.add-cart-btn {
  background: #007bff;
  color: white;
}

.add-cart-btn:hover {
  background: #0056b3;
}

.similar-btn {
  background: #6c757d;
  color: white;
}

.similar-btn:hover {
  background: #545b62;
}

.pack-btn {
  background: #28a745;
  color: white;
}

.pack-btn:hover {
  background: #218838;
}
</style>
