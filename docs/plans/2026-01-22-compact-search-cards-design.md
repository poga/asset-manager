# Compact Search Result Cards

**Goal:** Show ~1.4x more asset cards for faster scanning without scrolling.

## Changes

### Layout
- Column width: 220px → 155px
- Card bottom margin: 1rem → 0.75rem
- Column gap: unchanged (1rem)

### Card Content
- Pack name font: 0.75rem → 0.65rem
- Filename font: 0.875rem → 0.75rem
- Filename: single line with ellipsis (was wrapping)
- Info section padding: 0.5rem → 0.375rem
- Add-to-cart button: 28px → 24px

### Hover
- Add `title` attribute to filename for native tooltip showing full name

## Files to Modify
- `web/frontend/src/components/AssetGrid.vue`
