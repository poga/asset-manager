<template>
  <div class="app">
    <h1>Asset Search</h1>

    <SearchBar :filters="filters" @search="handleSearch" />

    <AssetGrid :assets="assets" @select="selectAsset" />

    <AssetModal
      v-if="selectedAsset"
      :asset="selectedAsset"
      @close="selectedAsset = null"
      @find-similar="findSimilar"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SearchBar from './components/SearchBar.vue'
import AssetGrid from './components/AssetGrid.vue'
import AssetModal from './components/AssetModal.vue'

const filters = ref({ packs: [], tags: [], colors: [] })
const assets = ref([])
const selectedAsset = ref(null)

let debounceTimer = null

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
}

async function findSimilar(id) {
  selectedAsset.value = null
  const res = await fetch(`/api/similar/${id}`)
  const data = await res.json()
  assets.value = data.assets
}

onMounted(() => {
  fetchFilters()
  search({ q: null, tag: [], color: null, pack: null, type: null })
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
