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
