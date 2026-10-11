# Design

## Context

Prototype layout: `src/tf3advisor/` (≈2,100 lines, Portuguese user-facing strings), `mod/alexandrevl_tf3_bridge/`
(one 934-line Lua game script on `guiUpdate`), `knowledge/*.md` in Portuguese, `data/tf3.db` inside the repo,
`scripts/install-mod.sh` (macOS paths). Paths come from `config.py`, which already supports
`TF3_USERDATA_DIR`/`TF3_DATA_DIR` overrides but auto-detects only the macOS Steam folder.

In-game facts learned while building the prototype (build 40420, macOS):
- `io` is not usable from the game script; `app.saveUserdata("tf3_bridge", …)` is rejected
  ("The directory you trying to access is not available or invalid"); `app.saveUserdata("towns_industries", …)` works.
- `app.loadUserdata` on a missing file shows a red in-game error even under `pcall`; the mod lists the
  folder with `app.getAllUserdata` first.
- `.script.lua` files must export through a global `data()` function.
- A monthly snapshot of a 99-line/339-vehicle save is ≈770 KB on disk and ≈570 KB as JSON.

The repository has no commits yet, so this change can rename freely with no history to preserve.

## Goals / Non-Goals

**Goals:**
- One English, consistently named codebase that later changes extend.
- Player data outside the source tree; knowledge shipped inside the package.
- Keep the author's existing history usable after the rename.

**Non-Goals:**
- Windows auto-detection of the game folder (change `cross-platform-and-saves`); the `TF3C_USERDATA_DIR`
  override works on every OS meanwhile.
- Per-save separation; this change still keeps a single store.

## Decisions

### D1 — Names
`tf3companion` / `tf3-companion` / `tf3c`, MCP server `tf3-companion`, mod `tf3_companion_bridge`,
content folder `content/tf3_companion/`, Lua files `bridge.gs.lua` and `bridge.script.lua` keep their roles.
Environment variables `TF3C_USERDATA_DIR` and `TF3C_DATA_DIR` replace the `TF3_*` ones.
Alternative `tf3` as CLI was rejected: too generic for PATH and PyPI.

### D2 — Single output sink
Delete the `io:tf3_bridge` and `userdata:tf3_bridge` sinks and the sink-probing loop. The writer calls
`app.saveUserdata("towns_industries", "tf3c_snap_<t>", tbl)`; the request reader lists `towns_industries`
and loads `tf3c_request` only if present. Python side: `paths.snapshot_folder = <userdata>/towns_industries`,
file regex `^tf3c_snap_(\d+)\.lua$`, request file `towns_industries/tf3c_request.lua`.
Keeping fallbacks was rejected: they never worked and each failed attempt costs a red error on load.

### D3 — Data directory
`platformdirs.user_data_path("tf3-companion", appauthor=False, roaming=False)`:
macOS `~/Library/Application Support/tf3-companion`, Windows `%LOCALAPPDATA%\tf3-companion`,
Linux `~/.local/share/tf3-companion`. Contents: `companion.db`, `notes.md`, `exports/`.
`TF3C_DATA_DIR` overrides. Repo `data/` is removed from the tree and kept in `.gitignore`.

### D4 — Knowledge as package data
Move `knowledge/` to `src/tf3companion/knowledge/` with English file names
(`mecanicas→mechanics`, `estrategia→strategy`, `economia_cargas→cargo_economy`, `dados→snapshot_schema`),
read through `importlib.resources`. `partida.md` is not shipped: its content becomes the author's `notes.md`.
Source conventions (`WIKI:`, `BASE:`, `ECO:` prefixes, `[INFERENCE]`, `[UNVERIFIED]`) are kept; any verbatim
game code found during translation is paraphrased.

### D5 — Notes
`notes.md` in the data dir. `save_notes(append: str | None)` returns the whole file; with `append` it first adds
`## <game date of latest snapshot or "no snapshot">` + the text. CLI `tf3c notes [--append TEXT]`.
Per-save placement comes with save identity in the next change.

### D6 — Finding codes and English categories
Add `code: str` as the first field of `Finding`. Codes listed in the `company-analysis` spec.
Categories become `finance | lines | vehicles | industries | data`. Number formatting stays `{:,}`.

### D7 — Opening files
Replace `open -a Numbers` with a helper: macOS `open <file>`, Windows `os.startfile`, otherwise `xdg-open`.

### D8 — Schema guard
`Snapshot.from_file` raises a clear error when `meta.schemaVersion > SUPPORTED_SCHEMA`; ingest records it as failed.

### D9 — Agent instructions
`AGENTS.md` becomes a contributor guide (layout, commands, conventions, OpenSpec workflow, in-game test loop).
The analyst persona moves verbatim-in-meaning to the MCP server `instructions` string in English, including
"answer in the user's language". `CLAUDE.md` stays a symlink to `AGENTS.md`.

### D10 — One-off migration of the author's data (not shipped)
1. Copy `data/tf3.db` → `<data dir>/companion.db` (schema unchanged; `source_file` values keep old names, harmless).
2. Write `notes.md` from `knowledge/partida.md` (translated).
3. Import any remaining prototype snapshot files into the working database without deleting them.
4. Preserve the installed prototype and original database as local backups. Install the renamed mod
   only for a coordinated player-controlled reload; avoid enabling both collectors in the same save.

## Risks / Trade-offs

- [Player must re-enable the mod per save] → documented in README/troubleshooting; the mod has no add/remove severity.
- [Knowledge translation drifts in meaning] → translate file by file, keep every source reference, diff headings count.
- [Live collector not yet switched] → report the pending reload explicitly; do not claim the new refresh round trip was verified.
- [MCP clients configured for `tf3`] → update `.mcp.json`; only the author is affected.
