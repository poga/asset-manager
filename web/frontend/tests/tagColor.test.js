import { describe, it, expect } from 'vitest'
import { tagHue } from '../src/utils/tagColor.js'

describe('tagHue', () => {
  it('is deterministic for the same tag', () => {
    expect(tagHue('forest')).toBe(tagHue('forest'))
  })

  it('only returns the 12 snapped hues and spreads across them', () => {
    const allowed = new Set(Array.from({ length: 12 }, (_, i) => i * 30))
    const seen = new Set()
    const tags = ['forest', 'weapons', 'ui', 'tileset', 'rpg', 'nature',
                  'sci-fi', 'characters', 'props', 'audio', 'fx', 'terrain']
    for (const t of tags) {
      const h = tagHue(t)
      expect(allowed.has(h)).toBe(true)
      seen.add(h)
    }
    expect(seen.size).toBeGreaterThan(1)
  })
})
