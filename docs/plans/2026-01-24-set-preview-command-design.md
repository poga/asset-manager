# Set Preview Command Design

Add a CLI command to set custom preview images for packs instead of the auto-generated 4x4 montage.

## Command Interface

```bash
# Explicit file path for specific pack
uv run index.py set-preview "Pensubmic_Dungeon_v1.0" /path/to/preview.gif

# Explicit file path with pattern (glob)
uv run index.py set-preview "pensubmic_*" /path/to/preview.gif

# Convention-based: finds preview.png/gif inside each matching pack's directory
uv run index.py set-preview "pensubmic_*"
uv run index.py set-preview "Pensubmic_Dungeon_v1.0"
```

**Arguments:**
- `pack_pattern` (required): Pack name or glob pattern (case-insensitive matching)
- `image_path` (optional): Path to preview image. If omitted, looks for `preview.png` or `preview.gif` in each pack's directory

**Output:**
```
Set preview for Pensubmic_Dungeon_v1.0: preview.gif
Set preview for Pensubmic_Forest_v2.1: preview.gif
Updated 2 pack(s)
```

## Implementation Logic

**Pack matching:**
- Query all packs from database
- Use `fnmatch` for glob patterns (e.g., `pensubmic_*` matches `Pensubmic_Dungeon_v1.0`)
- Case-insensitive matching
- If no packs match, print error and exit

**Preview file discovery (when no path given):**
- Look in pack's directory for: `preview.gif`, `preview.png` (in that order, preferring GIF for animation)
- If not found, skip that pack with a warning

**File copy:**
- Copy to `.assetindex/previews/{pack_name}.{ext}`
- Preserve original extension (gif/png)
- Overwrites any existing preview (auto-generated or custom)

**Database update:**
- Set `preview_path` to the new filename
- Set `preview_generated = FALSE` to mark it as custom

## Error Handling

**Errors that stop execution:**
- No packs match the pattern → `Error: No packs matching 'xyz_*' found`
- Explicit image path doesn't exist → `Error: File not found: /path/to/preview.gif`
- Explicit image path is not png/gif → `Error: Preview must be .png or .gif`

**Warnings that skip individual packs:**
- Convention-based lookup finds no preview file → `Warning: No preview.png/gif found in Pensubmic_Dungeon_v1.0, skipping`

**Final summary:**
- Always prints count: `Updated 2 pack(s)` or `No packs updated`

## Files to Modify

- `index.py`: Add `set-preview` subcommand with argparse
