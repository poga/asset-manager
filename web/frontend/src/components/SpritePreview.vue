<template>
  <canvas
    ref="canvas"
    :width="displaySize"
    :height="displaySize"
    class="sprite-canvas"
  />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  assetId: {
    type: Number,
    required: true
  },
  previewX: {
    type: Number,
    default: null
  },
  previewY: {
    type: Number,
    default: null
  },
  previewWidth: {
    type: Number,
    default: null
  },
  previewHeight: {
    type: Number,
    default: null
  },
  width: {
    type: Number,
    required: true
  },
  height: {
    type: Number,
    required: true
  }
})

const canvas = ref(null)
const displaySize = 100

const loadImage = () => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = `/api/image/${props.assetId}`
  })
}

const drawPreview = async () => {
  if (!canvas.value) return

  try {
    const img = await loadImage()
    const ctx = canvas.value.getContext('2d')

    // Clear canvas
    ctx.clearRect(0, 0, displaySize, displaySize)

    // Determine source region
    const sx = props.previewX ?? 0
    const sy = props.previewY ?? 0
    const sw = props.previewWidth ?? props.width
    const sh = props.previewHeight ?? props.height

    // Calculate scale to fit in display area
    const scale = Math.min(displaySize / sw, displaySize / sh)
    const scaledWidth = sw * scale
    const scaledHeight = sh * scale
    const offsetX = (displaySize - scaledWidth) / 2
    const offsetY = (displaySize - scaledHeight) / 2

    // Disable smoothing for pixel art
    ctx.imageSmoothingEnabled = false

    // Draw preview region
    ctx.drawImage(
      img,
      sx, sy, sw, sh,
      offsetX, offsetY, scaledWidth, scaledHeight
    )
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

onMounted(drawPreview)

watch(() => props.assetId, drawPreview)
</script>

<style scoped>
.sprite-canvas {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
</style>
