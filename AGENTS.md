# TF3 Companion contributor guide

TF3 Companion is an unofficial, local-first, read-only Transport Fever 3 data analyst. Keep code, comments, errors and documentation in English; MCP agents answer players in their own language. The player decides and executes all game changes. Never change a player's data or installed mods without explicit authorization.

## Layout

- `src/tf3companion/`: `paths` (platform data dir and game paths), `luadata` (game Lua table format), `snapshot` (typed view), `store` (SQLite history and decisions), `analysis` (findings/opportunities), `export` (XLSX), `service` (`Companion` use cases), `cli`, `mcp_server`.
- `src/tf3companion/knowledge/`: shipped English topics `mechanics`, `strategy`, `cargo_economy`, `snapshot_schema`, loaded through `importlib.resources`. Cite sources or mark inference/unverified claims; do not ship verbatim game code.
- `mod/tf3_companion_bridge/`: read-only Lua bridge; `content/tf3_companion/bridge.script.lua` handles `guiUpdate`. Script files export a global `data()` function.
- `tests/`: regression fixtures and tests; no real player data.
- `openspec/`: specifications and change plans. `docs/ROADMAP.md` records the delivery sequence.

## Commands

```sh
uv sync
uv run pytest
uv run tf3c --help
uv run tf3c status
uv run tf3c mcp
```

Use `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` for isolated test locations. The database is `companion.db` in the platform user-data directory, not in the repo. This version uses one store; save isolation is planned separately. Keep databases, notes, exports and snapshots out of version control.

## Change workflow

Use `openspec list` to identify the active change. Read its proposal, design, specs and tasks under `openspec/changes/<change>/` before editing. Use `openspec instructions <artifact> --change <change> --json` when creating artifacts. Update task checkboxes only after their acceptance criteria are met. Validate the plan with `openspec validate <change>` and run the applicable regression suite after changes are integrated.

New analysis belongs in `analysis.py`, exposed through `service.py` and, when appropriate, `mcp_server.py`; retain explainable evidence and stable finding codes. New snapshot fields need a bridge collector and a `snapshot_schema` update; bump schema version for incompatible changes. Reject snapshots newer than the supported schema rather than silently interpreting them.

## In-game test loop

Only with the player's approval:

1. Install the mod with `scripts/install-mod.sh` (Windows without a POSIX shell: copy the mod folder into the game's `staging_area`).
2. Enable **TF3 Companion Bridge** for the save, reload the save, and save it.
3. Run `uv run tf3c refresh`.
4. Run `uv run tf3c log`; look for `[tf3c] snapshot written` and inspect collection errors.

The mod writes only through `app.saveUserdata("towns_industries", ...)`, using `tf3c_snap_<gameTime>` with 15-digit padding. Requests use `tf3c_request`. Always list the folder with `app.getAllUserdata` before loading a request: loading a missing file causes a red game error even under `pcall`. Do not add unsupported output sinks or issue simulation commands.

`CLAUDE.md` is a symlink to this guide. The player-facing analyst persona belongs in the MCP server instructions, not here.
