# Frontend Redesign: View Packs & Masonry Layout

## Overview

Redesign the asset manager frontend to:
1. Support "View Pack" navigation - browse all assets in a pack directly
2. Use a Pinterest-like masonry layout with larger thumbnails

## Feature 1: Pack View Navigation

### New Route

- `/pack/:packName` - Shows all assets filtered to that pack

### Navigation Entry Points

1. **From Asset Modal** - "View Pack" button navigates to `/pack/{asset.pack}`
2. **From Asset Card** - Pack name is clickable, navigates to pack view

### URL Behavior

- `/pack/fantasy-characters` loads the grid filtered to that pack
- Back button returns to previous search/view
- Direct links are shareable

### UI Changes

- Pack view shows a header with the pack name (e.g., "Viewing: Fantasy Characters")
- "Clear" button to return to unfiltered view
- Pack dropdown in SearchBar stays synced with current pack view

### State Flow

```
Asset Modal → Click "View Pack" → Navigate to /pack/:name →
App.vue fetches assets with pack filter → AssetGrid displays results
```

## Feature 2: Masonry Layout with CSS Columns

### Layout Change

Replace the current CSS Grid:
```css
/* Old */
display: grid;
grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
```

With CSS Columns:
```css
/* New */
column-width: 220px;
column-gap: 1rem;
```

### Asset Card Design

```
┌─────────────────┐
│                 │
│     Image       │
│   (natural      │
│   aspect ratio) │
│                 │
├─────────────────┤
│ Pack Name       │  ← smaller, muted text, clickable
│ filename.png    │  ← primary text
└─────────────────┘
```

### Card Styling

- **Image**: Natural aspect ratio, `max-width: 100%`, `image-rendering: pixelated`
- **Pack name**: Smaller font, muted gray color, clickable (navigates to pack view)
- **Filename**: Normal font, truncated with ellipsis if too long
- **Card**: Subtle border or shadow, hover effect
- **Layout**: `break-inside: avoid` to keep cards intact across columns

### Preventing Layout Shift

Use pre-calculated aspect ratio from asset metadata:
```css
.asset-image-container {
  aspect-ratio: var(--asset-width) / var(--asset-height);
}
```

## Component Changes

### App.vue

- Add route handler for `/pack/:packName`
- When pack route is active, fetch assets filtered by pack
- Add state for `currentPackView` (null or pack name)

### SearchBar.vue

- When in pack view, show header: "Viewing: {Pack Name}" with "Clear" button
- Pack dropdown stays synced with current pack view

### AssetGrid.vue

- Replace CSS Grid with CSS Columns layout
- Update `.asset-item` to show: image, pack name, filename
- Add `break-inside: avoid` to cards
- Use `aspect-ratio` from asset metadata for image containers
- Make pack name clickable (emits event to navigate)

### AssetModal.vue

- Add "View Pack" button next to existing "Find Similar" button
- Clicking navigates to `/pack/{asset.pack}`

## CSS Summary

```css
/* AssetGrid container */
.asset-grid {
  column-width: 220px;
  column-gap: 1rem;
}

/* Asset card */
.asset-item {
  break-inside: avoid;
  margin-bottom: 1rem;
}

/* Image container with pre-set aspect ratio */
.asset-image-container {
  aspect-ratio: var(--asset-width) / var(--asset-height);
}

/* Pack name link */
.asset-pack-name {
  font-size: 0.85em;
  color: #666;
  cursor: pointer;
}

.asset-pack-name:hover {
  text-decoration: underline;
}
```
