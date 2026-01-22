<!-- web/frontend/src/components/Cart.vue -->
<template>
  <div class="cart">
    <div class="cart-header">
      <span class="cart-title">Cart</span>
    </div>

    <button
      class="download-btn"
      :disabled="items.length === 0"
      @click="$emit('download')"
    >
      <span class="download-icon">📥</span>
      <span>Download ZIP</span>
    </button>

    <div class="items-header">
      <span>Items</span>
      <span class="item-count" v-if="items.length > 0">{{ items.length }}</span>
    </div>

    <div class="cart-items" v-if="items.length > 0">
      <div
        v-for="item in items"
        :key="item.id"
        class="cart-item"
      >
        <img
          :src="`/api/image/${item.id}`"
          :alt="item.filename"
          class="item-thumbnail"
        />
        <div class="item-info">
          <span class="item-filename">{{ item.filename }}</span>
          <span class="item-pack">{{ item.pack }}</span>
        </div>
        <button class="remove-btn" @click="$emit('remove', item.id)">×</button>
      </div>
    </div>

    <div class="empty-state" v-else>
      <p>No items in cart</p>
      <p class="hint">Hover over assets and click + to add</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true }
})

defineEmits(['remove', 'download'])
</script>

<style scoped>
.cart {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.cart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
}

.cart-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text-primary);
}

.download-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin: 1rem;
  padding: 1rem;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background-color 150ms;
}

.download-btn:hover:not(:disabled) {
  background: var(--color-accent-hover);
}

.download-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.download-icon {
  font-size: 1.25rem;
}

.items-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
}

.item-count {
  background: var(--color-accent-light);
  color: var(--color-accent-hover);
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
  font-size: 0.75rem;
}

.cart-items {
  flex: 1;
  overflow-y: auto;
}

.cart-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  transition: background-color 150ms;
}

.cart-item:hover {
  background: var(--color-bg-elevated);
}

.item-thumbnail {
  width: 40px;
  height: 40px;
  object-fit: contain;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  image-rendering: pixelated;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-filename {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-pack {
  display: block;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.remove-btn {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0.25rem;
  transition: color 150ms;
}

.remove-btn:hover {
  color: var(--color-danger);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  text-align: center;
  padding: 2rem;
}

.empty-state p {
  margin: 0.25rem 0;
}

.hint {
  font-size: 0.75rem;
  color: var(--color-accent);
}
</style>
