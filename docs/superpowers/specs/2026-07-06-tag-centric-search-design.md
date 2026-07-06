# Tag-Centric Search — Design

Date: 2026-07-06
Status: Approved (pending spec review)

## Context

User direction: remove the color filter, rebuild search around tags, keep manual
pack tagging as shipped. Decisions made in brainstorming: pack tags and asset
tags unify into one vocabulary (pack tags flow down to the pack's assets in
search); the search UI is a single smart box with client-side suggestions
(5,726 asset tags ≈ 120KB shipped once — no autocomplete endpoint).

## Part 1: Backend — unified vocabulary + tag inheritance

### /api/filters

- `tags` becomes the full vocabulary: a list of `{name, count}` covering EVERY
  asset tag (count = number of assets carrying it), merged with every pack tag
  (count = SUM of `asset_count` over packs carrying it). A name present in both
  collapses to one entry with the larger count. Sorted by count descending,
  name ascending as tiebreak.
- The `colors` key is removed from the response.
- The per-pack `tags` arrays in `packs` stay unchanged (gallery consumes them).

### /api/search

- Each `tag` query param clause becomes: asset matches if it carries the tag
  itself OR its pack carries the tag:

```sql
(a.id IN (SELECT at.asset_id FROM asset_tags at
          JOIN tags tg ON at.tag_id = tg.id WHERE tg.name = ?)
 OR a.pack_id IN (SELECT pack_id FROM pack_tags WHERE tag = ?))
```

  (two bound params per tag, same lowercased value). Multiple `tag` params
  still AND together.
- The `color` param is removed entirely, along with `COLOR_NAMES` and the
  color conditions. Requests sending `color` get FastAPI's default behavior
  for unknown params (ignored).
- The tag clause must tolerate a DB without the `pack_tags` table (legacy):
  reuse `_ensure_pack_tags` before querying, consistent with `/api/filters`.

### Color scope (explicit)

Only the FILTER is removed. Color extraction at index time (`extract_colors`,
`asset_colors` writes) and the color swatches on the asset detail page/API stay.

## Part 2: Frontend — the smart box

`SearchBar.vue` becomes one input + the existing chips row. The "Any color"
and "Add tag…" dropdowns are deleted.

- Typing: the input text remains the live debounced filename/path query
  (current behavior). Simultaneously a suggestion dropdown shows the top 12
  vocabulary matches: prefix matches first, then substring matches, each group
  ranked by count descending; each row shows the tag name and count.
- Selection: clicking a suggestion, or highlighting via ArrowUp/ArrowDown and
  pressing Enter, adds the tag as a chip and clears the input (and thus the
  free-text query). No suggestion is highlighted by default, so plain Enter
  never adds a tag. Escape closes the dropdown. The dropdown closes on
  outside click (existing SearchBar pattern).
- Adding a tag already in the chips is a no-op. Chips keep AND semantics and
  click-to-remove.
- Emitted search params shrink to `{q, tag}` — the dead `type` and removed
  `color`/`modelOnly` fields are gone. `clear()` resets query + tags.
- `App.vue`: `search()` drops the color param; `hasActiveSearch(params)`
  becomes `!!(params.q || (params.tag && params.tag.length))`. Everything else
  (debounce, home/gallery logic) unchanged.
- The vocabulary comes from the `filters` prop SearchBar already receives
  (App fetches `/api/filters` once at mount — unchanged flow, richer payload).
- The gallery's pack-tag chip row is untouched.

## Part 3: Error handling

- Suggestions with an empty input: dropdown hidden (no zero-query popup).
- Vocabulary missing/empty (legacy API or no tags): smart box degrades to a
  plain filename search box; no errors.
- `/api/filters` and `/api/search` must not 500 on a DB lacking `pack_tags`.

## Testing

- API (real SQLite, no mocks): full-vocabulary shape with merged pack tags and
  correct counts (including the collapse-duplicate-name case); inheritance
  (tag a pack → its assets match via `/api/search?tag=`, AND-composition with
  a second tag still works); legacy-DB tolerance; color param and COLOR_NAMES
  removed (existing color tests deleted).
- Frontend (Vitest, existing conventions): suggestion filtering and ranking
  (prefix beats substring, count order), keyboard flow (arrow + Enter adds,
  plain Enter doesn't, Escape closes), click-to-add, duplicate add no-op,
  chips continue to work, emitted params shape `{q, tag}`; App predicate
  updated tests.
- Live browser verification against a disposable copy of the production DB:
  tag a pack, find its assets through the smart box, confirm color dropdown
  gone.

## Rollout

Merge + API restart. No reindex — pack tags apply to search immediately.

## Out of scope (YAGNI)

- Removing color extraction / detail-page swatches.
- OR/negation tag queries, saved searches, tag renaming.
- Server-side autocomplete endpoint (revisit if the vocabulary grows ~50×).
- Cleaning junk tokens out of the auto-derived tag vocabulary.
