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


class TestCanonicalFormatFilter:
    def test_glb_wins_over_gltf_same_stem(self, tmp_path):
        (tmp_path / "Knight.glb").write_bytes(b"glTF\x02\x00\x00\x00\x10\x00\x00\x00")
        (tmp_path / "Knight.gltf").write_text("{}")
        (tmp_path / "Knight.bin").write_bytes(b"")
        files = [tmp_path / "Knight.glb", tmp_path / "Knight.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert tmp_path / "Knight.glb" in kept
        assert tmp_path / "Knight.gltf" not in kept

    def test_keeps_gltf_when_no_glb_sibling(self, tmp_path):
        files = [tmp_path / "axe.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert files == kept

    def test_different_directories_independent(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir(); b.mkdir()
        files = [a / "Knight.glb", b / "Knight.gltf"]
        kept = model_indexer.filter_canonical_models(files)
        assert set(kept) == set(files)


class TestFindSampleThumbnail:
    def test_finds_sample_one_level_up(self, tmp_path):
        # pack/Characters/gltf/Knight.glb  ←  pack/Samples/knight.png
        pack = tmp_path / "pack"
        models = pack / "Characters" / "gltf"
        samples = pack / "Samples"
        models.mkdir(parents=True); samples.mkdir()
        model = models / "Knight.glb"; model.write_bytes(b"")
        sample = samples / "knight.png"; sample.write_bytes(b"\x89PNG")
        assert model_indexer.find_sample_thumbnail(model, pack) == sample

    def test_returns_none_when_no_match(self, tmp_path):
        pack = tmp_path / "pack"; (pack / "Samples").mkdir(parents=True)
        model = pack / "Mage.glb"; model.write_bytes(b"")
        assert model_indexer.find_sample_thumbnail(model, pack) is None


class TestRenderModelThumbnail:
    def test_renders_png(self, tmp_path):
        if not model_indexer.find_blender():
            pytest.skip("Blender not installed on this host")
        out = tmp_path / "thumb.png"
        ok = model_indexer.render_model_thumbnail(FIXTURES / "BoxAnimated.glb", out, size=128)
        assert ok is True
        from PIL import Image
        with Image.open(out) as img:
            assert img.size == (128, 128)

    def test_returns_false_on_garbage(self, tmp_path):
        if not model_indexer.find_blender():
            pytest.skip("Blender not installed on this host")
        bad = tmp_path / "bad.glb"; bad.write_bytes(b"not a glb")
        ok = model_indexer.render_model_thumbnail(bad, tmp_path / "out.png", size=128)
        assert ok is False

    def test_returns_false_when_blender_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(model_indexer, "find_blender", lambda: None)
        ok = model_indexer.render_model_thumbnail(FIXTURES / "BoxAnimated.glb",
                                                  tmp_path / "x.png", size=64)
        assert ok is False


class TestResolveThumbnail:
    def test_prefers_sample_over_render(self, tmp_path):
        pack = tmp_path / "p"; (pack / "Samples").mkdir(parents=True)
        sample = pack / "Samples" / "box.png"; sample.write_bytes(b"\x89PNG")
        model = pack / "Box.glb"; model.write_bytes(b"")
        cache = tmp_path / "cache"
        result = model_indexer.resolve_thumbnail(model, pack, cache, "k")
        assert result == sample

    def test_uses_cache_when_present(self, tmp_path):
        pack = tmp_path / "p"; pack.mkdir()
        model = pack / "Box.glb"; model.write_bytes(b"")
        cache = tmp_path / "cache"; cache.mkdir()
        cached = cache / "k.png"; cached.write_bytes(b"\x89PNG")
        result = model_indexer.resolve_thumbnail(model, pack, cache, "k")
        assert result == cached

    def test_returns_none_when_render_fails(self, tmp_path, monkeypatch):
        # No Sample, no cache, render fails → must return None (no fallback to pack imagery)
        pack = tmp_path / "p"; pack.mkdir()
        (pack / "contents.png").write_bytes(b"\x89PNG")  # not used as fallback
        model = pack / "Box.glb"; model.write_bytes(b"")
        cache = tmp_path / "cache"
        monkeypatch.setattr(model_indexer, "render_model_thumbnail", lambda *a, **k: False)
        result = model_indexer.resolve_thumbnail(model, pack, cache, "k")
        assert result is None


class TestFindPackPreview:
    def test_finds_contents_png(self, tmp_path):
        (tmp_path / "contents.png").write_bytes(b"\x89PNG")
        assert model_indexer.find_pack_preview(tmp_path) == tmp_path / "contents.png"

    def test_finds_contents_jpg(self, tmp_path):
        (tmp_path / "contents.jpg").write_bytes(b"\xff\xd8\xff")
        assert model_indexer.find_pack_preview(tmp_path) == tmp_path / "contents.jpg"

    def test_prefers_png_over_jpg(self, tmp_path):
        png = tmp_path / "contents.png"; png.write_bytes(b"\x89PNG")
        (tmp_path / "contents.jpg").write_bytes(b"\xff\xd8\xff")
        assert model_indexer.find_pack_preview(tmp_path) == png

    def test_returns_none_when_missing(self, tmp_path):
        assert model_indexer.find_pack_preview(tmp_path) is None

    def test_finds_prefixed_contents_jpg(self, tmp_path):
        target = tmp_path / "CityBuilder_Contents.jpg"
        target.write_bytes(b"\xff\xd8\xff")
        assert model_indexer.find_pack_preview(tmp_path) == target

    def test_skips_alternate_texture_variant(self, tmp_path):
        main = tmp_path / "Furniture_Contents.jpg"
        alt = tmp_path / "Furniture_Contents_AlternateTexture.jpg"
        main.write_bytes(b"\xff\xd8\xff")
        alt.write_bytes(b"\xff\xd8\xff")
        assert model_indexer.find_pack_preview(tmp_path) == main

    def test_picks_alphabetically_first_when_multiple_prefixed(self, tmp_path):
        (tmp_path / "Z_Contents.jpg").write_bytes(b"\xff\xd8\xff")
        a = tmp_path / "A_Contents.jpg"; a.write_bytes(b"\xff\xd8\xff")
        assert model_indexer.find_pack_preview(tmp_path) == a

    def test_exact_contents_png_beats_prefixed_jpg(self, tmp_path):
        (tmp_path / "Whatever_Contents.jpg").write_bytes(b"\xff\xd8\xff")
        exact = tmp_path / "contents.png"; exact.write_bytes(b"\x89PNG")
        assert model_indexer.find_pack_preview(tmp_path) == exact


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
