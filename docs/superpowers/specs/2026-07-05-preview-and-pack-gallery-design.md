# Spritesheet Preview Fix + Themed Pack Gallery — Design

Date: 2026-07-05
Status: Approved (pending spec review)

## Problems

**1. Spritesheet previews are wrong.** `detect_first_sprite_bounds` (index.py) treats
the first fully-transparent column/row after any content as a frame boundary. Any
transparent gap *inside* a sprite is mistaken for one, so previews show fragments
(a hat brim, half a creature). 8,330 of 10,910 minifantasy PNGs (76%) have a crop
under 12px in a dimension. When detection fails entirely, the UI shows the whole
sheet squeezed into 100px — unreadably small. Bad bounds also poison generated
pack montage previews, which reuse them.

**2. Packs are hard to find.** 101 packs render as a single-column sidebar of
~200px cards (~20,000px of scrolling). The name filter is hidden behind a toggle.
No grouping, no theme organization. User browses by theme and wants to land on a
pack to explore (confirmed in brainstorming).

## Part 1: Grid-aware sprite bounds

New module `frame_detect.py` replaces the gap heuristic. It resolves a frame size
per PNG through four layers; first hit wins. Every candidate must divide the sheet
dimensions exactly or it is discarded and the next layer tried.

1. **AnimationInfo parser.** Walk from the asset's directory up to the pack root
   looking for `*.txt` files matching `/animation.*info/i` (observed variants:
   `_AnimationInfo.txt`, `Animation Info.txt`, `Animation_Info.txt`, etc. — ~40%
   of minifantasy PNGs have one in an ancestor directory). Extract all
   `(\d+)\s*x\s*(\d+)\s*px` frame-size declarations. If several, pick the one that
   divides the sheet; tie → smallest.
2. **Filename hint.** `/(\d+)x(\d+)/` in the filename (e.g. `32x32Fire6.png`).
3. **Grid inference.** Smallest cell edge ≥ 8 that divides the sheet dimension
   where all interior grid boundary columns/rows are fully transparent (alpha ≤ 10,
   checking both sides of each boundary). Width and height inferred independently.
   Validated on real sheets: GoblinIdle 512×128 → 32×32; MotherSlime 256×128 →
   32×32; Dark_Abomination 360×160 → 40×40.
4. **Fallback.** Whole image is one frame.

Preview bounds = content bounding box (alpha > 10) **within the first occupied
cell**, scanning cells row-major, padded 1px, clamped to the cell. Sprites read
large (content-tight) but fragments are impossible: a crop can never cross or
undershoot a real frame boundary again.

- Images without an alpha channel keep the current behavior (no bounds → full image).
- No schema changes: same `preview_x/y/width/height` columns.
- No frontend changes: `SpritePreview.vue` and per-asset `use_full_image`
  overrides work as-is.
- `generate_pack_preview` montages improve automatically since they consume the
  same bounds.

### Rollout

`index --force` recomputes all bounds. The force path also clears `preview_path`
for packs with `preview_generated = TRUE` before the preview loop so montages and
convention previews are regenerated; manually-set previews
(`preview_generated = FALSE` via `set-preview`) are preserved.

### Testing (real files, no mocks)

Fixture PNGs copied from real minifantasy assets into `tests/fixtures/` (the
worktree has no `assets/` directory; fixtures make tests self-contained):

- GoblinIdle-like sheet resolves a 32×32 grid; crop stays within the first cell
  and captures the full sprite (not a 7×6 fragment).
- MotherSlime-like sheet: crop no longer cuts the sprite in half.
- Single 32×32 image with internal transparent gaps: crop = full content bbox,
  not gap-truncated.
- AnimationInfo parser: naming variants, `NNxNNpx` extraction, multi-size files,
  non-dividing sizes rejected.
- Filename hint parsing, including names with no hint.
- Grid inference: no-gap sheet falls back to whole-image frame.
- End-to-end: index a fixture tree, assert bounds in DB match expectations.

## Part 2: Themed pack gallery

### Theme assignment (index time)

- New column `packs.theme TEXT` (migration in `migrate_schema`).
- Checked-in mapping `pack_themes.py`: explicit name-pattern → theme entries for
  the current 101 packs, plus token rules (`forest→Nature`, `crypt→Dungeons & Caves`,
  …) for packs added later. Unmatched → `Other`.
- Themes (~9): Nature, Dungeons & Caves, Towns & Buildings,
  Characters & Creatures, Magic & Effects, Items & Icons, UI, Sci-fi, Vehicles.
- 2D/3D is a separate facet, not a theme: a pack is 3D when the majority of its
  assets have kind `model` or `animation_bundle` — KayKit packs get real themes
  plus a 3D badge.
- `/api/filters` pack entries gain `theme` and `is_3d`.

### Gallery home view

- New `PackGallery.vue` shown in the middle panel when nothing is selected and no
  search is active (replaces the random-asset home grid).
- Theme sections, each a wrapping grid of pack cards (~180px wide): cover image
  from `/api/pack-preview/`, pack name (existing `formatPackName` cleanup), asset
  count, 2D/3D badge. Missing cover → placeholder tile.
- Chip row at the top listing themes; clicking scrolls to that section.
- Card click → existing `viewPack` flow (select pack, show its assets).
- Header/title click returns to the gallery home.

### Compact sidebar

- Replace 150px-preview cards with compact rows: small thumbnail (~28px), name,
  count. Selection behavior (single/multi, view-pack on second click) unchanged.
- Filter input always visible (remove the 🔍 toggle).
- `expanded` panel state keeps the larger card grid.

### Testing

- Theme mapping unit tests: explicit entries, token rules, fallback to Other.
- API test: `/api/filters` packs include `theme` and `is_3d`.
- Gallery and sidebar verified live against the running dev servers.

## Error handling

- Frame detection failures (corrupt image, unreadable txt) fall through to the
  next layer, ultimately whole-image bbox; indexing never aborts on one asset.
- Packs with no cover art render a placeholder card, not a broken image.
- Unknown/new packs get theme `Other` and appear in the gallery's last section.

## Out of scope (YAGNI)

- Animated previews / hover scrubbing (frame data from Part 1 makes this easy later).
- Command palette / keyboard jump.
- Favorites, recents.
- Editing themes from the UI.
