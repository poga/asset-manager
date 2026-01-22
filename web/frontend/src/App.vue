<template>
  <div class="app">
    <header class="app-header">
      <h1>Asset Manager</h1>
    </header>

    <div class="app-layout">
      <aside class="left-panel">
        <PackList :packs="packList" v-model:selectedPacks="selectedPacks" />
      </aside>

      <main class="middle-panel">
        <SearchBar :filters="filters" @search="handleSearch" />

        <AssetDetail
          v-if="selectedAsset"
          :asset="selectedAsset"
          @back="selectedAsset = null"
          @add-to-cart="addToCart"
          @find-similar="findSimilar"
          @view-pack="viewPack"
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
const selectedPacks = ref([])
const cartItems = ref([])
const currentSearchParams = ref({})

let debounceTimer = null
let skipNextPush = false
let isInitializing = true

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

async function selectAsset(id) {
  const res = await fetch(`/api/asset/${id}`)
  selectedAsset.value = await res.json()
  window.history.pushState({ route: 'asset', id }, '', `/asset/${id}`)
}

async function findSimilar(id) {
  skipNextPush = true
  selectedAsset.value = null
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
  window.history.pushState({ route: 'similar', id }, '', `/similar/${id}`)
}

async function loadSimilarFromUrl(id) {
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
}

async function loadPack(packName) {
  selectedPacks.value = [packName]
  await search(currentSearchParams.value)
}

function viewPack(packName) {
  skipNextPush = true
  selectedAsset.value = null
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
    selectedPacks.value = []  // Empty = all packs
    search({ q: null, tag: [], color: null, type: null })
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
  await fetchFilters()
  search({ q: null, tag: [], color: null, type: null })
  handleInitialRoute()
  window.addEventListener('popstate', handlePopState)
  isInitializing = false
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
  clearTimeout(debounceTimer)
})
</script>

<style>
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
}

.app-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e0e0e0;
  background: #fff;
}

.app-header h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.app-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 1rem;
  padding: 1rem;
  background: #f0f0f0;
}

.left-panel {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.middle-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}
</style>
