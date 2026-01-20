# CLI Plain Text Output Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert assetsearch.py from Rich formatted tables to plain TSV output and add help subcommand.

**Architecture:** Remove Rich dependency, replace console.print() with print(), output tab-separated values. Add help command that prints usage info.

**Tech Stack:** Python 3.11+, typer, sqlite3

---

### Task 1: Remove Rich Dependency

**Files:**
- Modify: `assetsearch.py:1-18`

**Step 1: Update script header to remove rich**

Replace lines 1-18 with:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.9",
# ]
# ///
"""Search your game asset index."""

import sys
import sqlite3
from pathlib import Path
from typing import Optional

import typer
```

**Step 2: Remove console global**

Delete line 49: `console = Console()`

**Step 3: Verify script still parses**

Run: `python -m py_compile assetsearch.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: remove rich dependency from assetsearch"
```

---

### Task 2: Convert search Command to TSV

**Files:**
- Modify: `assetsearch.py:156-268`

**Step 1: Update search to output TSV**

Replace the search function (lines 156-268) with:

```python
@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search filename/path"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Filter by tag"),
    color: Optional[str] = typer.Option(None, "--color", "-c", help="Filter by dominant color (hex or name)"),
    pack: Optional[str] = typer.Option(None, "--pack", "-p", help="Filter by pack"),
    filetype: Optional[str] = typer.Option(None, "--type", help="Filter by filetype"),
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
):
    """Search assets by name, tags, or filters."""
    db_path = db or find_db()
    conn = get_db(db_path)

    # Build query
    conditions = []
    params = []

    if query:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    if pack:
        conditions.append("p.name LIKE ?")
        params.append(f"%{pack}%")

    if filetype:
        conditions.append("a.filetype = ?")
        params.append(filetype.lower().lstrip("."))

    if tag:
        for t in tag:
            conditions.append("""
                a.id IN (
                    SELECT at.asset_id FROM asset_tags at
                    JOIN tags t ON at.tag_id = t.id
                    WHERE t.name = ?
                )
            """)
            params.append(t.lower())

    if color:
        color_lower = color.lower()
        if color_lower in COLOR_NAMES:
            hex_values = COLOR_NAMES[color_lower]
            placeholders = ",".join("?" * len(hex_values))
            conditions.append(f"""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex IN ({placeholders})
                    AND percentage >= 0.1
                )
            """)
            params.extend(hex_values)
        else:
            conditions.append("""
                a.id IN (
                    SELECT asset_id FROM asset_colors
                    WHERE color_hex = ?
                    AND percentage >= 0.1
                )
            """)
            params.append(color if color.startswith("#") else f"#{color}")

    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.frame_count, p.name as pack_name,
               GROUP_CONCAT(DISTINCT t.name) as tags
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags t ON at.tag_id = t.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.filename
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()

    if not rows:
        print("No assets found.", file=sys.stderr)
        return

    for row in rows:
        size = f"{row['width']}x{row['height']}" if row['width'] else "-"
        if row['frame_count'] and row['frame_count'] > 1:
            size += f" ({row['frame_count']}f)"
        tags = row['tags'] or ""
        print(f"{row['id']}\t{row['path']}\t{size}\t{row['pack_name'] or '-'}\t{tags}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py search --limit 5`
Expected: TSV output with 5 rows, tab-separated

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert search command to TSV output"
```

---

### Task 3: Convert packs Command to TSV

**Files:**
- Modify: `assetsearch.py:271-306`

**Step 1: Update packs to output TSV**

Replace the packs function with:

```python
@app.command()
def packs(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
):
    """List all indexed packs."""
    db_path = db or find_db()
    conn = get_db(db_path)

    rows = conn.execute("""
        SELECT p.id, p.name, p.path, p.version, p.asset_count, p.preview_path
        FROM packs p
        ORDER BY p.name
    """).fetchall()

    if not rows:
        print("No packs indexed yet.", file=sys.stderr)
        return

    for row in rows:
        preview = row['preview_path'] or "-"
        print(f"{row['id']}\t{row['name']}\t{row['version'] or '-'}\t{row['asset_count']}\t{row['path']}\t{preview}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py packs`
Expected: TSV output with pack info

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert packs command to TSV output"
```

---

### Task 4: Convert tags Command to TSV

**Files:**
- Modify: `assetsearch.py:309-338`

**Step 1: Update tags to output TSV**

Replace the tags function with:

```python
@app.command()
def tags(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max tags to show"),
):
    """List all tags with counts."""
    db_path = db or find_db()
    conn = get_db(db_path)

    rows = conn.execute("""
        SELECT t.name, COUNT(at.asset_id) as count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY count DESC
        LIMIT ?
    """, [limit]).fetchall()

    if not rows:
        print("No tags found.", file=sys.stderr)
        return

    for row in rows:
        print(f"{row['name']}\t{row['count']}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py tags --limit 10`
Expected: TSV output with tag names and counts

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert tags command to TSV output"
```

---

### Task 5: Convert info Command to TSV

**Files:**
- Modify: `assetsearch.py:341-408`

**Step 1: Update info to output TSV**

Replace the info function with:

```python
@app.command()
def info(
    asset_id: int = typer.Argument(..., help="Asset ID"),
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
):
    """Show detailed info for an asset."""
    db_path = db or find_db()
    conn = get_db(db_path)

    row = conn.execute("""
        SELECT a.*, p.name as pack_name
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE a.id = ?
    """, [asset_id]).fetchone()

    if not row:
        print(f"Asset {asset_id} not found.", file=sys.stderr)
        raise typer.Exit(1)

    print(row['path'])
    print(f"pack\t{row['pack_name'] or '-'}")
    print(f"type\t{row['filetype']}")
    print(f"size\t{row['file_size']}")
    if row['width']:
        print(f"dimensions\t{row['width']}x{row['height']}")
    if row['frame_count']:
        print(f"frames\t{row['frame_count']}\t{row['frame_width']}x{row['frame_height']}")

    # Tags
    tags = conn.execute("""
        SELECT t.name
        FROM asset_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.asset_id = ?
        ORDER BY t.name
    """, [asset_id]).fetchall()

    if tags:
        print(f"tags\t{','.join(t['name'] for t in tags)}")

    # Colors
    colors = conn.execute("""
        SELECT color_hex, percentage
        FROM asset_colors
        WHERE asset_id = ?
        ORDER BY percentage DESC
    """, [asset_id]).fetchall()

    if colors:
        color_str = ",".join(f"{c['color_hex']}:{c['percentage']:.0%}" for c in colors)
        print(f"colors\t{color_str}")

    # Related
    related = conn.execute("""
        SELECT a.filename, ar.relation_type
        FROM asset_relations ar
        JOIN assets a ON ar.related_id = a.id
        WHERE ar.asset_id = ?
    """, [asset_id]).fetchall()

    if related:
        related_str = ",".join(f"{r['filename']}:{r['relation_type']}" for r in related)
        print(f"related\t{related_str}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py info 1`
Expected: Key-value TSV output

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert info command to TSV output"
```

---

### Task 6: Convert stats Command to TSV

**Files:**
- Modify: `assetsearch.py:411-437`

**Step 1: Update stats to output TSV**

Replace the stats function with:

```python
@app.command()
def stats(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
):
    """Show index statistics."""
    db_path = db or find_db()
    conn = get_db(db_path)

    pack_count = conn.execute("SELECT COUNT(*) FROM packs").fetchone()[0]
    asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    tag_count = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]

    filetypes = conn.execute("""
        SELECT filetype, COUNT(*) as count
        FROM assets
        GROUP BY filetype
        ORDER BY count DESC
    """).fetchall()

    print(f"packs\t{pack_count}")
    print(f"assets\t{asset_count}")
    print(f"tags\t{tag_count}")
    for ft in filetypes:
        print(f"{ft['filetype']}\t{ft['count']}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py stats`
Expected: Key-value TSV output

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert stats command to TSV output"
```

---

### Task 7: Convert similar Command to TSV

**Files:**
- Modify: `assetsearch.py:440-520`

**Step 1: Update similar to output TSV**

Replace the similar function with:

```python
@app.command()
def similar(
    reference: str = typer.Argument(..., help="Asset ID or path to image"),
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    max_distance: int = typer.Option(15, "--distance", "-d", help="Max hamming distance"),
):
    """Find visually similar assets."""
    db_path = db or find_db()
    conn = get_db(db_path)

    # Get reference hash
    ref_hash = None
    ref_name = reference

    if reference.isdigit():
        row = conn.execute(
            "SELECT phash FROM asset_phash WHERE asset_id = ?", [int(reference)]
        ).fetchone()
        if row:
            ref_hash = row["phash"]
    else:
        row = conn.execute(
            "SELECT ap.phash FROM asset_phash ap JOIN assets a ON ap.asset_id = a.id WHERE a.path LIKE ?",
            [f"%{reference}%"]
        ).fetchone()
        if row:
            ref_hash = row["phash"]
        elif Path(reference).exists():
            try:
                import imagehash
                from PIL import Image
                with Image.open(reference) as img:
                    h = imagehash.phash(img)
                    ref_hash = h.hash.tobytes()
                    ref_name = Path(reference).name
            except ImportError:
                print("Install imagehash for external file similarity: pip install imagehash", file=sys.stderr)
                raise typer.Exit(1)

    if not ref_hash:
        print(f"Could not find or compute hash for: {reference}", file=sys.stderr)
        raise typer.Exit(1)

    # Find similar
    results = []
    for row in conn.execute("""
        SELECT ap.asset_id, ap.phash, a.filename, a.path, p.name as pack_name
        FROM asset_phash ap
        JOIN assets a ON ap.asset_id = a.id
        LEFT JOIN packs p ON a.pack_id = p.id
    """):
        dist = hamming_distance(ref_hash, row["phash"])
        if dist <= max_distance and dist > 0:
            results.append((dist, row))

    results.sort(key=lambda x: x[0])
    results = results[:limit]

    if not results:
        print(f"No similar assets found for {ref_name}", file=sys.stderr)
        return

    for dist, row in results:
        print(f"{dist}\t{row['asset_id']}\t{row['path']}\t{row['pack_name'] or '-'}")
```

**Step 2: Test manually**

Run: `uv run assetsearch.py similar 1`
Expected: TSV output with distance, ID, path, pack

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "refactor: convert similar command to TSV output"
```

---

### Task 8: Add help Command

**Files:**
- Modify: `assetsearch.py` (add before `if __name__ == "__main__":`)

**Step 1: Add help command**

Add this function before the `if __name__ == "__main__":` block:

```python
COMMAND_HELP = {
    "search": {
        "desc": "Search assets by name, tags, or filters",
        "usage": "assetsearch.py search [QUERY] [OPTIONS]",
        "args": [
            ("QUERY", "Search filename/path"),
        ],
        "opts": [
            ("-t, --tag TAG", "Filter by tag (can repeat)"),
            ("-c, --color COLOR", "Filter by dominant color (hex or name)"),
            ("-p, --pack PACK", "Filter by pack"),
            ("--type TYPE", "Filter by filetype"),
            ("--db PATH", "Path to assets.db"),
            ("-n, --limit N", "Max results (default: 50)"),
        ],
    },
    "packs": {
        "desc": "List all indexed packs",
        "usage": "assetsearch.py packs [OPTIONS]",
        "args": [],
        "opts": [
            ("--db PATH", "Path to assets.db"),
        ],
    },
    "tags": {
        "desc": "List all tags with counts",
        "usage": "assetsearch.py tags [OPTIONS]",
        "args": [],
        "opts": [
            ("--db PATH", "Path to assets.db"),
            ("-n, --limit N", "Max tags to show (default: 50)"),
        ],
    },
    "info": {
        "desc": "Show detailed info for an asset",
        "usage": "assetsearch.py info ASSET_ID [OPTIONS]",
        "args": [
            ("ASSET_ID", "Asset ID"),
        ],
        "opts": [
            ("--db PATH", "Path to assets.db"),
        ],
    },
    "stats": {
        "desc": "Show index statistics",
        "usage": "assetsearch.py stats [OPTIONS]",
        "args": [],
        "opts": [
            ("--db PATH", "Path to assets.db"),
        ],
    },
    "similar": {
        "desc": "Find visually similar assets",
        "usage": "assetsearch.py similar REFERENCE [OPTIONS]",
        "args": [
            ("REFERENCE", "Asset ID or path to image"),
        ],
        "opts": [
            ("--db PATH", "Path to assets.db"),
            ("-n, --limit N", "Max results (default: 10)"),
            ("-d, --distance N", "Max hamming distance (default: 15)"),
        ],
    },
    "help": {
        "desc": "Show help for a command",
        "usage": "assetsearch.py help [COMMAND]",
        "args": [
            ("COMMAND", "Command name"),
        ],
        "opts": [],
    },
}


@app.command()
def help(
    command: Optional[str] = typer.Argument(None, help="Command name"),
):
    """Show help for a command."""
    if command is None:
        print("assetsearch - Search your game asset index")
        print()
        print("Commands:")
        for name, info in COMMAND_HELP.items():
            print(f"  {name:10s} {info['desc']}")
        print()
        print("Use 'assetsearch.py help <command>' for details.")
        return

    if command not in COMMAND_HELP:
        print(f"Unknown command: {command}", file=sys.stderr)
        raise typer.Exit(1)

    info = COMMAND_HELP[command]
    print(f"{command} - {info['desc']}")
    print()
    print(f"Usage: {info['usage']}")

    if info['args']:
        print()
        print("Arguments:")
        for arg, desc in info['args']:
            print(f"  {arg:20s} {desc}")

    if info['opts']:
        print()
        print("Options:")
        for opt, desc in info['opts']:
            print(f"  {opt:20s} {desc}")
```

**Step 2: Test help command**

Run: `uv run assetsearch.py help`
Expected: List of commands

Run: `uv run assetsearch.py help search`
Expected: Detailed search help

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "feat: add help subcommand"
```

---

### Task 9: Final Verification

**Step 1: Verify all commands work**

Run each command and verify TSV output:

```bash
uv run assetsearch.py search --limit 3
uv run assetsearch.py packs
uv run assetsearch.py tags --limit 5
uv run assetsearch.py info 1
uv run assetsearch.py stats
uv run assetsearch.py help
uv run assetsearch.py help search
```

**Step 2: Test piping**

```bash
uv run assetsearch.py search --limit 3 | cut -f2
```

Expected: Just the paths, one per line

**Step 3: Final commit if any fixes needed**

```bash
git add assetsearch.py
git commit -m "fix: address any issues from final verification"
```
