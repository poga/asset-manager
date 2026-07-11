// web/frontend/tests/AssetDetail.test.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
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

  describe('kind-based rendering', () => {
    const base = { id: 1, filename: 'x', path: 'x', tags: [], colors: [], width: 64, height: 64 }

    beforeEach(() => {
      // ModelViewer fetches animations on mount; stub to avoid invalid-URL errors in jsdom
      vi.stubGlobal('fetch', () => Promise.resolve({ ok: false }))
    })

    afterEach(() => { vi.unstubAllGlobals() })

    it('renders <img> for image asset', () => {
      const w = mount(AssetDetail, { props: { asset: { ...base, kind: 'image' } } })
      expect(w.find('img.asset-image').exists()).toBe(true)
      expect(w.find('model-viewer').exists()).toBe(false)
    })

    it('renders <model-viewer> for model asset', () => {
      const w = mount(AssetDetail, { props: { asset: { ...base, kind: 'model' } } })
      expect(w.find('model-viewer').exists()).toBe(true)
      expect(w.find('img.asset-image').exists()).toBe(false)
    })

    it('renders <model-viewer> for animation_bundle asset', () => {
      const w = mount(AssetDetail, { props: { asset: { ...base, kind: 'animation_bundle' } } })
      expect(w.find('model-viewer').exists()).toBe(true)
      expect(w.find('img.asset-image').exists()).toBe(false)
    })

    it('renders <img> when kind is absent (legacy)', () => {
      const w = mount(AssetDetail, { props: { asset: { ...base } } })
      expect(w.find('img.asset-image').exists()).toBe(true)
      expect(w.find('model-viewer').exists()).toBe(false)
    })
  })

  describe('Board image actions', () => {
    const boardAsset = {
      id: 5, filename: 'a.png', filetype: 'png', pack: 'My Board',
      is_board: true, board_id: 7, tags: [], colors: [], width: 10, height: 10
    }

    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ tags: [] }) })
      ))
    })

    afterEach(() => { vi.unstubAllGlobals() })

    it('hides board actions for non-board assets', () => {
      const wrapper = mount(AssetDetail, { props: { asset: mockAsset } })
      expect(wrapper.find('[data-testid="set-cover"]').exists()).toBe(false)
    })

    it('shows board image actions and emits on set-cover', async () => {
      const wrapper = mount(AssetDetail, { props: { asset: boardAsset } })
      const btn = wrapper.find('[data-testid="set-cover"]')
      expect(btn.exists()).toBe(true)
      await btn.trigger('click')
      await flushPromises()
      expect(wrapper.emitted('board-image-changed')).toBeTruthy()
    })

    it('emits board-image-removed on remove', async () => {
      const wrapper = mount(AssetDetail, { props: { asset: boardAsset } })
      await wrapper.find('.board-btn.danger').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('board-image-removed')).toBeTruthy()
    })

    it('adds a tag and emits board-image-changed', async () => {
      global.fetch.mockImplementationOnce(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve({ tags: ['new'] }) })
      )
      const wrapper = mount(AssetDetail, { props: { asset: boardAsset } })
      await wrapper.find('.tag-input').setValue('new')
      await wrapper.find('.tag-input').trigger('keyup.enter')
      await flushPromises()
      expect(wrapper.emitted('board-image-changed')).toBeTruthy()
      expect(wrapper.text()).toContain('new')
    })

    it('removes a tag and emits board-image-changed', async () => {
      const asset = { ...boardAsset, tags: ['old'] }
      const wrapper = mount(AssetDetail, { props: { asset } })
      await wrapper.find('.tag-remove').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('board-image-changed')).toBeTruthy()
    })
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

  describe('AssetDetail file kind', () => {
    const fileAsset = {
      id: 5, filename: 'blur.glsl', path: 'Shaders/blur.glsl', pack: 'Shaders',
      kind: 'file', file_size: 2048, width: null, height: null, tags: ['file'], colors: [],
    }

    it('shows a download link with attachment url', () => {
      const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
      const link = wrapper.find('.download-btn')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toContain('/asset/5/file?download=true')
    })

    it('renders a file panel instead of an image', () => {
      const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
      expect(wrapper.find('.file-panel').exists()).toBe(true)
      expect(wrapper.find('img').exists()).toBe(false)
      expect(wrapper.text()).toContain('2.0 KB')
    })

    it('hides pixel dimensions and Full Size for file assets', () => {
      const wrapper = mount(AssetDetail, { props: { asset: fileAsset } })
      expect(wrapper.text()).not.toContain('nullxnull')
      expect(wrapper.find('.full-size-btn').exists()).toBe(false)
    })
  })

  describe('AssetDetail font kind', () => {
    beforeEach(() => {
      vi.stubGlobal('FontFace', class {
        load() { return Promise.resolve(this) }
      })
    })
    afterEach(() => vi.unstubAllGlobals())

    it('renders the type tester for fonts', () => {
      const fontAsset = {
        id: 6, filename: 'pixel.ttf', path: 'Fonts/pixel.ttf', pack: 'Fonts',
        kind: 'font', file_size: 900, width: null, height: null, tags: ['font'], colors: [],
      }
      const wrapper = mount(AssetDetail, { props: { asset: fontAsset } })
      expect(wrapper.findComponent({ name: 'FontTester' }).exists()).toBe(true)
      expect(wrapper.find('.download-btn').exists()).toBe(true)
    })
  })
})
