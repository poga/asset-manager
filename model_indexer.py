"""3D asset indexing helpers: glTF/GLB parsing, sample matching, thumbnail rendering."""

import json
import struct
from pathlib import Path


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
