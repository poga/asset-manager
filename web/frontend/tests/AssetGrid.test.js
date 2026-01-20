import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetGrid from '../src/components/AssetGrid.vue'

const mockAssets = [
  { id: 1, filename: 'goblin.png', path: '/assets/goblin.png', width: 64, height: 64 },
  { id: 2, filename: 'orc.png', path: '/assets/orc.png', width: 128, height: 128 },
]

describe('AssetGrid', () => {
  it('renders grid of assets', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.findAll('.asset-item').length).toBe(2)
  })

  it('shows asset filename', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.text()).toContain('goblin.png')
  })

  it('shows result count', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.text()).toContain('2')
  })

  it('emits select event on click', async () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    await wrapper.find('.asset-item').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0]).toEqual([1])
  })

  it('shows empty message when no assets', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: [] }
    })
    expect(wrapper.text()).toContain('No results')
  })
})
