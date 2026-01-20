import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AssetModal from '../src/components/AssetModal.vue'

const mockAsset = {
  id: 1,
  filename: 'goblin.png',
  path: '/assets/creatures/goblin.png',
  pack: 'creatures',
  width: 64,
  height: 64,
  tags: ['creature', 'goblin'],
  colors: [{ hex: '#00ff00', percentage: 0.5 }],
  related: []
}

describe('AssetModal', () => {
  it('renders asset details', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('goblin.png')
    expect(wrapper.text()).toContain('/assets/creatures/goblin.png')
    expect(wrapper.text()).toContain('creatures')
    expect(wrapper.text()).toContain('64')
  })

  it('renders tags', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.text()).toContain('creature')
    expect(wrapper.text()).toContain('goblin')
  })

  it('renders color swatches', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('.color-swatch').exists()).toBe(true)
  })

  it('has Find Similar button', () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    expect(wrapper.find('button').text()).toContain('Find Similar')
  })

  it('emits find-similar event on button click', async () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('find-similar')).toBeTruthy()
    expect(wrapper.emitted('find-similar')[0]).toEqual([1])
  })

  it('emits close event on overlay click', async () => {
    const wrapper = mount(AssetModal, {
      props: { asset: mockAsset }
    })
    await wrapper.find('.modal-overlay').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
