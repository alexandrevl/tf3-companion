# Proposal

## Why

TF3 Companion only finds the game on macOS and keeps one history for everything it reads. Most Transport
Fever players are on Windows, and anyone with two games would see their histories mixed. Installation
still needs a bash script. These block any public release.

## What Changes

- Game discovery on Windows, macOS and Linux (Steam/Proton): Steam root from the registry or default
  locations, every Steam account folder holding TF3 data, explicit override required for ambiguous accounts.
- `tf3c doctor`: one report of what was found (OS, Steam root, accounts, userdata, mod installed/version,
  snapshot files, latest snapshot age, game log, data dir, active save) with a fix for each problem.
- `tf3c mod install` / `tf3c mod uninstall`: copy the mod shipped inside the Python package into the game's
  `staging_area`; `scripts/install-mod.sh` is removed. **BREAKING** for anyone using the script.
- Save identity: snapshots carry a persistent bridge-owned lineage id (never a town-id fingerprint); each save gets its own
  folder `<data>/saves/<saveId>/` with `companion.db`, `notes.md`, `reports/`, `exports/`.
  **BREAKING** the single `<data>/companion.db` and `<data>/notes.md` move into the save folder.
- Save selection: the active save follows the newest snapshot; `tf3c saves` lists saves,
  `tf3c saves use <id|label>` pins one, `tf3c saves label <id> <text>` names it; MCP tools `list_saves` and `use_save`.
- Snapshot interval set from the companion: `tf3c config snapshots-per-year <1|4|12>` is carried in the request
  file and honoured by the mod (default 12). Mod gains `meta.companyName` when the API exposes it; schema version 2.
- Stored snapshots are compressed in the database to keep long games small.

### Implemented setup subset

Portable discovery, independent read-only diagnostics, safe bundled-mod installation/removal and wheel
asset mapping are implemented. The existing single-store paths remain compatible. Regression tests
use isolated fake Steam trees; native Windows/Linux layouts and packaged-wheel behavior remain
acceptance gates until exercised. No installer is run against a player's game during development.
Save lineage, automatic per-save storage and interval configuration remain unimplemented pending
the player-controlled API persistence probe; none is implied by setup diagnostics.

## Capabilities

### New Capabilities
- `game-discovery`: locating the TF3 userdata, staging area and game log on each OS, and the `doctor` report.
- `mod-installation`: installing and removing the bridge mod from the CLI.
- `save-management`: save identity, per-save storage, listing, pinning and labelling saves.

### Modified Capabilities
- `snapshot-bridge`: interval, company name and verified persistent lineage id, with lineage-scoped filenames (schema 2).
- `snapshot-ingest`: ADDED requirements for routing snapshots to saves and compressed storage.
- `companion-cli`: ADDED requirements for `doctor`, `mod`, `saves` and `config` commands.
- `agent-interface`: ADDED requirements for `list_saves`, `use_save` and save info in `status`.

## Impact

- Code: `paths.py`, new `discovery.py` and `saves.py`, `store.py`, `service.py`, `cli.py`, `mcp_server.py`, mod script, packaging (mod as package data).
- Player: the author's database and notes are moved once into the verified lineage folder before release (design D6); no silent automatic grouping of legacy snapshots.
- Tests: discovery covered with fake directory trees for each OS; no Windows machine is available to the author.

## Out of scope

- Non-Steam storefronts (if any) beyond the `TF3C_USERDATA_DIR` override.
- Merging or splitting save histories by hand.
- A snapshot "light" mode; compression addresses size instead (see design).
