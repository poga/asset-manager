import { describe, it, expect } from 'vitest'
import { parseRoute, buildUrl } from '../src/router.js'

describe('router', () => {
  describe('parseRoute', () => {
    it('parses root path as home route', () => {
      const route = parseRoute('/')
      expect(route).toEqual({ name: 'home', params: {} })
    })

    it('parses /asset/:id as asset route', () => {
      const route = parseRoute('/asset/123')
      expect(route).toEqual({ name: 'asset', params: { id: '123' } })
    })

    it('parses /asset/:id with string id', () => {
      const route = parseRoute('/asset/abc-def')
      expect(route).toEqual({ name: 'asset', params: { id: 'abc-def' } })
    })

    it('returns home for unknown routes', () => {
      const route = parseRoute('/unknown/path')
      expect(route).toEqual({ name: 'home', params: {} })
    })

    it('parses /similar/:id as similar route', () => {
      const route = parseRoute('/similar/123')
      expect(route).toEqual({ name: 'similar', params: { id: '123' } })
    })

    it('parses /similar/:id with string id', () => {
      const route = parseRoute('/similar/abc-def')
      expect(route).toEqual({ name: 'similar', params: { id: 'abc-def' } })
    })
  })

  describe('buildUrl', () => {
    it('builds root URL for home route', () => {
      const url = buildUrl({ name: 'home' })
      expect(url).toBe('/')
    })

    it('builds asset URL with id', () => {
      const url = buildUrl({ name: 'asset', params: { id: '123' } })
      expect(url).toBe('/asset/123')
    })

    it('builds asset URL with string id', () => {
      const url = buildUrl({ name: 'asset', params: { id: 'abc-def' } })
      expect(url).toBe('/asset/abc-def')
    })

    it('builds similar URL with id', () => {
      const url = buildUrl({ name: 'similar', params: { id: '123' } })
      expect(url).toBe('/similar/123')
    })

    it('builds similar URL with string id', () => {
      const url = buildUrl({ name: 'similar', params: { id: 'abc-def' } })
      expect(url).toBe('/similar/abc-def')
    })
  })
})
