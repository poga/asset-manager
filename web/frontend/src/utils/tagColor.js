// deterministic hue per tag, snapped to 12 steps so tags stay distinguishable
const TAG_HUE_STEPS = 12

export function tagHue(tag) {
  let h = 0
  for (let i = 0; i < tag.length; i++) {
    h = (h << 5) - h + tag.charCodeAt(i)
    h |= 0
  }
  const step = ((h % TAG_HUE_STEPS) + TAG_HUE_STEPS) % TAG_HUE_STEPS
  return step * (360 / TAG_HUE_STEPS)
}
