import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PackGallery from '../src/components/PackGallery.vue'

const mockFetch = vi.fn()
global.fetch = mockFetch

const packs = [
  { name: 'Minifantasy_Ancient_Forests', count: 120, is_3d: false, tags: ['forest'] },
  { name: 'KayKit Forest Nature Pack 1.0', count: 80, is_3d: true, tags: ['forest'] },
  { name: 'Minifantasy_Dungeon_v2.3', count: 300, is_3d: false, tags: [] },
]

beforeEach(() => {
  mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: [] }) })
})

afterEach(() => {
  mockFetch.mockReset()
})

describe('PackGallery', () => {
  it('groups packs into 2D and 3D sections', () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const titles = wrapper.findAll('.dim-title').map(t => t.text())
    expect(titles).toEqual(['2D', '3D'])
    const twoD = wrapper.findAll('.dim-section')[0].findAll('.gallery-card')
    expect(twoD.length).toBe(2)
  })

  it('omits an empty dimension section', () => {
    const wrapper = mount(PackGallery, { props: { packs: packs.filter(p => !p.is_3d) } })
    expect(wrapper.findAll('.dim-title').map(t => t.text())).toEqual(['2D'])
  })

  it('renders tag chips with pack counts and filters on click', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const chip = wrapper.findAll('.chip').find(c => c.text().includes('forest'))
    expect(chip.text()).toContain('2')

    await chip.trigger('click')
    expect(wrapper.findAll('.gallery-card').length).toBe(2)

    // clicking the active chip clears the filter
    await chip.trigger('click')
    expect(wrapper.findAll('.gallery-card').length).toBe(3)
  })

  it('hides the chip row when no pack has tags', () => {
    const wrapper = mount(PackGallery, { props: { packs: [packs[2]] } })
    expect(wrapper.find('.tag-chips').exists()).toBe(false)
  })

  it('adds a tag through the API and renders it', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: ['cave'] }) })
    const wrapper = mount(PackGallery, { props: { packs } })
    const dungeonCard = wrapper.findAll('.gallery-card')
      .find(c => c.text().includes('Dungeon'))

    await dungeonCard.find('.tag-add').trigger('click')
    const input = dungeonCard.find('.tag-input')
    await input.setValue('cave')
    await input.trigger('keyup.enter')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pack/Minifantasy_Dungeon_v2.3/tags'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(dungeonCard.text()).toContain('cave')
  })

  it('removes a tag through the API', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: [] }) })
    const wrapper = mount(PackGallery, { props: { packs } })
    const forestCard = wrapper.findAll('.gallery-card')
      .find(c => c.text().includes('Ancient Forests'))

    await forestCard.find('.tag-remove').trigger('click')
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/tags/forest'),
      expect.objectContaining({ method: 'DELETE' })
    )
    expect(forestCard.find('.tag-chip').exists()).toBe(false)
  })

  it('clears the active filter when its last tag is removed', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ tags: [] }) })
    const wrapper = mount(PackGallery, { props: { packs: [packs[0], packs[2]] } })

    await wrapper.find('.chip').trigger('click')
    expect(wrapper.findAll('.gallery-card').length).toBe(1)

    await wrapper.find('.tag-remove').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.gallery-card').length).toBe(2)
  })

  it('does not call the API for an empty tag', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const card = wrapper.findAll('.gallery-card')[0]

    await card.find('.tag-add').trigger('click')
    const input = card.find('.tag-input')
    await input.setValue('   ')
    await input.trigger('keyup.enter')
    await flushPromises()

    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('tag interactions do not navigate to the pack', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const card = wrapper.findAll('.gallery-card')[0]
    await card.find('.card-tags').trigger('click')
    expect(wrapper.emitted('view-pack')).toBeFalsy()
    await card.trigger('click')
    expect(wrapper.emitted('view-pack')).toBeTruthy()
  })

  it('gives visually distinct tags a clearly separated hue', () => {
    const distinctPacks = [
      { name: 'A', count: 1, is_3d: false, tags: ['minifantasy'] },
      { name: 'B', count: 1, is_3d: false, tags: ['penusbmic'] },
    ]
    const wrapper = mount(PackGallery, { props: { packs: distinctPacks } })
    const hues = wrapper.findAll('.tag-chip').map(chip => {
      const hue = Number(chip.element.style.getPropertyValue('--tag-hue'))
      return hue
    })
    const [a, b] = hues
    const circularDistance = Math.min(Math.abs(a - b), 360 - Math.abs(a - b))
    expect(circularDistance).toBeGreaterThanOrEqual(20)
  })

  it('renders a BOARD badge on board packs', () => {
    const withBoard = [...packs, { name: 'My Board', count: 3, is_3d: false, is_board: true, tags: [], id: 9 }]
    const wrapper = mount(PackGallery, { props: { packs: withBoard } })
    expect(wrapper.text()).toContain('BOARD')
  })

  it('emits create-board when a name is entered on the new-board card', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    await wrapper.find('.new-board-card').trigger('click')
    const input = wrapper.find('.new-board-input')
    await input.setValue('Fresh Board')
    await input.trigger('keyup.enter')
    expect(wrapper.emitted('create-board')[0]).toEqual(['Fresh Board'])
  })

  it('upscales small covers crisply, leaves large covers smooth', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const imgs = wrapper.findAll('.card-cover img')

    Object.defineProperty(imgs[0].element, 'naturalWidth', { value: 64 })
    await imgs[0].trigger('load')
    expect(imgs[0].classes()).toContain('pixelated')

    Object.defineProperty(imgs[1].element, 'naturalWidth', { value: 512 })
    await imgs[1].trigger('load')
    expect(imgs[1].classes()).not.toContain('pixelated')
  })
})
