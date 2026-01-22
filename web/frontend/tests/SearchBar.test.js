// web/frontend/tests/SearchBar.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

describe('SearchBar', () => {
  const mockFilters = {
    packs: ['icons', 'sprites'],
    tags: ['character', 'ui'],
    colors: ['red', 'blue', 'green'],
  }

  it('renders search input', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('renders color dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="color"]').exists()).toBe(true)
  })

  it('does not render pack dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="pack"]').exists()).toBe(false)
  })

  it('emits search on input', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    await wrapper.find('input[type="text"]').setValue('hero')
    expect(wrapper.emitted('search')).toBeTruthy()
  })

  it('renders tag dropdown', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(wrapper.find('select[data-filter="tag"]').exists()).toBe(true)
  })

  it('adds and displays tags', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    const tagSelect = wrapper.find('select[data-filter="tag"]')
    await tagSelect.setValue('character')
    expect(wrapper.text()).toContain('character')
  })

  it('removes tag when clicked', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    const tagSelect = wrapper.find('select[data-filter="tag"]')
    await tagSelect.setValue('character')
    await wrapper.find('.tag').trigger('click')
    expect(wrapper.text()).not.toContain('character ×')
  })

  it('exposes addTagExternal method', () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    expect(typeof wrapper.vm.addTagExternal).toBe('function')
  })

  it('addTagExternal adds tag and emits search', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    wrapper.vm.addTagExternal('sword')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('search')).toBeTruthy()
    expect(wrapper.emitted('search')[0][0].tag).toContain('sword')
  })

  it('addTagExternal does not add duplicate tags', async () => {
    const wrapper = mount(SearchBar, {
      props: { filters: mockFilters }
    })
    wrapper.vm.addTagExternal('sword')
    wrapper.vm.addTagExternal('sword')
    await wrapper.vm.$nextTick()
    const lastEmit = wrapper.emitted('search').slice(-1)[0][0]
    expect(lastEmit.tag.filter(t => t === 'sword').length).toBe(1)
  })
})
