#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pillow>=10.0",
# ]
# ///
"""
Aseprite file format parser.

Parses .aseprite/.ase files to extract metadata and render frames.
Based on the official spec: https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md
"""

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

# Magic numbers
ASE_HEADER_MAGIC = 0xA5E0
ASE_FRAME_MAGIC = 0xF1FA

# Chunk types
CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_CEL_EXTRA = 0x2006
CHUNK_TAGS = 0x2018
CHUNK_PALETTE = 0x2019
CHUNK_USER_DATA = 0x2020
CHUNK_TILESET = 0x2023

# Color depths
COLOR_RGBA = 32
COLOR_GRAYSCALE = 16
COLOR_INDEXED = 8

# Cel types
CEL_RAW = 0
CEL_LINKED = 1
CEL_COMPRESSED = 2
CEL_COMPRESSED_TILEMAP = 3


@dataclass
class Layer:
    """Represents a layer in the Aseprite file."""
    name: str
    visible: bool
    opacity: int
    blend_mode: int
    layer_type: int  # 0=normal, 1=group, 2=tilemap
    child_level: int


@dataclass
class Cel:
    """Represents a cel (frame/layer intersection with pixel data)."""
    layer_index: int
    x: int
    y: int
    opacity: int
    width: int
    height: int
    pixels: Optional[bytes] = None  # Raw RGBA pixel data
    linked_frame: Optional[int] = None


@dataclass
class Tag:
    """Represents an animation tag."""
    name: str
    from_frame: int
    to_frame: int
    direction: int  # 0=forward, 1=reverse, 2=ping-pong, 3=ping-pong-reverse


@dataclass
class AsepriteFile:
    """Parsed Aseprite file data."""
    width: int
    height: int
    frame_count: int
    color_depth: int
    layers: list[Layer] = field(default_factory=list)
    frames: list[list[Cel]] = field(default_factory=list)  # frames[frame_idx] = list of cels
    tags: list[Tag] = field(default_factory=list)
    palette: list[tuple[int, int, int, int]] = field(default_factory=list)


def parse_aseprite(path: Path) -> dict:
    """
    Parse an Aseprite file and return metadata.

    Returns dict with:
        - width: int
        - height: int
        - frame_count: int
        - color_depth: int (32=RGBA, 16=grayscale, 8=indexed)
        - tags: list[str] - animation tag names
        - duration_ms: int - total duration in milliseconds
    """
    ase = _parse_file(path)
    return {
        "width": ase.width,
        "height": ase.height,
        "frame_count": ase.frame_count,
        "color_depth": ase.color_depth,
        "tags": [tag.name for tag in ase.tags],
        "duration_ms": 0,  # TODO: sum frame durations
    }


def render_first_frame(path: Path) -> Image.Image:
    """
    Render the first frame of an Aseprite file.

    Returns a PIL Image in RGBA mode with all visible layers composited.
    """
    ase = _parse_file(path)
    return _render_frame(ase, 0)


def _parse_file(path: Path) -> AsepriteFile:
    """Parse the complete Aseprite file."""
    with open(path, "rb") as f:
        data = f.read()

    # Parse header (128 bytes)
    if len(data) < 128:
        raise ValueError("Invalid Aseprite file: too small")

    file_size, magic, frames, width, height, color_depth, flags = struct.unpack_from(
        "<IHHHHHI", data, 0
    )

    if magic != ASE_HEADER_MAGIC:
        raise ValueError(f"Invalid Aseprite file: bad magic number 0x{magic:04X}")

    ase = AsepriteFile(
        width=width,
        height=height,
        frame_count=frames,
        color_depth=color_depth,
    )

    # Parse frames starting at offset 128
    offset = 128
    for frame_idx in range(frames):
        if offset >= len(data):
            break

        frame_cels, offset = _parse_frame(data, offset, ase)
        ase.frames.append(frame_cels)

    return ase


def _parse_frame(data: bytes, offset: int, ase: AsepriteFile) -> tuple[list[Cel], int]:
    """Parse a single frame and its chunks."""
    if offset + 16 > len(data):
        return [], offset

    frame_size, magic, old_chunks, duration_ms = struct.unpack_from("<IHHH", data, offset)

    if magic != ASE_FRAME_MAGIC:
        raise ValueError(f"Invalid frame magic at offset {offset}")

    # New chunk count at offset + 12 if old_chunks is 0xFFFF
    if old_chunks == 0xFFFF:
        num_chunks = struct.unpack_from("<I", data, offset + 12)[0]
    else:
        num_chunks = old_chunks

    cels = []
    chunk_offset = offset + 16

    for _ in range(num_chunks):
        if chunk_offset + 6 > len(data):
            break

        chunk_size, chunk_type = struct.unpack_from("<IH", data, chunk_offset)
        chunk_data = data[chunk_offset + 6 : chunk_offset + chunk_size]

        if chunk_type == CHUNK_LAYER:
            layer = _parse_layer_chunk(chunk_data)
            ase.layers.append(layer)
        elif chunk_type == CHUNK_CEL:
            cel = _parse_cel_chunk(chunk_data, ase.color_depth)
            if cel:
                cels.append(cel)
        elif chunk_type == CHUNK_TAGS:
            tags = _parse_tags_chunk(chunk_data)
            ase.tags.extend(tags)
        elif chunk_type == CHUNK_PALETTE:
            palette = _parse_palette_chunk(chunk_data)
            ase.palette = palette

        chunk_offset += chunk_size

    return cels, offset + frame_size


def _parse_layer_chunk(data: bytes) -> Layer:
    """Parse a layer chunk."""
    flags, layer_type, child_level = struct.unpack_from("<HHH", data, 0)
    # Skip default width/height (4 bytes), blend mode (2 bytes)
    blend_mode = struct.unpack_from("<H", data, 10)[0]
    opacity = data[12]
    # Skip 3 future bytes
    name_len = struct.unpack_from("<H", data, 16)[0]
    name = data[18 : 18 + name_len].decode("utf-8")

    return Layer(
        name=name,
        visible=bool(flags & 1),
        opacity=opacity,
        blend_mode=blend_mode,
        layer_type=layer_type,
        child_level=child_level,
    )


def _parse_cel_chunk(data: bytes, color_depth: int) -> Optional[Cel]:
    """Parse a cel chunk."""
    layer_index, x, y, opacity, cel_type = struct.unpack_from("<HhhBH", data, 0)

    if cel_type == CEL_LINKED:
        linked_frame = struct.unpack_from("<H", data, 7)[0]
        return Cel(
            layer_index=layer_index,
            x=x,
            y=y,
            opacity=opacity,
            width=0,
            height=0,
            linked_frame=linked_frame,
        )
    elif cel_type in (CEL_RAW, CEL_COMPRESSED):
        # Skip z-index (2 bytes) and future (5 bytes) = 7 bytes after cel_type
        # cel_type is at offset 7, so width is at 7 + 2 + 5 = 14? No wait...
        # Layout: layer(2) + x(2) + y(2) + opacity(1) + cel_type(2) + z_index(2) + future(5) = 16
        # Then width(2) + height(2)
        width, height = struct.unpack_from("<HH", data, 16)
        pixel_data_offset = 20

        if cel_type == CEL_RAW:
            raw_pixels = data[pixel_data_offset:]
        else:  # CEL_COMPRESSED
            compressed = data[pixel_data_offset:]
            raw_pixels = zlib.decompress(compressed)

        # Convert to RGBA if needed
        rgba_pixels = _convert_to_rgba(raw_pixels, color_depth, width, height)

        return Cel(
            layer_index=layer_index,
            x=x,
            y=y,
            opacity=opacity,
            width=width,
            height=height,
            pixels=rgba_pixels,
        )

    return None


def _convert_to_rgba(data: bytes, color_depth: int, width: int, height: int) -> bytes:
    """Convert pixel data to RGBA format."""
    if color_depth == COLOR_RGBA:
        return data
    elif color_depth == COLOR_GRAYSCALE:
        # Grayscale is 2 bytes per pixel: gray + alpha
        result = bytearray()
        for i in range(0, len(data), 2):
            gray = data[i]
            alpha = data[i + 1] if i + 1 < len(data) else 255
            result.extend([gray, gray, gray, alpha])
        return bytes(result)
    elif color_depth == COLOR_INDEXED:
        # TODO: need palette to convert indexed colors
        # For now, just expand to grayscale
        result = bytearray()
        for byte in data:
            result.extend([byte, byte, byte, 255])
        return bytes(result)
    return data


def _parse_tags_chunk(data: bytes) -> list[Tag]:
    """Parse a tags chunk."""
    num_tags = struct.unpack_from("<H", data, 0)[0]
    # Skip 8 reserved bytes
    tags = []
    offset = 10

    for _ in range(num_tags):
        if offset + 18 > len(data):
            break

        from_frame, to_frame = struct.unpack_from("<HH", data, offset)
        direction = data[offset + 4]
        # Skip: repeat (2) + reserved (6) + deprecated color (3) = 11 bytes
        # So name_len is at offset + 4 + 1 + 11 = offset + 16
        name_len = struct.unpack_from("<H", data, offset + 16)[0]
        name = data[offset + 18 : offset + 18 + name_len].decode("utf-8")

        tags.append(Tag(
            name=name,
            from_frame=from_frame,
            to_frame=to_frame,
            direction=direction,
        ))

        offset += 18 + name_len

    return tags


def _parse_palette_chunk(data: bytes) -> list[tuple[int, int, int, int]]:
    """Parse a palette chunk."""
    new_size, first_idx, last_idx = struct.unpack_from("<III", data, 0)
    # Skip 8 reserved bytes
    palette = []
    offset = 20

    for i in range(last_idx - first_idx + 1):
        if offset + 6 > len(data):
            break

        flags = struct.unpack_from("<H", data, offset)[0]
        r, g, b, a = data[offset + 2 : offset + 6]
        palette.append((r, g, b, a))

        # Skip name if present (flags & 1)
        offset += 6
        if flags & 1:
            name_len = struct.unpack_from("<H", data, offset)[0]
            offset += 2 + name_len

    return palette


def _render_frame(ase: AsepriteFile, frame_idx: int) -> Image.Image:
    """Render a single frame by compositing all visible layer cels."""
    # Create transparent canvas
    result = Image.new("RGBA", (ase.width, ase.height), (0, 0, 0, 0))

    if frame_idx >= len(ase.frames):
        return result

    cels = ase.frames[frame_idx]

    # Sort cels by layer index (bottom to top)
    sorted_cels = sorted(cels, key=lambda c: c.layer_index)

    for cel in sorted_cels:
        # Check if layer is visible
        if cel.layer_index < len(ase.layers):
            layer = ase.layers[cel.layer_index]
            if not layer.visible:
                continue

        if cel.pixels is None or cel.width == 0 or cel.height == 0:
            continue

        # Create cel image
        cel_img = Image.frombytes("RGBA", (cel.width, cel.height), cel.pixels)

        # Apply cel opacity
        if cel.opacity < 255:
            cel_img.putalpha(
                cel_img.getchannel("A").point(lambda x: x * cel.opacity // 255)
            )

        # Apply layer opacity if available
        if cel.layer_index < len(ase.layers):
            layer = ase.layers[cel.layer_index]
            if layer.opacity < 255:
                cel_img.putalpha(
                    cel_img.getchannel("A").point(lambda x: x * layer.opacity // 255)
                )

        # Composite onto result
        result.alpha_composite(cel_img, (cel.x, cel.y))

    return result
