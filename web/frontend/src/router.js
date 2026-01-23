const BASE = import.meta.env.BASE_URL.replace(/\/$/, '')

export function parseRoute(path) {
  const pathWithoutBase = path.startsWith(BASE) ? path.slice(BASE.length) : path
  const normalizedPath = pathWithoutBase || '/'

  const assetMatch = normalizedPath.match(/^\/asset\/([^/]+)$/)
  if (assetMatch) {
    return { name: 'asset', params: { id: assetMatch[1] } }
  }
  const similarMatch = normalizedPath.match(/^\/similar\/([^/]+)$/)
  if (similarMatch) {
    return { name: 'similar', params: { id: similarMatch[1] } }
  }
  const packMatch = normalizedPath.match(/^\/pack\/([^/]+)$/)
  if (packMatch) {
    return { name: 'pack', params: { name: packMatch[1] } }
  }
  return { name: 'home', params: {} }
}

export function buildUrl(route) {
  if (route.name === 'asset' && route.params?.id) {
    return `${BASE}/asset/${route.params.id}`
  }
  if (route.name === 'similar' && route.params?.id) {
    return `${BASE}/similar/${route.params.id}`
  }
  if (route.name === 'pack' && route.params?.name) {
    return `${BASE}/pack/${route.params.name}`
  }
  return `${BASE}/`
}
