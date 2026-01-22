<template>
  <div class="app">
    <h1>Asset Search</h1>

    <SearchBar :filters="filters" :current-pack="currentPack" @search="handleSearch" @clear-pack="clearPack" />

    <AssetGrid :assets="assets" @select="selectAsset" @view-pack="viewPack" />

    <AssetModal
      v-if="selectedAsset"
      :asset="selectedAsset"
      @close="selectedAsset = null"
      @find-similar="findSimilar"
      @view-pack="viewPack"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import SearchBar from './components/SearchBar.vue'
import AssetGrid from './components/AssetGrid.vue'
import AssetModal from './components/AssetModal.vue'
import { parseRoute } from './router.js'

const filters = ref({ packs: [], tags: [], colors: [] })
const assets = ref([])
const selectedAsset = ref(null)
const currentPack = ref(null)

let debounceTimer = null
let skipNextPush = false

async function fetchFilters() {
  const res = await fetch('/api/filters')
  filters.value = await res.json()
}

async function search(params) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.pack) query.set('pack', params.pack)
  if (params.color) query.set('color', params.color)
  if (params.type) query.set('type', params.type)
  for (const t of params.tag || []) {
    query.append('tag', t)
  }

  const res = await fetch(`/api/search?${query}`)
  const data = await res.json()
  assets.value = data.assets
}

function handleSearch(params) {
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
  currentPack.value = packName
  await search({ q: null, tag: [], color: null, pack: packName, type: null })
}

function viewPack(packName) {
  selectedAsset.value = null
  window.history.pushState({ route: 'pack', name: packName }, '', `/pack/${packName}`)
  loadPack(packName)
}

function clearPack() {
  currentPack.value = null
  window.history.pushState({ route: 'home' }, '', '/')
  search({ q: null, tag: [], color: null, pack: null, type: null })
}

watch(selectedAsset, (newVal, oldVal) => {
  if (oldVal !== null && newVal === null && !skipNextPush) {
    window.history.pushState({ route: 'home' }, '', '/')
  }
  skipNextPush = false
})

function handlePopState(event) {
  const route = parseRoute(window.location.pathname)
  skipNextPush = true
  if (route.name === 'home') {
    selectedAsset.value = null
    currentPack.value = null
    search({ q: null, tag: [], color: null, pack: null, type: null })
  } else if (route.name === 'asset') {
    selectAssetFromUrl(route.params.id)
  } else if (route.name === 'similar') {
    selectedAsset.value = null
    currentPack.value = null
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

onMounted(() => {
  fetchFilters()
  search({ q: null, tag: [], color: null, pack: null, type: null })
  handleInitialRoute()
  window.addEventListener('popstate', handlePopState)
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem;
}

h1 {
  margin-top: 0;
}
</style>
