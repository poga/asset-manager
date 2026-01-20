#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "uvicorn>=0.27",
# ]
# ///
"""Web API for asset search."""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

app = FastAPI(title="Asset Search API")

# Database path - can be overridden for testing
_db_path: Optional[Path] = None

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


def set_db_path(path: Path):
    """Set database path (for testing)."""
    global _db_path
    _db_path = path


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    path = _db_path or find_db()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def find_db() -> Path:
    """Find assets.db in current directory or parent directories."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        db_path = parent / "assets.db"
        if db_path.exists():
            return db_path
    raise FileNotFoundError("No assets.db found")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/search")
def search(
    q: Optional[str] = None,
    tag: list[str] = Query(default=[]),
    color: Optional[str] = None,
    pack: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100,
):
    """Search assets by name, tags, or filters."""
    conn = get_db()

    conditions = []
    params = []

    if q:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if pack:
        conditions.append("p.name LIKE ?")
        params.append(f"%{pack}%")

    if type:
        conditions.append("a.filetype = ?")
        params.append(type.lower().lstrip("."))

    for t in tag:
        conditions.append("""
            a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
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
               GROUP_CONCAT(DISTINCT tg.name) as tags
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        WHERE {where}
        GROUP BY a.id
        ORDER BY a.filename
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    assets = []
    for row in rows:
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
        })

    return {"assets": assets, "total": len(assets)}


def hamming_distance(h1: bytes, h2: bytes) -> int:
    """Calculate hamming distance between two hashes."""
    return sum(bin(a ^ b).count("1") for a, b in zip(h1, h2))


@app.get("/api/similar/{asset_id}")
def similar(
    asset_id: int,
    limit: int = 20,
    distance: int = 15,
):
    """Find visually similar assets."""
    conn = get_db()

    # Get reference hash
    row = conn.execute(
        "SELECT phash FROM asset_phash WHERE asset_id = ?", [asset_id]
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found or no phash")

    ref_hash = row["phash"]

    # Find similar
    results = []
    for row in conn.execute("""
        SELECT ap.asset_id, ap.phash, a.filename, a.path, p.name as pack_name,
               a.width, a.height
        FROM asset_phash ap
        JOIN assets a ON ap.asset_id = a.id
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE ap.asset_id != ?
    """, [asset_id]):
        dist = hamming_distance(ref_hash, row["phash"])
        if dist <= distance:
            results.append((dist, row))

    conn.close()

    results.sort(key=lambda x: x[0])
    results = results[:limit]

    assets = []
    for dist, row in results:
        assets.append({
            "id": row["asset_id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": [],
            "width": row["width"],
            "height": row["height"],
            "distance": dist,
        })

    return {"assets": assets, "total": len(assets)}


@app.get("/api/asset/{asset_id}")
def asset_detail(asset_id: int):
    """Get detailed info for an asset."""
    conn = get_db()

    row = conn.execute("""
        SELECT a.*, p.name as pack_name
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        WHERE a.id = ?
    """, [asset_id]).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get tags
    tags = conn.execute("""
        SELECT t.name FROM asset_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.asset_id = ?
    """, [asset_id]).fetchall()

    # Get colors
    colors = conn.execute("""
        SELECT color_hex, percentage FROM asset_colors
        WHERE asset_id = ?
        ORDER BY percentage DESC
    """, [asset_id]).fetchall()

    conn.close()

    return {
        "id": row["id"],
        "path": row["path"],
        "filename": row["filename"],
        "filetype": row["filetype"],
        "pack": row["pack_name"],
        "width": row["width"],
        "height": row["height"],
        "frame_count": row["frame_count"],
        "frame_width": row["frame_width"],
        "frame_height": row["frame_height"],
        "tags": [t["name"] for t in tags],
        "colors": [{"hex": c["color_hex"], "percentage": c["percentage"]} for c in colors],
    }


@app.get("/api/filters")
def filters():
    """Get available filter options."""
    conn = get_db()

    packs = conn.execute("SELECT name FROM packs ORDER BY name").fetchall()
    tags = conn.execute("""
        SELECT t.name, COUNT(at.asset_id) as count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY count DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return {
        "packs": [p["name"] for p in packs],
        "tags": [t["name"] for t in tags],
        "colors": list(COLOR_NAMES.keys()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
