# UI Refresh: Modern Theme with Dark Mode

## Overview

Refresh the frontend from stark white to a clean, modern design with more contrast and depth. Add dark mode support with system preference detection and manual toggle.

## Color Palette

### Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg-base` | `#f8fafc` | Page background |
| `--color-bg-surface` | `#ffffff` | Cards, panels |
| `--color-border` | `#e2e8f0` | Default borders |
| `--color-border-emphasis` | `#cbd5e1` | Emphasized borders |
| `--color-text-primary` | `#0f172a` | Headings, primary text |
| `--color-text-secondary` | `#475569` | Body text |
| `--color-text-muted` | `#94a3b8` | Placeholders, hints |

### Dark Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg-base` | `#0f172a` | Page background |
| `--color-bg-surface` | `#1e293b` | Cards, panels |
| `--color-border` | `#334155` | Default borders |
| `--color-border-emphasis` | `#475569` | Emphasized borders |
| `--color-text-primary` | `#f8fafc` | Headings, primary text |
| `--color-text-secondary` | `#cbd5e1` | Body text |
| `--color-text-muted` | `#64748b` | Placeholders, hints |

### Accent Colors (Both Modes)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-accent` | `#0d9488` | Primary buttons, links |
| `--color-accent-hover` | `#0f766e` | Hover state |
| `--color-accent-light` | `#ccfbf1` | Light mode badges |
| `--color-accent-dark` | `#134e4a` | Dark mode badges |
| `--color-success` | `#10b981` | Cart indicators |
| `--color-danger` | `#ef4444` | Remove actions |

## Visual Effects

### Shadows

```css
/* Cards and panels */
--shadow-card: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.08);

/* Elevated elements (dropdowns, modals) */
--shadow-elevated: 0 4px 6px rgba(0,0,0,0.07), 0 12px 28px rgba(0,0,0,0.12);

/* Dark mode - increased opacity for visibility */
--shadow-card-dark: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.3);
--shadow-elevated-dark: 0 4px 6px rgba(0,0,0,0.3), 0 12px 28px rgba(0,0,0,0.5);
```

### Glass Effect

```css
/* Sidebars and header */
backdrop-filter: blur(8px);
background: rgba(255,255,255,0.8);  /* light */
background: rgba(30,41,59,0.8);     /* dark */
```

### Border Radius

- Cards: `6px`
- Buttons, inputs: `4px`

### Transitions

- Interactive elements: `150ms ease`
- Theme switch: `200ms` on background/text

## Theme System

### CSS Variables

Define in `:root` for light mode, override in `[data-theme="dark"]` for dark mode.

### Toggle Logic

1. On load: check localStorage, fall back to system preference
2. On toggle: save to localStorage, update `data-theme` attribute
3. Listen for system changes when no manual override

### Toggle Placement

Header, right side. Sun/moon SVG icons.

## Component Changes

### Header
- Glass background effect
- Theme toggle button (right-aligned)
- Subtle bottom border

### PackList
- Glass background
- Cards: layered shadow
- Selected: teal left border accent
- Hover: subtle teal tint

### SearchBar
- Inputs: slate borders, teal focus ring
- Tags: teal-tinted background

### AssetGrid
- Cards: surface background, layered shadow
- Add button: teal
- Cart indicator: success green

### AssetDetail
- Prominent centered card shadow
- Teal primary buttons, slate secondary

### Cart
- Glass background
- Download: solid teal
- Remove: subtle, red on hover

## Files to Modify

- `web/frontend/src/App.vue` - CSS variables, theme logic, toggle
- `web/frontend/src/components/PackList.vue` - Variable references
- `web/frontend/src/components/SearchBar.vue` - Variable references
- `web/frontend/src/components/AssetGrid.vue` - Variable references
- `web/frontend/src/components/AssetDetail.vue` - Variable references
- `web/frontend/src/components/Cart.vue` - Variable references
