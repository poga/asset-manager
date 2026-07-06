# Pack Tags + Sidebar Revert — Design

Date: 2026-07-06
Status: Approved (pending spec review)

## Context

User feedback on the shipped gallery (PR #1/#2): auto-derived themes guess wrong too
often; packs should be organized only by 2D/3D plus user-assigned tags. The compact
sidebar rows lost the previews, which are the most important part of pack browsing.
Also: the "Models only" checkbox is unwanted, and clearing a pack selection should
return to the gallery.

## Part 1: 2D/3D + user tags replace themes

### Removals

- Delete `pack_themes.py` and `test_pack_themes.py`; drop the test line from the
  justfile `test` recipe.
- Delete the theme-assignment pass in `index.py`'s `index()` and the
  `import pack_themes`.
- `/api/filters` no longer returns `theme`. The `packs.theme` column stays in the
  DB unused (SCHEMA keeps it so existing DBs and fresh DBs agree; no code reads it).
- `PackGallery.vue` drops `THEME_ORDER` and theme grouping.
- The theme-related tests (test_index TestPackThemes theme-assignment test,
  test_api theme assertions) are removed or reworked to the new shape.
  The theme-column migration in `migrate_schema` stays (harmless, keeps old DBs
  compatible with SCHEMA).

### Tag storage

New table in `index.py` SCHEMA:

```sql
CREATE TABLE IF NOT EXISTS pack_tags (
    pack_id INTEGER REFERENCES packs(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (pack_id, tag)
);
```

The API creates it lazily too (`CREATE TABLE IF NOT EXISTS` before tag writes and
in the filters read path, so no reindex is required for rollout).

### API

- `/api/filters` pack entries: `{name, count, is_3d, tags: [str, ...]}` — tags
  sorted alphabetically, `[]` when none or when the table is missing (legacy DB
  read path must not 500). `is_3d` keeps the any-model EXISTS rule.
- `POST /api/pack/{pack_name}/tags` body `{"tag": "..."}` — trims and lowercases;
  rejects empty/whitespace tags (400) and unknown packs (404); idempotent
  (INSERT OR IGNORE). Returns the pack's updated tag list.
- `DELETE /api/pack/{pack_name}/tags/{tag}` — removes; unknown pack 404; removing
  an absent tag is a no-op success. Returns the updated tag list.
- Pack name in the URL is URL-encoded; handlers unquote it (same pattern as
  `/api/pack-preview/{pack_name:path}`).

### Gallery (PackGallery.vue)

- Two sections, `2D` then `3D`, packs alphabetical within each. Empty sections
  omitted.
- Top chip row: the union of all pack tags with pack counts. Clicking a chip
  filters both sections to packs carrying that tag; clicking the active chip
  clears the filter. Single active tag at a time. No tags anywhere → no chip row.
- Card tag editing: existing tags render as small chips with an `×` to remove;
  a `+` affordance opens an inline text input (Enter adds, Escape cancels).
  Tag clicks/edits must not trigger the card's `view-pack` navigation
  (stop propagation).
- After add/remove, the pack's tags update from the API response (no full
  filters refetch needed).

## Part 2: Sidebar revert (PackList.vue)

Restore the pre-gallery card layout as the only layout: full-width `.pack-card`
with the 150px `.pack-preview-container`, name, count, selected state; the
`normal`/`expanded` split goes back to the old single markup (expanded = wider
grid via the existing `.pack-grid.expanded` CSS). Compact `.pack-row` markup and
styles are deleted. Deliberate keep: the filter input remains always visible (no
🔍 toggle). `formatPackName` stays in `src/utils/packName.js`. PackList tests
return to `.pack-card` selectors; always-visible-filter tests stay.

## Part 3: Remove "Models only"

`SearchBar.vue` drops the checkbox and the `modelOnly` field from its emitted
params and from `clear()`. `App.vue` drops `params.modelOnly` from `search()`
(kind=model query) and from `handleSearch`'s active-params check. The API `kind`
parameter stays (still used by tests/other callers). SearchBar/App tests updated.

## Part 4: Clearing packs returns to the gallery

In `App.vue`, when `selectedPacks` transitions to empty and there is no active
search (same predicate as `handleSearch`: q/tag/color), set
`isDefaultHomeView = true`. Extract the active-params predicate into one helper
used by both paths. Covered by an App-level test (select pack → clear → gallery
stub visible again).

## Error handling

- Tag POST with empty/whitespace tag → 400; unknown pack on POST/DELETE → 404.
- Filters and tag reads tolerate a missing `pack_tags` table (legacy DB) by
  returning empty tag lists.
- Gallery tag input ignores empty submissions.

## Testing

- API: filters shape (tags list, empty default), POST/DELETE happy paths,
  validation (400/404), idempotency, legacy-DB tolerance. Real SQLite, no mocks.
- Frontend: gallery 2D/3D grouping, tag chip filtering (apply + clear), tag
  add/remove emits/renders, card click still navigates while tag clicks don't;
  PackList card revert; SearchBar without modelOnly; App clear-pack-returns-home.
- Live browser verification against the real DB before the PR.

## Out of scope (YAGNI)

- Multi-tag boolean filtering, tag rename, tag autocomplete.
- Asset-level user tags (packs only).
- Dropping the `packs.theme` column.
