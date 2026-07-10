"""Domain helpers for UI-created boards."""

import io
import re
import sqlite3
import uuid
from pathlib import Path

from PIL import Image

BOARD_ROOT = ".boards"
ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def slugify(name: str) -> str:
    """Lowercase, non-alphanumerics to single dashes, trimmed."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return s.strip("-") or "board"


def unique_slug(conn: sqlite3.Connection, name: str) -> str:
    """Slug whose .boards/<slug> path is not already used by a pack."""
    base = slugify(name)
    slug, n = base, 1
    while conn.execute(
        "SELECT 1 FROM packs WHERE path = ?", [f"{BOARD_ROOT}/{slug}"]
    ).fetchone():
        n += 1
        slug = f"{base}-{n}"
    return slug


def board_dir(assets_root: Path, slug: str) -> Path:
    return assets_root / BOARD_ROOT / slug


def validate_upload(filename: str, data: bytes) -> str:
    """Return the lowercased extension or raise ValueError."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported type: {ext}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large")
    return ext


def save_image(assets_root: Path, slug: str, data: bytes, ext: str) -> tuple[str, int, int]:
    """Write bytes under the board dir; return (rel_path, width, height)."""
    d = board_dir(assets_root, slug)
    d.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (d / name).write_bytes(data)
    with Image.open(io.BytesIO(data)) as img:
        w, h = img.size
    return f"{BOARD_ROOT}/{slug}/{name}", w, h


def insert_board_asset(
    conn: sqlite3.Connection, pack_id: int, rel_path: str,
    filename: str, ext: str, size: int, width: int, height: int,
) -> int:
    """Insert an asset row for a board image (full-image preview bounds)."""
    cur = conn.execute(
        """INSERT INTO assets
           (pack_id, path, filename, filetype, file_hash, file_size,
            width, height, preview_x, preview_y, preview_width, preview_height,
            category, asset_kind)
           VALUES (?, ?, ?, ?, '', ?, ?, ?, 0, 0, ?, ?, '', 'image')""",
        [pack_id, rel_path, filename, ext, size, width, height, width, height],
    )
    return cur.lastrowid
