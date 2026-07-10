#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "uvicorn>=0.27",
#     "pillow>=10.0",
#     "python-multipart>=0.0.9",
# ]
# ///
"""Web API for asset search."""

import io
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

# Add parent directory to path for local module imports
sys.path.insert(0, str(Path(__file__).parent.parent))
# make web/ importable so `import boards` works under uvicorn web.api:app
sys.path.insert(0, str(Path(__file__).parent))
import aseprite_parser
import model_indexer
import boards as boards_mod

app = FastAPI(title="Asset Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Frontend is served at base /assets/ so API calls go to /assets/api/...
# Strip the prefix so the same handlers respond at /api/... and /assets/api/...
@app.middleware("http")
async def strip_vite_base_for_api(request, call_next):
    p = request.scope.get("path", "")
    if p.startswith("/assets/api/") or p == "/assets/api":
        request.scope["path"] = p[len("/assets"):]
    return await call_next(request)

# Database path - can be overridden for testing
_db_path: Optional[Path] = None
# Assets path - can be overridden for testing
_assets_path: Optional[Path] = None
# Static files path (frontend dist) - can be overridden for testing
_static_path: Optional[Path] = None


class PreviewOverrideRequest(BaseModel):
    use_full_image: bool


class PackTagRequest(BaseModel):
    tag: str


class BoardCreateRequest(BaseModel):
    name: str
    tags: list[str] = []


class BoardPatchRequest(BaseModel):
    name: Optional[str] = None
    cover_asset_id: Optional[int] = None


class AssetTagRequest(BaseModel):
    tag: str


def set_db_path(path: Path):
    """Set database path (for testing)."""
    global _db_path
    _db_path = path


def set_assets_path(path: Path):
    """Set assets path (for testing)."""
    global _assets_path
    _assets_path = path


def set_static_path(path: Path):
    """Set static files path (for testing)."""
    global _static_path
    _static_path = path


def get_static_path() -> Optional[Path]:
    """Get static files directory path."""
    if _static_path:
        return _static_path
    # Look for frontend dist folder
    current = Path(__file__).parent
    dist_path = current / "frontend" / "dist"
    if dist_path.exists():
        return dist_path
    return None


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


def get_assets_path() -> Path:
    """Get assets directory path."""
    return _assets_path or find_assets()


def find_assets() -> Path:
    """Find assets folder in current directory or parent directories."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        assets_path = parent / "assets"
        if assets_path.exists() and assets_path.is_dir():
            return assets_path
    raise FileNotFoundError("No assets folder found")


def _ensure_pack_tags(conn: sqlite3.Connection) -> None:
    """Lazily create pack_tags so pre-existing DBs work without a reindex."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pack_tags (
            pack_id INTEGER REFERENCES packs(id),
            tag TEXT NOT NULL,
            PRIMARY KEY (pack_id, tag)
        )"""
    )


def _ensure_board_columns(conn: sqlite3.Connection) -> None:
    """Lazily add the board flag so pre-existing DBs work without a reindex."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(packs)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE packs ADD COLUMN source TEXT DEFAULT 'indexed'")


def _pack_tag_list(conn: sqlite3.Connection, pack_id: int) -> list[str]:
    return [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM pack_tags WHERE pack_id = ? ORDER BY tag", [pack_id]
        )
    ]


def _pack_id_or_404(conn: sqlite3.Connection, pack_name: str) -> int:
    from urllib.parse import unquote
    row = conn.execute(
        "SELECT id FROM packs WHERE name = ?", [unquote(pack_name)]
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pack not found")
    return row["id"]


def _board_or_404(conn: sqlite3.Connection, board_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM packs WHERE id = ? AND source = 'user'", [board_id]
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Board not found")
    return row


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/search")
def search(
    q: Optional[str] = None,
    tag: list[str] = Query(default=[]),
    pack: list[str] = Query(default=[]),
    type: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Search assets by name, tags, or filters."""
    conn = get_db()
    _ensure_pack_tags(conn)
    conn.commit()

    conditions = []
    params = []

    if q:
        conditions.append("(a.filename LIKE ? OR a.path LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    if pack:
        # Support multiple packs with OR
        pack_conditions = []
        for p in pack:
            pack_conditions.append("p.name LIKE ?")
            params.append(f"%{p}%")
        conditions.append(f"({' OR '.join(pack_conditions)})")

    if type:
        conditions.append("a.filetype = ?")
        params.append(type.lower().lstrip("."))

    if kind:
        conditions.append("a.asset_kind = ?")
        params.append(kind)

    for t in tag:
        conditions.append("""
            (a.id IN (
                SELECT at.asset_id FROM asset_tags at
                JOIN tags tg ON at.tag_id = tg.id
                WHERE tg.name = ?
            ) OR a.pack_id IN (
                SELECT pack_id FROM pack_tags WHERE tag = ?
            ))
        """)
        params.extend([t.lower(), t.lower()])

    where = " AND ".join(conditions) if conditions else "1=1"

    # Random order for empty search (discoverability), deterministic for filtered
    is_empty_search = not q and not tag and not pack and not type
    order_by = "RANDOM()" if is_empty_search else "a.path"

    sql = f"""
        SELECT a.id, a.path, a.filename, a.filetype, a.width, a.height,
               a.preview_x, a.preview_y, a.preview_width, a.preview_height,
               a.asset_kind, a.rig, a.thumbnail_path,
               p.name as pack_name,
               GROUP_CONCAT(DISTINCT tg.name) as tags,
               po.use_full_image
        FROM assets a
        LEFT JOIN packs p ON a.pack_id = p.id
        LEFT JOIN asset_tags at ON a.id = at.asset_id
        LEFT JOIN tags tg ON at.tag_id = tg.id
        LEFT JOIN asset_preview_overrides po ON a.path = po.path
        WHERE {where}
        GROUP BY a.id
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    params.append(limit)
    params.append(offset)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    assets = []
    for row in rows:
        use_full_image = None
        if row["use_full_image"] is not None:
            use_full_image = bool(row["use_full_image"])
        assets.append({
            "id": row["id"],
            "path": row["path"],
            "filename": row["filename"],
            "pack": row["pack_name"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "width": row["width"],
            "height": row["height"],
            "preview_x": row["preview_x"],
            "preview_y": row["preview_y"],
            "preview_width": row["preview_width"],
            "preview_height": row["preview_height"],
            "use_full_image": use_full_image,
            "kind": row["asset_kind"],
            "rig": row["rig"],
            "thumbnail_path": row["thumbnail_path"],
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

    # Get preview override
    override = conn.execute(
        "SELECT use_full_image FROM asset_preview_overrides WHERE path = ?",
        [row["path"]]
    ).fetchone()

    conn.close()

    return {
        "id": row["id"],
        "path": row["path"],
        "filename": row["filename"],
        "filetype": row["filetype"],
        "pack": row["pack_name"],
        "width": row["width"],
        "height": row["height"],
        "preview_x": row["preview_x"],
        "preview_y": row["preview_y"],
        "preview_width": row["preview_width"],
        "preview_height": row["preview_height"],
        "tags": [t["name"] for t in tags],
        "colors": [{"hex": c["color_hex"], "percentage": c["percentage"]} for c in colors],
        "use_full_image": bool(override["use_full_image"]) if override else None,
        "kind": row["asset_kind"],
        "rig": row["rig"],
        "thumbnail_path": row["thumbnail_path"],
    }


@app.post("/api/asset/{asset_id}/preview-override")
def set_preview_override(asset_id: int, request: PreviewOverrideRequest):
    """Set preview override for an asset."""
    conn = get_db()

    # Get asset path
    row = conn.execute("SELECT path FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_path = row["path"]

    # Insert or replace override
    conn.execute(
        """INSERT OR REPLACE INTO asset_preview_overrides (path, use_full_image, created_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)""",
        [asset_path, request.use_full_image]
    )
    conn.commit()
    conn.close()

    return {"success": True}


@app.delete("/api/asset/{asset_id}/preview-override")
def delete_preview_override(asset_id: int):
    """Remove preview override for an asset."""
    conn = get_db()

    # Get asset path
    row = conn.execute("SELECT path FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_path = row["path"]

    # Delete override
    conn.execute("DELETE FROM asset_preview_overrides WHERE path = ?", [asset_path])
    conn.commit()
    conn.close()

    return {"success": True}


@app.get("/api/filters")
def filters():
    """Get available filter options."""
    conn = get_db()

    _ensure_board_columns(conn)
    packs = conn.execute("""
        SELECT p.id, p.name, p.source, p.asset_count AS count,
               EXISTS (SELECT 1 FROM assets a
                       WHERE a.pack_id = p.id
                         AND a.asset_kind IN ('model', 'animation_bundle')) AS is_3d
        FROM packs p
        ORDER BY p.name
    """).fetchall()
    _ensure_pack_tags(conn)
    pack_tag_map: dict[int, list[str]] = {}
    for r in conn.execute("SELECT pack_id, tag FROM pack_tags ORDER BY tag"):
        pack_tag_map.setdefault(r["pack_id"], []).append(r["tag"])

    # one vocabulary: asset tags plus pack tags (pack tags reach all assets)
    tag_counts: dict[str, int] = {}
    for r in conn.execute("""
        SELECT t.name AS name, COUNT(at.asset_id) AS count
        FROM tags t
        JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
    """):
        tag_counts[r["name"]] = r["count"]
    for r in conn.execute("""
        SELECT pt.tag AS name, SUM(p.asset_count) AS count
        FROM pack_tags pt
        JOIN packs p ON pt.pack_id = p.id
        GROUP BY pt.tag
    """):
        tag_counts[r["name"]] = max(tag_counts.get(r["name"], 0), r["count"] or 0)
    vocabulary = [
        {"name": name, "count": count}
        for name, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    conn.commit()
    conn.close()

    return {
        "packs": [
            {
                "id": p["id"],
                "name": p["name"],
                "count": p["count"],
                "is_3d": bool(p["is_3d"]),
                "is_board": p["source"] == "user",
                "tags": pack_tag_map.get(p["id"], []),
            }
            for p in packs
        ],
        "tags": vocabulary,
    }


ASEPRITE_EXTENSIONS = {".aseprite", ".ase"}


_3D_KINDS = {"model", "animation_bundle"}


@app.get("/api/image/{asset_id}")
def image(asset_id: int):
    """Serve asset image file. Renders Aseprite files as PNG."""
    conn = get_db()
    row = conn.execute(
        "SELECT path, asset_kind, thumbnail_path FROM assets WHERE id = ?",
        [asset_id],
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Serve thumbnail PNG for 3D assets; raw file has no visual representation
    if row["asset_kind"] in _3D_KINDS:
        if not row["thumbnail_path"]:
            raise HTTPException(status_code=404, detail="No thumbnail")
        thumb = Path(row["thumbnail_path"])
        serve_path = thumb if thumb.is_absolute() else get_assets_path().parent / thumb
        if not serve_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        return FileResponse(serve_path, media_type="image/png")

    # Paths in DB are relative to assets folder
    assets_dir = get_assets_path()
    image_path = assets_dir / row["path"]
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    # Render Aseprite files as PNG
    if image_path.suffix.lower() in ASEPRITE_EXTENSIONS:
        img = aseprite_parser.render_first_frame(image_path)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return Response(content=buffer.getvalue(), media_type="image/png")

    return FileResponse(image_path)


MODEL_CONTENT_TYPES = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
}


@app.get("/api/asset/{asset_id}/animations")
def asset_animations(asset_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM assets WHERE id = ?", [asset_id]).fetchone()
    if not row:
        conn.close(); raise HTTPException(404)

    # Bundles: asset itself (if it has embedded clips) plus linked animation bundles
    bundle_ids: list[int] = []
    self_clips = conn.execute(
        "SELECT clip_index, name FROM asset_animations WHERE asset_id = ? ORDER BY clip_index",
        [asset_id]
    ).fetchall()
    if self_clips:
        bundle_ids.append(asset_id)
    linked = conn.execute(
        "SELECT related_id FROM asset_relations WHERE asset_id = ? AND relation_type='animation_for_rig'",
        [asset_id]
    ).fetchall()
    bundle_ids.extend(r["related_id"] for r in linked)

    out = []
    for bid in bundle_ids:
        b = conn.execute("SELECT filename FROM assets WHERE id = ?", [bid]).fetchone()
        clips = conn.execute(
            "SELECT clip_index, name FROM asset_animations WHERE asset_id = ? ORDER BY clip_index",
            [bid]
        ).fetchall()
        out.append({
            "bundle_id": bid,
            "bundle_name": b["filename"],
            "clips": [{"name": c["name"], "gltf_name": c["name"]} for c in clips],
        })
    conn.close()
    return out


@app.get("/api/asset/{asset_id}/model")
def asset_model(asset_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT path, asset_kind FROM assets WHERE id = ?", [asset_id]
    ).fetchone()
    conn.close()
    if not row or row["asset_kind"] not in ("model", "animation_bundle"):
        raise HTTPException(404, "Model not found")
    p = (get_assets_path() / row["path"]).resolve()
    if not p.exists():
        raise HTTPException(404, "Model file missing")
    ct = MODEL_CONTENT_TYPES.get(p.suffix.lower(), "application/octet-stream")
    return FileResponse(p, media_type=ct)


@app.get("/api/asset/{asset_id}/model/{filename}")
def asset_model_sibling(asset_id: int, filename: str):
    if "/" in filename or filename.startswith(".."):
        raise HTTPException(400, "Invalid filename")
    conn = get_db()
    row = conn.execute(
        "SELECT path, asset_kind FROM assets WHERE id = ?", [asset_id]
    ).fetchone()
    conn.close()
    if not row or row["asset_kind"] not in ("model", "animation_bundle"):
        raise HTTPException(404)
    assets_dir = get_assets_path().resolve()
    asset_dir = (assets_dir / row["path"]).parent.resolve()
    target = (asset_dir / filename).resolve()
    # Reject resolved paths that escape the asset's directory
    if asset_dir not in target.parents and target.parent != asset_dir:
        raise HTTPException(400, "Path traversal")
    if not target.exists():
        raise HTTPException(404)
    ct = MODEL_CONTENT_TYPES.get(target.suffix.lower())
    return FileResponse(target, media_type=ct) if ct else FileResponse(target)


@app.get("/api/pack-preview/{pack_name:path}")
def pack_preview(pack_name: str):
    """Serve pack preview image."""
    db_path = find_db()
    previews_dir = db_path.parent / ".index" / "previews"

    # URL decode the pack name
    from urllib.parse import unquote
    pack_name = unquote(pack_name)

    conn = get_db()
    _ensure_board_columns(conn)
    row = conn.execute(
        "SELECT preview_path FROM packs WHERE name = ? AND source = 'user'", [pack_name]
    ).fetchone()
    conn.close()
    if row and row["preview_path"]:
        cover = get_assets_path() / row["preview_path"]
        if cover.exists():
            media = "image/gif" if cover.suffix.lower() == ".gif" else "image/png"
            if cover.suffix.lower() in (".jpg", ".jpeg"):
                media = "image/jpeg"
            elif cover.suffix.lower() == ".webp":
                media = "image/webp"
            return FileResponse(cover, media_type=media)

    # Check for both .gif and .png
    gif_path = previews_dir / f"{pack_name}.gif"
    png_path = previews_dir / f"{pack_name}.png"

    if gif_path.exists():
        return FileResponse(gif_path, media_type="image/gif")
    elif png_path.exists():
        return FileResponse(png_path, media_type="image/png")
    else:
        raise HTTPException(status_code=404, detail="Pack preview not found")


@app.post("/api/pack/{pack_name}/tags")
def add_pack_tag(pack_name: str, request: PackTagRequest):
    """Attach a user tag to a pack (idempotent)."""
    tag = request.tag.strip().lower()
    if not tag:
        raise HTTPException(status_code=400, detail="Empty tag")
    conn = get_db()
    _ensure_pack_tags(conn)
    pack_id = _pack_id_or_404(conn, pack_name)
    conn.execute(
        "INSERT OR IGNORE INTO pack_tags (pack_id, tag) VALUES (?, ?)",
        [pack_id, tag],
    )
    conn.commit()
    tags = _pack_tag_list(conn, pack_id)
    conn.close()
    return {"tags": tags}


@app.delete("/api/pack/{pack_name}/tags/{tag}")
def remove_pack_tag(pack_name: str, tag: str):
    """Detach a user tag from a pack (absent tag is a no-op)."""
    conn = get_db()
    _ensure_pack_tags(conn)
    pack_id = _pack_id_or_404(conn, pack_name)
    conn.execute(
        "DELETE FROM pack_tags WHERE pack_id = ? AND tag = ?",
        [pack_id, tag.strip().lower()],
    )
    conn.commit()
    tags = _pack_tag_list(conn, pack_id)
    conn.close()
    return {"tags": tags}


@app.post("/api/boards", status_code=201)
def create_board(request: BoardCreateRequest):
    """Create a user board pack, optionally with pack-level tags."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty name")
    conn = get_db()
    _ensure_board_columns(conn)
    _ensure_pack_tags(conn)
    if conn.execute("SELECT 1 FROM packs WHERE name = ?", [name]).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Name already exists")
    slug = boards_mod.unique_slug(conn, name)
    path = f"{boards_mod.BOARD_ROOT}/{slug}"
    cur = conn.execute(
        "INSERT INTO packs (name, path, source, asset_count) VALUES (?, ?, 'user', 0)",
        [name, path],
    )
    board_id = cur.lastrowid
    for tag in request.tags:
        t = tag.strip().lower()
        if t:
            conn.execute(
                "INSERT OR IGNORE INTO pack_tags (pack_id, tag) VALUES (?, ?)",
                [board_id, t],
            )
    conn.commit()
    conn.close()
    return {"id": board_id, "name": name, "path": path}


@app.post("/api/boards/{board_id}/images", status_code=201)
def upload_board_images(board_id: int, files: list[UploadFile] = File(...)):
    """Upload images to a board; first upload sets the cover."""
    conn = get_db()
    _ensure_board_columns(conn)
    board = _board_or_404(conn, board_id)
    slug = board["path"].split("/", 1)[1]
    assets_root = get_assets_path()

    # validate all before writing so a bad file writes nothing
    payloads = []
    for f in files:
        data = f.file.read()
        try:
            ext = boards_mod.validate_upload(f.filename, data)
        except ValueError as e:
            conn.close()
            raise HTTPException(status_code=400, detail=str(e))
        payloads.append((f.filename, data, ext))

    created = []
    for filename, data, ext in payloads:
        rel, w, h = boards_mod.save_image(assets_root, slug, data, ext)
        asset_id = boards_mod.insert_board_asset(
            conn, board_id, rel, filename, ext, len(data), w, h
        )
        created.append({"id": asset_id, "path": rel, "filename": filename,
                        "width": w, "height": h})

    conn.execute(
        "UPDATE packs SET asset_count = (SELECT COUNT(*) FROM assets WHERE pack_id = ?) WHERE id = ?",
        [board_id, board_id],
    )
    cover_id, cover_path = None, None
    if not board["preview_path"] and created:
        cover_path = created[0]["path"]
        cover_id = created[0]["id"]
        conn.execute("UPDATE packs SET preview_path = ? WHERE id = ?", [cover_path, board_id])
    conn.commit()
    conn.close()
    return {"assets": created, "cover_asset_id": cover_id, "cover_asset_path": cover_path}


@app.patch("/api/boards/{board_id}")
def patch_board(board_id: int, request: BoardPatchRequest):
    """Rename a board and/or set its cover asset."""
    conn = get_db()
    _ensure_board_columns(conn)
    board = _board_or_404(conn, board_id)
    name = board["name"]
    if request.name is not None:
        name = request.name.strip()
        if not name:
            conn.close()
            raise HTTPException(status_code=400, detail="Empty name")
        clash = conn.execute(
            "SELECT 1 FROM packs WHERE name = ? AND id != ?", [name, board_id]
        ).fetchone()
        if clash:
            conn.close()
            raise HTTPException(status_code=409, detail="Name already exists")
        conn.execute("UPDATE packs SET name = ? WHERE id = ?", [name, board_id])
    preview_path = board["preview_path"]
    if request.cover_asset_id is not None:
        row = conn.execute(
            "SELECT path FROM assets WHERE id = ? AND pack_id = ?",
            [request.cover_asset_id, board_id],
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=400, detail="Asset not in board")
        preview_path = row["path"]
        conn.execute("UPDATE packs SET preview_path = ? WHERE id = ?", [preview_path, board_id])
    conn.commit()
    conn.close()
    return {"id": board_id, "name": name, "path": board["path"], "preview_path": preview_path}


class DownloadCartRequest(BaseModel):
    asset_ids: list[int]


@app.post("/api/download-cart")
def download_cart(request: DownloadCartRequest):
    """Download selected assets as a ZIP file."""
    if not request.asset_ids:
        raise HTTPException(status_code=400, detail="No assets selected")

    conn = get_db()

    # Get asset info with pack name
    placeholders = ",".join("?" * len(request.asset_ids))
    rows = conn.execute(
        f"""SELECT a.id, a.path, a.filename, a.width, a.height, a.asset_kind, p.name as pack_name
            FROM assets a
            LEFT JOIN packs p ON a.pack_id = p.id
            WHERE a.id IN ({placeholders})""",
        request.asset_ids
    ).fetchall()

    if not rows:
        conn.close()
        raise HTTPException(status_code=404, detail="No valid assets found")

    # Get tags for all assets
    asset_tags = {}
    tag_rows = conn.execute(
        f"""SELECT at.asset_id, t.name FROM asset_tags at
            JOIN tags t ON at.tag_id = t.id
            WHERE at.asset_id IN ({placeholders})""",
        request.asset_ids
    ).fetchall()
    for tag_row in tag_rows:
        asset_id = tag_row["asset_id"]
        if asset_id not in asset_tags:
            asset_tags[asset_id] = []
        asset_tags[asset_id].append(tag_row["name"])

    # Get colors for all assets
    asset_colors = {}
    color_rows = conn.execute(
        f"""SELECT asset_id, color_hex, percentage FROM asset_colors
            WHERE asset_id IN ({placeholders})
            ORDER BY asset_id, percentage DESC""",
        request.asset_ids
    ).fetchall()
    for color_row in color_rows:
        asset_id = color_row["asset_id"]
        if asset_id not in asset_colors:
            asset_colors[asset_id] = []
        asset_colors[asset_id].append(f"{color_row['color_hex']} ({color_row['percentage']:.0%})")

    conn.close()

    assets_dir = get_assets_path()

    # Build metadata.txt content
    metadata_lines = ["Asset Metadata", "=" * 50, ""]
    for row in rows:
        metadata_lines.append(f"File: {row['filename']}")
        if row["pack_name"]:
            metadata_lines.append(f"Pack: {row['pack_name']}")
        if row["width"] and row["height"]:
            metadata_lines.append(f"Size: {row['width']}x{row['height']}")
        tags = asset_tags.get(row["id"], [])
        if tags:
            metadata_lines.append(f"Tags: {', '.join(tags)}")
        colors = asset_colors.get(row["id"], [])
        if colors:
            metadata_lines.append(f"Colors: {', '.join(colors)}")
        metadata_lines.append("")

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            file_path = assets_dir / row["path"]
            if file_path.exists():
                # Use filename to avoid path issues
                zf.write(file_path, row["filename"])
            if row["asset_kind"] in ("model", "animation_bundle") and file_path.suffix.lower() == ".gltf":
                try:
                    info = model_indexer.extract_model_info(file_path)
                    for ref in info.referenced_files:
                        ref_path = (file_path.parent / ref).resolve()
                        if ref_path.exists() and ref_path.is_relative_to(assets_dir.resolve()):
                            zf.write(ref_path, ref_path.name)
                except Exception:
                    pass
        # Add metadata file
        zf.writestr("metadata.txt", "\n".join(metadata_lines))

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="assets-{timestamp}.zip"'
        }
    )


VITE_BASE_PREFIX = "assets/"  # mirrors web/frontend/vite.config.js `base: '/assets/'`


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """Serve static files or fallback to index.html for SPA routing."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    static_path = get_static_path()
    if not static_path:
        raise HTTPException(status_code=404, detail="Frontend not built")

    # URL may carry the Vite base prefix (built bundle paths look like
    # /assets/foo.js but the file on disk is dist/foo.js — base maps the
    # URL prefix onto dist/). Probe both forms.
    candidates = [static_path / full_path]
    if full_path.startswith(VITE_BASE_PREFIX):
        candidates.append(static_path / full_path[len(VITE_BASE_PREFIX):])
    for p in candidates:
        if p.is_file():
            return FileResponse(p)

    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
