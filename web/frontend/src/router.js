export function parseRoute(path) {
  const assetMatch = path.match(/^\/asset\/([^/]+)$/)
  if (assetMatch) {
    return { name: 'asset', params: { id: assetMatch[1] } }
  }
  const similarMatch = path.match(/^\/similar\/([^/]+)$/)
  if (similarMatch) {
    return { name: 'similar', params: { id: similarMatch[1] } }
  }
  const packMatch = path.match(/^\/pack\/([^/]+)$/)
  if (packMatch) {
    return { name: 'pack', params: { name: packMatch[1] } }
  }
  return { name: 'home', params: {} }
}

export function buildUrl(route) {
  if (route.name === 'asset' && route.params?.id) {
    return `/asset/${route.params.id}`
  }
  if (route.name === 'similar' && route.params?.id) {
    return `/similar/${route.params.id}`
  }
  if (route.name === 'pack' && route.params?.name) {
    return `/pack/${route.params.name}`
  }
  return '/'
}
