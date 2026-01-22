# Frontend 3-Column Redesign

NotebookLM-style layout with pack list, search/grid, and cart.

## Layout Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│  Asset Manager                                    ⚙ Settings         │
├────────────────────┬─────────────────────────────┬───────────────────┤
│  Packs        Q ≡  │  Search                     │  Cart             │
├────────────────────┤─────────────────────────────┼───────────────────┤
│  + Add pack        │                             │  📥 Download ZIP  │
│                    │  [🔍 Search assets...]      │                   │
│  Select all packs  │  [Color ▼]  [Tags: + ]     │  Items        Q ≋ │
│                    │                             │                   │
│  ☑ icons     (124) │  ┌───────┐ ┌───────┐       │  ┌──┐ button.png  │
│  ☐ ui-kit    (89)  │  │       │ │       │  [+]  │  │  │ ui-kit      │
│  ☑ monsters  (45)  │  │ asset │ │ asset │       │  └──┘         [×] │
│  ☐ sprites   (156) │  └───────┘ └───────┘       │                   │
│                    │                             │  ┌──┐ slime.png   │
│                    │  ┌───────┐ ┌───────┐       │  │  │ monsters    │
│                    │  │       │ │       │  [+]  │  └──┘         [×] │
│                    │  │ asset │ │ asset │       │                   │
│                    │  └───────┘ └───────┘       │                   │
└────────────────────┴─────────────────────────────┴───────────────────┘
```

**Column widths:**
- Left (Packs): Fixed 240px
- Middle (Search/Content): Flexible
- Right (Cart): Fixed 280px

## Left Panel: Pack List

**Header:** "Packs" with search and list icons

**Features:**
- "Select all packs" checkbox at top
- Each row: checkbox + pack name + count badge (right-aligned, muted)
- Multiple packs can be selected (multi-select filtering)
- Clicking "View Pack" from detail view selects only that pack

**Styling:**
- Background: `#fafafa`
- Pack names: `#333`
- Counts: `#888`
- Rounded checkboxes with brand color when checked

## Middle Panel: Search & Content

**Header:** "Search"

**Search Controls:**
- Full-width search input with icon
- Color dropdown and Tags selector below (no pack dropdown - moved to left panel)

**Grid View (default):**
- Masonry layout
- Hover reveals "+" button to add to cart
- Click thumbnail → Detail View

**Detail View (replaces grid):**
- "← Back to results" breadcrumb
- Large asset preview
- Metadata: filename, pack, dimensions, tags, colors
- Actions: "Add to Cart", "Find Similar", "View Pack"

## Right Panel: Cart

**Header:** "Cart" with search and filter icons

**Top Action:**
- "Download ZIP" card (prominent, like NotebookLM's "Create Audio Overview")
- Disabled when cart empty

**Items List:**
- Each item: thumbnail (40x40) + filename (bold) + pack name (muted) + remove (×)
- Hover highlights row

**Empty State:**
- "No items in cart"
- "Hover over assets and click + to add"

## Interactions

**Adding to Cart:**
- Hover asset → "+" button appears (top-right)
- Click → added to cart, shows "✓" briefly
- Assets in cart show indicator in grid

**Removing:**
- Click "×" on cart item

**Download ZIP:**
- Click "Download ZIP" → loading state → browser downloads file

## API

**New endpoint:**
```
POST /api/download-cart
Body: { "asset_ids": ["id1", "id2", "id3"] }
Response: ZIP file stream (Content-Disposition: attachment)
Filename: assets-{timestamp}.zip
```

## State Management

- Cart: Vue ref `cartItems = ref([{ id, filename, pack, thumbnail_url }])`
- Selected packs: Vue ref `selectedPacks = ref([])`
- Session only, no persistence

## URL Routing

- `/` - Home, all packs selected
- `/?packs=icons,monsters` - Filtered by packs
- `/asset/{id}` - Detail view
- `/asset/{id}?packs=icons` - Detail view with pack filter

## Components

| Component | Changes |
|-----------|---------|
| App.vue | New 3-column layout wrapper, cart state |
| PackList.vue | **New** - Left panel pack list with checkboxes |
| SearchPanel.vue | **New** - Middle panel wrapper (search + grid/detail) |
| SearchBar.vue | Remove pack dropdown |
| AssetGrid.vue | Add hover "+" button, cart indicator |
| AssetDetail.vue | **New** - Detail view (replaces modal) |
| Cart.vue | **New** - Right panel cart |
| AssetModal.vue | **Remove** - Replaced by AssetDetail |
