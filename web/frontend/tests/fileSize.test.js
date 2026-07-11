import { describe, it, expect } from 'vitest'
import { formatSize } from '../src/utils/fileSize.js'

describe('formatSize', () => {
  it('scales through units and rounds sensibly', () => {
    expect(formatSize(512)).toBe('512 B')
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(15 * 1024 * 1024)).toBe('15 MB')
    expect(formatSize(null)).toBe('')
  })
})
