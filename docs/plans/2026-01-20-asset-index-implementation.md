# Asset Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a SQLite-based game asset index with search, autotagging, and visual similarity features as single-file uv scripts.

**Architecture:** Two standalone Python scripts with inline uv dependencies. `assetindex.py` handles indexing (heavier deps: pillow, imagehash). `assetsearch.py` handles queries (minimal deps: rich, typer). Both share the same SQLite database.

**Tech Stack:** Python 3.11+, SQLite, uv (inline script dependencies), Pillow, imagehash, typer, rich

---

## Phase 1: Core Index (MVP)

### Task 1: Create assetsearch.py with schema setup

**Files:**
- Create: `assetsearch.py`

**Step 1: Create the search script with schema**

Create `assetsearch.py` with inline uv dependencies and database schema:

```python
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


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Search filename/path"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Filter by tag"),
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


if __name__ == "__main__":
    app()
```

**Step 2: Make executable and test**

Run:
```bash
chmod +x assetsearch.py
uv run assetsearch.py --help
```

Expected: Help output showing search, packs, tags, info, stats commands.

**Step 3: Commit**

```bash
git add assetsearch.py
git commit -m "feat: add assetsearch.py with schema and search commands"
```

---

### Task 2: Create assetindex.py with file scanning

**Files:**
- Create: `assetindex.py`

**Step 1: Create the indexer script**

Create `assetindex.py` with file scanning and basic metadata:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pillow>=10.0",
#     "imagehash>=4.3",
#     "rich>=13.0",
#     "typer>=0.9",
# ]
# ///
"""Build and update the game asset index."""

import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

app = typer.Typer(help="Build and update the game asset index")
console = Console()

# Supported asset types
IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
ASSET_EXTENSIONS = IMAGE_EXTENSIONS | {".aseprite", ".ase"}

# Noise words to skip in tag extraction
NOISE_WORDS = {
    "assets", "asset", "commercial", "version", "free", "v", "the", "and", "or",
    "gifs", "gif", "shadows", "shadow", "animationinfo", "txt", "png",
}

# Tag aliases for normalization
TAG_ALIASES = {
    "dmg": "damage",
    "atk": "attack",
    "char": "character",
    "chars": "characters",
    "anim": "animation",
    "anims": "animations",
}

# Schema (same as assetsearch.py)
SCHEMA = """
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

CREATE TABLE IF NOT EXISTS asset_relations (
    asset_id INTEGER REFERENCES assets(id),
    related_id INTEGER REFERENCES assets(id),
    relation_type TEXT,
    PRIMARY KEY (asset_id, related_id)
);

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

CREATE TABLE IF NOT EXISTS asset_colors (
    asset_id INTEGER REFERENCES assets(id),
    color_hex TEXT,
    percentage REAL,
    PRIMARY KEY (asset_id, color_hex)
);

CREATE TABLE IF NOT EXISTS asset_phash (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    phash BLOB
);

CREATE TABLE IF NOT EXISTS asset_embeddings (
    asset_id INTEGER PRIMARY KEY REFERENCES assets(id),
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_assets_filename ON assets(filename);
CREATE INDEX IF NOT EXISTS idx_assets_filetype ON assets(filetype);
CREATE INDEX IF NOT EXISTS idx_assets_pack_id ON assets(pack_id);
CREATE INDEX IF NOT EXISTS idx_assets_file_hash ON assets(file_hash);
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


def file_hash(path: Path) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_version(name: str) -> Optional[str]:
    """Extract version number from pack name."""
    match = re.search(r"v(\d+(?:\.\d+)*)", name, re.IGNORECASE)
    return match.group(1) if match else None


def get_image_info(path: Path) -> dict:
    """Extract image dimensions and frame info."""
    try:
        with Image.open(path) as img:
            width, height = img.size
            # Detect spritesheet frames (assume square frames if width > height)
            frame_count = 1
            frame_width = width
            frame_height = height
            if width > height and height > 0 and width % height == 0:
                frame_count = width // height
                frame_width = height
            elif height > width and width > 0 and height % width == 0:
                frame_count = height // width
                frame_height = width
            return {
                "width": width,
                "height": height,
                "frame_count": frame_count,
                "frame_width": frame_width,
                "frame_height": frame_height,
            }
    except Exception:
        return {}


def extract_tags_from_path(path: Path, asset_root: Path) -> list[str]:
    """Extract tags from file path."""
    rel_path = path.relative_to(asset_root)
    tags = set()

    # Split path components and filename
    parts = list(rel_path.parts[:-1]) + [rel_path.stem]

    for part in parts:
        # Split on underscores and other separators
        words = re.split(r"[_\-\s]+", part)
        for word in words:
            # Skip version numbers
            if re.match(r"^v?\d+(\.\d+)*$", word, re.IGNORECASE):
                continue
            # Normalize
            word = word.lower()
            if word in NOISE_WORDS or len(word) < 2:
                continue
            # Apply aliases
            word = TAG_ALIASES.get(word, word)
            tags.add(word)

    # Detect action from filename
    filename_lower = path.stem.lower()
    actions = ["attack", "idle", "walk", "run", "jump", "die", "damage", "hit", "cast", "shoot"]
    for action in actions:
        if action in filename_lower:
            tags.add(action)

    return sorted(tags)


def detect_pack(path: Path, asset_root: Path) -> tuple[str, Path]:
    """Detect pack name and path from asset path."""
    rel_path = path.relative_to(asset_root)
    # Pack is typically the first directory level
    if len(rel_path.parts) > 1:
        pack_name = rel_path.parts[0]
        pack_path = asset_root / pack_name
        return pack_name, pack_path
    return "", asset_root


def get_category(path: Path, pack_path: Path) -> str:
    """Get category from path relative to pack."""
    try:
        rel = path.relative_to(pack_path)
        if len(rel.parts) > 1:
            return "/".join(rel.parts[:-1])
    except ValueError:
        pass
    return ""


def add_tags(conn: sqlite3.Connection, asset_id: int, tags: list[str], source: str):
    """Add tags to an asset."""
    for tag in tags:
        # Get or create tag
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", [tag])
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", [tag]).fetchone()[0]
        # Link to asset
        conn.execute(
            "INSERT OR IGNORE INTO asset_tags (asset_id, tag_id, source) VALUES (?, ?, ?)",
            [asset_id, tag_id, source]
        )


def scan_assets(asset_root: Path) -> list[Path]:
    """Scan directory for asset files."""
    assets = []
    for ext in ASSET_EXTENSIONS:
        assets.extend(asset_root.rglob(f"*{ext}"))
    return sorted(assets)


@app.command()
def index(
    asset_path: Path = typer.Argument(..., help="Path to assets directory"),
    db: Path = typer.Option("assets.db", "--db", help="Output database path"),
    force: bool = typer.Option(False, "--force", "-f", help="Force full reindex"),
):
    """Index assets from a directory."""
    asset_root = asset_path.resolve()
    if not asset_root.is_dir():
        console.print(f"[red]Not a directory: {asset_root}[/red]")
        raise typer.Exit(1)

    conn = get_db(db)
    console.print(f"Indexing [cyan]{asset_root}[/cyan] -> [green]{db}[/green]")

    # Get existing hashes for incremental update
    existing = {}
    if not force:
        for row in conn.execute("SELECT path, file_hash FROM assets"):
            existing[row["path"]] = row["file_hash"]

    # Scan for assets
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        scan_task = progress.add_task("Scanning...", total=None)
        files = scan_assets(asset_root)
        progress.update(scan_task, completed=True, total=1)

        # Track packs
        packs_seen = {}

        # Index each file
        index_task = progress.add_task("Indexing...", total=len(files))
        new_count = 0
        skip_count = 0

        for file_path in files:
            rel_path = str(file_path.relative_to(asset_root))

            # Check if unchanged
            current_hash = file_hash(file_path)
            if rel_path in existing and existing[rel_path] == current_hash:
                skip_count += 1
                progress.advance(index_task)
                continue

            # Detect pack
            pack_name, pack_path = detect_pack(file_path, asset_root)
            if pack_name and pack_name not in packs_seen:
                pack_rel = str(pack_path.relative_to(asset_root))
                version = extract_version(pack_name)
                conn.execute(
                    """INSERT OR REPLACE INTO packs (name, path, version, indexed_at)
                       VALUES (?, ?, ?, ?)""",
                    [pack_name, pack_rel, version, datetime.now()]
                )
                pack_id = conn.execute("SELECT id FROM packs WHERE path = ?", [pack_rel]).fetchone()[0]
                packs_seen[pack_name] = pack_id
            pack_id = packs_seen.get(pack_name)

            # Get image info
            img_info = get_image_info(file_path) if file_path.suffix.lower() in IMAGE_EXTENSIONS else {}

            # Category
            category = get_category(file_path, pack_path) if pack_name else ""

            # Insert or update asset
            conn.execute(
                """INSERT OR REPLACE INTO assets
                   (pack_id, path, filename, filetype, file_hash, file_size,
                    width, height, frame_count, frame_width, frame_height, category, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    pack_id,
                    rel_path,
                    file_path.name,
                    file_path.suffix.lower().lstrip("."),
                    current_hash,
                    file_path.stat().st_size,
                    img_info.get("width"),
                    img_info.get("height"),
                    img_info.get("frame_count"),
                    img_info.get("frame_width"),
                    img_info.get("frame_height"),
                    category,
                    datetime.now(),
                ]
            )
            asset_id = conn.execute("SELECT id FROM assets WHERE path = ?", [rel_path]).fetchone()[0]

            # Extract and add tags
            tags = extract_tags_from_path(file_path, asset_root)
            add_tags(conn, asset_id, tags, "path")

            new_count += 1
            progress.advance(index_task)

        conn.commit()

    # Update pack asset counts
    conn.execute("""
        UPDATE packs SET asset_count = (
            SELECT COUNT(*) FROM assets WHERE assets.pack_id = packs.id
        )
    """)
    conn.commit()

    console.print(f"\n[green]Done![/green] Indexed {new_count} new/changed, skipped {skip_count} unchanged.")

    # Show stats
    pack_count = conn.execute("SELECT COUNT(*) FROM packs").fetchone()[0]
    asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    console.print(f"Total: {pack_count} packs, {asset_count} assets")


@app.command()
def update(
    db: Path = typer.Option("assets.db", "--db", help="Database path"),
):
    """Update index (incremental, hash-based)."""
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        console.print("Run 'assetindex.py index <path>' first.")
        raise typer.Exit(1)

    # Get asset root from first pack
    conn = get_db(db)
    row = conn.execute("SELECT path FROM packs LIMIT 1").fetchone()
    if not row:
        console.print("[yellow]No packs in database. Run index command first.[/yellow]")
        raise typer.Exit(1)

    # Infer asset root from pack paths
    pack_path = Path(row["path"])
    asset_root = db.parent
    if not (asset_root / pack_path).exists():
        console.print(f"[red]Asset root not found. Expected packs at: {asset_root}[/red]")
        raise typer.Exit(1)

    # Re-run index
    console.print(f"Updating index from [cyan]{asset_root}[/cyan]")
    index(asset_root, db, force=False)


if __name__ == "__main__":
    app()
```

**Step 2: Make executable and test**

Run:
```bash
chmod +x assetindex.py
uv run assetindex.py --help
```

Expected: Help output showing index and update commands.

**Step 3: Test indexing on minifantasy**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db
```

Expected: Progress bar, summary showing packs and assets indexed.

**Step 4: Test search**

Run:
```bash
uv run assetsearch.py goblin
uv run assetsearch.py --tag attack
uv run assetsearch.py packs
uv run assetsearch.py stats
```

Expected: Results tables showing matching assets.

**Step 5: Commit**

```bash
git add assetindex.py
git commit -m "feat: add assetindex.py with file scanning and autotagging"
```

---

### Task 3: Add color extraction

**Files:**
- Modify: `assetindex.py`

**Step 1: Add color extraction function**

Add after the `get_image_info` function in `assetindex.py`:

```python
def extract_colors(path: Path, num_colors: int = 5) -> list[tuple[str, float]]:
    """Extract dominant colors from image."""
    try:
        with Image.open(path) as img:
            # Convert to RGB, ignore alpha
            img = img.convert("RGB")
            # Resize for speed
            img.thumbnail((100, 100))
            # Get colors
            colors = img.getcolors(maxcolors=10000)
            if not colors:
                return []
            # Sort by count
            colors.sort(key=lambda x: x[0], reverse=True)
            total = sum(c[0] for c in colors)
            # Get top colors
            result = []
            for count, rgb in colors[:num_colors]:
                hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
                percentage = count / total
                if percentage >= 0.05:  # At least 5%
                    result.append((hex_color, percentage))
            return result
    except Exception:
        return []
```

**Step 2: Add color indexing to the index loop**

In the `index` function, after `add_tags(conn, asset_id, tags, "path")`, add:

```python
            # Extract colors for images
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                colors = extract_colors(file_path)
                for hex_color, percentage in colors:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage)
                           VALUES (?, ?, ?)""",
                        [asset_id, hex_color, percentage]
                    )
```

**Step 3: Test color extraction**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db --force
uv run assetsearch.py info 1
```

Expected: Asset info shows colors.

**Step 4: Commit**

```bash
git add assetindex.py
git commit -m "feat: add color extraction to indexer"
```

---

### Task 4: Add color search to assetsearch.py

**Files:**
- Modify: `assetsearch.py`

**Step 1: Add color option to search command**

In `assetsearch.py`, update the `search` function signature to add:

```python
    color: Optional[str] = typer.Option(None, "--color", "-c", help="Filter by dominant color (hex or name)"),
```

**Step 2: Add color name mapping**

Add near the top of the file:

```python
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
```

**Step 3: Add color filter to search query**

In the `search` function, after the `if tag:` block, add:

```python
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
```

**Step 4: Test color search**

Run:
```bash
uv run assetsearch.py --color green
uv run assetsearch.py --color "#8b4513"
```

Expected: Assets with matching dominant colors.

**Step 5: Commit**

```bash
git add assetsearch.py
git commit -m "feat: add color search to assetsearch.py"
```

---

### Task 5: Add perceptual hash and similarity search

**Files:**
- Modify: `assetindex.py`
- Modify: `assetsearch.py`

**Step 1: Add phash computation to assetindex.py**

Add import at top of `assetindex.py`:

```python
import imagehash
```

Add function after `extract_colors`:

```python
def compute_phash(path: Path) -> Optional[bytes]:
    """Compute perceptual hash of image."""
    try:
        with Image.open(path) as img:
            h = imagehash.phash(img)
            return h.hash.tobytes()
    except Exception:
        return None
```

**Step 2: Add phash indexing to the index loop**

After the color extraction block, add:

```python
                # Compute perceptual hash
                phash = compute_phash(file_path)
                if phash:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_phash (asset_id, phash)
                           VALUES (?, ?)""",
                        [asset_id, phash]
                    )
```

**Step 3: Add similar command to assetsearch.py**

Add import:

```python
import struct
```

Add function:

```python
def hamming_distance(h1: bytes, h2: bytes) -> int:
    """Calculate hamming distance between two hashes."""
    return sum(bin(a ^ b).count("1") for a, b in zip(h1, h2))
```

Add command:

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
```

**Step 4: Test similarity search**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db --force
uv run assetsearch.py similar 1
```

Expected: List of visually similar assets.

**Step 5: Commit**

```bash
git add assetindex.py assetsearch.py
git commit -m "feat: add perceptual hash and similarity search"
```

---

### Task 6: Add pack preview generation

**Files:**
- Modify: `assetindex.py`

**Step 1: Add preview generation function**

Add after `compute_phash`:

```python
def generate_pack_preview(
    conn: sqlite3.Connection,
    pack_id: int,
    asset_root: Path,
    preview_dir: Path,
    grid_size: int = 4,
    thumb_size: int = 64,
) -> Optional[str]:
    """Generate a preview montage for a pack."""
    # Get representative assets (prefer idle animations)
    rows = conn.execute("""
        SELECT path, filename FROM assets
        WHERE pack_id = ?
        AND filetype = 'png'
        ORDER BY
            CASE WHEN filename LIKE '%Idle%' THEN 0 ELSE 1 END,
            category,
            filename
        LIMIT ?
    """, [pack_id, grid_size * grid_size]).fetchall()

    if len(rows) < 4:
        return None

    # Create montage
    preview_dir.mkdir(parents=True, exist_ok=True)
    pack_row = conn.execute("SELECT name FROM packs WHERE id = ?", [pack_id]).fetchone()
    preview_name = f"{pack_row['name']}.png"
    preview_path = preview_dir / preview_name

    try:
        montage = Image.new("RGBA", (grid_size * thumb_size, grid_size * thumb_size), (0, 0, 0, 0))

        for i, row in enumerate(rows):
            x = (i % grid_size) * thumb_size
            y = (i // grid_size) * thumb_size

            img_path = asset_root / row["path"]
            with Image.open(img_path) as img:
                # For spritesheets, take first frame
                if img.width > img.height:
                    frame_w = img.height
                    img = img.crop((0, 0, frame_w, frame_w))
                elif img.height > img.width:
                    frame_h = img.width
                    img = img.crop((0, 0, frame_h, frame_h))

                img.thumbnail((thumb_size, thumb_size), Image.Resampling.NEAREST)
                # Center in cell
                offset_x = (thumb_size - img.width) // 2
                offset_y = (thumb_size - img.height) // 2
                montage.paste(img, (x + offset_x, y + offset_y))

        montage.save(preview_path)
        return str(preview_path.relative_to(preview_dir.parent))
    except Exception as e:
        console.print(f"[yellow]Preview generation failed: {e}[/yellow]")
        return None
```

**Step 2: Add preview generation to index command**

At the end of the `index` function, before the final stats print, add:

```python
    # Generate pack previews
    preview_dir = db.parent / ".assetindex" / "previews"
    console.print("Generating pack previews...")
    for row in conn.execute("SELECT id, name, preview_path FROM packs"):
        if row["preview_path"]:
            continue  # Already has preview
        preview_path = generate_pack_preview(conn, row["id"], asset_root, preview_dir)
        if preview_path:
            conn.execute(
                "UPDATE packs SET preview_path = ?, preview_generated = TRUE WHERE id = ?",
                [preview_path, row["id"]]
            )
    conn.commit()
```

**Step 3: Test preview generation**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db --force
ls -la .assetindex/previews/
```

Expected: Preview images generated for each pack.

**Step 4: Commit**

```bash
git add assetindex.py
git commit -m "feat: add pack preview generation"
```

---

### Task 7: Add metadata file parsing

**Files:**
- Modify: `assetindex.py`

**Step 1: Add animation info parser**

Add function:

```python
def parse_animation_info(path: Path) -> dict:
    """Parse _AnimationInfo.txt file."""
    info = {}
    try:
        text = path.read_text()
        # Parse frame size
        match = re.search(r"(\d+)x(\d+)px", text)
        if match:
            info["frame_size"] = f"{match.group(1)}x{match.group(2)}"

        # Parse frame durations
        durations = re.findall(r"(\d+)ms:\s*([^.]+)", text)
        if durations:
            info["durations"] = {anim.strip().lower(): int(ms) for ms, anim in durations}
    except Exception:
        pass
    return info
```

**Step 2: Apply metadata to nearby assets**

In the index loop, after detecting the pack, add:

```python
            # Check for animation info in same or parent directory
            anim_info = {}
            for info_name in ["_AnimationInfo.txt", "AnimationInfo.txt"]:
                info_path = file_path.parent / info_name
                if info_path.exists():
                    anim_info = parse_animation_info(info_path)
                    break

            # Add frame size as tag if found in metadata
            if anim_info.get("frame_size"):
                add_tags(conn, asset_id, [anim_info["frame_size"]], "metadata")
```

**Step 3: Test metadata parsing**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db --force
uv run assetsearch.py --tag 32x32
```

Expected: Assets tagged with frame sizes from metadata.

**Step 4: Commit**

```bash
git add assetindex.py
git commit -m "feat: add animation metadata parsing"
```

---

### Task 8: Add asset relationship linking

**Files:**
- Modify: `assetindex.py`

**Step 1: Add relationship detection function**

Add function:

```python
def detect_relationships(conn: sqlite3.Connection):
    """Detect relationships between assets (sprite <-> shadow <-> gif)."""
    # Find shadow variants
    conn.execute("""
        INSERT OR IGNORE INTO asset_relations (asset_id, related_id, relation_type)
        SELECT a1.id, a2.id, 'shadow'
        FROM assets a1
        JOIN assets a2 ON a2.path LIKE '%_Shadows/%' || a1.filename
        WHERE a1.path NOT LIKE '%_Shadows/%'
    """)

    # Find GIF previews
    conn.execute("""
        INSERT OR IGNORE INTO asset_relations (asset_id, related_id, relation_type)
        SELECT a1.id, a2.id, 'gif_preview'
        FROM assets a1
        JOIN assets a2 ON a2.path LIKE '%_GIFs/%'
            AND REPLACE(a2.filename, '.gif', '') = REPLACE(a1.filename, '.png', '')
        WHERE a1.filetype = 'png' AND a2.filetype = 'gif'
    """)

    conn.commit()
```

**Step 2: Call relationship detection in index**

At the end of the `index` function, after preview generation:

```python
    # Detect asset relationships
    console.print("Detecting asset relationships...")
    detect_relationships(conn)
```

**Step 3: Test relationships**

Run:
```bash
uv run assetindex.py index assets/minifantasy --db assets.db --force
uv run assetsearch.py info 1
```

Expected: Related assets shown in info output.

**Step 4: Commit**

```bash
git add assetindex.py
git commit -m "feat: add asset relationship detection"
```

---

## Summary

After completing all tasks, you will have:

1. `assetsearch.py` - Lightweight search script with:
   - Filename/path search
   - Tag-based search
   - Color search
   - Similarity search (phash)
   - Pack listing, tag listing, stats, asset info

2. `assetindex.py` - Indexer script with:
   - File scanning with hash-based change detection
   - Image dimension and frame detection
   - Path-based autotagging
   - Metadata file parsing
   - Color extraction
   - Perceptual hash computation
   - Pack preview generation
   - Asset relationship detection

3. `assets.db` - SQLite database (single file, shareable)

4. `.assetindex/previews/` - Generated pack preview images
