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

// XHR (not fetch) exposes upload progress; onProgress gets 0-100, 100 = sent.
export function uploadImages(boardId, fileList, onProgress) {
  const form = new FormData()
  for (const f of fileList) form.append('files', f)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/boards/${boardId}/images`)
    xhr.upload.addEventListener('progress', e => {
      if (onProgress && e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    })
    xhr.upload.addEventListener('load', () => onProgress && onProgress(100))
    xhr.addEventListener('load', () => {
      let body = {}
      try { body = JSON.parse(xhr.responseText) } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject(new Error(body.detail || xhr.statusText || 'Upload failed'))
    })
    xhr.addEventListener('error', () => reject(new Error('Upload failed')))
    xhr.send(form)
  })
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
