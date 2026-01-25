# Full Size Button in Asset Detail View

## Overview

Add a "Full Size" button to the asset detail view that opens the original asset image directly in a new browser tab.

## Requirements

- Button labeled "Full Size" in the action buttons row
- Opens `/api/image/{asset.id}` in a new tab
- User sees the raw image at native resolution

## Implementation

**File:** `web/frontend/src/components/AssetDetail.vue`

**Changes:**
1. Add a "Full Size" button after the existing action buttons
2. Use `<a>` tag with `target="_blank"` and `rel="noopener noreferrer"`
3. Style consistently with existing buttons

**No backend changes required** - the `/api/image/{id}` endpoint already serves original images.

## Testing

- Click "Full Size" button opens image in new tab
- Image displays at native resolution
- Works for all image types (PNG, GIF, JPG, WEBP, Aseprite)
