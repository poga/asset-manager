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

import imagehash
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


def compute_phash(path: Path) -> Optional[bytes]:
    """Compute perceptual hash of image."""
    try:
        with Image.open(path) as img:
            h = imagehash.phash(img)
            return h.hash.tobytes()
    except Exception:
        return None


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

            # Extract colors for images
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                colors = extract_colors(file_path)
                for hex_color, percentage in colors:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_colors (asset_id, color_hex, percentage)
                           VALUES (?, ?, ?)""",
                        [asset_id, hex_color, percentage]
                    )

                # Compute perceptual hash
                phash = compute_phash(file_path)
                if phash:
                    conn.execute(
                        """INSERT OR REPLACE INTO asset_phash (asset_id, phash)
                           VALUES (?, ?)""",
                        [asset_id, phash]
                    )

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
