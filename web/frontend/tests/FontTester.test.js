import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FontTester from '../src/components/FontTester.vue'

describe('FontTester', () => {
  beforeEach(() => {
    vi.stubGlobal('FontFace', class {
      constructor(family, source) {
        this.family = family
        this.source = source
      }
      load() { return Promise.resolve(this) }
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('loads the font and renders the sample at three sizes', async () => {
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    const specimens = wrapper.findAll('.specimen')
    expect(specimens).toHaveLength(3)
    expect(specimens[0].attributes('style')).toContain('font-size: 16px')
    expect(specimens[2].attributes('style')).toContain('font-size: 64px')
    expect(specimens[0].attributes('style')).toContain('asset-font-7')
  })

  it('re-renders specimens when the sample text is edited', async () => {
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    await wrapper.find('.sample-input').setValue('Hello 123')
    expect(wrapper.find('.specimen').text()).toBe('Hello 123')
  })

  it('shows an error state when the font fails to load', async () => {
    vi.stubGlobal('FontFace', class {
      load() { return Promise.reject(new Error('bad font')) }
    })
    const wrapper = mount(FontTester, { props: { assetId: 7, apiBase: '/api' } })
    await flushPromises()
    expect(wrapper.find('.tester-error').exists()).toBe(true)
    expect(wrapper.findAll('.specimen')).toHaveLength(0)
  })
})
