<template>
  <canvas
    ref="canvas"
    :width="displaySize"
    :height="displaySize"
    class="sprite-canvas"
  />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  assetId: {
    type: Number,
    required: true
  },
  frames: {
    type: Array,
    required: true
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
let animationInterval = null
let currentFrame = 0
let spriteImage = null

const loadImage = () => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = `/api/image/${props.assetId}`
  })
}

const drawFrame = () => {
  if (!canvas.value || !spriteImage || !props.frames.length) return

  const ctx = canvas.value.getContext('2d')
  const frame = props.frames[currentFrame]

  // Clear canvas
  ctx.clearRect(0, 0, displaySize, displaySize)

  // Calculate scale to fit frame in display area
  const scale = Math.min(displaySize / frame.width, displaySize / frame.height)
  const scaledWidth = frame.width * scale
  const scaledHeight = frame.height * scale
  const offsetX = (displaySize - scaledWidth) / 2
  const offsetY = (displaySize - scaledHeight) / 2

  // Disable smoothing for pixel art
  ctx.imageSmoothingEnabled = false

  // Draw current frame
  ctx.drawImage(
    spriteImage,
    frame.x, frame.y, frame.width, frame.height,
    offsetX, offsetY, scaledWidth, scaledHeight
  )
}

const startAnimation = async () => {
  try {
    spriteImage = await loadImage()
    drawFrame()

    if (props.frames.length > 1) {
      animationInterval = setInterval(() => {
        currentFrame = (currentFrame + 1) % props.frames.length
        drawFrame()
      }, 120)
    }
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

const stopAnimation = () => {
  if (animationInterval) {
    clearInterval(animationInterval)
    animationInterval = null
  }
}

onMounted(startAnimation)
onUnmounted(stopAnimation)

watch(() => props.assetId, () => {
  stopAnimation()
  currentFrame = 0
  startAnimation()
})
</script>

<style scoped>
.sprite-canvas {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
</style>
