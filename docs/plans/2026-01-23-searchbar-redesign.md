# SearchBar Redesign

## Overview

Refine the SearchBar component with a minimal, clean aesthetic inspired by Linear and Notion. Keep the single-row layout but elevate the visual quality through custom dropdowns, improved tag pills, and better spacing.

## Design Decisions

- **Style**: Minimal & clean - whitespace, subtle borders, understated elegance
- **Layout**: Single row, refined spacing
- **Dropdowns**: Custom styled (not native `<select>`), text only
- **Tags**: Subtle pills with × icon on hover only
- **Interactions**: Minimal - smooth focus states only, no animations

## Structure

The search bar remains a horizontal row with improved spacing:

```
[🔍 Search input...        ] [Color ▼] [Tag ▼] [pill1 ×] [pill2 ×]
```

- Container: transparent background, 12px gaps between elements
- Search input: primary element, takes remaining space (flex: 1)
- Dropdowns: secondary, fixed widths, styled as quiet buttons
- Tags: tertiary, minimal visual weight, flow inline after dropdowns

## Component Styling

### Search Input

- Height: 36px
- Background: white / surface color
- Border: 1px solid, light gray
- Border-radius: 6px
- Padding-left: 36px (room for search icon)
- Search icon: 16px, muted gray, 10px from left edge
- Placeholder: "Search assets..." in muted gray
- Focus: border shifts to subtle accent, no glow

### Custom Dropdowns

- Height: 36px (matches input)
- Min-width: 100px
- Background: transparent or very subtle gray
- Border: 1px solid, light gray
- Border-radius: 6px
- Chevron icon: 12px, right-aligned, 8px padding
- Dropdown panel: white background, subtle shadow, 4px border-radius
- Options: 32px height, light gray hover background

### Tag Pills

- Height: 24px
- Background: very light gray (#f3f4f6 light / #374151 dark)
- Border-radius: 12px (full pill)
- Padding: 0 10px
- Font-size: 13px
- × icon: hidden by default, appears on hover, 12px
- Text color: secondary gray

## Implementation

### Approach

- Replace native `<select>` with custom dropdown (button + absolute-positioned panel)
- Keep dropdown logic inline in SearchBar.vue (no separate component needed)
- Use inline SVGs for icons (search, chevron, close) - no dependencies
- Add wrapper div for search input to position icon

### CSS Changes

- Remove `.search-bar select` styles
- Add `.dropdown-trigger`, `.dropdown-panel`, `.dropdown-option` classes
- Update `.tag` to pill styling with hover-revealed × icon
- Add `.search-input-wrapper` for icon positioning

### Edge Cases

- Long tag names: truncate with ellipsis at ~100px, title attribute for full name
- Many tags: wrap to next line (flex-wrap)
- Click outside: closes dropdown
- Dropdown overflow: left-align to trigger button

### Accessibility

- Dropdown trigger is `<button>` (keyboard focusable)
- Proper ARIA roles (listbox, option)
- Escape key closes dropdown
- Visible focus states on tags

### Testing

Update existing tests to:
- Use button clicks instead of select changes
- Test dropdown open/close behavior
- Verify tag functionality still works
