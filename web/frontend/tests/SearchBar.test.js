import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

describe('SearchBar', () => {
  it('renders search input', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: [] } }
    })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('emits search event on input', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: [] } }
    })
    await wrapper.find('input[type="text"]').setValue('goblin')
    expect(wrapper.emitted('search')).toBeTruthy()
    expect(wrapper.emitted('search')[0]).toEqual([{ q: 'goblin', tag: [], color: null, pack: null, type: null }])
  })

  it('renders pack filter dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: ['creatures', 'items'], tags: [], colors: [] } }
    })
    const select = wrapper.find('select[data-filter="pack"]')
    expect(select.exists()).toBe(true)
    expect(select.findAll('option').length).toBe(3) // empty + 2 packs
  })

  it('emits search with pack filter', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: ['creatures'], tags: [], colors: [] } }
    })
    await wrapper.find('select[data-filter="pack"]').setValue('creatures')
    const events = wrapper.emitted('search')
    const lastEvent = events[events.length - 1][0]
    expect(lastEvent.pack).toBe('creatures')
  })

  it('renders color filter dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: { packs: [], tags: [], colors: ['red', 'green', 'blue'] } }
    })
    const select = wrapper.find('select[data-filter="color"]')
    expect(select.exists()).toBe(true)
  })
})
