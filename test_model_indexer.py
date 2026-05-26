#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
#     "pillow>=10.0",
#     "trimesh[easy]>=4.0",
# ]
# ///
"""Tests for model_indexer."""

from pathlib import Path

import pytest

import model_indexer

FIXTURES = Path(__file__).parent / "tests" / "fixtures" / "3d"


class TestLoadGltfJson:
    def test_loads_glb(self):
        data = model_indexer.load_gltf_json(FIXTURES / "BoxAnimated.glb")
        assert "asset" in data
        assert "animations" in data
        assert len(data["animations"]) >= 1

    def test_loads_gltf(self):
        data = model_indexer.load_gltf_json(FIXTURES / "axe_1handed.gltf")
        assert "asset" in data
        assert "buffers" in data

    def test_glb_magic_validated(self, tmp_path):
        bogus = tmp_path / "fake.glb"
        bogus.write_bytes(b"NOPE" + b"\x00" * 100)
        with pytest.raises(ValueError, match="not a glTF binary"):
            model_indexer.load_gltf_json(bogus)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
