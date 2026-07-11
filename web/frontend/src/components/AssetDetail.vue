<!-- web/frontend/src/components/AssetDetail.vue -->
<template>
  <div class="asset-detail">
    <button class="back-btn" @click="$emit('back')">
      ← Back to results
    </button>

    <div class="detail-content">
      <ModelViewer
        v-if="asset.kind === 'model' || asset.kind === 'animation_bundle'"
        :asset-id="asset.id"
        :filename="asset.filename"
        :api-base="API_BASE"
      />
      <div v-else-if="asset.kind === 'file'" class="file-panel">
        <span class="file-ext-big">.{{ fileExt }}</span>
        <span class="file-panel-name">{{ asset.filename }}</span>
        <span class="file-panel-size" v-if="asset.file_size != null">{{ formatSize(asset.file_size) }}</span>
      </div>
      <!-- inline style needed for jsdom test compatibility (scoped CSS not processed) -->
      <img
        v-else
        :src="`${API_BASE}/image/${asset.id}`"
        :alt="asset.filename"
        class="asset-image"
        :style="{ minWidth: '300px', minHeight: '300px' }"
      />
        <label
          v-if="(asset.kind === 'image' || !asset.kind) && asset.preview_x !== null && asset.preview_x !== undefined"
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
          <div v-if="asset.width != null">
            <strong>Size:</strong> {{ asset.width }}x{{ asset.height }}
          </div>
          <div v-if="asset.file_size != null">
            <strong>File size:</strong> {{ formatSize(asset.file_size) }}
          </div>
        </div>

        <div class="tags" v-if="asset.tags && asset.tags.length">
          <strong>Tags:</strong>
          <span
            v-for="tag in asset.tags"
            :key="tag"
            class="tag"
            :style="{ '--tag-hue': tagHue(tag) }"
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
          <a
            v-if="asset.kind !== 'file'"
            :href="`${API_BASE}/image/${asset.id}`"
            target="_blank"
            rel="noopener noreferrer"
            class="full-size-btn"
          >
            Full Size
          </a>
          <a
            v-if="asset.kind === 'font' || asset.kind === 'file'"
            :href="`${API_BASE}/asset/${asset.id}/file?download=true`"
            class="download-btn"
          >
            Download
          </a>
        </div>

        <div v-if="asset.is_board" class="board-image-actions">
          <button data-testid="set-cover" class="board-btn" @click="makeCover">Set as cover</button>
          <button class="board-btn danger" @click="removeImage">Remove</button>
          <div class="image-tags">
            <span v-for="t in localTags" :key="t" class="tag-chip">
              {{ t }}<button class="tag-remove" @click="dropTag(t)">×</button>
            </span>
            <input
              v-model="newTag"
              class="tag-input"
              placeholder="+ tag"
              @keyup.enter="addTag"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ModelViewer from './ModelViewer.vue'
import { tagHue } from '../utils/tagColor.js'
import { setCover, deleteImage, addImageTag, removeImageTag } from '../api/boards.js'
import { formatSize } from '../utils/fileSize.js'

const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

const props = defineProps({
  asset: { type: Object, required: true }
})

const emit = defineEmits([
  'back', 'add-to-cart', 'find-similar', 'view-pack', 'tag-click', 'toggle-preview-override',
  'board-image-changed', 'board-image-removed'
])

const localTags = ref([...(props.asset.tags || [])])
const newTag = ref('')

const fileExt = computed(() => {
  const parts = props.asset.filename.split('.')
  return parts.length > 1 ? parts.pop().toUpperCase() : ''
})

watch(() => props.asset, a => { localTags.value = [...(a.tags || [])] })

async function makeCover() {
  await setCover(props.asset.board_id, props.asset.id)
  emit('board-image-changed')
}

async function removeImage() {
  await deleteImage(props.asset.id)
  emit('board-image-removed')
}

async function addTag() {
  const t = newTag.value.trim()
  newTag.value = ''
  if (!t) return
  const res = await addImageTag(props.asset.id, t)
  localTags.value = res.tags
  emit('board-image-changed')
}

async function dropTag(t) {
  const res = await removeImageTag(props.asset.id, t)
  localTags.value = res.tags
  emit('board-image-changed')
}
</script>

<style scoped>
.asset-detail {
  padding: 1rem 1.25rem 2rem;
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
  background: hsl(var(--tag-hue, 0), 50%, 92%);
  color: hsl(var(--tag-hue, 0), 40%, 30%);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 0.25rem;
  font-size: 0.875rem;
  cursor: pointer;
  transition: filter 150ms;
}

[data-theme='dark'] .tag {
  background: hsl(var(--tag-hue, 0), 30%, 24%);
  color: hsl(var(--tag-hue, 0), 55%, 78%);
}

.tag:hover {
  filter: brightness(0.95);
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

.full-size-btn {
  display: inline-block;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-size: 0.875rem;
  text-decoration: none;
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: background-color 150ms;
}

.full-size-btn:hover {
  background: var(--color-border);
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

.board-image-actions { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.75rem; }
.board-image-actions .board-btn {
  border: 1px solid var(--color-border); background: var(--color-bg-surface);
  color: var(--color-text-secondary); border-radius: 6px; padding: 0.375rem 0.75rem;
  cursor: pointer; font-size: 0.8125rem; align-self: flex-start;
}
.board-image-actions .board-btn.danger:hover { border-color: var(--color-danger); color: var(--color-danger); }
.image-tags { display: flex; flex-wrap: wrap; gap: 0.375rem; align-items: center; }

.file-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-width: 300px;
  min-height: 200px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 2rem 3rem;
}

.file-ext-big {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary);
}

.file-panel-name {
  color: var(--color-text-primary);
  word-break: break-all;
}

.file-panel-size {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.download-btn {
  display: inline-block;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-size: 0.875rem;
  text-decoration: none;
  background: var(--color-accent);
  color: white;
  cursor: pointer;
  transition: background-color 150ms;
}

.download-btn:hover {
  background: var(--color-accent-hover);
}
</style>
