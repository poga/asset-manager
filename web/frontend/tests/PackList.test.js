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

  it('shows checkbox checked for selected packs', () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: ['icons'] }
    })
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const iconCheckbox = checkboxes.find(cb =>
      cb.element.closest('.pack-item')?.textContent?.includes('icons')
    )
    expect(iconCheckbox.element.checked).toBe(true)
  })

  it('emits update:selectedPacks when checkbox clicked', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(true)
    expect(wrapper.emitted('update:selectedPacks')).toBeTruthy()
  })

  it('select all checkbox selects all packs', async () => {
    const wrapper = mount(PackList, {
      props: { packs: mockPacks, selectedPacks: [] }
    })
    const selectAll = wrapper.find('.select-all input')
    await selectAll.setValue(true)
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
