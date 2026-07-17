import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
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

describe('AssetGrid viewport filling', () => {
  // simulate a scroll container of a given content/viewport height
  function setLayout(el, { scrollHeight, clientHeight }) {
    Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true })
    Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true })
  }

  it('requests another page when content does not fill the scroll container', async () => {
    const wrapper = mount(AssetGrid, { props: { assets: mockAssets, loading: false } })
    setLayout(wrapper.element, { scrollHeight: 400, clientHeight: 900 })
    await wrapper.setProps({ assets: [...mockAssets] })  // a page arrives
    await flushPromises()
    expect(wrapper.emitted('load-more')).toBeTruthy()
  })

  it('does not request more once content overflows the scroll container', async () => {
    const wrapper = mount(AssetGrid, { props: { assets: mockAssets, loading: false } })
    setLayout(wrapper.element, { scrollHeight: 1600, clientHeight: 900 })
    await wrapper.setProps({ assets: [...mockAssets] })
    await flushPromises()
    expect(wrapper.emitted('load-more')).toBeFalsy()
  })

  it('does not request more while a page load is already in flight', async () => {
    const wrapper = mount(AssetGrid, { props: { assets: mockAssets, loading: true } })
    setLayout(wrapper.element, { scrollHeight: 400, clientHeight: 900 })
    await wrapper.setProps({ assets: [...mockAssets] })
    await flushPromises()
    expect(wrapper.emitted('load-more')).toBeFalsy()
  })

  it('pages repeatedly until the container fills, then stops (big-screen scenario)', async () => {
    const CLIENT = 900, ROW_H = 150, PER_ROW = 5
    const make = (n) => Array.from({ length: n }, (_, i) => ({ id: i + 1, filename: `a${i}.png`, width: 64, height: 64, pack: 'p' }))
    const wrapper = mount(AssetGrid, { props: { assets: make(10), loading: false } })

    // content height tracks item count against a fixed tall viewport
    let total = 10
    const step = async () => {
      const rows = Math.ceil(total / PER_ROW)
      setLayout(wrapper.element, { scrollHeight: rows * ROW_H, clientHeight: CLIENT })
      await wrapper.setProps({ assets: make(total) })
      await flushPromises()
    }

    // play App.loadMore: append a page each time the grid asks for more
    await step()
    let handled = 0
    for (let i = 0; i < 40 && (wrapper.emitted('load-more')?.length ?? 0) > handled; i++) {
      handled = wrapper.emitted('load-more').length
      total += 10
      await step()
    }

    expect(total).toBeGreaterThan(30)  // auto-loaded several pages, not just one
    expect(total).toBeLessThan(300)    // and terminated once the viewport filled
  })
})

describe('AssetGrid file/font kinds', () => {
  const fileAsset = {
    id: 10, filename: 'blur.glsl', pack: 'Shaders', kind: 'file',
    file_size: 2048, tags: [], preview_x: null, width: null, height: null,
  }
  const fontAsset = {
    id: 11, filename: 'pixel.ttf', pack: 'Fonts', kind: 'font',
    tags: [], preview_x: null, width: null, height: null,
  }

  it('renders extension badge instead of image for file assets', () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fileAsset] } })
    expect(wrapper.find('.file-ext').text()).toBe('.GLSL')
    expect(wrapper.find('.file-size').text()).toBe('2.0 KB')
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('renders thumbnail image for font assets', () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fontAsset] } })
    expect(wrapper.find('img').attributes('src')).toContain('/image/11')
  })

  it('falls back to Aa placeholder when a font thumbnail fails', async () => {
    const wrapper = mount(AssetGrid, { props: { assets: [fontAsset] } })
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('.font-fallback').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
  })
})

describe('AssetGrid batch tagging', () => {
  const assets = [
    { id: 1, filename: 'a.png', path: '/a.png', width: 64, height: 64, pack: 'p', tags: ['wip'] },
    { id: 2, filename: 'b.png', path: '/b.png', width: 64, height: 64, pack: 'p', tags: ['wip', 'hero'] },
  ]

  it('selects assets and batch-removes a tag via a union chip', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ results: [
        { id: 1, tags: [] }, { id: 2, tags: ['hero'] },
      ] }),
    })
    const wrapper = mount(AssetGrid, { props: { assets } })

    await wrapper.find('.select-toggle').trigger('click')
    const cards = wrapper.findAll('.asset-image-container')
    await cards[0].trigger('click')
    await cards[1].trigger('click')

    expect(wrapper.emitted('select')).toBeUndefined()  // selecting != opening
    expect(wrapper.find('.batch-count').text()).toContain('2')
    // union of ['wip'] and ['wip','hero'] = ['hero','wip'] (sorted)
    const chips = wrapper.findAll('.batch-chip').map(c => c.text().replace('×', '').trim())
    expect(chips).toEqual(['hero', 'wip'])

    // 'wip' is the second sorted chip
    await wrapper.findAll('.batch-chip-remove')[1].trigger('click')
    await flushPromises()

    const [url, opts] = global.fetch.mock.calls.at(-1)
    expect(url).toMatch(/\/assets\/tags$/)
    expect(JSON.parse(opts.body)).toEqual({ asset_ids: [1, 2], tag: 'wip', op: 'remove' })
    // overrides applied -> union recomputed to just ['hero']
    expect(wrapper.findAll('.batch-chip').map(c => c.text().replace('×', '').trim())).toEqual(['hero'])
  })

  it('clears selection when the results change', async () => {
    global.fetch = vi.fn()
    const wrapper = mount(AssetGrid, { props: { assets } })
    await wrapper.find('.select-toggle').trigger('click')
    await wrapper.findAll('.asset-image-container')[0].trigger('click')
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    await wrapper.setProps({ assets: [{ id: 3, filename: 'c.png', path: '/c.png', width: 64, height: 64, pack: 'p', tags: [] }] })
    expect(wrapper.find('.batch-bar').exists()).toBe(false)
  })

  it('preserves selection when more results are appended (pagination)', async () => {
    global.fetch = vi.fn()
    const wrapper = mount(AssetGrid, { props: { assets } })
    await wrapper.find('.select-toggle').trigger('click')
    await wrapper.findAll('.asset-image-container')[0].trigger('click')  // select id 1
    expect(wrapper.find('.batch-count').text()).toContain('1')
    // append a superset (new array reference), as pagination does
    await wrapper.setProps({ assets: [...assets, { id: 3, filename: 'c.png', path: '/c.png', width: 64, height: 64, pack: 'p', tags: [] }] })
    expect(wrapper.find('.batch-bar').exists()).toBe(true)
    expect(wrapper.find('.batch-count').text()).toContain('1')
  })
})
