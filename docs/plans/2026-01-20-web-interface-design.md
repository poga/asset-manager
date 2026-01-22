# Web Interface for Asset Search

## Overview

Vue 3 web interface with instant search for the asset-manager CLI tool. Focus on quick, comprehensive search rather than fancy UI.

## Requirements

- Instant search (no submit button, search as you type)
- All search modes: text, tags, color, pack, file type
- "Find similar" for visual similarity (click a result to find similar)
- Grid of thumbnails as primary view
- Modal for asset details

## Architecture

**Frontend:** Vue 3 SPA with composition API
- Single search view with grid results
- Reactive instant search (debounced 150-200ms)
- Modal component for asset details

**Backend:** FastAPI server wrapping existing search logic
- Reuses `search.py` query functions directly
- Serves asset images from original paths
- JSON API responses

**Testing (TDD):**
- API tests: pytest for each endpoint before implementation
- Component tests: Vitest + Vue Test Utils

## File Structure

```
web/
├── api.py              # FastAPI server
├── test_api.py         # API tests (written first)
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── SearchBar.vue
│   │   │   ├── AssetGrid.vue
│   │   │   └── AssetModal.vue
│   │   └── main.js
│   ├── tests/
│   │   ├── SearchBar.test.js
│   │   ├── AssetGrid.test.js
│   │   └── AssetModal.test.js
│   └── package.json
```

## API Endpoints

### GET /api/search

Query params:
- `q` - text search (filename/path matching)
- `tag` - tag filter (repeatable, AND logic)
- `color` - color filter (hex or named)
- `pack` - pack name filter
- `type` - file type filter
- `limit` - max results (default 100)

Response:
```json
{
  "assets": [
    {
      "id": 42,
      "path": "/assets/creatures/goblin_attack.png",
      "filename": "goblin_attack.png",
      "pack": "creatures",
      "tags": ["creature", "goblin", "attack"],
      "width": 64,
      "height": 64
    }
  ],
  "total": 1
}
```

### GET /api/similar/{asset_id}

Query params:
- `limit` - max results (default 20)
- `distance` - max hamming distance (default 15)

Returns same structure as search.

### GET /api/asset/{asset_id}

Returns full asset details: path, pack, tags, colors, dimensions, frame count, related assets.

### GET /api/image/{asset_id}

Serves the actual image file.

### GET /api/filters

Returns available filter options: all packs, top tags, color names.

## Frontend Components

### App.vue
- Contains SearchBar, AssetGrid, AssetModal
- Manages state: searchQuery, filters, results, selectedAsset
- Watches inputs, debounces, fetches from API

### SearchBar.vue
- Text input with placeholder "Search assets..."
- Inline filter dropdowns: pack, tag (multi-select), color, type
- Emits filter changes immediately

### AssetGrid.vue
- CSS Grid of thumbnail images
- Each cell: image + filename
- Click emits select event
- Shows result count

### AssetModal.vue
- Large image, full path, pack, dimensions, frame count
- Tags as chips, colors as swatches
- Related assets
- "Find Similar" button
- Click outside or X to close

## UI Behavior

- Instant search starting at 0 characters (show all results initially)
- Debounce 150-200ms on input
- Default limit 100 results
- Grid thumbnails use original images (no thumbnail generation)
- Modal opens on asset click, "Find Similar" triggers new search

## TDD Implementation Order

### Phase 1: API Backend
1. Write tests for /api/search
2. Implement /api/search
3. Write tests for /api/similar/{asset_id}
4. Implement similar endpoint
5. Write tests for /api/asset/{asset_id} and /api/filters
6. Implement those endpoints
7. Implement /api/image/{asset_id}

### Phase 2: Vue Frontend
1. Set up Vue project with Vitest
2. Write SearchBar tests → implement
3. Write AssetGrid tests → implement
4. Write AssetModal tests → implement
5. Wire up App.vue with API integration

### Phase 3: Integration
1. Manual testing of full flow
2. Adjust debounce timing, result limits as needed
