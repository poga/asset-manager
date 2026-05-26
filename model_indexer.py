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


BLENDER_CANDIDATES = (
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/usr/local/bin/blender",
    "/opt/homebrew/bin/blender",
    "blender",
)


def find_blender() -> Optional[str]:
    """Locate a Blender executable, honoring BLENDER_PATH env var first."""
    import os
    import shutil as _sh
    env = os.environ.get("BLENDER_PATH")
    if env and (Path(env).is_file() or _sh.which(env)):
        return env
    for c in BLENDER_CANDIDATES:
        if Path(c).is_file() or _sh.which(c):
            return c
    return None


RENDER_SCRIPT = Path(__file__).parent / "scripts" / "render_gltf_thumbnail.py"


def render_model_thumbnail(model_path: Path, out_path: Path, size: int = 256) -> bool:
    """Render a thumbnail via headless Blender. Returns True on success."""
    import subprocess
    blender = find_blender()
    if not blender:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [blender, "-b", "-P", str(RENDER_SCRIPT), "--",
             str(model_path), str(out_path), str(size)],
            capture_output=True, timeout=120, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0


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


def resolve_thumbnail(
    model_path: Path,
    pack_root: Path,
    cache_dir: Path,
    cache_key: str,
) -> Optional[Path]:
    """Resolve a thumbnail for a 3D asset.

    1. Sample match in pack/Samples.
    2. Cached render at cache_dir/<cache_key>.png.
    3. Fresh render via Blender into the cache.
    4. None — caller decides what to do (do not paper over with pack imagery).
    """
    sample = find_sample_thumbnail(model_path, pack_root)
    if sample:
        return sample
    rendered = cache_dir / f"{cache_key}.png"
    if rendered.exists():
        return rendered
    if render_model_thumbnail(model_path, rendered):
        return rendered
    return None
