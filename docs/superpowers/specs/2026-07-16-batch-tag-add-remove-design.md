# Batch Tag Add/Remove for Packs and Assets

**Date:** 2026-07-16
**Status:** Approved

## Goal

Let the user add or remove a user tag across many packs or many assets at once,
instead of one item at a time. Selection is grid-level: a "Select" mode with
per-card checkboxes, then a batch toolbar to add a typed tag or remove a tag by
clicking it.

## Decisions (from brainstorming)

1. **Batch model:** selection mode with per-card checkboxes. Keeps tagging
   separate from the existing download cart (whose semantics are "download ZIP").
2. **Selection scope:** per-view. Packs are selected in the pack gallery, assets
   in the search/results grid. No mixed pack+asset batch.
3. **Tag entry:** free-type input adds a tag (new or existing) to all selected;
   the union of tags on the selection shows as chips, click × to remove that tag
   from all selected. Mirrors the existing single-item add/remove pattern.
4. **Backend shape:** one batch endpoint per entity carrying an `op`
   discriminator (not N single-item calls, not DELETE-with-body).

## Scope

In: packs and assets, grid-level only, user tags only.
Out: the single-asset detail view (already one-at-a-time), any non-tag bulk op,
mixed pack+asset selection.

## Backend API

Two new endpoints, one per entity. `op` unifies add and remove into one
transaction and one code path.

```
POST /api/assets/tags   { asset_ids: [int],  tag: str, op: "add" | "remove" }
POST /api/packs/tags     { pack_names: [str], tag: str, op: "add" | "remove" }
```

Plural paths — no collision with the singular `/api/asset/{id}/tags` and
`/api/pack/{pack_name}/tags`.

**Add** (`op == "add"`):
- Assets: `INSERT OR IGNORE INTO tags(name)`, resolve `tag_id`, then
  `INSERT OR IGNORE INTO asset_tags(asset_id, tag_id, source)` (`'user'`) for
  every id.
- Packs: `INSERT OR IGNORE INTO pack_tags(pack_id, tag)` for every resolved
  pack. `_ensure_pack_tags(conn)` first, as the other pack-tag routes do.
- Idempotent: items that already carry the tag are untouched.

**Remove** (`op == "remove"`):
- Assets: resolve the tag; if it exists, one `DELETE FROM asset_tags WHERE
  asset_id IN (...) AND tag_id = ?`.
- Packs: `DELETE FROM pack_tags WHERE pack_id IN (...) AND tag = ?`.

**Semantics:**
- `tag` is trimmed + lower-cased, matching the single-item endpoints.
- Empty `tag` → 400. Empty id/name list → 400. `op` not in {add, remove} → 422
  (validation).
- Unknown ids/names are silently skipped — single-user local tool, the frontend
  only sends live items, so one stale id must not fail a whole batch.
- One connection, one `commit()`.

**Response:**

```json
{ "results": [ { "id": 12, "tags": ["2d", "goblin"] }, ... ] }
```

Packs return `"name"` instead of `"id"`. Each affected item's full new tag list,
so the frontend patches cards and recomputes the removable-chip union without a
refetch. Skipped (unknown) items are absent from `results`.

**Request models** (pydantic, near the existing `AssetTagRequest`):

```python
class BatchAssetTagRequest(BaseModel):
    asset_ids: list[int]
    tag: str
    op: Literal["add", "remove"]

class BatchPackTagRequest(BaseModel):
    pack_names: list[str]
    tag: str
    op: Literal["add", "remove"]
```

## Frontend — selection mode

- A **"Select"** toggle in the pack-gallery header and in the results header.
  Toggling off, changing view, or changing the search clears the selection.
- New App state, named to avoid the existing `selectedPacks` / `selectedAsset`
  (which drive navigation): `batchPackNames` and `batchAssetIds` (sets), plus
  `selectMode`.
- In select mode a card shows a checkbox and a click **toggles selection**
  instead of opening the asset / navigating into the pack.
- A shared **`BatchTagBar.vue`** (fixed bottom bar), driven by App state and
  parameterized by entity, renders when the current view's selection is
  non-empty:
  - **"N selected"** + **Clear**.
  - **Add tag** free-type input → `op:"add"` for all selected.
  - **Union chips** — union of `tags` across the selected items (both grids
    already carry `tags`, so computed client-side) — each with × → `op:"remove"`
    for all selected.
- After a call, patch affected items from `results`: PackGallery already has the
  `tagOverrides` map; asset results are patched in App's results list. The union
  chips recompute from the patched tags.

## Testing

**Backend — `web/test_api.py`, TDD, real SQLite, no mocks.** State transitions:
- Batch add a tag across several assets → each carries it.
- Re-add an already-present tag → idempotent, no duplicates.
- Batch remove → gone from all; no-op where a target lacked it.
- Same add + remove for packs.
- Add a brand-new tag via batch → created in `tags` and linked.
- Empty tag → 400; empty id/name list → 400.
- Unknown id/name in the list → skipped, present ids still applied, absent from
  `results`.

**Frontend UI** — validated by driving the real app in the browser (verify
skill): enter select mode, multi-select, add a tag, confirm the union chips and
persistence, remove via a chip. A vitest component test is added only if the
existing harness makes it earn its place.

## Files touched

- `web/api.py` — two request models, two endpoints.
- `web/test_api.py` — batch tag tests.
- `web/frontend/src/App.vue` — select mode + batch selection state.
- `web/frontend/src/components/PackGallery.vue` — checkboxes + select mode.
- `web/frontend/src/components/AssetGrid.vue` — checkboxes + select mode.
- `web/frontend/src/components/BatchTagBar.vue` — new shared toolbar.
- `web/frontend/src/api/boards.js` — batch tag fetch helpers.
