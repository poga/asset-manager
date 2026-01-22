import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PackList from '../src/components/PackList.vue'

describe('PackList', () => {
  const mockPacks = [
    { name: 'icons', count: 124 },
    { name: 'sprites', count: 89 },
    { name: 'monsters', count: 45 },
  ]

  it('renders pack list with counts', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    expect(wrapper.text()).toContain('icons')
    expect(wrapper.text()).toContain('124')
    expect(wrapper.text()).toContain('sprites')
  })

  it('shows selected class for selected packs', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'] }
    })
    const cards = wrapper.findAll('.pack-card')
    const iconCard = cards.find(card => card.text().includes('icons'))
    expect(iconCard.classes()).toContain('selected')
  })

  it('emits update:selectedPacks when card clicked', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const card = wrapper.find('.pack-card')
    await card.trigger('click')
    expect(wrapper.emitted('update:selectedPacks')).toBeTruthy()
  })

  it('select all button selects all packs', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const selectAllBtn = wrapper.findAll('.action-btn').find(btn => btn.text() === 'Select all')
    await selectAllBtn.trigger('click')
    const emitted = wrapper.emitted('update:selectedPacks')
    expect(emitted[0][0]).toEqual(['icons', 'sprites', 'monsters'])
  })

  it('filters packs when searching', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    // Click the search button to reveal the search input
    await wrapper.find('.icon-btn').trigger('click')
    const searchInput = wrapper.find('.pack-search')
    await searchInput.setValue('icon')
    expect(wrapper.text()).toContain('icons')
    expect(wrapper.text()).not.toContain('monsters')
  })
})
