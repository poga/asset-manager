# Pack Selection Mode Toggle Design

## Summary

Change pack selection from multi-select (current default) to single-select by default, with a toggle button to switch between modes.

## State Changes

**New state in App.vue:**
```javascript
const selectionMode = ref('single')  // 'single' | 'multi'
```

**localStorage persistence:**
- Add `selectionMode` to the existing `panelState` object
- Default to `'single'` if not present

**Selection behavior in PackList.vue:**
- **Single mode:** Clicking a pack replaces the selection (array with just that pack, or empty if deselecting)
- **Multi mode:** Current behavior - clicking toggles the pack in/out of the array

**Mode switching logic:**
- Multi → Single: Keep only `selectedPacks[0]`, or empty if none selected
- Single → Multi: Keep current selection as-is

## UI Changes

**Toggle button in PackList header:**
- Position: After search button, before "Select all" button
- Icon: `1` for single mode, `+` or stack icon for multi mode
- Tooltip: Shows current mode name
- Styling: Match existing header buttons

**Conditional button visibility:**
- Single mode: Hide "Select all" button
- Multi mode: Show both "Select all" and "Clear" buttons

## Component Interface

**New prop for PackList.vue:**
```javascript
selectionMode: { type: String, default: 'single' }
```

**New emit:**
```javascript
'update:selectionMode'
```

**App.vue binding:**
```vue
<PackList
  v-model:selectedPacks="selectedPacks"
  v-model:selectionMode="selectionMode"
  ...
/>
```

## Test Cases

1. Single mode: clicking a pack replaces selection
2. Single mode: clicking selected pack deselects it
3. Multi mode: clicking toggles pack in/out (existing behavior)
4. Mode toggle button switches between modes
5. Switching multi→single keeps first selected pack
6. "Select all" button hidden in single mode
7. Mode persists to localStorage
