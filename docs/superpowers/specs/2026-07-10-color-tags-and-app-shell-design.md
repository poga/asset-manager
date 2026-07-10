# Color-Coded Tags + App-Shell Layout — Design

Date: 2026-07-10
Status: Approved (pending spec review)

## Context

Two visual tweaks, both enabled by the recent removal of the left pack rail
(the center panel is now the whole workspace):

1. **Color-code the tag filter.** Only the gallery pack-card chips are
   color-coded today. The tag *filters* and other tag displays are still
   monochrome. Make one color system that every tag surface shares.
2. **Rethink the center layout.** `.middle-panel` is styled as a floating card
   (surface bg + shadow + rounded corners + inset padding). That framing earned
   its keep when it was one of three columns; now it is the only stage, so the
   frame is redundant chrome that eats width in a grid-heavy browser. Move to a
   full-bleed app shell.

Frontend only. No API, DB, or index changes.

## Part 1 — Unified tag color system

### Shared util

Extract the existing `tagHue()` from `PackGallery.vue` into
`src/utils/tagColor.js`. Algorithm is unchanged: a deterministic string hash
snapped to one of `TAG_HUE_STEPS = 12` evenly-spaced hues, so unrelated tags are
never a near-identical, hard-to-distinguish color. Export `tagHue(tag)` returning
a hue number in `[0, 360)`. `PackGallery.vue` imports it instead of defining it.

### Surfaces

A tag is the same hue everywhere it appears:

| Surface | File | Today | After |
|---|---|---|---|
| Gallery card chips | `PackGallery.vue` | color-coded | unchanged (hue now from util) |
| Gallery filter-chip row | `PackGallery.vue` | mono outline | tinted by hue; active = filled hue |
| Search-bar selected tags | `SearchBar.vue` | mono grey | tinted by hue + × close |
| Search-bar suggestions | `SearchBar.vue` | plain text | leading hue dot per name |
| Asset-detail tags | `AssetDetail.vue` | all accent-teal | tinted by hue |

### Chip color formula

Reuse the card-chip formula already in `PackGallery.vue`:

- Light inactive: `background: hsl(hue,50%,92%)`, `color: hsl(hue,40%,30%)`
- Dark inactive: `background: hsl(hue,30%,24%)`, `color: hsl(hue,55%,78%)`

The one new visual is the gallery filter's **active** (selected) state, which must
stay obviously distinct from the many tinted-inactive chips around it:

- Light active: `background: hsl(hue,55%,45%)`, `color: #fff`
- Dark active: `background: hsl(hue,50%,55%)`, `color: #0f172a`

The suggestion **hue dot** is a small (0.5rem) inline circle,
`background: hsl(hue,55%,50%)`, before the tag name.

## Part 2 — App-shell layout

Two stacked **sticky** bars sharing the existing frosted-glass treatment
(`--glass-bg` + backdrop blur), with full-bleed content scrolling beneath.

### Brand bar (top)

Current `.app-header`, plus a cart button on the right:
`Asset Manager` (home link) · theme toggle · **🛒 cart button + count badge**.
The count badge shows `cartItems.length` when non-zero.

### Search toolbar (below brand bar)

The `SearchBar` component (input + selected-tag chips), full width, sticky
directly under the brand bar. Bottom border separates it from content.

### Content region

`.middle-panel` drops its card chrome — no surface background, no `box-shadow`,
no `border-radius`, no inset `1rem` padding. Gallery / grid / detail render
directly on `--color-bg-base`, edge-to-edge, so grids gain columns on wide
screens. Horizontal padding becomes each view's responsibility:

- `PackGallery` already has `padding: 0 1.25rem 2rem` — keep.
- `AssetGrid` and `AssetDetail` get horizontal padding matching the gallery's
  `1.25rem` so content is not flush against the viewport edge.
- The gallery's sticky filter row keeps bleeding to the viewport edges; its
  negative-margin / padding values are retuned to the new page padding so the
  frosted row still spans full width and sticks below the search toolbar.

The `.app-layout` flex row no longer needs a second column (the cart aside is
gone — see Part 3), so it simplifies to the single scrolling content area.

## Part 3 — Cart as a right slide-over drawer

The right-docked `<aside class="right-panel">` (280px expanded / 40px collapsed
strip) is **removed**. The `🛒` brand-bar button toggles a right **slide-over
drawer**:

- Fixed-position overlay on the right; does **not** consume layout width.
- Opens over content with a dimmed/backdrop scrim; closes on scrim click, on ✕,
  or on `Escape`.
- `Cart.vue` is reused **unchanged** inside the drawer. Its existing collapse
  button (`➡️`, currently emitting `toggle-panel`) becomes the drawer close —
  `App.vue` maps that emit to "close drawer".

### Removed state machinery

The drawer is transient and closed by default, so the panel-persistence code is
deleted as a net subtraction:

- `cartPanelExpanded` ref → replaced by a `cartOpen` ref (default `false`, not
  persisted).
- `loadPanelState`, `savePanelState`, and the `panelState` localStorage key —
  removed. The `onMounted` call to `loadPanelState` is removed.
- `.right-panel`, `.right-panel.cart-collapsed`, `.collapsed-strip`,
  `.strip-icon`, `.strip-badge` CSS — removed. New `.cart-drawer` / `.cart-scrim`
  CSS added.

## Components touched

- **New:** `src/utils/tagColor.js`
- **Edited:** `App.vue` (layout, cart drawer, state removal),
  `PackGallery.vue` (import util, color filter chips),
  `SearchBar.vue` (color selected tags + suggestion dots),
  `AssetDetail.vue` (color tags)
- **Unchanged:** `Cart.vue`, router, all API calls

## Testing

TDD. Baseline before work: 104 passing, 1 pre-existing unrelated failure in
`tests/router.test.js` (`parses /pack/:name with spaces encoded`). Do not fix
that here.

- **New** `tests/tagColor.test.js`: `tagHue` is deterministic (same input →
  same hue), output is one of the 12 snapped steps, and two chosen tags that
  previously collided remain distinct. (Non-obvious logic — earns its place.)
- **Update** `tests/App.test.js`: remove assertions about the `.right-panel`
  aside / collapsed strip; add the brand-bar cart button and the cart drawer
  open/close behavior (button opens drawer; ✕ / scrim / Escape closes it).
- Do **not** add trivial "chip has a style attribute" tests — color is a
  designer-adjustable value; assert behavior, not CSS values.
- `npm test` green afterward except the one pre-existing router failure.
- Live browser verification at :5173: home renders full-bleed with no card
  frame; filter chips are colored and the active chip is clearly filled; a tag
  is the same hue in the gallery, the search bar, and asset detail; the cart
  button opens the drawer and ✕ / scrim / Escape close it; dark mode looks
  correct.

## Out of scope (YAGNI)

- Any change to tag semantics, the search API, or the pack-filter vs.
  tag-search distinction (the gallery filter row filters visible packs; the
  search bar searches assets — they stay separate features).
- Persisting cart drawer open state across reloads.
- Restyling `Cart.vue`'s internals.
- Fixing the pre-existing `router.test.js` encoding failure.
