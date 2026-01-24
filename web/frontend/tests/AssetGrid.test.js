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

  it('uses preview dimensions for aspect ratio when preview bounds exist', () => {
    // A spritesheet asset: full image is 137x2002 but preview bounds are 50x33
    const spritesheetAsset = {
      id: 3,
      filename: 'attack 1.png',
      path: '/assets/attack.png',
      width: 137,
      height: 2002,
      preview_x: 1,
      preview_y: 52,
      preview_width: 50,
      preview_height: 33,
      pack: 'penusbmic_Sci-fi'
    }
    const wrapper = mount(AssetGrid, {
      props: { assets: [spritesheetAsset] }
    })
    const container = wrapper.find('.asset-image-container')
    // Should use preview dimensions (50/33) not full image dimensions (137/2002)
    expect(container.attributes('style')).toContain('50 / 33')
  })

  it('uses full image dimensions for aspect ratio when no preview bounds', () => {
    const wrapper = mount(AssetGrid, {
      props: { assets: mockAssets }
    })
    const container = wrapper.find('.asset-image-container')
    // Should use full image dimensions
    expect(container.attributes('style')).toContain('64 / 64')
  })

  describe('Preview Override', () => {
    it('shows full image when use_full_image is true even with preview bounds', () => {
      const assets = [{
        id: 1,
        filename: 'sprite.png',
        pack: 'sprites',
        width: 128,
        height: 64,
        preview_x: 0,
        preview_y: 0,
        preview_width: 32,
        preview_height: 32,
        use_full_image: true,
      }]

      const wrapper = mount(AssetGrid, {
        props: { assets, cartIds: [] }
      })

      // Should use img tag, not SpritePreview
      expect(wrapper.findComponent({ name: 'SpritePreview' }).exists()).toBe(false)
      expect(wrapper.find('.asset-image-container img').exists()).toBe(true)
    })

    it('uses SpritePreview when use_full_image is false with preview bounds', () => {
      const assets = [{
        id: 1,
        filename: 'sprite.png',
        pack: 'sprites',
        width: 128,
        height: 64,
        preview_x: 0,
        preview_y: 0,
        preview_width: 32,
        preview_height: 32,
        use_full_image: false,
      }]

      const wrapper = mount(AssetGrid, {
        props: { assets, cartIds: [] }
      })

      expect(wrapper.findComponent({ name: 'SpritePreview' }).exists()).toBe(true)
    })
  })
})
