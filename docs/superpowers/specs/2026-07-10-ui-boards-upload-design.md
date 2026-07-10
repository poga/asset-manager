# UI-Created Boards (Pinterest-style upload) — Design

**Date:** 2026-07-10
**Status:** Approved, pending implementation plan

## Problem

Today the only way assets enter the system is the disk-first CLI pipeline:
`index.py` scans `assets/<pack>/` directories and populates `assets.db`. The web
UI (Vue + FastAPI) is read-only. Users want to **create asset packs directly in
the UI and upload images into them, Pinterest-style** — a write path that does
not exist yet.

## Scope

Uploaded images are **lightweight reference / mood-board content**, not deeply
indexed game assets. Confirmed decisions:

- **Purpose:** reference / mood boards. Store the file, capture basic info, show
  it in the grid. No color extraction, no perceptual hash, no similarity.
- **Data model:** boards live in the *same* PackGallery as indexed packs,
  distinguished by a flag/badge. Reuse the `packs` table.
- **Upload UX:** drag-and-drop files + a file-picker button. No clipboard paste,
  no add-from-URL.
- **Management (all v1):** remove an image from a board, delete/rename a board,
  choose the cover image, tag images.

## Non-goals (v1)

- Generated thumbnail derivatives (serve originals; personal-scale boards).
- Clipboard paste and add-from-URL upload.
- True masonry layout (reuse existing grid; masonry is later polish).
- Color / similarity / phash indexing of uploaded images.

## Data model

Add one column to `packs`:

- `source TEXT DEFAULT 'indexed'` — boards are `source = 'user'`.

A board is an ordinary pack row:

- `name` — user-supplied board name (unique).
- `path = '.boards/<slug>'` — slug derived from the name at creation; stays fixed
  for the board's lifetime so files never move on rename. Slug uniqueness is
  enforced independently of name (append `-2`, `-3`, … on collision), since two
  distinct names can slugify to the same string.
- `source = 'user'`.
- `preview_path` — points at the chosen cover image (reuses existing cover
  mechanism).

Uploaded images are ordinary `assets` rows:

- `pack_id` = the board.
- `path = '.boards/<slug>/<uuid>.<ext>'` (relative to assets root, like every
  other asset).
- `width` / `height` captured on upload (cheap, enables future masonry).
- Preview bounds = full image (null bounds already mean "use the whole image").
- **No** rows written to `asset_colors` / `asset_phash`.

## Storage on disk

Files land under `assets/.boards/<board-slug>/<uuid>.<ext>`.

Two consequences follow from keeping board files *under* the assets root but in a
dot-prefixed directory:

1. **Serving is unchanged.** `/api/image/{id}` resolves `assets_dir / row.path`;
   board paths are relative to the assets root exactly like indexed assets, so no
   new serving code is required.
2. **Reindex safety.** `scan_assets` is taught to skip hidden directories (any
   path segment starting with `.`, which covers `.boards/`). `index.py` therefore
   never scans, re-pipelines, or prunes board files. This is the entire reason
   files live under a dot-dir rather than a normal pack directory.

Upload constraints: accept `png`, `jpg`/`jpeg`, `gif`, `webp`; reject files over
~20 MB.

## API — new write endpoints

The API becomes a writer (previously read-only). All writes use short
transactions to coexist with the CLI indexer.

- `POST /api/boards` — body `{name, tags?}`. Creates the board pack
  (`source='user'`, `path='.boards/<slug>'`), applies optional pack-level tags,
  returns the board. Rejects duplicate names.
- `POST /api/boards/{id}/images` — multipart, one or more files. Validates
  type/size, writes each file to the board directory with a uuid name, inserts an
  asset row (width/height, full-image preview bounds). If the board has no cover
  yet, the first uploaded image becomes the cover. Returns the created assets.
- `PATCH /api/boards/{id}` — body `{name?, cover_asset_id?}`. Rename updates
  `packs.name` only (slug/path unchanged). `cover_asset_id` sets `preview_path`
  to that image (must belong to the board).
- `DELETE /api/boards/{id}` — deletes the board row, its image rows and tag
  links, and removes the board directory from disk. Guarded to `source='user'`.
- `DELETE /api/asset/{id}` — removes a single image: asset row, its tag links,
  and the file on disk. Guarded to assets whose pack is `source='user'`.
- `POST /api/asset/{id}/tags` — body `{tag}`. Adds a manual tag (reuses `tags` /
  `asset_tags`, source `'user'`).
- `DELETE /api/asset/{id}/tags/{tag}` — removes a manual tag.

`/api/filters` gains `is_board` per pack (from `source`) so the frontend can
badge boards.

Guards return `404`/`400` (not `500`) when an id is missing, an asset isn't a
board asset, or a name collides.

## Frontend

- **PackGallery:** a "+ New board" card (name + optional tags → `POST /api/boards`
  → navigate to the board). Boards render with a `BOARD` badge driven by
  `is_board`.
- **Board view:** reuses the existing `/pack/:name` route and `AssetGrid`. Adds:
  - a drop-zone overlay + "Add images" button (drag-drop and file picker, both
    → `POST /api/boards/{id}/images`);
  - per-image hover menu: Set as cover / Add tag / Remove;
  - board header menu: Rename / Delete.
- Reuses the existing grid for layout consistency; masonry is deferred.

## Search behaviour (confirmed)

Board images are real `asset` rows, so they appear in normal search by filename
and by the tags the user adds — this is exactly what makes "tag images →
findable" work. They contribute nothing to color or similarity search (no data
written there). **No special exclusion in v1.**

## Testing (TDD, no mocks)

Real FastAPI app against a temp DB and temp assets dir; real image bytes.

- **Board lifecycle:** create board → upload real image → assert asset row + file
  on disk → set cover (`preview_path` updated) → add/remove tag → remove image
  (row + file gone) → delete board (dir gone, rows gone).
- **Upload validation:** oversized / wrong-type file rejected with 4xx, no row or
  file written.
- **Guards:** `DELETE /api/asset/{id}` refuses a non-board (indexed) asset;
  duplicate board name refused.
- **Reindex isolation:** seed a board, run `index.py` indexing against the assets
  root, assert `.boards/` files are not scanned and the board's rows/cover survive
  unchanged.

Order matches the real flow (create → upload → first-tick equivalent of cover
assignment → mutate → delete); assertions are on observable outcomes (file on
disk, row present/absent, cover pointer) rather than internal counters.
