# Set Preview Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a CLI command to set custom preview images for packs by name or glob pattern.

**Architecture:** Add a `set-preview` typer command to `index.py` that accepts a pack pattern and optional image path, matches packs using fnmatch, copies the preview image to `.assetindex/previews/`, and updates the database.

**Tech Stack:** Python, typer, PIL, sqlite3, fnmatch, shutil

---

### Task 1: Write failing test for set_pack_preview function

**Files:**
- Modify: `test_index.py`

**Step 1: Write the failing test**

Add a new test class after line 914 (after `TestPreviewBoundsSchema`):

```python
class TestSetPackPreview:
    """Tests for set_pack_preview function."""

    def test_sets_preview_with_explicit_path(self, temp_dir):
        """Set preview from explicit image path."""
        # Create pack in database
        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.execute(
            "INSERT INTO packs (id, name, path) VALUES (?, ?, ?)",
            [1, "TestPack_v1.0", "TestPack_v1.0"]
        )
        conn.commit()

        # Create preview image
        preview_img = temp_dir / "custom_preview.png"
        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        img.save(preview_img)

        # Create preview directory
        preview_dir = temp_dir / ".assetindex" / "previews"
        preview_dir.mkdir(parents=True)

        # Call function
        count = index.set_pack_preview(conn, "TestPack_v1.0", preview_dir, preview_img)

        # Verify
        assert count == 1
        assert (preview_dir / "TestPack_v1.0.png").exists()
        row = conn.execute("SELECT preview_path, preview_generated FROM packs WHERE id = 1").fetchone()
        assert row["preview_path"] == "previews/TestPack_v1.0.png"
        assert row["preview_generated"] == 0
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest test_index.py::TestSetPackPreview::test_sets_preview_with_explicit_path -v`
Expected: FAIL with "AttributeError: module 'index' has no attribute 'set_pack_preview'"

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add failing test for set_pack_preview function"
```

---

### Task 2: Implement set_pack_preview function

**Files:**
- Modify: `index.py:670` (before the `if __name__` block)

**Step 1: Write minimal implementation**

Add after line 669 (after `detect_relationships` function), before the `@app.command()` decorators:

```python
def set_pack_preview(
    conn: sqlite3.Connection,
    pack_pattern: str,
    preview_dir: Path,
    image_path: Optional[Path] = None,
    asset_root: Optional[Path] = None,
) -> int:
    """
    Set custom preview image for packs matching a pattern.

    Args:
        conn: Database connection
        pack_pattern: Pack name or glob pattern (case-insensitive)
        preview_dir: Directory to store previews
        image_path: Explicit path to preview image (optional)
        asset_root: Root directory for assets (needed for convention-based lookup)

    Returns:
        Number of packs updated
    """
    import fnmatch
    import shutil

    # Get all packs
    packs = conn.execute("SELECT id, name, path FROM packs").fetchall()

    # Match packs using fnmatch (case-insensitive)
    matched = [p for p in packs if fnmatch.fnmatch(p["name"].lower(), pack_pattern.lower())]

    if not matched:
        return 0

    preview_dir.mkdir(parents=True, exist_ok=True)
    updated = 0

    for pack in matched:
        # Determine source image
        source_image = image_path

        if source_image is None and asset_root:
            # Convention-based lookup
            pack_dir = asset_root / pack["path"]
            for name in ["preview.gif", "preview.png"]:
                candidate = pack_dir / name
                if candidate.exists():
                    source_image = candidate
                    break

        if source_image is None or not source_image.exists():
            continue

        # Copy to preview directory
        ext = source_image.suffix.lower()
        dest_path = preview_dir / f"{pack['name']}{ext}"
        shutil.copy2(source_image, dest_path)

        # Update database
        preview_rel_path = f"previews/{pack['name']}{ext}"
        conn.execute(
            "UPDATE packs SET preview_path = ?, preview_generated = FALSE WHERE id = ?",
            [preview_rel_path, pack["id"]]
        )
        updated += 1

    conn.commit()
    return updated
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPackPreview::test_sets_preview_with_explicit_path -v`
Expected: PASS

**Step 3: Commit**

```bash
git add index.py
git commit -m "feat: add set_pack_preview function"
```

---

### Task 3: Add test for glob pattern matching

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add to `TestSetPackPreview` class:

```python
    def test_matches_packs_with_glob_pattern(self, temp_dir):
        """Set preview for multiple packs using glob pattern."""
        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [1, "Penusbmic_Dungeon", "Penusbmic_Dungeon"])
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [2, "Penusbmic_Forest", "Penusbmic_Forest"])
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [3, "OtherPack", "OtherPack"])
        conn.commit()

        preview_img = temp_dir / "preview.gif"
        img = Image.new("RGBA", (64, 64), (0, 255, 0, 255))
        img.save(preview_img)

        preview_dir = temp_dir / ".assetindex" / "previews"
        preview_dir.mkdir(parents=True)

        count = index.set_pack_preview(conn, "penusbmic_*", preview_dir, preview_img)

        assert count == 2
        assert (preview_dir / "Penusbmic_Dungeon.gif").exists()
        assert (preview_dir / "Penusbmic_Forest.gif").exists()
        assert not (preview_dir / "OtherPack.gif").exists()
        conn.close()
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPackPreview::test_matches_packs_with_glob_pattern -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add glob pattern matching test for set_pack_preview"
```

---

### Task 4: Add test for convention-based lookup

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add to `TestSetPackPreview` class:

```python
    def test_finds_preview_in_pack_directory(self, temp_dir):
        """Find preview.png/gif in pack directory when no explicit path given."""
        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [1, "TestPack", "TestPack"])
        conn.commit()

        # Create pack directory with preview.gif
        pack_dir = temp_dir / "TestPack"
        pack_dir.mkdir()
        preview_in_pack = pack_dir / "preview.gif"
        img = Image.new("RGBA", (32, 32), (0, 0, 255, 255))
        img.save(preview_in_pack)

        preview_dir = temp_dir / ".assetindex" / "previews"
        preview_dir.mkdir(parents=True)

        count = index.set_pack_preview(conn, "TestPack", preview_dir, asset_root=temp_dir)

        assert count == 1
        assert (preview_dir / "TestPack.gif").exists()
        conn.close()
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPackPreview::test_finds_preview_in_pack_directory -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add convention-based lookup test for set_pack_preview"
```

---

### Task 5: Add test for no matching packs

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add to `TestSetPackPreview` class:

```python
    def test_returns_zero_for_no_matches(self, temp_dir):
        """Return 0 when no packs match the pattern."""
        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [1, "SomePack", "SomePack"])
        conn.commit()

        preview_img = temp_dir / "preview.png"
        img = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        img.save(preview_img)

        preview_dir = temp_dir / ".assetindex" / "previews"
        preview_dir.mkdir(parents=True)

        count = index.set_pack_preview(conn, "nonexistent_*", preview_dir, preview_img)

        assert count == 0
        conn.close()
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPackPreview::test_returns_zero_for_no_matches -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add no-match test for set_pack_preview"
```

---

### Task 6: Write failing test for CLI command

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add new test class after `TestSetPackPreview`:

```python
class TestSetPreviewCLI:
    """Tests for set-preview CLI command."""

    def test_set_preview_command_with_explicit_path(self, temp_dir):
        """CLI command sets preview with explicit path."""
        from typer.testing import CliRunner

        # Setup: create database with pack
        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.execute("INSERT INTO packs (id, name, path) VALUES (?, ?, ?)", [1, "TestPack", "TestPack"])
        conn.commit()
        conn.close()

        # Create preview image
        preview_img = temp_dir / "my_preview.png"
        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        img.save(preview_img)

        # Create preview directory
        preview_dir = temp_dir / ".assetindex" / "previews"
        preview_dir.mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(index.app, [
            "set-preview",
            "TestPack",
            str(preview_img),
            "--db", str(db_path)
        ])

        assert result.exit_code == 0
        assert "Updated 1 pack(s)" in result.stdout
        assert (preview_dir / "TestPack.png").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest test_index.py::TestSetPreviewCLI::test_set_preview_command_with_explicit_path -v`
Expected: FAIL with "No such command 'set-preview'"

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add failing test for set-preview CLI command"
```

---

### Task 7: Implement set-preview CLI command

**Files:**
- Modify: `index.py` (add after the `update` command, before `if __name__`)

**Step 1: Write the CLI command**

Add after the `update` command (around line 705):

```python
@app.command("set-preview")
def set_preview(
    pack_pattern: str = typer.Argument(..., help="Pack name or glob pattern (e.g., 'pensubmic_*')"),
    image_path: Optional[Path] = typer.Argument(None, help="Path to preview image (png/gif)"),
    db: Path = typer.Option("assets.db", "--db", help="Database path"),
):
    """Set custom preview image for packs."""
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        raise typer.Exit(1)

    # Validate explicit image path if provided
    if image_path is not None:
        if not image_path.exists():
            console.print(f"[red]Error: File not found: {image_path}[/red]")
            raise typer.Exit(1)
        if image_path.suffix.lower() not in {".png", ".gif"}:
            console.print(f"[red]Error: Preview must be .png or .gif[/red]")
            raise typer.Exit(1)

    conn = get_db(db)
    preview_dir = db.parent / ".assetindex" / "previews"

    # Infer asset root from pack paths
    asset_root = db.parent
    row = conn.execute("SELECT path FROM packs LIMIT 1").fetchone()
    if row and not (asset_root / row["path"]).exists():
        # Try to find assets directory
        for candidate in [db.parent / "assets", db.parent]:
            if candidate.exists():
                asset_root = candidate
                break

    count = set_pack_preview(conn, pack_pattern, preview_dir, image_path, asset_root)

    if count == 0:
        if image_path is None:
            console.print(f"[yellow]No packs matching '{pack_pattern}' found, or no preview.png/gif in pack directories[/yellow]")
        else:
            console.print(f"[red]Error: No packs matching '{pack_pattern}' found[/red]")
        raise typer.Exit(1)

    # Print what was updated
    matched_packs = conn.execute(
        "SELECT name FROM packs WHERE preview_generated = FALSE"
    ).fetchall()
    for pack in matched_packs[-count:]:
        console.print(f"Set preview for {pack['name']}")

    console.print(f"[green]Updated {count} pack(s)[/green]")
    conn.close()
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPreviewCLI::test_set_preview_command_with_explicit_path -v`
Expected: PASS

**Step 3: Commit**

```bash
git add index.py
git commit -m "feat: add set-preview CLI command"
```

---

### Task 8: Add CLI test for error when image not found

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add to `TestSetPreviewCLI` class:

```python
    def test_error_when_image_not_found(self, temp_dir):
        """CLI exits with error when image path doesn't exist."""
        from typer.testing import CliRunner

        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.close()

        runner = CliRunner()
        result = runner.invoke(index.app, [
            "set-preview",
            "TestPack",
            "/nonexistent/image.png",
            "--db", str(db_path)
        ])

        assert result.exit_code == 1
        assert "File not found" in result.stdout
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPreviewCLI::test_error_when_image_not_found -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add CLI error handling test for missing image"
```

---

### Task 9: Add CLI test for invalid file type

**Files:**
- Modify: `test_index.py`

**Step 1: Write the test**

Add to `TestSetPreviewCLI` class:

```python
    def test_error_when_invalid_file_type(self, temp_dir):
        """CLI exits with error when image is not png/gif."""
        from typer.testing import CliRunner

        db_path = temp_dir / "test.db"
        conn = index.get_db(db_path)
        conn.close()

        bad_file = temp_dir / "preview.jpg"
        bad_file.touch()

        runner = CliRunner()
        result = runner.invoke(index.app, [
            "set-preview",
            "TestPack",
            str(bad_file),
            "--db", str(db_path)
        ])

        assert result.exit_code == 1
        assert "must be .png or .gif" in result.stdout
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest test_index.py::TestSetPreviewCLI::test_error_when_invalid_file_type -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test_index.py
git commit -m "test: add CLI error handling test for invalid file type"
```

---

### Task 10: Run all tests and verify

**Step 1: Run all tests**

Run: `uv run pytest test_index.py -v`
Expected: All tests PASS

**Step 2: Commit final changes if any**

```bash
git status
```

---

### Task 11: Manual verification

**Step 1: Test with real data**

Run the command against the actual database to verify it works:

```bash
# Check current packs
uv run search.py packs | grep -i penusbmic

# Run set-preview with convention-based lookup
uv run index.py set-preview "penusbmic_*" --db assets.db

# Or with explicit path
uv run index.py set-preview "penusbmic_Dungeon" /path/to/preview.gif --db assets.db
```

**Step 2: Verify in web UI**

Open http://localhost:5173 and check that pack previews display correctly.
