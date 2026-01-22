# CLI Plain Text Output Design

## Summary

Convert `search.py` CLI output from Rich formatted tables to plain TSV (tab-separated values) for unix-style piping. Add a `help` subcommand for discoverability.

## Output Format

All commands output TSV to stdout:
- One record per line
- Fields separated by tabs
- No headers
- Errors to stderr

### search

```
42	/full/path/to/goblin_attack.png	32x32 (4f)	creatures	animated,creature
```

Fields: ID, path, size, pack, tags

### packs

```
1	creatures	1.0	245	/path/to/preview.png
```

Fields: ID, name, version, asset_count, preview_path

### tags

```
animated	156
creature	89
```

Fields: tag, count

### stats

```
packs	5
assets	1234
tags	89
png	980
gif	254
```

Fields: key, value (filetypes listed after totals)

### info

```
/full/path/to/goblin_attack.png
pack	creatures
type	png
size	1234
dimensions	32x32
frames	4	8x8
tags	animated,creature,goblin
colors	#ff0000:45%,#00ff00:30%
related	goblin_attack_shadow.png:shadow,goblin_attack.gif:preview
```

Key-value pairs, tab-separated. First line is always the path.

### similar

```
3	45	/path/to/orc_attack.png	creatures
5	67	/path/to/troll_attack.png	creatures
```

Fields: distance, ID, path, pack

## Help Command

Add `help` subcommand alongside existing `--help`:

```
$ search.py help

search - Search your game asset index

Commands:
  search    Search assets by name, tags, or filters
  packs     List all indexed packs
  tags      List all tags with counts
  info      Show detailed info for an asset
  stats     Show index statistics
  similar   Find visually similar assets
  help      Show help for a command

Use 'search.py help <command>' for details.
```

```
$ search.py help search

search - Search assets by name, tags, or filters

Usage: search.py search [QUERY] [OPTIONS]

Arguments:
  QUERY    Search filename/path

Options:
  -t, --tag TAG      Filter by tag (can repeat)
  -c, --color COLOR  Filter by dominant color (hex or name)
  -p, --pack PACK    Filter by pack
  --type TYPE        Filter by filetype
  --db PATH          Path to assets.db
  -n, --limit N      Max results (default: 50)
```

## Implementation

### Dependencies

- Remove `rich` from inline script dependencies
- Keep `typer`

### Changes

1. Remove Rich imports and console global
2. Replace `console.print()` with `print()` / `print(..., file=sys.stderr)`
3. Replace table rendering with TSV print statements
4. Add `help` command function
5. Use `a.path` instead of `a.filename` in output

### Files

- `search.py` only
