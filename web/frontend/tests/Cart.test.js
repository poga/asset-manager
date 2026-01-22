// web/frontend/tests/Cart.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Cart from '../src/components/Cart.vue'

describe('Cart', () => {
  const mockItems = [
    { id: 1, filename: 'button.png', pack: 'ui-kit' },
    { id: 2, filename: 'slime.png', pack: 'monsters' },
  ]

  it('renders cart items', () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    expect(wrapper.text()).toContain('button.png')
    expect(wrapper.text()).toContain('ui-kit')
    expect(wrapper.text()).toContain('slime.png')
  })

  it('shows empty state when no items', () => {
    const wrapper = mount(Cart, {
      props: { items: [] }
    })
    expect(wrapper.text()).toContain('No items in cart')
  })

  it('emits remove when remove button clicked', async () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    await wrapper.find('.remove-btn').trigger('click')
    expect(wrapper.emitted('remove')).toBeTruthy()
    expect(wrapper.emitted('remove')[0][0]).toBe(1)
  })

  it('emits download when download button clicked', async () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    await wrapper.find('.download-btn').trigger('click')
    expect(wrapper.emitted('download')).toBeTruthy()
  })

  it('disables download button when cart is empty', () => {
    const wrapper = mount(Cart, {
      props: { items: [] }
    })
    const downloadBtn = wrapper.find('.download-btn')
    expect(downloadBtn.element.disabled).toBe(true)
  })

  it('shows item count in header', () => {
    const wrapper = mount(Cart, {
      props: { items: mockItems }
    })
    expect(wrapper.text()).toContain('2')
  })
})
