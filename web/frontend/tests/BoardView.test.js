import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BoardView from '../src/components/BoardView.vue'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ assets: [], cover_asset_id: 1 }) })
})

const board = { id: 7, name: 'My Board' }

describe('BoardView', () => {
  it('shows the board name and an Add images control', () => {
    const wrapper = mount(BoardView, { props: { board, assets: [], cartIds: [], loading: false } })
    expect(wrapper.text()).toContain('My Board')
    expect(wrapper.find('[data-testid="add-images"]').exists()).toBe(true)
  })

  it('uploads dropped files and emits changed', async () => {
    const wrapper = mount(BoardView, { props: { board, assets: [], cartIds: [], loading: false } })
    const file = new File([new Uint8Array([1, 2])], 'a.png', { type: 'image/png' })
    await wrapper.find('[data-testid="dropzone"]').trigger('drop', { dataTransfer: { files: [file] } })
    await flushPromises()
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/boards/7/images'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
