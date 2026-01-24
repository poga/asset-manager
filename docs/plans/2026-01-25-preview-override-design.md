# Preview Override Feature Design

## Problem

The asset manager auto-detects sprite sheet bounds and shows the first frame as the preview. This causes two issues:

1. **Misdetection** - Single images sometimes get incorrectly cropped as if they were sprite sheets
2. **Preference** - Some sprite sheets are better viewed in full (to see all frames at a glance)

## Solution

Allow users to mark individual assets to show the full image instead of the detected first frame.

## Data Model

New table (separate from `assets` to survive re-indexing):

```sql
CREATE TABLE asset_preview_overrides (
    path TEXT PRIMARY KEY,
    use_full_image BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Using `path` as the key ensures marks persist through re-indexing since the `assets` table gets recreated.

## API Changes

### New Endpoints

**Set override:**
```
POST /api/asset/{id}/preview-override
Body: { "use_full_image": true }
```

**Remove override:**
```
DELETE /api/asset/{id}/preview-override
```

### Modified Responses

`GET /api/asset/{id}` includes:
```json
{
  "use_full_image": true
}
```

`GET /api/search` includes `use_full_image` per asset.

## Frontend Changes

### Asset Detail View (`AssetDetail.vue`)

- Add checkbox "Show full image" below the image
- Only visible when asset has detected preview bounds
- Toggles the override via API

### Asset Grid (`AssetGrid.vue`)

- Check `use_full_image` when rendering each asset
- If true: show full image instead of `SpritePreview`
- If false/null: current behavior (detected first frame)

## Edge Cases

- **Asset re-indexed**: Override persists (keyed by path)
- **Asset path changes**: Old override orphaned (harmless)
- **No preview bounds**: Checkbox hidden (nothing to override)
