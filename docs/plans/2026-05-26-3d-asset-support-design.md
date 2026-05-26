# 3D Asset Support — Design

**Status:** approved
**Date:** 2026-05-26
**Driver:** KayKit Collection v5 (~23 sub-packs, glTF/GLB/FBX/OBJ models, some rigged with animations)

## Goal

Extend the asset manager to index, browse, search, and view 3D assets alongside the existing 2D assets. Browsing must feel uniform — 2D and 3D assets share the grid, pack list, search, and cart. 3D assets get an interactive viewer with animation playback in the detail view.

## Non-goals

- Format conversion between glTF/FBX/OBJ
- Drag-and-drop import from arbitrary file managers
- Editing animations or rigs
- Rendering 3D thumbnails in the browser (server-side only)
- Color search / perceptual-hash similarity for 3D assets

## Key decisions

| Decision | Choice |
|---|---|
| Scope | Full 3D: indexing + interactive viewer + animation playback |
| Canonical format | `.glb` if present, else `.gltf` (with sibling `.bin` + textures) |
| Skipped formats | `.fbx`, `.obj` not indexed (still on disk; unused) |
| Thumbnails | First match `Samples/<name>.png` (case-insensitive). Else render offscreen with `trimesh` at index time. Else placeholder. |
| Animations | Parse glTF `animations[]`. Animation-only files (no mesh) become `asset_kind='animation_bundle'`, linked to character meshes sharing the same `rig`. |
| Pack location | User flattens the collection: `mv ~/Documents/The\ Complete\ KayKit\ Collection\ v5/KayKit\ * assets/` so each sub-pack sits directly under `assets/`. No indexer changes for grouping. |
| Color / phash | Skipped for 3D (NULL). 2D pipeline unchanged. |
| Schema strategy | Additive: extend the existing `assets` table with three nullable columns + one new `asset_animations` table. Reuse `asset_relations` for character↔bundle. |

## Architecture

```
asset-manager/
├── index.py                          extended: dispatch to model_indexer for .glb/.gltf
├── model_indexer.py                  NEW: parse glTF, match samples, render fallback,
│                                          enumerate clips, infer rig
├── search.py                         extended: projection only — include kind/rig/thumbnail
├── web/api.py                        extended: /asset/{id}/model, /asset/{id}/animations
│                                                /assets serializes asset_kind, rig, thumbnail_path
└── web/frontend/src/components/
    ├── AssetGrid.vue                 unchanged
    ├── AssetDetail.vue               branches on asset_kind
    └── ModelViewer.vue               NEW: <model-viewer> wrapper + clip dropdown
```

### Data flow — 3D path

1. `scan_assets` walks `assets/`, finds `.glb` and `.gltf` files
2. Canonical-format filter: when both `Knight.glb` and `Knight.gltf` exist in the same directory, drop the `.gltf`
3. `model_indexer.parse(path)` reads the file's glTF JSON (binary chunk for `.glb`, plain JSON for `.gltf`) and returns `ModelInfo`
4. `resolve_thumbnail` tries `Samples/<stem>.png` (case-insensitive, walking up pack root) → falls back to `render_model_thumbnail` → falls back to NULL
5. Row inserted into `assets` with `asset_kind`, `rig`, `thumbnail_path` populated
6. Tags extracted from path (existing logic) + `'3d'` tag injected
7. Post-pass per pack: link every character mesh to every animation_bundle with matching `rig` via `asset_relations(relation_type='animation_for_rig')`

### Frontend flow

- **Grid:** unchanged. `<img src=thumbnail_path>` works for both kinds because thumbnails are PNG in either case.
- **Detail:** `v-if="asset.kind === 'model'"` mounts `ModelViewer.vue` (which loads `<model-viewer src="/asset/{id}/model">`). Otherwise existing `<img>` flow.
- **ModelViewer** fetches `/asset/{id}/animations`, merges the character's own embedded clips with rig-compatible bundle clips into a flat dropdown, controls play/pause.

## Data model

### Migrations on `assets` table (additive)

```sql
ALTER TABLE assets ADD COLUMN asset_kind     TEXT NOT NULL DEFAULT 'image';
ALTER TABLE assets ADD COLUMN rig            TEXT;
ALTER TABLE assets ADD COLUMN thumbnail_path TEXT;
CREATE INDEX idx_assets_kind ON assets(asset_kind);
CREATE INDEX idx_assets_rig  ON assets(rig);
```

`asset_kind` values:
- `'image'` — existing 2D asset (DEFAULT — backfills automatically)
- `'model'` — 3D mesh (.glb/.gltf), may or may not be rigged
- `'animation_bundle'` — 3D file with animations but no mesh (e.g. `Rig_Medium_General.glb`)

`rig` values (free-form, but indexed): `'Rig_Medium'`, `'Rig_Large'`, `'Rig_Small'`, ... NULL for non-rigged.

`thumbnail_path` is a relative path under `assets/` (or under `.index/thumbs/` for rendered fallbacks). The web API serves both transparently.

### New table

```sql
CREATE TABLE asset_animations (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    clip_index INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(asset_id, clip_index)
);
CREATE INDEX idx_asset_animations_asset ON asset_animations(asset_id);
```

Populated only for `animation_bundle` assets (and for `model` assets that happen to embed their own clips).

### Reused tables

- `asset_relations(from_asset_id, to_asset_id, relation_type)` — `relation_type='animation_for_rig'` links character mesh → animation bundle. Inferred at index time by matching `rig`. Scoped to within a single pack to avoid cross-pack noise.
- `asset_tags` — same path-based extraction; additionally inject `'3d'` for any 3D asset
- `asset_colors`, `asset_phash` — skipped for 3D (no rows inserted)

### Untouched fields on 3D rows

`width`, `height`, `preview_x/y/width/height` remain NULL. The frontend already tolerates NULL there.

## Indexing pipeline

### File discovery

```python
MODEL_EXTENSIONS = {".glb", ".gltf"}
# scan_assets extends to glob MODEL_EXTENSIONS in addition to IMAGE_EXTENSIONS/ASEPRITE_EXTENSIONS
```

### Canonical-format filter

A pass after `scan_assets`, before per-file indexing:

- Group scanned 3D files by `(parent_dir, file_stem)`
- If both `.glb` and `.gltf` versions exist, drop the `.gltf`
- Operates on the in-memory file list only — files stay on disk untouched

### `model_indexer.parse(path) → ModelInfo`

```python
@dataclass
class ModelInfo:
    rig: Optional[str]               # 'Rig_Medium' | 'Rig_Large' | 'Rig_Small' | None
    animations: list[str]            # clip names from glTF animations[]
    has_mesh: bool                   # False → animation_bundle
    referenced_files: list[str]      # .bin / textures listed in buffers[] / images[]
```

Implementation:

- For `.gltf`: `json.load(open(path))`
- For `.glb`: parse the 12-byte file header (magic `0x46546C67`, version, length), then the first chunk (`JSON` type), no third-party dep needed
- `animations`: `[a.get("name", f"clip_{i}") for i, a in enumerate(j.get("animations") or [])]`
- `has_mesh`: `bool(j.get("meshes"))`
- `rig`: regex `r"Rig_(Large|Medium|Small)"` on the filename first. If no match, inspect skeleton root node names. If still no match, NULL.
- `referenced_files`: union of `buffers[].uri` and `images[].uri` (non-data-URI entries only)

### `resolve_thumbnail(model_path, pack_root) → str | None`

1. Walk from `model_path.parent` upward until hitting `pack_root`. At each level, check `Samples/<stem>.png` (case-insensitive). Take the first match.
2. If no match: call `render_model_thumbnail(model_path, .index/thumbs/<asset_id>.png, size=256)`. Uses `trimesh.load(path)` + `scene.save_image(resolution=(256,256), visible=False)`. Pyglet hidden-window mode on macOS.
3. If rendering raises: log a warning and return NULL. Frontend shows a 3D-cube placeholder.

### Animation-bundle linking

Run as a post-pass per pack (after all of that pack's 3D files are indexed):

```python
chars   = assets where pack_id=p AND asset_kind='model'            AND rig IS NOT NULL
bundles = assets where pack_id=p AND asset_kind='animation_bundle' AND rig IS NOT NULL
for c in chars:
    for b in bundles where b.rig == c.rig:
        INSERT OR IGNORE INTO asset_relations(from_asset_id=c.id, to_asset_id=b.id, relation_type='animation_for_rig')
```

### Tag injection

Existing `extract_tags_from_path` runs as-is. Additionally, for any 3D asset, append `'3d'` so users can filter "models only" via the existing tag chip UI.

### Re-indexing safety

- The existing file-hash incremental check applies to 3D files too — binary glb is hashed normally
- Re-render only when hash changes or `--force` is passed
- Schema migration is idempotent (`ALTER TABLE ... DEFAULT` on existing tables won't re-run because the column already exists; we use `IF NOT EXISTS` semantics via `PRAGMA table_info` check before each ALTER)

### Dependencies

- Add `trimesh[easy]` to `index.py`'s inline deps block (pulls `pyglet>=2.0`). One new dep.
- No node packages added on the indexer side.

## Web API

### New endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/asset/{id}/model` | Returns the canonical 3D file (`.glb` or `.gltf`) with correct content-type. |
| `GET` | `/asset/{id}/model/{filename}` | Serves a sibling file (e.g. `foo.bin`, texture PNGs) from the same directory as the asset's model. Path-traversal safe. |
| `GET` | `/asset/{id}/animations` | Returns `[{bundle_id, bundle_name, clips: [{name, gltf_name}]}, ...]`. The asset's own clips appear first (bundle_id = asset.id); then each rig-compatible bundle, in indexed order. |

### Modified endpoints

- `/assets` and `/asset/{id}` JSON now serialize `kind`, `rig`, `thumbnail_path` alongside existing fields. Existing 2D consumers ignore them.
- `/assets?kind=model` — new filter; uniform with existing `?pack=...&color=...` filters.
- `/cart/export` — when including 3D assets, also bundle `referenced_files` (the sibling `.bin` and textures) so the exported zip is self-contained.

### Content types

- `.glb` → `model/gltf-binary`
- `.gltf` → `model/gltf+json`
- `.bin` → `application/octet-stream`

## Frontend

### `ModelViewer.vue` (new)

Thin wrapper around Google's `<model-viewer>` web component. The component loads via a `<script type="module">` tag in `index.html` (self-hosted from `web/frontend/public/model-viewer.min.js` for offline reliability — pinned to v4.x).

```vue
<template>
  <div class="model-viewer-wrap">
    <model-viewer
      ref="viewer"
      :src="`/asset/${assetId}/model`"
      camera-controls
      auto-rotate
      shadow-intensity="1"
      exposure="1"
      :animation-name="selectedClip?.gltfName"
      :autoplay="isPlaying"
    />
    <div v-if="clips.length" class="anim-controls">
      <select v-model="selectedClip">
        <option v-for="c in clips" :key="`${c.bundleId}:${c.gltfName}`" :value="c">
          {{ c.bundleName }} › {{ c.name }}
        </option>
      </select>
      <button @click="isPlaying = !isPlaying">{{ isPlaying ? '⏸' : '▶' }}</button>
    </div>
  </div>
</template>
```

Props: `assetId: number`.
On mount: fetches `/asset/{id}/animations`. Flattens result into `clips`. Auto-selects first clip if available.

### `AssetDetail.vue` (modified)

```vue
<ModelViewer v-if="asset.kind === 'model'" :asset-id="asset.id" />
<img v-else :src="imageUrl" />
```

All other parts of the detail view (metadata panel, tag chips, cart button) stay identical.

### `AssetGrid.vue` (unchanged)

The grid card already binds to a `thumbnail_path`-equivalent field. 3D and 2D look the same.

### `SearchBar.vue` (one-line addition)

Add a "Models only" toggle that sets `kind=model` on the search query. Mirrors existing pack/color filters. The `'3d'` tag chip also works for the same filter naturally.

## Pack setup

One-time manual step the user runs once:

```bash
mv ~/Documents/The\ Complete\ KayKit\ Collection\ v5/KayKit\ * \
   ~/projects/asset-manager/assets/
```

After this, `assets/` looks like:

```
assets/
├── KayKit Adventurers 2.0/
├── KayKit Dungeon Remastered 1.1/
├── ... 23 sub-packs ...
├── Minifantasy_AMyriadOfNPCs_v.1.0/   (untouched existing 2D packs)
└── ...
```

The existing `detect_pack` already uses `rel_path.parts[0]` — no indexer change for grouping. Each KayKit sub-pack becomes a normal pack in the UI.

## Testing

Following the project's testing rules: no mocks; real files; assert observable outcomes.

### Fixtures

A handful of small, real glTF files in `tests/fixtures/`:

- One Khronos sample (`BoxAnimated.glb`, ~10KB) — known-good baseline
- 2–3 KayKit files copied into the fixtures dir at fixture-setup time (small enough: a few hundred KB each)

### `test_model_indexer.py` (new)

| Test | Asserts |
|---|---|
| `test_parse_glb_with_mesh` | Real `Knight.glb` → `has_mesh=True`, `rig='Rig_Medium'`, `animations==[]` |
| `test_parse_animation_bundle` | Real `Rig_Medium_General.glb` → `has_mesh=False`, `rig='Rig_Medium'`, animation list non-empty and contains an `'Idle'`-style entry |
| `test_parse_gltf_with_external_bin` | Real `axe_1handed.gltf` → `referenced_files` includes its `.bin` sibling |
| `test_canonical_format_filter` | Folder containing both `Knight.glb` and `Knight.gltf` → scan returns only `.glb` |
| `test_sample_match_case_insensitive` | Model `Characters/gltf/Knight.glb` with `Samples/knight.png` → `thumbnail_path` set to the Sample |
| `test_thumbnail_fallback_renders_png` | Asset with no Sample match → renders to `.index/thumbs/<id>.png`, file non-empty, dims 256×256 |
| `test_thumbnail_fallback_returns_null_on_render_failure` | Corrupted glb → returns NULL, no crash |

### `test_index.py` (additions)

| Test | Asserts |
|---|---|
| `test_index_3d_pack_end_to_end` | Fixture pack with 1 character glb + 1 anim bundle: after `index()`, DB has 2 asset rows with correct `asset_kind`, `asset_animations` rows populated, one `asset_relations` row linking character → bundle with `relation_type='animation_for_rig'` |
| `test_reindex_skips_unchanged_3d` | Re-running index without changes produces 0 new rows for the 3D assets |
| `test_existing_2d_assets_unaffected` | Pack with both a `Knight.glb` and `Knight_portrait.png`: both indexed; 2D row has `asset_kind='image'`; no regression in colors/phash for the 2D row |

### `test_api.py` (additions)

| Test | Asserts |
|---|---|
| `test_get_model_serves_glb` | `GET /asset/{id}/model` returns bytes starting with `glTF` magic, content-type `model/gltf-binary` |
| `test_get_model_serves_gltf_with_sibling_bin` | `GET /asset/{id}/model` returns the `.gltf` JSON; `GET /asset/{id}/model/foo.bin` returns the `.bin` bytes; path-traversal (`../`) is rejected with 400 |
| `test_animations_endpoint` | Character with one linked bundle → response merges character's own clips first, then bundle's clips |
| `test_kind_filter` | `GET /assets?kind=model` returns only 3D rows |
| `test_cart_export_includes_referenced_files` | Export of a `.gltf` asset includes both the `.gltf` and its `.bin` in the zip |

### Frontend tests

One focused test (UI tests are expensive):

| Test | Asserts |
|---|---|
| `AssetDetail.spec.ts` | Given `kind='model'` asset, renders a `<model-viewer>` element (not `<img>`); given `kind='image'`, renders `<img>` (not `<model-viewer>`) |

### Out-of-scope tests (per project testing rules)

- model-viewer's rendering quality (3rd-party)
- trimesh's render quality (3rd-party)
- Exact strings of designer-authored clip names (designer-adjustable)
- Tag extraction from path (already covered for 2D, same code path)
- Default values of new columns (engine guarantee)

### Manual verification at the end

1. `just test` — all tests pass
2. `just reindex-assets` — full reindex of real KayKit collection completes without crash
3. Browser smoke: open frontend, pick a KayKit character → viewer rotates, animation dropdown lists clips, clip plays smoothly
4. Browser smoke: open an existing 2D asset → grid + detail still work identically (no 2D regression)
5. Cart smoke: add one 3D + one 2D asset, export, verify zip contains both plus the 3D asset's `.bin` sibling

## Risks and fallbacks

- **`trimesh` headless rendering unreliable on macOS.** Fallback chain (`Samples` match → render → NULL placeholder) means we can ship with placeholders for some assets and improve later. Per-asset, never a crash.
- **glTF files referencing missing buffers/textures.** Indexer warns at index time and still creates the row. Viewer in the browser will surface the failure visually; not our problem to fix beyond logging.
- **Cross-pack rig name collisions** (two unrelated packs both using `Rig_Medium`). Mitigated by scoping the linking pass to within a single pack.
- **`<model-viewer>` web component bundle size.** ~600KB. Self-hosted, served once, cached. Acceptable for a local dev tool.

## Out of scope (future work)

- FBX / OBJ indexing
- 3D-specific perceptual similarity (could use shape descriptors)
- Bulk thumbnail re-render command (`index.py rerender-thumbs`)
- Configurable rendering backend (Blender headless as a higher-quality alternative)
- AR / USDZ export
