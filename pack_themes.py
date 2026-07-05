#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Theme assignment for asset packs.

Names are normalized to a version-free slug so version bumps keep their
theme. Edit PACK_THEMES to recategorize; TOKEN_RULES only catches packs
with no explicit entry.
"""

import re

NATURE = "Nature"
DUNGEONS = "Dungeons & Caves"
TOWNS = "Towns & Buildings"
CHARACTERS = "Characters & Creatures"
MAGIC = "Magic & Effects"
ITEMS = "Items & Icons"
UI = "UI"
SCIFI = "Sci-fi"
VEHICLES = "Vehicles"
OTHER = "Other"

THEME_ORDER = [
    NATURE, DUNGEONS, TOWNS, CHARACTERS, MAGIC, ITEMS, UI, SCIFI, VEHICLES, OTHER,
]

# slug -> theme; slugs come from _slug() (lowercase letters only,
# vendor prefix and version/filler words removed)
PACK_THEMES = {
    # KayKit
    "adventurers": CHARACTERS,
    "block": ITEMS,
    "boardgame": ITEMS,
    "characteranimations": CHARACTERS,
    "citybuilder": TOWNS,
    "dungeonremastered": DUNGEONS,
    "fantasyweapons": ITEMS,
    "forestnature": NATURE,
    "furniture": ITEMS,
    "halloween": ITEMS,
    "holiday": ITEMS,
    "medievalhexagon": TOWNS,
    "mysterymonthlyseries": OTHER,
    "platformer": OTHER,
    "prototype": OTHER,
    "rpgtools": ITEMS,
    "resource": ITEMS,
    "restaurant": TOWNS,
    "skeletons": CHARACTERS,
    "spacebase": SCIFI,
    # Minifantasy
    "amyriadofnpcs": CHARACTERS,
    "ancientforests": NATURE,
    "builders": TOWNS,
    "castlesandstrongholds": TOWNS,
    "craftingandprofessions": ITEMS,
    "creatures": CHARACTERS,
    "cryptoftheforgotten": DUNGEONS,
    "darkbrotherhood": CHARACTERS,
    "deepcaves": DUNGEONS,
    "desolatedesert": NATURE,
    "dungeon": DUNGEONS,
    "dwarvenkingdom": DUNGEONS,
    "dwarvenworkshop": TOWNS,
    "elvenkingdom": TOWNS,
    "enchantedcompanions": CHARACTERS,
    "faedepths": DUNGEONS,
    "farm": TOWNS,
    "forestdwellers": CHARACTERS,
    "forgottenplains": NATURE,
    "gloomhollows": NATURE,
    "hellscape": DUNGEONS,
    "icywilderness": NATURE,
    "lostcivilization": DUNGEONS,
    "lostjungle": NATURE,
    "magicandsorcery": MAGIC,
    "magicweaponsandeffects": MAGIC,
    "maps": UI,
    "medievalcarnival": TOWNS,
    "medievalcity": TOWNS,
    "modernapocalypse": TOWNS,
    "moderntown": TOWNS,
    "monstercreatures": CHARACTERS,
    "mountainstronghold": TOWNS,
    "mounts": CHARACTERS,
    "necropolis": DUNGEONS,
    "nightmarerealm": MAGIC,
    "orckingdom": TOWNS,
    "persianpalace": TOWNS,
    "pharaohtomb": DUNGEONS,
    "plantsfoliage": NATURE,
    "portraitgenerator": UI,
    "rtshumans": CHARACTERS,
    "rtsorcs": CHARACTERS,
    "raidedvillage": TOWNS,
    "scifispacederelict": SCIFI,
    "sewers": DUNGEONS,
    "shipsanddocks": VEHICLES,
    "silentswamp": NATURE,
    "spelleffects": MAGIC,
    "spelleffectsii": MAGIC,
    "templeofthesnakegod": DUNGEONS,
    "templesandshrines": TOWNS,
    "tinyoverworld": NATURE,
    "tinyoverworldii": NATURE,
    "towers": TOWNS,
    "towns": TOWNS,
    "trains": VEHICLES,
    "trueheroes": CHARACTERS,
    "trueheroesii": CHARACTERS,
    "trueheroesiii": CHARACTERS,
    "trueheroesiv": CHARACTERS,
    "truevillainsi": CHARACTERS,
    "uioverhaul": UI,
    "undeadcreatures": CHARACTERS,
    "warplands": NATURE,
    "weapons": ITEMS,
    "wildwesttown": TOWNS,
    "wildlife": CHARACTERS,
    "wizardsacademy": TOWNS,
    # penusbmic
    "alchemist": CHARACTERS,
    "dark": CHARACTERS,
    "scifi": SCIFI,
    "stranded": SCIFI,
    "thrones": ITEMS,
    "fantasycards": UI,
}

# fallback for packs without an explicit entry; first match wins
TOKEN_RULES = [
    (r"forest|jungle|swamp|plain|desert|ic[ey]|winter|nature|plant|foliage|overworld|wild", NATURE),
    (r"dungeon|cave|crypt|sewer|tomb|necropolis|ruin|depth", DUNGEONS),
    (r"town|city|village|castle|stronghold|palace|temple|farm|house|build", TOWNS),
    (r"creature|character|hero|villain|npc|monster|undead|skeleton|companion|mount", CHARACTERS),
    (r"magic|spell|effect|sorcery|enchant", MAGIC),
    (r"weapon|item|icon|prop|furniture|resource|tool|craft", ITEMS),
    (r"\bui\b|interface|portrait|card|menu", UI),
    (r"sci-?fi|space|cyber|derelict", SCIFI),
    (r"train|ship|boat|vehicle|cart", VEHICLES),
]

_VERSION = re.compile(r"v?\.?\d+(\.\d+)*")
_FILLER = re.compile(r"commercial|version|pack|bits|assets|graphical")
_NON_ALPHA = re.compile(r"[^a-z]")


def _slug(name: str) -> str:
    s = name.lower()
    s = _VERSION.sub("", s)
    s = _FILLER.sub("", s)
    s = _NON_ALPHA.sub("", s)
    for prefix in ("minifantasy", "kaykit", "penusbmic"):
        s = s.removeprefix(prefix)
    return s


def assign_theme(pack_name: str) -> str:
    slug = _slug(pack_name)
    if slug in PACK_THEMES:
        return PACK_THEMES[slug]
    lower = pack_name.lower()
    for pattern, theme in TOKEN_RULES:
        if re.search(pattern, lower):
            return theme
    return OTHER
