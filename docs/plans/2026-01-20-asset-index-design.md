# Game Asset Index Design

A SQLite-based index for managing game development assets with search, autotagging, and visual similarity features.

## Goals

- Single-file SQLite database (portable, shareable)
- Fast filename, tag, and color-based search
- Automatic tagging from paths, metadata, and image analysis
- Visual similarity search via perceptual hashing
- Optional semantic search via CLIP embeddings
- Easy deployment: single uv script with inline dependencies

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SQLite Database                       │
│              (single file: assets.db)                   │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
        ┌─────────────────┼─────────────────┐
        ▼                                   ▼
┌───────────────────┐              ┌───────────────────┐
│   index.py   │              │  search.py   │
│  (build/update)   │              │  (query - daily)  │
│                   │              │                   │
│  pillow, imagehash│              │  rich, typer only │
└───────────────────┘              └───────────────────┘
```

## Database Schema

### Core Tables

```sql
-- Asset packs (top-level grouping)
CREATE TABLE packs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    version TEXT,
    preview_path TEXT,
    preview_generated BOOLEAN,
    asset_count INTEGER,
    indexed_at TIMESTAMP
);

-- Individual asset files
CREATE TABLE assets (
    id INTEGER PRIMARY KEY,
    pack_id INTEGER REFERENCES packs(id),
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    filetype TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    frame_count INTEGER,
    frame_width INTEGER,
    frame_height INTEGER,
    category TEXT,
    indexed_at TIMESTAMP
);

-- Related assets (sprite <-> shadow <-> gif <-> metadata)
CREATE TABLE asset_relations (
    asset_id INTEGER REFERENCES assets(id),
    related_id INTEGER REFERENCES assets(id),
    relation_type TEXT,
    PRIMARY KEY (asset_id, related_id)
);

-- Tags (many-to-many)
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE asset_tags (
    asset_id INTEGER REFERENCES assets(id),
    tag_id INTEGER REFERENCES tags(id),
    source TEXT,
    PRIMARY KEY (asset_id, tag_id)
);
```

### Visual Search Tables

```sql
-- Dominant colors per asset
CREATE TABLE asset_colors (
    asset_id INTEGER REFERENCES assets(id),
    color_hex TEXT,
    percentage REAL,
    PRIMARY KEY (asset_id, color_hex)
);

-- Perceptual hash for similarity
CREATE TABLE asset_phash (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    phash BLOB
);

-- Optional CLIP embeddings
CREATE TABLE asset_embeddings (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    embedding BLOB
);
```

## Autotagging System

### Tag Sources

1. **Path-based extraction**
   - Split path on `/` and `_`
   - Normalize: lowercase, strip version numbers, skip noise words
   - Action detection from filename endings (Attack, Idle, Walk, Die, Dmg)

2. **Metadata file parsing**
   - Parse `_AnimationInfo.txt` for frame size and duration
   - Add tags like `32x32`, `animated`

3. **Image analysis**
   - Frame count detection from spritesheet dimensions
   - Dominant color extraction
   - Transparency detection

### Tag Normalization

```python
TAG_ALIASES = {
    "dmg": "damage",
    "atk": "attack",
    "char": "character",
}

TAG_HIERARCHY = {
    "skeleton": ["undead", "creature"],
    "goblin": ["humanoid", "creature"],
}
```

## Search Capabilities

### Exact Search
```python
db.search(filename="goblin")
db.search(pack="creatures")
db.search(path="undead/skeleton")
```

### Tag Search
```python
db.search(tags=["goblin", "attack", "32x32"])
db.search(tags=["goblin", "skeleton"], match="any")
db.search(tags=["creature"], exclude_tags=["undead"])
```

### Color Search
```python
db.search(color="#4a7c59")
db.search(color="green")
db.search(colors=["green", "brown"], threshold=0.2)
```

### Similarity Search
```python
db.similar(asset_id=123, limit=10)
db.similar(path="Goblin/GoblinIdle.png")
db.similar(image="./reference.png")
```

### Semantic Search (optional)
```python
db.semantic("medieval knight with sword")
```

## CLI Interface

```bash
# Index your assets
uv run index.py ./assets --db assets.db
uv run index.py --update              # incremental update

# Search
uv run search.py goblin
uv run search.py --tag creature --tag attack
uv run search.py --pack creatures --color green
uv run search.py --similar ./reference.png

# Utilities
uv run search.py --packs              # list all packs
uv run search.py --tags               # list all tags
uv run search.py --info <id>          # asset details
```

## File Structure

```
index.py           # Indexer script (heavier deps)
search.py          # Search script (minimal deps)

your-assets-folder/
├── assets.db           # The index (shareable)
├── .index/
│   └── previews/       # Auto-generated pack previews
└── assets/
    └── minifantasy/
        └── ...
```

## Dependencies

**search.py** (daily use):
- rich
- typer

**index.py** (indexing):
- pillow
- imagehash
- rich
- typer

## Pack Previews

1. Look for existing: `preview.png`, `cover.png`, `thumbnail.png`
2. Check for concept art in `_ConceptArt/`
3. Auto-generate: 4x4 grid montage from representative assets

## Implementation Phases

### Phase 1: Core Index (MVP)
- Schema creation and DB setup
- File scanner with hash-based change detection
- Basic metadata extraction
- Path-based autotagging
- CLI: `init`, `update`, `search`

### Phase 2: Visual Search
- Color palette extraction
- Perceptual hash computation
- Pack preview generation
- CLI: `--color`, `--similar`

### Phase 3: Enhanced Tagging
- Parse `_AnimationInfo.txt`
- Spritesheet frame detection
- Asset relationship linking
- Tag hierarchy/aliases

### Phase 4: Optional Embeddings
- CLIP integration (separate script)
- Semantic search

## Deferred (YAGNI)

- GUI
- Watch mode / live updates
- Web interface
- Multi-user / server mode
