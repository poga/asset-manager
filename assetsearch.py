#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.0",
#     "typer>=0.9",
# ]
# ///
"""Search your game asset index."""

import sqlite3
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

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
console = Console()

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
    frame_count INTEGER,
    frame_width INTEGER,
    frame_height INTEGER,
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
        # All tags must match (AND)
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
        # Resolve color name to hex values
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
            # Direct hex match (with some tolerance)
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
        console.print("[yellow]No assets found.[/yellow]")
        return

    table = Table(title=f"Assets ({len(rows)} results)")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Filename", style="cyan")
    table.add_column("Size", width=10)
    table.add_column("Pack", style="green")
    table.add_column("Tags", style="yellow")

    for row in rows:
        size = f"{row['width']}x{row['height']}" if row['width'] else "-"
        if row['frame_count'] and row['frame_count'] > 1:
            size += f" ({row['frame_count']}f)"
        tags = row['tags'] or ""
        if len(tags) > 30:
            tags = tags[:27] + "..."
        table.add_row(
            str(row['id']),
            row['filename'],
            size,
            row['pack_name'] or "-",
            tags,
        )

    console.print(table)


@app.command()
def packs(
    db: Optional[Path] = typer.Option(None, "--db", help="Path to assets.db"),
):
    """List all indexed packs."""
    db_path = db or find_db()
    conn = get_db(db_path)

    rows = conn.execute("""
        SELECT p.id, p.name, p.version, p.asset_count, p.preview_path
        FROM packs p
        ORDER BY p.name
    """).fetchall()

    if not rows:
        console.print("[yellow]No packs indexed yet.[/yellow]")
        return

    table = Table(title="Asset Packs")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Version", width=8)
    table.add_column("Assets", justify="right", width=8)
    table.add_column("Preview", style="green")

    for row in rows:
        preview = "Yes" if row['preview_path'] else "No"
        table.add_row(
            str(row['id']),
            row['name'],
            row['version'] or "-",
            str(row['asset_count']),
            preview,
        )

    console.print(table)


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
        console.print("[yellow]No tags found.[/yellow]")
        return

    table = Table(title="Tags")
    table.add_column("Tag", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for row in rows:
        table.add_row(row['name'], str(row['count']))

    console.print(table)


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
        console.print(f"[red]Asset {asset_id} not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]{row['filename']}[/bold cyan]")
    console.print(f"  Path: {row['path']}")
    console.print(f"  Pack: {row['pack_name'] or '-'}")
    console.print(f"  Type: {row['filetype']}")
    console.print(f"  Size: {row['file_size']} bytes")
    if row['width']:
        console.print(f"  Dimensions: {row['width']}x{row['height']}")
    if row['frame_count']:
        console.print(f"  Frames: {row['frame_count']} ({row['frame_width']}x{row['frame_height']} each)")

    # Tags
    tags = conn.execute("""
        SELECT t.name, at.source
        FROM asset_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.asset_id = ?
        ORDER BY t.name
    """, [asset_id]).fetchall()

    if tags:
        console.print(f"  Tags: {', '.join(t['name'] for t in tags)}")

    # Colors
    colors = conn.execute("""
        SELECT color_hex, percentage
        FROM asset_colors
        WHERE asset_id = ?
        ORDER BY percentage DESC
    """, [asset_id]).fetchall()

    if colors:
        color_str = ", ".join(f"{c['color_hex']} ({c['percentage']:.0%})" for c in colors)
        console.print(f"  Colors: {color_str}")

    # Related
    related = conn.execute("""
        SELECT a.filename, ar.relation_type
        FROM asset_relations ar
        JOIN assets a ON ar.related_id = a.id
        WHERE ar.asset_id = ?
    """, [asset_id]).fetchall()

    if related:
        console.print("  Related:")
        for r in related:
            console.print(f"    - {r['filename']} ({r['relation_type']})")

    console.print()


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

    console.print(f"\n[bold]Index Statistics[/bold]")
    console.print(f"  Packs: {pack_count}")
    console.print(f"  Assets: {asset_count}")
    console.print(f"  Tags: {tag_count}")
    console.print(f"  File types:")
    for ft in filetypes:
        console.print(f"    - {ft['filetype']}: {ft['count']}")
    console.print()


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
        # By ID
        row = conn.execute(
            "SELECT phash FROM asset_phash WHERE asset_id = ?", [int(reference)]
        ).fetchone()
        if row:
            ref_hash = row["phash"]
    else:
        # By path (in DB or external file)
        row = conn.execute(
            "SELECT ap.phash FROM asset_phash ap JOIN assets a ON ap.asset_id = a.id WHERE a.path LIKE ?",
            [f"%{reference}%"]
        ).fetchone()
        if row:
            ref_hash = row["phash"]
        elif Path(reference).exists():
            # External file - compute hash
            try:
                import imagehash
                from PIL import Image
                with Image.open(reference) as img:
                    h = imagehash.phash(img)
                    ref_hash = h.hash.tobytes()
                    ref_name = Path(reference).name
            except ImportError:
                console.print("[red]Install imagehash for external file similarity: pip install imagehash[/red]")
                raise typer.Exit(1)

    if not ref_hash:
        console.print(f"[red]Could not find or compute hash for: {reference}[/red]")
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
        if dist <= max_distance and dist > 0:  # Exclude exact match
            results.append((dist, row))

    results.sort(key=lambda x: x[0])
    results = results[:limit]

    if not results:
        console.print(f"[yellow]No similar assets found for {ref_name}[/yellow]")
        return

    table = Table(title=f"Similar to {ref_name}")
    table.add_column("Dist", style="dim", width=4)
    table.add_column("ID", style="dim", width=6)
    table.add_column("Filename", style="cyan")
    table.add_column("Pack", style="green")

    for dist, row in results:
        table.add_row(
            str(dist),
            str(row["asset_id"]),
            row["filename"],
            row["pack_name"] or "-",
        )

    console.print(table)


if __name__ == "__main__":
    app()
