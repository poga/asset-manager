# Pack Routing and Sorting Improvements

## Overview

Two improvements to the asset manager:
1. Fix "view pack" to update the browser URL for shareable links
2. Sort search results by full file path instead of filename

## Changes

### 1. URL Update for View Pack

**Problem:** Clicking "view pack" sets internal state but doesn't update the browser URL. Users can't share or bookmark pack views.

**Solution:** Update `App.vue`'s `viewPack()` to use the router's `pushState()` function, navigating to `/pack/{name}`.

**Files:**
- `web/frontend/src/App.vue` - Update `viewPack()` to call router navigation

### 2. Sort by Full Path

**Problem:** Results are sorted by `filename` only, which doesn't preserve directory grouping.

**Solution:** Change `ORDER BY a.filename` to `ORDER BY a.path` in the search endpoint.

**Files:**
- `web/api.py` - Update ORDER BY clause in search query
