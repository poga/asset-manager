import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import BoardView from '../src/components/BoardView.vue'

vi.mock('../src/api/boards.js', () => ({
  uploadImages: vi.fn(),
  renameBoard: vi.fn(() => Promise.resolve({})),
  deleteBoard: vi.fn(() => Promise.resolve({}))
}))
import { uploadImages } from '../src/api/boards.js'

const board = { id: 7, name: 'My Board' }
const file = name => new File([new Uint8Array([1, 2])], name, { type: 'image/png' })

function mountBoard() {
  return mount(BoardView, { props: { board, assets: [], cartIds: [], loading: false } })
}

async function dropFiles(wrapper, files) {
  await wrapper.find('[data-testid="dropzone"]').trigger('drop', { dataTransfer: { files } })
}

beforeEach(() => {
  uploadImages.mockReset()
  uploadImages.mockResolvedValue({ assets: [], cover_asset_id: 1 })
})

describe('BoardView', () => {
  it('shows the board name and an Add images control', () => {
    const wrapper = mountBoard()
    expect(wrapper.text()).toContain('My Board')
    expect(wrapper.find('[data-testid="add-images"]').exists()).toBe(true)
  })

  it('uploads dropped files and emits changed', async () => {
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png')])
    await flushPromises()
    expect(uploadImages).toHaveBeenCalledWith(7, expect.anything(), expect.any(Function))
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('shows a percent progress bar while bytes upload, then a processing state', async () => {
    let onProgress
    uploadImages.mockImplementation((id, files, cb) => {
      onProgress = cb
      return new Promise(() => {}) // stay pending
    })
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png'), file('b.png')])
    await nextTick()

    onProgress(40)
    await nextTick()
    const bar = wrapper.find('[data-testid="upload-progress"]')
    expect(bar.exists()).toBe(true)
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('40%')

    onProgress(100)
    await nextTick()
    expect(wrapper.text().toLowerCase()).toContain('processing')
  })

  it('clears the progress UI after a successful upload', async () => {
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png')])
    await flushPromises()
    expect(wrapper.find('[data-testid="upload-progress"]').exists()).toBe(false)
  })

  it('surfaces the server error message and re-enables controls on failure', async () => {
    uploadImages.mockRejectedValue(new Error('a.png is not a valid image'))
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png')])
    await flushPromises()
    expect(wrapper.text()).toContain('a.png is not a valid image')
    expect(wrapper.find('[data-testid="add-images"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('changed')).toBeFalsy()
  })

  it('disables the Add images control while an upload is in flight', async () => {
    uploadImages.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png')])
    await nextTick()
    expect(wrapper.find('[data-testid="add-images"]').attributes('disabled')).toBeDefined()
  })

  it('ignores a new drop while an upload is already running', async () => {
    uploadImages.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountBoard()
    await dropFiles(wrapper, [file('a.png')])
    await nextTick()
    await dropFiles(wrapper, [file('b.png')])
    await nextTick()
    expect(uploadImages).toHaveBeenCalledTimes(1)
  })
})
