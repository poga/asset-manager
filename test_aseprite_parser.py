#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
# ]
# ///
"""Tests for Aseprite file parser."""

import struct
import tempfile
import zlib
from pathlib import Path

import pytest
from PIL import Image


# =============================================================================
# Test Fixtures - Generate minimal valid Aseprite files
# =============================================================================


def create_aseprite_header(
    width: int = 32,
    height: int = 32,
    frames: int = 1,
    color_depth: int = 32,  # RGBA
) -> bytes:
    """Create a minimal valid Aseprite header (128 bytes)."""
    header = bytearray(128)

    # File size - will be updated later
    struct.pack_into("<I", header, 0, 0)
    # Magic number
    struct.pack_into("<H", header, 4, 0xA5E0)
    # Frame count
    struct.pack_into("<H", header, 6, frames)
    # Width
    struct.pack_into("<H", header, 8, width)
    # Height
    struct.pack_into("<H", header, 10, height)
    # Color depth (32 = RGBA)
    struct.pack_into("<H", header, 12, color_depth)
    # Flags (bit 1 = layer opacity valid)
    struct.pack_into("<I", header, 14, 1)
    # Speed (deprecated, use frame duration)
    struct.pack_into("<H", header, 18, 100)
    # Reserved zeros at 20-27
    # Transparent index
    header[28] = 0
    # Ignore 3 bytes at 29-31
    # Number of colors (0 = 256 for old sprites)
    struct.pack_into("<H", header, 32, 0)
    # Pixel width/height (aspect ratio)
    header[34] = 1
    header[35] = 1
    # Grid position
    struct.pack_into("<h", header, 36, 0)
    struct.pack_into("<h", header, 38, 0)
    # Grid size
    struct.pack_into("<H", header, 40, 16)
    struct.pack_into("<H", header, 42, 16)
    # Rest is reserved (zeros)

    return bytes(header)


def create_frame(chunks: list[bytes], duration_ms: int = 100) -> bytes:
    """Create a frame with given chunks."""
    chunks_data = b"".join(chunks)
    frame_size = 16 + len(chunks_data)  # Frame header is 16 bytes

    frame = bytearray(16)
    # Frame size
    struct.pack_into("<I", frame, 0, frame_size)
    # Magic
    struct.pack_into("<H", frame, 4, 0xF1FA)
    # Old chunk count (use 0xFFFF to indicate new field)
    struct.pack_into("<H", frame, 6, len(chunks) if len(chunks) < 0xFFFF else 0xFFFF)
    # Duration in ms
    struct.pack_into("<H", frame, 8, duration_ms)
    # Reserved
    frame[10] = 0
    frame[11] = 0
    # New chunk count
    struct.pack_into("<I", frame, 12, len(chunks))

    return bytes(frame) + chunks_data


def create_layer_chunk(name: str = "Layer 1", visible: bool = True) -> bytes:
    """Create a layer chunk (0x2004)."""
    name_bytes = name.encode("utf-8")
    # Chunk: size (4) + type (2) + flags (2) + type (2) + child_level (2) +
    #        default_width (2) + default_height (2) + blend_mode (2) + opacity (1) +
    #        future (3) + name_len (2) + name
    data = bytearray()
    # Flags: bit 0 = visible
    flags = 1 if visible else 0
    data.extend(struct.pack("<H", flags))
    # Layer type (0 = normal)
    data.extend(struct.pack("<H", 0))
    # Child level
    data.extend(struct.pack("<H", 0))
    # Default width/height (ignored)
    data.extend(struct.pack("<H", 0))
    data.extend(struct.pack("<H", 0))
    # Blend mode (0 = normal)
    data.extend(struct.pack("<H", 0))
    # Opacity
    data.append(255)
    # Future (3 bytes)
    data.extend(b"\x00\x00\x00")
    # Name
    data.extend(struct.pack("<H", len(name_bytes)))
    data.extend(name_bytes)

    chunk_size = 6 + len(data)
    return struct.pack("<IH", chunk_size, 0x2004) + bytes(data)


def create_cel_chunk_compressed(
    layer_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    pixels: bytes,
) -> bytes:
    """Create a compressed cel chunk (0x2005)."""
    compressed = zlib.compress(pixels)

    data = bytearray()
    # Layer index
    data.extend(struct.pack("<H", layer_index))
    # X, Y position
    data.extend(struct.pack("<h", x))
    data.extend(struct.pack("<h", y))
    # Opacity
    data.append(255)
    # Cel type (2 = compressed image)
    data.extend(struct.pack("<H", 2))
    # Z-index
    data.extend(struct.pack("<h", 0))
    # Future (5 bytes)
    data.extend(b"\x00\x00\x00\x00\x00")
    # Width, height (for compressed)
    data.extend(struct.pack("<H", width))
    data.extend(struct.pack("<H", height))
    # Compressed pixel data
    data.extend(compressed)

    chunk_size = 6 + len(data)
    return struct.pack("<IH", chunk_size, 0x2005) + bytes(data)


def create_tags_chunk(tags: list[tuple[str, int, int]]) -> bytes:
    """Create a tags chunk (0x2018). Tags are (name, from_frame, to_frame)."""
    data = bytearray()
    # Number of tags
    data.extend(struct.pack("<H", len(tags)))
    # Reserved (8 bytes)
    data.extend(b"\x00" * 8)

    for name, from_frame, to_frame in tags:
        name_bytes = name.encode("utf-8")
        # From frame
        data.extend(struct.pack("<H", from_frame))
        # To frame
        data.extend(struct.pack("<H", to_frame))
        # Animation direction (0 = forward)
        data.append(0)
        # Repeat (0 = infinite)
        data.extend(struct.pack("<H", 0))
        # Reserved (6 bytes) - used to be 10, now 6 + RGB color
        data.extend(b"\x00" * 6)
        # Tag color (deprecated, 3 bytes RGB)
        data.extend(b"\x00\x00\x00")
        # Name length and name
        data.extend(struct.pack("<H", len(name_bytes)))
        data.extend(name_bytes)

    chunk_size = 6 + len(data)
    return struct.pack("<IH", chunk_size, 0x2018) + bytes(data)


def create_minimal_aseprite(
    width: int = 32,
    height: int = 32,
    color: tuple[int, int, int, int] = (255, 0, 0, 255),
    tags: list[tuple[str, int, int]] | None = None,
) -> bytes:
    """Create a minimal valid Aseprite file with one frame and one layer."""
    # Create pixel data (RGBA)
    pixels = bytes(color) * (width * height)

    # Build chunks for frame 0
    chunks = [
        create_layer_chunk("Layer 1", visible=True),
        create_cel_chunk_compressed(0, 0, 0, width, height, pixels),
    ]
    if tags:
        chunks.append(create_tags_chunk(tags))

    frame = create_frame(chunks)
    header = create_aseprite_header(width, height, frames=1)

    # Update file size in header
    file_data = bytearray(header + frame)
    struct.pack_into("<I", file_data, 0, len(file_data))

    return bytes(file_data)


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_aseprite(temp_dir):
    """Create a sample Aseprite file."""
    path = temp_dir / "test.aseprite"
    path.write_bytes(create_minimal_aseprite(32, 32, (255, 0, 0, 255)))
    return path


@pytest.fixture
def aseprite_with_tags(temp_dir):
    """Create an Aseprite file with animation tags."""
    path = temp_dir / "tagged.aseprite"
    data = create_minimal_aseprite(
        32, 32,
        tags=[("idle", 0, 0), ("walk", 0, 0), ("attack", 0, 0)]
    )
    path.write_bytes(data)
    return path


# =============================================================================
# Tests for parse_aseprite
# =============================================================================


class TestParseAseprite:
    """Tests for parse_aseprite function."""

    def test_parses_dimensions(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.parse_aseprite(sample_aseprite)

        assert result["width"] == 32
        assert result["height"] == 32

    def test_parses_frame_count(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.parse_aseprite(sample_aseprite)

        assert result["frame_count"] == 1

    def test_parses_color_depth(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.parse_aseprite(sample_aseprite)

        assert result["color_depth"] == 32

    def test_parses_tags(self, aseprite_with_tags):
        import aseprite_parser

        result = aseprite_parser.parse_aseprite(aseprite_with_tags)

        assert "tags" in result
        assert "idle" in result["tags"]
        assert "walk" in result["tags"]
        assert "attack" in result["tags"]

    def test_returns_empty_tags_when_none(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.parse_aseprite(sample_aseprite)

        assert result["tags"] == []

    def test_raises_on_invalid_magic(self, temp_dir):
        import aseprite_parser

        bad_file = temp_dir / "bad.aseprite"
        bad_file.write_bytes(b"\x00" * 128)

        with pytest.raises(ValueError, match="Invalid Aseprite file"):
            aseprite_parser.parse_aseprite(bad_file)


# =============================================================================
# Tests for render_first_frame
# =============================================================================


class TestRenderFirstFrame:
    """Tests for render_first_frame function."""

    def test_returns_pil_image(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.render_first_frame(sample_aseprite)

        assert isinstance(result, Image.Image)

    def test_correct_dimensions(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.render_first_frame(sample_aseprite)

        assert result.size == (32, 32)

    def test_correct_mode(self, sample_aseprite):
        import aseprite_parser

        result = aseprite_parser.render_first_frame(sample_aseprite)

        assert result.mode == "RGBA"

    def test_renders_pixel_color(self, temp_dir):
        import aseprite_parser

        # Create file with known color
        path = temp_dir / "red.aseprite"
        path.write_bytes(create_minimal_aseprite(4, 4, (255, 0, 0, 255)))

        result = aseprite_parser.render_first_frame(path)

        # Check center pixel is red
        pixel = result.getpixel((2, 2))
        assert pixel == (255, 0, 0, 255)


# =============================================================================
# Entry point
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
