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
uv run assetindex.py /path/to/assets --db assets.db

# Incremental update
uv run assetindex.py --update
```

### Search Assets

```bash
# Search by name
uv run assetsearch.py goblin

# Search by tags
uv run assetsearch.py --tag creature --tag attack

# Search by color
uv run assetsearch.py --color red
uv run assetsearch.py --color "#ff5500"

# Find similar assets
uv run assetsearch.py --similar reference.png

# Filter by pack
uv run assetsearch.py --pack creatures
```

### Utilities

```bash
uv run assetsearch.py packs    # List all packs
uv run assetsearch.py tags     # List all tags
uv run assetsearch.py info 42  # Asset details by ID
uv run assetsearch.py stats    # Index statistics
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
uv run pytest test_assetindex.py
```

## Supported Formats

PNG, GIF, JPG, WEBP, Aseprite (.ase, .aseprite)
