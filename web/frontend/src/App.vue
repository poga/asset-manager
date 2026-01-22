<template>
  <div class="app">
    <header class="app-header">
      <h1>Asset Manager</h1>
      <button
        class="theme-toggle"
        data-testid="theme-toggle"
        @click="toggleTheme"
        :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      >
        <svg v-if="isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/>
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </button>
    </header>

    <div class="app-layout">
      <aside class="left-panel">
        <PackList :packs="packList" v-model:selectedPacks="selectedPacks" />
      </aside>

      <main class="middle-panel">
        <SearchBar ref="searchBarRef" :filters="filters" @search="handleSearch" />

        <AssetDetail
          v-if="selectedAsset"
          :asset="selectedAsset"
          @back="selectedAsset = null"
          @add-to-cart="addToCart"
          @find-similar="findSimilar"
          @view-pack="viewPack"
          @tag-click="handleTagClick"
        />

        <AssetGrid
          v-else
          :assets="assets"
          :cart-ids="cartIds"
          @select="selectAsset"
          @view-pack="viewPack"
          @add-to-cart="addToCart"
        />
      </main>

      <aside class="right-panel">
        <Cart :items="cartItems" @remove="removeFromCart" @download="downloadCart" />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PackList from './components/PackList.vue'
import SearchBar from './components/SearchBar.vue'
import AssetGrid from './components/AssetGrid.vue'
import AssetDetail from './components/AssetDetail.vue'
import Cart from './components/Cart.vue'
import { parseRoute } from './router.js'

const filters = ref({ packs: [], tags: [], colors: [] })
const assets = ref([])
const selectedAsset = ref(null)
const searchBarRef = ref(null)
const selectedPacks = ref([])
const cartItems = ref([])
const currentSearchParams = ref({})
const isDark = ref(false)
const isDefaultHomeView = ref(true)

let debounceTimer = null
let skipNextPush = false
let isInitializing = true

function getSystemTheme() {
  if (window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'light'
}

function applyTheme(theme) {
  isDark.value = theme === 'dark'
  document.documentElement.setAttribute('data-theme', theme)
}

function toggleTheme() {
  const newTheme = isDark.value ? 'light' : 'dark'
  localStorage.setItem('theme', newTheme)
  applyTheme(newTheme)
}

function initTheme() {
  const saved = localStorage.getItem('theme')
  const theme = saved || getSystemTheme()
  applyTheme(theme)
}

// Listen for system theme changes
let mediaQuery = null
function handleSystemThemeChange(e) {
  if (!localStorage.getItem('theme')) {
    applyTheme(e.matches ? 'dark' : 'light')
  }
}

const packList = computed(() => filters.value.packs)
const cartIds = computed(() => cartItems.value.map(item => item.id))

async function fetchFilters() {
  const res = await fetch('/api/filters')
  const data = await res.json()
  filters.value = data
  // Default to no selection (which means "all packs")
  selectedPacks.value = []
}

async function search(params) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.color) query.set('color', params.color)
  for (const t of params.tag || []) {
    query.append('tag', t)
  }
  // Only filter by packs if some are selected (empty = all packs)
  if (selectedPacks.value.length > 0) {
    for (const p of selectedPacks.value) {
      query.append('pack', p)
    }
  }

  const res = await fetch(`/api/search?${query}`)
  if (!res) return
  const data = await res.json()
  assets.value = data.assets
}

function handleSearch(params) {
  currentSearchParams.value = params
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(params), 150)
}

function handleTagClick(tag) {
  selectedAsset.value = null
  if (searchBarRef.value) {
    searchBarRef.value.addTagExternal(tag)
  }
}

async function selectAsset(id) {
  const res = await fetch(`/api/asset/${id}`)
  selectedAsset.value = await res.json()
  window.history.pushState({ route: 'asset', id }, '', `/asset/${id}`)
}

async function findSimilar(id) {
  skipNextPush = true
  selectedAsset.value = null
  isDefaultHomeView.value = false
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
  window.history.pushState({ route: 'similar', id }, '', `/similar/${id}`)
}

async function loadSimilarFromUrl(id) {
  isDefaultHomeView.value = false
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
}

async function loadPack(packName) {
  isDefaultHomeView.value = false
  selectedPacks.value = [packName]
  await search(currentSearchParams.value)
}

function viewPack(packName) {
  skipNextPush = true
  selectedAsset.value = null
  isDefaultHomeView.value = false
  selectedPacks.value = [packName]
  window.history.pushState({ route: 'pack', name: packName }, '', `/pack/${packName}`)
}

function addToCart(asset) {
  if (!cartItems.value.some(item => item.id === asset.id)) {
    cartItems.value.push({ id: asset.id, filename: asset.filename, pack: asset.pack })
  }
}

function removeFromCart(id) {
  cartItems.value = cartItems.value.filter(item => item.id !== id)
}

async function downloadCart() {
  if (cartItems.value.length === 0) return
  const response = await fetch('/api/download-cart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_ids: cartIds.value })
  })
  if (response.ok) {
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `assets-${Date.now()}.zip`
    a.click()
    URL.revokeObjectURL(url)
  }
}

watch(selectedAsset, (newVal, oldVal) => {
  if (oldVal !== null && newVal === null && !skipNextPush) {
    window.history.pushState({ route: 'home' }, '', '/')
  }
  skipNextPush = false
})

watch(selectedPacks, () => {
  if (!isInitializing) {
    search(currentSearchParams.value)
  }
})

function handlePopState(event) {
  const route = parseRoute(window.location.pathname)
  skipNextPush = true
  if (route.name === 'home') {
    selectedAsset.value = null
    const hadPackFilter = selectedPacks.value.length > 0
    // Only re-fetch if we were on a non-home view (similar/pack) or had pack filters
    if (!isDefaultHomeView.value || hadPackFilter) {
      selectedPacks.value = []  // Clear pack filter (triggers watcher, but we also call search)
      search({ q: null, tag: [], color: null, type: null })
      isDefaultHomeView.value = true
    }
    // Otherwise, keep existing assets - just close asset detail view
  } else if (route.name === 'asset') {
    selectAssetFromUrl(route.params.id)
  } else if (route.name === 'similar') {
    selectedAsset.value = null
    loadSimilarFromUrl(route.params.id)
  } else if (route.name === 'pack') {
    selectedAsset.value = null
    loadPack(route.params.name)
  }
}

async function selectAssetFromUrl(id) {
  const res = await fetch(`/api/asset/${id}`)
  selectedAsset.value = await res.json()
}

function handleInitialRoute() {
  const route = parseRoute(window.location.pathname)
  if (route.name === 'asset') {
    selectAssetFromUrl(route.params.id)
  } else if (route.name === 'similar') {
    loadSimilarFromUrl(route.params.id)
  } else if (route.name === 'pack') {
    loadPack(route.params.name)
  }
}

onMounted(async () => {
  initTheme()
  if (window.matchMedia) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', handleSystemThemeChange)
  }
  await fetchFilters()
  search({ q: null, tag: [], color: null, type: null })
  handleInitialRoute()
  window.addEventListener('popstate', handlePopState)
  isInitializing = false
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', handleSystemThemeChange)
  }
  clearTimeout(debounceTimer)
})
</script>

<style>
:root {
  /* Light mode colors */
  --color-bg-base: #f8fafc;
  --color-bg-surface: #ffffff;
  --color-bg-elevated: #ffffff;
  --color-border: #e2e8f0;
  --color-border-emphasis: #cbd5e1;
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #94a3b8;

  /* Accent colors */
  --color-accent: #0d9488;
  --color-accent-hover: #0f766e;
  --color-accent-light: #ccfbf1;
  --color-success: #10b981;
  --color-success-hover: #0a9b6e;
  --color-danger: #ef4444;

  /* Shadows */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.08);
  --shadow-elevated: 0 4px 6px rgba(0,0,0,0.07), 0 12px 28px rgba(0,0,0,0.12);

  /* Glass effect */
  --glass-bg: rgba(255,255,255,0.8);
}

[data-theme="dark"] {
  --color-bg-base: #0f172a;
  --color-bg-surface: #1e293b;
  --color-bg-elevated: #334155;
  --color-border: #334155;
  --color-border-emphasis: #475569;
  --color-text-primary: #f8fafc;
  --color-text-secondary: #cbd5e1;
  --color-text-muted: #64748b;

  --color-accent-light: #134e4a;

  --shadow-card: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.3);
  --shadow-elevated: 0 4px 6px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.5);

  --glass-bg: rgba(30,41,59,0.8);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
}

.app {
  font-family: system-ui, sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  transition: background-color 200ms, color 200ms;
}

.app-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-header h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.theme-toggle {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.5rem;
  cursor: pointer;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 150ms, background-color 150ms;
}

.theme-toggle:hover {
  border-color: var(--color-border-emphasis);
  background: var(--color-bg-surface);
}

.theme-toggle svg {
  width: 18px;
  height: 18px;
}

.app-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 1rem;
  padding: 1rem;
  background: var(--color-bg-base);
}

.left-panel {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.middle-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg-surface);
  border-radius: 8px;
  box-shadow: var(--shadow-card);
  padding: 1rem;
}

.middle-panel > :last-child {
  flex: 1;
  overflow-y: auto;
}

.right-panel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}
</style>
