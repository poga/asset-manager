<template>
  <div class="board-view">
    <div class="board-header">
      <input
        v-if="renaming"
        class="board-name-input"
        v-model="draftName"
        @keyup.enter="commitRename"
        @keyup.escape="renaming = false"
        v-focus
      />
      <h2 v-else class="board-name">{{ board.name }}</h2>
      <div class="board-actions">
        <button data-testid="add-images" class="board-btn" :disabled="uploading" @click="pick">+ Add images</button>
        <button class="board-btn" @click="startRename">Rename</button>
        <button class="board-btn danger" @click="removeBoard">Delete</button>
      </div>
      <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="onPick" />
    </div>

    <div v-if="uploading" data-testid="upload-progress" class="upload-progress">
      <div class="upload-progress-label">
        <span v-if="processing">Processing {{ fileCount }} {{ fileCount === 1 ? 'file' : 'files' }}…</span>
        <span v-else>Uploading {{ fileCount }} {{ fileCount === 1 ? 'file' : 'files' }}…</span>
        <span v-if="!processing" class="upload-progress-pct">{{ progress }}%</span>
      </div>
      <div class="upload-bar">
        <div class="upload-bar-fill" :class="{ processing }" :style="processing ? {} : { width: progress + '%' }"></div>
      </div>
    </div>

    <div v-if="errorMsg" data-testid="upload-error" class="upload-error">
      <span>⚠ {{ errorMsg }}</span>
      <button class="upload-error-dismiss" @click="errorMsg = ''">Dismiss</button>
    </div>

    <div
      data-testid="dropzone"
      class="dropzone"
      :class="{ over: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <AssetGrid
        :assets="assets"
        :cart-ids="cartIds"
        :loading="loading"
        @select="$emit('select', $event)"
        @view-pack="$emit('view-pack', $event)"
        @add-to-cart="$emit('add-to-cart', $event)"
        @load-more="$emit('load-more')"
      />
      <p v-if="!assets.length" class="empty-hint">Drop images here or use “Add images”.</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AssetGrid from './AssetGrid.vue'
import { uploadImages, renameBoard, deleteBoard } from '../api/boards.js'

const props = defineProps({
  board: { type: Object, required: true },
  assets: { type: Array, required: true },
  cartIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['select', 'add-to-cart', 'load-more', 'view-pack', 'changed', 'deleted'])

const vFocus = { mounted: el => el.focus() }
const fileInput = ref(null)
const dragOver = ref(false)
const renaming = ref(false)
const draftName = ref('')

const uploading = ref(false)
const processing = ref(false)
const progress = ref(0)
const fileCount = ref(0)
const errorMsg = ref('')

function pick() { fileInput.value?.click() }

async function upload(files) {
  if (!files || !files.length || uploading.value) return
  errorMsg.value = ''
  uploading.value = true
  processing.value = false
  progress.value = 0
  fileCount.value = files.length
  try {
    await uploadImages(props.board.id, files, p => {
      progress.value = p
      processing.value = p >= 100
    })
    emit('changed')
  } catch (e) {
    errorMsg.value = e.message || 'Upload failed'
  } finally {
    uploading.value = false
    processing.value = false
  }
}

function onPick(e) {
  upload(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  dragOver.value = false
  upload(e.dataTransfer?.files)
}

function startRename() {
  draftName.value = props.board.name
  renaming.value = true
}

async function commitRename() {
  const name = draftName.value.trim()
  renaming.value = false
  if (name && name !== props.board.name) {
    await renameBoard(props.board.id, name)
    emit('changed')
  }
}

async function removeBoard() {
  await deleteBoard(props.board.id)
  emit('deleted')
}
</script>

<style scoped>
.board-view { display: flex; flex-direction: column; height: 100%; }
.board-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; flex-wrap: wrap;
}
.board-name { margin: 0; font-size: 1.375rem; font-weight: 700; }
.board-name-input {
  font-size: 1.25rem; padding: 0.25rem 0.5rem;
  border: 1px solid var(--color-accent); border-radius: 6px;
  background: var(--color-bg-surface); color: var(--color-text-primary);
}
.board-actions { display: flex; gap: 0.5rem; margin-left: auto; }
.board-btn {
  border: 1px solid var(--color-border); background: var(--color-bg-surface);
  color: var(--color-text-secondary); border-radius: 6px; padding: 0.375rem 0.75rem;
  cursor: pointer; font-size: 0.8125rem;
}
.board-btn:hover { border-color: var(--color-accent); color: var(--color-text-primary); }
.board-btn.danger:hover { border-color: var(--color-danger); color: var(--color-danger); }
.upload-progress { padding: 0 1.25rem 0.75rem; }
.upload-progress-label {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 0.8125rem; color: var(--color-text-secondary); margin-bottom: 0.375rem;
}
.upload-progress-pct { font-variant-numeric: tabular-nums; color: var(--color-text-primary); }
.upload-bar {
  height: 6px; border-radius: 3px; overflow: hidden;
  background: var(--color-border);
}
.upload-bar-fill {
  height: 100%; background: var(--color-accent);
  border-radius: 3px; transition: width 0.15s ease;
}
.upload-bar-fill.processing {
  width: 40%; animation: upload-indeterminate 1s ease-in-out infinite;
}
@keyframes upload-indeterminate {
  0% { margin-left: -40%; }
  100% { margin-left: 100%; }
}
.upload-error {
  display: flex; align-items: center; gap: 0.75rem;
  margin: 0 1.25rem 0.75rem; padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-danger); border-radius: 6px;
  color: var(--color-danger); font-size: 0.8125rem;
}
.upload-error-dismiss {
  margin-left: auto; border: none; background: transparent;
  color: var(--color-danger); cursor: pointer; text-decoration: underline; font-size: 0.8125rem;
}
.board-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.dropzone { flex: 1; overflow-y: auto; position: relative; }
.dropzone.over { outline: 2px dashed var(--color-accent); outline-offset: -6px; }
.empty-hint { text-align: center; color: var(--color-text-muted); padding: 2rem; }
</style>
