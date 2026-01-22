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

# Basic color name to hex ranges
COLOR_NAMES = {
    "red": ("#ff0000", "#cc0000", "#990000", "#ff3333", "#cc3333"),
    "green": ("#00ff00", "#00cc00", "#009900", "#33ff33", "#33cc33", "#336633", "#669966"),
    "blue": ("#0000ff", "#0000cc", "#000099", "#3333ff", "#3333cc", "#333366"),
    "yellow": ("#ffff00", "#cccc00", "#999900", "#ffff33"),
    "orange": ("#ff8800", "#ff6600", "#cc6600", "#ff9933"),
    "purple": ("#ff00ff", "#cc00cc", "#990099", "#9900ff", "#6600cc"),
    "brown": ("#8b4513", "#a0522d", "#cd853f", "#d2691e", "#8b5a2b"),
    "black": ("#000000", "#111111", "#222222", "#333333"),
    "white": ("#ffffff", "#eeeeee", "#dddddd", "#cccccc"),
    "gray": ("#888888", "#999999", "#aaaaaa", "#777777", "#666666"),
    "grey": ("#888888", "#999999", "#aaaaaa", "#777777", "#666666"),
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def color_distance(c1: str, c2: str) -> float:
    """Calculate distance between two hex colors."""
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2) ** 0.5


app = typer.Typer(help="Search your game asset index")

SCHEMA = """
-- Asset packs (top-level grouping)
CREATE TABLE IF NOT EXISTS packs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    version TEXT,
    preview_path TEXT,
    preview_generated BOOLEAN DEFAULT FALSE,
    asset_count INTEGER DEFAULT 0,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual asset files
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    pack_id INTEGER REFERENCES packs(id),
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    filetype TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    preview_x INTEGER,
    preview_y INTEGER,
    preview_width INTEGER,
    preview_height INTEGER,
    category TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Related assets (sprite <-> shadow <-> gif)
CREATE TABLE IF NOT EXISTS asset_relations (
    asset_id INTEGER REFERENCES assets(id),
    related_id INTEGER REFERENCES assets(id),
    relation_type TEXT,
    PRIMARY KEY (asset_id, related_id)
);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER REFERENCES assets(id),
    tag_id INTEGER REFERENCES tags(id),
    source TEXT,
    PRIMARY KEY (asset_id, tag_id)
);

-- Dominant colors per asset
CREATE TABLE IF NOT EXISTS asset_colors (
    asset_id INTEGER REFERENCES assets(id),
    color_hex TEXT,
    percentage REAL,
    PRIMARY KEY (asset_id, color_hex)
);

-- Perceptual hash for similarity
CREATE TABLE IF NOT EXISTS asset_phash (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    phash BLOB
);

-- Optional CLIP embeddings
CREATE TABLE IF NOT EXISTS asset_embeddings (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    embedding BLOB
);

-- Indexes for fast search
CREATE INDEX IF NOT EXISTS idx_assets_filename ON assets(filename);
CREATE INDEX IF NOT EXISTS idx_assets_filetype ON assets(filetype);
CREATE INDEX IF NOT EXISTS idx_assets_pack_id ON assets(pack_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_asset_id ON asset_tags(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id ON asset_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_asset_colors_color ON asset_colors(color_hex);
"""


def get_db(db_path: Path) -> sqlite3.Connection:
    """Get database connection, creating schema if needed."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def find_db() -> Path:
    """Find assets.db in current directory or parent directories."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        db_path = parent / "assets.db"
        if db_path.exists():
            return db_path
    raise typer.BadParameter("No assets.db found. Run assetindex.py first.")


def hamming_distance(h1: bytes, h2: bytes) -> int:
    """Calculate hamming distance between two hashes."""
    return sum(bin(a ^ b).count("1") for a, b in zip(h1, h2))


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
               a.preview_width, a.preview_height, p.name as pack_name,
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
        if row['preview_width'] and row['preview_height']:
            size += f" (preview: {row['preview_width']}x{row['preview_height']})"
        tags = row['tags'] or ""
        print(f"{row['id']}\t{row['path']}\t{size}\t{row['pack_name'] or '-'}\t{tags}")


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
    if row['preview_x'] is not None:
        print(f"preview\t{row['preview_x']},{row['preview_y']}\t{row['preview_width']}x{row['preview_height']}")

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


if __name__ == "__main__":
    app()
