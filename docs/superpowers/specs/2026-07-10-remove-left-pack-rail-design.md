# Remove Left Pack Rail — Design

Date: 2026-07-10
Status: Approved (pending spec review)

## Context

The center `PackGallery` (home view) is now the rich pack surface: 2D/3D
sections, tag-chip filtering, per-pack tag editing. The left `PackList` rail
duplicates it — both are grids of pack cards with previews. The rail's only
non-redundant jobs were multi-pack filtering and persistent pack-switching.
User confirmed they use neither (never multi-select; Home→gallery switching is
fine). So the rail is pure redundancy plus a switcher whose space the user would
rather reclaim. This is a subtraction: remove the rail, widen the workspace, add
no new components or abstractions.

## Scope

Frontend only (`web/frontend`). No API, DB, or index changes. Pack-scoped search
and `/pack/:name` routing are preserved; only the rail UI and the now-unused
selection-mode / panel-state machinery are removed.

## Removals (App.vue)

- The entire `<aside class="left-panel">` block (collapsed strip + `PackList`).
- `import PackList` and the component usage.
- Panel-state machine: `packPanelState` ref, `togglePackPanel()`, and the
  auto-collapse-cart-on-expand behavior.
- Selection-mode system: `selectionMode` ref, `watch(selectionMode, ...)`, and
  everything that read it. The left rail was its only UI.
- Left-panel CSS: `.left-panel`, `.left-panel.pack-collapsed`,
  `.left-panel.pack-normal`, `.left-panel.pack-expanded`.

## Deletions (files)

- `src/components/PackList.vue`
- `tests/PackList.test.js`

## Preserved, with simplification (App.vue)

- **`selectedPacks`** stays — it is the source of truth for pack-scoped search
  (`buildSearchQuery`) and `/pack/:name` URLs. It is driven by `viewPack()`,
  gallery clicks, and route handling, not by the rail.
- **`watch(selectedPacks, ...)`** stays. Drop the `selectionMode.value === 'single'`
  guard on the URL push — mode was always effectively "single" for routing, so
  the branch becomes unconditional (`if (!skipNextPush) { ... }`). Behavior
  unchanged: selecting one pack pushes `/pack/:name`; clearing pushes `/`.
- **`loadPanelState` / `savePanelState`** shrink to persist only the cart's
  expanded state. Reads of `state.pack` and `state.selectionMode` are removed;
  the persisted object becomes `{ cart: <bool> }`. `savePanelState` is now called
  only by `toggleCartPanel`.
- **`.collapsed-strip`, `.strip-icon`, `.strip-badge` CSS stays** — the cart's
  collapsed strip still uses it.

## Untouched

`PackGallery.vue` (center), `Cart.vue` (right), `SearchBar.vue`, `AssetGrid.vue`,
`AssetDetail.vue`, router, and all API calls.

## Layout result

`.middle-panel` is already `flex: 1`, so it reclaims the freed width with no new
layout code. Home shows the full-width gallery; search/pack views gain grid
columns. The cart stays on the right, still collapsible.

## Behavior after removal

- Home = center gallery (all packs, 2D/3D, tag chips, tag editing), full width.
- Click a pack card → `AssetGrid` for that pack (unchanged).
- Return to all packs via the "Asset Manager" Home link (unchanged).
- No functional loss: multi-select and persistent pack-switching were the only
  capabilities removed, and both are unused.

## Testing

- Delete `tests/PackList.test.js`.
- Update `tests/App.test.js`:
  - Remove the `import PackList`, the `PackList` entries in `stubs`, the
    `.left-panel` existence assertion, and the "renders PackList in left panel"
    test.
  - **Keep** the `selectedPacks → URL` behavior tests (nav-to-pack pushes
    `/pack/:name`; clearing the last pack pushes `/`). Drive them by setting
    `wrapper.vm.selectedPacks` directly and by removing the now-gone
    `wrapper.vm.selectionMode = 'single'` lines, since the emit source
    (`PackList`) no longer exists.
- `npm test` (vitest) green afterward, except one **pre-existing, unrelated**
  failure in `tests/router.test.js` (`parses /pack/:name with spaces encoded` —
  expects `RPG Heroes` but `parseRoute` returns `RPG%20Heroes`). This predates
  the change; do not fix it here. Baseline before work: 119 passing, that 1
  failing.
- Live browser verification against the running app (port 5173): home shows the
  full-width gallery with no left rail; a pack card opens its grid; Home returns
  to the gallery; the cart still expands/collapses on the right.

## Out of scope (YAGNI)

- Any replacement rail (slim nav rail, faceted filters). Explicitly rejected in
  brainstorming.
- Cart panel changes.
- Fixing the pre-existing `router.test.js` encoding failure.
