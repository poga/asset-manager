const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, '') + '/api'

async function json(res) {
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
  return res.json()
}

export function createBoard(name, tags = []) {
  return fetch(`${API_BASE}/boards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, tags })
  }).then(json)
}

export function uploadImages(boardId, fileList) {
  const form = new FormData()
  for (const f of fileList) form.append('files', f)
  return fetch(`${API_BASE}/boards/${boardId}/images`, { method: 'POST', body: form }).then(json)
}

export function renameBoard(id, name) {
  return fetch(`${API_BASE}/boards/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }).then(json)
}

export function setCover(id, coverAssetId) {
  return fetch(`${API_BASE}/boards/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cover_asset_id: coverAssetId })
  }).then(json)
}

export function deleteBoard(id) {
  return fetch(`${API_BASE}/boards/${id}`, { method: 'DELETE' }).then(json)
}

export function deleteImage(assetId) {
  return fetch(`${API_BASE}/asset/${assetId}`, { method: 'DELETE' }).then(json)
}

export function addImageTag(assetId, tag) {
  return fetch(`${API_BASE}/asset/${assetId}/tags`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag })
  }).then(json)
}

export function removeImageTag(assetId, tag) {
  return fetch(`${API_BASE}/asset/${assetId}/tags/${encodeURIComponent(tag)}`, {
    method: 'DELETE'
  }).then(json)
}
