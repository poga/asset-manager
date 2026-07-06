# Pack Gallery Redesign

## Problem

The center pack gallery (`PackGallery.vue`, the home view) is too dense and hard
to read. With 101 real packs it renders ~7 columns of 180px cards, each carrying
an always-visible tag editor (`minifantasy × +` on 70+ cards), a name/count pair
crammed on one line that wraps unevenly, weak 2D/3D section hierarchy, and a
sticky filter bar whose background (`--color-bg-base`) mismatches the middle
panel (`--color-bg-surface`). Small pixel-art previews sit unscaled in the dark
covers, so many covers read as empty boxes.

## Goal

A calm, professional gallery: fewer, larger cards with consistent geometry,
clear typographic hierarchy, tag editing available but quiet, and covers that
present the packs' art properly. No behavior changes.

## Non-goals

- The left sidebar `PackList.vue` (its previews stay exactly as they are).
- Search, asset grid, detail view, cart.
- New sections/grouping (2D/3D + user tags only, per prior product decision).
- New dependencies, fonts, or theme tokens outside the existing palette.

## Approaches considered

1. **Refined card grid (chosen)** — keep the grid metaphor, fix density,
   hierarchy, and noise. Lowest risk, preserves visual browsing.
2. List rows — scans fast but demotes previews to thumbnails; previews are the
   point of an asset gallery. Rejected.
3. Poster wall (meta on hover overlay) — cleanest surface but hides counts and
   tags and makes tag editing undiscoverable. Rejected.

## Design

All changes are scoped to `PackGallery.vue` (template + scoped CSS + one small
image-load handler). Existing class names and DOM event contracts are kept so
the 9 existing component tests pass unchanged.

### Grid and card geometry

- Grid: `repeat(auto-fill, minmax(220px, 1fr))`, gap `1.25rem 1rem`
  (~5 columns at a 1500px viewport instead of 7).
- Card: radius 10px, 1px border, surface background. Hover: accent border,
  `--shadow-card`, `translateY(-1px)`; transitions ~150ms. Respect
  `prefers-reduced-motion` (no transform).
- Cover: `aspect-ratio: 5 / 3`, fluid height (replaces fixed 110px), dark stage
  `#1a1a2e` in both themes — a consistent viewport for game art.

### Cover image treatment (the signature)

Small pixel-art previews should fill the stage crisply instead of floating
tiny in a dark box:

- Image: `width/height: 100%`, `object-fit: contain`, inner padding ~0.5rem.
- On image load, if `naturalWidth < 200`, add a `pixelated` class →
  `image-rendering: pixelated`. Large previews (maps, 3D renders) keep smooth
  scaling; small sprites upscale crisp.
- Failed covers keep the 📦 placeholder, centered, muted.

### Typography and meta

- Pack name on its own line: `0.875rem`, weight 600, single-line ellipsis with
  `title` attribute for the full name.
- Count as a muted subline: `N assets` (`0.75rem`, `--color-text-muted`) —
  no pill, no competing weight.
- Section headers as quiet eyebrows: `2D`/`3D` in `0.75rem` uppercase with
  letter-spacing, pack count alongside (e.g. `2D — 80 packs`), hairline rule
  filling the remaining width. First header has no extra top margin.
  The count and rule are siblings of `.dim-title`, not inside it — a test
  asserts the title's text is exactly `2D`/`3D`.

### Tag editing (noise removal)

- Per-card tag chips stay visible but quiet: no border, elevated background,
  `0.6875rem`, muted text.
- The remove `×` inside a chip is hidden (opacity 0) until the chip is hovered
  or the button is focus-visible.
- The `+` add button is hidden until the card is hovered or it is
  focus-visible. It remains in the DOM at all times (tests and keyboard access
  depend on it).
- Tag input styling matches the chips; behavior unchanged.

### Filter bar

- Sticky bar keeps position but gets the middle panel's background
  (`--color-bg-surface`) and a bottom hairline so it reads as a toolbar rather
  than a floating band; full-bleed across the scroll area (negative margin +
  padding compensation).
- Chips keep pill shape; active state stays accent-tinted.

## Error handling

Unchanged: failed cover loads fall back to the placeholder; tag API failures
already leave state untouched (`res.ok` guards). The auto-clear of a stale
active tag filter stays as is.

## Testing

- The 9 existing `PackGallery.test.js` tests must pass unchanged — they are the
  behavior contract (sections, filter chips, tag add/remove, navigation).
- One new test for the only new logic: an image `load` event with small
  `naturalWidth` adds the `pixelated` class; a large one does not.
- No tests for spacing, colors, or other designer-adjustable presentation.
- Visual verification in the browser (light + dark) against the running app.
