# Font + Anyfile Asset Support

**Date:** 2026-07-11
**Status:** Approved

## Goal

Two new asset kinds:

- **`font`** (`.ttf .otf .woff .woff2`) — indexed with a rendered specimen
  thumbnail, browsable in the grid, live type tester in the detail view,
  downloadable.
- **`file`** (catch-all) — any file no other handler claims (shaders, .blend,
  zips, licenses, ...). No preview; a labeled card and a download button.

Delivered on top of a refactor of the indexing pipeline into a kind-handler
registry (user-selected approach).

## Decisions (from brainstorming)

1. **Anyfile scope:** catch-all + junk denylist. Every unrecognized file is
   indexed as `kind='file'`; a small denylist skips OS/engine junk.
2. **Font preview:** Pillow specimen thumbnail for the grid **plus** a live
   `@font-face` type tester in the detail view.
3. **Browsing:** new **Fonts** and **Files** pack sections in the sidebar,
   alongside the existing 2D/3D sections.
4. **Approach:** kind-handler registry refactor (not in-place extension).

## Architecture: kind-handler registry

New module `asset_kinds.py` with a handler protocol:

```python
class KindHandler(Protocol):
    extensions: set[str] | None     # None = catch-all
    def match(self, path: Path) -> bool: ...   # default: suffix in extensions
    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta: ...
```

`asset_kind` is carried by `AssetMeta`, not the handler — ModelHandler alone
produces two kinds (`model` / `animation_bundle`).

`AssetMeta` carries what the inlined dispatch produces today: width/height,
preview bounds, `asset_kind`, `rig`, `thumbnail_path`, extra tags, animation
rows, plus flags for the image-only post-steps (colors, phash).

Ordered registry, first match wins:

```
[AsepriteHandler, ImageHandler, ModelHandler, FontHandler, FileHandler]
```

The registry replaces:

- the extension whitelist + `scan_assets` rglob sets (`index.py:41-44`,
  `index.py:511-523`) — discovery becomes "every visible file, matched
  against the registry; `FileHandler` claims the rest unless denylisted",
- the per-suffix dispatch inlined in the `index()` loop (`index.py:665-698`).

Existing image/aseprite/model behavior must stay byte-identical; the current
test suite is the proof. The dead pre-3D `index_asset()` function
(`index.py:400-495`) is deleted after verifying nothing references it.

## Data model

**No schema change.** `assets.asset_kind` (existing TEXT column) gains values
`'font'` and `'file'`. Fonts reuse `thumbnail_path`; `width`/`height` stay
NULL for both new kinds; `filetype` stores the bare extension as today;
`file_size` already exists. Existing DBs only need a reindex to discover the
new files.

Index-time injected tags mirror the `'3d'` precedent: `'font'` for fonts,
`'file'` for anyfiles. Path-derived tags apply to all kinds as today.

## Indexing

### FontHandler

- Extensions: `.ttf .otf .woff .woff2`, `kind='font'`.
- Renders a specimen PNG at index time with `PIL.ImageFont` (Pillow already a
  dependency) into `.index/thumbs/` (same cache dir + relative-path storage
  as model thumbnails, `index.py:692-695`).
- Specimen content: family name from `font.getname()` on one line, sample
  text ("Aa Bb 0123" + short pangram) below. 512×256 PNG, light text (#eee)
  on transparent background to suit the dark UI.
- If FreeType cannot load the file (corrupt font, `.woff2` without brotli):
  log a warning, leave `thumbnail_path` NULL, index the asset anyway. The
  frontend shows a placeholder; the detail tester may still work since
  browsers load woff2 natively.

### FileHandler (catch-all)

- Matches anything unclaimed, `kind='file'`. Records name, extension, size.
- Denylist skips junk — by name: `.DS_Store`, `Thumbs.db`, `desktop.ini`;
  by extension: `.db`, `.db-journal`, `.import`, `.meta`, `.tmp`, `.part`.
- Dotfiles and dot-directories are already skipped by `visible()`.

### Unchanged

- Colors and phash remain image-only.
- SHA256 incremental indexing (`index.py:612-644`) is type-agnostic and
  applies to the new kinds as-is.

## API

- **New** `GET /api/asset/{id}/file` — serves the raw asset file, content
  type guessed via `mimetypes` (fallback `application/octet-stream`).
  `?download=true` adds `Content-Disposition: attachment; filename=...`.
  Used by the Download button and by `@font-face` in the type tester.
  Follows the raw-model-file precedent (`web/api.py:661-674`). CORS for font
  fetches must work from the frontend origin (verify existing middleware).
- `GET /api/image/{id}` — the thumbnail-serving branch (`web/api.py:592-599`)
  extends to `kind='font'` (serve `thumbnail_path`, 404 if NULL).
  `kind='file'` returns 404; the frontend never requests it.
- `GET /api/search` — `kind=` param already filters `asset_kind`
  (`web/api.py:234-236`); new kinds work automatically. Fix: include `kind`
  in `is_empty_search` (`web/api.py:253`) so `?kind=font` alone gets stable
  ordering instead of `RANDOM()`.
- `GET /api/filters` — each pack gains a computed `section` field:
  - any `model`/`animation_bundle` asset → `'3d'` (preserves `is_3d`),
  - else plurality of asset kinds among image/font/file, ties broken
    font > file > image → `'fonts'` / `'files'` / `'2d'`.
  - Rationale: a shader pack with 3 preview images lands in Files; a sprite
    pack with a stray license.txt stays in 2D.
  - `is_3d` remains in the response until the frontend switches to
    `section`, then is removed in the same change.

## Frontend

- **AssetGrid** — branch on `asset.kind`:
  - `font`: `<img>` from `/api/image/{id}` (specimen); on error or missing
    thumbnail, a placeholder card ("Aa" glyph + filename).
  - `file`: no image request. File card with extension badge (e.g. `.GLSL`),
    filename, and human-readable size.
  - Other kinds unchanged.
- **AssetDetail** — new branches beside the `ModelViewer` branch
  (`AssetDetail.vue:9-22`):
  - `font`: live type tester — `FontFace` API loads the font from
    `/api/asset/{id}/file`, one editable sample text input rendered in the
    font at three preset sizes (16/32/64px), plus a Download button.
  - `file`: info panel (filename, size, type) with a prominent Download
    button.
  - Download button uses `/api/asset/{id}/file?download=true`.
- **PackGallery** — sections become 2D / 3D / Fonts / Files, grouped by the
  server's `section` field; empty sections hidden.
- **Cart** — no changes: the ZIP endpoint already writes raw files
  (`web/api.py:1013-1018`), so fonts/anyfiles are cart-compatible.

## Pack previews

Montage generation stays untouched for packs with ≥4 usable PNGs (previews
are sacred). When a pack has fewer than 4, the candidate pool is padded with
font specimen thumbnails (PNGs first, then specimens) so font packs get real
previews. Files-only packs keep the existing no-preview fallback card.
Convention previews (`contents.png` etc.) still take priority as today.

## Error handling

- Unloadable font → warn, index with NULL thumbnail (see FontHandler).
- Raw-file endpoint 404s when the file is missing on disk, like `/api/image`.
- Catch-all never follows dotfiles/dot-dirs; denylist prevents OS/engine junk.
- Large files index fine (hash cost only); no size cap — downloadability is
  the point.

## Testing (NO MOCKS — real files, real pipeline)

- **Fixtures:** vendor a small OFL-licensed `.ttf` in `tests/fixtures/fonts/`
  (license file included). Shader/anyfile fixtures are plain-text files
  written by tests. A corrupt-font fixture is a few bytes of garbage with a
  `.ttf` suffix.
- **`test_index.py`** — end-to-end via the real Typer CLI
  (`CliRunner().invoke(app, ["index", ...])`, template at
  `test_index.py:1099-1162`) on a temp pack containing png + ttf + glsl +
  `.DS_Store`:
  - rows get correct `asset_kind`, injected `font`/`file` tags,
  - the specimen PNG exists on disk and has non-transparent pixels,
  - denylisted junk is absent from the DB,
  - existing image/aseprite/3D assertions still pass (refactor is
    behavior-preserving),
  - corrupt font indexes with NULL `thumbnail_path`,
  - incremental reindex skips unchanged fonts/files.
- **`web/test_api.py`** — real `TestClient` + temp SQLite with files on disk:
  - `/api/asset/{id}/file` returns exact bytes; `?download=true` sets
    attachment disposition with the filename,
  - `/api/image/{id}` serves the font thumbnail; 404 for `file` kind,
  - `/api/search?kind=font` filters correctly and has stable ordering,
  - `/api/filters` section classification: mostly-shaders pack → `files`,
    fonts-plurality pack → `fonts`, model pack → `3d`, sprite pack with a
    license.txt → `2d`.
- **Frontend Vitest** — AssetGrid renders the file card for `kind='file'`
  and the specimen image for `kind='font'`; AssetDetail shows the tester
  for fonts and the download panel for files.
- **Montage** — fonts-only pack produces a montage from specimen thumbnails.

## Out of scope

- Font metadata columns (family/style as searchable fields) — the specimen
  shows the name; YAGNI.
- Text/code preview for `file` assets — "just a file to download".
- Per-kind sidebar preview redesign; board upload of non-image files.
