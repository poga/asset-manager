# Random Default Search Results

## Goal

Make default search results (with no filters) randomly sorted to improve asset discoverability.

## Behavior

- **Empty search** (no q, no tag, no color, no pack, no type): Results ordered randomly via `ORDER BY RANDOM()`
- **Any filter active**: Results ordered deterministically via `ORDER BY a.path`

## Implementation

Single change in `web/api.py` search function (~line 206):

```python
# Determine ordering
is_empty_search = not q and not tag and not color and not pack and not type
order_by = "RANDOM()" if is_empty_search else "a.path"

sql = f"""
    SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
           a.preview_x, a.preview_y, a.preview_width, a.preview_height,
           p.name as pack_name,
           GROUP_CONCAT(DISTINCT tg.name) as tags
    FROM assets a
    LEFT JOIN packs p ON a.pack_id = p.id
    LEFT JOIN asset_tags at ON a.id = at.asset_id
    LEFT JOIN tags tg ON at.tag_id = tg.id
    WHERE {where}
    GROUP BY a.id
    ORDER BY {order_by}
    LIMIT ?
"""
```

## Why SQL RANDOM()

- Simple, minimal code change
- Efficient for result set size (LIMIT 100)
- No schema changes needed
- No frontend changes needed

## Testing

- Verify empty search returns different order on refresh
- Verify filtered search returns consistent order
