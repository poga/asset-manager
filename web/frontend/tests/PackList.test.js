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
    const rows = wrapper.findAll('.pack-row')
    const iconRow = rows.find(row => row.text().includes('icons'))
    expect(iconRow.classes()).toContain('selected')
  })

  it('emits update:selectedPacks when card clicked', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const row = wrapper.find('.pack-row')
    await row.trigger('click')
    expect(wrapper.emitted('update:selectedPacks')).toBeTruthy()
  })

  it('search input is always visible', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    expect(wrapper.find('.pack-search').exists()).toBe(true)
  })

  it('renders card grid when expanded', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], panelState: 'expanded' }
    })
    expect(wrapper.findAll('.pack-card').length).toBe(3)
    expect(wrapper.findAll('.pack-row').length).toBe(0)
  })

  it('select all button selects all packs', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], selectionMode: 'multi' }
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
    const searchInput = wrapper.find('.pack-search')
    await searchInput.setValue('icon')
    expect(wrapper.text()).toContain('icons')
    expect(wrapper.text()).not.toContain('monsters')
  })

  it('single mode: clicking a pack replaces selection', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'single' }
    })
    const spritesRow = wrapper.findAll('.pack-row').find(row => row.text().includes('sprites'))
    await spritesRow.trigger('click')
    const emitted = wrapper.emitted('update:selectedPacks')
    expect(emitted[0][0]).toEqual(['sprites'])
  })

  it('single mode: clicking selected pack emits view-pack to navigate', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'single' }
    })
    const iconsRow = wrapper.findAll('.pack-row').find(row => row.text().includes('icons'))
    await iconsRow.trigger('click')
    // Should emit view-pack, NOT deselect
    const viewPackEmitted = wrapper.emitted('view-pack')
    expect(viewPackEmitted).toBeTruthy()
    expect(viewPackEmitted[0][0]).toBe('icons')
    // Should NOT emit update:selectedPacks (no deselection)
    expect(wrapper.emitted('update:selectedPacks')).toBeFalsy()
  })

  it('multi mode: clicking toggles pack in/out of selection', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'], selectionMode: 'multi' }
    })
    const spritesRow = wrapper.findAll('.pack-row').find(row => row.text().includes('sprites'))
    await spritesRow.trigger('click')
    const emitted = wrapper.emitted('update:selectedPacks')
    expect(emitted[0][0]).toEqual(['icons', 'sprites'])
  })

  it('mode toggle button switches between single and multi', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], selectionMode: 'single' }
    })
    const modeBtn = wrapper.find('[data-testid="mode-toggle"]')
    expect(modeBtn.exists()).toBe(true)
    await modeBtn.trigger('click')
    const emitted = wrapper.emitted('update:selectionMode')
    expect(emitted[0][0]).toBe('multi')
  })

  it('single mode: hides Select all button', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], selectionMode: 'single' }
    })
    const selectAllBtn = wrapper.findAll('.action-btn').find(btn => btn.text() === 'Select all')
    expect(selectAllBtn).toBeUndefined()
  })

  it('multi mode: shows Select all button', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [], selectionMode: 'multi' }
    })
    const selectAllBtn = wrapper.findAll('.action-btn').find(btn => btn.text() === 'Select all')
    expect(selectAllBtn).toBeDefined()
  })
})
