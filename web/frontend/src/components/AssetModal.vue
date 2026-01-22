<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content">
      <button class="close-btn" @click="$emit('close')">&times;</button>

      <img :src="`/api/image/${asset.id}`" :alt="asset.filename" class="asset-image" />

      <h2>{{ asset.filename }}</h2>
      <p class="path">{{ asset.path }}</p>

      <div class="details">
        <div><strong>Pack:</strong> {{ asset.pack || '-' }}</div>
        <div><strong>Size:</strong> {{ asset.width }}x{{ asset.height }}</div>
        <div v-if="asset.frame_count">
          <strong>Frames:</strong> {{ asset.frame_count }} ({{ asset.frame_width }}x{{ asset.frame_height }})
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

      <button @click="$emit('find-similar', asset.id)" class="find-similar-btn">
        Find Similar
      </button>
      <button @click="$emit('view-pack', asset.pack)" class="view-pack-btn" v-if="asset.pack">
        View Pack
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  asset: {
    type: Object,
    required: true
  }
})

defineEmits(['close', 'find-similar', 'view-pack'])
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
}

.close-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
}

.asset-image {
  max-width: 100%;
  max-height: 300px;
  object-fit: contain;
  display: block;
  margin: 0 auto 1rem;
}

h2 {
  margin: 0 0 0.5rem;
}

.path {
  color: #666;
  font-size: 0.875rem;
  word-break: break-all;
  margin-bottom: 1rem;
}

.details {
  margin-bottom: 1rem;
}

.tags {
  margin-bottom: 1rem;
}

.tag {
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
}

.find-similar-btn {
  background: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.find-similar-btn:hover {
  background: #0056b3;
}

.view-pack-btn {
  background: #28a745;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  margin-left: 0.5rem;
}

.view-pack-btn:hover {
  background: #218838;
}
</style>
