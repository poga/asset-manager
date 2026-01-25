// web/frontend/tests/AssetDetail.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetDetail from '../src/components/AssetDetail.vue'

describe('AssetDetail', () => {
  const mockAsset = {
    id: 1,
    filename: 'hero.png',
    path: 'characters/hero.png',
    pack: 'sprites',
    width: 64,
    height: 64,
    tags: ['character', 'player'],
    colors: [
      { hex: '#ff0000', percentage: 0.3 },
      { hex: '#00ff00', percentage: 0.2 },
    ],
  }

  it('renders asset details', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('hero.png')
    expect(wrapper.text()).toContain('64x64')
    expect(wrapper.text()).toContain('sprites')
  })

  it('shows back button', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('.back-btn').exists()).toBe(true)
  })

  it('emits back when back button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.back-btn').trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()
  })

  it('emits add-to-cart when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.add-cart-btn').trigger('click')
    expect(wrapper.emitted('add-to-cart')).toBeTruthy()
    expect(wrapper.emitted('add-to-cart')[0][0]).toEqual(mockAsset)
  })

  it('emits find-similar when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.similar-btn').trigger('click')
    expect(wrapper.emitted('find-similar')).toBeTruthy()
    expect(wrapper.emitted('find-similar')[0][0]).toBe(1)
  })

  it('emits view-pack when button clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.pack-btn').trigger('click')
    expect(wrapper.emitted('view-pack')).toBeTruthy()
    expect(wrapper.emitted('view-pack')[0][0]).toBe('sprites')
  })

  it('renders Full Size link pointing to image URL', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    const fullSizeLink = wrapper.find('.full-size-btn')
    expect(fullSizeLink.exists()).toBe(true)
    expect(fullSizeLink.attributes('href')).toBe('/assets/api/image/1')
    expect(fullSizeLink.attributes('target')).toBe('_blank')
    expect(fullSizeLink.attributes('rel')).toBe('noopener noreferrer')
    expect(fullSizeLink.text()).toBe('Full Size')
  })

  it('renders tags', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('character')
    expect(wrapper.text()).toContain('player')
  })

  it('renders color swatches', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    const swatches = wrapper.findAll('.color-swatch')
    expect(swatches.length).toBe(2)
  })

  it('has minimum image size of 300x300', () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    const img = wrapper.find('.asset-image')
    const style = window.getComputedStyle(img.element)
    expect(style.minWidth).toBe('300px')
    expect(style.minHeight).toBe('300px')
  })

  it('emits tag-click when tag clicked', async () => {
    const wrapper = mount(AssetDetail, {
      props: { asset: mockAsset }
    })
    const tags = wrapper.findAll('.tag')
    await tags[0].trigger('click')
    expect(wrapper.emitted('tag-click')).toBeTruthy()
    expect(wrapper.emitted('tag-click')[0][0]).toBe('character')
  })

  describe('Preview Override', () => {
    const mockAssetWithPreview = {
      id: 1,
      filename: 'sprite.png',
      path: 'sprites/sprite.png',
      pack: 'sprites',
      width: 128,
      height: 64,
      preview_x: 0,
      preview_y: 0,
      preview_width: 32,
      preview_height: 32,
      tags: [],
      colors: [],
      use_full_image: false,
    }

    it('shows checkbox when asset has preview bounds', () => {
      const wrapper = mount(AssetDetail, {
        props: { asset: mockAssetWithPreview }
      })
      expect(wrapper.find('.preview-override-checkbox').exists()).toBe(true)
    })

    it('hides checkbox when asset has no preview bounds', () => {
      const assetNoPreview = { ...mockAssetWithPreview, preview_x: null }
      const wrapper = mount(AssetDetail, {
        props: { asset: assetNoPreview }
      })
      expect(wrapper.find('.preview-override-checkbox').exists()).toBe(false)
    })

    it('emits toggle-preview-override when checkbox clicked', async () => {
      const wrapper = mount(AssetDetail, {
        props: { asset: mockAssetWithPreview }
      })
      await wrapper.find('.preview-override-checkbox input').trigger('change')
      expect(wrapper.emitted('toggle-preview-override')).toBeTruthy()
      expect(wrapper.emitted('toggle-preview-override')[0][0]).toEqual({
        assetId: 1,
        useFullImage: true
      })
    })

    it('checkbox reflects use_full_image state', () => {
      const assetWithOverride = { ...mockAssetWithPreview, use_full_image: true }
      const wrapper = mount(AssetDetail, {
        props: { asset: assetWithOverride }
      })
      const checkbox = wrapper.find('.preview-override-checkbox input')
      expect(checkbox.element.checked).toBe(true)
    })
  })
})
