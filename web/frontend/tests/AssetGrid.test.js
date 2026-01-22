import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetGrid from '../src/components/AssetGrid.vue'

const mockAssets = [
  { id: 1, filename: 'goblin.png', path: '/assets/goblin.png', width: 64, height: 64, pack: 'fantasy-pack' },
  { id: 2, filename: 'orc.png', path: '/assets/orc.png', width: 128, height: 128, pack: 'monster-pack' },
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
    await wrapper.find('.asset-image-container').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0]).toEqual([1])
  })

  it('shows empty message when no assets', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: [] }
    })
    expect(wrapper.text()).toContain('No results')
  })

  it('shows pack name on asset cards', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    expect(wrapper.text()).toContain('fantasy-pack')
    expect(wrapper.text()).toContain('monster-pack')
  })

  it('emits view-pack event when pack name clicked', async () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    await wrapper.find('.asset-pack').trigger('click')
    expect(wrapper.emitted('view-pack')).toBeTruthy()
    expect(wrapper.emitted('view-pack')[0]).toEqual(['fantasy-pack'])
  })

  it('shows add-to-cart button on hover', async () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets, cartIds: [] }
    })
    const item = wrapper.find('.asset-item')
    await item.trigger('mouseenter')
    expect(wrapper.find('.add-cart-btn').exists()).toBe(true)
  })

  it('emits add-to-cart when button clicked', async () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets, cartIds: [] }
    })
    const item = wrapper.find('.asset-item')
    await item.trigger('mouseenter')
    await wrapper.find('.add-cart-btn').trigger('click')
    expect(wrapper.emitted('add-to-cart')).toBeTruthy()
  })

  it('shows in-cart indicator for items in cart', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets, cartIds: [1] }
    })
    expect(wrapper.find('.in-cart').exists()).toBe(true)
  })
})
