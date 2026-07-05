#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest>=8.0",
# ]
# ///
"""Tests for pack theme assignment."""

import sys

import pytest

import pack_themes


class TestAssignTheme:
    @pytest.mark.parametrize("name,theme", [
        ("Minifantasy_Creatures_v3.3_Commercial_Version", "Characters & Creatures"),
        ("Minifantasy_Ancient_Forests", "Nature"),
        ("Minifantasy_Dungeon_v2.3_Commercial_Version", "Dungeons & Caves"),
        ("Minifantasy_Towns_v3.0", "Towns & Buildings"),
        ("Minifantasy_Towns2_v1.0", "Towns & Buildings"),
        ("Minifantasy_Spell Effects_v1.0", "Magic & Effects"),
        ("Minifantasy_Spell_Effects_II_v1.0", "Magic & Effects"),
        ("Minifantasy_UI _Overhaul_v1.0", "UI"),
        ("Minifantasy_Scifi_SpaceDerelict_v1.0", "Sci-fi"),
        ("Minifantasy_Trains_v1.0", "Vehicles"),
        ("Minifantasy_Weapons_v3.0", "Items & Icons"),
        ("Minifantasy_RTS_Humans_v1.0 2", "Characters & Creatures"),
        ("KayKit Dungeon Remastered 1.1", "Dungeons & Caves"),
        ("KayKit Forest Nature Pack 1.0", "Nature"),
        ("KayKit Space Base Bits 1.0", "Sci-fi"),
        ("KayKit Mystery Monthly Series 4", "Other"),
        ("penusbmic_Sci-fi", "Sci-fi"),
        ("penusbmic_Dungeon", "Dungeons & Caves"),
    ])
    def test_known_packs(self, name, theme):
        assert pack_themes.assign_theme(name) == theme

    def test_version_bump_keeps_theme(self):
        assert pack_themes.assign_theme("Minifantasy_Creatures_v9.9") == \
            "Characters & Creatures"

    def test_token_fallback_for_unknown_pack(self):
        assert pack_themes.assign_theme("SuperVendor_Frozen_Forest_v2.0") == "Nature"

    def test_unmatchable_pack_is_other(self):
        assert pack_themes.assign_theme("Zzz_Unknowable_v1.0") == "Other"

    def test_every_current_pack_gets_a_named_theme(self):
        # every explicit mapping value must be a real theme
        for theme in pack_themes.PACK_THEMES.values():
            assert theme in pack_themes.THEME_ORDER


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
