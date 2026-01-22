#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27",
#     "rich>=13.0",
# ]
# ///
"""Fetch pack preview images from itch.io (one-time operation)."""

import re
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress

console = Console()

# URL slug patterns for itch.io pages
ITCH_URL_OVERRIDES = {
    # Special cases where slug doesn't match pack name
    "npcs": "minifantasy-npcs",
    "amyriadofnpcs": "minifantasy-npcs",
    "scifi_spacederelict": "minifantasy-scifi-space-derelict",
    "scifispacerelict": "minifantasy-scifi-space-derelict",
    "spacederelict": "minifantasy-scifi-space-derelict",
    "dwarvenworkshop": "minifantasydwarven-workshop",  # Note: no hyphen
    "dwarven-workshop": "minifantasydwarven-workshop",
    "spelleffectsii": "minifantasyspell-effects-ii",  # Note: no hyphen before spell
    "spell_effects_ii": "minifantasyspell-effects-ii",
    "spell-effects-i-i": "minifantasyspell-effects-ii",
    "craftingandprofessions2": "minifantasy-crafting-and-professions-ii",
    "crafting-and-professions2": "minifantasy-crafting-and-professions-ii",
    "craftingandprofessions": "minifantasy-crafting-and-professions-i",
    "crafting-and-professions": "minifantasy-crafting-and-professions-i",
    "towns2": "minifantasy-towns-ii",
    "towns": "minifantasy-towns",
    "plants_&_foliage": "minifantasy-plants-foliage",
    "plantsfoliage": "minifantasy-plants-foliage",
    "plants-foliage": "minifantasy-plants-foliage",
    "portrait_generator_graphical_assets": "minifantasy-portrait-generator",
    "portraitgeneratorgraphicalassets": "minifantasy-portrait-generator",
    "portrait-generator-graphical-assets": "minifantasy-portrait-generator",
    "portrait-generator": "minifantasy-portrait-generator",
    "ui_overhaul": "minifantasy-ui-overhaul",
    "uioverhaul": "minifantasy-ui-overhaul",
    "ui-overhaul": "minifantasy-ui-overhaul",
    "spell_effects": "minifantasy-spell-effects",
    "spelleffects": "minifantasy-spell-effects",
    "ships_and_docks": "minifantasy-ships-and-docks",
    "shipsanddocks": "minifantasy-ships-and-docks",
    "ships-and-docks": "minifantasy-ships-and-docks",
    "tinyoverworld": "minifantasy-tiny-overworld",
    "tiny-overworld": "minifantasy-tiny-overworld",
    "trueheroes": "minifantasy-true-heroes",
    "true-heroes": "minifantasy-true-heroes",
}


def extract_cover_image(html: str) -> str | None:
    """Extract cover image URL from HTML (prefer game cover over og:image)."""
    # Look for screenshot_list which contains the actual cover image
    match = re.search(r'class="screenshot_list".*?<img[^>]*src="([^"]+)"', html, re.DOTALL)
    if match:
        # Use the URL as-is (keep the size parameter, it's valid)
        return match.group(1)

    # Try to find animated GIF in the page (often used as cover)
    match = re.search(r'<img[^>]*src="(https://img\.itch\.zone/[^"]+\.gif)"', html)
    if match:
        return match.group(1)

    # Fallback to og:image meta tag
    match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if match:
        return match.group(1)

    # Try alternate format
    match = re.search(r'<meta\s+content="([^"]+)"\s+property="og:image"', html)
    if match:
        return match.group(1)

    return None


def normalize_pack_name(name: str) -> str:
    """Normalize pack name by removing version suffix and extra words."""
    # Remove trailing numbers (like " 2" for duplicates) FIRST
    name = re.sub(r'\s+\d+$', '', name)
    # Remove version suffix like _v1.0, _v.1.0, _v3.3_Commercial_Version (with underscore)
    name = re.sub(r'[_ ]v\.?\d+\.?\d*(_Commercial_Version)?$', '', name, flags=re.IGNORECASE)
    return name


def camel_to_kebab(name: str) -> str:
    """Convert CamelCase to kebab-case."""
    # Insert hyphen before uppercase letters
    result = re.sub(r'([a-z])([A-Z])', r'\1-\2', name)
    return result.lower()


def find_pack_url(pack_name: str) -> str | None:
    """Find itch.io URL for a pack name by deriving slug from name."""
    # Normalize the pack name
    normalized = normalize_pack_name(pack_name)

    # Remove Minifantasy_ prefix
    if normalized.startswith("Minifantasy_"):
        slug_base = normalized[12:]  # Remove "Minifantasy_"
    else:
        slug_base = normalized

    # Check overrides first (lowercase, no underscores for matching)
    slug_key = slug_base.lower().replace("_", "").replace(" ", "")
    if slug_key in ITCH_URL_OVERRIDES:
        return f"https://krishna-palacio.itch.io/{ITCH_URL_OVERRIDES[slug_key]}"

    # Also try with underscores preserved
    slug_key_with_underscores = slug_base.lower()
    if slug_key_with_underscores in ITCH_URL_OVERRIDES:
        return f"https://krishna-palacio.itch.io/{ITCH_URL_OVERRIDES[slug_key_with_underscores]}"

    # Convert CamelCase to kebab-case (e.g., DeepCaves -> deep-caves)
    slug = camel_to_kebab(slug_base)
    # Replace underscores and spaces with hyphens
    slug = slug.replace("_", "-").replace(" ", "-")
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove special chars
    slug = re.sub(r'[^a-z0-9-]', '', slug)

    return f"https://krishna-palacio.itch.io/minifantasy-{slug}"


def fetch_preview(client: httpx.Client, pack_name: str, output_dir: Path) -> bool:
    """Fetch and save preview image for a pack."""
    url = find_pack_url(pack_name)
    if not url:
        console.print(f"[yellow]No URL mapping for: {pack_name}[/yellow]")
        return False

    try:
        # Fetch page
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()

        # Extract image URL
        img_url = extract_cover_image(resp.text)
        if not img_url:
            console.print(f"[yellow]No cover image found for: {pack_name}[/yellow]")
            return False

        # Download image
        img_resp = client.get(img_url, follow_redirects=True)
        img_resp.raise_for_status()

        # Determine extension from URL or content type
        ext = ".png"
        if ".gif" in img_url.lower():
            ext = ".gif"
        elif img_resp.headers.get("content-type", "").startswith("image/gif"):
            ext = ".gif"

        # Save image
        output_path = output_dir / f"{pack_name}{ext}"
        output_path.write_bytes(img_resp.content)

        return True
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error for {pack_name}: {e}[/red]")
        return False


def main(force: bool = False):
    """Fetch all pack previews from itch.io."""
    import sqlite3
    import sys

    # Check for --force flag
    if "--force" in sys.argv:
        force = True

    # Find database - try multiple locations
    db_path = Path("assets.db")
    if not db_path.exists():
        db_path = Path(".assetindex/assets.db")
    if not db_path.exists():
        console.print("[red]Database not found at assets.db or .assetindex/assets.db[/red]")
        return

    # Get pack names from database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    packs = conn.execute("SELECT name FROM packs ORDER BY name").fetchall()
    pack_names = [row["name"] for row in packs]
    conn.close()

    console.print(f"Found {len(pack_names)} packs in database")

    # Create output directory
    output_dir = Path(".assetindex/previews")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch previews
    success_count = 0
    skip_count = 0

    with httpx.Client(timeout=30.0) as client:
        with Progress() as progress:
            task = progress.add_task("Fetching previews...", total=len(pack_names))

            for pack_name in pack_names:
                # Skip if already exists (check both .png and .gif)
                if not force:
                    png_path = output_dir / f"{pack_name}.png"
                    gif_path = output_dir / f"{pack_name}.gif"
                    if png_path.exists() or gif_path.exists():
                        skip_count += 1
                        progress.advance(task)
                        continue

                if fetch_preview(client, pack_name, output_dir):
                    success_count += 1

                progress.advance(task)

                # Be nice to itch.io
                time.sleep(0.5)

    console.print(f"\n[green]Done![/green] Downloaded {success_count} previews, skipped {skip_count} existing")


if __name__ == "__main__":
    main()
