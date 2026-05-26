"""3D asset indexing helpers: glTF/GLB parsing, sample matching, thumbnail rendering."""

import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


GLB_MAGIC = 0x46546C67  # 'glTF'
CHUNK_JSON = 0x4E4F534A  # 'JSON'


def load_gltf_json(path: Path) -> dict:
    """Read a .gltf or .glb file and return its JSON dictionary."""
    suffix = path.suffix.lower()
    if suffix == ".gltf":
        with open(path) as f:
            return json.load(f)
    if suffix == ".glb":
        with open(path, "rb") as f:
            magic, _version, _length = struct.unpack("<III", f.read(12))
            if magic != GLB_MAGIC:
                raise ValueError(f"not a glTF binary: {path}")
            chunk_len, chunk_type = struct.unpack("<II", f.read(8))
            if chunk_type != CHUNK_JSON:
                raise ValueError(f"first chunk is not JSON: {path}")
            return json.loads(f.read(chunk_len).decode("utf-8"))
    raise ValueError(f"unsupported extension: {path}")


RIG_PATTERN = re.compile(r"Rig_(Large|Medium|Small)", re.IGNORECASE)


@dataclass
class ModelInfo:
    rig: Optional[str]
    animations: list[str]
    has_mesh: bool
    referenced_files: list[str]


def _infer_rig(path: Path, gltf: dict) -> Optional[str]:
    m = RIG_PATTERN.search(path.stem)
    if m:
        return f"Rig_{m.group(1).capitalize()}"
    for node in gltf.get("nodes") or []:
        name = node.get("name", "")
        m = RIG_PATTERN.search(name)
        if m:
            return f"Rig_{m.group(1).capitalize()}"
    return None


def _collect_referenced_files(gltf: dict) -> list[str]:
    out: list[str] = []
    for buf in gltf.get("buffers") or []:
        uri = buf.get("uri")
        if uri and not uri.startswith("data:"):
            out.append(uri)
    for img in gltf.get("images") or []:
        uri = img.get("uri")
        if uri and not uri.startswith("data:"):
            out.append(uri)
    return out


def filter_canonical_models(paths: list[Path]) -> list[Path]:
    """Drop .gltf entries that have a sibling .glb with the same stem."""
    by_key: dict[tuple[Path, str], list[Path]] = {}
    for p in paths:
        by_key.setdefault((p.parent, p.stem), []).append(p)

    keep: list[Path] = []
    for group in by_key.values():
        if len(group) == 1:
            keep.append(group[0])
            continue
        glb = next((p for p in group if p.suffix.lower() == ".glb"), None)
        keep.append(glb if glb else group[0])
    return [p for p in paths if p in set(keep)]


def extract_model_info(path: Path) -> ModelInfo:
    gltf = load_gltf_json(path)
    animations = [
        a.get("name", f"clip_{i}")
        for i, a in enumerate(gltf.get("animations") or [])
    ]
    has_mesh = bool(gltf.get("meshes"))
    return ModelInfo(
        rig=_infer_rig(path, gltf),
        animations=animations,
        has_mesh=has_mesh,
        referenced_files=_collect_referenced_files(gltf),
    )


def find_sample_thumbnail(model_path: Path, pack_root: Path) -> Optional[Path]:
    """Walk up from model_path toward pack_root, looking for Samples/<stem>.png (case-insensitive)."""
    target = model_path.stem.lower() + ".png"
    cur = model_path.parent
    while True:
        samples = cur / "Samples"
        if samples.is_dir():
            for f in samples.iterdir():
                if f.is_file() and f.name.lower() == target:
                    return f
        if cur == pack_root or cur.parent == cur:
            return None
        cur = cur.parent


def render_model_thumbnail(model_path: Path, out_path: Path, size: int = 256) -> bool:
    """Render an offscreen thumbnail. Returns True on success, False otherwise."""
    try:
        import trimesh  # heavy import; keep local
        scene = trimesh.load(str(model_path), force="scene")
        png = scene.save_image(resolution=(size, size), visible=False)
        if not png:
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png)
        return True
    except Exception:
        return False


PACK_PREVIEW_NAMES = ("contents.png", "contents.jpg", "preview.png", "preview.gif")


def find_pack_preview(pack_root: Path) -> Optional[Path]:
    """Find a pack-level conventional preview image at pack_root.

    Tier 1: exact match for contents.{png,jpg} / preview.{png,gif}.
    Tier 2: <prefix>_Contents.{png,jpg} (KayKit naming for packs without a
    bare contents.* file), excluding *AlternateTexture* variants.
    """
    for name in PACK_PREVIEW_NAMES:
        candidate = pack_root / name
        if candidate.is_file():
            return candidate
    matches = []
    for p in pack_root.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".png", ".jpg"):
            continue
        stem_lower = p.stem.lower()
        if "contents" not in stem_lower:
            continue
        if "alternate" in stem_lower:
            continue
        matches.append(p)
    if matches:
        return sorted(matches)[0]
    return None


def _walk_up_for_pack_preview(start: Path, pack_root: Path) -> Optional[Path]:
    """Search for a pack-convention preview at each directory from start up to pack_root."""
    cur = start
    while True:
        found = find_pack_preview(cur)
        if found:
            return found
        if cur == pack_root or cur.parent == cur:
            return None
        cur = cur.parent


def resolve_thumbnail(
    model_path: Path,
    pack_root: Path,
    cache_dir: Path,
    cache_key: str,
) -> Optional[Path]:
    """Resolve a thumbnail for a 3D asset.

    1. Sample match in pack/Samples (returns its absolute path).
    2. Rendered fallback into cache_dir/<cache_key>.png.
    3. Nearest pack-convention image walking up from model_path to pack_root.
    4. None.
    """
    sample = find_sample_thumbnail(model_path, pack_root)
    if sample:
        return sample
    rendered = cache_dir / f"{cache_key}.png"
    if rendered.exists():
        return rendered
    if render_model_thumbnail(model_path, rendered):
        return rendered
    return _walk_up_for_pack_preview(model_path.parent, pack_root)
