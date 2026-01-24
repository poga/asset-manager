# Assets Manager

A SQLite-based indexing and search system for game development assets. Index sprites, animations, and textures with intelligent auto-tagging, color search, and visual similarity matching.

## Features

- **Smart Indexing** - Scans directories, extracts metadata, detects sprite sheets
- **Auto-Tagging** - Tags from paths, filenames, and animation metadata
- **Color Search** - Find assets by dominant colors
- **Visual Similarity** - Find similar assets using perceptual hashing
- **Relationship Detection** - Links sprites to shadows and GIF previews
- **Pack Previews** - Auto-generates 4x4 montage thumbnails

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (dependencies are managed inline)

## Usage

### Index Assets

```bash
# Initial index
uv run index.py index /path/to/assets --db assets.db

# Incremental update (re-run index command, skips unchanged files)
uv run index.py index /path/to/assets --db assets.db
```

### Search Assets

```bash
# Search by name
uv run search.py search goblin

# Search by tags
uv run search.py search --tag creature --tag attack

# Search by color
uv run search.py search --color red
uv run search.py search --color "#ff5500"

# Find similar assets
uv run search.py similar reference.png

# Filter by pack
uv run search.py search --pack creatures
```

### Utilities

```bash
uv run search.py packs    # List all packs
uv run search.py tags     # List all tags
uv run search.py info 42  # Asset details by ID
uv run search.py stats    # Index statistics
```

## Database Schema

- `packs` - Asset pack metadata (name, path, version)
- `assets` - Individual files (path, hash, dimensions, frames)
- `tags` / `asset_tags` - Searchable tags
- `asset_colors` - Dominant colors per asset
- `asset_phash` - Perceptual hashes for similarity
- `asset_relations` - Links between sprites, shadows, GIFs

## Testing

```bash
uv run pytest test_index.py
```

## Supported Formats

PNG, GIF, JPG, WEBP, Aseprite (.ase, .aseprite)

## Web Interface

A web UI for browsing and searching assets.

### Folder Structure

```
asset-manager/
├── assets/              # Asset images (required)
│   ├── PackName1/
│   │   └── images...
│   └── PackName2/
│       └── images...
├── assets.db            # SQLite database (required)
└── web/
    ├── api.py           # Backend API
    └── frontend/        # Vue.js frontend
```

- **`assets.db`** - Place at project root. The API searches upward from CWD to find it.
- **`assets/`** - Place at project root. Paths in the database are relative to this folder.

### Running the Web Interface

```bash
# Start backend (from project root)
uv run web/api.py

# Start frontend (in separate terminal)
cd web/frontend
npm install
npm run dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### API Endpoints

- `GET /api/search` - Search assets (query params: `q`, `tag`, `color`, `pack`, `type`, `limit`)
- `GET /api/image/{id}` - Serve asset image
- `GET /api/asset/{id}` - Asset details
- `GET /api/similar/{id}` - Find visually similar assets
- `GET /api/filters` - Available filter options
