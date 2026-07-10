import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { uploadImages } from '../src/api/boards.js'

// Fake XHR so we can drive upload progress and response events by hand.
class FakeXHR {
  constructor() {
    this.status = 0
    this.responseText = ''
    this.listeners = {}
    this.upload = {
      listeners: {},
      addEventListener(type, cb) { (this.listeners[type] ||= []).push(cb) }
    }
    FakeXHR.instance = this
  }
  addEventListener(type, cb) { (this.listeners[type] ||= []).push(cb) }
  open(method, url) { this.method = method; this.url = url }
  send(body) { this.body = body }
  fireUpload(type, ev) { (this.upload.listeners[type] || []).forEach(cb => cb(ev)) }
  fire(type, ev) { (this.listeners[type] || []).forEach(cb => cb(ev)) }
}

const file = name => new File([new Uint8Array([1, 2])], name, { type: 'image/png' })

beforeEach(() => { global.XMLHttpRequest = FakeXHR })
afterEach(() => { delete global.XMLHttpRequest })

describe('uploadImages', () => {
  it('POSTs the files as multipart to the board images endpoint', () => {
    uploadImages(7, [file('a.png')])
    const xhr = FakeXHR.instance
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toContain('/boards/7/images')
    expect(xhr.body).toBeInstanceOf(FormData)
    expect(xhr.body.getAll('files')).toHaveLength(1)
  })

  it('reports byte progress as a 0-100 percent via the callback', () => {
    const seen = []
    uploadImages(7, [file('a.png')], p => seen.push(p))
    FakeXHR.instance.fireUpload('progress', { lengthComputable: true, loaded: 50, total: 200 })
    FakeXHR.instance.fireUpload('progress', { lengthComputable: true, loaded: 150, total: 200 })
    expect(seen).toEqual([25, 75])
  })

  it('reports 100 once all bytes are sent', () => {
    const seen = []
    uploadImages(7, [file('a.png')], p => seen.push(p))
    FakeXHR.instance.fireUpload('load', {})
    expect(seen[seen.length - 1]).toBe(100)
  })

  it('resolves with the parsed JSON body on success', async () => {
    const promise = uploadImages(7, [file('a.png')])
    const xhr = FakeXHR.instance
    xhr.status = 201
    xhr.responseText = JSON.stringify({ assets: [{ id: 9 }], cover_asset_id: 9 })
    xhr.fire('load', {})
    await expect(promise).resolves.toEqual({ assets: [{ id: 9 }], cover_asset_id: 9 })
  })

  it('rejects with the server detail message on a 4xx', async () => {
    const promise = uploadImages(7, [file('bad.png')])
    const xhr = FakeXHR.instance
    xhr.status = 400
    xhr.responseText = JSON.stringify({ detail: 'bad.png is not a valid image' })
    xhr.fire('load', {})
    await expect(promise).rejects.toThrow('bad.png is not a valid image')
  })

  it('rejects on a network error', async () => {
    const promise = uploadImages(7, [file('a.png')])
    FakeXHR.instance.fire('error', {})
    await expect(promise).rejects.toThrow()
  })
})
