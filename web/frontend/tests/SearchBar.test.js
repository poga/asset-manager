import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../src/components/SearchBar.vue'

const filters = {
  packs: [],
  tags: [
    { name: 'goblin', count: 120 },
    { name: 'gold', count: 40 },
    { name: 'dragon-gold', count: 90 },
    { name: 'idle', count: 300 },
  ],
}

function lastSearch(wrapper) {
  const emitted = wrapper.emitted('search')
  return emitted[emitted.length - 1][0]
}

describe('SearchBar smart box', () => {
  it('emits only q and tag', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('sword')
    const params = lastSearch(wrapper)
    expect(Object.keys(params).sort()).toEqual(['q', 'tag'])
    expect(params.q).toBe('sword')
  })

  it('renders no color or add-tag dropdowns', () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    expect(wrapper.find('[data-filter="color"]').exists()).toBe(false)
    expect(wrapper.find('[data-filter="tag"]').exists()).toBe(false)
  })

  it('suggests prefix matches before substring matches, count-ranked', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('go')
    const names = wrapper.findAll('.suggestion').map(s => s.find('.suggestion-name').text())
    // prefix: goblin(120), gold(40); substring: dragon-gold(90)
    expect(names).toEqual(['goblin', 'gold', 'dragon-gold'])
    expect(wrapper.findAll('.suggestion-count')[0].text()).toBe('120')
  })

  it('click on a suggestion adds a chip and clears the input', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    expect(lastSearch(wrapper)).toEqual({ q: null, tag: ['goblin'] })
    expect(wrapper.find('input').element.value).toBe('')
    expect(wrapper.find('.tag').text()).toContain('goblin')
  })

  it('arrow down + enter adds the highlighted suggestion', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'ArrowDown' })
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastSearch(wrapper).tag).toEqual(['gold'])
  })

  it('plain enter with no highlight adds no tag', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastSearch(wrapper).tag).toEqual([])
    expect(lastSearch(wrapper).q).toBe('go')
  })

  it('escape closes the suggestion dropdown', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    expect(wrapper.find('.suggestion').exists()).toBe(true)
    await input.trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.suggestion').exists()).toBe(false)
  })

  it('already-chosen tags are not suggested again', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    await input.setValue('gob')
    const names = wrapper.findAll('.suggestion').map(s => s.find('.suggestion-name').text())
    expect(names).not.toContain('goblin')
  })

  it('chips remove on click and re-emit', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    await wrapper.find('.tag').trigger('click')
    expect(lastSearch(wrapper).tag).toEqual([])
  })

  it('clear() resets query and tags', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    await wrapper.find('input').setValue('gob')
    await wrapper.find('.suggestion').trigger('mousedown')
    wrapper.vm.clear()
    await wrapper.vm.$nextTick()
    expect(lastSearch(wrapper)).toEqual({ q: null, tag: [] })
  })

  it('degrades to plain search when vocabulary is empty', async () => {
    const wrapper = mount(SearchBar, { props: { filters: { packs: [], tags: [] } } })
    await wrapper.find('input').setValue('goblin')
    expect(wrapper.find('.suggestion').exists()).toBe(false)
    expect(lastSearch(wrapper).q).toBe('goblin')
  })

  it('outside click then Enter does not add a stale highlight', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    const input = wrapper.find('input')
    await input.setValue('go')
    await input.trigger('keydown', { key: 'ArrowDown' })
    document.body.click()
    await wrapper.vm.$nextTick()
    await input.trigger('keydown', { key: 'Enter' })
    expect(lastSearch(wrapper).tag).toEqual([])
  })

  it('addTagExternal adds a chip and ignores a duplicate call', async () => {
    const wrapper = mount(SearchBar, { props: { filters } })
    wrapper.vm.addTagExternal('goblin')
    await wrapper.vm.$nextTick()
    expect(lastSearch(wrapper).tag).toContain('goblin')
    expect(wrapper.emitted('search').length).toBe(1)

    wrapper.vm.addTagExternal('goblin')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('search').length).toBe(1)
    expect(lastSearch(wrapper).tag).toEqual(['goblin'])
  })
})
