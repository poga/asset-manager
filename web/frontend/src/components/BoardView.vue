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
        <button data-testid="add-images" class="board-btn" @click="pick">+ Add images</button>
        <button class="board-btn" @click="startRename">Rename</button>
        <button class="board-btn danger" @click="removeBoard">Delete</button>
      </div>
      <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="onPick" />
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

function pick() { fileInput.value?.click() }

async function upload(files) {
  if (!files || !files.length) return
  await uploadImages(props.board.id, files)
  emit('changed')
}

function onPick(e) { upload(e.target.files) }

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
.dropzone { flex: 1; overflow-y: auto; position: relative; }
.dropzone.over { outline: 2px dashed var(--color-accent); outline-offset: -6px; }
.empty-hint { text-align: center; color: var(--color-text-muted); padding: 2rem; }
</style>
