# Collapsible Panels Design

## Overview

Make the pack panel and cart panel collapsible with localStorage persistence.

## Pack Panel States

Three states, cycling on toggle click:

| State | Width | Grid Columns |
|-------|-------|--------------|
| collapsed | 40px (icon strip) | - |
| normal | 320px | 1 column |
| expanded | 60% screen | auto-fit |

Default: `normal`

## Cart Panel States

Two states, toggling on click:

| State | Width |
|-------|-------|
| collapsed | 40px (icon strip) |
| expanded | 280px |

Default: `collapsed`

## Collapsed State UI

- 40px wide vertical strip
- Icon centered near top (folder icon for packs, cart icon for cart)
- Glass-morphism background (same as expanded)
- Click anywhere on strip to expand
- Optional: badge showing count

## Toggle Button

- Located in panel header (right edge)
- When collapsed, clicking the icon strip expands

## Interaction Rules

- When pack panel expands to 60%, auto-collapse cart panel
- State persists to localStorage (key: `panelState`)
- No animations, instant toggle

## localStorage Schema

```json
{
  "pack": "collapsed" | "normal" | "expanded",
  "cart": true | false
}
```

## Files to Modify

- `web/frontend/src/App.vue` - state management, layout logic, localStorage
- `web/frontend/src/components/PackList.vue` - toggle button, auto-fit grid
- `web/frontend/src/components/Cart.vue` - toggle button
