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
})
