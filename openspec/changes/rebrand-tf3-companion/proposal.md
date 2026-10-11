# Proposal

## Why

The prototype ("tf3advisor") works for one player on one Mac: strings are Portuguese, the player's notes
and database live inside the repository, the mod id carries a personal prefix and the output path still
tries two sinks that never worked. Before the project can be shared as **TF3 Companion**, it needs a
clean, English, product-shaped baseline that every later change builds on.

## What Changes

- **BREAKING** Python package `tf3advisor` → `tf3companion` (distribution `tf3-companion`), CLI `tf3` → `tf3c`,
  MCP server name `tf3` → `tf3-companion`, service class `Advisor` → `Companion`, `config.py` → `paths.py`.
- **BREAKING** Mod id `alexandrevl_tf3_bridge` → `tf3_companion_bridge`, display name "TF3 Companion Bridge",
  content folder `tf3_companion/`, log prefix `[tf3c]`. Players re-enable the mod once per save.
- **BREAKING** The mod writes only through the sink that works in practice:
  `towns_industries/tf3c_snap_<gameTime>.lua`; refresh requests use `towns_industries/tf3c_request.lua`.
  The `io` sink and the `tf3_bridge/` folder are removed; `scripts/install-mod.sh` no longer creates it.
- All code comments, docstrings, CLI help, MCP tool descriptions, finding texts and error messages in English.
  Findings gain a stable `code` so agents and UIs can translate them.
- Player data moves out of the repo into the platform user-data directory (`TF3C_DATA_DIR` override).
- Knowledge base translated to English and shipped as package data: `mechanics`, `strategy`, `cargo_economy`,
  `snapshot_schema`. Save-specific notes (today `knowledge/partida.md`) become per-save notes in the data
  dir, read and appended through a new `save_notes` MCP tool and `tf3c notes` command.
- Opening an exported spreadsheet uses the OS default application (no hard-coded Apple Numbers).
- `AGENTS.md` becomes a short contributor guide in English; the player-facing analyst persona stays
  available to agents through the MCP server instructions (fully reworked later in `agent-experience`).
- The existing history of the author's save is migrated once into the new data dir (manual step, not shipped code).
- Baseline specs are written for the behaviour that exists today, so later changes can extend them.

## Capabilities

### New Capabilities
- `snapshot-bridge`: what the in-game mod collects, when it writes a snapshot, where, and that it is read-only.
- `snapshot-ingest`: how snapshot files become stored history, including partial/malformed files and file retention.
- `company-analysis`: findings and opportunities computed from a snapshot and its predecessor.
- `decision-journal`: recording, updating and listing decisions stamped with the game date.
- `agent-interface`: the MCP tool surface and its error behaviour.
- `knowledge-base`: shipped game-knowledge topics and per-save notes.
- `companion-cli`: the `tf3c` command surface.

### Modified Capabilities
- (none; no specs exist yet)

## Impact

- Code: every module in `src/`, `mod/`, `scripts/install-mod.sh`, tests, `pyproject.toml`, `.mcp.json`, `README.md`, `AGENTS.md`, `knowledge/`.
- Dependencies: adds `platformdirs`.
- Player: must enable "TF3 Companion Bridge" in the save's mod list and save once; old `tf3_bridge_snap_*` files are no longer read.

## Out of scope

- Windows/Linux game discovery, save identity, `doctor`, CLI mod install (change `cross-platform-and-saves`).
- New analyses, reports, MCP prompts/resources, release docs and CI (later changes).
- Publishing to GitHub, PyPI or mod.io.
