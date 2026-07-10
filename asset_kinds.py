"""Asset kind handlers: match files to kinds, extract per-kind metadata."""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

import aseprite_parser
import frame_detect
import model_indexer

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
ASEPRITE_EXTENSIONS = {".aseprite", ".ase"}
MODEL_EXTENSIONS = {".glb", ".gltf"}


@dataclass
class IndexContext:
    asset_root: Path
    pack_root: Path  # pack dir, or asset_root for packless files
    db_root: Path  # thumbnail_path is stored relative to this
    rel_path: str  # asset path relative to asset_root


@dataclass
class AssetMeta:
    asset_kind: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None
    preview_bounds: Optional[tuple] = None
    rig: Optional[str] = None
    thumbnail_path: Optional[str] = None
    extra_tags: list[str] = field(default_factory=list)
    clip_names: list[str] = field(default_factory=list)
    wants_colors: bool = False  # image-only post steps: colors + phash


def _thumb_key(rel_path: str) -> str:
    return hashlib.sha256(rel_path.encode()).hexdigest()[:16]


def _rel_to_db_root(thumb: Path, db_root: Path) -> str:
    try:
        return str(thumb.relative_to(db_root))
    except ValueError:
        return str(thumb)


class ExtensionHandler:
    extensions: set[str] = set()

    def match(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions


class ImageHandler(ExtensionHandler):
    extensions = IMAGE_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        meta = AssetMeta(wants_colors=True)
        try:
            with Image.open(path) as img:
                meta.width, meta.height = img.size
        except Exception:
            pass
        meta.preview_bounds = frame_detect.detect_preview_bounds(path, ctx.pack_root)
        return meta


class AsepriteHandler(ExtensionHandler):
    extensions = ASEPRITE_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        info = aseprite_parser.parse_aseprite(path)
        return AssetMeta(width=info["width"], height=info["height"])


class ModelHandler(ExtensionHandler):
    extensions = MODEL_EXTENSIONS

    def index_file(self, path: Path, ctx: IndexContext) -> AssetMeta:
        info = model_indexer.extract_model_info(path)
        # KayKit animation bundles ship mannequin meshes, so has_mesh
        # is unreliable. Use filename prefix + animations instead.
        is_bundle = path.stem.startswith("Rig_") and bool(info.animations)
        meta = AssetMeta(
            asset_kind="animation_bundle" if is_bundle else "model",
            rig=info.rig,
            clip_names=info.animations,
            extra_tags=["3d"],
        )
        cache_dir = ctx.db_root / ".index" / "thumbs"
        thumb = model_indexer.resolve_thumbnail(
            path, ctx.pack_root, cache_dir, _thumb_key(ctx.rel_path)
        )
        if thumb:
            meta.thumbnail_path = _rel_to_db_root(thumb, ctx.db_root)
        return meta


HANDLERS = [AsepriteHandler(), ImageHandler(), ModelHandler()]


def find_handler(path: Path):
    """First handler claiming the file, or None (file is not indexed)."""
    for handler in HANDLERS:
        if handler.match(path):
            return handler
    return None
