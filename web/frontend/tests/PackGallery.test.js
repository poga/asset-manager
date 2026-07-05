import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PackGallery from '../src/components/PackGallery.vue'

const packs = [
  { name: 'Minifantasy_Ancient_Forests', count: 120, theme: 'Nature', is_3d: false },
  { name: 'KayKit Forest Nature Pack 1.0', count: 80, theme: 'Nature', is_3d: true },
  { name: 'Minifantasy_Dungeon_v2.3', count: 300, theme: 'Dungeons & Caves', is_3d: false },
]

describe('PackGallery', () => {
  it('groups packs into theme sections in canonical order', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const titles = wrapper.findAll('.theme-title').map(t => t.text())
    expect(titles).toEqual(['Nature', 'Dungeons & Caves'])
    const natureCards = wrapper.findAll('.theme-section')[0].findAll('.gallery-card')
    expect(natureCards.length).toBe(2)
  })

  it('omits empty themes', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    expect(wrapper.text()).not.toContain('Sci-fi')
  })

  it('shows 3D badge only for 3d packs', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const badges = wrapper.findAll('.badge-3d')
    expect(badges.length).toBe(1)
  })

  it('emits view-pack with the raw pack name on card click', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    await wrapper.find('.gallery-card').trigger('click')
    expect(wrapper.emitted('view-pack')[0]).toEqual(['Minifantasy_Ancient_Forests'])
  })

  it('renders theme jump chips with counts', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const chips = wrapper.findAll('.chip').map(c => c.text())
    expect(chips[0]).toContain('Nature')
    expect(chips[0]).toContain('2')
  })
})
