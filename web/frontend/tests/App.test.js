import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import App from '../src/App.vue'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('App URL routing', () => {
  let pushStateSpy
  let originalLocation

  beforeEach(() => {
    pushStateSpy = vi.spyOn(window.history, 'pushState')
    originalLocation = window.location.pathname

    // Default fetch responses
    mockFetch.mockImplementation((url) => {
      if (url === '/api/filters') {
        return Promise.resolve({
          json: () => Promise.resolve({ packs: [], tags: [], colors: [] })
        })
      }
      if (url.startsWith('/api/search')) {
        return Promise.resolve({
          json: () => Promise.resolve({ assets: [] })
        })
      }
      if (url.startsWith('/api/asset/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            id: 123,
            filename: 'test.png',
            path: '/test.png',
            pack: 'test',
            width: 32,
            height: 32,
            tags: [],
            colors: [],
            related: []
          })
        })
      }
      if (url.startsWith('/api/similar/')) {
        return Promise.resolve({
          json: () => Promise.resolve({
            assets: [
              { id: 201, filename: 'similar1.png', path: '/similar1.png', pack: 'test', tags: [], width: 32, height: 32 },
              { id: 202, filename: 'similar2.png', path: '/similar2.png', pack: 'test', tags: [], width: 32, height: 32 }
            ]
          })
        })
      }
      return Promise.resolve({ json: () => Promise.resolve({}) })
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    mockFetch.mockReset()
    // Restore original location
    window.history.replaceState({}, '', originalLocation)
  })

  it('calls pushState with /asset/:id when selecting an asset', async () => {
    const wrapper = mount(App)
    await flushPromises()

    // Simulate asset selection
    wrapper.vm.selectAsset(123)
    await flushPromises()

    expect(pushStateSpy).toHaveBeenCalledWith(
      { route: 'asset', id: 123 },
      '',
      '/asset/123'
    )
  })

  it('calls pushState with / when closing asset modal', async () => {
    const wrapper = mount(App)
    await flushPromises()

    // Open asset first
    wrapper.vm.selectAsset(123)
    await flushPromises()
    pushStateSpy.mockClear()

    // Close modal
    wrapper.vm.selectedAsset = null
    await flushPromises()

    expect(pushStateSpy).toHaveBeenCalledWith(
      { route: 'home' },
      '',
      '/'
    )
  })

  it('loads asset from URL on mount when path is /asset/:id', async () => {
    // Set URL before mounting
    window.history.replaceState({}, '', '/asset/456')

    const wrapper = mount(App)
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/asset/456')
    expect(wrapper.vm.selectedAsset).not.toBeNull()
  })

  it('handles popstate event (back button)', async () => {
    const wrapper = mount(App)
    await flushPromises()

    // Open asset
    wrapper.vm.selectAsset(123)
    await flushPromises()

    // Simulate back button
    window.history.replaceState({}, '', '/')
    window.dispatchEvent(new PopStateEvent('popstate', {
      state: { route: 'home' }
    }))
    await flushPromises()

    expect(wrapper.vm.selectedAsset).toBeNull()
  })

  it('handles popstate to asset route', async () => {
    const wrapper = mount(App)
    await flushPromises()

    // Simulate forward to asset
    window.history.replaceState({}, '', '/asset/789')
    window.dispatchEvent(new PopStateEvent('popstate', {
      state: { route: 'asset', id: 789 }
    }))
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/asset/789')
  })

  it('calls pushState with /similar/:id when finding similar', async () => {
    const wrapper = mount(App)
    await flushPromises()
    pushStateSpy.mockClear()

    // Find similar
    wrapper.vm.findSimilar(123)
    await flushPromises()

    expect(pushStateSpy).toHaveBeenCalledWith(
      { route: 'similar', id: 123 },
      '',
      '/similar/123'
    )
  })

  it('loads similar assets from URL on mount when path is /similar/:id', async () => {
    // Set URL before mounting
    window.history.replaceState({}, '', '/similar/456')

    const wrapper = mount(App)
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/similar/456')
    expect(wrapper.vm.assets.length).toBe(2)
  })

  it('handles popstate to similar route', async () => {
    const wrapper = mount(App)
    await flushPromises()
    mockFetch.mockClear()

    // Simulate forward to similar
    window.history.replaceState({}, '', '/similar/789')
    window.dispatchEvent(new PopStateEvent('popstate', {
      state: { route: 'similar', id: 789 }
    }))
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/similar/789')
  })
})
