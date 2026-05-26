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


class TestExtractModelInfo:
    def test_character_has_mesh_and_rig(self):
        info = model_indexer.extract_model_info(FIXTURES / "Knight.glb")
        assert info.has_mesh is True
        assert info.rig == "Rig_Medium"
        # Knight.glb itself ships with no embedded clips
        assert info.animations == []

    def test_animation_bundle_has_rig_and_clips(self):
        # KayKit bundles include mannequin meshes alongside animation data
        info = model_indexer.extract_model_info(FIXTURES / "Rig_Medium_General.glb")
        assert info.rig == "Rig_Medium"
        assert len(info.animations) >= 1
        assert any("idle" in n.lower() for n in info.animations)

    def test_gltf_lists_referenced_bin(self):
        info = model_indexer.extract_model_info(FIXTURES / "axe_1handed.gltf")
        assert "axe_1handed.bin" in info.referenced_files

    def test_glb_has_no_external_references(self):
        info = model_indexer.extract_model_info(FIXTURES / "Knight.glb")
        # .glb is self-contained; data-URIs and embedded chunks aren't external files
        assert info.referenced_files == []

    def test_rig_unknown_returns_none(self, tmp_path):
        # Build a tiny GLB with no rig hint in name
        src = FIXTURES / "BoxAnimated.glb"
        dst = tmp_path / "anonymous.glb"
        dst.write_bytes(src.read_bytes())
        info = model_indexer.extract_model_info(dst)
        assert info.rig is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
